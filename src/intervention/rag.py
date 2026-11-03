"""Process recorded sessions with earlier text retrieval and structured memory."""

import argparse
import json
from pathlib import Path
from typing import Callable

from .findings import FINDINGS_SCHEMA, SYSTEM_PROMPT, validate_findings
from .ollama_client import OllamaClient
from .reports import write_report
from .session_index import SessionIndex
from .transcripts import load_sessions, spoken_turns
from ..utils.constants import HISTORIES, RAG_RESULTS


class InterventionRAG:
    def __init__(self, index: SessionIndex, client: OllamaClient,
                 max_prompt_chars: int = 60000) -> None:
        self.index = index
        self.client = client
        self.max_prompt_chars = max_prompt_chars

    def analyse(self, history_id: str, through_session: int | None = None,
                question: str = "What changed, which actions remain pending, and what is the intervention outcome?",
                *, on_session: Callable[[dict], None] | None = None) -> dict:
        history = self.index.history(history_id, through_session)
        timeline = []
        for current in history:
            passages = self.index.retrieve(history_id, question + " " + current.text,
                                           before_session=current.number)
            context = {
                "question": question,
                "current_session_number": current.number,
                "earlier_validated_memory": timeline,
                "retrieved_prior_passages": [
                    {"session_number": passage.session_number, "text": passage.text}
                    for passage in passages
                ],
                "current_conversation": spoken_turns(current.turns),
            }
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ]
            if len(json.dumps(messages)) + len(json.dumps(FINDINGS_SCHEMA)) > self.max_prompt_chars:
                raise ValueError("History exceeds prompt budget; increase the budget and model context")
            try:
                findings = self.client.generate(messages, FINDINGS_SCHEMA)
                validate_findings(findings)
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
    parser.add_argument("--question", default="What changed, which actions remain pending, and what is the intervention outcome?")
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
