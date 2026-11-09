"""Save bounded offline Phase 2 verification artifacts using the regression fixtures.

This harness deliberately imports test fixtures. It is not a population experiment
or a live-model benchmark. The output directory must be new.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
from unittest.mock import patch

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.research_experiments import load_config, live_snapshot_comparisons, make_controller
from src.school.feedback_experiments import save_episode
from src.school.feedback_replay import read_jsonl, replay_feedback_episode
from src.school.feedback_validation import validate_feedback_episode
from tests.test_phase2_correctness import controlled_episode, MonitoringFixture, CountingExtractor


ROOT = Path(__file__).resolve().parents[1]
FOCUSED_MODULES = ("tests.test_phase2_correctness", "tests.test_phase1_correctness",
    "tests.test_feedback_closed_loop", "tests.test_feedback_extraction",
    "tests.test_feedback_estimation", "tests.test_research_information", "tests.test_extraction_evaluation")


def source_identity():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    paths = git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    # Fingerprint runnable sources/configuration, including uncommitted files.
    # Documentation may subsequently quote this record without a circular hash.
    files = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(set(paths))
             if (name.startswith(("src/", "tests/", "scripts/", "configs/", ".github/workflows/"))
                 or name in ("pyproject.toml", "requirements.txt")) and (ROOT / name).is_file()}
    return {"branch": git("branch", "--show-current"), "commit": git("rev-parse", "HEAD"),
        "working_tree_status": git("status", "--short"),
        "source_sha256": sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "files_sha256": files,
        "scope": "HEAD plus listed working-tree source/configuration bytes; not a claim these edits are committed"}


def verify_commands(output):
    commands = {"focused": [sys.executable, "-m", "unittest", *FOCUSED_MODULES, "-v"],
                "offline": [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                "diff_check": ["git", "diff", "--check"]}
    results = {}
    for name, command in commands.items():
        print(f"Verifying {name}: {shlex.join(command)}", flush=True)
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        (output / f"{name}.log").write_text(result.stdout, encoding="utf-8")
        counts = re.search(r"Ran (\d+) tests? in ([\d.]+)s", result.stdout)
        results[name] = {"command": shlex.join(command), "exit_code": result.returncode,
            "tests": int(counts[1]) if counts else None,
            "seconds": float(counts[2]) if counts else None, "log": f"{name}.log"}
    return results


class ReplayFixture(CountingExtractor):
    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    def extract(self, note, cutoff):
        if self.kind == "failure" or (self.kind == "mixed" and note.student_id == "SYN00002"):
            raise RuntimeError("model unavailable")
        batch = super().extract(note, cutoff)
        return replace(batch, facts=()) if self.kind == "empty" else batch


def verify(output):
    if sys.version_info[:2] not in ((3, 12), (3, 13)):
        raise RuntimeError("verification requires supported Python 3.12 or 3.13")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    identity = source_identity()
    checks = verify_commands(output)
    traces = {}
    for name, omit in (("perfect", False), ("omission", True)):
        c = controlled_episode(omit=omit)
        validate_feedback_episode(c)
        save_episode(c, output / name)
        sid = "SYN00003"
        state = c.snapshots[1]
        estimate = next(e for e in state.estimated_student_states if e.student_id == sid)
        risk = next(r for r in state.risk_estimates if r.student_id == sid)
        note = next(n for n in c.notes if n.student_id == sid and n.event_month == 1)
        attempt = next(a for a in c.extraction_attempts if a["note_id"] == note.note_id)
        traces[name] = {"note": asdict(note), "attempt": attempt,
            "estimate": asdict(estimate), "risk": asdict(risk),
            "benefits": c.decisions[1]["benefits"],
            "month_1_admitted": c.decisions[0]["admitted_ids"],
            "month_1_conditions": c.environment.records[0].conditions,
            "month_2_admitted": c.decisions[1]["admitted_ids"],
            "budget_trajectory": [r.remaining_budget for r in c.environment.records],
            "diagnostics": c.extraction_diagnostics(), "per_cutoff": c.decision_diagnostics}
    assert traces["perfect"]["month_1_conditions"] == traces["omission"]["month_1_conditions"]
    assert traces["perfect"]["month_2_admitted"] != traces["omission"]["month_2_admitted"]
    config = load_config()
    config["scenario"].update(num_students=3, num_mentors=1, horizon=3,
        monthly_admissions=1, monthly_appointments=5, budget=10, fairness_min_access=0)
    config["evaluation"].update(live_seeds=[42], monitoring_notes_per_month=3)
    config["notes"] = {}
    # Deliberately available, informative B and corrupted D reports at cutoff 2.
    # This avoids an unexercised tiny fixture caused by random omission/delay.
    config["primary_notes_true"] = {"misleading_probability": 1.0}
    config["primary_notes_false"] = {"misleading_probability": 1.0}

    def fixture_controller(*args, **kwargs):
        c = make_controller(*args, **kwargs)
        c.observation_model = MonitoringFixture(True)
        return c

    contrasts = {}
    with patch("src.evaluation.research_experiments.make_controller", side_effect=fixture_controller):
        for name, extractor in (("perfect", CountingExtractor()), ("omission", CountingExtractor(omit=True)),
                                ("unavailable", CountingExtractor(fail=True))):
            destination = output / ("matched_" + name)
            destination.mkdir()
            rows = live_snapshot_comparisons(destination, config, extractor)
            contrasts[name] = {"injected_calls": len(extractor.received),
                "statuses": sorted({r["status"] for r in rows}),
                "max_belief_l1": max((r["belief_l1"] or 0) for r in rows),
                "assignment_disagreement_rows": sum(bool(r["mentor_changed"]) for r in rows)}
    replays = {}
    for name in ("success", "empty", "mixed", "failure"):
        c = controlled_episode(run=False)
        c.extractor = ReplayFixture(name)
        c.run_episode()
        source, replay = output / f"replay_{name}_source", output / f"replay_{name}_result"
        save_episode(c, source)
        summary = replay_feedback_episode(source, replay)
        replays[name] = {"summary": summary,
            "original_outcomes": read_jsonl(source / "extraction_attempts.jsonl"),
            "replayed_outcomes": read_jsonl(replay / "extraction_attempts.jsonl")}
    report = {"purpose": "synthetic development wiring and sensitivity; no improvement claim",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": identity, "python": platform.python_version(), "executable": sys.executable,
        "dependencies": dict(sorted((d.metadata["Name"], d.version) for d in distributions())),
        "commands": checks, "verification_command": shlex.join([
            sys.executable, "scripts/verify_phase2.py", "--output", str(output)]),
        "output": str(output), "replays": replays,
        "limitations": ["Synthetic fixtures only; no empirical effectiveness or live LLM validation.",
            "Replay requires complete current-format outcome records; legacy batch-only artifacts are insufficient.",
            "Replay supports ordinary resource/fairness planners with reproducible settings, not arbitrary robust/custom policies.",
            "Solver runtime is excluded from equality; time-limited nondeterministic solves may not replay exactly.",
            "Generated experiment folders and logs are ignored by Git; reproduce with the recorded command."],
        "live_model_calls": 0, "traces": traces, "matched_comparisons": contrasts,
        "matched_configuration": config}
    if source_identity()["source_sha256"] != identity["source_sha256"]:
        raise RuntimeError("source changed during verification")
    (output / "verification.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(output), "matched_comparisons": contrasts,
        "commands": checks, "source_sha256": identity["source_sha256"],
        "month_2": {name: trace["month_2_admitted"] for name, trace in traces.items()},
        "replays": {name: row["summary"] for name, row in replays.items()}}, indent=2))
    if any(r["exit_code"] for r in checks.values()):
        raise RuntimeError("verification failed; inspect recorded command results and logs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    verify(parser.parse_args().output)
