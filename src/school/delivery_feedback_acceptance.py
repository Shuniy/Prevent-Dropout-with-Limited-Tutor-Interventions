"""Phase 4.2 matched actual-session mentor-feedback acceptance; offline only."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from .delivery_acceptance import LOW, VAGUE, _mentors
from .delivery_config import DeliveryConfig
from .delivery_controller import WeeklyFeedbackController
from .delivery_environment import WeeklyDeliveryEnvironment
from .delivery_experiments import (normalized, synthetic_environment, scorecard,
    save_delivery_episode, replay_delivery_episode, episode_payload)
from .delivery_policy import WeeklyDeliveryPolicy
from .observation_model import ObservationConfig


class MentorBoundaryController(WeeklyFeedbackController):
    """Explicit controlled language channel, never direct posterior/action edits.

    School information is fixed in every arm. The focal student's source-week 1
    condition is supplied solely by their actual delivered-session measurement.
    """
    def __init__(self, *args, unsupported_text=None, **kwargs):
        self.unsupported_text = unsupported_text
        super().__init__(*args, **kwargs)

    def _generate_notes(self):
        super()._generate_notes()
        result = []
        for note in self.notes:
            if not note.programme_id:
                text = LOW if note.source_week == 0 or (
                    note.source_week == 1 and note.student_id != 'fictional-00') else VAGUE
                note = replace(note, text=text)
            elif (self.unsupported_text is not None and note.observation_contract
                    and note.student_id == 'fictional-00' and note.source_week == 1):
                note = replace(note, text=self.unsupported_text)
            result.append(note)
        self.notes = result


def mentor_boundary_episode(signal='regular_participation', *, unsupported_text=None,
                            extra_reads=False, seed=41, mode='point'):
    config = DeliveryConfig(num_students=3, num_mentors=1, horizon_weeks=8,
        weekly_mentor_hours=1, weekly_session_capacity=1, max_concurrent_students=1,
        acceptance_probability=1, attendance_probability=1, delivery_probability=1,
        cancellation_probability=0, budget=11, seed=seed)
    original = synthetic_environment(config)
    session = f'{seed}:fictional-00:weekly-programme:1:session:1'
    env = WeeklyDeliveryEnvironment(original.profiles, _mentors(config), config,
        initial_conditions=original.initial_conditions,
        observation_config=ObservationConfig(missing_probability=0, delay_probability=0),
        mentor_signal_overrides=((session, signal),))
    if extra_reads:
        env.observe()
        env.observe()
    c = MentorBoundaryController(env, WeeklyDeliveryPolicy(config, mode, continuation_margin=.01),
        unsupported_text=unsupported_text)
    while not env.done:
        if extra_reads:
            env.observe()
            env.observe()
        c.run_week()
        if extra_reads:
            env.observe()
            env.observe()
    c.final_snapshot = c.prepare_decision_snapshot()
    c.validate()
    return c


def mentor_chain(c):
    env = c.environment
    observation = next(e for e in env.emitted_mentor_signals
        if e.student_id == 'fictional-00' and e.source_week == 1)
    note = next(n for n in c.notes if n.source_event_ids == (observation.event_id,))
    student = c.snapshots[1].students[0]
    return normalized(dict(
        actual_delivery=next(e for e in env.events if e.event_id == observation.delivery_event_id),
        mentor_observation=observation, note=note,
        extraction_attempt=next(a for a in c.attempts if a['note_id'] == note.note_id),
        validated_evidence=next(b for b in c.batches if b.note_id == note.note_id),
        estimate_update=next(u for u in c.estimator.updates if u.student_id == 'fictional-00' and u.month == 2),
        posterior=student.estimate, usual_support_risk=student.risk,
        committed_support_risk=student.committed_risk,
        uncertainty=c.decisions[1].uncertainty_sets[0],
        continuation_review=c.decisions[1].continuation_reviews[0],
        decision=c.decisions[1], ledger_before=c.snapshots[1].ledger,
        ledger_next_cutoff=c.snapshots[2].ledger,
        later_offers=[dict(week=s.week, offers=a.offers) for s, a in zip(c.snapshots[2:], c.decisions[2:]) if a.offers],
        delivered_sessions=[e for e in env.events if e.kind == 'session_delivered'],
        frozen_windows=env.windows, fairness_initializations=env.window_initializations,
        resource_records=env.records, trajectory=env.evaluator_truth,
        final_scorecard=scorecard(c)))


def run_acceptance(output):
    from ..evaluation.provenance import staged_artifacts, seal_directory, verify_directory
    with staged_artifacts(Path(output), identity={'phase4_2_acceptance': 1}) as stage:
        arms = dict(regular=mentor_boundary_episode(),
            low=mentor_boundary_episode('low_participation'),
            unsupported=mentor_boundary_episode(unsupported_text=VAGUE),
            unsupported_extra=mentor_boundary_episode(unsupported_text=VAGUE+' The mentor will follow up.'),
            extra_reads=mentor_boundary_episode(extra_reads=True))
        a, b = arms['regular'], arms['low']
        if (a.decisions[1].continuation_reviews[0].decision,
                b.decisions[1].continuation_reviews[0].decision) != ('cancel', 'continue'):
            raise AssertionError('mentor observations did not cross constructed decision boundary')
        if not a.decisions[2].offers or a.decisions[1].offers:
            raise AssertionError('released resources must support a later feasible offer')
        if arms['unsupported'].snapshots != arms['unsupported_extra'].snapshots or (
                arms['unsupported'].decisions != arms['unsupported_extra'].decisions):
            raise AssertionError('unsupported prose changed estimates or actions')
        if normalized(episode_payload(a)) != normalized(episode_payload(arms['extra_reads'])) or (
                a.environment.evaluator_truth != arms['extra_reads'].environment.evaluator_truth):
            raise AssertionError('read order changed actual execution')
        if scorecard(a) != scorecard(arms['extra_reads']):
            raise AssertionError('extra reads changed fairness scorecards')
        replays = {}
        for name, c in arms.items():
            save_delivery_episode(c, stage/name)
            replays[name] = replay_delivery_episode(stage/name, stage/(name+'_replay'))
        report = dict(contract='scheduled_weekly/mentor_acceptance/v1', seed=41,
            scope='bounded_synthetic_decision_boundary_not_empirical_effect_or_policy_ranking',
            counterfactual={name: mentor_chain(c) for name, c in arms.items()},
            fairness_extra_reads='identical_execution_including_weeks_4_to_5', replays=replays)
        (stage/'acceptance_report.json').write_text(json.dumps(report, indent=2, sort_keys=True))
        seal_directory(stage)
        verify_directory(stage)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = run_acceptance(args.output)
    print(json.dumps(dict(status='acceptance_verified', episodes=len(report['replays']),
        replays={k: v['status'] for k, v in report['replays'].items()}), indent=2))


if __name__ == '__main__':
    main()
