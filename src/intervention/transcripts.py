"""Read spoken transcript turns, excluding headers and labels."""

from pathlib import Path
import re
from .session import Session
from ..utils.constants import HISTORIES


def spoken_turns(turns: tuple[str, ...] | list[str]) -> list[dict[str, str]]:
    """Represent each spoken turn with its speaker and utterance."""
    return [{"speaker": turn.split(": ", 1)[0], "utterance": turn.split(": ", 1)[1]}
            for turn in turns]


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
        sessions.append(Session(
            path.parent.relative_to(root).as_posix(), int(match[1]),
            turns,
        ))
    if not sessions:
        raise ValueError(f"No session transcripts found in {root}")
    identities = [(s.history_id, s.number) for s in sessions]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate session number within a source history")
    return sorted(sessions, key=lambda s: (s.history_id, s.number))

