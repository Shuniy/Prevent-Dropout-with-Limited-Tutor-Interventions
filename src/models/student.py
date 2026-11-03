"""Plain student models matching the processed and synthetic CSV schemas."""

from dataclasses import dataclass, field

try:
    from ..utils.enums import SupportType
except ImportError:  # Direct script entry point.
    from utils.enums import SupportType


@dataclass
class Student:
    student_id: str
    school_id: str

    age_years: int
    sex_source: str
    rural_residence: bool
    family_size_gt3: bool
    parents_apart: bool
    mother_education_code: int
    father_education_code: int
    mother_job: str
    father_job: str
    guardian: str

    travel_time_category: int
    study_time_category: int
    past_failures_count: int
    school_support_existing: bool
    family_support_existing: bool
    paid_classes_existing: bool
    extracurricular: bool
    nursery_attended: bool
    higher_education_aspiration: bool
    internet_at_home: bool

    family_relationship_rating: int
    health_self_rating: int
    anchor_grade1_0_20: int
    math_grade1_0_20: int | None

    # derived features
    @property
    def no_home_internet(self) -> bool:
        return not self.internet_at_home

    @property
    def travel_over_30min(self) -> bool:
        return self.travel_time_category >= 3

    @property
    def both_parents_education_at_most_2(self) -> bool:
        return (
            self.mother_education_code <= 2
            and self.father_education_code <= 2
        )

    @property
    def disadvantage_proxy_count(self) -> int:
        return sum(
            (
                self.both_parents_education_at_most_2,
                self.no_home_internet,
                self.travel_over_30min,
            )
        )

    @property
    def disadvantage_proxy_group(self) -> bool:
        return self.disadvantage_proxy_count >= 2

    @property
    def learning_gap(self) -> float:
        """
        As per analysis of the dataset, the average anchor grade is 11.39 and the average math grade is 10.94
        Average anchor grade across all schools: 11.39
        Average math grade across all schools: 10.94
        Average anchor grade by math and anchor combined (when math_grade1_0_20 is not null):
        11.513054830287206
        let's say using learning gap as a proxy for performance, where learning gap is defined as (10 - anchor_grade1_0_20) / 10, capped between 0 and 1
        
        Calculate the learning gap based on the average of anchor_grade1_0_20 and math_grade1_0_20.
        If math_grade1_0_20 is None, only anchor_grade1_0_20 is used for the calculation.
        The learning gap is normalized to a value between 0 and 1, where 0 indicates no learning gap and 1 indicates the maximum learning gap.
        
        """
        grades = [self.anchor_grade1_0_20]

        if self.math_grade1_0_20 is not None:
            grades.append(self.math_grade1_0_20)

        average_grade = sum(grades) / len(grades)
        return min(1.0, max(0.0, (10 - average_grade) / 10))


    @property
    def need_profile(self) -> list[dict]:
        """Ranked hypothetical support needs derived from current properties.

        Severity lies in [0, 1]. It is a scenario priority, not dropout risk or
        treatment benefit. Optional simulation inputs stay unknown when absent.
        Each access returns a fresh profile so source changes are reflected.
        """
        attendance = getattr(self, "initial_attendance_fraction_assumed", None)
        engagement = getattr(self, "initial_engagement_assumed", None)
        for name, value in (("attendance", attendance), ("engagement", engagement)):
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"initial {name} must be between 0 and 1")
        problems = []

        def add(problem: str, support_type: str, severity: float) -> None:
            problems.append({"problem": problem, "support_type": support_type,
                             "severity": round(severity, 4)})

        if getattr(self, "enrolled_initial_assumed", None) is False:
            add("return_to_learning", "reentry_support", 1.0)
        if self.learning_gap > 0 or self.past_failures_count > 0:
            add("learning_gap", "tutoring", max(self.learning_gap, min(1, self.past_failures_count / 4)))
        if attendance is not None and attendance < 0.85:
            add("attendance_routine", "attendance_planning", 1 - attendance)
        if self.no_home_internet:
            add("digital_access", "device_access", 0.5)
        if self.travel_over_30min:
            add("long_journey", "transport_assessment", (self.travel_time_category - 2) / 2)
        if self.study_time_category == 1:
            add("study_routine", "homework_support", 0.25)
        if self.family_relationship_rating <= 2:
            add("family_communication", "family_liaison", (3 - self.family_relationship_rating) / 3)
        if self.health_self_rating <= 2:
            add("wellbeing_checkin", "wellbeing_checkin", (3 - self.health_self_rating) / 3)
        if engagement is not None and engagement < 0.6:
            add("participation_opportunities", "peer_support", 1 - engagement)
        if getattr(self, "financial_need_verified", None) is True:
            add("verified_financial_need", "family_finances", 0.75)
        if not problems:
            add("routine_learning_checkin", "tutoring", 0.0)
        problems.sort(key=lambda problem: (-problem["severity"], problem["problem"]))
        return problems

    @property
    def need_score(self) -> float:
        """Highest need severity, used to prioritize scarce mentor places."""
        return self.need_profile[0]["severity"]

    @property
    def primary_support_type(self) -> SupportType:
        """Support addressing the highest need; ties use the concern name."""
        return self.need_profile[0]["support_type"]

    @property
    def initial_scores(self) -> dict[str, float | None]:
        """Numeric inputs and support priority, keeping dropout risk unknown."""
        return {
            "learning_gap_0_1": self.learning_gap,
            "attendance_fraction_assumed": getattr(self, "initial_attendance_fraction_assumed", None),
            "engagement_assumed": getattr(self, "initial_engagement_assumed", None),
            "support_priority_0_1": self.need_score,
            "school_dropout_risk": None,
        }


@dataclass
class StudentSimulation(Student):
    initial_attendance_fraction_assumed: float
    initial_engagement_assumed: float
    weeks_since_offer: int
    support_sessions_completed: int
    enrolled_initial_assumed: bool
    financial_need_verified: bool | None


@dataclass
class StudentInterventionProfile:
    """One simulated programme, kept separate from the source CSV record.

    Problems and priority scores are declared scenario rules, not diagnoses or
    predicted school-dropout risk. Numeric inputs are not changed by LLM findings.
    """

    student_id: str
    dataset_profile: dict
    initial_scores: dict[str, float | None]
    problems: list[dict]
    planned_sessions: int
    mentor_id: str | None = None
    history_id: str | None = None
    sessions_completed: int = 0
    status: str = "unassigned"
    session_reports: list[dict] = field(default_factory=list)
