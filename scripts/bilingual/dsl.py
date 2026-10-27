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


def unescape_dsl(text: str) -> str:
    """Reverse :func:`escape_dsl` for values escaped elsewhere.

    kaikki's per-record transcription picker returns DSL-ready text; the
    builder stores the raw value (so the HTML preview and any future plain-
    text consumer are not shown escapes) and re-escapes at emit time.
    """
    out: List[str] = []
    it = iter(range(len(text)))
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in "\\[]<>":
            out.append(text[i + 1])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


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
    """One RU-synset sense: equivalents lead, Russian definition explains."""

    definition: str = ""
    equivalents: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    example: Optional[Tuple[str, str]] = None
    pos: str = ""


@dataclass
class Card:
    """One headword card: part of speech plus senses in render order."""

    headword: str = ""
    pos: str = ""
    transcription: str = ""
    senses: List[Sense] = field(default_factory=list)
    audio: List[str] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)
    pairs: List[Tuple[str, str]] = field(default_factory=list)
    readings: str = ""
    title: str = ""


def emit_sense(sense: Sense, number: int) -> List[str]:
    """Render one sense as DSL body lines (no headword line).

    Equivalents come first — they are the lookup answer — with a numbered
    ``[m1]`` marker, then the Russian definition as a subordinate italic line,
    mirroring printed bilingual dictionaries (translations lead, qualifiers
    follow). ``number`` 0 means a lone sense: no counter is emitted, since a
    solitary "1." carries no information. (The reader's ``[mN]`` tags are
    single-digit, so a global ``[m10]`` counter would be an unknown tag on
    long cards.)
    """
    lines = []
    if number > 0:
        lines.append(f"    [m1]{number}.[/m]")
    for equiv in sense.equivalents[:EQUIVALENTS_PER_SENSE]:
        lines.append(f"    [trn]{escape_dsl(equiv)}[/trn]")
    if sense.definition:
        lines.append(f"    [i]{escape_dsl(sense.definition)}[/i]")
    if sense.example is not None:
        en, ru = sense.example
        lines.append("        [*]")
        lines.append(f"        [ex]{escape_dsl(en)}[/ex]")
        lines.append(f"        [trn]{escape_dsl(ru)}[/trn]")
        lines.append("        [/*]")
    if sense.synonyms:
        kept = ", ".join(escape_dsl(s) for s in sense.synonyms[:SYNONYMS_PER_SENSE])
        lines.append(f"        (syn. {kept})")
    return lines


def emit_card(card: Card) -> List[str]:
    """Render one card: headword line, audio, then POS sections in order.

    Senses carrying a part of speech start a new `[p]` section when it
    changes; numbering restarts at each section. Senses without one keep the
    card-level POS line for backward compatibility.
    """
    lines = [clean_headword(card.headword)]
    if card.title:
        # Alias card (opt-in reading indexing): name the article after its
        # primary headword, so a lookup that arrived through a reading knows
        # which word it defines — same convention as the monolingual card.
        lines.append(f"    [b]{escape_dsl(card.title)}[/b]")
    if card.transcription:
        lines.append(f"    [t]{escape_dsl(card.transcription)}[/t]")
    if card.pos:
        lines.append(f"    [p]{escape_dsl(card.pos)}[/p]")
    for name in card.audio:
        lines.append(f"    [s]{escape_dsl(name)}[/s]")
    if card.readings:
        # Kana readings (Japanese on/kun groupings), same [com] line the
        # monolingual card renders — a pronunciation aid, not a definition.
        lines.append(f"    [com]{escape_dsl(card.readings)}[/com]")
    for comment in card.comments:
        lines.append(f"    [com]{escape_dsl(comment)}[/com]")
    if card.pairs:
        # Pairs ARE the article here (no senses to annotate), so they are not
        # hidden behind a zone — a card that is only a [+] button helps nobody.
        # The Russian line is marked [trn]: it is a translation, not an example.
        for en, ru in card.pairs:
            lines.append(f"    [ex]{escape_dsl(en)}[/ex]")
            lines.append(f"    [trn]{escape_dsl(ru)}[/trn]")
    section: Optional[str] = None
    pending: List[Sense] = []

    def flush() -> None:
        if not pending:
            return
        # A lone sense needs no counter ("1." on a single-sense card, like a
        # single-definition monolingual entry, carries no information).
        numbered = len(pending) > 1
        for i, sense in enumerate(pending, 1):
            lines.extend(emit_sense(sense, i if numbered else 0))
        pending.clear()

    for sense in card.senses:
        if sense.pos and sense.pos != section:
            flush()
            section = sense.pos
            lines.append(f"    [p]{escape_dsl(section)}[/p]")
        elif not sense.pos and section is None and card.pos:
            section = card.pos
        pending.append(sense)
    # Senses without a POS all belong to the card-level section.
    flush()
    return lines


def assemble(
    cards: Sequence[Card], name: str, title: Optional[str] = None,
    about: Optional[Card] = None,
    index_lang: str = "English", contents_lang: str = "Russian",
) -> str:
    """Assemble the full DSL text: headers, about card, cards in headword order.

    Deterministic: same cards always yield the same text (cards sorted by
    headword; header order fixed; the about card always opens the dictionary).
    The language headers follow the build direction — the app classifies the
    dictionary from them, so ru→en dictionaries must not claim English/Russian.
    """
    shown = title or name
    out = [
        f'#NAME "{header_arg(shown)}"',
        f'#INDEX_LANGUAGE "{header_arg(index_lang)}"',
        f'#CONTENTS_LANGUAGE "{header_arg(contents_lang)}"',
        "",
    ]
    if about is not None:
        out.extend(emit_card(about))
        out.append("")
    for card in sorted(cards, key=lambda c: c.headword):
        out.extend(emit_card(card))
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"
