"""Exact finite-horizon reference with complete next-state probabilities, no draws."""

from dataclasses import replace
from functools import lru_cache
from itertools import product

import numpy as np

from .constraints import candidate_assignments, validate_allocation
from .constrained_planner import ConstrainedAllocationPlanner
from .student_condition import STATES
from .transition_model import P_WAIT, programme_matrix, validate_matrix


def enumerate_allocations(state):
    """Enumerate every feasible joint assignment, including wait for everyone."""
    candidates = candidate_assignments(state)
    choices = []
    for student in state.students:
        options = [None] + [item for item in candidates if item.student_id == student.student_id]
        choices.append(options)
    feasible = []
    for choice in product(*choices):
        selected = tuple(item for item in choice if item is not None)
        try:
            validate_allocation(state, selected)
        except ValueError:
            continue
        feasible.append(selected)
    return tuple(feasible)


class ExactTinyMDP:
    """Reference for at most four students and three remaining months.

    Integer programme costs/budget keep the cache exact. Future mentor resources
    are a declared schedule, defaulting to the current resources each month.
    Objective ties prefer wait; this makes the option of delaying visible.
    Fairness and partially observed estimation are outside this reference.
    """

    def __init__(
        self, initial_state, *, wait_matrix=P_WAIT, treatment_matrix=None, mentor_schedule=None
    ):
        if len(initial_state.students) > 4 or initial_state.months_remaining > 3:
            raise ValueError("exact reference is limited to four students and three months")
        if initial_state.months_remaining < 1:
            raise ValueError("exact reference requires a decision month")
        costs = [5 * mentor.cost_per_appointment for mentor in initial_state.mentors]
        if any(
            abs(value - round(value)) > 1e-9 for value in [initial_state.remaining_budget, *costs]
        ):
            raise ValueError("tiny reference requires integer budget and programme costs")
        if any(student.condition is None for student in initial_state.students):
            raise ValueError("exact reference requires fully observed conditions")
        self.initial = initial_state
        self.wait = validate_matrix(wait_matrix)
        self.programme = validate_matrix(
            programme_matrix() if treatment_matrix is None else treatment_matrix
        )
        self.schedule = mentor_schedule
        if mentor_schedule is not None:
            end = initial_state.month + initial_state.months_remaining
            for month in range(initial_state.month, end):
                if month not in mentor_schedule:
                    raise ValueError("mentor_schedule must include every remaining decision month")
                for mentor in mentor_schedule[month]:
                    cost = 5 * mentor.cost_per_appointment
                    if not np.isfinite(cost) or abs(cost - round(cost)) > 1e-9:
                        raise ValueError(
                            "tiny reference requires integer programme costs in every month"
                        )
        self._next_states = tuple(product(range(4), repeat=len(initial_state.students)))

    def compare(self):
        planner = ConstrainedAllocationPlanner(
            wait_matrix=self.wait, treatment_matrix=self.programme
        )
        initial_conditions = tuple(
            STATES.index(student.condition) for student in self.initial.students
        )
        initial_used = tuple(bool(student.programme_months) for student in self.initial.students)
        end = self.initial.month + self.initial.months_remaining

        def snapshot(month, conditions, used, budget):
            students = tuple(
                replace(
                    student,
                    condition=STATES[condition],
                    enrolled=condition != 3,
                    programme_months=(0,) if was_used else (),
                )
                for student, condition, was_used in zip(self.initial.students, conditions, used)
            )
            mentors = self.initial.mentors if self.schedule is None else self.schedule[month]
            return replace(
                self.initial,
                month=month,
                months_remaining=end - month,
                remaining_budget=budget,
                students=students,
                mentors=mentors,
            )

        def expectation(month, conditions, used, budget, action, continuation):
            selected = {item.student_id for item in action}
            next_used = tuple(
                was_used or student.student_id in selected
                for student, was_used in zip(self.initial.students, used)
            )
            next_budget = budget - round(sum(item.cost_units for item in action))
            rows = []
            for student, condition in zip(self.initial.students, conditions):
                matrix = self.programme if student.student_id in selected else self.wait
                rows.append(matrix[condition])
            value = 0.0
            for next_conditions in self._next_states:
                probability = 1.0
                for row, condition in zip(rows, next_conditions):
                    probability *= row[condition]
                if probability:
                    value += probability * continuation(
                        month + 1, next_conditions, next_used, next_budget
                    )
            return value

        @lru_cache(maxsize=None)
        def optimal(month, conditions, used, budget):
            if month == end:
                # Bellman boundary V_T(S) = sum_i 1[s_i != withdrawn].
                return float(sum(condition != 3 for condition in conditions))
            state = snapshot(month, conditions, used, budget)
            # V_t(S) = max_(a feasible) E[V_(t+1)(S') | S, a].
            return max(
                expectation(month, conditions, used, budget, action, optimal)
                for action in enumerate_allocations(state)
            )

        @lru_cache(maxsize=None)
        def approximate(month, conditions, used, budget):
            if month == end:
                return float(sum(condition != 3 for condition in conditions))
            state = snapshot(month, conditions, used, budget)
            allocation = planner.plan(state)
            if allocation.status not in ("optimal", "no_candidates", "zero_benefit"):
                raise RuntimeError(
                    "exact comparison requires a solved monthly heuristic: " + allocation.status
                )
            return expectation(month, conditions, used, budget, allocation.assignments, approximate)

        args = (
            self.initial.month,
            initial_conditions,
            initial_used,
            round(self.initial.remaining_budget),
        )
        actions = enumerate_allocations(self.initial)
        values = [expectation(*args, action, optimal) for action in actions]
        best = max(range(len(actions)), key=lambda index: values[index])
        greedy = planner.plan(self.initial).assignments
        exact_value = values[best]
        heuristic_value = approximate(*args)
        return {
            "exact_expected_terminal_enrollment": exact_value,
            "heuristic_expected_terminal_enrollment": heuristic_value,
            "objective_gap": exact_value - heuristic_value,
            "exact_first_student_ids": [item.student_id for item in actions[best]],
            "heuristic_first_student_ids": [item.student_id for item in greedy],
            "exact_first_action": actions[best],
            "states_evaluated": optimal.cache_info().currsize,
        }
