"""A retrieved text passage."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Passage:
    session_number: int
    text: str
    first_turn_number: int = 1
    turns: tuple[str, ...] = ()
