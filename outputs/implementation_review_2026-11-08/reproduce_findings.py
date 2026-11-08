"""Offline review probes. Writes evidence only; does not change application code."""

from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.evaluation.research_experiments import (
    freeze, live_snapshot_comparisons, load_config, make_policy,
)
from src.intervention.feedback_notes import NoteQuality, render_note
from src.intervention.observation_extractor import (
    FixtureObservationExtractor, gold_payload, validate_extraction,
)
from src.observations.observable_events import EnrollmentRecord, ObservableEvent
from src.school.baseline_policy import BASELINES, BaselinePolicy
from src.school.cmdp_experiments import run_experiments, run_policy
from src.school.cmdp_scenarios import build_school
from src.school.constrained_planner import ConstrainedAllocationPlanner
from src.school.decision_state import DecisionState
from src.school.fairness_planner import FairnessPlanner
from src.school.feedback_experiments import save_episode
from src.school.feedback_replay import replay_feedback_episode
from src.school.observation_model import ObservationConfig
from src.school.robust_fair_planner import FairRobustPlanner
from src.school.scenario_config import ScenarioConfig
from src.school.simulated_withdrawal_risk import SimulatedWithdrawalRiskEstimator
from src.school.state_estimator import StudentStateEstimator
from src.school.student_observation import StudentObservation
from src.school.uncertainty_scenarios import (
    UncertaintyScenarioConfig, build_belief_scenarios,
)


class ProbeExtractor:
    def __init__(self, behavior="gold"):
        self.behavior = behavior
        self.calls = 0
        self.note_types = []

    def extract(self, note, cutoff):
        self.calls += 1
        self.note_types.append(note.note_type)
        if self.behavior == "fail":
            raise ValueError("intentional extraction failure in offline review probe")
        payload = gold_payload(note)
        if self.behavior == "empty":
            payload["observations"] = []
        return validate_extraction(payload, note, cutoff)


def compact(controller):
    return [[asdict(a) for a in record.allocation.assignments]
            for record in controller.environment.records]


def llm_influence():
    rows = []
    for name, policy_type in (("resource", ConstrainedAllocationPlanner),
                              ("fairness", FairnessPlanner),
                              ("robust", FairRobustPlanner)):
        for seed in (0, 1, 42):
            config = ScenarioConfig(num_students=12, num_mentors=2, horizon=4,
                                    monthly_admissions=1, monthly_appointments=5,
                                    budget=30, seed=seed)
            runs = []
            for behavior in ("gold", "empty", "fail"):
                extractor = ProbeExtractor(behavior)
                controller = build_school(config).run_cmdp_feedback(
                    policy_type(), config=config, mode="llm_notes", extractor=extractor,
                    observation_config=ObservationConfig(missing_probability=0,
                                                         delay_probability=0))
                runs.append(controller)
            reference = runs[0]
            rows.append({
                "policy": name, "seed": seed,
                "extractor_calls": [c.extractor.calls for c in runs],
                "all_injected_calls_are_programme_notes": all(
                    set(c.extractor.note_types) <= {"programme"} for c in runs),
                "assignments_equal_despite_empty_and_failed_extraction": all(
                    compact(c) == compact(reference) for c in runs[1:]),
                "all_truth_equal": all(c.evaluator_truth == reference.evaluator_truth
                                       for c in runs[1:]),
                "cutoff_beliefs_differ": [
                    any(a.condition_probabilities != b.condition_probabilities
                        for left, right in zip(reference.snapshots, c.snapshots)
                        for a, b in zip(left.students, right.students)) for c in runs[1:]],
                "extraction_failures": [len(c.failures) for c in runs],
            })
    return rows


def freshness():
    extractor = FixtureObservationExtractor()
    old_note = render_note(ObservableEvent("old", "A", 0, 1, "low_participation"), seed=1)
    initial_registry = (EnrollmentRecord("A", 0, 1, True),)
    old_batch = extractor.extract(old_note, 1)
    baseline_estimator = StudentStateEstimator()
    initial = baseline_estimator.initialize("A", (old_batch,), registry=initial_registry)
    new_registry = (EnrollmentRecord("A", 1, 2, True),)
    predicted = baseline_estimator.update(initial, as_of_month=2, registry=new_registry)
    rows = []
    for case in ("conflict", "insufficient_evidence", "completion_only", "no_new_evidence"):
        estimator = StudentStateEstimator()
        event = ObservableEvent("new", "A", 1, 2, "low_participation",
                                "M" if case == "completion_only" else None,
                                "P" if case == "completion_only" else None,
                                case == "completion_only")
        note = render_note(event, seed=1,
                           quality=NoteQuality(conflict_probability=1 if case == "conflict" else 0))
        if case == "insufficient_evidence":
            note = replace(note, text="There is insufficient evidence about participation.")
        elif case == "completion_only":
            note = replace(note, text="The student completed the scheduled mentoring appointments.")
        batches = () if case == "no_new_evidence" else (extractor.extract(note, 2),)
        estimate = estimator.update(initial, batches, as_of_month=2, registry=new_registry)
        student = StudentObservation("A", True, estimate.estimated_condition, "tutoring", .5,
                                     (), 1, False, "F", estimate.condition_probabilities,
                                     estimate.estimate_id)
        risk = SimulatedWithdrawalRiskEstimator().predict(estimate, 3)
        state = DecisionState(2, 3, 10, (student,), (), "estimated_state", "10",
                              estimated_student_states=(estimate,), risk_estimates=(risk,))
        scenario = build_belief_scenarios(state, UncertaintyScenarioConfig(),
                                        estimator.wait, estimator.programme)[0]
        uncertainty = dict(dict(scenario.parameters)["student_uncertainty"])["A"]
        rows.append({"case": case,
                     "posterior_equals_no_new_condition_evidence":
                         estimate.condition_probabilities == predicted.condition_probabilities,
                     "last_observation_month": estimate.last_observation_month,
                     "missing_current_signal": dict(estimate.observation_uncertainty)["missing_current_signal"],
                     "robust_uncertainty": dict(uncertainty),
                     "rejections": estimator.updates[-1].rejected_observations})
    return rows


def baseline_feedback():
    config = ScenarioConfig(num_students=6, num_mentors=1, horizon=2)
    rows = []
    for name in BASELINES:
        try:
            build_school(config).run_cmdp_feedback(BaselinePolicy(name), config=config)
        except Exception as exc:
            rows.append({"policy": name, "error": type(exc).__name__, "message": str(exc)})
        else:
            rows.append({"policy": name, "error": None})
    return rows


def snapshots_without_llm():
    config = load_config()
    config = {**config, "scenario": {**config["scenario"], "num_students": 12,
              "horizon": 3, "monthly_admissions": 1, "monthly_appointments": 5},
              "evaluation": {**config["evaluation"], "live_seeds": [1000]}}
    extractor = ProbeExtractor("fail")
    with tempfile.TemporaryDirectory() as directory:
        live_snapshot_comparisons(Path(directory), config, extractor)
        import csv
        with (Path(directory) / "extraction_snapshot_comparison.csv").open() as stream:
            rows = list(csv.DictReader(stream))
    return {"extractor_calls": extractor.calls, "exported_comparison_rows": len(rows),
            "all_belief_differences_zero": all(float(row["belief_l1"]) == 0 for row in rows),
            "all_mentor_assignments_equal": all(row["mentor_changed"] == "False" for row in rows)}


def replay_quality():
    config = ScenarioConfig(num_students=12, num_mentors=1, horizon=3,
                            monthly_admissions=1, monthly_appointments=5, budget=10)
    school = build_school(config)
    qualities = {s.student_id: NoteQuality(omission_probability=1) for s in school.students}
    controller = school.run_cmdp_feedback(ConstrainedAllocationPlanner(), config=config,
        mode="b_matched", note_quality_by_student=qualities,
        observation_config=ObservationConfig(missing_probability=0, delay_probability=0))
    with tempfile.TemporaryDirectory() as directory:
        source, destination = Path(directory) / "source", Path(directory) / "replay"
        save_episode(controller, source)
        manifest = json.loads((source / "experiment_config.json").read_text())
        try:
            replay_feedback_episode(source, destination)
        except Exception as exc:
            return {"saved_per_student_quality_count": len(manifest["note_quality_by_student"]),
                    "error": type(exc).__name__, "message": str(exc)}
    return {"error": None}


def historic_hashes():
    saved = json.loads((ROOT / "results/research_evaluation_v1/configuration_manifest.json").read_text())
    changed, missing, same = [], [], []
    for path, expected in saved["file_hashes"].items():
        file = ROOT / path
        if not file.exists():
            missing.append(path)
        elif sha256(file.read_bytes()).hexdigest() != expected:
            changed.append(path)
        else:
            same.append(path)
    return {"changed_count": len(changed), "missing_count": len(missing),
            "unchanged_count": len(same), "changed": changed, "missing": missing}


def free_programmes():
    config = ScenarioConfig(num_students=12, num_mentors=1, horizon=3, budget=0,
                            cost_per_appointment=0, monthly_admissions=12,
                            monthly_appointments=60, seed=0)
    wait_metrics, wait_trajectory = run_policy(config, "wait")
    random_metrics, random_trajectory = run_policy(config, "random")
    with tempfile.TemporaryDirectory() as directory:
        try:
            run_experiments(config, output=Path(directory) / "run", stage="development",
                            development_seed_count=1, evaluation_seed_count=1,
                            policies=("wait", "random"))
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        else:
            error = None
    return {"zero_budget": config.budget, "programme_price": 0,
            "random_programmes": random_metrics["programmes"],
            "random_spending": random_metrics["spending"],
            "legitimate_truth_difference": [r["conditions"] for r in wait_trajectory] !=
                [r["conditions"] for r in random_trajectory], "runner_error": error}


def ignored_fairness_flag():
    config = load_config()
    disabled = {**config, "scenario": {**config["scenario"], "fairness_enabled": False}}
    return {"configured_enabled": False,
            "actual_planner_enabled": {name: make_policy(disabled, name).enabled
                                       for name in ("FairPoint", "FairRobust")}}


def main():
    output = {"revision": subprocess.check_output(
                  ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "python": sys.version, "llm_influence": llm_influence(),
              "freshness": freshness(), "baseline_feedback": baseline_feedback(),
              "live_snapshot_comparison": snapshots_without_llm(),
              "replay_group_quality": replay_quality(),
              "historic_source_hashes": historic_hashes(),
              "free_programmes": free_programmes(),
              "ignored_fairness_flag": ignored_fairness_flag()}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        before_hashes = {"docs/research_evaluation_protocol.md": "before"}
        after_hashes = {"docs/research_evaluation_protocol.md": "after"}
        with patch("src.evaluation.research_experiments.fingerprint", return_value=before_hashes):
            before = freeze(path)
        (path / "episodes/evaluation_probe").mkdir(parents=True)
        with patch("src.evaluation.research_experiments.fingerprint", return_value=after_hashes):
            after = freeze(path, "Offline review probe: amended after held-out execution")
        manifests = list(path.glob("configuration_manifest*.json"))
        output["manifest_amendment"] = {
            "input_digest_changed": before["input_digest"] != after["input_digest"],
            "heldout_already_executed": after["heldout_already_executed"],
            "manifest_files": [p.name for p in manifests],
            "old_digest_still_in_any_manifest": any(
                before["input_digest"] in p.read_text() for p in manifests)}
    destination = Path(__file__).with_name("evidence.json")
    destination.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: value for key, value in output.items()
                      if key not in ("llm_influence", "historic_source_hashes")}, indent=2))
    print("LLM influence pairs:", len(output["llm_influence"]))
    print("All decisions/truth unchanged:", all(
        row["assignments_equal_despite_empty_and_failed_extraction"] and row["all_truth_equal"]
        for row in output["llm_influence"]))
    print("Historic hash counts:", {key: value for key, value in output["historic_source_hashes"].items()
                                     if key.endswith("count")})


if __name__ == "__main__":
    main()
