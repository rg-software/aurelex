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
import re
import sys
from typing import Dict, List, Optional, Sequence

from . import audio as _audio
from . import dsl as _dsl
from . import equivalents as _eq
from . import package as _package
from . import provenance as _prov
from . import tatoeba as _tat


def _choose_case(key: str, forms: Sequence[str],
                 pairs: Sequence[Tuple[str, str]]) -> str:
    """Pick one headword per case-variant group.

    Your own heuristic: look at how the card body spells it. The lowercase
    form wins when it occurs as a whole word in the group's own pairs
    (common noun used lowercase somewhere, even mid-sentence); otherwise the
    capitalized form stands (proper names like Sisyphus never occur
    lowercase). Single-form groups keep their form. Deterministic.
    """
    if len(forms) == 1:
        only = forms[0]
        if only == key:
            return only
    pat = re.compile(r"(?<!\w)" + re.escape(key) + r"(?!\w)")
    if any(pat.search(en) for en, _ in pairs):
        return key
    return sorted(forms)[0]


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
    skipped = 0
    skipped_shape = 0
    by_lower: Dict[str, List[str]] = {}
    for word in words:
        if not word or not word[0].isalpha():
            skipped_shape += 1
            continue
        by_lower.setdefault(word.lower(), []).append(word)
    print(f"pairs dictionary: {len(by_lower):,} case-folded headwords to check",
          file=sys.stderr)
    n = 0
    for key in sorted(by_lower):
        n += 1
        if n % 50000 == 0:
            print(f"pairs selected: {n:,}/{len(by_lower):,}", file=sys.stderr)
        headword_pairs = _tat.pairs_for(key, corpus)
        kept = _tat.select(headword_pairs, (), corpus.rus_freq, keep=keep)
        if not kept:
            skipped += 1
            continue
        cards.append(_dsl.Card(headword=_choose_case(key, by_lower[key], headword_pairs),
                               pairs=list(kept)))
    print(f"pairs dictionary: {len(cards):,} cards, {skipped:,} without pairs "
          f"and {skipped_shape:,} ill-shaped headwords skipped", file=sys.stderr)

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
        "skipped_empty": skipped,
        "skipped_shape": skipped_shape,
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
    resolve_cache: Optional[str] = None,
) -> Dict[str, object]:
    """Build one import-ready sample pair; return a summary for verification."""
    shown = title or name
    sources = sources or _prov.Sources()

    cache_id = None
    if resolve_cache is not None and backend is None:
        try:
            db_path = _eq._ruwordnet_db_path()  # noqa: SLF001
            st = os.stat(db_path)
            cache_id = f"{db_path}|{st.st_size}|{int(st.st_mtime)}"
        except (RuntimeError, OSError):
            cache_id = None

    def _progress(done: int, total: int) -> None:
        print(f"resolving equivalents: {done:,}/{total:,}", file=sys.stderr)

    resolved, eq_report = _eq.resolve_words(
        words, backend, progress=_progress,
        cache_path=resolve_cache, cache_id=cache_id,
    )
    print(f"resolved {eq_report.synsets_linked:,}/{eq_report.synsets:,} synsets linked",
          file=sys.stderr)
    print(f"indexing examples: {len(words):,} headwords", file=sys.stderr)
    word_pairs: Dict[str, List] = {}
    if corpus is not None:
        for n, word in enumerate(words, 1):
            word_pairs[word] = _tat.pairs_for(word, corpus)
            if n % 5000 == 0:
                print(f"examples indexed: {n:,}/{len(words):,}", file=sys.stderr)

    cards: List[_dsl.Card] = []
    skipped_empty = 0
    rus_freq = corpus.rus_freq if corpus is not None else {}
    for word in words:
        senses = resolved.get(word, [])
        dsl_senses = []
        for sense in senses:
            example = None
            equivalents = list(sense.equivalents)
            if corpus is not None:
                example = _tat.select_for_sense(
                    sense.equivalents, word_pairs.get(word, []), corpus.rus_freq
                )
                # Rank only where we have a frequency signal; otherwise keep
                # the RuWordNet member order untouched.
                equivalents = _eq.rank_equivalents(equivalents, rus_freq)
            dsl_senses.append(
                _dsl.Sense(
                    definition=sense.definition,
                    equivalents=equivalents,
                    synonyms=[s for s in sense.synonyms if s.lower() != word.lower()],
                    example=example,
                    pos=_eq.russian_pos(sense.pos),
                )
            )
        # One card per headword; POS sections and per-POS numbering happen in
        # dsl.emit_card. Headwords with no senses at all get no card: an empty
        # headword entry is exactly the vacuous article the reviews rejected.
        if dsl_senses:
            cards.append(_dsl.Card(headword=word, senses=dsl_senses))
        else:
            skipped_empty += 1
    if skipped_empty:
        print(f"skipped {skipped_empty:,} headwords with no senses", file=sys.stderr)

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
        "skipped_empty": skipped_empty,
        "synsets": eq_report.synsets,
        "synsets_linked": eq_report.synsets_linked,
        "unresolved": check["unresolved"],
        "audio_refs": check["audio"],
    }
