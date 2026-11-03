"""Spoken turns belonging to one recorded session."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    history_id: str
    number: int
    turns: tuple[str, ...]

    intervention_type: str | None = None
    date: str | None = None
    stage: str | None = None

    @property
    def metadata(self) -> dict[str, str]:
        """Descriptive headers only; no prewritten findings or outcome labels."""
        return {key: value for key in ("intervention_type", "date", "stage")
                if (value := getattr(self, key)) is not None}

    @property
    def text(self) -> str:
        return "\n\n".join(self.turns)
