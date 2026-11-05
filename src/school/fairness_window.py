"""Frozen window membership and access reconstructed from admission histories."""

from dataclasses import dataclass, field

from .fairness_audit import freeze_cohorts, required_access, compatible_ids
from .constraints import candidate_assignments


@dataclass
class FairnessWindow:
    start: int
    end: int
    cohorts: tuple
    target: float
    recipients: set[str] = field(default_factory=set)
    actionable_ids: set[str] = field(default_factory=set)
    excluded_no_compatible_ids: tuple[str, ...] = ()
    withdrawn_ids: set[str] = field(default_factory=set)

    @classmethod
    def initialize(cls, state, *, window_months, target, attribute):
        start = ((state.month - 1) // window_months) * window_months + 1
        if state.month != start:
            raise ValueError("fairness planner must observe the start of each assessment window")
        end = min(start + window_months - 1, state.month + state.months_remaining - 1)
        compatible = compatible_ids(state, end)
        window = cls(start, end, freeze_cohorts(state, attribute, end_month=end), target,
                     excluded_no_compatible_ids=tuple(sorted(
                         s.student_id for s in state.students if s.eligible and s.student_id not in compatible)))
        window.update(state)
        return window

    def update(self, state):
        self.recipients.update(s.student_id for s in state.students
                               if any(self.start <= month <= min(state.month, self.end)
                                      for month in s.programme_months))
        self.actionable_ids = {a.student_id for a in candidate_assignments(state)}
        self.withdrawn_ids.update(s.student_id for s in state.students if not s.enrolled)

    def rows(self, projected_ids=()):
        projected = self.recipients | set(projected_ids)
        result = []
        for cohort in self.cohorts:
            ids = set(cohort.student_ids)
            size = len(ids)
            covered = len(ids & self.recipients)
            future_covered = len(ids & projected)
            required = required_access(self.target, size)
            result.append({"attribute": cohort.attribute, "group": cohort.group,
                           "condition_at_start": cohort.condition_at_start,
                           "window_start": self.start, "window_end": self.end,
                           "eligible_count": size, "target_coverage": self.target,
                           "required_students": required, "covered_before": covered,
                           "outstanding_before": max(0, required - covered),
                           "actionable_count": len(ids & self.actionable_ids),
                           "uncovered_unactionable_count": len(ids - self.recipients - self.actionable_ids),
                           "withdrawn_uncovered_count": len((ids & self.withdrawn_ids) - self.recipients),
                           "projected_coverage": future_covered,
                           "projected_shortfall": max(0, required - future_covered)})
        return result
