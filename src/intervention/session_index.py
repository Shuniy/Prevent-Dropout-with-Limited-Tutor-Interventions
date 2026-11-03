"""SQLite text retrieval scoped to a history and earlier sessions."""

from pathlib import Path
import re
import sqlite3

from .session import Session
from .passage import Passage


class SessionIndex:
    """Persistent source index; rebuilding replaces stale/deleted source chunks."""

    def __init__(self, path: Path | str = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5("
            "history_id UNINDEXED, session_number UNINDEXED, "
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
            history = grouped.setdefault(session.history_id, [])
            if any(old.number == session.number for old in history):
                raise ValueError("Duplicate session number within a source history")
            history.append(session)
        with self.connection:
            self.connection.execute("DELETE FROM passages")
            for history in grouped.values():
                history.sort(key=lambda s: s.number)
                for session in history:
                    for chunk, start in enumerate(range(0, len(session.turns), turns_per_chunk)):
                        self.connection.execute(
                            "INSERT INTO passages VALUES (?, ?, ?, ?)",
                            (session.history_id, session.number, chunk,
                             "\n\n".join(session.turns[start:start + turns_per_chunk])),
                        )
        self.sessions = grouped

    def history(self, history_id: str, through_session: int | None = None) -> list[Session]:
        if history_id not in self.sessions:
            raise ValueError(f"Unknown source history: {history_id}")
        history = self.sessions[history_id]
        if through_session is not None:
            if through_session not in {s.number for s in history}:
                raise ValueError(f"Session {through_session} is not recorded for {history_id}")
            history = [s for s in history if s.number <= through_session]
        return list(history)

    def retrieve(self, history_id: str, query: str, before_session: int,
                 per_session: int = 2) -> list[Passage]:
        """Retrieve matches from each earlier session, with a recency fallback.

        Per-session coverage keeps the initial session visible even when recent
        wording differs. Filtering happens inside SQL before BM25 ranking.
        """
        if per_session < 1:
            raise ValueError("per_session must be positive")
        history = self.history(history_id)
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
                    "AND history_id = ? AND session_number = ? "
                    "ORDER BY bm25(passages), CAST(chunk AS INTEGER) LIMIT ?",
                    (expression, history_id, session.number, per_session),
                ).fetchall()
            # Fill with the closing turns, where agreed actions usually occur.
            fallback = self.connection.execute(
                "SELECT chunk, text FROM passages WHERE history_id = ? "
                "AND session_number = ? ORDER BY CAST(chunk AS INTEGER) DESC LIMIT ?",
                (history_id, session.number, per_session),
            ).fetchall()
            seen = {row[0] for row in rows}
            for row in fallback:
                if len(rows) < per_session and row[0] not in seen:
                    rows.append(row)
                    seen.add(row[0])
            passages.extend(Passage(session.number, text)
                            for chunk, text in sorted(rows, key=lambda row: int(row[0])))
        return passages
