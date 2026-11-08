"""Save bounded offline Phase 2 verification artifacts using the regression fixtures.

This harness deliberately imports test fixtures. It is not a population experiment
or a live-model benchmark. The output directory must be new.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from unittest.mock import patch

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.research_experiments import load_config, live_snapshot_comparisons, make_controller
from src.school.feedback_experiments import save_episode
from src.school.feedback_validation import validate_feedback_episode
from tests.test_phase2_correctness import controlled_episode, MonitoringFixture, CountingExtractor


def verify(output):
    output.mkdir(parents=True, exist_ok=False)
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
    report = {"purpose": "synthetic development wiring and sensitivity; no improvement claim",
        "live_model_calls": 0, "traces": traces, "matched_comparisons": contrasts,
        "matched_configuration": config}
    (output / "verification.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(output), "matched_comparisons": contrasts,
        "month_2": {name: trace["month_2_admitted"] for name, trace in traces.items()}}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    verify(parser.parse_args().output)
