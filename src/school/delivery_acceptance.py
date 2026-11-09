"""Reproducible Phase 4.1 acceptance; wholly fictional, no live inference."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path

from .delivery_config import DeliveryConfig
from .delivery_controller import WeeklyFeedbackController
from .delivery_environment import WeeklyDeliveryEnvironment
from .delivery_experiments import normalized, save_delivery_episode, replay_delivery_episode, synthetic_environment
from .delivery_policy import WeeklyDeliveryPolicy
from .observation_model import ObservationConfig


REGULAR = 'The school reports regular participation in recent activities.'
LOW = 'The school reports low participation in recent activities.'
VAGUE = 'There is insufficient evidence about participation.'


class InformationConditionController(WeeklyFeedbackController):
    """Controlled note channel. Only one condition fact differs between arms.

    Source identities, authorized timestamps, initial truth and emission draws
    remain unchanged. This is an information intervention, not outcome editing.
    """
    def __init__(self, *args, changed_text=REGULAR, information='accurate', boundary=True, **kwargs):
        self.changed_text, self.information, self.boundary = changed_text, information, boundary
        super().__init__(*args, **kwargs)

    def _generate_notes(self):
        super()._generate_notes()
        notes = []
        for note in self.notes:
            if not note.programme_id:
                if self.boundary and note.source_week == 0:
                    note = replace(note, text=LOW)
                elif self.boundary and note.source_week == 1:
                    note = replace(note, text=self.changed_text if note.student_id == 'fictional-00' else LOW)
                if self.information == 'stale_missing' and note.source_week >= 1:
                    note = replace(note, text=VAGUE)
            notes.append(note)
        self.notes = notes


def boundary_episode(text=REGULAR, *, mode='point', information='accurate', margin=.01, seed=41, boundary=True):
    config = DeliveryConfig(num_students=3,num_mentors=1,horizon_weeks=8,
        weekly_mentor_hours=1,weekly_session_capacity=1,max_concurrent_students=1,
        acceptance_probability=1,attendance_probability=1,delivery_probability=1,
        cancellation_probability=0,budget=11,seed=seed)
    original = synthetic_environment(config)
    env = WeeklyDeliveryEnvironment(original.profiles,
        # Reuse explicit immutable calendars via ordinary mentor construction.
        _mentors(config),config,initial_conditions=original.initial_conditions,
        observation_config=ObservationConfig(missing_probability=0,delay_probability=0),
        mentor_observations_enabled=False)  # Preserve the historical school-note counterfactual.
    policy = WeeklyDeliveryPolicy(config,mode,continuation_margin=margin)
    return InformationConditionController(env,policy,changed_text=text,information=information,
        boundary=boundary).run_episode()


def _mentors(config):
    from .mentor import Mentor
    from .mentor_availability import MentorAvailability
    return (Mentor('mentor-0',['tutoring'],config.max_concurrent_students,
        availability_by_step=[MentorAvailability(w,config.weekly_mentor_hours,config.weekly_session_capacity)
            for w in range(1,config.horizon_weeks+1)],cost_units_per_session=config.cost_per_session),)


def causal_chain(controller):
    s = controller.snapshots[1].students[0]
    action = controller.decisions[1]
    note = next(n for n in controller.notes if n.student_id == s.student_id and n.source_week == 1 and not n.programme_id)
    batch = next(b for b in controller.batches if b.note_id == note.note_id)
    env = controller.environment
    return normalized(dict(note=note,validated_evidence=batch,estimate=s.estimate,
        seed=env.config.seed,
        usual_support_risk=s.risk,committed_support_risk=s.committed_risk,
        continuation_reviews=action.continuation_reviews,action=action,
        commitments_before=controller.snapshots[1].ledger,
        commitments_after=controller.snapshots[2].ledger,
        subsequent_offers=[a.offers for a in controller.decisions[2:]],
        delivered_service=[e for e in env.events if e.kind == 'session_delivered'],
        simulated_trajectory=env.evaluator_truth,terminal_retained=env.terminal_reward(),
        uncertainty_sets=[a.uncertainty_sets for a in controller.decisions],
        cutoff_records=[dict(week=s.week,students=s.students,action=a)
                        for s,a in zip(controller.snapshots,controller.decisions)],
        solver_statuses=[a.status for a in controller.decisions]))


def run_acceptance(output):
    from ..evaluation.provenance import staged_artifacts,seal_directory,verify_directory
    output = Path(output)
    with staged_artifacts(output,identity={'phase4_1_acceptance':1}) as stage:
        arms = {name:boundary_episode(text) for name,text in (('regular',REGULAR),('low',LOW),
            ('negative_a',VAGUE),('negative_b',VAGUE+' The mentor will follow up.'))}
        regular,low = arms['regular'],arms['low']
        if bool(regular.decisions[1].cancel_programme_ids) == bool(low.decisions[1].cancel_programme_ids):
            raise AssertionError('constructed observation did not cross continuation boundary')
        if arms['negative_a'].decisions != arms['negative_b'].decisions:
            raise AssertionError('unsupported prose changed a decision')
        comparisons = {}
        for seed in (41,42):
            for mode in ('fair_point','fair_robust'):
                for info in ('accurate','stale_missing'):
                    name = mode+'_'+info+'_'+str(seed)
                    arms[name] = boundary_episode(REGULAR,mode=mode,information=info,boundary=False,seed=seed)
                    comparisons[name] = causal_chain(arms[name])
        replays = {}
        for name,c in arms.items():
            c.validate()
            save_delivery_episode(c,stage/name)
            replays[name] = replay_delivery_episode(stage/name,stage/(name+'_replay'))
        report = dict(contract='scheduled_weekly/acceptance/v1',seed=41,comparison_seeds=[41,42],
            scope='bounded_synthetic_engineering_example_not_policy_superiority',
            counterfactual={name:causal_chain(arms[name]) for name in ('regular','low','negative_a','negative_b')},
            matched_information_policy_comparison=comparisons,replays=replays)
        (stage/'acceptance_report.json').write_text(json.dumps(report,indent=2,sort_keys=True))
        for name in arms:
            for expected in ('episode.json','manifest.json','summary.json','artifact_integrity.json','evaluator_only/world.json'):
                if not (stage/name/expected).is_file():
                    raise AssertionError('missing acceptance artifact: '+name+'/'+expected)
        seal_directory(stage)
        verify_directory(stage)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    report = run_acceptance(args.output)
    print(json.dumps(dict(status='acceptance_verified',episodes=len(report['replays']),
        replays={k:v['status'] for k,v in report['replays'].items()}),indent=2))


if __name__ == '__main__':
    main()
