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

The corpus is symmetric: both frequency counters and both inverted indexes
are built in the same acquisition pass, and :meth:`Corpus.flipped` swaps the
pair order so the Russian→English dictionary reuses every selection
function unchanged (matching, dedupe, ranking, case merge, hygiene rules).
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
    """Tatoeba slice: pairs, per-side token frequencies, pinned date, indexes.

    ``pairs`` are always (source, target) in build order — English→Russian
    as acquired. ``flipped()`` returns the Russian→English view with the
    pair order, counters, indexes, and tokenizer swapped, so the selection
    machinery cannot tell which direction it serves.
    """

    pairs: List[Tuple[str, str]] = field(default_factory=list)
    rus_freq: Counter = field(default_factory=Counter)
    date: str = ""
    index: Dict[str, List[int]] = field(default_factory=dict)
    eng_freq: Counter = field(default_factory=Counter)
    index_ru: Dict[str, List[int]] = field(default_factory=dict)
    lang: str = "en"

    def flipped(self) -> "Corpus":
        """Russian→English view of this corpus (new object, shared date)."""
        return Corpus(
            pairs=[(ru, en) for en, ru in self.pairs],
            rus_freq=self.eng_freq,
            date=self.date,
            index=self.index_ru,
            eng_freq=self.rus_freq,
            index_ru=self.index,
            lang="ru" if self.lang == "en" else "en",
        )


_WORD_RE = re.compile(r"[a-z0-9']+")
_RU_WORD_RE = re.compile(r"[а-яё0-9]+")
_TOKENIZERS = {"en": _WORD_RE, "ru": _RU_WORD_RE}


def index_pairs(pairs: Sequence[Tuple[str, str]],
                lang: str = "en") -> Dict[str, List[int]]:
    """Inverted index over source-side tokens: token -> pair positions.

    Built once per build; without it a full dictionary pays a regex scan of
    all pairs per headword (~35k × 831k searches). Lookup stays exact: the
    index only narrows candidates, the word-boundary regex still decides.
    ``lang`` selects the tokenizer (`en` or `ru` word regex).
    """
    tok = _TOKENIZERS[lang]
    index: Dict[str, List[int]] = {}
    for i, (src, _tgt) in enumerate(pairs):
        for t in set(tok.findall(src.lower())):
            index.setdefault(t, []).append(i)
    return index


def pairs_for(word: str, corpus: Corpus) -> List[Tuple[str, str]]:
    """Candidate pairs for a headword: index hit, then exact regex check.

    A word whose token never occurs in the corpus cannot match anywhere, so
    it returns immediately instead of scanning all pairs; multi-token words
    scan only the smallest token list. The word-boundary regex still decides
    every candidate. The match side follows the corpus view: on a flipped
    (Russian→English) corpus the Russian text is searched with the Russian
    tokenizer. Single-character headwords never match at all: in running
    English text a one-letter token is overwhelmingly the article "a" (or the
    pronoun "I"), so any hit would illustrate the article, not the headword
    ("Be a man" for the letter A = ampere). Such headwords keep their card
    but ship no examples.
    """
    if len(word) < 2:
        return []
    pat = re.compile(r"(?<!\w)" + re.escape(word) + r"(?!\w)", re.I)
    tok = _TOKENIZERS[corpus.lang]
    toks = tok.findall(word.lower())
    if not toks:
        return []
    lists = []
    for tok in toks:
        hit = corpus.index.get(tok)
        if hit is None:
            return []
        lists.append(hit)
    cands = (corpus.pairs[i] for i in min(lists, key=len))
    return [p for p in cands if pat.search(p[0])]


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
    eng_freq: Counter = Counter()
    for text in eng.values():
        eng_freq.update(_WORD_RE.findall(text.lower()))
    by_en = index_pairs(pairs)
    by_ru = index_pairs([(ru, en) for en, ru in pairs], lang="ru")
    return Corpus(pairs=pairs, rus_freq=freq, date=date, index=by_en,
                  eng_freq=eng_freq, index_ru=by_ru)


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
    first_en: Dict[str, str] = {}
    for en, ru in pairs:
        norm = _normalize(en)
        if norm not in by_en:
            by_en[norm] = []
            first_en[norm] = en
        by_en[norm].append(ru)
    order = list(by_en)
    pats = _compile([e.lower() for e in equivalents])
    ranked = []
    for norm in order:
        variant = rank_variants(by_en[norm], equivalents, rus_freq)
        if variant is None:
            continue
        en_text = first_en[norm]
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
