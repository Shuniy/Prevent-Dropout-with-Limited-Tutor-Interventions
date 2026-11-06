"""Extraction schema; source and semantic checks run before persistence."""

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


def object_schema(properties: dict) -> dict:
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def choice(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


TEXT = {"type": "string", "minLength": 1}
EVIDENCE_SCHEMA = object_schema({
    "history_id": TEXT,
    "session_number": {"type": "integer", "minimum": 1},
    "turn_number": {"type": "integer", "minimum": 1},
    "quote": TEXT,
})
EVIDENCE_LIST = {"type": "array", "items": EVIDENCE_SCHEMA}
ACTION_STATUSES = ("not_started", "attempted", "partially_completed", "completed",
                   "not_completed", "unknown")
ACTION_SCHEMA = object_schema({
    "action_id": TEXT,
    "original_action": TEXT,
    "responsible_person": {"type": ["string", "null"], "minLength": 1},
    "agreed_on": {"type": ["string", "null"], "minLength": 1},
    "due_date": {"type": ["string", "null"], "minLength": 1},
    "original_evidence": EVIDENCE_SCHEMA,
    "status": choice(*ACTION_STATUSES),
    "status_evidence": EVIDENCE_LIST,
})
OUTCOME_CHOICES = {
    "primary_barrier_resolved": choice("yes", "no", "partial", "unknown", "conflicting"),
    "attendance_improved": choice("yes", "no", "partial", "unknown", "conflicting"),
    "intervention_helpful": choice("yes", "no", "mixed", "unknown", "conflicting"),
}


def component_schema(*statuses: str) -> dict:
    return object_schema({"component_id": TEXT, "description": TEXT,
                          "status": choice(*statuses), "evidence": EVIDENCE_LIST})


FINDINGS_SCHEMA = object_schema({
    "session_summary": TEXT,
    "primary_concern": TEXT,
    "tracked_details": {"type": "array", "items": object_schema({
        "detail": TEXT,
        "status": choice("reported", "planned", "pending", "completed", "unresolved", "unknown", "conflicting"),
        "evidence": EVIDENCE_LIST,
    })},
    "actions": {"type": "array", "items": ACTION_SCHEMA},
    "intervention": object_schema({
        "intended_intervention": object_schema({
            "type": {"type": "string"},
            "status": choice("not_discussed", "information_only", "proposed", "inquiry_planned",
                             "assessment_requested", "referral_made", "pending", "active", "completed", "declined", "unknown"),
            "component_ids": {"type": "array", "items": TEXT, "uniqueItems": True},
            "evidence": EVIDENCE_LIST,
        }),
        "direct_activities": {"type": "array", "items": component_schema(
            "proposed", "delivered", "not_delivered", "unknown", "conflicting")},
        "external_support": {"type": "array", "items": component_schema(
            "requested", "pending", "received", "not_received", "declined", "unknown", "conflicting")},
    }),
    "outcome": object_schema(OUTCOME_CHOICES),
    "outcome_evidence": object_schema({key: EVIDENCE_LIST for key in OUTCOME_CHOICES}),
    "session_helpful": choice("yes", "no", "mixed", "unknown"),
    "session_helpful_evidence": EVIDENCE_LIST,
    "next_steps": {"type": "array", "items": {"type": "string"}},
    "uncertainties": {"type": "array", "items": {"type": "string"}},
    "conclusion": TEXT,
})


def validate_findings(findings: dict) -> None:
    """Validate JSON shape only; evaluators must also call validate_semantics."""
    try:
        Draft202012Validator(FINDINGS_SCHEMA).validate(findings)
    except ValidationError as exc:
        raise ValueError(f"Invalid findings: {exc.message}") from exc
