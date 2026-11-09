"""Replay one recorded episode without invoking a language model."""

import json
from hashlib import sha256
from pathlib import Path

from ..intervention.feedback_notes import NoteQuality
from ..intervention.observation_extractor import RecordedOutcomeExtractor
from ..observations.observable_events import EnrollmentRecord, Note, ObservableEvent
from .closed_loop_controller import ClosedLoopCMDPController
from .feedback_experiments import _write_episode
from .observation_model import ObservationConfig, SyntheticObservationModel
from .scenario_config import ScenarioConfig
from .state_estimator import StudentStateEstimator
from .policy_configuration import reconstruct_policy
from .cmdp_environment import CMDPEnvironment
from .student_simulation import StudentSimulation
from .mentor import Mentor
from .mentor_availability import MentorAvailability
from ..evaluation.provenance import (digest, source_fingerprints, runtime_identity,
    staged_artifacts, seal_directory, verify_directory)


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class RecordedObservations(SyntheticObservationModel):
    """Authorized input history; evaluator truth is never an extraction input."""
    def __init__(self, source, config):
        super().__init__(config)
        self.events = [ObservableEvent(**r) for r in read_jsonl(source / "observable_events.jsonl")]
        self.registry = [EnrollmentRecord(**r) for r in read_jsonl(source / "administrative_enrollment.jsonl")]

    def generate(self, conditions, *, month, **kwargs):
        return (tuple(r for r in self.events if r.event_month == month),
                tuple(r for r in self.registry if r.event_month == month))


class ReplayController(ClosedLoopCMDPController):
    def __init__(self, *args, source, replay_provenance, **kwargs):
        super().__init__(*args, **kwargs)
        self.recorded_notes = {r["note_id"]: Note(**{**r, "source_event_ids": tuple(r["source_event_ids"])})
                              for r in read_jsonl(source / "mentor_notes.jsonl")}
        self.replay_provenance = replay_provenance

    def _generate_observations(self):
        super()._generate_observations()
        # Preserve exact recorded prose/dates, including custom fixture notes.
        self.notes = [self.recorded_notes[n.note_id] for n in self.notes]


def _replay_feedback_episode(source, output):
    source, output = Path(source), Path(output)
    manifest = json.loads((source / "experiment_config.json").read_text())
    if manifest.get('replay_contract_version') != 3:
        raise ValueError('incomplete historical record: exact replay requires contract version 3')
    if digest({k: v for k, v in manifest.items() if k not in ('episode_identity', 'replay_provenance')}) != manifest.get('episode_identity'):
        raise ValueError('replay configuration identity/integrity mismatch')
    config = ScenarioConfig(**manifest["scenario"])
    attempts_path = source / "extraction_attempts.jsonl"
    if not attempts_path.exists():
        raise ValueError("complete outcome replay requires extraction_attempts.jsonl; legacy batch-only traces are insufficient")
    attempts = read_jsonl(attempts_path)
    batches = read_jsonl(source / "extracted_observations.jsonl")
    extractor = RecordedOutcomeExtractor(attempts, batches)
    integrity_path = source / 'record_integrity.json'
    if not integrity_path.exists():
        raise ValueError('missing replay record integrity/provenance')
    integrity = json.loads(integrity_path.read_text())
    ignored = {'record_integrity.json'}
    if manifest.get('persistence_contract_version') != 1:
        ignored.add('replay_result.json')
    actual = {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
              and str(p.relative_to(source)) not in ignored}
    if set(integrity) != actual:
        raise ValueError('incomplete replay record inventory')
    for name, expected_hash in integrity.items():
        if sha256((source / name).read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f'replay record integrity mismatch: {name}')
    if manifest.get('persistence_contract_version') == 1:
        verify_directory(source, 'record_integrity.json')
    policy = reconstruct_policy(manifest['policy'])
    if manifest['provenance']['file_hashes'] != source_fingerprints():
        raise ValueError('exact replay requires the recorded source/configuration versions')
    runtime = runtime_identity()
    original_runtime = manifest['provenance']['runtime']
    if any(runtime[k] != original_runtime[k] for k in ('python', 'implementation', 'dependencies')):
        raise ValueError('exact replay requires the recorded interpreter/dependency versions')
    observation = dict(manifest["observation_model"])
    observation["emissions"] = tuple(tuple(row) for row in observation["emissions"])
    estimator_config = manifest["estimator"]
    estimator_observation = dict(estimator_config["observation_config"])
    estimator_observation["emissions"] = tuple(tuple(row) for row in estimator_observation["emissions"])
    estimator = StudentStateEstimator(prior=estimator_config["prior"],
        wait_matrix=estimator_config["wait_matrix"], treatment_matrix=estimator_config["programme_matrix"],
        observation_config=ObservationConfig(**estimator_observation))
    world = json.loads((source / 'evaluator_only/initial_world.json').read_text())
    environment = CMDPEnvironment([StudentSimulation(**s) for s in world['students']],
        [Mentor(**{**m, 'availability_by_step': [MentorAvailability(**a)
            for a in m['availability_by_step']]}) for m in world['mentors']], config,
        wait_matrix=manifest['environment_wait_matrix'],
        treatment_matrix=manifest['environment_programme_matrix'])
    result = ReplayController(environment, policy,
        source=source, replay_provenance={
            "original_model_invocations": sum(a["model_invocations"] for a in attempts),
            "original_cache_hits": sum(a["cache_hit"] for a in attempts),
            "replay_model_invocations": 0,
            "attempt_provenance": "historical original execution, not replay inference"},
        mode=manifest["information_mode"], extractor=extractor,
        estimator=estimator,
        **manifest['controller_model'],
        observation_config=ObservationConfig(**observation),
        note_quality=NoteQuality(**manifest["note_quality"]),
        note_quality_by_student={sid: NoteQuality(**quality) for sid, quality
                                 in manifest["note_quality_by_student"].items()},
        max_notes_per_month=manifest["max_notes_per_month"],
        max_monitoring_notes_per_month=manifest["max_monitoring_notes_per_month"],
        extraction_contract=manifest["extraction_contract"])
    result.observation_model = RecordedObservations(source, ObservationConfig(**observation))
    result.experiment_identity = manifest['experiment_identity']
    result.recorded_extractor_identity = manifest['extractor']
    # Gold routing is determined by identity in the controller; keep a separate
    # recorded adapter so injected routes remain explicitly injected.
    gold_attempts = [a for a in attempts if a["route"] == "gold"]
    gold_keys = {(a["note_id"], a["as_of_month"]) for a in gold_attempts}
    gold_extractor = RecordedOutcomeExtractor(gold_attempts,
        [b for b in batches if (b["note_id"], b["as_of_month"]) in gold_keys])
    result.gold_extractor = gold_extractor
    result.run_episode()
    if extractor.used | gold_extractor.used != set(extractor.outcomes):
        raise ValueError("recorded extraction outcomes were not all replayed")
    expected = read_jsonl(source / "allocation_decisions.jsonl")

    def deterministic_decisions(rows):
        rows = json.loads(json.dumps(rows))
        for row in rows:
            row["allocation"].pop("runtime_seconds", None)
        return rows

    if deterministic_decisions(result.decisions) != deterministic_decisions(expected):
        raise ValueError("replay allocation/resource mismatch")
    expected_truth = read_jsonl(source / "evaluator_only/truth_trajectories.jsonl")
    if json.loads(json.dumps(result.evaluator_truth)) != expected_truth:
        raise ValueError("replay transition mismatch")
    _write_episode(result, output)
    restored = json.loads((output/'experiment_config.json').read_text())
    for name in ('scenario', 'information_mode', 'observation_model', 'note_quality',
                 'max_notes_per_month', 'extraction_contract', 'max_monitoring_notes_per_month',
                 'note_quality_by_student', 'estimator', 'policy', 'controller_model',
                 'environment_wait_matrix', 'environment_programme_matrix', 'extractor',
                 'allocation_policy_settings', 'fairness_stratum_rule', 'support_need_rule',
                 'extraction_diagnostics'):
        if restored[name] != manifest[name]:
            raise ValueError(f'replay configuration mismatch: {name}')
    checked = ("mentor_notes", "note_selection", "extracted_observations", "extraction_attempts",
               "extraction_failures", "estimate_updates", "risk_estimates", "decision_snapshots",
               "decision_extraction_diagnostics", "observable_events", "administrative_enrollment",
               "fairness_windows", "final_beliefs", "initial_observations")
    for name in checked:
        if read_jsonl(output / f"{name}.jsonl") != read_jsonl(source / f"{name}.jsonl"):
            raise ValueError(f"replay {name} mismatch")
    if deterministic_decisions(read_jsonl(output / 'environment_records.jsonl')) != deterministic_decisions(
            read_jsonl(source / 'environment_records.jsonl')):
        raise ValueError('replay environment resource ledger mismatch')
    deterministic = {name: read_jsonl(output / f'{name}.jsonl') for name in checked}
    deterministic.update(decisions=deterministic_decisions(result.decisions), truth=expected_truth,
        environment_records=deterministic_decisions(read_jsonl(output / 'environment_records.jsonl')))
    summary = {"source": str(source), "decisions_reproduced": len(result.decisions),
               "deterministic_digest": sha256(json.dumps(deterministic, sort_keys=True).encode()).hexdigest(),
               "terminal_enrolled": result.environment.terminal_reward(), "real_llm_calls": 0,
               "snapshots_allocations_resources_and_truth_match": True,
               "evidence_processing_history_match": True, "checked_records": checked,
               "extraction_attempts": len(attempts),
               "accepted_extractions": sum(a["status"] == "accepted" for a in attempts),
               "quarantined_extractions": sum(a["status"] == "quarantined" for a in attempts),
               **result.replay_provenance}
    (output / "replay_result.json").write_text(json.dumps(summary, indent=2))
    return summary


def replay_feedback_episode(source, output):
    """Late comparison failures retain diagnostics but never publish a replay."""
    with staged_artifacts(output, identity={'operation': 'offline_replay', 'source': str(source)}) as staging:
        summary = _replay_feedback_episode(Path(source), staging)
        seal_directory(staging, 'record_integrity.json')
        verify_directory(staging, 'record_integrity.json')
    return summary
