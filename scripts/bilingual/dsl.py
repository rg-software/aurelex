"""DSL card model and emitter for translation dictionaries.

Card layout (decided in docs/BILINGUAL-EXPERIMENT.md): senses numbered per
part of speech, Russian definition as the sense heading, ``[trn]`` equivalents,
English synonyms secondary, at most one anchored example pair per sense in a
per-sense collapsible zone. The L1 gloss is build metadata only and is never
rendered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .constants import (
    EQUIVALENTS_PER_SENSE,
    EXAMPLES_PER_SENSE,
    SYNONYMS_PER_SENSE,
)


def escape_dsl(text: Optional[str]) -> str:
    """Escape free text so it cannot form DSL markup.

    Same contract as the kaikki builder: backslash, square brackets and the
    ``<<``/``>>`` delimiters are escaped; tabs/newlines collapse to spaces.
    """
    if not text:
        return ""
    s = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    s = s.replace("\t", " ")
    s = s.replace("\\", "\\\\")
    s = s.replace("[", "\\[")
    s = s.replace("]", "\\]")
    s = s.replace("<<", "\\<\\<").replace(">>", "\\>\\>")
    s = re.sub(r" {2,}", " ", s)
    return s.strip()


def clean_headword(word: Optional[str]) -> str:
    """Sanitise a headword line (column 0, no indentation)."""
    hw = escape_dsl(word)
    hw = hw.lstrip("\t ")
    if hw.startswith("#"):
        hw = "\\" + hw
    return hw


def header_arg(value: Optional[str]) -> str:
    """Sanitise a quoted DSL header argument (no embedded quotes)."""
    return escape_dsl(value).replace('"', "'")


@dataclass
class Sense:
    """One RU-synset sense: Russian definition, equivalents, EN synonyms,
    and at most one anchored example pair."""

    definition: str = ""
    equivalents: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    example: Optional[Tuple[str, str]] = None


@dataclass
class Card:
    """One headword card: part of speech plus senses in render order."""

    headword: str = ""
    pos: str = ""
    senses: List[Sense] = field(default_factory=list)
    audio: List[str] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)
    pairs: List[Tuple[str, str]] = field(default_factory=list)


def emit_sense(sense: Sense, number: int) -> List[str]:
    """Render one sense as DSL body lines (no headword line).

    Numbering is plain text (``1. definition``), kaikki-style: the reader
    renders ``[mN]`` by indentation level and only single-digit tags exist, so
    a global ``[m10]`` counter would be an unknown tag on long cards. Every
    sense sits at ``[m1]`` — one level under its part of speech.
    """
    lines = [f"    [m1]{number}. {escape_dsl(sense.definition)}[/m]"]
    for equiv in sense.equivalents[:EQUIVALENTS_PER_SENSE]:
        lines.append(f"        [trn]{escape_dsl(equiv)}[/trn]")
    if sense.synonyms:
        kept = ", ".join(escape_dsl(s) for s in sense.synonyms[:SYNONYMS_PER_SENSE])
        lines.append(f"        (syn. {kept})")
    if sense.example is not None:
        en, ru = sense.example
        lines.append("        [*]")
        lines.append(f"        [ex]{escape_dsl(en)}[/ex]")
        lines.append(f"        [trn]{escape_dsl(ru)}[/trn]")
        lines.append("        [/*]")
    return lines


def emit_card(card: Card) -> List[str]:
    """Render one card: headword line, POS line, audio, numbered senses."""
    lines = [clean_headword(card.headword)]
    if card.pos:
        lines.append(f"    [p]{escape_dsl(card.pos)}[/p]")
    for name in card.audio:
        lines.append(f"    [s]{escape_dsl(name)}[/s]")
    for comment in card.comments:
        lines.append(f"    [com]{escape_dsl(comment)}[/com]")
    if card.pairs:
        # Pairs ARE the article here (no senses to annotate), so they are not
        # hidden behind a zone — a card that is only a [+] button helps nobody.
        # The Russian line is marked [trn]: it is a translation, not an example.
        for en, ru in card.pairs:
            lines.append(f"    [ex]{escape_dsl(en)}[/ex]")
            lines.append(f"    [trn]{escape_dsl(ru)}[/trn]")
    for i, sense in enumerate(card.senses, 1):
        lines.extend(emit_sense(sense, i))
    return lines


def assemble(
    cards: Sequence[Card], name: str, title: Optional[str] = None,
    about: Optional[Card] = None,
) -> str:
    """Assemble the full DSL text: headers, about card, cards in headword order.

    Deterministic: same cards always yield the same text (cards sorted by
    headword; header order fixed; the about card always opens the dictionary).
    """
    shown = title or name
    out = [
        f'#NAME "{header_arg(shown)}"',
        '#INDEX_LANGUAGE "English"',
        '#CONTENTS_LANGUAGE "Russian"',
        "",
    ]
    if about is not None:
        out.extend(emit_card(about))
        out.append("")
    for card in sorted(cards, key=lambda c: c.headword):
        out.extend(emit_card(card))
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"
