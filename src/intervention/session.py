"""Spoken turns belonging to one recorded session."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    history_id: str
    number: int
    turns: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(self.turns)
