"""An explicit estimated condition, without a truth mutation interface."""

from dataclasses import dataclass

from .student_condition import StudentCondition


@dataclass(frozen=True)
class ConditionEstimate:
    student_id: str
    as_of_month: int
    condition: StudentCondition
    provenance: str

    def __post_init__(self):
        if not isinstance(self.condition, StudentCondition):
            raise ValueError("estimated condition must be a StudentCondition")
        if type(self.as_of_month) is not int or self.as_of_month < 0:
            raise ValueError("as_of_month must be a non-negative integer")
        if not self.provenance:
            raise ValueError("condition estimates require explicit provenance")
