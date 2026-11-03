"""Small shared fixtures for feature tests; no live model required."""

import json
from pathlib import Path


def findings():
    return {
        "session_summary": "The task remains difficult.",
        "primary_concern": "learning_gap",
        "tracked_details": [{"detail": "Practice task", "status": "pending"}],
        "intervention": {"type": "tutoring", "status": "active", "service_delivered": None},
        "outcome": {"primary_barrier_resolved": "unknown", "attendance_improved": "unknown",
                    "intervention_helpful": "unknown"},
        "session_helpful": "unknown", "next_steps": ["Practice one example"],
        "uncertainties": ["Later progress is unknown"], "conclusion": "Practice is still needed.",
    }


class FakeClient:
    def __init__(self, fail_at=None, failure="invalid"):
        self.contexts = []
        self.fail_at = fail_at
        self.failure = failure

    def generate(self, messages, schema):
        context = json.loads(messages[1]["content"])
        self.contexts.append(context)
        if context["current_session_number"] == self.fail_at:
            if self.failure == "network":
                raise RuntimeError("local model unavailable")
            return {}
        return findings()


def write_history(root: Path, history_id="02_tutoring/student", count=2):
    folder = root / history_id
    folder.mkdir(parents=True, exist_ok=True)
    for number in range(1, count + 1):
        stage = "initial" if number == 1 else "followup"
        (folder / f"session_{number:02d}_{stage}.md").write_text(
            "# History\n**Intervention type:** HEADER_SECRET\n\n"
            f"**Student:** Practice task {number} remains difficult.\n\n"
            "**Mentor:** We can review one example together.\n", encoding="utf-8")
