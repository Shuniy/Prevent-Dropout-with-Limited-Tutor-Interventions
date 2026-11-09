"""Session-linked, conditionally independent synthetic weekly measurements.

The environment alone supplies end-of-week truth. Mentor and school signals are
independent conditional on that same latent condition, with the SAME explicitly
declared ObservationConfig likelihood (including the uniform misleading mixture).
This is a research assumption, not a calibrated measurement or treatment effect.
"""
from dataclasses import dataclass
import numpy as np

from .student_condition import STATES
from .transition_model import keyed_uniform
from ..observations.observable_events import SIGNALS


MENTOR_OBSERVATION_CONTRACT = 'weekly_mentor/independent_same_likelihood/v1'


@dataclass(frozen=True)
class MentorSessionObservation:
    event_id: str
    student_id: str
    source_week: int
    available_week: int
    signal: str
    mentor_id: str
    programme_id: str
    session_id: str
    delivery_event_id: str
    observation_contract: str = MENTOR_OBSERVATION_CONTRACT

    def __post_init__(self):
        if (not all((self.event_id, self.student_id, self.mentor_id, self.programme_id,
                     self.session_id, self.delivery_event_id))
                or self.signal not in SIGNALS or type(self.source_week) is not int
                or self.source_week < 1 or type(self.available_week) is not int
                or self.available_week <= self.source_week
                or self.observation_contract != MENTOR_OBSERVATION_CONTRACT):
            raise ValueError('invalid session observation provenance, timing or protocol')


class MentorSessionObservationModel:
    def __init__(self, config):
        self.config = config

    def generate(self, delivery, condition, *, seed, signal_override=None):
        """Private observation boundary; never called for a missed session."""
        if delivery.kind != 'session_delivered':
            raise ValueError('mentor condition observation requires actual delivered service')
        if signal_override is not None and signal_override not in SIGNALS:
            raise ValueError('unsupported controlled mentor signal')
        draws, values = [], {}
        for role in ('signal', 'missing', 'delay'):
            stream = f'weekly_mentor_observation/v1:{role}:{delivery.session_id}'
            value = keyed_uniform(seed, delivery.student_id, delivery.source_week, stream)
            values[role] = value
            draws.append(dict(key=(delivery.student_id, 'mentor_observation',
                delivery.source_week, delivery.session_id, role), stream=stream, uniform=value))
        if values['missing'] < self.config.missing_probability:
            return None, tuple(draws)
        row = self.config.likelihood_matrix[STATES.index(condition)]
        index = min(int(np.searchsorted(np.cumsum(row), values['signal'], side='right')), 3)
        delay = self.config.delay_months if values['delay'] < self.config.delay_probability else 0
        signal = SIGNALS[index] if signal_override is None else signal_override
        return MentorSessionObservation(delivery.session_id + ':mentor-observation:v1',
            delivery.student_id, delivery.source_week, delivery.source_week + 1 + delay,
            signal, delivery.mentor_id, delivery.programme_id, delivery.session_id,
            delivery.event_id), tuple(draws)


def render_mentor_note(event, *, seed, quality):
    """Render only an emitted observable record; no latent-state access."""
    from ..intervention.feedback_notes import render_note, MENTOR_SIGNAL_PHRASES
    from ..observations.observable_events import ObservableEvent
    from .delivery_contracts import WeeklyNote
    observable = ObservableEvent(event.event_id, event.student_id, event.source_week,
        event.available_week, event.signal, event.mentor_id, event.programme_id, False)
    rendered = render_note(observable, seed=seed, quality=quality,
        signal_phrases=MENTOR_SIGNAL_PHRASES,
        random_namespace=f'weekly_mentor_note/v1:{event.session_id}:')
    return WeeklyNote(rendered.note_id, event.student_id, event.source_week,
        rendered.available_from_month, rendered.text, rendered.source_event_ids,
        event.mentor_id, event.programme_id, event.session_id, event.delivery_event_id,
        event.observation_contract)


def validate_note_source(note, environment, cutoff, batch=None):
    """Bind programme prose to public source records, never evaluator truth.

    Delayed copies may arrive later but cannot change source time or identity.
    Lifecycle records can attest delivery workflow, never educational condition.
    """
    from ..intervention.feedback_notes import MENTOR_SIGNAL_PHRASES
    source_id = note.source_event_ids[0]
    observations = {e.event_id: e for e in environment.emitted_mentor_signals}
    events = {e.event_id: e for e in environment.events}
    observation = observations.get(source_id)
    if observation is not None:
        delivery = events.get(observation.delivery_event_id)
        if (delivery is None or delivery.kind != 'session_delivered'
                or delivery.available_week > cutoff or observation.available_week > cutoff
                or (delivery.student_id, delivery.mentor_id, delivery.programme_id,
                    delivery.session_id, delivery.source_week) !=
                   (observation.student_id, observation.mentor_id, observation.programme_id,
                    observation.session_id, observation.source_week)
                or (note.student_id, note.mentor_id, note.programme_id, note.session_id,
                    note.delivery_event_id, note.source_week, note.observation_contract) !=
                   (observation.student_id, observation.mentor_id, observation.programme_id,
                    observation.session_id, observation.delivery_event_id,
                    observation.source_week, observation.observation_contract)
                or note.available_week < observation.available_week):
            raise ValueError('mentor note delivered-session provenance mismatch')
    elif note.programme_id is not None or note.session_id is not None or source_id in events:
        event = events.get(source_id)
        if (event is None or event.available_week > cutoff or note.available_week < event.available_week
                or (note.student_id, note.mentor_id, note.programme_id, note.source_week) !=
                   (event.student_id, event.mentor_id, event.programme_id, event.source_week)
                or any((note.session_id, note.delivery_event_id, note.observation_contract))):
            raise ValueError('programme note source provenance mismatch')
        if batch is not None and any(f.field != 'mentoring_support' for f in batch.facts):
            raise ValueError('operational event cannot attest an educational condition')
    elif batch is not None and any(f.evidence in MENTOR_SIGNAL_PHRASES.values() for f in batch.facts):
        raise ValueError('mentor condition prose requires delivered-session provenance')
