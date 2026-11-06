"""Safe trajectory-note renderer: accepts observable events, never an environment."""

from dataclasses import dataclass
import math

from ..observations.observable_events import Note, ObservableEvent, SIGNALS, synthetic_creation_time
from ..utils.keyed_random import keyed_uniform


# Phrase -> separate extraction concepts. Also the declared synthetic language model.
PHRASES = {
    "The school reports regular participation in recent activities.":
        ("participation", "reported", "unknown", "present", "regular", "unknown", "unknown"),
    "The student reports difficulty completing assignments.":
        ("academic_difficulty", "reported", "unknown", "present", "difficulty", "unresolved", "unknown"),
    "The school reports low participation in recent activities.":
        ("participation", "reported", "unknown", "present", "low", "unknown", "unknown"),
    "The school reports no recent contact with the student.":
        ("participation", "reported", "unknown", "absent", "no_contact", "unknown", "unknown"),
    "The student completed the scheduled mentoring appointments.":
        ("mentoring_support", "observed", "unknown", "present", "unknown", "unknown", "completed"),
    "The student reports greater participation, but progress is not yet consistent.":
        ("participation", "reported", "improved", "present", "unknown", "partially_resolved", "unknown"),
    "The student reports that transport remains a barrier; the support application is pending.":
        ("support_barrier", "reported", "unchanged", "present", "unknown", "unresolved", "pending"),
    "The student denies difficulty completing assignments.":
        ("academic_difficulty", "reported", "unknown", "absent", "unknown", "unknown", "unknown"),
    "There is insufficient evidence about participation.":
        ("participation", "insufficient_evidence", "unknown", "unknown", "unknown", "unknown", "unknown"),
    "Reports about participation conflict and remain unresolved.":
        ("participation", "conflicting", "unknown", "unknown", "unknown", "unknown", "unknown"),
    "The school reports that participation has worsened since the previous observation.":
        ("participation", "reported", "worsened", "present", "unknown", "unknown", "unknown"),
}
SIGNAL_PHRASES = dict(zip(SIGNALS, tuple(PHRASES)[:4]))


@dataclass(frozen=True)
class NoteQuality:
    omission_probability: float = 0.0
    conflict_probability: float = 0.0
    misleading_probability: float = 0.0
    delay_probability: float = 0.0
    delay_months: int = 1
    ambiguity_probability: float = 0.0
    negation_probability: float = 0.0
    partial_reporting_probability: float = 0.0

    def __post_init__(self):
        for name in ("omission_probability", "conflict_probability", "misleading_probability", "delay_probability",
                     "ambiguity_probability", "negation_probability", "partial_reporting_probability"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be within [0, 1]")
        if type(self.delay_months) is not int or self.delay_months < 1:
            raise ValueError("delay_months must be positive")


def render_note(event: ObservableEvent, *, seed, quality=NoteQuality()):
    if not isinstance(event, ObservableEvent):
        raise TypeError("note renderer accepts only ObservableEvent")
    draw = lambda name: keyed_uniform(seed, event.student_id, event.event_month, "note:" + name)
    pieces = []
    if draw("omission") >= quality.omission_probability:
        signal = event.signal
        if draw("misleading") < quality.misleading_probability:
            signal = SIGNALS[(SIGNALS.index(signal) + 1) % len(SIGNALS)]
        phrase = SIGNAL_PHRASES[signal]
        if draw("ambiguity") < quality.ambiguity_probability:
            phrase = "There is insufficient evidence about participation."
        elif signal == "assignment_difficulty" and draw("negation") < quality.negation_probability:
            phrase = "The student denies difficulty completing assignments."
        elif draw("partial_reporting") < quality.partial_reporting_probability:
            phrase = "The student reports greater participation, but progress is not yet consistent."
        pieces.append(phrase)
        if draw("conflict") < quality.conflict_probability:
            pieces.extend([SIGNAL_PHRASES[SIGNALS[(SIGNALS.index(signal) + 2) % len(SIGNALS)]],
                           "Reports about participation conflict and remain unresolved."])
    if event.support_completed:
        pieces.append("The student completed the scheduled mentoring appointments.")
    if not pieces:
        pieces.append("There is insufficient evidence about participation.")
    delay = quality.delay_months if draw("delay") < quality.delay_probability else 0
    return Note(f"{event.event_id}:note", event.student_id, event.mentor_id, event.programme_id,
                "programme" if event.programme_id else "monitoring", event.event_month,
                synthetic_creation_time(event.event_month), event.available_from_month + delay,
                " ".join(pieces), (event.event_id,))
