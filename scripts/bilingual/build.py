"""End-to-end bilingual sample build: equivalents + examples + audio + provenance.

Thin assembly over the source modules — no new decisions here, only the
plumbing the spec's packaging and provenance requirements need:

1. resolve headwords (PWN → ``ili`` → RuWordNet),
2. select one anchored example per sense (Tatoeba),
3. plan + bundle kaikki EN audio verbatim,
4. write ``.dsl.dz`` + sibling bundle + ``.ann`` and verify references.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

from . import audio as _audio
from . import dsl as _dsl
from . import equivalents as _eq
from . import package as _package
from . import provenance as _prov
from . import tatoeba as _tat


def build_pairs(
    words: Sequence[str],
    out_dir: str,
    name: str,
    title: Optional[str] = None,
    sources: Optional[_prov.Sources] = None,
    corpus: Optional[_tat.Corpus] = None,
    keep: int = 3,
) -> Dict[str, object]:
    """Build the sentence-example dictionary: headword → kept pairs, no senses.

    Pure concordance ranking (no equivalents to anchor on): dedupe by
    normalized English text, shortest first, keep N per headword. No audio.
    """
    shown = title or name
    sources = sources or _prov.Sources(equivalents=False)
    sources.equivalents = False
    corpus = corpus or _tat.Corpus()

    cards: List[_dsl.Card] = []
    for word in words:
        pat = _tat.re.compile(r"(?<!\w)" + _tat.re.escape(word) + r"(?!\w)", _tat.re.I)
        headword_pairs = [(en, ru) for en, ru in corpus.pairs if pat.search(en)]
        kept = _tat.select(headword_pairs, (), corpus.rus_freq, keep=keep)
        cards.append(_dsl.Card(headword=word, pairs=list(kept)))

    about = _prov.about_card(shown, sources, len(cards))
    dz_path, _text = _package.build(cards, out_dir, name, shown, about=about)

    ann_path = os.path.join(out_dir, f"{name}.ann")
    _prov.write_annotation(ann_path, shown, sources, len(cards))

    check = _audio.verify(dz_path, None)
    return {
        "dz_path": dz_path,
        "bundle_path": None,
        "ann_path": ann_path,
        "cards": len(cards),
        "cards_out": cards,
        "synsets": 0,
        "synsets_linked": 0,
        "unresolved": check["unresolved"],
        "audio_refs": [],
    }


def build_sample(
    words: Sequence[str],
    out_dir: str,
    name: str,
    title: Optional[str] = None,
    sources: Optional[_prov.Sources] = None,
    snapshot_path: Optional[str] = None,
    corpus: Optional[_tat.Corpus] = None,
    archive_path: Optional[str] = None,
    download_dir: Optional[str] = None,
    per_word_audio: int = 3,
    audio_lang: Optional[str] = None,
    audio_enabled: bool = True,
    backend=None,
) -> Dict[str, object]:
    """Build one import-ready sample pair; return a summary for verification."""
    shown = title or name
    sources = sources or _prov.Sources()

    resolved, eq_report = _eq.resolve_words(words, backend)
    word_pairs: Dict[str, List] = {}
    if corpus is not None:
        for word in words:
            pat = _tat.re.compile(r"(?<!\w)" + _tat.re.escape(word) + r"(?!\w)", _tat.re.I)
            word_pairs[word] = [(en, ru) for en, ru in corpus.pairs if pat.search(en)]

    cards: List[_dsl.Card] = []
    for word in words:
        senses = resolved.get(word, [])
        dsl_senses = []
        for sense in senses:
            example = None
            if corpus is not None:
                example = _tat.select_for_sense(
                    sense.equivalents, word_pairs.get(word, []), corpus.rus_freq
                )
            dsl_senses.append(
                _dsl.Sense(
                    definition=sense.definition,
                    equivalents=list(sense.equivalents),
                    synonyms=[s for s in sense.synonyms if s.lower() != word.lower()],
                    example=example,
                )
            )
        groups: Dict[str, List[_dsl.Sense]] = {}
        order: List[str] = []
        for sense, raw in zip(dsl_senses, senses):
            if raw.pos not in groups:
                groups[raw.pos] = []
                order.append(raw.pos)
            groups[raw.pos].append(sense)
        for pos in order:
            cards.append(
                _dsl.Card(
                    headword=word,
                    pos=_eq.russian_pos(pos),
                    senses=groups[pos],
                )
            )

    names_by_word: Dict[str, List[str]] = {w: [] for w in words}
    planner = None
    if snapshot_path is not None:
        names_by_word, planner = _audio.plan_words(
            list(words), snapshot_path,
            per_word=per_word_audio, audio_lang=audio_lang,
            enabled=audio_enabled, archive_path=archive_path,
            download_dir=download_dir,
        )
        cards = _audio.attach_audio(cards, names_by_word)

    about = _prov.about_card(shown, sources, len(cards))
    dz_path, _text = _package.build(cards, out_dir, name, shown, about=about)

    bundle_path = None
    if planner is not None:
        bundle_path = _audio.bundle_for(planner, dz_path, "zip", archive_path)

    ann_path = os.path.join(out_dir, f"{name}.ann")
    _prov.write_annotation(ann_path, shown, sources, len(cards))

    check = _audio.verify(dz_path, bundle_path)
    return {
        "dz_path": dz_path,
        "bundle_path": bundle_path,
        "ann_path": ann_path,
        "cards": len(cards),
        "cards_out": cards,
        "synsets": eq_report.synsets,
        "synsets_linked": eq_report.synsets_linked,
        "unresolved": check["unresolved"],
        "audio_refs": check["audio"],
    }
