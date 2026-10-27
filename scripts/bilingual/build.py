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
from typing import Dict, List, Optional, Sequence, Set, Tuple

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
    Scripts without case (Japanese kana/kanji): the first sorted form stands.
    """
    if len(forms) == 1:
        only = forms[0]
        if only == key:
            return only
    if not re.search(r"[A-Za-zА-Яа-яЁё]", key):
        return sorted(forms)[0]
    pat = re.compile(r"(?<!\w)" + re.escape(key) + r"(?!\w)")
    if any(pat.search(en) for en, _ in pairs):
        return key
    return sorted(forms)[0]


def _with_reading_aliases(cards: List[_dsl.Card],
                           keys_by_word: Dict[str, List[str]]) -> List[_dsl.Card]:
    """Duplicate cards under hiragana reading headwords (opt-in).

    Each alias carries the primary card whole — equivalents, examples,
    audio, transcription, readings — and opens with the primary headword
    as its title, so a lookup that arrives through a reading knows which
    word it defines. A reading that collides with a real headword (or an
    earlier alias) stays with the first card; aliases never steal names.
    """
    taken = {c.headword for c in cards}
    out = list(cards)
    for card in cards:
        for key in keys_by_word.get(card.headword, []):
            if not key or key in taken:
                continue
            taken.add(key)
            out.append(_dsl.Card(
                headword=key,
                title=card.headword,
                pos=card.pos,
                transcription=card.transcription,
                senses=list(card.senses),
                audio=list(card.audio),
                comments=list(card.comments),
                pairs=list(card.pairs),
                readings=card.readings,
            ))
    return out


# Kana/kanji runs: a Japanese headword containing any of these is a
# native spelling even when it starts with a digit (10月, 10代).
_JA_LETTER_RE = re.compile(r"[ぁ-んァ-ン一-鿿々〆]")


def headword_ok(word: str, src_lang: str) -> bool:
    """Whether a candidate headword is kept (shared hygiene rule).

    A headword must start with a Unicode letter — except Japanese, where
    native spellings routinely start with a digit (10月, 10代): those are
    kept as long as they contain kana or kanji. Pure numbers and stray
    punctuation are dropped everywhere.
    """
    if not word:
        return False
    if word[0].isalpha():
        return True
    return src_lang == "ja" and bool(_JA_LETTER_RE.search(word))


def _pair_langs(direction: str) -> Dict[str, str]:
    """DSL header languages for a build direction, as `package.build` kwargs."""
    names = {"en": "English", "ru": "Russian", "ja": "Japanese"}
    try:
        src, tgt = direction.split("-", 1)
    except ValueError:
        return {"index_lang": "English", "contents_lang": "Russian"}
    return {"index_lang": names.get(src, src), "contents_lang": names.get(tgt, tgt)}


def _pos_for_direction(en_pos: str, direction: str) -> str:
    """Target-language POS label for an English POS value."""
    tgt = direction.split("-", 1)[-1] if "-" in direction else "ru"
    if tgt == "en":
        return en_pos
    if tgt == "ja":
        return _eq.japanese_pos(en_pos)
    return _eq.russian_pos(en_pos)


def build_pairs(
    words: Sequence[str],
    out_dir: str,
    name: str,
    title: Optional[str] = None,
    sources: Optional[_prov.Sources] = None,
    corpus: Optional[_tat.Corpus] = None,
    keep: int = 3,
    direction: str = "en-ru",
    snapshot_path: Optional[str] = None,
    index_readings: bool = False,
) -> Dict[str, object]:
    """Build the sentence-example dictionary: headword → kept pairs, no senses.

    Pure concordance ranking (no equivalents to anchor on): dedupe by
    normalized source text, shortest first, keep N per headword. No audio.
    With ``index_readings`` (Japanese sources only), each card is also
    indexed under its hiragana readings (needs ``snapshot_path``).
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
        if not headword_ok(word, direction.split("-", 1)[0]):
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
        kept = _tat.select(headword_pairs, (), corpus.rus_freq, keep=keep,
                           target_lang=getattr(corpus, "tgt_lang", "ru"))
        if not kept:
            skipped += 1
            continue
        cards.append(_dsl.Card(headword=_choose_case(key, by_lower[key], headword_pairs),
                               pairs=list(kept)))
    print(f"pairs dictionary: {len(cards):,} cards, {skipped:,} without pairs "
          f"and {skipped_shape:,} ill-shaped headwords skipped", file=sys.stderr)

    if index_readings:
        if snapshot_path is None:
            raise ValueError("reading indexing needs --snapshot")
        keys = _audio.reading_keys(
            [c.headword for c in cards], snapshot_path,
            lang=direction.split("-", 1)[0])
        cards = _with_reading_aliases(cards, keys)

    about = _prov.about_card(shown, sources, len(cards))
    dz_path, _text = _package.build(cards, out_dir, name, shown, about=about,
                                    **_pair_langs(direction))

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
    direction: str = "en-ru",
    audio_lang_code: str = "en",
    index_readings: bool = False,
) -> Dict[str, object]:
    """Build one import-ready sample pair; return a summary for verification."""
    shown = title or name
    sources = sources or _prov.Sources()

    # Headword hygiene, same rule as the pairs dictionary: a headword must
    # start with a Unicode letter — except Japanese, where native spellings
    # routinely start with a digit (10月, 10代). Those are kept as long as
    # they contain kana or kanji; pure numbers are dropped everywhere.
    # Dropped before resolution so they cost no thesaurus lookups and
    # never enter the resolve cache.
    src_lang = direction.split("-", 1)[0] if "-" in direction else "en"
    clean_words: List[str] = []
    skipped_shape = 0
    for _w in words:
        if not headword_ok(_w, src_lang):
            skipped_shape += 1
            continue
        clean_words.append(_w)
    words = clean_words
    if skipped_shape:
        print(f"skipped {skipped_shape:,} ill-shaped headwords", file=sys.stderr)

    cache_id = None
    if resolve_cache is not None and backend is None:
        try:
            cache_id = _eq._default_backend(direction).db_identity()  # noqa: SLF001
        except RuntimeError:
            cache_id = None

    def _progress(done: int, total: int) -> None:
        print(f"resolving equivalents: {done:,}/{total:,}", file=sys.stderr)

    resolved, eq_report = _eq.resolve_words(
        words, backend, progress=_progress,
        cache_path=resolve_cache, cache_id=cache_id,
        direction=direction,
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
    if corpus is not None and getattr(corpus, "tgt_lang", "ru") == "ja":
        # Phrase counts for every equivalent in play (posting-list
        # narrowed, memoized per phrase): ranking and anchor rarity.
        uniq: Set[str] = set()
        for _senses in resolved.values():
            for _sense in _senses:
                uniq.update(_sense.equivalents)
        print(f"counting examples: {len(uniq):,} phrases", file=sys.stderr)
        rus_freq = _tat.count_phrases(sorted(uniq), corpus)
    for word in words:
        senses = resolved.get(word, [])
        dsl_senses = []
        # Pass 1 (card-wide reservation): every sense's anchored pick is
        # claimed up front in sense order, skipping anything already
        # claimed, so an anchor-less sense's fallback can never steal a
        # pair that anchors a later sense — and no pair, source, or
        # translation ever repeats within a card.
        # A sense with neither equivalents nor a definition is a numbered
        # shell: the unlinked shells the reviews rejected. It stays counted
        # in coverage (resolve-level) but renders nothing — not even its
        # concordance example or untranslatable synonyms.
        renderable = [s for s in senses
                      if s.equivalents or s.definition]
        used_pairs: List[Tuple[str, str]] = []
        reserved: List[Optional[Tuple[str, str]]] = [None] * len(renderable)
        if corpus is not None:
            tgt = getattr(corpus, "tgt_lang", "ru")
            for i, sense in enumerate(renderable):
                anchor = _tat.best_anchor(
                    sense.equivalents, word_pairs.get(word, []), rus_freq,
                    target_lang=tgt, exclude=used_pairs,
                )
                reserved[i] = anchor
                if anchor is not None:
                    used_pairs.append(anchor)
        for sense, reserved_anchor in zip(renderable, reserved):
            example = None
            equivalents = list(sense.equivalents)
            if corpus is not None:
                if reserved_anchor is not None:
                    example = reserved_anchor
                else:
                    example = _tat.concordance_fallback(
                        word_pairs.get(word, []), exclude=used_pairs)
                if example is not None and example not in used_pairs:
                    used_pairs.append(example)
                # Rank only where we have a frequency signal; otherwise keep
                # the RuWordNet member order untouched.
                equivalents = _eq.rank_equivalents(
                    equivalents, rus_freq,
                    target_lang=getattr(corpus, "tgt_lang", "ru"))
            dsl_senses.append(
                _dsl.Sense(
                    definition=sense.definition,
                    equivalents=equivalents,
                    synonyms=[s for s in sense.synonyms if s.lower() != word.lower()],
                    example=example,
                    # POS labels are the target language's (English for
                    # *-en, Russian for *-ru, Japanese for *-ja).
                    pos=_pos_for_direction(sense.pos, direction),
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
        print(f"planning audio: {len(cards):,} cards", file=sys.stderr)
        # Plan audio only for headwords that survived resolution: a skipped
        # headword has no card, so its recordings would ride the bundle as
        # dead weight (audio bundles are hundreds of megabytes).
        card_words = [c.headword for c in cards]
        names_by_word, planner = _audio.plan_words(
            card_words, snapshot_path,
            per_word=per_word_audio, audio_lang=audio_lang,
            enabled=audio_enabled, archive_path=archive_path,
            download_dir=download_dir, lang=audio_lang_code,
        )
        cards = _audio.attach_audio(cards, names_by_word)
        # Transcription rides the same snapshot scan (memoized: no second
        # pass) and is independent of the audio switch — a silent card
        # keeps its text.
        transcriptions = _audio.transcribe_words(
            card_words, snapshot_path, lang=audio_lang_code)
        for card in cards:
            if card.headword in transcriptions:
                card.transcription = transcriptions[card.headword]
        # Readings ride the same memoized scan; only a profile declaring
        # readings (Japanese) ever yields a line.
        readings = _audio.reading_lines(
            card_words, snapshot_path, lang=audio_lang_code)
        for card in cards:
            if card.headword in readings:
                card.readings = readings[card.headword]
        if index_readings:
            print(f"indexing readings: {len(cards):,} cards", file=sys.stderr)
            cards = _with_reading_aliases(
                cards,
                _audio.reading_keys(
                    card_words, snapshot_path, lang=audio_lang_code),
            )

    about = _prov.about_card(shown, sources, len(cards))
    dz_path, _text = _package.build(cards, out_dir, name, shown, about=about,
                                    **_pair_langs(direction))

    bundle_path = None
    if planner is not None:
        bundle_path = _audio.bundle_for(planner, dz_path, "zip", archive_path)

    ann_path = os.path.join(out_dir, f"{name}.ann")
    _prov.write_annotation(ann_path, shown, sources, len(cards))

    print(f"verifying {len(cards):,} cards", file=sys.stderr)
    check = _audio.verify(dz_path, bundle_path)
    return {
        "dz_path": dz_path,
        "bundle_path": bundle_path,
        "ann_path": ann_path,
        "cards": len(cards),
        "cards_out": cards,
        "skipped_empty": skipped_empty,
        "skipped_shape": skipped_shape,
        "synsets": eq_report.synsets,
        "synsets_linked": eq_report.synsets_linked,
        "unresolved": check["unresolved"],
        "audio_refs": check["audio"],
    }
