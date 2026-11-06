"""Declared research emissions, not calibrated measurements of source attendance."""

from dataclasses import dataclass
import math
import numpy as np

from ..observations.observable_events import EnrollmentRecord, ObservableEvent, SIGNALS
from .student_condition import STATES, StudentCondition
from .transition_model import keyed_uniform


# Rows = conditions, columns = qualitative observable signals. Every row overlaps.
DEFAULT_EMISSIONS = ((.65, .22, .10, .03), (.25, .45, .25, .05),
                     (.08, .22, .50, .20), (.03, .07, .25, .65))


@dataclass(frozen=True)
class ObservationConfig:
    emissions: tuple[tuple[float, ...], ...] = DEFAULT_EMISSIONS
    missing_probability: float = .05
    delay_probability: float = .10
    delay_months: int = 1
    misleading_probability: float = .05

    def __post_init__(self):
        rows = np.asarray(self.emissions, dtype=float)
        if (rows.shape != (4, 4) or not np.isfinite(rows).all()
                or np.any(rows < 0) or not np.allclose(rows.sum(axis=1), 1, atol=1e-12, rtol=0)):
            raise ValueError("emission rows must be four probability distributions")
        for name in ("missing_probability", "delay_probability", "misleading_probability"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be within [0, 1]")
        if type(self.delay_months) is not int or self.delay_months < 1:
            raise ValueError("delay_months must be a positive integer")

    @property
    def likelihood_matrix(self):
        # Random misleading reports are a uniform mixture, included in likelihoods.
        return ((1 - self.misleading_probability) * np.asarray(self.emissions)
                + self.misleading_probability / len(SIGNALS))


class SyntheticObservationModel:
    def __init__(self, config=ObservationConfig()):
        self.config = config

    def generate(self, conditions, *, month, seed, assignments=()):
        """Only the environment calls this boundary with realized current truth."""
        assigned = {a.student_id: a for a in assignments}
        events, registry = [], []
        for sid, condition in sorted(conditions):
            registry.append(EnrollmentRecord(sid, month, month + 1,
                                              condition != StudentCondition.WITHDRAWN))
            draw = lambda name: keyed_uniform(seed, sid, month, "observation:" + name)
            if draw("missing") < self.config.missing_probability:
                continue
            row = self.config.likelihood_matrix[STATES.index(condition)]
            index = min(int(np.searchsorted(np.cumsum(row), draw("signal"), side="right")), 3)
            delay = self.config.delay_months if draw("delay") < self.config.delay_probability else 0
            assignment = assigned.get(sid)
            events.append(ObservableEvent(
                f"{seed}:{sid}:event:{month}", sid, month, month + 1 + delay, SIGNALS[index],
                assignment.mentor_id if assignment else None,
                f"{seed}:{sid}:programme:{month}" if assignment else None,
                assignment is not None))
        return tuple(events), tuple(registry)
