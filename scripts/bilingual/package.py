"""Deterministic `.dsl.dz` packaging for bilingual dictionaries."""

from __future__ import annotations

import os
from typing import List, Sequence, Tuple

from . import dsl as _dsl
from .dsl import Card


def _dictzip():
    import sys

    scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from kaikki import dictzip

    return dictzip


def build(
    cards: Sequence[Card],
    out_dir: str,
    name: str,
    title: str | None = None,
    about: Card | None = None,
) -> Tuple[str, str]:
    """Write ``<name>.dsl.dz`` deterministically; return (dz_path, dsl_text).

    Same inputs always yield byte-identical output: cards render in headword
    order, headers are fixed-order, and the dictzip writer pins chunk order
    and per-entry metadata.
    """
    text = _dsl.assemble(cards, name, title, about)
    dz = _dictzip()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.dsl.dz")
    with open(path, "wb") as f:
        f.write(dz.make_dictzip(dz.encode_dsl(text)))
    return path, text


def read(path: str) -> str:
    """Read a built ``.dsl.dz`` back to DSL text (test/verify helper)."""
    return _dictzip().read_dictzip(path)


def card_list(words: Sequence[str]) -> List[Card]:
    """Minimal cards (headword only) — keeps the skeleton CLI honest."""
    return [Card(headword=w) for w in words]
