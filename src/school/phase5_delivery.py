"""Opt-in Phase 5 adapters; historical weekly and monthly entrypoints unchanged."""
from dataclasses import asdict
import json
from pathlib import Path

from ..evaluation.provenance import (digest, runtime_identity, source_fingerprints,
    staged_artifacts, seal_directory, verify_directory, write_exclusive, extractor_identity)
from ..intervention.feedback_notes import NoteQuality
from ..intervention.observation_extractor import RecordedOutcomeExtractor
from .delivery_config import DeliveryConfig
from .delivery_contracts import DeliveryAction, WeeklyNote
from .delivery_controller import WeeklyFeedbackController
from .delivery_environment import WeeklyDeliveryEnvironment
from .delivery_experiments import synthetic_environment, normalized, episode_payload, scorecard
from .delivery_policy import WeeklyDeliveryPolicy
from .delivery_resources import feasible_offers, validate_offers
from .loading import create_mentors
from .observation_model import ObservationConfig
from .population_sampling import sample_population, PopulationGeneratorConfig, population_validation
from .trained_withdrawal_risk import TrainedWithdrawalRiskModel, decision_features


def population_environment(config, *, population_mode='legacy_fixed_fixture', split=None,
                           population_seed=None, generator=PopulationGeneratorConfig(), observation_config=ObservationConfig()):
    if population_mode == 'legacy_fixed_fixture':
        if split is not None or population_seed is not None:
            raise ValueError('legacy fictional fixture has no source split/seed')
        return synthetic_environment(config),None
    if population_mode != 'source_held_out' or split is None or population_seed is None:
        raise ValueError('source-held-out mode requires explicit split and population seed')
    population = sample_population(split,config.num_students,population_seed,generator_config=generator)
    mentors = create_mentors(config.num_mentors,num_months=config.horizon_weeks,
        students_per_mentor=config.max_concurrent_students,sessions_per_student=config.weekly_session_capacity,
        support_type='tutoring',cost_units_per_session=config.cost_per_session)
    # Full schedules need actual hours, not the monthly helper's zero-hour calendars.
    from .mentor_availability import MentorAvailability
    for mentor in mentors:
        mentor.availability_by_step = [MentorAvailability(w,config.weekly_mentor_hours,config.weekly_session_capacity)
                                      for w in range(1,config.horizon_weeks+1)]
    env = WeeklyDeliveryEnvironment.from_students(population.students(),mentors,config)
    # Reconstruct with a declared observation law; the adapter intentionally keeps
    # the old from_students signature and all existing callers unchanged.
    if observation_config != env.observation_config:
        env = WeeklyDeliveryEnvironment(env.profiles,mentors,config,
            initial_conditions=env.initial_conditions,observation_config=observation_config)
    return env,population


class PredictionController(WeeklyFeedbackController):
    def __init__(self,*args,trained_model=None,prediction_horizon=4,**kwargs):
        self.trained_model,self.prediction_horizon=trained_model,prediction_horizon
        self.trained_predictions=[]
        self._predicted_cutoffs=set()
        self._prediction_snapshot_cache=None
        super().__init__(*args,**kwargs)

    def prepare_decision_snapshot(self):
        if self._prediction_snapshot_cache is not None and self._prediction_snapshot_cache.week==self.environment.week:
            return self._prediction_snapshot_cache
        state=super().prepare_decision_snapshot()
        if self.trained_model is not None and state.week not in self._predicted_cutoffs:
            for student in state.students:
                features=decision_features(student,cutoff_week=state.week,remaining_weeks=state.weeks_remaining,
                    config=self.environment.config,horizon=self.prediction_horizon)
                self.trained_predictions.append(self.trained_model.predict(features,
                    expected_estimate_id=student.estimate.estimate_id,expected_model_version=self.trained_model.version))
            self._predicted_cutoffs.add(state.week)
        self._prediction_snapshot_cache=state
        return state


class ResearchInformationController(PredictionController):
    MODES=('structured_observable','random_missing','group_dependent','corrupted_language','heldout_style')

    def __init__(self,*args,information_mode='structured_observable',**kwargs):
        if information_mode not in self.MODES:
            raise ValueError('unsupported frozen information condition')
        self.information_mode=information_mode
        self._information_generated=set()
        super().__init__(*args,**kwargs)

    def _generate_notes(self):
        # Generate fresh text independently before verifying recorded prose.
        recorded=self.recorded_notes
        self.recorded_notes=None
        try:
            super()._generate_notes()
        finally:
            self.recorded_notes=recorded
        from dataclasses import replace
        from ..intervention.feedback_notes import render_note
        from .delivery_observations import render_mentor_note
        from ..evaluation.phase5_language import CASES
        from ..intervention.feedback_notes import SIGNAL_PHRASES,MENTOR_SIGNAL_PHRASES
        from ..observations.observable_events import SIGNALS
        env=self.environment
        groups={p.student_id:getattr(p,env.config.fairness_grouping_attribute) for p in env.profiles}
        school={e.event_id:e for e in env.emitted_signals}
        mentor={e.event_id:e for e in env.emitted_mentor_signals}
        heldout={signal:next(row[2] for row in CASES['test'] if row[3]==label)
                 for signal,label in zip(SIGNALS,('regular','difficulty','low','no_contact'))}
        result=[]
        for note in self.notes:
            if note.note_id not in self._information_generated:
                mode=self.information_mode
                quality=NoteQuality()
                if mode=='random_missing':
                    quality=NoteQuality(omission_probability=.3)
                elif mode=='group_dependent':
                    poorer_documentation=(groups[note.student_id]=='F' if env.config.fairness_grouping_attribute=='sex_source'
                                          else groups[note.student_id] is True)
                    quality=NoteQuality(omission_probability=.6 if poorer_documentation else .15,
                        conflict_probability=.2 if poorer_documentation else .1,
                        misleading_probability=.1 if poorer_documentation else .05,
                        delay_probability=.25 if poorer_documentation else .1)
                elif mode=='corrupted_language':
                    quality=NoteQuality(omission_probability=.25,conflict_probability=.2,
                        misleading_probability=.1,delay_probability=.2,ambiguity_probability=.1)
                source=note.source_event_ids[0]
                if source in school:
                    rendered=render_note(school[source],seed=env.config.seed,quality=quality)
                    note=replace(note,text=rendered.text,available_week=rendered.available_from_month)
                elif source in mentor:
                    note=render_mentor_note(mentor[source],seed=env.config.seed,quality=quality)
                if mode in ('heldout_style','corrupted_language'):
                    for signal in SIGNALS:
                        for phrase in (SIGNAL_PHRASES[signal],MENTOR_SIGNAL_PHRASES[signal]):
                            note=replace(note,text=note.text.replace(phrase,heldout[signal]))
                if recorded is not None and recorded.get(note.note_id)!=note:
                    raise ValueError('frozen Phase 5 information generation mismatch')
                self._information_generated.add(note.note_id)
            result.append(note)
        self.notes=result


class TrainedRiskPriorityPolicy(WeeklyDeliveryPolicy):
    """Separate risk-target baseline; never substitutes WeeklyRisk or benefit."""
    def __init__(self,config,model,horizon=4):
        super().__init__(config,'priority')
        self.model,self.horizon=model,horizon

    @property
    def configuration(self):
        return {**super().configuration,'contract':'trained_risk_priority/v1',
            'trained_model_version':self.model.version,'horizon':self.horizon,
            'failure_rule':'unavailable_students_not_offered; no fallback'}

    def _plan_offers(self,state):
        probabilities={}
        for s in state.students:
            f=decision_features(s,cutoff_week=state.week,remaining_weeks=state.weeks_remaining,
                config=self.config,horizon=self.horizon)
            p=self.model.predict(f,expected_estimate_id=s.estimate.estimate_id,expected_model_version=self.model.version)
            if p.probability is not None:
                probabilities[s.student_id]=p.probability
        candidates=feasible_offers(state,self.config,end_week=state.week)
        selected=[]
        for offer in sorted((a for a in candidates if a.student_id in probabilities),
                            key=lambda a:(-probabilities[a.student_id],a.student_id,a.mentor_id)):
            try:
                validate_offers(state,DeliveryAction(tuple([*selected,offer])),self.config)
            except ValueError:
                continue
            selected.append(offer)
        return DeliveryAction(tuple(selected),status='feasible_trained_event_risk_priority',lexicographic_complete=True)


def phase5_payload(controller):
    return normalized(dict(weekly=episode_payload(controller),
        predictions=getattr(controller,'trained_predictions',[])))


def save_phase5_episode(controller,population,output,*,protocol_text):
    if population is None:
        raise ValueError('Phase 5 replay requires explicit source lineage')
    env=controller.environment
    model=getattr(controller,'trained_model',None)
    manifest=dict(contract='phase5_source_weekly/replay/v1',scenario=asdict(env.config),
        population=asdict(population),population_identity=population.identity,
        policy=controller.policy.configuration,observation_config=asdict(env.observation_config),
        note_quality=asdict(controller.note_quality),extractor=extractor_identity(controller.extractor),
        trained_model=model.artifact if model is not None else None,
        prediction_horizon=getattr(controller,'prediction_horizon',4),
        information_mode=getattr(controller,'information_mode',None),
        protocol_text=protocol_text,protocol_identity=digest(protocol_text),
        runtime=runtime_identity(),source_fingerprints=source_fingerprints())
    payload=phase5_payload(controller)
    manifest['payload_identity']=digest(payload)
    manifest['identity']=digest(manifest)
    with staged_artifacts(output,identity={'phase5_episode':manifest['identity']}) as staging:
        write_exclusive(staging/'manifest.json',normalized(manifest))
        write_exclusive(staging/'episode.json',payload)
        write_exclusive(staging/'summary.json',normalized(scorecard(controller)))
        write_exclusive(staging/'population_validation.json',population_validation(population))
        write_exclusive(staging/'evaluator_only/world.json',normalized(dict(truth=env.evaluator_truth,
            initial_conditions=env.initial_conditions,exogenous_draws=env.exogenous_draws)))
        seal_directory(staging)
        verify_directory(staging)
    return manifest['identity']


def replay_phase5_episode(source,output=None,*,on_verified_controller=None):
    source=Path(source)
    verify_directory(source)
    manifest=json.loads((source/'manifest.json').read_text())
    payload=json.loads((source/'episode.json').read_text())
    if (manifest.get('contract') != 'phase5_source_weekly/replay/v1'
            or digest({k:v for k,v in manifest.items() if k!='identity'})!=manifest['identity']
            or digest(payload)!=manifest['payload_identity']
            or digest(manifest['protocol_text'])!=manifest['protocol_identity']):
        raise ValueError('Phase 5 manifest/payload/protocol mismatch')
    runtime=runtime_identity()
    if (source_fingerprints()!=manifest['source_fingerprints'] or
            any(runtime[k]!=manifest['runtime'][k] for k in ('python','implementation','dependencies'))):
        raise ValueError('exact Phase 5 replay requires recorded source/runtime')
    p=manifest['population']
    config=DeliveryConfig(**manifest['scenario'])
    env,population=population_environment(config,population_mode='source_held_out',split=p['split'],
        population_seed=p['population_seed'],generator=PopulationGeneratorConfig(**p['generator']),
        observation_config=ObservationConfig(**manifest['observation_config']))
    if population.identity!=manifest['population_identity'] or normalized(asdict(population))!=p:
        raise ValueError('source population/lineage reconstruction mismatch')
    model=TrainedWithdrawalRiskModel(manifest['trained_model']) if manifest['trained_model'] else None
    pc=manifest['policy']
    if pc['contract']=='trained_risk_priority/v1':
        if model is None:
            raise ValueError('missing priority model artifact')
        policy=TrainedRiskPriorityPolicy(config,model,pc['horizon'])
    else:
        policy=WeeklyDeliveryPolicy(config,pc['mode'],uncertainty_radius=pc['uncertainty_radius'],
            continuation_margin=pc['continuation_margin'],minimum_review_age_weeks=pc['minimum_review_age_weeks'])
    if policy.configuration!=pc:
        raise ValueError('Phase 5 policy reconstruction mismatch')
    weekly=payload['weekly']
    notes={n['note_id']:WeeklyNote(**{**{k:v for k,v in n.items() if k!='creation_time'},
        'source_event_ids':tuple(n['source_event_ids'])}) for n in weekly['notes']}
    controller_class=ResearchInformationController if manifest['information_mode'] is not None else PredictionController
    information={'information_mode':manifest['information_mode']} if manifest['information_mode'] is not None else {}
    controller=controller_class(env,policy,trained_model=model,prediction_horizon=manifest['prediction_horizon'],**information,
        extractor=RecordedOutcomeExtractor(weekly['extraction_attempts'],weekly['extracted_batches']),
        note_quality=NoteQuality(**manifest['note_quality']),recorded_notes=notes).run_episode()
    if (phase5_payload(controller)!=payload or normalized(scorecard(controller))!=json.loads((source/'summary.json').read_text())
            or normalized(population_validation(population))!=json.loads((source/'population_validation.json').read_text())
            or normalized(dict(truth=env.evaluator_truth,initial_conditions=env.initial_conditions,
                exogenous_draws=env.exogenous_draws))!=json.loads((source/'evaluator_only/world.json').read_text())):
        raise ValueError('Phase 5 exact replay mismatch')
    result=dict(status='exact_replay_verified',identity=manifest['identity'],
        compared='population,lineage,notes,extractions,beliefs,risks,actions,ledgers,fairness,truth,draws')
    if on_verified_controller is not None:
        on_verified_controller(controller,population)
    if output is not None:
        with staged_artifacts(output,identity={'replay_of':manifest['identity']}) as staging:
            write_exclusive(staging/'replay.json',result)
            seal_directory(staging)
            verify_directory(staging)
    return result
