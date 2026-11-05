"""Stable keyed draws shared by the environment and independent note renderer."""

import hashlib
import json


def keyed_uniform(seed: int, student_id: str, month: int, event_type: str) -> float:
    key = json.dumps([seed, student_id, month, event_type], separators=(",", ":"))
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return (int.from_bytes(digest[:8], "big") >> 11) / 2**53
