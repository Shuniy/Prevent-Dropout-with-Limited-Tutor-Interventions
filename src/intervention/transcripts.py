"""Read spoken turns and allowlisted descriptive session headers."""

from pathlib import Path
import re
from .session import Session
from ..utils.constants import HISTORIES


def spoken_turns(turns: tuple[str, ...] | list[str], *, first_turn_number: int = 1) -> list[dict]:
    """Represent each spoken turn with its speaker and utterance."""
    return [{"turn_number": number, "speaker": turn.split(": ", 1)[0],
             "utterance": turn.split(": ", 1)[1]}
            for number, turn in enumerate(turns, start=first_turn_number)]


def group_sessions(sessions: list[Session]) -> dict[str, list[Session]]:
    """Validate and order source histories without building a retrieval index."""
    grouped: dict[str, list[Session]] = {}
    for session in sessions:
        if type(session.number) is not int or session.number < 1 or not session.turns:
            raise ValueError("Sessions require a positive number and spoken turns")
        history = grouped.setdefault(session.history_id, [])
        if any(old.number == session.number for old in history):
            raise ValueError("Duplicate session number within a source history")
        history.append(session)
    for history in grouped.values():
        history.sort(key=lambda session: session.number)
    return grouped


def history_sessions(histories: dict[str, list[Session]], history_id: str,
                     through_session: int | None = None) -> list[Session]:
    if history_id not in histories:
        raise ValueError(f"Unknown source history: {history_id}")
    history = histories[history_id]
    if through_session is not None:
        if through_session not in {session.number for session in history}:
            raise ValueError(f"Session {through_session} is not recorded for {history_id}")
        history = [session for session in history if session.number <= through_session]
    return list(history)


def load_sessions(root: Path = HISTORIES) -> list[Session]:
    """Load only session Markdown; full relative parent paths are history IDs."""
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
        # Read only descriptive headers before the conversation, never outcome notes.
        header = text.split("##", 1)[0]
        metadata = {}
        for label, key in (("Intervention type", "intervention_type"),
                           ("Date", "date"), ("Stage", "stage")):
            value = re.search(rf"^\*\*{label}:\*\*[ \t]*([^\n]+)", header, re.MULTILINE)
            if value:
                metadata[key] = value.group(1).strip()
        sessions.append(Session(
            path.parent.relative_to(root).as_posix(), int(match[1]),
            turns, **metadata,
        ))
    if not sessions:
        raise ValueError(f"No session transcripts found in {root}")
    identities = [(s.history_id, s.number) for s in sessions]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate session number within a source history")
    return sorted(sessions, key=lambda s: (s.history_id, s.number))

