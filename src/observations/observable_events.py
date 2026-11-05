"""Controller-authorized records. No true condition or effect parameter belongs here."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SIGNALS = ("regular_participation", "assignment_difficulty", "low_participation", "no_recent_contact")


@dataclass(frozen=True)
class ObservableEvent:
    event_id: str
    student_id: str
    event_month: int
    available_from_month: int
    signal: str
    mentor_id: str | None = None
    programme_id: str | None = None
    support_completed: bool = False
    model_version: str = "synthetic_observation_v1"

    def __post_init__(self):
        if (not self.event_id or not self.student_id or self.signal not in SIGNALS
                or type(self.event_month) is not int or self.event_month < 0
                or type(self.available_from_month) is not int
                or self.available_from_month <= self.event_month
                or type(self.support_completed) is not bool
                or (self.mentor_id is None) != (self.programme_id is None)
                or (self.support_completed and self.programme_id is None)):
            raise ValueError("invalid observable event identity, timing, signal or delivery record")


@dataclass(frozen=True)
class EnrollmentRecord:
    """Declared exact administrative registry, shared by every information mode."""
    student_id: str
    event_month: int
    available_from_month: int
    enrolled: bool

    def __post_init__(self):
        if (not self.student_id or type(self.enrolled) is not bool
                or type(self.event_month) is not int or self.event_month < 0
                or type(self.available_from_month) is not int
                or self.available_from_month <= self.event_month):
            raise ValueError("invalid administrative enrollment record")


@dataclass(frozen=True)
class Note:
    note_id: str
    student_id: str
    mentor_id: str | None
    programme_id: str | None
    note_type: str
    event_month: int
    creation_time: str
    available_from_month: int
    text: str
    source_event_ids: tuple[str, ...]
    generator_version: str = "observable_note_v1"

    def __post_init__(self):
        if (not self.note_id or not self.student_id or not self.source_event_ids
                or type(self.event_month) is not int or self.event_month < 0
                or type(self.available_from_month) is not int
                or self.available_from_month <= self.event_month
                or self.note_type not in ("monitoring", "programme")
                or (self.mentor_id is None) != (self.programme_id is None)
                or (self.note_type == "programme") != (self.programme_id is not None)):
            raise ValueError("notes require identity, provenance and next-cutoff availability")
        created = datetime.fromisoformat(self.creation_time)
        if created.tzinfo is None:
            raise ValueError("note creation time must include a timezone")
        epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
        if not (epoch + timedelta(days=30 * self.event_month) <= created
                <= epoch + timedelta(days=30 * self.available_from_month)):
            raise ValueError("note creation must follow its event and precede availability")


def synthetic_creation_time(event_month):
    """Reproducible synthetic calendar, separate from event/availability indices."""
    return (datetime(2026, 1, 1, tzinfo=timezone.utc)
            + timedelta(days=30 * event_month, hours=23)).isoformat()
