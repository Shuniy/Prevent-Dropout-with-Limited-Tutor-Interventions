"""Simple allocation baselines with the same hard constraints as the planner."""

from numpy.random import default_rng

from ..utils.constants import SEED
from .allocation_result import AllocationResult
from .greedy_matching import assign_feasible
from .student_condition import STATES


BASELINES = ("wait", "random", "severity", "need_priority", "longest_waiting")
BASELINE_VERSION = "student_priority_v3"


class BaselinePolicy:
    """Need priority uses the fixed initial maximum shared-rule need severity.

    Waiting starts for everyone at the first decision. It ends on admission or
    withdrawal. Consequently, unserved survivors tie in this closed cohort.
    """

    def __init__(self, name="wait", seed=SEED):
        if name not in BASELINES:
            raise ValueError(f"unknown baseline: {name}")
        self.name = name
        self.seed = seed

    def rank_students(self, state):
        """Rank eligible students independently of mentor compatibility.

        Random shuffles a stable ID order with a local, episode/month seeded
        generator, separate from environmental keyed draws. This is a random
        student ordering, not uniform sampling over feasible joint allocations.
        """
        if self.name == "wait":
            return ()
        students = sorted(
            (student for student in state.students if student.eligible),
            key=lambda student: student.student_id,
        )
        if self.name == "random":
            default_rng([self.seed, state.month]).shuffle(students)
            return tuple(students)

        def priority(student):
            if self.name == "severity":
                if student.condition is None:
                    raise ValueError("severity policy requires an observed or estimated condition")
                score = STATES.index(student.condition)
            elif self.name == "need_priority":
                score = student.need_score
            else:
                score = student.waiting_months
            return (-score, student.student_id)

        return tuple(sorted(students, key=priority))

    def plan(self, state):
        return AllocationResult(assign_feasible(state, self.rank_students(state)))
