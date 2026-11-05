"""The small planning contract shared by all school allocation policies."""

from typing import Protocol

from .allocation_result import AllocationResult
from .decision_state import DecisionState


class AllocationPolicy(Protocol):
    """Choose programmes from current immutable observations and resources only."""

    def plan(self, state: DecisionState) -> AllocationResult: ...
