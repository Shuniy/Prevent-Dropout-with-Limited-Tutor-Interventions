"""Scientific separation, common-information planning and weekly offer fairness."""
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import unittest

from src.school.delivery_config import DeliveryConfig, load_world_config
from src.school.delivery_contracts import DeliveryAction, SupportOffer
from src.school.delivery_controller import WeeklyFeedbackController
from src.school.delivery_experiments import save_delivery_episode, replay_delivery_episode, normalized, scorecard
from src.school.delivery_fairness import offer_fairness_rows
from src.school.delivery_policy import WeeklyDeliveryPolicy, delivery_rollout_marginals
from src.school.delivery_resources import feasible_offers, validate_offers
from src.school.student_condition import StudentCondition
from src.school.scenario_config import ScenarioConfig
from tests.test_delivery_lifecycle import world


class ResourceTests(unittest.TestCase):
    def test_independent_auditor_rejects_double_charge_with_fresh_event_id(self):
        from src.school.delivery_resources import audit_delivery_events
        env=world()
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        delivered=next(e for e in env.events if e.kind=='session_delivered')
        with self.assertRaisesRegex(ValueError,'double charged'):
            audit_delivery_events(env.config,env.mentors,(*env.events,replace(delivered,event_id='forged')))

    def test_zero_hour_calendar_is_rejected_in_weekly_world(self):
        from src.school.delivery_environment import WeeklyDeliveryEnvironment
        from src.school.mentor import Mentor
        from src.school.mentor_availability import MentorAvailability
        from src.school.delivery_contracts import StudentProfile
        config = DeliveryConfig(num_students=1,num_mentors=1)
        mentor = Mentor('m', ['tutoring'], 1,
            availability_by_step=[MentorAvailability(1, 0, 5)], cost_units_per_session=1)
        with self.assertRaisesRegex(ValueError, 'nonzero working hours'):
            WeeklyDeliveryEnvironment((StudentProfile('s','tutoring',.5,False,'F'),), (mentor,),
                config, initial_conditions=(('s',StudentCondition.STABLE),))

    def test_future_calendar_reduction_rejects_programme_at_start(self):
        env = world()
        mentor = env.mentors[0]
        env.mentors = (replace(mentor, calendar=tuple(
            (w, '0', 0) if w==4 else (w,h,slots) for w,h,slots in mentor.calendar)),*env.mentors[1:])
        with self.assertRaises(ValueError):
            env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        self.assertFalse(env.events)

    def test_working_hours_and_session_slots_are_independent(self):
        for settings in ({'weekly_mentor_hours': 1, 'weekly_session_capacity': 2},
                         {'weekly_mentor_hours': 2, 'weekly_session_capacity': 1}):
            with self.subTest(settings=settings):
                env = world(**settings)
                with self.assertRaises(ValueError):
                    env.step(DeliveryAction((SupportOffer('s0','m0',1), SupportOffer('s1','m0',1))))

    def test_caseload_consumed_in_gaps_between_sessions(self):
        env = world(sessions_required=3, session_cadence_weeks=2, max_concurrent_students=1)
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        with self.assertRaisesRegex(ValueError, 'caseload'):
            env.step(DeliveryAction((SupportOffer('s1','m0',2),)))

    def test_existing_commitments_block_then_release_future_slots(self):
        env = world(weekly_mentor_hours=1, weekly_session_capacity=1)
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        self.assertNotIn(SupportOffer('s1','m0',2), feasible_offers(env.prepare_decision(), env.config))
        env.step(DeliveryAction(cancel_programme_ids=(env.programmes[0].programme_id,)))
        self.assertIn(SupportOffer('s1','m0',3), feasible_offers(env.prepare_decision(), env.config))

    def test_zero_budget_and_zero_cost_services(self):
        env = world(budget=0, cost_per_session=0, administrative_offer_cost=0)
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        self.assertEqual(float(env.ledger.spent), 0)
        self.assertEqual(float(env.ledger.reserved), 0)

    def test_decimal_budget_cannot_overspend_by_solver_tolerance(self):
        env = world(budget=.49999999999, cost_per_session=.1, administrative_offer_cost=0)
        with self.assertRaisesRegex(ValueError, 'budget'):
            env.step(DeliveryAction((SupportOffer('s0','m0',1),)))

    def test_duplicate_student_and_incompatible_support_rejected(self):
        env = world()
        with self.assertRaises(ValueError):
            env.step(DeliveryAction((SupportOffer('s0','m0',1), SupportOffer('s0','m1',1))))
        env.profiles = (replace(env.profiles[0], support_type='transport_assessment'), *env.profiles[1:])
        with self.assertRaises(ValueError):
            env.step(DeliveryAction((SupportOffer('s0','m0',1),)))

    def test_missed_charge_and_wasted_slot_are_separate(self):
        env = world(cost_per_session=1, missed_session_cost=.25, administrative_offer_cost=.1)
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)), outcomes={('s0','attendance',1):False})
        self.assertEqual(float(env.ledger.spent), .35)
        self.assertEqual(float(env.ledger.reserved), 4)
        cell = next(c for c in env.ledger.cells if c.mentor_id == 'm0' and c.week == 1)
        self.assertEqual(cell.wasted_slots, 1)
        self.assertEqual(cell.delivered_sessions, 0)
        self.assertEqual(float(cell.released_money), .75)

    def test_three_students_two_mentors_hand_calculated_overlapping_demand(self):
        env = world(weekly_mentor_hours=1, weekly_session_capacity=1, max_concurrent_students=1,
            cost_per_session=.2, administrative_offer_cost=.1, budget=3, fairness_target=1)
        initial = env.prepare_decision()
        self.assertEqual(sum(len(c.student_ids) for c in initial.fairness_window.cohorts), 3)
        env.step(DeliveryAction((SupportOffer('s0','m0',1), SupportOffer('s1','m1',1))))
        self.assertAlmostEqual(float(env.ledger.reserved), 1.6)
        self.assertAlmostEqual(float(env.ledger.spent), .6)
        with self.assertRaises(ValueError):
            env.step(DeliveryAction((SupportOffer('s2','m0',2),)))
        for _ in range(4):
            env.step(DeliveryAction())
        self.assertEqual(sum(p.status == 'COMPLETED' for p in env.programmes), 2)
        self.assertAlmostEqual(float(env.ledger.spent), 2.2)
        self.assertAlmostEqual(float(env.ledger.spendable), .8)
        rows = offer_fairness_rows(initial.fairness_window, env.events, env.config)
        # Need strata now use processed evidence at explicit preparation. Sum
        # group counts across those strata for this resource-accounting check.
        false = {k: sum(r[k] for r in rows if r['group']=='False') for k in (
            'frozen_eligible_students', 'unique_offers', 'shortfall', 'completed_students')}
        true = {k: sum(r[k] for r in rows if r['group']=='True') for k in (
            'frozen_eligible_students', 'unique_offers', 'shortfall', 'completed_students')}
        self.assertEqual((false['frozen_eligible_students'], false['unique_offers'], false['shortfall']), (2,1,1))
        self.assertEqual((true['frozen_eligible_students'], true['unique_offers'], true['shortfall']), (1,1,0))
        self.assertEqual((false['completed_students'], true['completed_students']), (1,1))


class FairnessTests(unittest.TestCase):
    def test_accepted_and_multiple_deliveries_still_count_one_offer(self):
        env = world()
        window = env.prepare_decision().fairness_window
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        for _ in range(2):
            env.step(DeliveryAction())
        rows = offer_fairness_rows(window, env.events, env.config)
        self.assertEqual(sum(r['unique_offers'] for r in rows),1)
        self.assertEqual(sum(r['accepted_students'] for r in rows),1)
        self.assertEqual(sum(r['completed_students'] for r in rows),0)

    def test_strict_infeasibility_never_relaxes_hard_capacity(self):
        env = world(budget=0, fairness_target=1, fairness_allow_shortfall=False)
        for mode in ('fair_point','fair_robust'):
            action = WeeklyDeliveryPolicy(env.config,mode).plan(env.prepare_decision())
            self.assertEqual(action.status,'fairness_infeasible')
            self.assertFalse(action.offers)
            validate_offers(env.prepare_decision(),action,env.config)

    def test_repeat_refusals_count_once_and_never_count_as_completion(self):
        env = world()
        window = env.prepare_decision().fairness_window
        for week in (1,2):
            env.step(DeliveryAction((SupportOffer('s0','m0',week),)), outcomes={('s0','acceptance',week):False})
        rows = offer_fairness_rows(window, env.events, env.config)
        row = next(r for r in rows if r['group']=='False' and r['frozen_eligible_students'])
        self.assertEqual(row['unique_offers'], 1)
        self.assertEqual(row['accepted_students'], 0)
        self.assertEqual(row['completed_students'], 0)

    def test_five_week_programme_keeps_original_offer_window(self):
        env = world()
        first = env.prepare_decision().fairness_window
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        for _ in range(3):
            env.step(DeliveryAction())
        second = env.prepare_decision().fairness_window
        self.assertEqual((second.start_week, second.end_week), (5,8))
        env.step(DeliveryAction())
        rows = offer_fairness_rows(first, env.events, env.config)
        self.assertEqual(sum(r['unique_offers'] for r in rows), 1)
        self.assertEqual(sum(r['completed_students'] for r in rows), 1)
        self.assertEqual(sum(r['completed_within_offer_window'] for r in rows), 0)
        self.assertEqual(sum(r['unique_offers'] for r in offer_fairness_rows(second, env.events, env.config)), 0)

    def test_frozen_denominator_survives_withdrawal(self):
        withdraw = ((0.,0.,0.,1.),)*4
        env = world(weekly_wait_matrix=withdraw, weekly_tutoring_matrix=withdraw)
        window = env.prepare_decision().fairness_window
        env.step(DeliveryAction())
        self.assertEqual(sum(len(c.student_ids) for c in window.cohorts), 3)
        rows = offer_fairness_rows(window, env.events, env.config)
        self.assertEqual(sum(r['frozen_eligible_students'] for r in rows), 3)
        self.assertEqual(sum(s.eligible for s in env.prepare_decision().students), 0)

    def test_empty_small_groups_and_infeasible_targets_expose_shortfall(self):
        env = world(budget=0, fairness_target=1)
        state = env.prepare_decision()
        action = WeeklyDeliveryPolicy(env.config, 'fair_point').plan(state)
        self.assertFalse(action.offers)
        self.assertGreater(action.projected_normalized_shortfall, 0)
        rows = offer_fairness_rows(state.fairness_window, env.events, env.config)
        self.assertTrue(any(r['offer_coverage'] is None for r in rows))
        self.assertTrue(any(r['small_group'] for r in rows))
        validate_offers(state, action, env.config)


class ScientificTests(unittest.TestCase):
    def test_future_draw_changes_are_absent_from_current_snapshot(self):
        env=world()
        state=env.prepare_decision()
        env.exogenous_draws.append({'key':('s0','attendance',5),'outcome':False})
        self.assertEqual(state,env.prepare_decision())

    def test_withdrawal_cancels_only_future_delivery_at_next_cutoff(self):
        withdraw = ((0.,0.,0.,1.),)*4
        env = world(weekly_wait_matrix=withdraw, weekly_tutoring_matrix=withdraw,
            administrative_offer_cost=0)
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        self.assertEqual(env.programmes[0].status,'CANCELLED')
        self.assertEqual(env.programmes[0].delivered_sessions,1)
        self.assertEqual(float(env.ledger.spent),1)
        self.assertEqual(float(env.ledger.reserved),0)
        cancellation = next(e for e in env.events if e.kind=='programme_cancelled')
        self.assertEqual((cancellation.source_week,cancellation.available_week),(1,2))
        self.assertIn(cancellation.event_id,env.prepare_decision().authorized_event_ids)

    def test_failed_note_extraction_does_not_change_hidden_delivery(self):
        class BrokenExtractor:
            def extract(self,*args):
                raise ValueError('unsupported assertion')
        a,b = world(),world()
        ca = WeeklyFeedbackController(a,WeeklyDeliveryPolicy(a.config,'random'))
        cb = WeeklyFeedbackController(b,WeeklyDeliveryPolicy(b.config,'random'),extractor=BrokenExtractor())
        ca.run_episode()
        cb.run_episode()
        self.assertEqual(a.evaluator_truth,b.evaluator_truth)
        self.assertEqual(a.events,b.events)
        self.assertTrue(all(r['status']=='quarantined' for r in cb.attempts))
        self.assertTrue(all(s.estimate.last_observation_week is None for s in cb.final_snapshot.students))

    def test_full_weekly_schedule_rollout_matches_hand_formula(self):
        import numpy as np
        cfg = replace(DeliveryConfig(),horizon_weeks=5,acceptance_probability=.5,
            attendance_probability=.8,delivery_probability=.75,cancellation_probability=0)
        wait,treatment = np.asarray(cfg.weekly_wait_matrix),cfg.treatment_matrix
        q=.8*.75
        terminal=np.array([1,1,1,0])
        expected=.5*(np.linalg.matrix_power(q*treatment+(1-q)*wait,5)
                     -np.linalg.matrix_power(wait,5)) @ terminal
        np.testing.assert_allclose(delivery_rollout_marginals(cfg,1,1),expected,atol=1e-14)

    def test_offer_acceptance_without_delivery_matches_wait_truth(self):
        treatment = ((1.,0.,0.,0.), (1.,0.,0.,0.), (1.,0.,0.,0.), (0.,0.,0.,1.))
        offered, wait = world(weekly_tutoring_matrix=treatment), world(weekly_tutoring_matrix=treatment)
        offered.step(DeliveryAction((SupportOffer('s0','m0',1),)), outcomes={('s0','delivery',1):False})
        wait.step(DeliveryAction())
        self.assertEqual(offered.evaluator_truth, wait.evaluator_truth)
        self.assertEqual(dict(offered.evaluator_truth[-1][1])['s0'],StudentCondition.VULNERABLE)

    def test_actual_delivery_changes_only_the_delivered_week_transition(self):
        identity = tuple(tuple(float(i==j) for j in range(4)) for i in range(4))
        treatment = ((1.,0.,0.,0.), (1.,0.,0.,0.), (1.,0.,0.,0.), (0.,0.,0.,1.))
        delivered = world(weekly_wait_matrix=identity, weekly_tutoring_matrix=treatment)
        wait = world(weekly_wait_matrix=identity, weekly_tutoring_matrix=treatment)
        delivered.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        wait.step(DeliveryAction())
        self.assertEqual(dict(delivered.evaluator_truth[-1][1])['s0'], StudentCondition.STABLE)
        self.assertEqual(dict(wait.evaluator_truth[-1][1])['s0'], StudentCondition.VULNERABLE)
        self.assertEqual(dict(wait.evaluator_truth[-1][1])['s1'], dict(delivered.evaluator_truth[-1][1])['s1'])

    def test_zero_effect_matched_draws_entire_trajectory(self):
        from src.school.delivery_config import WEEKLY_WAIT_V1, WEEKLY_TUTORING_V1
        a, b = (world(effect_strength=0, weekly_wait_matrix=WEEKLY_WAIT_V1,
                      weekly_tutoring_matrix=WEEKLY_TUTORING_V1) for _ in range(2))
        a.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        b.step(DeliveryAction())
        while not a.done:
            a.step(DeliveryAction())
            b.step(DeliveryAction())
        self.assertEqual(a.evaluator_truth, b.evaluator_truth)

    def test_hidden_only_changes_leave_public_snapshot_and_decision_identical(self):
        a, b = world(), world()
        # Hold all authorized inputs fixed; modify evaluator truth alone.
        b._conditions['s0'] = StudentCondition.DISENGAGED
        self.assertEqual(a.prepare_decision(), b.prepare_decision())
        for mode in WeeklyDeliveryPolicy.MODES:
            self.assertEqual(WeeklyDeliveryPolicy(a.config, mode).plan(a.prepare_decision()),
                             WeeklyDeliveryPolicy(b.config, mode).plan(b.prepare_decision()))

    def test_delayed_note_cannot_rewrite_earlier_snapshot(self):
        env = world()
        c = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config, 'wait'))
        note = next(n for n in c.notes if n.student_id == 's0' and n.source_week == 0)
        c.notes.remove(note)
        c.run_week()
        previous = c.snapshots[0]
        c.notes.append(replace(note, note_id='delayed', available_week=3,
            text='The school reports low participation in recent activities.'))
        c.run_week()
        self.assertNotIn('delayed', c.processed)
        c.run_week()
        self.assertIn('delayed', c.processed)
        self.assertEqual(next(a['status'] for a in c.attempts if a['note_id'] == 'delayed'), 'accepted')
        self.assertEqual(c.snapshots[0], previous)

    def test_estimate_and_risk_versions_match_and_snapshot_has_no_future_draws(self):
        env = world()
        c = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config, 'priority'))
        c.run_week()
        state = c.prepare_decision_snapshot()
        state.validate_estimates()
        for student in state.students:
            self.assertEqual(student.risk.input_estimate_id, student.estimate.estimate_id)
        encoded = str(asdict(state))
        for forbidden in ('_conditions', 'exogenous_draws', 'future_attendance', 'response_coefficient'):
            self.assertNotIn(forbidden, encoded)
        bad = replace(state.students[0], risk=replace(state.students[0].risk, input_estimate_id='stale'))
        with self.assertRaises(ValueError):
            replace(state, students=(bad,*state.students[1:])).validate_estimates()

    def test_unrelated_programme_does_not_shift_keyed_draws(self):
        a,b = world(),world()
        a.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        b.step(DeliveryAction((SupportOffer('s0','m0',1),SupportOffer('s1','m1',1))))
        self.assertEqual([d for d in a.exogenous_draws if d['key'][0]=='s0'],
                         [d for d in b.exogenous_draws if d['key'][0]=='s0'])

    def test_transition_stream_is_separate_and_offer_draws_do_not_enter_policy(self):
        env = world()
        env.step(DeliveryAction((SupportOffer('s0','m0',1),)))
        streams = [d['stream'] for d in env.exogenous_draws if d['key'][0]=='s0']
        self.assertEqual(len(streams), len(set(streams)))
        self.assertTrue(any('acceptance' in s for s in streams))
        self.assertTrue(any('attendance' in s for s in streams))
        self.assertTrue(any('transition' in s for s in streams))

    def test_delivery_rollout_zero_uptake_or_zero_effect_is_zero(self):
        import numpy as np
        for changes in ({'acceptance_probability':0}, {'attendance_probability':0}, {'effect_strength':0}):
            config = replace(DeliveryConfig(), **changes)
            np.testing.assert_allclose(delivery_rollout_marginals(config, 1, 1), 0, atol=1e-14)


class ExecutionTests(unittest.TestCase):
    def test_replay_preserves_exact_integer_calendar_and_price_representations(self):
        env=world(weekly_mentor_hours=2,cost_per_session=1)
        c=WeeklyFeedbackController(env,WeeklyDeliveryPolicy(env.config,'priority')).run_episode()
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'integer_calendar'
            save_delivery_episode(c,source)
            self.assertEqual(replay_delivery_episode(source)['status'],'exact_replay_verified')

    def test_small_start_milp_matches_exhaustive_feasible_subsets(self):
        from itertools import combinations
        from src.school.delivery_config import WEEKLY_WAIT_V1,WEEKLY_TUTORING_V1
        from src.school.fairness_audit import required_access
        env=world(count=2,mentors=1,weekly_mentor_hours=1,max_concurrent_students=1,
            weekly_wait_matrix=WEEKLY_WAIT_V1,weekly_tutoring_matrix=WEEKLY_TUTORING_V1,
            fairness_target=1,budget=6)
        state=env.prepare_decision()
        candidates=feasible_offers(state,env.config,end_week=4)
        feasible=[]
        for size in range(3):
            for selected in combinations(candidates,size):
                try:
                    validate_offers(state,DeliveryAction(selected),env.config,projected=True)
                except ValueError:
                    continue
                ids={a.student_id for a in selected}
                shortfall=sum(max(0,required_access(env.config.fairness_target,len(c.student_ids))
                    -len(set(c.student_ids)&ids))/len(c.student_ids)
                    for c in state.fairness_window.cohorts if c.student_ids)
                belief={s.student_id:s.estimate.condition_probabilities for s in state.students}
                value=sum(float(__import__('numpy').asarray(belief[a.student_id]) @
                    delivery_rollout_marginals(env.config,1,a.start_week)) for a in selected)
                feasible.append((shortfall,-value))
        optimum=min(feasible)
        action=WeeklyDeliveryPolicy(env.config,'fair_point').plan(state)
        self.assertTrue(action.lexicographic_complete)
        self.assertAlmostEqual(action.projected_normalized_shortfall,optimum[0])
        self.assertAlmostEqual(action.objective,-optimum[1])
        robust=WeeklyDeliveryPolicy(env.config,'fair_robust',uncertainty_radius=0).plan(state)
        self.assertEqual(action.offers,robust.offers)
        self.assertEqual(action.projected_offers,robust.projected_offers)

    def test_weekly_cli_rejects_monthly_units(self):
        import subprocess,sys
        result=subprocess.run([sys.executable,'-m','src.main','--runner','delivery','--months','12'],
            capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('weekly delivery requires --weeks',result.stderr)
        self.assertNotIn('Traceback',result.stderr)

    def test_all_six_policies_complete_common_weekly_contract(self):
        for mode in WeeklyDeliveryPolicy.MODES:
            with self.subTest(mode=mode):
                env = world()
                c = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config, mode)).run_episode()
                c.validate()
                self.assertEqual(len(c.snapshots), 8)
                self.assertEqual(len(c.decisions), 8)

    def test_same_seed_same_events_snapshots_decisions(self):
        def run():
            env = world()
            return WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config,'priority')).run_episode()
        self.assertEqual(normalized(run().environment.events), normalized(run().environment.events))

    def test_replay_retains_refusal_miss_cancel_and_completion(self):
        env = world(count=4)
        c = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(env.config,'priority'))
        def outcomes(week):
            return {('s0','acceptance',week):False, ('s1','attendance',2):False,
                    ('s2','cancellation',2):True}
        c.run_episode(outcome_provider=outcomes)
        kinds = {e.kind for e in env.events}
        self.assertTrue({'offer_refused','session_missed','programme_cancelled','programme_completed'} <= kinds)
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/'original', Path(directory)/'replayed'
            save_delivery_episode(c, source)
            result = replay_delivery_episode(source, output)
            self.assertEqual(result['status'], 'exact_replay_verified')
            with self.assertRaises(FileExistsError):
                save_delivery_episode(c, source)
            self.assertEqual(scorecard(c)['overbooking_checks'], 'passed_independent_event_reconstruction')

    def test_explicit_mode_configuration_dispatch_and_invalid_combinations(self):
        self.assertEqual(ScenarioConfig().world_mode, 'atomic_monthly')
        self.assertEqual(load_world_config('configs/delivery_weekly_v1.toml').time_unit, 'week')
        self.assertEqual(load_world_config('configs/cmdp.toml').time_unit, 'month')
        for changes in ({'time_unit':'month'}, {'fairness_window_weeks':5},
                        {'weekly_mentor_hours':0}, {'rescheduling_policy':'automatic'},
                        {'transition_version':'monthly'}, {'missed_session_cost':2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(DeliveryConfig(), **changes)


if __name__ == '__main__':
    unittest.main()
