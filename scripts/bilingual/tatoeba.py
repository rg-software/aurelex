"""Dict B example selection: Tatoeba acquisition + dedupe → rank → cap.

Acquisition joins per-language sentence files with the pre-joined per-pair
link file (no global dump needed)::

    eng_sentences.tsv.bz2   id<TAB>eng<TAB>text
    rus_sentences.tsv.bz2   id<TAB>rus<TAB>text
    eng-rus_links.tsv.bz2   eng_id<TAB>rus_id

Selection per headword, decided in docs/BILINGUAL-EXPERIMENT.md: group pairs
by normalized English text and keep one Russian variant per group; rank
anchored-first (Russian side contains a Dict-A equivalent as a whole word),
then rarest anchor, then shortest; length ranks, never filters. A sense with
no anchored pair falls back to an unanchored (concordance) pair.
"""

from __future__ import annotations

import bz2
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .constants import EXAMPLES_PER_HEADWORD, PREFERRED_EXAMPLE_LENGTH


@dataclass
class Corpus:
    """Loaded Tatoeba slice: pairs plus Russian token frequencies."""

    pairs: List[Tuple[str, str]] = field(default_factory=list)
    rus_freq: Counter = field(default_factory=Counter)
    date: str = ""


def load_sentences(path: str) -> Dict[int, str]:
    """Load an ``id<TAB>lang<TAB>text`` sentence file (plain or ``.bz2``)."""
    opener = bz2.open if path.endswith(".bz2") else open
    sentences = {}
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 2)
            if len(parts) == 3:
                try:
                    sentences[int(parts[0])] = parts[2]
                except ValueError:
                    continue
    return sentences


def load_links(path: str) -> List[Tuple[int, int]]:
    """Load an ``eng_id<TAB>rus_id`` link file (plain or ``.bz2``)."""
    opener = bz2.open if path.endswith(".bz2") else open
    links = []
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            halves = line.split()
            if len(halves) != 2:
                continue
            try:
                links.append((int(halves[0]), int(halves[1])))
            except ValueError:
                continue
    return links


def acquire(eng_path: str, rus_path: str, links_path: str, date: str) -> Corpus:
    """Join sentences with links into eng→rus pairs, pinned to an export date.

    The date is the operator-recorded weekly-export date (like the kaikki
    ``--dump-date``); it travels with the corpus into provenance.
    """
    eng = load_sentences(eng_path)
    rus = load_sentences(rus_path)
    pairs = [
        (eng[a], rus[b])
        for a, b in load_links(links_path)
        if a in eng and b in rus
    ]
    freq: Counter = Counter()
    for text in rus.values():
        freq.update(re.findall(r"[а-яё]+", text.lower()))
    return Corpus(pairs=pairs, rus_freq=freq, date=date)


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _compile(equivalents: Sequence[str]) -> List[Tuple[str, "re.Pattern"]]:
    return [(e, re.compile(r"(?<!\w)" + re.escape(e) + r"(?!\w)")) for e in equivalents]


def _rarity(equivalent: str, rus_freq: Counter) -> int:
    return rus_freq.get(equivalent.split()[0].lower(), 1)


def rank_variants(
    variants: Sequence[str],
    equivalents: Sequence[str],
    rus_freq: Counter,
) -> Optional[str]:
    """Pick one Russian variant: anchored first, rarest anchor wins.

    An anchored variant contains a Dict-A equivalent as a whole word (so
    ``давать`` never matches inside ``сдаваться``). Rarity prefers
    distinctive equivalents (``посвятить``) over ubiquitous verbs (``уйти``).
    Unanchored variants lose to any anchored one; the shortest wins among
    themselves.
    """
    pats = _compile([e.lower() for e in equivalents])
    anchored = []
    for variant in variants:
        lowered = variant.lower()
        matched = [e for e, p in pats if p.search(lowered)]
        if matched:
            anchored.append((min(_rarity(e, rus_freq) for e in matched), len(variant), variant))
    if anchored:
        return min(anchored)[2]
    if variants:
        return min(variants, key=len)
    return None


def select(
    pairs: Sequence[Tuple[str, str]],
    equivalents: Sequence[str],
    rus_freq: Counter,
    keep: int = EXAMPLES_PER_HEADWORD,
) -> List[Tuple[str, str]]:
    """Dedupe → rank → cap one headword's pairs.

    Groups by normalized English text (one RU variant per group via
    :func:`rank_variants`), then keeps the best ``keep`` groups:
    anchored-first, rarest anchor, shortest English text. No length filter —
    a headword with only long pairs still ships its best.
    """
    by_en: Dict[str, List[str]] = {}
    order: List[str] = []
    for en, ru in pairs:
        norm = _normalize(en)
        if norm not in by_en:
            by_en[norm] = []
            order.append(norm)
        by_en[norm].append(ru)
    pats = _compile([e.lower() for e in equivalents])
    ranked = []
    for norm in order:
        variant = rank_variants(by_en[norm], equivalents, rus_freq)
        if variant is None:
            continue
        en_text = next(en for en, _ru in pairs if _normalize(en) == norm)
        lowered = variant.lower()
        anchors = [e for e, p in pats if p.search(lowered)]
        score = min([_rarity(e, rus_freq) for e in anchors], default=None)
        ranked.append(((score is None, score or 0, len(en_text)), en_text, variant))
    ranked.sort(key=lambda item: item[0])
    return [(en, ru) for _, en, ru in ranked[:keep] if keep > 0]


def select_for_sense(
    sense_equivalents: Sequence[str],
    headword_pairs: Sequence[Tuple[str, str]],
    rus_freq: Counter,
) -> Optional[Tuple[str, str]]:
    """Keep at most one pair for a sense, else fall back to concordance.

    ``headword_pairs`` are this headword's pairs (already word-matched on the
    English side). A pair anchored by one of the *sense's* equivalents wins;
    with none anchored, the shortest pair ships so the sense is still
    illustrated — still bilingual, never a kaikki English-only example.
    """
    if not headword_pairs:
        return None
    pats = _compile([e.lower() for e in sense_equivalents])
    anchored = []
    for en, ru in headword_pairs:
        lowered = ru.lower()
        matched = [e for e, p in pats if p.search(lowered)]
        if matched:
            anchored.append(
                (min(_rarity(e, rus_freq) for e in matched), len(en), en, ru)
            )
    if anchored:
        _, _, en, ru = min(anchored)
        return (en, ru)
    en, ru = min(headword_pairs, key=lambda p: len(p[0]))
    return (en, ru)
