"""Dict A equivalent resolution: PWN synsets bridged to RuWordNet via `ili`.

Each English synset resolves to its linked RU synsets; each linked RU synset
becomes one card sense with its Russian definition (or title fallback) and
member lemmas. Senses with no `ili` link (including all adverb senses in
practice) resolve unlinked: they keep their English synonyms, ship no
equivalents, and count against coverage.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


def _ru_pos_labels() -> Dict[str, str]:
    scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from kaikki.profiles import _RU_POS_LABELS

    return _RU_POS_LABELS


# PWN synset POS letter (as in WNSynset ids like ``07679356-n``) to card POS.
_EN_POS = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}
POS_ORDER = ["noun", "verb", "adjective", "adverb"]


@dataclass
class RuGroup:
    """One linked RU synset: title, definition (may be empty), member lemmas."""

    title: str = ""
    definition: str = ""
    lemmas: List[str] = field(default_factory=list)


@dataclass
class EnSynset:
    """One English synset: POS, member lemmas, linked RU groups (maybe none)."""

    pos: str = ""
    lemmas: List[str] = field(default_factory=list)
    groups: List[RuGroup] = field(default_factory=list)


@dataclass
class ResolvedSense:
    """One card sense, ready for the DSL emitter."""

    pos: str = ""
    definition: str = ""
    equivalents: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    linked: bool = False


@dataclass
class ResolutionReport:
    words: int = 0
    words_no_en: int = 0
    synsets: int = 0
    synsets_linked: int = 0


def russian_pos(en_pos: str) -> str:
    """Map an English POS name to the Russian card label."""
    labels = _ru_pos_labels()
    short = {"noun": "noun", "verb": "verb", "adjective": "adj", "adverb": "adv"}
    return labels.get(short.get(en_pos, en_pos), en_pos)


def _sense_definition(group: RuGroup) -> str:
    """RU definition with the title fallback, lowercased if ALL-CAPS.

    Synset titles are stored uppercase; natural-case definitions (which may
    hold proper nouns) pass through untouched.
    """
    text = (group.definition or "").strip() or group.title
    if text.isupper():
        text = text.lower()
    return text


class RuWordNetBackend:
    """Live backend over the `python-ruwordnet` sqlite database."""

    def __init__(self) -> None:
        try:
            from ruwordnet import RuWordNet
        except ImportError as exc:
            raise RuntimeError(
                "Dict A needs the `ruwordnet` package: "
                "`pip install ruwordnet && ruwordnet download`"
            ) from exc
        self._wn = RuWordNet()

    def en_synsets(self, word: str) -> List[EnSynset]:
        out = []
        for sense in self._wn.get_en_senses(word):
            syn = sense.synset
            pos_letter = syn.id.rsplit("-", 1)[-1]
            groups = [
                RuGroup(
                    title=rs.title or "",
                    definition=(rs.definition or "").strip(),
                    lemmas=sorted({s.name.lower() for s in rs.senses if s.name}),
                )
                for rs in (syn.ili or [])
            ]
            out.append(
                EnSynset(
                    pos=_EN_POS.get(pos_letter, "?"),
                    lemmas=sorted({s.name.replace("_", " ") for s in syn.senses}),
                    groups=groups,
                )
            )
        return out


from . import dsl as _dsl


def english_lemma_universe(db_path: Optional[str] = None) -> List[str]:
    """Every English lemma in the bundled EN subset (max-coverage headwords).

    The bundled subset holds only `ili`-linked synsets, so this universe is
    exactly the headwords the translation dictionary can cover. Default locates
    the installed `python-ruwordnet` sqlite (2021 db preferred).
    """
    import sqlite3

    if db_path is None:
        try:
            import ruwordnet as _pkg
        except ImportError as exc:
            raise RuntimeError(
                "EN lemma universe needs the `ruwordnet` package: "
                "`pip install ruwordnet && ruwordnet download`"
            ) from exc
        static = os.path.join(os.path.dirname(_pkg.__file__), "static")
        for cand in ("ruwordnet-2021.db", "ruwordnet.db"):
            if os.path.isfile(os.path.join(static, cand)):
                db_path = os.path.join(static, cand)
                break
        if db_path is None:
            raise RuntimeError("no RuWordNet sqlite found; run `ruwordnet download`")
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT DISTINCT name FROM wn_sense").fetchall()
    finally:
        con.close()
    return sorted({str(name).replace("_", " ") for (name,) in rows if name})


def to_cards(word: str, senses: Sequence[ResolvedSense]) -> List[_dsl.Card]:
    """Group resolved senses into one DSL card per part of speech.

    Senses arrive in POS order; each card numbers its senses from 1, which is
    the spec's per-POS numbering.
    """
    cards: List[_dsl.Card] = []
    current: List[ResolvedSense] = []
    current_pos = None
    for sense in senses:
        if sense.pos != current_pos and current:
            cards.append(_to_card(word, current_pos or "", current))
            current = []
        current_pos = sense.pos
        current.append(sense)
    if current or current_pos is not None:
        cards.append(_to_card(word, current_pos or "", current))
    if not cards:
        cards.append(_dsl.Card(headword=word))
    return cards


def _to_card(word: str, en_pos: str, senses: Sequence[ResolvedSense]) -> _dsl.Card:
    return _dsl.Card(
        headword=word,
        pos=russian_pos(en_pos),
        senses=[
            _dsl.Sense(
                definition=s.definition,
                equivalents=list(s.equivalents),
                synonyms=[s for s in s.synonyms if s.lower() != word.lower()],
            )
            for s in senses
        ],
    )


def resolve_word(word: str, backend: Optional[RuWordNetBackend] = None) -> List[ResolvedSense]:
    """Resolve one headword to card senses, grouped per RU synset."""
    backend = backend or RuWordNetBackend()
    senses: List[ResolvedSense] = []
    for syn in backend.en_synsets(word):
        if not syn.groups:
            senses.append(
                ResolvedSense(
                    pos=syn.pos,
                    definition="",
                    equivalents=[],
                    synonyms=syn.lemmas,
                    linked=False,
                )
            )
            continue
        for group in syn.groups:
            senses.append(
                ResolvedSense(
                    pos=syn.pos,
                    definition=_sense_definition(group),
                    equivalents=list(group.lemmas),
                    synonyms=syn.lemmas,
                    linked=True,
                )
            )
    senses.sort(key=lambda s: POS_ORDER.index(s.pos) if s.pos in POS_ORDER else 99)
    return senses


def resolve_words(
    words: Sequence[str], backend: Optional[RuWordNetBackend] = None
) -> Tuple[Dict[str, List[ResolvedSense]], ResolutionReport]:
    """Resolve headwords, counting coverage (unlinked senses included)."""
    backend = backend or RuWordNetBackend()
    report = ResolutionReport()
    cards: Dict[str, List[ResolvedSense]] = {}
    for word in words:
        report.words += 1
        synsets = backend.en_synsets(word)
        if not synsets:
            report.words_no_en += 1
            cards[word] = []
            continue
        report.synsets += len(synsets)
        report.synsets_linked += sum(1 for s in synsets if s.groups)
        cards[word] = []
        for syn in synsets:
            if not syn.groups:
                cards[word].append(
                    ResolvedSense(
                        pos=syn.pos, definition="", equivalents=[],
                        synonyms=syn.lemmas, linked=False,
                    )
                )
                continue
            for group in syn.groups:
                cards[word].append(
                    ResolvedSense(
                        pos=syn.pos,
                        definition=_sense_definition(group),
                        equivalents=list(group.lemmas),
                        synonyms=syn.lemmas,
                        linked=True,
                    )
                )
        cards[word].sort(
            key=lambda s: POS_ORDER.index(s.pos) if s.pos in POS_ORDER else 99
        )
    return cards, report
