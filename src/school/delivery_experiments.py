"""Immutable weekly v1 episodes, exact offline replay, and bounded scorecards."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from ..evaluation.provenance import (digest, runtime_identity, source_fingerprints,
    staged_artifacts, seal_directory, verify_directory, extractor_identity)
from ..intervention.feedback_notes import NoteQuality
from ..intervention.observation_extractor import RecordedOutcomeExtractor
from .delivery_config import DeliveryConfig
from .delivery_contracts import StudentProfile, WeeklyNote
from .delivery_controller import WeeklyFeedbackController
from .delivery_environment import WeeklyDeliveryEnvironment
from .delivery_fairness import offer_fairness_rows, offer_feasibility_diagnostics
from .delivery_policy import WeeklyDeliveryPolicy
from .mentor import Mentor
from .mentor_availability import MentorAvailability
from .student_condition import StudentCondition
from .money import amount
from .observation_model import ObservationConfig


PROTOCOL_PATH = Path(__file__).resolve().parents[2]/'docs'/'phase4_1_adaptive_delivery_correctness.md'


def normalized(value):
    return json.loads(json.dumps(value, default=lambda x: asdict(x), sort_keys=True, allow_nan=False))


def scorecard(controller):
    env = controller.environment
    ledger = controller.validate()
    events = env.events
    counts = {kind: sum(e.kind == kind for e in events) for kind in (
        'support_offered', 'offer_accepted', 'offer_refused', 'programme_active',
        'session_delivered', 'session_missed', 'programme_completed', 'programme_cancelled', 'programme_incomplete')}
    fairness = []
    feasibility = []
    terminal_conditions = dict(env.evaluator_truth[-1][1])
    for window in env.windows:
        frozen = next(s for s in controller.snapshots if s.week == window.start_week)
        feasibility.append(offer_feasibility_diagnostics(frozen,env.config,events))
        cohorts = {(c.group,c.stratum): c.student_ids for c in window.cohorts}
        rows = offer_fairness_rows(window,events,env.config)
        for row in rows:
            ids = cohorts[(row['group'],row['stratum'])]
            row['evaluator_terminal_retention'] = sum(terminal_conditions[sid] != StudentCondition.WITHDRAWN
                for sid in ids)/len(ids) if ids else None
        fairness.extend(rows)
    workload = []
    for mentor in env.mentors:
        cells = [c for c in ledger.cells if c.mentor_id == mentor.mentor_id]
        available_hours = sum(float(c.available_hours) for c in cells)
        delivered_hours = sum(float(c.delivered_hours) for c in cells)
        workload.append(dict(mentor_id=mentor.mentor_id, delivered_hours=delivered_hours,
            available_hours=available_hours, utilization=delivered_hours/available_hours if available_hours else None,
            delivered_sessions=sum(c.delivered_sessions for c in cells),
            missed_wasted_slots=sum(c.wasted_slots for c in cells),
            unused_hours=sum(float(c.unused_hours) for c in cells),
            peak_concurrent_students=max((len(c.active_students) for c in cells), default=0),
            reserved_money=sum(float(c.reserved_money) for c in cells),
            spent_money=sum(float(c.spent_money) for c in cells)))
    return dict(stage='bounded_synthetic_development_not_statistical_policy_evidence',
        policy=controller.policy.mode, time_unit='week', **counts,
        reserved_money=ledger.reserved, spent_money=ledger.spent,
        released_liabilities=ledger.released, administration_cost=ledger.administrative_cost,
        remaining_unspent_budget=str(amount(ledger.budget)-amount(ledger.spent)),
        spendable_budget=ledger.spendable, overbooking_checks='passed_independent_event_reconstruction',
        mentor_workload=workload, fairness=fairness, fairness_feasibility=feasibility,
        risk_targets=dict(usual_support='WeeklyRisk.probability: synthetic terminal non-enrollment; no future tutoring',
            committed_support='WeeklyCommittedRisk.probability: continue accepted schedules, no new offers',
            approximation='joint_active_inactive_expected_weekly_delivery/v1'),
        extraction_attempts=len(controller.attempts),
        quarantined_extractions=sum(a['status'] == 'quarantined' for a in controller.attempts),
        actionable_extraction_opportunities=sum(r['actionable_extraction_attempts'] for r in controller.extraction_diagnostics
                                               if r['has_allocation_decision']),
        eligible_cutoff_pairs_with_new_usable_evidence=sum(len(r['newly_usable_eligible_ids'])
            for r in controller.extraction_diagnostics if r['has_allocation_decision']),
        solver_statuses=[a.status for a in controller.decisions],
        simulated_terminal_retention=env.terminal_reward(),
        initial_cohort_size=len(env.profiles))


def episode_payload(controller):
    controller.validate()
    env = controller.environment
    return dict(contract='scheduled_weekly/replay/v2',
        notes=[{**asdict(n), 'creation_time': n.creation_time} for n in controller.notes],
        extraction_attempts=controller.attempts,
        actionable_extraction_diagnostics=controller.extraction_diagnostics,
        # Explicit adapters: source_month/as_of_month mean source/as-of WEEK
        # within these existing extractor/filter payloads only.
        extraction_period_adapter='week_indices_in_legacy_schema/v1',
        extracted_batches=controller.batches, estimate_updates=controller.estimator.updates,
        decision_snapshots=controller.snapshots, allocation_decisions=controller.decisions,
        final_snapshot=controller.final_snapshot, events=env.events, programmes=env.programmes,
        resource_records=env.records, fairness_windows=env.windows,
        authorized_signals=[dict(event_id=e.event_id, student_id=e.student_id, source_week=e.event_month,
            available_week=e.available_from_month, signal=e.signal) for e in env.emitted_signals],
        administrative_enrollment=[dict(student_id=r.student_id, source_week=r.event_month,
            available_week=r.available_from_month, enrolled=r.enrolled) for r in env.enrollment_history])


def save_delivery_episode(controller, output):
    """Validate, serialize, seal, verify, publish once; never replace a run."""
    payload = normalized(episode_payload(controller))
    env = controller.environment
    manifest = dict(contract='scheduled_weekly/replay/v2', scenario=asdict(env.config),
        policy=controller.policy.configuration, note_quality=asdict(controller.note_quality),
        estimator=controller.estimator.configuration,
        observation_config=asdict(env.observation_config),
        initial_authorized_profiles=[asdict(p) for p in env.profiles],
        initial_and_future_mentor_calendars=[asdict(m) for m in env.mentors],
        extractor=extractor_identity(controller.extractor),
        protocol_text=PROTOCOL_PATH.read_text(),
        protocol_sha256=digest(PROTOCOL_PATH.read_text()),
        provenance=dict(runtime=runtime_identity(), source_fingerprints=source_fingerprints()),
        payload_sha256=digest(payload))
    manifest['episode_identity'] = digest(manifest)
    with staged_artifacts(output, identity={'weekly_episode': manifest['episode_identity']}) as staging:
        (staging/'episode.json').write_text(json.dumps(payload, sort_keys=True, indent=2, allow_nan=False))
        (staging/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False))
        (staging/'summary.json').write_text(json.dumps(scorecard(controller), sort_keys=True, indent=2, allow_nan=False))
        evaluator = staging/'evaluator_only'
        evaluator.mkdir()
        (evaluator/'world.json').write_text(json.dumps(normalized(dict(
            initial_conditions=env.initial_conditions, truth=env.evaluator_truth,
            exogenous_draws=env.exogenous_draws)), sort_keys=True, indent=2))
        seal_directory(staging)
        verify_directory(staging)
    return manifest['episode_identity']


def read_delivery_episode(source):
    """Read/verify v1 or v2 artifacts without claiming execution compatibility.

    Historical v1 exact execution belongs to its fingerprinted original checkout
    and runtime. This reader preserves access without weakening those guards.
    """
    source = Path(source)
    verify_directory(source)
    manifest = json.loads((source/'manifest.json').read_text())
    if manifest.get('contract') not in ('scheduled_weekly/replay/v1', 'scheduled_weekly/replay/v2'):
        raise ValueError('unsupported weekly replay contract')
    if digest({k:v for k,v in manifest.items() if k != 'episode_identity'}) != manifest['episode_identity']:
        raise ValueError('weekly manifest identity mismatch')
    payload = json.loads((source/'episode.json').read_text())
    if digest(payload) != manifest['payload_sha256']:
        raise ValueError('weekly payload identity mismatch')
    if digest(manifest['protocol_text']) != manifest['protocol_sha256']:
        raise ValueError('weekly protocol identity mismatch')
    return manifest,payload


def replay_delivery_episode(source, output=None):
    """Re-run public policy decisions and hidden transitions without a live LLM."""
    source = Path(source)
    manifest,payload = read_delivery_episode(source)
    if source_fingerprints() != manifest['provenance']['source_fingerprints']:
        raise ValueError('exact weekly replay requires recorded source/configuration versions')
    if manifest['contract'] == 'scheduled_weekly/replay/v1':
        raise ValueError('v1 remains readable; exact execution requires its archived v1 source and runtime')
    if (manifest['protocol_text'] != PROTOCOL_PATH.read_text()
            or digest(manifest['protocol_text']) != manifest['protocol_sha256']):
        raise ValueError('weekly protocol version mismatch')
    runtime = runtime_identity()
    if any(runtime[k] != manifest['provenance']['runtime'][k] for k in ('python', 'implementation', 'dependencies')):
        raise ValueError('exact weekly replay requires recorded runtime/dependencies')
    config = DeliveryConfig(**manifest['scenario'])
    mentors = tuple(Mentor(m['mentor_id'], list(m['support_types']), m['max_concurrent_students'],
        # Preserve decimal representation as well as numeric value. Converting
        # a saved '2' to float 2.0 changes exact ledger strings and snapshot IDs.
        availability_by_step=[MentorAvailability(w, amount(h), slots) for w,h,slots in m['calendar']],
        cost_units_per_session=amount(m['cost_per_session'])) for m in manifest['initial_and_future_mentor_calendars'])
    world = json.loads((source/'evaluator_only'/'world.json').read_text())
    env = WeeklyDeliveryEnvironment(tuple(StudentProfile(**p) for p in manifest['initial_authorized_profiles']),
        mentors, config, initial_conditions=tuple(tuple(row) for row in world['initial_conditions']),
        observation_config=ObservationConfig(**manifest['observation_config']))
    policy_record = manifest['policy']
    policy = WeeklyDeliveryPolicy(config, policy_record['mode'], uncertainty_radius=policy_record['uncertainty_radius'],
        continuation_margin=policy_record['continuation_margin'],
        minimum_review_age_weeks=policy_record['minimum_review_age_weeks'])
    if policy.configuration != policy_record:
        raise ValueError('weekly policy configuration mismatch')
    notes = {n['note_id']: WeeklyNote(**{**{k:v for k,v in n.items() if k != 'creation_time'},
        'source_event_ids': tuple(n['source_event_ids'])}) for n in payload['notes']}
    extractor = RecordedOutcomeExtractor(payload['extraction_attempts'], payload['extracted_batches'])
    controller = WeeklyFeedbackController(env, policy, extractor=extractor,
        note_quality=NoteQuality(**manifest['note_quality']), recorded_notes=notes)
    overrides = {}
    for row in world['exogenous_draws']:
        if 'outcome' in row:
            overrides.setdefault(row['key'][2], {})[tuple(row['key'])] = row['outcome']
    controller.run_episode(outcome_provider=lambda week: overrides.get(week, {}))
    if normalized(episode_payload(controller)) != payload:
        raise ValueError('weekly replay mismatch in decisions, estimates, events, observations or ledger')
    if normalized(scorecard(controller)) != json.loads((source/'summary.json').read_text()):
        raise ValueError('weekly replay summary mismatch in risk labels, fairness feasibility or resource diagnostics')
    if normalized(dict(initial_conditions=env.initial_conditions, truth=env.evaluator_truth,
                       exogenous_draws=env.exogenous_draws)) != world:
        raise ValueError('weekly replay evaluator trajectory/randomness mismatch')
    result = dict(status='exact_replay_verified', episode_identity=manifest['episode_identity'],
                  compared='all_decisions_events_resources_observations_estimates_fairness_and_hidden_trajectories')
    if output is not None:
        with staged_artifacts(output, identity={'replay_of': manifest['episode_identity']}) as staging:
            (staging/'replay_result.json').write_text(json.dumps(result, indent=2))
            seal_directory(staging)
            verify_directory(staging)
    return result


def synthetic_environment(config, *, num_students=None, num_mentors=None):
    """Wholly fictional cohort, no source microdata or inferred socioeconomic traits."""
    num_students = config.num_students if num_students is None else num_students
    num_mentors = config.num_mentors if num_mentors is None else num_mentors
    if num_students != config.num_students or num_mentors != config.num_mentors:
        from dataclasses import replace
        config = replace(config,num_students=num_students,num_mentors=num_mentors)
    profiles = tuple(StudentProfile(f'fictional-{i:02d}', 'tutoring', .5,
        bool(i % 2), 'F' if i % 2 else 'M') for i in range(num_students))
    mentors = tuple(Mentor(f'mentor-{i}', ['tutoring'], config.max_concurrent_students,
        availability_by_step=[MentorAvailability(w, config.weekly_mentor_hours,
            config.weekly_session_capacity) for w in range(1, config.horizon_weeks+1)],
        cost_units_per_session=config.cost_per_session) for i in range(num_mentors))
    return WeeklyDeliveryEnvironment(profiles, mentors, config,
        initial_conditions=tuple((p.student_id, (StudentCondition.VULNERABLE,
            StudentCondition.DISENGAGED, StudentCondition.STABLE)[i % 3]) for i,p in enumerate(profiles)))


def run_demonstration(config, output):
    """One paired seed for engineering acceptance; no superiority inference."""
    output = Path(output)
    with staged_artifacts(output, identity={'phase4_demo': digest(asdict(config))}) as staging:
        summaries = []
        for mode in WeeklyDeliveryPolicy.MODES:
            env = synthetic_environment(config)
            controller = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(config, mode)).run_episode()
            save_delivery_episode(controller, staging/mode)
            replay_delivery_episode(staging/mode, staging/(mode+'_replay'))
            summaries.append(scorecard(controller))
        # A guaranteed lifecycle trace supplements stochastic development runs.
        # All weekly transitions are identity in this fixture only.
        from dataclasses import replace
        identity = tuple(tuple(float(i==j) for j in range(4)) for i in range(4))
        fixture_config = replace(config, weekly_wait_matrix=identity, weekly_tutoring_matrix=identity,
            acceptance_probability=1, attendance_probability=1, delivery_probability=1,
            cancellation_probability=0, horizon_weeks=max(8, config.horizon_weeks), budget=50,
            weekly_mentor_hours=2, weekly_session_capacity=2, max_concurrent_students=2,
            session_duration_hours=1, sessions_required=5, session_cadence_weeks=1,
            num_students=4,num_mentors=2,cost_per_session=1,administrative_offer_cost=.1,
            missed_session_cost=0)
        env = synthetic_environment(fixture_config)
        controller = WeeklyFeedbackController(env, WeeklyDeliveryPolicy(fixture_config, 'priority'))
        controller.run_episode(outcome_provider=lambda week: {
            ('fictional-00', 'acceptance', week): False,
            ('fictional-01', 'attendance', 2): False,
            ('fictional-02', 'cancellation', 2): True,
        })
        if not {'offer_refused', 'session_missed', 'programme_cancelled', 'programme_completed'} <= {e.kind for e in env.events}:
            raise ValueError('guaranteed lifecycle fixture failed to exercise its declared paths')
        save_delivery_episode(controller, staging/'guaranteed_lifecycle')
        replay_delivery_episode(staging/'guaranteed_lifecycle', staging/'guaranteed_lifecycle_replay')
        summaries.append(scorecard(controller))
        (staging/'scorecards.json').write_text(json.dumps(summaries, indent=2, sort_keys=True))
        lines = ['# Phase 4 bounded delivery demonstration', '',
            'Synthetic engineering example, one seed; no statistical policy ranking.', '',
            '| Policy | Offers | Accepted | Delivered | Complete | Missed | Cancelled/incomplete | Spent | Reserved | Retained |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for row in summaries:
            lines.append(f"| {row['policy']} | {row['support_offered']} | {row['offer_accepted']} | "
                f"{row['session_delivered']} | {row['programme_completed']} | {row['session_missed']} | "
                f"{row['programme_cancelled']+row['programme_incomplete']} | {row['spent_money']} | "
                f"{row['reserved_money']} | {row['simulated_terminal_retention']} |")
        (staging/'scorecard.md').write_text('\n'.join(lines)+'\n')
        seal_directory(staging)
        verify_directory(staging)
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/delivery_weekly_v1.toml')
    parser.add_argument('--output', required=True)
    parser.add_argument('--replay')
    args = parser.parse_args()
    if args.replay:
        print(json.dumps(replay_delivery_episode(args.replay, args.output), indent=2))
    else:
        rows = run_demonstration(DeliveryConfig.load(args.config), args.output)
        print(json.dumps([{k:v for k,v in r.items() if k not in ('fairness', 'mentor_workload', 'solver_statuses')}
                          for r in rows], indent=2))


if __name__ == '__main__':
    main()
