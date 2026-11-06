"""Finite-scenario robust extension of the existing rolling fairness MILP."""

from dataclasses import replace
import time

import numpy as np

from .allocation_result import AllocationResult
from .constraints import validate_allocation
from .fairness_audit import coverage_shortfall, required_access
from .fairness_planner import FairnessPlanner, feasible_vector
from .fairness_window import FairnessWindow
from .optimization import solve_milp
from .retention_value import estimate_all_student_benefits
from .uncertainty_scenarios import (SCENARIO_SOURCE,
    UncertaintyScenarioConfig, build_belief_scenarios, scenario_candidate_values)
from .window_optimization import validate_schedule, window_model


class FairRobustPlanner(FairnessPlanner):
    """Lexicographic shortfall, worst scenario aggregate benefit, cost, bits.

    eta <= sum_j Delta[j,s] x_j for each complete scenario s. eta is continuous
    and can be negative. As in FairnessPlanner, only current admissions execute;
    future assignments remain disposable forecasts. At q=0 the same robust
    objective applies to current candidates without future access pressure.
    """

    def __init__(self, *, uncertainty_radius=.25, uncertainty_config=None, **kwargs):
        super().__init__(**kwargs)
        self.uncertainty_config = uncertainty_config or UncertaintyScenarioConfig(radius=uncertainty_radius)
        if not isinstance(self.uncertainty_config, UncertaintyScenarioConfig):
            raise ValueError("uncertainty_config must be UncertaintyScenarioConfig")
        self.last_scenarios = ()
        self.last_scenario_values = np.empty((0, 0))
        self.last_robust_benefit = 0.0

    @property
    def settings(self):
        config = self.uncertainty_config
        return (*super().settings,
            ("uncertainty_source", SCENARIO_SOURCE), ("uncertainty_radius", config.radius),
            ("uncertainty_missingness_multiplier", config.missingness_multiplier),
            ("uncertainty_freshness_months", config.freshness_months),
            ("robust_objective", "min_scenario_sum_assignment_benefits"))

    def belief_scenarios(self, state):
        """Separate pure construction boundary, override only in unit fixtures."""
        return build_belief_scenarios(state, self.uncertainty_config,
                                     self.wait_matrix, self.programme_matrix)

    def plan(self, state):
        state.validate_estimates()
        started = time.perf_counter()
        self.last_scenarios = self.belief_scenarios(state)
        self.last_scenario_values = np.empty((len(self.last_scenarios), 0))
        self.last_robust_benefit = 0.0
        start = ((state.month - 1) // self.window_months) * self.window_months + 1
        if self.window is None or self.window.start != start:
            self.window = FairnessWindow.initialize(state, window_months=self.window_months,
                target=self.minimum_access, attribute=self.grouping_attribute)
            self.windows.append(self.window)
        self.window.update(state)
        window, prior = self.window, self.window.recipients
        active_fairness = self.enabled and self.minimum_access > 0

        def finish(allocation, schedule=(), complete=False):
            if "fallback" in allocation.status and self.failure_mode == "raise":
                raise RuntimeError(allocation.status + ": " + allocation.message)
            planned = {a.student_id for a in schedule}
            admitted = {a.student_id for a in allocation.assignments}
            projected = coverage_shortfall(window.cohorts, prior | planned, self.minimum_access)
            realized = coverage_shortfall(window.cohorts, prior | admitted, self.minimum_access)
            metadata = (("robust_worst_case_benefit", self.last_robust_benefit),
                ("scenario_names", tuple(s.name for s in self.last_scenarios)),
                ("scenario_provenance", tuple((s.name, s.source, s.parameters)
                                              for s in self.last_scenarios)))
            return replace(allocation, runtime_seconds=time.perf_counter() - started,
                fairness_shortfall=projected, projected_fairness_shortfall=projected,
                realized_fairness_shortfall=realized, tentative_assignments=tuple(schedule),
                projected_coverage=tuple(tuple(row.items()) for row in window.rows(planned)),
                fairness_window_start=window.start, fairness_window_end=window.end,
                fairness_mode=("disabled" if not active_fairness else
                               "shortfall_aware" if self.allow_shortfall else "strict"),
                projected_fairness_feasible=projected <= self.FAIRNESS_TOLERANCE,
                lexicographic_complete=complete,
                eligible_student_count=sum(s.eligible for s in state.students),
                available_mentor_count=sum(m.admissions > 0 and m.appointments >= 5 for m in state.mentors),
                current_month=state.month, remaining_budget=state.remaining_budget,
                months_remaining=state.months_remaining,
                solver_settings=(*self.settings, *metadata))

        end = window.end if active_fairness else state.month
        candidates, resources, resource_upper, nominal_values, costs, states = window_model(
            state, end, self.wait_matrix, self.programme_matrix)
        count = len(candidates)
        cohorts = tuple(c for c in window.cohorts if c.student_ids) if active_fairness else ()
        if not count:
            shortfall = coverage_shortfall(cohorts, prior, self.minimum_access)
            status = ("fair_robust_infeasible" if shortfall and not self.allow_shortfall
                      else "fair_robust_no_candidates")
            return finish(AllocationResult(status=status,
                message="No actionable compatible, affordable slots remain."), complete=True)
        scenario_values = scenario_candidate_values(state, candidates, self.last_scenarios,
                                                    self.wait_matrix, self.programme_matrix)
        self.last_scenario_values = scenario_values
        slack_count = len(cohorts) if self.allow_shortfall else 0
        integer_count = count + slack_count
        size = integer_count + 1
        eta = size - 1
        rows = np.zeros((len(resources) + len(cohorts) + len(scenario_values), size))
        lower = np.full(len(rows), -np.inf)
        upper = np.full(len(rows), np.inf)
        rows[:len(resources), :count] = resources
        upper[:len(resources)] = resource_upper
        weights = np.zeros(size)
        for index, cohort in enumerate(cohorts):
            ids = set(cohort.student_ids)
            row = len(resources) + index
            rows[row, :count] = [int(a.student_id in ids) for a in candidates]
            lower[row] = required_access(self.minimum_access, len(ids)) - len(ids & prior)
            if self.allow_shortfall:
                rows[row, count + index] = 1
                weights[count + index] = 1 / len(ids)
        offset = len(resources) + len(cohorts)
        rows[offset:, :count] = -scenario_values
        rows[offset:, eta] = 1
        upper[offset:] = 0
        variable_lower = np.zeros(size)
        # A finite valid lower bound includes negative treatment effects.
        variable_lower[eta] = -float(np.abs(scenario_values).sum(axis=1).max())

        def solve(objective):
            remaining = self.time_limit - (time.perf_counter() - started)
            if remaining <= 0:
                raise TimeoutError("total monthly solve time limit reached")
            result = solve_milp(objective, rows, lower, upper, binary_count=count,
                integer_count=integer_count, variable_lower=variable_lower, time_limit=remaining)
            if not feasible_vector(result, rows, lower, upper, integer_count=integer_count,
                                   variable_lower=variable_lower):
                return result, None
            vector = np.asarray(result.x).copy()
            vector[:integer_count] = np.rint(vector[:integer_count])
            if np.any(vector[:count] > 1):
                return result, None
            selected = tuple(a for a, bit in zip(candidates, vector[:count]) if bit)
            validate_schedule(state, states, selected)
            # Keep eta continuous; evaluating the scenario rows removes any
            # solver feasibility tolerance from subsequent objective locks.
            vector[eta] = float(np.min(scenario_values @ vector[:count]))
            return result, vector

        try:
            first, best = solve(weights)
        except Exception as error:
            return finish(AllocationResult(status="fair_robust_solver_wait_fallback", message=repr(error)))
        if best is None:
            status = ("fair_robust_infeasible" if first.status == 2 and not self.allow_shortfall
                      else "fair_robust_solver_wait_fallback")
            return finish(AllocationResult(status=status, message=str(first.message)))
        best_shortfall = float(weights @ best)
        if slack_count:
            rows = np.vstack([rows, weights])
            lower = np.append(lower, -np.inf)
            upper = np.append(upper, best_shortfall + self.FAIRNESS_TOLERANCE)
        complete, message = first.status == 0, str(first.message)
        status = "fair_robust_optimal" if complete else "fair_robust_feasible_limit"
        robust_row, cost_row = np.zeros(size), np.zeros(size)
        robust_row[eta] = -1
        cost_row[:count] = costs
        objectives = [("robust_benefit", robust_row), ("cost", cost_row)]
        for offset in range(0, count, self.TIE_BLOCK_SIZE):
            bit_row = np.zeros(size)
            block = min(count - offset, self.TIE_BLOCK_SIZE)
            bit_row[offset:offset + block] = [2 ** p for p in reversed(range(block))]
            objectives.append(("tie", -bit_row))
        if complete:
            for stage, objective in objectives:
                try:
                    result, proposed = solve(objective)
                    if (proposed is None or result.status != 0
                            or np.any(rows @ proposed < lower - self.OBJECTIVE_TOLERANCE)
                            or np.any(rows @ proposed > upper + self.OBJECTIVE_TOLERANCE)):
                        complete, status, message = False, "fair_robust_" + stage + "_incomplete", str(result.message)
                        break
                    best = proposed
                except Exception as error:
                    complete, status, message = False, "fair_robust_" + stage + "_limit_or_error", repr(error)
                    break
                achieved = float(objective @ best)
                rows = np.vstack([rows, objective])
                lower = np.append(lower, -np.inf)
                upper = np.append(upper, achieved + (self.OBJECTIVE_TOLERANCE
                                  if stage == "robust_benefit" else 0))
        schedule = tuple(a for a, bit in zip(candidates, best[:count]) if bit)
        current = tuple(a for a in schedule if a.month == state.month)
        validate_allocation(state, current)
        self.last_robust_benefit = float(np.min(scenario_values @ best[:count]))
        immediate = estimate_all_student_benefits(state, self.wait_matrix, self.programme_matrix)
        return finish(AllocationResult(current, status=status,
            objective=sum(immediate[a.student_id] for a in current), message=message,
            candidate_pair_count=count, decision_variable_count=size,
            projected_total_benefit=float(nominal_values @ best[:count])), schedule, complete)
