"""Deterministic headword sampling for the bilingual builder.

``first`` takes the first N headwords in list order; ``random`` spreads across
the whole list by sha256 key, so re-runs on the same inputs yield the same
sample (mirrors the kaikki tool's reproducibility contract on a bounded list
rather than a snapshot window).
"""

from __future__ import annotations

import hashlib
from typing import List, Sequence


def select(headwords: Sequence[str], n: int, mode: str = "first") -> List[str]:
    """Return at most N headwords, deterministically for the same inputs."""
    if n <= 0:
        return []
    if mode == "random":
        keyed = sorted(
            headwords, key=lambda w: hashlib.sha256(w.encode("utf-8")).digest()
        )
        return list(keyed[:n])
    return list(headwords[:n])
