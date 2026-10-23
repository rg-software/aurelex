"""Provenance and licensing for bilingual dictionaries.

Every produced dictionary names the sources it was built from, their licenses,
and their pinned versions — in the about article and the sibling `.ann`
annotation; the headers identify the dictionary (#NAME title,
#INDEX/#CONTENTS_LANGUAGE). The about card states the output is for
non-commercial use and distribution only (the RuWordNet terms cover a
translation dictionary wholesale; a pairs-only dictionary travels under the
Tatoeba sentence license alone). Neither is a catalog entry.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple

from . import dsl as _dsl


@dataclass
class Sources:
    """Pinned source versions recorded in every build."""

    pwn: str = "Princeton WordNet 3.0"
    ruwordnet: str = "RuWordNet 2.0 (2021)"
    tatoeba_date: str = "unknown"
    kaikki_dump_date: str = "unknown"
    equivalents: bool = True
    direction: str = "en-ru"


def _pair_kind(sources: Sources) -> Tuple[str, str]:
    """(kind phrase, pair label) for the build direction."""
    if sources.direction == "ru-en":
        return ("a Russian-English example-sentences dictionary",
                "Tatoeba rus-eng pairs")
    return ("an English-Russian example-sentences dictionary",
            "Tatoeba eng-rus pairs")


def description_lines(title: str, sources: Sources, card_count: int) -> list:
    """Shared description for the about article and the `.ann`.

    kaikki-style: derivative-work line, source list with pinned versions, one
    license rule, entry count. Only the used sources are named. The single
    license line states the rule every source's terms agree on — it must keep
    the RuWordNet non-commercial term (a bare CC BY 2.0 FR would permit
    commercial use the thesaurus forbids) and the Tatoeba attribution.
    """
    kind = "an English-Russian translation dictionary" if sources.equivalents \
        else _pair_kind(sources)[0]
    if sources.equivalents:
        lines = [
            f"{title}: {kind}",
            "",
            "This is a derivative work, based on:",
            sources.pwn,
            sources.ruwordnet,
            f"Tatoeba eng-rus pairs, snapshot {sources.tatoeba_date}",
            f"Wiktionary / kaikki.org audio, snapshot {sources.kaikki_dump_date}",
            "",
            "Non-commercial use and distribution only, with attribution to "
            "Princeton WordNet, RuWordNet, and Tatoeba (CC BY 2.0 FR).",
        ]
    else:
        _kind, pair_label = _pair_kind(sources)
        lines = [
            f"{title}: {kind}",
            "",
            "This is a derivative work, based on "
            f"{pair_label}, snapshot {sources.tatoeba_date}.",
            "",
            "License: CC BY 2.0 FR.",
        ]
    lines.append(f"Entries: {card_count:,}")
    return lines


def about_card(title: str, sources: Sources, card_count: int) -> _dsl.Card:
    """The about article: headword is the title, body is [com] lines."""
    return _dsl.Card(
        headword=f"About {title}",
        comments=[ln for ln in description_lines(title, sources, card_count) if ln],
    )


def write_annotation(path: str, title: str, sources: Sources, card_count: int) -> None:
    """Write the Lingvo-style sibling `.ann` annotation (plain text, not DSL)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(description_lines(title, sources, card_count)) + "\n")
