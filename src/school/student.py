"""Plain student models matching the processed and synthetic CSV schemas."""

from dataclasses import dataclass

from ..utils.enums import SupportType


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
    def disadvantage_proxy_count(self) -> int | None:
        if any(getattr(self, name) is None for name in (
            "mother_education_code", "father_education_code", "internet_at_home",
            "travel_time_category",
        )):
            return None
        return sum(
            (
                self.both_parents_education_at_most_2,
                self.no_home_internet,
                self.travel_over_30min,
            )
        )

    @property
    def disadvantage_proxy_group(self) -> bool | None:
        count = self.disadvantage_proxy_count
        return None if count is None else count >= 2

    @property
    def learning_gap(self) -> float:
        """Grade shortfall below 10, normalized to [0, 1]."""
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
        from .needs import calculate_needs
        return calculate_needs(self)

    @property
    def need_score(self) -> float:
        """Highest need severity, used to prioritize scarce mentor places."""
        return self.need_profile[0]["severity"]

    @property
    def primary_support_type(self) -> SupportType:
        """Support addressing the highest need; ties use the concern name."""
        return self.need_profile[0]["support_type"]
