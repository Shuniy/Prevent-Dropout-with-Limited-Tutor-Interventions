"""Process recorded sessions with earlier text retrieval and structured memory."""

import argparse
import json
from pathlib import Path
from typing import Callable

from .findings import FINDINGS_SCHEMA, validate_findings
from .ollama_client import OllamaClient
from .prompts import DEFAULT_QUESTION, RAG_SYSTEM_PROMPT
from .reports import write_report
from .session_index import SessionIndex
from .semantic_validation import source_backed_actions, validate_semantics
from .transcripts import load_sessions, spoken_turns
from ..utils.constants import HISTORIES, RAG_RESULTS


class InterventionRAG:
    def __init__(self, index: SessionIndex, client: OllamaClient,
                 max_prompt_chars: int = 60000) -> None:
        self.index = index
        self.client = client
        self.max_prompt_chars = max_prompt_chars

    def analyse(self, history_id: str, through_session: int | None = None,
                question: str = DEFAULT_QUESTION,
                *, on_session: Callable[[dict], None] | None = None) -> dict:
        history = self.index.history(history_id, through_session)
        timeline = []
        for position, current in enumerate(history):
            passages = self.index.retrieve(history_id, question + " " + current.text,
                                           before_session=current.number)
            context = {
                "history_id": history_id,
                "question": question,
                "current_session_number": current.number,
                "current_session_metadata": current.metadata,
                "earlier_validated_memory": timeline,
                "source_backed_actions": source_backed_actions(timeline, history[:position]),
                "retrieved_prior_passages": [
                    {"session_number": passage.session_number, "text": passage.text,
                     "metadata": next(s.metadata for s in history if s.number == passage.session_number),
                     "conversation": spoken_turns(passage.turns, first_turn_number=passage.first_turn_number)}
                    for passage in passages
                ],
                "current_conversation": spoken_turns(current.turns),
            }
            messages = [
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ]
            if len(json.dumps(messages)) + len(json.dumps(FINDINGS_SCHEMA)) > self.max_prompt_chars:
                raise ValueError("History exceeds prompt budget; increase the budget and model context")
            try:
                findings = self.client.generate(messages, FINDINGS_SCHEMA)
                validate_findings(findings)
                validate_semantics(findings, history[:position + 1], context["source_backed_actions"],
                                   self.client, self.max_prompt_chars,
                                   prior_passages=context["retrieved_prior_passages"])
            except ValueError as exc:
                raise ValueError(f"Session {current.number}: {exc}") from exc
            step = {"session_number": current.number, "findings": findings}
            timeline.append(step)
            if on_session is not None:
                on_session(step)
        return {"history_id": history_id, "as_of_session": history[-1].number,
                "timeline": timeline, "conclusion": timeline[-1]["findings"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history_id", help="Full relative history folder")
    parser.add_argument("--root", type=Path, default=HISTORIES)
    parser.add_argument("--through-session", type=int)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--output", type=Path, default=RAG_RESULTS / "conclusion.json")
    args = parser.parse_args()
    index = SessionIndex()
    try:
        index.build(load_sessions(args.root))
        report = InterventionRAG(index, OllamaClient(args.model)).analyse(
            args.history_id, args.through_session, args.question)
        write_report(args.output, report)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    finally:
        index.close()
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
