"""Frozen comparable-need denominator; withdrawal never removes members."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccessCohort:
    attribute: str
    group: str
    condition_at_start: str
    support_type: str
    student_ids: tuple[str, ...]
