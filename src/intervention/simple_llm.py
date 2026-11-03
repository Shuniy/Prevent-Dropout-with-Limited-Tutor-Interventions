"""Extract a complete intervention timeline in one call, without retrieval."""

import argparse
import json
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .findings import FINDINGS_SCHEMA, object_schema
from .ollama_client import OllamaClient
from .prompts import DEFAULT_QUESTION, SIMPLE_SYSTEM_PROMPT
from .reports import write_report
from .session import Session
from .transcripts import group_sessions, history_sessions, load_sessions, spoken_turns
from ..utils.constants import HISTORIES, PROJECT_ROOT


class SimpleLLM:
    def __init__(self, sessions: list[Session], client: OllamaClient,
                 max_prompt_chars: int = 60000) -> None:
        self.histories = group_sessions(sessions)
        self.client = client
        self.max_prompt_chars = max_prompt_chars

    def analyse(self, history_id: str, through_session: int | None = None,
                question: str = DEFAULT_QUESTION,
                *, on_session: Callable[[dict], None] | None = None) -> dict:
        history = history_sessions(self.histories, history_id, through_session)
        numbers = [session.number for session in history]
        step_schema = object_schema({
            "session_number": {"type": "integer", "enum": numbers},
            "findings": FINDINGS_SCHEMA,
        })
        schema = object_schema({"timeline": {
            "type": "array", "items": step_schema,
            "minItems": len(history), "maxItems": len(history),
        }})
        context = {
            "task": "Evaluate this student's school-support intervention across the supplied sessions.",
            "question": question,
            "record_scope": {"first_supplied_session": numbers[0],
                             "last_supplied_session": numbers[-1],
                             "session_count": len(history)},
            "sessions": [
                {"session_number": session.number,
                 "conversation_position": position,
                 "chronology_label": f"Conversation {position} of {len(history)}"
                                     + (" (first supplied conversation)" if position == 1 else ""),
                 "prior_session_numbers": numbers[:position - 1],
                 "metadata": session.metadata,
                 "conversation": spoken_turns(session.turns)}
                for position, session in enumerate(history, start=1)
            ],
        }
        messages = [
            {"role": "system", "content": SIMPLE_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]
        if len(json.dumps(messages)) + len(json.dumps(schema)) > self.max_prompt_chars:
            raise ValueError("History exceeds prompt budget; increase the budget and model context")
        response = self.client.generate(messages, schema)
        try:
            Draft202012Validator(schema).validate(response)
        except ValidationError as exc:
            raise ValueError(f"Invalid timeline: {exc.message}") from exc
        timeline = response["timeline"]
        if [step["session_number"] for step in timeline] != numbers:
            raise ValueError("Invalid timeline: sessions must appear exactly once in source order")
        # Validate the entire response before retaining or persisting any findings.
        if on_session is not None:
            for step in timeline:
                on_session(step)
        return {"history_id": history_id, "as_of_session": numbers[-1],
                "timeline": timeline, "conclusion": timeline[-1]["findings"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history_id", help="Full relative history folder")
    parser.add_argument("--root", type=Path, default=HISTORIES)
    parser.add_argument("--through-session", type=int)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "results/intervention_simple_llm/conclusion.json")
    args = parser.parse_args()
    try:
        report = SimpleLLM(load_sessions(args.root), OllamaClient(args.model)).analyse(
            args.history_id, args.through_session, args.question)
        write_report(args.output, report)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
