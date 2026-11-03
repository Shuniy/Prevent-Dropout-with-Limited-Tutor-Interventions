"""Validate coherent source histories and select with a local seeded RNG."""

import random
from .session_index import SessionIndex
from ..utils.constants import ALL_SUPPORT_TYPES


def catalogue_histories(index: SessionIndex) -> dict[str, tuple[str, ...]]:
    catalogue: dict[str, list[str]] = {}
    for history_id, history in sorted(index.sessions.items()):
        if [session.number for session in history] != list(range(1, len(history) + 1)):
            raise ValueError(f"History must have consecutive sessions starting at 1: {history_id}")
        folder = history_id.split("/", 1)[0]
        support = folder.split("_", 1)[1] if folder[:2].isdigit() else folder
        if support not in ALL_SUPPORT_TYPES:
            raise ValueError(f"Unknown history support type: {folder}")
        catalogue.setdefault(support, []).append(history_id)
    return {support: tuple(histories) for support, histories in catalogue.items()}


def select_history(catalogue: dict[str, tuple[str, ...]], support: str,
                   rng: random.Random) -> str | None:
    histories = catalogue.get(support, ())
    return rng.choice(histories) if histories else None
