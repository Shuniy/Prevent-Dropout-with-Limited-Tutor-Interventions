"""Student-scoped lexical RAG and chronological memory using local Ollama.

Only spoken transcript turns enter the index. CSV labels and transcript headers
are intentionally excluded. SQLite FTS5 supplies BM25 retrieval without an
embedding model or additional model downloads.
"""

from __future__ import annotations

try:
    from ..utils.constants import (
        CONCLUSION_SCHEMA,
        EVIDENCE_LIST,
        EVIDENCE_SCHEMA,
        GENERATION_SCHEMA,
        HISTORIES,
        RAG_RESULTS as RESULTS,
        SYSTEM_PROMPT,
        enum,
        object_schema,
        reference_schema,
    )
except ImportError:  # Direct script entry point.
    from utils.constants import (
        CONCLUSION_SCHEMA,
        EVIDENCE_LIST,
        EVIDENCE_SCHEMA,
        GENERATION_SCHEMA,
        HISTORIES,
        RAG_RESULTS as RESULTS,
        SYSTEM_PROMPT,
        enum,
        object_schema,
        reference_schema,
    )


import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


@dataclass(frozen=True)
class Session:
    student_id: str
    number: int
    source: str
    turns: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(self.turns)

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()


@dataclass(frozen=True)
class Passage:
    session_number: int
    source: str
    chunk: int
    text: str


def spoken_turns(turns: tuple[str, ...] | list[str]) -> list[dict[str, str]]:
    """Keep quote boundaries explicit instead of flattening adjacent speakers."""
    return [{"speaker": turn.split(": ", 1)[0], "utterance": turn.split(": ", 1)[1]}
            for turn in turns]


def load_sessions(root: Path = HISTORIES) -> list[Session]:
    """Load only session Markdown; full relative parent paths are student IDs."""
    root = Path(root)
    sessions = []
    for path in sorted(root.rglob("session_*.md")):
        match = re.fullmatch(r"session_(\d+)_(?:initial|followup)\.md", path.name)
        if not match:
            continue
        text = path.read_text(encoding="utf-8")
        # The corpus has one utterance per paragraph. Ignore headings/timestamps.
        turns = tuple(
            f"{speaker}: {words.strip()}"
            for speaker, words in re.findall(
                r"^\*\*(Mentor|Student):\*\*\s*(.*?)(?=\n\s*\n|\Z)",
                text, flags=re.MULTILINE | re.DOTALL,
            )
        )
        if not turns:
            raise ValueError(f"No spoken turns found in {path}")
        sessions.append(Session(
            path.parent.relative_to(root).as_posix(), int(match[1]),
            path.relative_to(root).as_posix(), turns,
        ))
    if not sessions:
        raise ValueError(f"No session transcripts found in {root}")
    identities = [(s.student_id, s.number) for s in sessions]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate session number within a student history")
    return sorted(sessions, key=lambda s: (s.student_id, s.number))


class SessionIndex:
    """Persistent source index; rebuilding replaces stale/deleted source chunks."""

    def __init__(self, path: Path | str = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5("
            "student_id UNINDEXED, session_number UNINDEXED, source UNINDEXED, "
            "chunk UNINDEXED, text)"
        )
        self.sessions: dict[str, list[Session]] = {}

    def close(self) -> None:
        self.connection.close()

    def build(self, sessions: list[Session], turns_per_chunk: int = 12) -> None:
        if turns_per_chunk < 2:
            raise ValueError("turns_per_chunk must be at least 2")
        grouped: dict[str, list[Session]] = {}
        for session in sessions:
            if session.number < 1 or not session.turns:
                raise ValueError("Sessions require a positive number and spoken turns")
            history = grouped.setdefault(session.student_id, [])
            if any(old.number == session.number for old in history):
                raise ValueError("Duplicate session number within a student history")
            history.append(session)
        with self.connection:
            self.connection.execute("DELETE FROM passages")
            for history in grouped.values():
                history.sort(key=lambda s: s.number)
                for session in history:
                    for chunk, start in enumerate(range(0, len(session.turns), turns_per_chunk)):
                        self.connection.execute(
                            "INSERT INTO passages VALUES (?, ?, ?, ?, ?)",
                            (session.student_id, session.number, session.source, chunk,
                             "\n\n".join(session.turns[start:start + turns_per_chunk])),
                        )
        self.sessions = grouped

    def history(self, student_id: str, through_session: int | None = None) -> list[Session]:
        if student_id not in self.sessions:
            raise ValueError(f"Unknown student history: {student_id}")
        history = self.sessions[student_id]
        if through_session is not None:
            if through_session not in {s.number for s in history}:
                raise ValueError(f"Session {through_session} is not recorded for {student_id}")
            history = [s for s in history if s.number <= through_session]
        return list(history)

    def retrieve(self, student_id: str, query: str, before_session: int,
                 per_session: int = 2) -> list[Passage]:
        """Retrieve matches from each earlier session, with a recency fallback.

        Per-session coverage keeps the initial session visible even when recent
        wording differs. Filtering happens inside SQL before BM25 ranking.
        """
        if per_session < 1:
            raise ValueError("per_session must be positive")
        history = self.history(student_id)
        terms = list(dict.fromkeys(re.findall(r"\w+", query.lower())))[:80]
        expression = " OR ".join('"' + term + '"' for term in terms)
        passages = []
        for session in history:
            if session.number >= before_session:
                continue
            rows = []
            if expression:
                rows = self.connection.execute(
                    "SELECT chunk, text FROM passages WHERE passages MATCH ? "
                    "AND student_id = ? AND session_number = ? "
                    "ORDER BY bm25(passages), CAST(chunk AS INTEGER) LIMIT ?",
                    (expression, student_id, session.number, per_session),
                ).fetchall()
            # Fill with the closing turns, where agreed actions usually occur.
            fallback = self.connection.execute(
                "SELECT chunk, text FROM passages WHERE student_id = ? "
                "AND session_number = ? ORDER BY CAST(chunk AS INTEGER) DESC LIMIT ?",
                (student_id, session.number, per_session),
            ).fetchall()
            seen = {row[0] for row in rows}
            for row in fallback:
                if len(rows) < per_session and row[0] not in seen:
                    rows.append(row)
                    seen.add(row[0])
            passages.extend(Passage(session.number, session.source, int(chunk), text)
                            for chunk, text in sorted(rows, key=lambda row: int(row[0])))
        return passages


def map_evidence(value: object, convert: Callable) -> object:
    """Convert evidence leaves without changing findings or earlier memory."""
    if isinstance(value, dict):
        if set(value) in ({"session_number", "quote"}, {"evidence_id"}):
            return convert(value)
        return {key: map_evidence(item, convert) for key, item in value.items()}
    if isinstance(value, list):
        return [map_evidence(item, convert) for item in value]
    if isinstance(value, str):
        # Prompt-local labels are redundant once citation objects contain exact
        # quotes. Leave quoted source text intact by converting evidence first.
        return re.sub(r"\s*\(evidence\s+e[1-9][0-9]*(?:(?:\s*[,–-]\s*|\s+and\s+)e[1-9][0-9]*)*\)",
                      "", value, flags=re.IGNORECASE)
    return value


class OllamaClient:
    def __init__(self, model: str = "qwen3.5:latest", base_url: str | None = None,
                 timeout: int = 300, num_ctx: int = 32768) -> None:
        self.model = model
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout = timeout
        self.num_ctx = num_ctx

    def generate(self, messages: list[dict], schema: dict) -> dict:
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "think": False, "format": schema,
                   "options": {"temperature": 0, "num_ctx": self.num_ctx}}
        request = Request(f"{self.base_url}/api/chat", json.dumps(payload).encode(),
                          {"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"Ollama HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"Ollama unavailable at {self.base_url}; start Ollama and install {self.model}") from exc
        if result.get("done_reason") == "length":
            raise ValueError("Ollama output was truncated; increase context or output budget")
        return json.loads(result["message"]["content"])


def validate_conclusion(result: dict, visible: dict[int, list[str]]) -> None:
    """Reject malformed JSON, unseen/future citations and unsupported effect claims.

    Verbatim matching verifies provenance, not whether a quote entails a claim.
    Semantic accuracy still needs human/held-out evaluation.
    """
    Draft202012Validator(CONCLUSION_SCHEMA).validate(result)

    def check(value: object) -> None:
        if isinstance(value, dict):
            if set(value) == {"session_number", "quote"}:
                utterances = visible.get(value["session_number"], [])
                quote = value["quote"]
                if not quote.strip() or not any(quote in utterance for utterance in utterances):
                    raise ValueError(f"Evidence is not a visible spoken excerpt: {value}")
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    check(result)
    intervention = result["intervention"]
    outcome = result["outcome"]
    if intervention["service_delivered"] is True and not intervention["delivery_evidence"]:
        raise ValueError("Delivered service requires delivery evidence")
    if outcome["intervention_helpful"] != "unknown" and (
        intervention["service_delivered"] is not True or not outcome["outcome_evidence"]
    ):
        raise ValueError("Intervention helpfulness requires delivery and post-delivery outcome evidence")
    if any(outcome[key] != "unknown" for key in ("primary_barrier_resolved", "attendance_improved")) and not outcome["outcome_evidence"]:
        raise ValueError("Observed barrier/attendance outcomes require outcome evidence")


class InterventionRAG:
    def __init__(self, index: SessionIndex, client: OllamaClient | None = None,
                 max_prompt_chars: int = 60000, validation_retries: int = 2) -> None:
        if validation_retries < 0:
            raise ValueError("validation_retries must be nonnegative")
        self.index = index
        self.client = client or OllamaClient()
        self.max_prompt_chars = max_prompt_chars
        self.validation_retries = validation_retries

    def analyse(self, student_id: str, through_session: int | None = None,
                question: str = "What changed, which actions remain pending, and what is the intervention outcome?",
                *, on_session: Callable[[dict], None] | None = None) -> dict:
        """Replay attended sessions; every step sees only earlier validated memory.

        Replays use current source text, avoiding stale summaries after edits.
        The full current session is always supplied; prior raw passages supplement
        cumulative structured memory. Stop rather than silently truncate context.
        """
        history = self.index.history(student_id, through_session)
        timeline = []
        for current in history:
            passages = self.index.retrieve(student_id, question + " " + current.text,
                                           before_session=current.number)
            memory = [{"session_number": step["session_number"], "findings": step["findings"]}
                      for step in timeline]
            # Only raw turns in this prompt and exact evidence carried in memory
            # can be cited, not unprovided passages from the rest of the index.
            visible: dict[int, list[str]] = {
                current.number: [turn.split(": ", 1)[1] for turn in current.turns]
            }
            for passage in passages:
                visible.setdefault(passage.session_number, []).extend(
                    turn.split(": ", 1)[1] for turn in passage.text.split("\n\n")
                )

            def add_memory_quotes(value: object) -> None:
                if isinstance(value, dict):
                    if set(value) == {"session_number", "quote"}:
                        visible.setdefault(value["session_number"], []).append(value["quote"])
                    for item in value.values():
                        add_memory_quotes(item)
                elif isinstance(value, list):
                    for item in value:
                        add_memory_quotes(item)

            add_memory_quotes(memory)
            references = {}
            reference_ids = {}

            def reference(number: int, quote: str) -> str:
                key = (number, quote)
                if key not in reference_ids:
                    evidence_id = f"e{len(references) + 1}"
                    reference_ids[key] = evidence_id
                    references[evidence_id] = {"session_number": number, "quote": quote[:600]}
                return reference_ids[key]

            def source_turns(turns: tuple[str, ...] | list[str], number: int) -> list[dict]:
                return [{**turn, "evidence_id": reference(number, turn["utterance"])}
                        for turn in spoken_turns(turns)]

            context = {"question": question, "current_session_number": current.number,
                       "earlier_validated_memory": map_evidence(memory, lambda evidence: {
                           **evidence, "evidence_id": reference(evidence["session_number"], evidence["quote"])}),
                       "retrieved_prior_passages": [
                           {"session_number": p.session_number, "chunk": p.chunk,
                            "utterances": source_turns(p.text.split("\n\n"), p.session_number)}
                           for p in passages
                       ],
                       "current_conversation": source_turns(current.turns, current.number)}
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ]
            if len(json.dumps(messages)) + len(json.dumps(GENERATION_SCHEMA)) > self.max_prompt_chars:
                raise ValueError("History exceeds prompt budget; increase the budget and model context explicitly")

            def resolve(evidence: dict) -> dict:
                evidence_id = evidence["evidence_id"]
                if evidence_id not in references:
                    raise ValueError(f"Unknown evidence_id: {evidence_id}; select an ID supplied in this prompt")
                return dict(references[evidence_id])

            validation_failures = []
            for attempt in range(self.validation_retries + 1):
                if len(json.dumps(messages)) + len(json.dumps(GENERATION_SCHEMA)) > self.max_prompt_chars:
                    raise ValueError("Repair exceeds prompt budget; increase the budget and model context explicitly")
                try:
                    generated = self.client.generate(messages, GENERATION_SCHEMA)
                    Draft202012Validator(GENERATION_SCHEMA).validate(generated)
                    findings = map_evidence(generated, resolve)
                    validate_conclusion(findings, visible)
                    break
                except (ValueError, ValidationError) as exc:
                    # A rejected response never enters the memory timeline.
                    error = str(exc)[:1200]
                    validation_failures.append(error)
                    if attempt == self.validation_retries:
                        raise ValueError(
                            f"Session {current.number} failed validation after {attempt + 1} attempts: {error}"
                        ) from exc
                    messages.append({"role": "user", "content": (
                        "The previous generation was rejected by validation: " + error +
                        "\nGenerate the complete JSON again from the original supplied evidence. "
                        "Select only evidence_id values present beside current utterances, retrieved utterances "
                        "or earlier validated memory. Do not generate quote or session_number inside evidence. "
                        "Do not treat a rejected ID as new evidence. Check every citation and outcome field."
                    )})
            timeline.append({"session_number": current.number, "source": current.source,
                             "sha256": current.digest, "findings": findings,
                             "validation_failures": validation_failures,
                             "retrieved_passages": [asdict(p) for p in passages]})
            if on_session is not None:
                on_session(timeline[-1])
        return {"student_id": student_id, "as_of_session": history[-1].number,
                "model": self.client.model, "retrieval": "sqlite_fts5_bm25",
                "question": question, "timeline": timeline,
                "conclusion": timeline[-1]["findings"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("student_id", help="Full relative history folder, e.g. 01_transport_assessment/intervention_student_001")
    parser.add_argument("--root", type=Path, default=HISTORIES)
    parser.add_argument("--through-session", type=int)
    parser.add_argument("--question", default="What changed, which actions remain pending, and what is the intervention outcome?")
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--output", type=Path, default=RESULTS / "conclusion.json")
    args = parser.parse_args()
    index = SessionIndex(RESULTS / "sessions.sqlite3")
    try:
        index.build(load_sessions(args.root))
        report = InterventionRAG(index, OllamaClient(args.model)).analyse(
            args.student_id, args.through_session, args.question)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(args.output)
    finally:
        index.close()


if __name__ == "__main__":
    main()
