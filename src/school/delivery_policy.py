"""Shared weekly feasibility and finite-scenario rollout allocation heuristics.

The MILP solves a deterministic reservation/expected-value approximation. It
does not solve the stochastic sequential CMDP or anticipate realized attendance.
"""
from dataclasses import replace
import math
import time

import numpy as np

from ..utils.keyed_random import keyed_uniform
from .delivery_contracts import DeliveryAction
from .delivery_resources import feasible_offers, offer_cost, validate_offers
from .fairness_audit import required_access
from .fairness_planner import feasible_vector
from .money import amount, integer_costs
from .optimization import solve_milp


def delivery_rollout_marginals(config, cutoff, start_week):
    """Four state-specific expected terminal gains for an offered schedule.

    Acceptance is one programme-level Bernoulli. Conditional on acceptance,
    each scheduled week's transition is q*T+(1-q)*W, q=attendance*delivery.
    Cancellation transfers mass from active to inactive before later weeks.
    This preserves acceptance/cancellation correlation across session weeks.
    """
    wait, treatment = np.asarray(config.weekly_wait_matrix), config.treatment_matrix
    active = np.eye(4) * config.acceptance_probability
    inactive = np.eye(4) * (1 - config.acceptance_probability)
    schedule = config.schedule(start_week)
    q = config.attendance_probability * config.delivery_probability
    for week in range(cutoff, config.horizon_weeks + 1):
        if start_week < week <= schedule[-1]:
            cancelled = active * config.cancellation_probability
            active = active - cancelled
            inactive = inactive + cancelled
        matrix = (q * treatment + (1-q) * wait) if week in schedule else wait
        active, inactive = active @ matrix, inactive @ wait
    retained = np.array([1., 1., 1., 0.])
    baseline = np.linalg.matrix_power(wait, config.horizon_weeks-cutoff+1) @ retained
    return (active + inactive) @ retained - baseline


def weekly_resource_rows(state, candidates, config):
    """Binary starts consume EVERY future week, with existing obligations fixed."""
    rows, upper = [], []
    for student in state.students:
        row = [int(a.student_id == student.student_id) for a in candidates]
        if any(row):
            rows.append(row)
            upper.append(1)
    for cell in state.ledger.cells:
        slots = [int(a.mentor_id == cell.mentor_id and cell.week in config.schedule(a.start_week))
                 for a in candidates]
        caseload = [int(a.mentor_id == cell.mentor_id and
                        a.start_week <= cell.week <= config.schedule(a.start_week)[-1]) for a in candidates]
        used = cell.reserved_slots + cell.delivered_sessions + cell.wasted_slots
        if any(slots):
            # Duration/hours converted to exact integer multiples just like money.
            duration, available = integer_costs(
                [config.session_duration_hours * bit for bit in slots],
                amount(cell.available_hours) - used * amount(config.session_duration_hours))
            rows.extend([slots, duration])
            upper.extend([cell.available_slots-used, available])
        if any(caseload):
            rows.append(caseload)
            upper.append(cell.maximum_caseload-len(cell.active_students))
    mentors = {m.mentor_id: m for m in state.mentors}
    costs, budget = integer_costs([offer_cost(config, mentors[a.mentor_id]) for a in candidates],
                                  state.ledger.spendable)
    rows.append(costs)
    upper.append(budget)
    return np.asarray(rows, dtype=float), np.asarray(upper, dtype=float), np.asarray(costs)


class WeeklyDeliveryPolicy:
    MODES = ('wait', 'random', 'priority', 'point', 'fair_point', 'fair_robust')

    def __init__(self, config, mode='fair_point', *, uncertainty_radius=.25):
        if mode not in self.MODES:
            raise ValueError('unsupported weekly allocation policy')
        if not math.isfinite(uncertainty_radius) or not 0 <= uncertainty_radius <= 1:
            raise ValueError('weekly uncertainty radius must be within [0,1]')
        self.config, self.mode, self.uncertainty_radius = config, mode, uncertainty_radius

    @property
    def configuration(self):
        return dict(contract='scheduled_weekly/policy/v1', mode=self.mode,
            uncertainty_radius=self.uncertainty_radius,
            valuation='expected_weekly_delivery_rollout_v1',
            robust_scenarios='nominal_and_global_enrolled_low_high_marginal_mixtures',
            fairness_objective='equal_cell_sum_shortfall_over_frozen_denominator',
            optimization_scope='deterministic_start_schedule_approximation')

    def plan(self, state):
        state.validate_estimates()
        config = self.config
        if self.mode == 'wait':
            return DeliveryAction(status='wait', lexicographic_complete=True)
        fair = self.mode in ('fair_point', 'fair_robust')
        end = state.fairness_window.end_week if fair else state.week
        candidates = feasible_offers(state, config, end_week=end)
        if self.mode in ('random', 'priority'):
            students = {s.student_id: s for s in state.students}
            if self.mode == 'random':
                key = lambda a: (keyed_uniform(config.seed, a.student_id, state.week,
                    'weekly_policy_random:' + a.mentor_id), a.student_id, a.mentor_id)
            else:
                key = lambda a: (-students[a.student_id].risk.probability,
                    -students[a.student_id].waiting_weeks, a.student_id, a.mentor_id)
            selected = []
            for candidate in sorted(candidates, key=key):
                action = DeliveryAction(tuple([*selected, candidate]))
                try:
                    validate_offers(state, action, config)
                except ValueError:
                    continue
                selected.append(candidate)
            return DeliveryAction(tuple(selected), status='feasible_' + self.mode, lexicographic_complete=True)
        cohorts = tuple(c for c in state.fairness_window.cohorts if c.student_ids) if fair else ()
        prior = set(state.fairness_window.offered_ids)

        def shortfall(selected):
            ids = prior | {a.student_id for a in selected}
            return sum(max(0, required_access(config.fairness_target, len(c.student_ids))
                           - len(set(c.student_ids) & ids)) / len(c.student_ids) for c in cohorts)

        if not candidates:
            return DeliveryAction(status='fairness_infeasible' if shortfall(()) and
                not config.fairness_allow_shortfall else 'no_candidates',
                projected_normalized_shortfall=shortfall(()), lexicographic_complete=True)
        count = len(candidates)
        slack_count = len(cohorts) if config.fairness_allow_shortfall else 0
        robust = self.mode == 'fair_robust'
        integer_count = count + slack_count
        size = integer_count + int(robust)
        base_rows, base_upper, costs = weekly_resource_rows(state, candidates, config)
        rows = np.pad(base_rows, ((0, 0), (0, size-count)))
        lower, upper = np.full(len(rows), -np.inf), base_upper
        weights = np.zeros(size)
        for index, cohort in enumerate(cohorts):
            ids = set(cohort.student_ids)
            row = np.zeros(size)
            row[:count] = [int(a.student_id in ids-prior) for a in candidates]
            if slack_count:
                row[count+index] = 1
                weights[count+index] = 1 / len(ids)
            rows = np.vstack([rows, row])
            lower = np.append(lower, required_access(config.fairness_target, len(ids)) - len(ids & prior))
            upper = np.append(upper, np.inf)
        by_id = {s.student_id: s for s in state.students}
        marginal = {w: delivery_rollout_marginals(config, state.week, w)
                    for w in {a.start_week for a in candidates}}
        # One belief per student/scenario, shared across all alternative starts
        # and mentors. A scenario cannot change a student's state to suit the
        # candidate being valued. Extremes use the current-start reference gain.
        reference_gain = delivery_rollout_marginals(config, state.week, state.week)
        scenarios = []
        for scenario in ('nominal', 'low', 'high') if robust else ('nominal',):
            values = []
            for a in candidates:
                belief = np.asarray(by_id[a.student_id].estimate.condition_probabilities)
                gain = marginal[a.start_week]
                if scenario != 'nominal':
                    best = int(np.argmin(reference_gain[:3]) if scenario == 'low' else np.argmax(reference_gain[:3]))
                    extreme = np.zeros(4)
                    extreme[best], extreme[3] = 1-belief[3], belief[3]
                    belief = (1-self.uncertainty_radius)*belief + self.uncertainty_radius*extreme
                values.append(float(belief @ gain))
            scenarios.append(values)
        scenario_values = np.asarray(scenarios)
        value_row, cost_row = np.zeros(size), np.zeros(size)
        cost_row[:count] = costs
        variable_lower = np.zeros(size)
        if robust:
            value_row[-1] = 1
            variable_lower[-1] = -float(np.abs(scenario_values).sum(axis=1).max())
            for values in scenario_values:
                row = np.zeros(size)
                row[:count], row[-1] = -values, 1
                rows = np.vstack([rows, row])
                lower, upper = np.append(lower, -np.inf), np.append(upper, 0)
        else:
            value_row[:count] = scenario_values[0]
        started = time.perf_counter()

        def solve(objective):
            remaining = config.planner_time_limit - (time.perf_counter()-started)
            if remaining <= 0:
                raise TimeoutError('weekly total solve deadline reached')
            result = solve_milp(objective, rows, lower, upper, binary_count=count,
                integer_count=integer_count, variable_lower=variable_lower, time_limit=remaining)
            if not feasible_vector(result, rows, lower, upper, integer_count=integer_count,
                                   variable_lower=variable_lower):
                return result, None
            vector = np.asarray(result.x).copy()
            vector[:integer_count] = np.rint(vector[:integer_count])
            if np.any(vector[:count] > 1):
                return result, None
            if robust:
                vector[-1] = float(np.min(scenario_values @ vector[:count]))
            selected = tuple(a for a, bit in zip(candidates, vector[:count]) if bit)
            validate_offers(state, DeliveryAction(selected), config, projected=True)
            return result, vector

        objectives = []
        if slack_count:
            objectives.append(('fairness', weights))
        objectives.extend([('benefit', -value_row), ('cost', cost_row)])
        for offset in range(0, count, 20):
            bits = np.zeros(size)
            block = min(20, count-offset)
            bits[offset:offset+block] = [2**p for p in reversed(range(block))]
            objectives.append(('canonical', -bits))
        best, complete, message = None, True, ''
        for stage, objective in objectives:
            try:
                result, proposed = solve(objective)
            except Exception as exc:
                complete, message = False, repr(exc)
                break
            if proposed is None:
                complete, message = False, str(result.message)
                if best is None:
                    return DeliveryAction(status='fairness_infeasible' if result.status == 2 and fair
                        else 'solver_wait_fallback', solver_message=message,
                        projected_normalized_shortfall=shortfall(()))
                break
            best, message = proposed, str(result.message)
            if result.status != 0:
                complete = False
                break
            rows = np.vstack([rows, objective])
            tolerance = 1e-10 if stage == 'benefit' else 1e-8 if stage == 'fairness' else 0
            lower, upper = np.append(lower, -np.inf), np.append(upper, float(objective @ best) + tolerance)
        if best is None:
            return DeliveryAction(status='solver_wait_fallback', solver_message=message)
        selected = tuple(a for a, bit in zip(candidates, best[:count]) if bit)
        current = tuple(a for a in selected if a.start_week == state.week)
        validate_offers(state, DeliveryAction(current), config)
        return DeliveryAction(current, status='weekly_rollout_milp_optimal' if complete else 'weekly_rollout_feasible_incomplete',
            objective=float(value_row @ best), projected_offers=selected,
            projected_normalized_shortfall=shortfall(selected), lexicographic_complete=complete,
            solver_message=message)
