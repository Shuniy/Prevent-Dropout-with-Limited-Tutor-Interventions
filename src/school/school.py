"""A small, configurable agent-based mentor allocation simulation."""

from dataclasses import replace
from .mentor_assignment import MentorAssignment
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from ..intervention import InterventionRequest, InterventionResult
from .performance import initial_performance, current_needs, apply_outcomes

from ..utils.constants import (
    DEFAULT_BUDGET,
    DEFAULT_MENTOR_COST_PER_SESSION,
    DEFAULT_NUMBER_OF_MENTORS,
    DEFAULT_NUMBER_OF_MONTHS,
    DEFAULT_NUMBER_OF_SESSIONS_PER_STUDENT,
    DEFAULT_NUMBER_OF_STUDENTS,
    DEFAULT_NUMBER_OF_STUDENTS_PER_MENTOR,
    SEED,
    create_rng,
)

from .mentor import Mentor
from ..utils.enums import SupportType
from ..utils.constants import DEFAULT_STUDENT_DATA_PATH
from .student import Student
from .allocation_policy import AllocationPolicy
from .scenario_config import ScenarioConfig
from .loading import (
    create_mentors,
    existing_assignments,
    load_students,
    mentor_can_take,
    validate_configuration,
    validate_unique_ids,
)


class School:
    """Coordinate student and mentor agents over a monthly allocation schedule.

    When explicit agents are not supplied, the school reads student agents from
    the synthetic population CSV and creates mentor agents using the defaults in
    :mod:`constants`.
    """

    def __init__(
        self,
        num_students: int = DEFAULT_NUMBER_OF_STUDENTS,
        num_mentors: int = DEFAULT_NUMBER_OF_MENTORS,
        *,
        students: Iterable[Student] | None = None,
        mentors: Iterable[Mentor] | None = None,
        student_data_path: str | Path = DEFAULT_STUDENT_DATA_PATH,
        num_months: int = DEFAULT_NUMBER_OF_MONTHS,
        budget: float = DEFAULT_BUDGET,
        mentor_cost_per_session: float = DEFAULT_MENTOR_COST_PER_SESSION,
        sessions_per_student: int = DEFAULT_NUMBER_OF_SESSIONS_PER_STUDENT,
        students_per_mentor: int = DEFAULT_NUMBER_OF_STUDENTS_PER_MENTOR,
        support_type: SupportType = "tutoring",
        seed: int = SEED,
    ) -> None:
        validate_configuration(
            num_students=num_students,
            num_mentors=num_mentors,
            num_months=num_months,
            budget=budget,
            mentor_cost_per_session=mentor_cost_per_session,
            sessions_per_student=sessions_per_student,
            students_per_mentor=students_per_mentor,
        )

        self.num_months = num_months
        self.budget = float(budget)
        self.sessions_per_student = sessions_per_student
        self.students_per_mentor = students_per_mentor
        self.support_type = support_type
        self.seed = seed
        self._rng = create_rng(seed)

        self.students = (
            list(students)
            if students is not None
            else load_students(student_data_path, num_students)
        )
        self.mentors = (
            list(mentors)
            if mentors is not None
            else create_mentors(
                num_mentors,
                num_months=num_months,
                students_per_mentor=students_per_mentor,
                sessions_per_student=sessions_per_student,
                support_type=support_type,
                cost_units_per_session=mentor_cost_per_session,
            )
        )

        validate_unique_ids(self.students, self.mentors)
        self.assignments = existing_assignments(self.students, self.mentors)
        self._initial_mentor_assignments = dict(self.assignments)
        self._initial_caseloads = {m.mentor_id: tuple(m.current_student_ids) for m in self.mentors}
        self.assignment_history: list[MentorAssignment] = []
        self.monthly_assignments: dict[int, dict[str, str]] = {}
        self.spent_budget = 0.0
        self._school_assigned_student_ids: set[str] = set()
        self._sessions_used: dict[tuple[str, int], int] = {}
        self.run_id = uuid4().hex
        self.current_month = 1
        self.performance = {s.student_id: initial_performance(s) for s in self.students}
        self.intervention_results: dict[str, InterventionResult] = {}
        self._requests: dict[str, InterventionRequest] = {}
        self.monthly_evaluations: dict = {}
        self.monthly_reports: dict = {}
        self.simulation_report: dict | None = None

    @property
    def remaining_budget(self) -> float:
        return self.budget - self.spent_budget

    @property
    def unassigned_student_ids(self) -> list[str]:
        return [
            student.student_id
            for student in self.students
            if student.student_id not in self.assignments
        ]

    def step(
        self,
        month: int,
        *,
        support_type: SupportType | None = None,
        student_support_types: dict[str, SupportType] | None = None,
        excluded_student_ids: set[str] | None = None,
        preferred_mentor_ids: dict[str, str] | None = None,
        prioritize_by_need: bool = True,
    ) -> list[MentorAssignment]:
        """Allocate students within mentor skills, capacity, sessions and budget.

        With ``prioritize_by_need``, highest current need severity goes first and
        seeded shuffling breaks ties. Support defaults to the student's primary
        need unless a caller supplies per-student or shared support explicitly.
        Students already allocated in this run are never allocated again.
        """

        if month < 1 or month > self.num_months:
            raise ValueError(f"month must be between 1 and {self.num_months}")

        # A mentor's student capacity renews at the start of every month.
        for mentor in self.mentors:
            for student_id in list(mentor.current_student_ids):
                if student_id in self._school_assigned_student_ids:
                    mentor.release_student(student_id)

        self._school_assigned_student_ids.clear()

        selected_support_type = support_type or self.support_type
        required_sessions = self.sessions_per_student
        new_assignments: list[MentorAssignment] = []

        students_this_month = list(self.students)
        self._rng.shuffle(students_this_month)
        needs = {
            s.student_id: current_needs(s, self.performance[s.student_id])[0] for s in self.students
        }
        if prioritize_by_need:
            students_this_month.sort(
                key=lambda student: needs[student.student_id]["severity"], reverse=True
            )

        for student in students_this_month:
            if student.student_id in self.assignments or (
                excluded_student_ids is not None and student.student_id in excluded_student_ids
            ):
                continue

            requested_support = (
                student_support_types[student.student_id]
                if student_support_types is not None
                else (
                    needs[student.student_id]["support_type"]
                    if prioritize_by_need and support_type is None
                    else selected_support_type
                )
            )

            eligible_mentors = [
                mentor
                for mentor in self.mentors
                if (
                    not preferred_mentor_ids
                    or student.student_id not in preferred_mentor_ids
                    or mentor.mentor_id == preferred_mentor_ids[student.student_id]
                )
                and mentor_can_take(
                    mentor,
                    student_id=student.student_id,
                    support_type=requested_support,
                    month=month,
                    required_sessions=required_sessions,
                    sessions_used=self._sessions_used.get((mentor.mentor_id, month), 0),
                    remaining_budget=self.remaining_budget,
                )
            ]
            if not eligible_mentors:
                continue

            mentor = min(
                eligible_mentors,
                key=lambda candidate: (candidate.current_caseload, candidate.mentor_id),
            )
            usage_key = (mentor.mentor_id, month)
            assignment_cost = required_sessions * mentor.cost_units_per_session

            mentor.assign_student(student.student_id)
            self.assignments[student.student_id] = mentor.mentor_id
            self._school_assigned_student_ids.add(student.student_id)
            self._sessions_used[usage_key] = (
                self._sessions_used.get(usage_key, 0) + required_sessions
            )
            self.spent_budget += assignment_cost

            assignment = MentorAssignment(
                student_id=student.student_id,
                mentor_id=mentor.mentor_id,
                support_type=requested_support,
                month=month,
                sessions=required_sessions,
                cost_units=assignment_cost,
            )
            self.assignment_history.append(assignment)
            new_assignments.append(assignment)

        self.monthly_assignments[month] = {
            assignment.student_id: assignment.mentor_id for assignment in new_assignments
        }
        return new_assignments

    def _prepare_run(self) -> dict[str, str]:
        self.reset()
        preferred = dict(self.assignments)
        for mentor in self.mentors:
            for student_id in list(mentor.current_student_ids):
                if student_id in preferred:
                    mentor.release_student(student_id)
        self.assignments.clear()
        return preferred

    def allocate_programmes(
        self, *, support_type: SupportType | None = None
    ) -> dict[int, dict[str, str]]:
        """Plan once per student without intervention or attendance claims."""
        preferred = self._prepare_run()
        for month in range(1, self.num_months + 1):
            self.current_month = month
            self.step(month, support_type=support_type, preferred_mentor_ids=preferred)
        return {month: dict(assignments) for month, assignments in self.monthly_assignments.items()}

    def run_simulation(
        self,
        intervention,
        *,
        output_dir: Path | None = None,
        support_type: SupportType | None = None,
    ) -> dict:
        """Start a fresh complete monthly school cycle using an explicit intervention."""
        from .simulation import run_simulation

        return run_simulation(self, intervention, output_dir=output_dir, support_type=support_type)

    def create_cmdp_environment(self, *, config: ScenarioConfig | None = None):
        """Create a synthetic retention world from this school's existing models.

        The world owns copied resources, simulated conditions and budget history.
        Recorded measurements and reported intervention outcomes stay separate.
        """
        from .cmdp_environment import CMDPEnvironment

        if config is None:
            config = ScenarioConfig(
                num_students=len(self.students),
                num_mentors=len(self.mentors),
                horizon=self.num_months,
                budget=self.budget,
                seed=self.seed,
                monthly_admissions=self.students_per_mentor,
                monthly_appointments=self.students_per_mentor * self.sessions_per_student,
                appointments_per_programme=self.sessions_per_student,
            )
        if (
            config.horizon != self.num_months
            or config.budget != self.budget
            or config.seed != self.seed
            or config.appointments_per_programme != self.sessions_per_student
        ):
            raise ValueError(
                "CMDP configuration must match the school's horizon, budget, seed and programme size"
            )
        return CMDPEnvironment(self.students, self.mentors, config)

    def run_cmdp(self, policy: AllocationPolicy, *, config: ScenarioConfig | None = None):
        """Run an injected allocation policy through the school's CMDP coordinator."""
        from .cmdp_simulation import CMDPSimulation

        environment = self.create_cmdp_environment(config=config)
        return CMDPSimulation(environment, policy).run()

    def run_cmdp_feedback(self, policy: AllocationPolicy, *, config: ScenarioConfig | None = None,
                          **feedback_options):
        """Step 5 sequential observations, belief estimation and the existing planner."""
        from .closed_loop_controller import ClosedLoopCMDPController

        return ClosedLoopCMDPController(self.create_cmdp_environment(config=config), policy,
                                       **feedback_options).run_episode()

    def reset(self) -> None:
        """Restore baseline performance, complete initial caseloads and seeded run state."""
        for mentor in self.mentors:
            mentor.current_student_ids[:] = self._initial_caseloads[mentor.mentor_id]
        self.assignments = dict(self._initial_mentor_assignments)
        self._school_assigned_student_ids.clear()
        self.assignment_history.clear()
        self.monthly_assignments.clear()
        self.spent_budget = 0.0
        self._sessions_used.clear()
        self._rng = create_rng(self.seed)
        self.run_id = uuid4().hex
        self.current_month = 1
        self.performance = {s.student_id: initial_performance(s) for s in self.students}
        self.intervention_results.clear()
        self._requests.clear()
        self.monthly_evaluations.clear()
        self.monthly_reports.clear()
        self.simulation_report = None

    def make_intervention_request(self, assignment: MentorAssignment) -> InterventionRequest:
        """Validate the school allocation and copy only the scalars intervention uses."""
        if assignment not in self.assignment_history or assignment.completed_sessions is not None:
            raise ValueError("request requires an unprocessed school assignment")
        if assignment.month != self.current_month:
            raise ValueError("assignment must belong to the current school month")
        mentor = next(m for m in self.mentors if m.mentor_id == assignment.mentor_id)
        if (
            self.assignments.get(assignment.student_id) != assignment.mentor_id
            or assignment.student_id not in mentor.current_student_ids
            or not mentor.supports(assignment.support_type)
        ):
            raise ValueError("assignment is not valid for this student and mentor")
        programme_id = f"{self.run_id}:{assignment.student_id}"
        if programme_id in self._requests:
            raise ValueError("programme has already been requested")
        request = InterventionRequest(
            self.run_id,
            programme_id,
            assignment.month,
            assignment.student_id,
            assignment.mentor_id,
            assignment.support_type,
            assignment.sessions,
        )
        self._requests[programme_id] = request
        return request

    def apply_intervention_result(self, result: InterventionResult) -> None:
        """Check identity and counts before exactly-once accounting/performance updates."""
        if not isinstance(result, InterventionResult):
            raise TypeError("result must be an InterventionResult")
        result.__post_init__()
        request = self._requests.get(result.programme_id)
        if request is None or any(
            getattr(result, name) != getattr(request, name)
            for name in (
                "run_id",
                "programme_id",
                "month",
                "student_id",
                "mentor_id",
                "support_type",
                "planned_sessions",
            )
        ):
            raise ValueError("result must match a requested programme")
        if result.programme_id in self.intervention_results:
            raise ValueError("programme result has already been applied")
        if result.month != self.current_month:
            raise ValueError("result must belong to the current school month")
        assignment = next(a for a in self.assignment_history if a.student_id == result.student_id)
        self._record_intervention_attendance(assignment, result.sessions_completed)
        apply_outcomes(self.performance[result.student_id], result)
        self.intervention_results[result.programme_id] = result

    def _record_intervention_attendance(
        self, assignment: MentorAssignment, completed_sessions: int
    ) -> None:
        if not 0 <= completed_sessions <= assignment.sessions:
            raise ValueError("completed sessions must be within the scheduled programme")
        position = self.assignment_history.index(assignment)
        if assignment.completed_sessions is not None:
            raise ValueError("attendance has already been recorded")
        cost = assignment.cost_units * completed_sessions / assignment.sessions
        self.spent_budget -= assignment.cost_units - cost
        key = (assignment.mentor_id, assignment.month)
        self._sessions_used[key] -= assignment.sessions - completed_sessions
        self.assignment_history[position] = replace(
            assignment, completed_sessions=completed_sessions, cost_units=cost
        )
