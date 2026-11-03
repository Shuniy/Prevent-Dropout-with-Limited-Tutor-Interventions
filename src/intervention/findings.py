"""The JSON structure requested from the model and checked before saving."""

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


def object_schema(properties: dict) -> dict:
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def choice(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


FINDINGS_SCHEMA = object_schema({
    "session_summary": {"type": "string", "minLength": 1},
    "primary_concern": {"type": "string", "minLength": 1},
    "tracked_details": {"type": "array", "items": object_schema({
        "detail": {"type": "string", "minLength": 1},
        "status": choice("reported", "planned", "pending", "completed", "unresolved", "unknown", "conflicting"),
    })},
    "intervention": object_schema({
        "type": {"type": "string"},
        "status": choice("not_discussed", "information_only", "proposed", "inquiry_planned",
                         "assessment_requested", "referral_made", "pending", "active", "completed", "declined", "unknown"),
        "service_delivered": {"type": ["boolean", "null"]},
    }),
    "outcome": object_schema({
        "primary_barrier_resolved": choice("yes", "no", "partial", "unknown", "conflicting"),
        "attendance_improved": choice("yes", "no", "partial", "unknown", "conflicting"),
        "intervention_helpful": choice("yes", "no", "mixed", "unknown", "conflicting"),
    }),
    "session_helpful": choice("yes", "no", "mixed", "unknown"),
    "next_steps": {"type": "array", "items": {"type": "string"}},
    "uncertainties": {"type": "array", "items": {"type": "string"}},
    "conclusion": {"type": "string", "minLength": 1},
})

def validate_findings(findings: dict) -> None:
    """Check structure; factual interpretation remains the model's responsibility."""
    try:
        Draft202012Validator(FINDINGS_SCHEMA).validate(findings)
    except ValidationError as exc:
        raise ValueError(f"Invalid findings: {exc.message}") from exc
