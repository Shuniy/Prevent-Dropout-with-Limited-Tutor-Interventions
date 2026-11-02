"""Load the dialogue corpus as a problem and support reference index."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, cast

try:
    from ..models.mentor import ALL_SUPPORT_TYPES, SupportType
except ImportError:  # Support running ``python src/main.py`` directly.
    from models.mentor import ALL_SUPPORT_TYPES, SupportType


DIALOGUE_ROOT = Path(__file__).resolve().parent / "student_mentor_dialogues"
DEFAULT_DIALOGUE_MANIFEST_PATH = DIALOGUE_ROOT / "manifest.csv"

REQUIRED_MANIFEST_FIELDS = {
    "session_id",
    "filename",
    "category",
    "category_label",
    "primary_scenario",
    "concern_label",
    "support_type",
    "support_status",
    "session_stage",
    "minutes",
}


@dataclass(frozen=True)
class ConcernCategory:
    """One broad, ordered problem category from the dialogue index."""

    category_id: str
    label: str


@dataclass(frozen=True)
class Concern:
    """One specific student problem nested under a broad category."""

    concern_id: str
    label: str
    category_id: str
    category_label: str


@dataclass(frozen=True)
class DialogueSession:
    """Indexed metadata for one student-mentor dialogue transcript."""

    session_id: str
    filename: str
    category_id: str
    category_label: str
    concern_id: str
    concern_label: str
    support_type: SupportType
    support_status: str
    session_stage: str
    minutes: int
    transcript_path: Path

    def read_transcript(self) -> str:
        """Return the complete synthetic transcript for this session."""

        return self.transcript_path.read_text(encoding="utf-8")


class DialogueIndex:
    """Query dialogue sessions by their indexed category, problem, or support."""

    def __init__(self, sessions: Iterable[DialogueSession]) -> None:
        self.sessions = tuple(sessions)
        if not self.sessions:
            raise ValueError("dialogue index must contain at least one session")

        self._sessions_by_concern: dict[str, list[DialogueSession]] = {}
        self._sessions_by_category: dict[str, list[DialogueSession]] = {}
        self._sessions_by_support: dict[SupportType, list[DialogueSession]] = {}
        categories: dict[str, ConcernCategory] = {}
        concerns: dict[str, Concern] = {}
        session_ids: set[str] = set()

        for session in self.sessions:
            if session.session_id in session_ids:
                raise ValueError(
                    f"duplicate dialogue session ID: {session.session_id!r}"
                )
            session_ids.add(session.session_id)

            category = ConcernCategory(
                category_id=session.category_id,
                label=session.category_label,
            )
            previous_category = categories.setdefault(session.category_id, category)
            if previous_category != category:
                raise ValueError(
                    f"inconsistent category metadata for {session.category_id!r}"
                )

            concern = Concern(
                concern_id=session.concern_id,
                label=session.concern_label,
                category_id=session.category_id,
                category_label=session.category_label,
            )
            previous_concern = concerns.setdefault(session.concern_id, concern)
            if previous_concern != concern:
                raise ValueError(
                    f"inconsistent concern metadata for {session.concern_id!r}"
                )

            self._sessions_by_concern.setdefault(session.concern_id, []).append(session)
            self._sessions_by_category.setdefault(session.category_id, []).append(session)
            self._sessions_by_support.setdefault(session.support_type, []).append(session)

        self.categories = tuple(
            categories[category_id] for category_id in sorted(categories)
        )
        self.concerns = tuple(
            sorted(
                concerns.values(),
                key=lambda concern: (concern.category_id, concern.concern_id),
            )
        )
        represented_support_types = set(self._sessions_by_support)
        self.support_types = tuple(
            support_type
            for support_type in ALL_SUPPORT_TYPES
            if support_type in represented_support_types
        )
        self._concerns_by_id = concerns

    @classmethod
    def from_manifest(
        cls,
        manifest_path: str | Path = DEFAULT_DIALOGUE_MANIFEST_PATH,
    ) -> DialogueIndex:
        """Load and validate the corpus' canonical ``manifest.csv`` index."""

        path = Path(manifest_path)
        if not path.is_file():
            raise FileNotFoundError(f"dialogue manifest not found: {path}")

        dialogue_root = path.parent.resolve()
        sessions: list[DialogueSession] = []
        with path.open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            fields = set(reader.fieldnames or ())
            missing_fields = REQUIRED_MANIFEST_FIELDS - fields
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(f"dialogue manifest is missing fields: {missing}")

            for row_number, row in enumerate(reader, start=2):
                support_type = row["support_type"]
                if support_type not in ALL_SUPPORT_TYPES:
                    raise ValueError(
                        f"unknown support type {support_type!r} on row {row_number}"
                    )

                relative_filename = Path(row["filename"])
                transcript_path = (dialogue_root / relative_filename).resolve()
                if not transcript_path.is_relative_to(dialogue_root):
                    raise ValueError(
                        f"dialogue path escapes the corpus on row {row_number}"
                    )
                if not transcript_path.is_file():
                    raise FileNotFoundError(
                        f"dialogue transcript not found: {transcript_path}"
                    )

                sessions.append(
                    DialogueSession(
                        session_id=row["session_id"],
                        filename=relative_filename.as_posix(),
                        category_id=row["category"],
                        category_label=row["category_label"],
                        concern_id=row["primary_scenario"],
                        concern_label=row["concern_label"],
                        support_type=cast(SupportType, support_type),
                        support_status=row["support_status"],
                        session_stage=row["session_stage"],
                        minutes=int(row["minutes"]),
                        transcript_path=transcript_path,
                    )
                )

        return cls(sessions)

    def concern(self, concern_id: str) -> Concern:
        """Return one concern, rejecting IDs that are absent from the index."""

        try:
            return self._concerns_by_id[concern_id]
        except KeyError as error:
            raise ValueError(f"unknown dialogue concern: {concern_id!r}") from error

    def sessions_for(
        self,
        *,
        concern_id: str | None = None,
        category_id: str | None = None,
        support_type: SupportType | None = None,
    ) -> tuple[DialogueSession, ...]:
        """Return sessions matching every supplied index field."""

        if concern_id is not None:
            candidates = self._sessions_by_concern.get(concern_id, ())
        elif category_id is not None:
            candidates = self._sessions_by_category.get(category_id, ())
        elif support_type is not None:
            candidates = self._sessions_by_support.get(support_type, ())
        else:
            candidates = self.sessions

        return tuple(
            session
            for session in candidates
            if (category_id is None or session.category_id == category_id)
            and (support_type is None or session.support_type == support_type)
        )

    def support_types_for(self, concern_id: str) -> tuple[SupportType, ...]:
        """Return support types represented by dialogues for one problem."""

        self.concern(concern_id)
        represented = {
            session.support_type
            for session in self._sessions_by_concern[concern_id]
        }
        return tuple(
            support_type
            for support_type in ALL_SUPPORT_TYPES
            if support_type in represented
        )
