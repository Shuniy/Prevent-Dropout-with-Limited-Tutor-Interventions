"""Synthetic environment with hard realized resource accounting and private truth."""

from copy import deepcopy
import math
from .money import amount, programme_cost

from .loading import mentor_can_take, validate_unique_ids
from .allocation_result import AllocationResult
from .condition_estimate import ConditionEstimate
from .constraints import validate_allocation
from .decision_state import DecisionState
from .student_condition import StudentCondition
from .mentor_resource import MentorResource
from .month_record import MonthRecord
from .student_observation import StudentObservation
from .transition_model import (
    P_WAIT,
    keyed_uniform,
    programme_matrix,
    sample_condition,
    validate_matrix,
)


def initial_condition(student) -> StudentCondition | None:
    """None means outside the initial retention cohort, not simulated withdrawal."""
    enrolled = getattr(student, "enrolled_initial_assumed", None)
    if type(enrolled) is not bool:
        raise ValueError(f"{student.student_id}: known initial enrollment is required")
    for name in ("initial_attendance_fraction_assumed", "initial_engagement_assumed"):
        value = getattr(student, name, None)
        if value is None or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{student.student_id}: {name} must be known and within [0, 1]")
    if not enrolled:
        return None
    attendance = student.initial_attendance_fraction_assumed
    engagement = student.initial_engagement_assumed
    if attendance < 0.70 or engagement < 0.40:
        return StudentCondition.DISENGAGED
    # Private reset shares the public academic shortfall rule under the declared
    # first-period availability assumption. The resulting condition stays private.
    from .student import grade_shortfall
    reset_gap = grade_shortfall(student.anchor_grade1_0_20, student.math_grade1_0_20)
    if attendance < 0.85 or engagement < 0.60 or reset_gap >= 0.30:
        return StudentCondition.VULNERABLE
    return StudentCondition.STABLE


class CMDPEnvironment:
    """Only categorical condition evolves; source measurements remain unchanged.

    One step atomically validates/charges programmes, transitions everyone in the
    initial cohort (including absorbing states), records, then advances the clock.
    Initially non-enrolled students are excluded and listed separately.
    """

    def __init__(self, students, mentors, config, *, wait_matrix=None, treatment_matrix=None):
        self.config = config
        students = deepcopy(list(students))
        self._mentors = deepcopy(list(mentors))
        validate_unique_ids(students, self._mentors)
        self._wait_matrix = validate_matrix(P_WAIT if wait_matrix is None else wait_matrix)
        treatment = (
            programme_matrix(config.effect_strength)
            if treatment_matrix is None
            else treatment_matrix
        )
        self._programme_matrix = validate_matrix(treatment)
        self._conditions = {}
        self._profiles = {}
        self._programme_months = {}
        self._waiting_months = {}
        self._excluded = []
        for student in students:
            condition = initial_condition(student)
            if condition is None:
                self._excluded.append(student.student_id)
                continue
            self._conditions[student.student_id] = condition
            self._programme_months[student.student_id] = ()
            self._waiting_months[student.student_id] = 0
            self._profiles[student.student_id] = (
                student.primary_support_type,
                student.need_score,
                student.disadvantage_proxy_group,
                student.sex_source,
            )
        for mentor in self._mentors:
            if not math.isfinite(mentor.cost_units_per_session):
                raise ValueError("mentor appointment price must be finite")
            if mentor.current_student_ids:
                raise ValueError("CMDP episodes require mentors with empty initial caseloads")
        self._month = 1
        self._remaining_budget = amount(config.budget)
        self._records = []

    @property
    def records(self):
        return tuple(self._records)

    @property
    def excluded_student_ids(self):
        return tuple(self._excluded)

    @property
    def done(self):
        return self._month > self.config.horizon

    @property
    def transition_assumptions(self):
        """Declared model parameters for manifests; never realized/future draws."""
        return self._wait_matrix.tolist(), self._programme_matrix.tolist()

    def observe(self, *, fully_observed=True, estimates=()) -> DecisionState:
        """Enrollment is an assumed exact administrative observation in both modes.

        Partial mode has no condition unless an explicit as-of estimate is supplied.
        No estimate or reported LLM outcome can write the environment truth.
        """
        estimate_by_id = {}
        for estimate in estimates:
            if not isinstance(estimate, ConditionEstimate):
                raise ValueError("estimates must be validated ConditionEstimate records")
            if estimate.student_id not in self._conditions or estimate.student_id in estimate_by_id:
                raise ValueError("condition estimates must reference unique cohort students")
            if estimate.as_of_month != self._month:
                raise ValueError("condition estimate must match the current decision month")
            estimate_by_id[estimate.student_id] = estimate.condition
        observations = []
        for student_id, truth in self._conditions.items():
            support, need, disadvantage, sex = self._profiles[student_id]
            history = self._programme_months[student_id]
            observations.append(
                StudentObservation(
                    student_id,
                    truth != StudentCondition.WITHDRAWN,
                    truth if fully_observed else estimate_by_id.get(student_id),
                    support,
                    need,
                    history,
                    self._waiting_months[student_id],
                    disadvantage,
                    sex,
                )
            )
        resources = self._mentor_resources(observations, self._month)
        return DecisionState(
            self._month,
            max(0, self.config.horizon - self._month + 1),
            float(self._remaining_budget),
            tuple(observations),
            resources,
            "fully_observed_benchmark" if fully_observed else "estimated_or_unobserved",
            str(self._remaining_budget),
            tuple((month, self._mentor_resources(observations, month))
                  for month in range(self._month, self.config.horizon + 1)),
        )

    def _mentor_resources(self, observations, month):
        """Public, preannounced calendar applied to currently observed students.

        Compatibility uses fixed skills and support needs, never future truth.
        The environment has no programme-hours requirement (required_hours=0).
        """
        resources = []
        for mentor in self._mentors:
            available = mentor.availability_at(month)
            compatible = []
            for student in observations:
                if mentor_can_take(
                    mentor,
                    student_id=student.student_id,
                    support_type=student.support_type,
                    month=month,
                    required_sessions=5,
                    sessions_used=0,
                    # Compatibility is independent of affordability. Exact
                    # programme costs and budget are checked by the validator.
                    remaining_budget=math.inf,
                ):
                    compatible.append(student.student_id)
            resources.append(
                MentorResource(
                    mentor.mentor_id,
                    tuple(mentor.support_types),
                    mentor.remaining_capacity if available else 0,
                    available.max_sessions if available else 0,
                    mentor.cost_units_per_session,
                    tuple(compatible),
                )
            )
        return tuple(resources)

    def generate_observable_records(self, observation_model):
        """Privileged observation boundary, used at reset and after each transition.

        Only emitted authorized records leave this method; the note renderer and
        estimator never receive the environment's condition map.
        """
        assignments = self._records[-1].allocation.assignments if self._records else ()
        return observation_model.generate(tuple(self._conditions.items()),
            month=self._month - 1, seed=self.config.seed, assignments=assignments)

    def operational_snapshot(self, enrollment_records, *, estimates=(), risks=()):
        """Build Step 5 inputs from explicit registry records, never truth masks.

        Unlike the legacy benchmark API, waiting/eligibility here depend solely
        on these current authorized records and committed admission history.
        """
        from dataclasses import replace
        registry = {r.student_id: r for r in enrollment_records}
        if set(registry) != set(self._profiles) or len(registry) != len(enrollment_records):
            raise ValueError("operational snapshot requires unique cohort registry records")
        if any(r.event_month != self._month - 1 or r.available_from_month > self._month
               or type(r.enrolled) is not bool for r in registry.values()):
            raise ValueError("registry must be available at the current decision cutoff")
        by_id = {e.student_id: e for e in estimates}
        students = []
        for sid, (support, need, disadvantage, sex) in self._profiles.items():
            history = self._programme_months[sid]
            estimate = by_id.get(sid)
            students.append(StudentObservation(
                sid, registry[sid].enrolled,
                estimate.estimated_condition if estimate else None,
                support, need, history, self._month - 1 if registry[sid].enrolled and not history else 0,
                disadvantage, sex,
                estimate.condition_probabilities if estimate else (),
                estimate.estimate_id if estimate else None))
        snapshot = DecisionState(self._month, max(0, self.config.horizon - self._month + 1),
            float(self._remaining_budget), tuple(students), self._mentor_resources(students, self._month),
            "estimated_state", str(self._remaining_budget),
            tuple((month, self._mentor_resources(students, month))
                  for month in range(self._month, self.config.horizon + 1)))
        snapshot = replace(snapshot, estimated_student_states=tuple(estimates), risk_estimates=tuple(risks))
        snapshot.validate_estimates()
        return snapshot

    def step(self, allocation) -> MonthRecord:
        if self.done:
            raise ValueError("episode has already completed")
        if not isinstance(allocation, AllocationResult):
            raise ValueError("step requires an immutable AllocationResult")
        # Revalidate against current truth and resources, not a policy's estimate.
        state = self.observe()
        validate_allocation(state, allocation.assignments)
        assigned = {assignment.student_id for assignment in allocation.assignments}
        recipient_waits = tuple(
            self._waiting_months[item.student_id] for item in allocation.assignments
        )
        prices = {mentor.mentor_id: mentor.cost_per_appointment for mentor in state.mentors}
        spending = sum((programme_cost(prices[item.mentor_id])
                        for item in allocation.assignments), amount(0))
        self._remaining_budget -= spending
        for student_id in assigned:
            self._programme_months[student_id] += (self._month,)
        for student_id, condition in self._conditions.items():
            matrix = self._programme_matrix if student_id in assigned else self._wait_matrix
            uniform = keyed_uniform(
                self.config.seed, student_id, self._month, "environment_transition"
            )
            self._conditions[student_id] = sample_condition(condition, matrix, uniform)
            if (
                self._conditions[student_id] != StudentCondition.WITHDRAWN
                and not self._programme_months[student_id]
            ):
                # Count only full waiting months survived without a programme.
                self._waiting_months[student_id] += 1
        eligible_waits = [
            self._waiting_months[student_id]
            for student_id, condition in self._conditions.items()
            if condition != StudentCondition.WITHDRAWN
            and not self._programme_months[student_id]
        ]
        record = MonthRecord(
            self._month,
            tuple(self._conditions.items()),
            float(self._remaining_budget),
            allocation,
            tuple(
                (mentor.mentor_id, mentor.admissions, mentor.appointments)
                for mentor in state.mentors
            ),
            sum(eligible_waits) / len(eligible_waits) if eligible_waits else 0.0,
            tuple(self._waiting_months.items()),
            recipient_waits,
        )
        self._records.append(record)
        self._month += 1
        return record

    def terminal_reward(self) -> int:
        if not self.done:
            raise ValueError("terminal reward is defined after the final transition")
        # R_T = sum_i 1[s_i,T != withdrawn]; intermediate reward is zero, gamma = 1.
        return sum(
            condition != StudentCondition.WITHDRAWN for condition in self._conditions.values()
        )

    def completed_resource_totals(self):
        """Post-episode reporting only; policies never receive future resources."""
        if not self.done:
            raise ValueError("resource totals are available after the episode")
        totals = []
        for mentor in self._mentors:
            admissions = 0
            appointments = 0
            for month in range(1, self.config.horizon + 1):
                available = mentor.availability_at(month)
                if available:
                    admissions += mentor.max_active_students
                    appointments += available.max_sessions
            totals.append((mentor.mentor_id, admissions, appointments))
        return tuple(totals)
