"""Opt-in weekly evidence record; extraction itself has no school dependency."""
from dataclasses import dataclass

from .delivery_contracts import WeeklyNote
from ..intervention.followup_extractor import EVIDENCE_CONTRACT


@dataclass(frozen=True)
class FollowupWeeklyNote(WeeklyNote):
    evidence_contract: str = EVIDENCE_CONTRACT

    def __post_init__(self):
        super().__post_init__()
        if self.evidence_contract != EVIDENCE_CONTRACT:
            raise ValueError('unsupported follow-up evidence contract')
