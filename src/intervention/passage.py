"""A retrieved text passage."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Passage:
    session_number: int
    text: str
