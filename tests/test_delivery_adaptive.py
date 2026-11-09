"""Phase 4.1 regressions, with independent finite-instance checks."""
from dataclasses import replace
import unittest

from test_delivery_lifecycle import world
from src.school.delivery_contracts import DeliveryAction, SupportOffer
from src.school.delivery_controller import WeeklyFeedbackController
from src.school.delivery_policy import WeeklyDeliveryPolicy
from src.school.delivery_contracts import WeeklyNote
from src.school.delivery_acceptance import boundary_episode, REGULAR, LOW, VAGUE
from src.school.delivery_uncertainty import weekly_uncertainty_sets, weekly_belief_scenarios, weekly_scenario_values
from src.school.delivery_forecasts import terminal_operator, remaining_marginals
from src.school.delivery_resources import feasible_offers, validate_offers, audit_delivery_events
from src.school.delivery_config import WEEKLY_WAIT_V1, WEEKLY_TUTORING_V1
from src.school.delivery_fairness import offer_feasibility_diagnostics
import numpy as np


class AdaptiveReproductions(unittest.TestCase):
    def test_active_programme_is_explicitly_reviewed(self):
        env = world()
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)))
        state = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config, 'point')).prepare_decision_snapshot()
        action = WeeklyDeliveryPolicy(env.config, 'point').plan(state)
        self.assertEqual(len(action.continuation_reviews), 1)

    def test_uncertainty_is_student_specific_and_audited(self):
        env = world()
        policy = WeeklyDeliveryPolicy(env.config, 'fair_robust')
        policy.plan(WeeklyFeedbackController(env, policy).prepare_decision_snapshot())
        self.assertEqual(len(policy.last_uncertainty_sets), 3)

    def test_commitment_risk_is_separately_named(self):
        env = world()
        env.step(DeliveryAction((SupportOffer('s0', 'm0', 1),)))
        state = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config)).prepare_decision_snapshot()
        self.assertEqual(state.students[0].committed_risk.forecast_regime, 'continue_accepted_no_new_offers')

    def test_fairness_feasibility_does_not_remove_denominator(self):
        from src.school.delivery_fairness import offer_feasibility_diagnostics
        env = world()
        state = env.prepare_decision()
        diagnostic = offer_feasibility_diagnostics(state, env.config)
        self.assertEqual(diagnostic['frozen_eligible_students'], 3)


class NoteToActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.regular, cls.low = boundary_episode(REGULAR), boundary_episode(LOW)

    def test_single_fact_counterfactual_chain(self):
        a,b = self.regular,self.low
        self.assertEqual(a.environment.initial_conditions,b.environment.initial_conditions)
        self.assertEqual(a.snapshots[0],b.snapshots[0])
        self.assertEqual(a.decisions[0],b.decisions[0])
        self.assertEqual(a.snapshots[1].ledger,b.snapshots[1].ledger)
        self.assertEqual(a.environment.config,b.environment.config)
        notes_a = {n.note_id:n for n in a.notes if n.source_week <= 1}
        notes_b = {n.note_id:n for n in b.notes if n.source_week <= 1}
        changed = [k for k in notes_a if notes_a[k] != notes_b[k]]
        self.assertEqual(len(changed),1)
        batches = [next(x for x in c.batches if x.note_id == changed[0]) for c in (a,b)]
        self.assertNotEqual(batches[0].facts[0].value,batches[1].facts[0].value)
        sa,sb = a.snapshots[1].students[0],b.snapshots[1].students[0]
        self.assertEqual(sum(s.eligible for s in a.snapshots[1].students),2)
        self.assertNotEqual(sa.estimate.condition_probabilities,sb.estimate.condition_probabilities)
        self.assertNotEqual(sa.risk.probability,sb.risk.probability)
        for s in (sa,sb):
            self.assertEqual(s.risk.input_estimate_id,s.estimate.estimate_id)
            self.assertEqual(s.committed_risk.input_estimate_id,s.estimate.estimate_id)
        for c,s,index in ((a,sa,0),(b,sb,2)):
            predicted = np.asarray(c.snapshots[0].students[0].estimate.condition_probabilities) @ c.environment.config.treatment_matrix
            weighted = predicted * np.array([1,1,1,0]) * c.estimator.likelihoods[:,index]
            np.testing.assert_allclose(s.estimate.condition_probabilities,weighted/weighted.sum(),atol=1e-14)
        ra,rb = a.decisions[1].continuation_reviews[0],b.decisions[1].continuation_reviews[0]
        self.assertLess(ra.continuation_value,rb.continuation_value)
        self.assertEqual(ra.opportunity_value,rb.opportunity_value)
        self.assertEqual((ra.decision,rb.decision),('cancel','continue'))
        self.assertFalse(a.decisions[1].offers)
        self.assertTrue(a.decisions[2].offers)
        self.assertFalse(b.decisions[2].offers)
        self.assertEqual(a.environment.evaluator_truth[:2],b.environment.evaluator_truth[:2])

    def test_cancellation_preserves_history_expenditure_and_validates_later_offer(self):
        c = self.regular
        self.assertEqual(float(c.snapshots[1].ledger.spent),1.1)
        self.assertEqual(float(c.snapshots[2].ledger.spent),1.1)
        self.assertEqual(float(c.snapshots[2].ledger.reserved),0)
        self.assertEqual(float(c.snapshots[2].ledger.released),4)
        p = c.environment.programmes[0]
        self.assertEqual(p.delivered_sessions,1)
        self.assertEqual(p.status,'CANCELLED')
        self.assertEqual(sum(e.kind == 'support_offered' and e.programme_id == p.programme_id
                             for e in c.environment.events),1)
        for s,a in zip(c.snapshots,c.decisions):
            validate_offers(s,a,c.environment.config)
        self.assertEqual(c.validate(),audit_delivery_events(c.environment.config,c.environment.mentors,
            c.environment.events,profiles=c.environment.profiles))

    def test_negative_control_unsupported_prose_does_not_change_estimates_or_actions(self):
        a,b = boundary_episode(VAGUE),boundary_episode(VAGUE+' The mentor will follow up.')
        self.assertEqual(a.snapshots,b.snapshots)
        self.assertEqual(a.decisions,b.decisions)
        r = a.decisions[1].continuation_reviews[0]
        self.assertFalse(r.fresh_evidence)
        self.assertEqual(r.decision,'continue')

    def test_true_transitions_depend_only_on_actual_delivered_action_and_keyed_draw(self):
        from src.school.transition_model import sample_condition,keyed_uniform
        for c in (self.regular,self.low):
            env = c.environment
            for t in range(1,env.config.horizon_weeks+1):
                past,now = dict(env.evaluator_truth[t-1][1]),dict(env.evaluator_truth[t][1])
                delivered = {e.student_id for e in env.events if e.kind == 'session_delivered' and e.source_week == t}
                for sid in past:
                    matrix = env.config.treatment_matrix if sid in delivered else env.config.weekly_wait_matrix
                    draw = keyed_uniform(env.config.seed,sid,t,'weekly_environment_transition/v1')
                    self.assertEqual(now[sid],sample_condition(past[sid],matrix,draw))

    def test_all_nonwait_families_have_same_review_action_space(self):
        state = self.regular.snapshots[1]
        for mode in WeeklyDeliveryPolicy.MODES:
            action = WeeklyDeliveryPolicy(self.regular.environment.config,mode).plan(state)
            validate_offers(state,action,self.regular.environment.config)
            self.assertEqual(len(action.continuation_reviews),int(mode != 'wait'))

    def test_no_speculative_same_cutoff_offer(self):
        s = self.regular.snapshots[1]
        pid = s.students[0].programmes[0].programme_id
        bad = DeliveryAction((SupportOffer('fictional-01','mentor-0',2),),(pid,))
        with self.assertRaises(ValueError):
            validate_offers(s,bad,self.regular.environment.config)

    def test_nonoptimal_opportunity_cannot_trigger_cancellation(self):
        from unittest.mock import patch
        with patch('src.school.delivery_reassessment.portfolio_value',return_value=(None,'nonoptimal_1')):
            action = WeeklyDeliveryPolicy(self.regular.environment.config,'point').plan(self.regular.snapshots[1])
        self.assertFalse(action.cancel_programme_ids)
        self.assertEqual(action.continuation_reviews[0].reason,'nonoptimal_opportunity_solve_preserves_support')


class InformationQualityTests(unittest.TestCase):
    def controller(self):
        env = world()
        c = WeeklyFeedbackController(env,WeeklyDeliveryPolicy(env.config,'wait'))
        c.notes = [WeeklyNote('base','s0',0,1,LOW,('source0',))]
        return c

    def test_fresh_stale_missing_and_clipping_rule(self):
        c = self.controller()
        state = c.prepare_decision_snapshot()
        u = {u.student_id:u for u in weekly_uncertainty_sets(state)}
        self.assertEqual(u['s0'].radius,.25)
        self.assertEqual(u['s1'].radius,.75)
        self.assertEqual(u['s0'].latest_assimilated_source_week,0)
        c.run_week()
        c.notes = [n for n in c.notes if n.source_week == 0]
        stale = weekly_uncertainty_sets(c.prepare_decision_snapshot())[0]
        self.assertAlmostEqual(stale.radius,.25*1.5*(1+1/12))
        clipped = weekly_uncertainty_sets(state,1)[1]
        self.assertEqual(clipped.radius,1)
        self.assertTrue(clipped.clipping_applied)

    def test_duplicate_evidence_does_not_refresh_or_shrink_uncertainty(self):
        c = self.controller()
        first = c.prepare_decision_snapshot()
        c.notes.append(replace(c.notes[0],note_id='copy'))
        again = c.prepare_decision_snapshot()
        self.assertEqual(first.students[0].estimate.condition_probabilities,again.students[0].estimate.condition_probabilities)
        self.assertEqual(first.students[0].estimate.estimate_id,again.students[0].estimate.estimate_id)
        self.assertEqual(weekly_uncertainty_sets(first)[0].radius,weekly_uncertainty_sets(again)[0].radius)
        self.assertEqual(weekly_uncertainty_sets(first),weekly_uncertainty_sets(again))
        c.run_week()
        c.notes = [replace(c.notes[0],note_id='later-copy',available_week=2)]
        later = c.prepare_decision_snapshot()
        self.assertEqual(dict(later.students[0].estimate.uncertainty)['new_condition_evidence_ids'],())

    def test_conflicting_evidence_neither_refreshes_nor_shrinks(self):
        c = self.controller()
        c.run_week()
        c.notes = [n for n in c.notes if n.source_week == 0]
        baseline = c.prepare_decision_snapshot()
        c.notes.append(WeeklyNote('conflict','s0',1,2,REGULAR+' '+LOW,('conflict1',)))
        after = c.prepare_decision_snapshot()
        self.assertEqual(after.students[0].estimate.last_observation_week,0)
        self.assertEqual(after.students[0].estimate.condition_probabilities,baseline.students[0].estimate.condition_probabilities)
        ua,ub = weekly_uncertainty_sets(after)[0],weekly_uncertainty_sets(baseline)[0]
        self.assertTrue(ua.conflict)
        self.assertGreaterEqual(ua.radius,ub.radius)

    def test_quarantine_does_not_manufacture_condition_measurement(self):
        c = self.controller()
        c.run_week()
        c.notes = [n for n in c.notes if n.source_week == 0]
        class Reject:
            def extract(self,*args):
                raise ValueError('invalid assertion')
        c.extractor = Reject()
        c.notes.append(WeeklyNote('rejected','s0',1,2,REGULAR,('new1',)))
        state = c.prepare_decision_snapshot()
        u = weekly_uncertainty_sets(state)[0]
        self.assertEqual(u.latest_assimilated_source_week,0)
        self.assertTrue(u.rejected_condition_observation)
        self.assertFalse(u.newly_assimilated_evidence_ids)

    def test_future_and_workflow_notes_do_not_override_condition(self):
        c = self.controller()
        before = c.prepare_decision_snapshot()
        c.notes.extend([WeeklyNote('future','s0',1,2,REGULAR,('future1',)),
            WeeklyNote('status','s0',0,1,'The student completed the scheduled mentoring appointments.',('status0',),
                'm0','known-programme')])
        after = c.prepare_decision_snapshot()
        self.assertEqual(before.students[0].estimate.condition_probabilities,after.students[0].estimate.condition_probabilities)
        self.assertEqual(before.students[0].estimate.last_observation_week,after.students[0].estimate.last_observation_week)
        self.assertNotIn('future',c.processed)
        self.assertEqual(c.snapshots,[])

    def test_uncertainty_ignores_hidden_truth_and_is_reproducible(self):
        a,b = world(),world()
        from src.school.student_condition import StudentCondition
        b._conditions['s0'] = StudentCondition.DISENGAGED
        self.assertEqual(weekly_uncertainty_sets(a.prepare_decision()),weekly_uncertainty_sets(b.prepare_decision()))
        self.assertEqual(weekly_uncertainty_sets(a.prepare_decision()),weekly_uncertainty_sets(a.prepare_decision()))

    def test_new_valid_signal_can_supersede_an_older_conflict(self):
        c = self.controller()
        c.notes[0] = replace(c.notes[0],text=REGULAR+' '+LOW)
        c.run_week()
        c.notes = [c.notes[0],WeeklyNote('fresh','s0',1,2,LOW,('source1',))]
        u = weekly_uncertainty_sets(c.prepare_decision_snapshot())[0]
        self.assertFalse(u.conflict)
        self.assertEqual(u.latest_assimilated_source_week,1)
        self.assertEqual(u.radius,.25)

    def test_matched_information_conditions_change_valuation_without_claiming_superiority(self):
        for mode in ('fair_point','fair_robust'):
            accurate = boundary_episode(mode=mode,boundary=False)
            stale = boundary_episode(mode=mode,boundary=False,information='stale_missing')
            self.assertEqual(accurate.snapshots[0],stale.snapshots[0])
            ua,ub = accurate.decisions[1].uncertainty_sets,stale.decisions[1].uncertainty_sets
            self.assertTrue(all(a.radius < b.radius for a,b in zip(ua,ub)))
            self.assertNotEqual(accurate.decisions[1].continuation_reviews[0].continuation_value,
                stale.decisions[1].continuation_reviews[0].continuation_value)

    def test_same_cutoff_preparation_is_idempotent_for_policy_decisions(self):
        c = self.controller()
        a = c.prepare_decision_snapshot()
        b = c.prepare_decision_snapshot()
        self.assertEqual(a,b)
        self.assertEqual(WeeklyDeliveryPolicy(c.environment.config,'fair_robust').plan(a),
                         WeeklyDeliveryPolicy(c.environment.config,'fair_robust').plan(b))

    def test_candidate_order_and_zero_radius_point_equivalence(self):
        env = world(weekly_wait_matrix=WEEKLY_WAIT_V1,weekly_tutoring_matrix=WEEKLY_TUTORING_V1)
        state = env.prepare_decision()
        point,robust = (WeeklyDeliveryPolicy(env.config,m,uncertainty_radius=0).plan(state)
                        for m in ('fair_point','fair_robust'))
        self.assertEqual(point.offers,robust.offers)
        self.assertEqual(point.projected_offers,robust.projected_offers)
        self.assertAlmostEqual(point.objective,robust.objective)
        candidates = feasible_offers(state,env.config,end_week=4)
        policy = WeeklyDeliveryPolicy(env.config,'fair_robust')
        policy.plan(state)
        values = weekly_scenario_values(env.config,state,candidates,policy.last_scenarios)
        reversed_values = weekly_scenario_values(env.config,state,candidates[::-1],policy.last_scenarios)
        np.testing.assert_allclose(values,reversed_values[:,::-1],atol=1e-15)

    def test_robust_milp_matches_actual_finite_scenario_enumeration(self):
        from itertools import combinations
        from src.school.fairness_audit import required_access
        env = world(count=2,mentors=1,weekly_mentor_hours=1,max_concurrent_students=1,
            weekly_wait_matrix=WEEKLY_WAIT_V1,weekly_tutoring_matrix=WEEKLY_TUTORING_V1,
            budget=6,fairness_target=1)
        state = env.prepare_decision()
        policy = WeeklyDeliveryPolicy(env.config,'fair_robust')
        action = policy.plan(state)
        candidates = feasible_offers(state,env.config,end_week=4)
        values = weekly_scenario_values(env.config,state,candidates,policy.last_scenarios)
        choices = []
        for size in range(3):
            for indices in combinations(range(len(candidates)),size):
                selected = tuple(candidates[i] for i in indices)
                try:
                    validate_offers(state,DeliveryAction(selected),env.config,projected=True)
                except ValueError:
                    continue
                ids = {a.student_id for a in selected}
                deficit = sum(max(0,required_access(env.config.fairness_target,len(c.student_ids))
                    -len(set(c.student_ids)&ids))/len(c.student_ids)
                    for c in state.fairness_window.cohorts if c.student_ids)
                value = min(values[:,indices].sum(axis=1)) if indices else 0.
                choices.append((deficit,-value))
        optimum = min(choices)
        self.assertTrue(action.lexicographic_complete)
        self.assertAlmostEqual(action.projected_normalized_shortfall,optimum[0])
        self.assertAlmostEqual(action.objective,-optimum[1])
        validate_offers(state,action,env.config)


class CommittedForecastTests(unittest.TestCase):
    def active(self, **changes):
        env = world(weekly_wait_matrix=WEEKLY_WAIT_V1,weekly_tutoring_matrix=WEEKLY_TUTORING_V1,**changes)
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        return env

    def test_active_forecast_differs_and_no_commitments_agree(self):
        env = self.active()
        state = env.prepare_decision()
        self.assertLess(state.students[0].committed_risk.probability,state.students[0].risk.probability)
        for s in state.students[1:]:
            self.assertAlmostEqual(s.committed_risk.probability,s.risk.probability)
        state.validate_estimates()

    def test_cancelled_and_zero_effect_forecasts_agree(self):
        env = self.active()
        env.step(DeliveryAction(cancel_programme_ids=(env.programmes[0].programme_id,)))
        for s in env.prepare_decision().students:
            self.assertAlmostEqual(s.risk.probability,s.committed_risk.probability)
        zero = self.active(effect_strength=0)
        for s in zero.prepare_decision().students:
            self.assertAlmostEqual(s.risk.probability,s.committed_risk.probability)

    def test_accepted_does_not_receive_offer_probability_twice(self):
        env = self.active()
        p = env.programmes[0]
        a = remaining_marginals(env.config,2,p)
        b = remaining_marginals(replace(env.config,acceptance_probability=.01),2,p)
        np.testing.assert_allclose(a,b,atol=0)

    def test_cancellation_survival_matches_independent_path_enumeration(self):
        from itertools import product
        cfg = replace(world().config,horizon_weeks=4,cancellation_probability=.3,
            attendance_probability=.7,delivery_probability=.8,
            weekly_wait_matrix=WEEKLY_WAIT_V1,weekly_tutoring_matrix=WEEKLY_TUTORING_V1)
        w,t = np.asarray(cfg.weekly_wait_matrix),cfg.treatment_matrix
        mix = .56*t+.44*w
        result = np.zeros((4,4))
        # Enumerate first cancellation time, including survival to the end.
        for cancel in (2,3,4,5):
            probability = .7**(cancel-2)*.3 if cancel < 5 else .7**3
            op = np.eye(4)
            for week in range(2,5):
                op = op @ (mix if week < cancel else w)
            result += probability*op
        np.testing.assert_allclose(terminal_operator(cfg,2,(2,3,4),offer_week=1),result,atol=1e-14)

    def test_past_misses_and_completions_have_no_future_effect(self):
        env = self.active()
        p = env.programmes[0]
        modified = replace(p,sessions=(replace(p.sessions[0],status='MISSED'),*p.sessions[1:]))
        np.testing.assert_allclose(remaining_marginals(env.config,2,p),remaining_marginals(env.config,2,modified))
        from src.school.delivery_forecasts import committed_support_risk
        s = env.prepare_decision().students[0]
        r = committed_support_risk(env.config,s.estimate,(replace(p,status='COMPLETED'),))
        self.assertAlmostEqual(r.probability,s.risk.probability)

    def test_forecast_uses_assumptions_not_future_draws_and_checks_versions(self):
        env = self.active()
        state = env.prepare_decision()
        env.exogenous_draws.append({'future_attendance':False})
        self.assertEqual(state,env.prepare_decision())
        for s in state.students:
            self.assertTrue(0 <= s.risk.probability <= 1)
            self.assertTrue(0 <= s.committed_risk.probability <= 1)
        bad = replace(state.students[0],committed_risk=replace(state.students[0].committed_risk,input_estimate_id='wrong'))
        with self.assertRaises(ValueError):
            replace(state,students=(bad,*state.students[1:])).validate_estimates()


class FairnessBoundTests(unittest.TestCase):
    def test_terminal_window_has_zero_capacity_and_nonempty_denominator(self):
        from src.school.delivery_config import DeliveryConfig
        from src.school.delivery_experiments import synthetic_environment
        identity = tuple(tuple(float(i == j) for j in range(4)) for i in range(4))
        env = synthetic_environment(DeliveryConfig(num_students=3,num_mentors=1,
            weekly_wait_matrix=identity,weekly_tutoring_matrix=identity))
        for _ in range(8):
            env.step(DeliveryAction())
        state = env.prepare_decision()
        d = offer_feasibility_diagnostics(state,env.config)
        self.assertEqual(d['frozen_eligible_students'],3)
        self.assertEqual(d['maximum_attainable_unique_offers'],0)
        self.assertEqual(d['feasible_candidate_starts'],0)
        self.assertEqual(d['unavoidable_shortfall_under_frozen_model'],d['required_unique_offers'])
        self.assertTrue(d['terminal_no_carryover_infeasibility'])
        self.assertEqual((d['window_start_week'],d['window_end_week']),(9,12))

    def test_enough_and_overloaded_capacity_match_exhaustive_joint_bound(self):
        from itertools import combinations
        for hours in (1,2,3):
            env = world(count=3,mentors=1,weekly_mentor_hours=hours,
                weekly_session_capacity=hours,max_concurrent_students=hours,budget=30,fairness_target=1)
            state = env.prepare_decision()
            candidates = feasible_offers(state,env.config,end_week=4)
            maximum = 0
            for size in range(1,4):
                for selected in combinations(candidates,size):
                    try:
                        validate_offers(state,DeliveryAction(selected),env.config,projected=True)
                    except ValueError:
                        continue
                    maximum = max(maximum,len({a.student_id for a in selected}))
            d = offer_feasibility_diagnostics(state,env.config)
            self.assertEqual(maximum,hours)
            self.assertEqual(d['maximum_attainable_unique_offers'],maximum)
            self.assertEqual(d['unavoidable_shortfall_under_frozen_model'],3-maximum)
            self.assertEqual(d['actual_coverage_shortfall'],3)
            self.assertEqual(d['additional_shortfall_beyond_frozen_model'],maximum)
            self.assertEqual(sum(c['attainable_unique_offers_in_joint_witness'] for c in d['cohort_witness']),maximum)

    def test_shared_budget_limits_unique_starts(self):
        env = world(budget=5.1,fairness_target=1)
        d = offer_feasibility_diagnostics(env.prepare_decision(),env.config)
        self.assertEqual(d['maximum_attainable_unique_offers'],1)
        self.assertEqual(d['unavoidable_shortfall_under_frozen_model'],2)

    def test_refusal_duplicates_and_cancellation_do_not_erase_offer(self):
        from src.school.delivery_fairness import offer_fairness_rows
        env = world(count=1,mentors=1)
        frozen = env.prepare_decision()
        for w in (1,2):
            env.step(DeliveryAction((SupportOffer('s0','m0',w),)),outcomes={('s0','acceptance',w):False})
        d = offer_feasibility_diagnostics(frozen,env.config,env.events)
        self.assertEqual(d['actual_unique_offers'],1)
        self.assertEqual(d['maximum_attainable_unique_offers'],1)
        c = boundary_episode(REGULAR)
        rows = offer_fairness_rows(c.environment.windows[0],c.environment.events,c.environment.config)
        self.assertEqual(sum(r['unique_offers'] for r in rows),2)
        self.assertTrue(all('stratum' in r and 'group' in r for r in rows))


class VersionedReplayTests(unittest.TestCase):
    def test_saved_risk_labels_and_independently_rebuilt_summary(self):
        import tempfile,json
        from pathlib import Path
        from src.school.delivery_experiments import save_delivery_episode,replay_delivery_episode,read_delivery_episode
        from src.evaluation.provenance import artifact_hashes
        c = boundary_episode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'episode'
            save_delivery_episode(c,path)
            manifest,payload = read_delivery_episode(path)
            self.assertEqual(manifest['contract'],'scheduled_weekly/replay/v3')
            self.assertEqual(payload['decision_snapshots'][1]['contract'],'scheduled_weekly/decision/v3')
            self.assertEqual(replay_delivery_episode(path)['status'],'exact_replay_verified')
            summary = json.loads((path/'summary.json').read_text())
            self.assertIn('no future tutoring',summary['risk_targets']['usual_support'])
            self.assertIn('continue accepted schedules',summary['risk_targets']['committed_support'])
            summary['risk_targets']['committed_support'] = 'wrong forecast regime'
            (path/'summary.json').write_text(json.dumps(summary))
            # A self-consistent seal is not proof of scientific correctness.
            # Rebuild the summary independently instead of trusting its label.
            (path/'artifact_integrity.json').write_text(json.dumps(artifact_hashes(path)))
            with self.assertRaisesRegex(ValueError,'summary mismatch'):
                replay_delivery_episode(path)


if __name__ == '__main__':
    unittest.main()
