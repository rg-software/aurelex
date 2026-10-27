"""Dict B example selection: Tatoeba acquisition + dedupe → rank → cap.

Acquisition joins per-language sentence files with the pre-joined per-pair
link file (no global dump needed)::

    eng_sentences.tsv.bz2   id<TAB>eng<TAB>text
    rus_sentences.tsv.bz2   id<TAB>rus<TAB>text
    jpn_sentences.tsv.bz2   id<TAB>jpn<TAB>text
    eng-rus_links.tsv.bz2   eng_id<TAB>rus_id
    eng-jpn_links.tsv.bz2   eng_id<TAB>jpn_id
    jpn-rus_links.tsv.bz2   jpn_id<TAB>rus_id

Selection per headword, decided in docs/BILINGUAL-EXPERIMENT.md: group pairs
by normalized source text and keep one target variant per group; rank
anchored-first (target side contains a Dict-A equivalent), then rarest
anchor, then shortest; length ranks, never filters. A sense with
no anchored pair falls back to an unanchored (concordance) pair.

The corpus is symmetric: both frequency counters and both inverted indexes
are built in the same acquisition pass, and :meth:`Corpus.flipped` swaps the
pair order so the reverse dictionary reuses every selection
function unchanged (matching, dedupe, ranking, case merge, hygiene rules).

Japanese matching is substring-based: Japanese text has no word spaces, so
there is no word-boundary regex and over-long examples split at Japanese
sentence punctuation (。、！？) as well as `.`.
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

    ``pairs`` are always (source, target) in build order. ``flipped()``
    returns the reverse view with the pair order, counters, indexes,
    tokenizer, and language tags swapped, so the selection machinery cannot
    tell which direction it serves. ``rus_freq`` is the target-side counter
    and ``eng_freq`` the source-side counter (historical names, kept for
    compatibility); ``index`` covers the source side, ``index_ru`` the
    target side. ``lang`` is the source language, ``tgt_lang`` the target.
    """

    pairs: List[Tuple[str, str]] = field(default_factory=list)
    rus_freq: Counter = field(default_factory=Counter)
    date: str = ""
    index: Dict[str, List[int]] = field(default_factory=dict)
    eng_freq: Counter = field(default_factory=Counter)
    index_ru: Dict[str, List[int]] = field(default_factory=dict)
    lang: str = "en"
    tgt_lang: str = "ru"

    def flipped(self) -> "Corpus":
        """Reverse view of this corpus (new object, shared date)."""
        return Corpus(
            pairs=[(tgt, src) for src, tgt in self.pairs],
            rus_freq=self.eng_freq,
            date=self.date,
            index=self.index_ru,
            eng_freq=self.rus_freq,
            index_ru=self.index,
            lang=self.tgt_lang,
            tgt_lang=self.lang,
        )


_WORD_RE = re.compile(r"[a-z0-9']+")
_RU_WORD_RE = re.compile(r"[а-яё0-9]+")
_TOKENIZERS = {"en": _WORD_RE, "ru": _RU_WORD_RE}


def _ja_chars(text: str) -> List[str]:
    """Unique characters of a Japanese text, for the inverted index."""
    return list(set(text))


def freq_for_lang(texts, lang: str) -> Counter:
    """Token frequencies for one side of the corpus, by language.

    English/Russian count word tokens. Japanese has no word tokens, so this
    counts individual characters — only a coarse fallback. The real
    Japanese-target signal is phrase containment (see :func:`count_phrases`),
    built from the resolved equivalents once they are known.
    Unknown languages fall back to a simple lowercase word split.
    """
    freq: Counter = Counter()
    if lang == "ja":
        for text in texts:
            freq.update(ch for ch in text if not ch.isspace())
        return freq
    if lang == "ru":
        for text in texts:
            freq.update(re.findall(r"[а-яё]+", text.lower()))
        return freq
    tok = _TOKENIZERS.get(lang, _WORD_RE)
    for text in texts:
        freq.update(tok.findall(text.lower()))
    return freq


def index_pairs(pairs: Sequence[Tuple[str, str]],
                lang: str = "en") -> Dict[str, List[int]]:
    """Inverted index over source-side text: token -> pair positions.

    Built once per build; without it a full dictionary pays a regex scan of
    all pairs per headword (~35k × 831k searches). Lookup stays exact: the
    index only narrows candidates, the match check still decides.
    ``lang`` selects the strategy: word tokens for `en`/`ru`, characters
    for `ja` (spaceless text has no word tokens to index).
    """
    index: Dict[str, List[int]] = {}
    if lang == "ja":
        for i, (src, _tgt) in enumerate(pairs):
            for ch in set(src):
                if ch.strip():
                    index.setdefault(ch, []).append(i)
        return index
    tok = _TOKENIZERS.get(lang, _WORD_RE)
    for i, (src, _tgt) in enumerate(pairs):
        for t in set(tok.findall(src.lower())):
            index.setdefault(t, []).append(i)
    return index


def pairs_for(word: str, corpus: Corpus) -> List[Tuple[str, str]]:
    """Candidate pairs for a headword, index hit then exact match.

    A word whose token never occurs in the corpus returns immediately
    instead of scanning all pairs; multi-token words scan only the smallest
    token list. The match check still decides every candidate: a
    word-boundary regex for `en`/`ru`, a plain substring for `ja`
    (spaceless text has no boundaries to assert). The match side follows
    the corpus view: on a flipped corpus the target side is searched.
    Single-character English and Russian headwords never match at all: in
    running text a one-letter token is overwhelmingly the article "a" (or a
    pronoun like "I" / "я"), so any hit would illustrate the article, not
    the headword ("Be a man" for the letter A = ampere). Japanese is
    exempt: a single kanji is a complete word (犬, 水, 本), and CJK matching
    is substring-based with no word boundaries — the same discipline as the
    monolingual converter. Such headwords keep their card but ship no
    examples.
    """
    if len(word) < 2 and corpus.lang != "ja":
        return []
    if corpus.lang == "ja":
        # Substring match; the char index only narrows candidates.
        chars = [ch for ch in set(word) if ch.strip()]
        if not chars:
            return []
        lists = []
        for ch in chars:
            hit = corpus.index.get(ch)
            if hit is None:
                return []
            lists.append(hit)
        cands = (corpus.pairs[i] for i in min(lists, key=len))
        return [p for p in cands if word in p[0]]
    pat = re.compile(r"(?<!\w)" + re.escape(word) + r"(?!\w)", re.I)
    tok = _TOKENIZERS.get(corpus.lang, _WORD_RE)
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
    """Load a ``src_id<TAB>tgt_id`` link file (plain or ``.bz2``)."""
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


def acquire(src_path: str, tgt_path: str, links_path: str, date: str,
            src_lang: str = "en", tgt_lang: str = "ru") -> Corpus:
    """Join sentences with links into (source, target) pairs, pinned to a date.

    The date is the operator-recorded weekly-export date (like the kaikki
    ``--dump-date``); it travels with the corpus into provenance.
    ``src_lang``/``tgt_lang`` select tokenizers, frequency counters, and
    indexes (``ja`` uses substring matching and a kana/kanji-run counter).
    Positional calls ``acquire(eng, rus, links, date)`` keep the old
    English→Russian meaning.
    """
    src_sentences = load_sentences(src_path)
    tgt_sentences = load_sentences(tgt_path)
    pairs = [
        (src_sentences[a], tgt_sentences[b])
        for a, b in load_links(links_path)
        if a in src_sentences and b in tgt_sentences
    ]
    tgt_freq = freq_for_lang(tgt_sentences.values(), tgt_lang)
    src_freq = freq_for_lang(src_sentences.values(), src_lang)
    by_src = index_pairs(pairs, lang=src_lang)
    by_tgt = index_pairs([(tgt, src) for src, tgt in pairs], lang=tgt_lang)
    return Corpus(pairs=pairs, rus_freq=tgt_freq, date=date, index=by_src,
                  eng_freq=src_freq, index_ru=by_tgt,
                  lang=src_lang, tgt_lang=tgt_lang)


def _normalize(text: str) -> str:
    # Grouping key for sentence dedupe: case- and whitespace-insensitive like
    # before, and now punctuation-insensitive too, so "Give me water!" and
    # "Give me water." (or "水をくれ。" vs "水をくれ！") collapse into one
    # group instead of shipping twice. The kept representative still carries
    # its own original punctuation; only the key is normalized.
    lowered = " ".join(text.split()).lower()
    return " ".join(re.sub(r"[^\w\s]", "", lowered).split())


def _compile(equivalents: Sequence[str],
               target_lang: str = "ru") -> List[Tuple[str, "re.Pattern"]]:
    if target_lang == "ja":
        # Spaceless text: no word boundaries, plain substring patterns.
        return [(e, re.compile(re.escape(e))) for e in equivalents]
    return [(e, re.compile(r"(?<!\w)" + re.escape(e) + r"(?!\w)")) for e in equivalents]


def count_phrases(phrases: Sequence[str], corpus: Corpus) -> Counter:
    """Sentence counts per phrase on the corpus target side.

    The Japanese-target frequency signal, where word tokens don't exist:
    how many target sentences contain the phrase. Candidates narrow through
    the target-side inverted index (a character index for Japanese), so the
    cost is one short posting-list walk per phrase instead of a corpus scan.
    """
    import sys as _sys

    counts: Counter = Counter()
    tgts = [tgt for _, tgt in corpus.pairs]
    index = corpus.index_ru or {}
    total = len(phrases)
    for n, phrase in enumerate(phrases, 1):
        if n == 1 or n % 20000 == 0:
            print(f"counting phrases: {n:,}/{total:,}", file=_sys.stderr)
        if not phrase:
            counts[phrase] = 0
            continue
        lists = [index[ch] for ch in set(phrase) if ch in index]
        if not lists:
            counts[phrase] = 0
            continue
        cands = set(lists[0])
        for lst in lists[1:]:
            cands.intersection_update(lst)
            if not cands:
                break
        counts[phrase] = sum(1 for i in cands if phrase in tgts[i])
    return counts


def _rarity(equivalent: str, rus_freq: Counter) -> int:
    return rus_freq.get(equivalent.split()[0].lower(), 1)


def rank_variants(
    variants: Sequence[str],
    equivalents: Sequence[str],
    rus_freq: Counter,
    target_lang: str = "ru",
) -> Optional[str]:
    """Pick one target variant: anchored first, rarest anchor wins.

    An anchored variant contains a Dict-A equivalent (whole-word for `en`/
    `ru`, substring for `ja`, so ``давать`` never matches inside
    ``сдаваться``). Rarity prefers distinctive equivalents (``посвятить``)
    over ubiquitous verbs (``уйти``). Unanchored variants lose to any
    anchored one; the shortest wins among themselves.
    """
    pats = _compile([e.lower() if target_lang != "ja" else e for e in equivalents],
                    target_lang)
    anchored = []
    for variant in variants:
        lowered = variant if target_lang == "ja" else variant.lower()
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
    target_lang: str = "ru",
) -> List[Tuple[str, str]]:
    """Dedupe → rank → cap one headword's pairs.

    Groups by normalized source text (one target variant per group via
    :func:`rank_variants`), then keeps the best ``keep`` groups:
    anchored-first, rarest anchor, shortest source text. A group whose
    chosen translation duplicates an already-kept one is skipped, so two
    near-identical source sentences sharing one translation (``Я купил
    хлеб.`` / ``Я купила хлеб.`` → ``パン買ったよ。``) ship once and leave
    room for a different pair. No length filter — a headword with only
    long pairs still ships its best.
    """
    by_src: Dict[str, List[str]] = {}
    first_src: Dict[str, str] = {}
    for src, tgt in pairs:
        norm = _normalize(src)
        if norm not in by_src:
            by_src[norm] = []
            first_src[norm] = src
        by_src[norm].append(tgt)
    order = list(by_src)
    pats = _compile([e.lower() if target_lang != "ja" else e for e in equivalents],
                    target_lang)
    ranked = []
    for norm in order:
        variant = rank_variants(by_src[norm], equivalents, rus_freq, target_lang)
        if variant is None:
            continue
        src_text = first_src[norm]
        lowered = variant if target_lang == "ja" else variant.lower()
        anchors = [e for e, p in pats if p.search(lowered)]
        score = min([_rarity(e, rus_freq) for e in anchors], default=None)
        ranked.append(((score is None, score or 0, len(src_text)), src_text, variant))
    ranked.sort(key=lambda item: item[0])
    if keep <= 0:
        return []
    out: List[Tuple[str, str]] = []
    seen_tgt = set()
    for _, src_text, variant in ranked:
        if _normalize(variant) in seen_tgt:
            continue
        seen_tgt.add(_normalize(variant))
        out.append((src_text, variant))
        if len(out) >= keep:
            break
    return out


def _best_anchor(
    sense_equivalents: Sequence[str],
    headword_pairs: Sequence[Tuple[str, str]],
    rus_freq: Counter,
    target_lang: str = "ru",
    exclude: Sequence[Tuple[str, str]] = (),
) -> Optional[Tuple[str, str]]:
    """Best anchored pair for a sense, or None when nothing anchors.

    Pure anchor search with no fallback: the card-wide reservation pass
    uses this so an anchor-less sense's fallback can never steal a pair
    that anchors a later sense. Pairs sharing a normalized source or
    translation with ``exclude`` are skipped — no pair, source sentence,
    or translation repeats within a card.
    """
    used_src = {_normalize(src) for src, _ in exclude}
    used_tgt = {_normalize(tgt) for _, tgt in exclude}
    pats = _compile([e.lower() if target_lang != "ja" else e for e in sense_equivalents],
                    target_lang)
    anchored = []
    for src, tgt in headword_pairs:
        if _normalize(src) in used_src or _normalize(tgt) in used_tgt:
            continue
        lowered = tgt if target_lang == "ja" else tgt.lower()
        matched = [e for e, p in pats if p.search(lowered)]
        if matched:
            anchored.append(
                (min(_rarity(e, rus_freq) for e in matched), len(src), src, tgt)
            )
    if not anchored:
        return None
    _, _, src, tgt = min(anchored)
    return (src, tgt)


def best_anchor(
    sense_equivalents: Sequence[str],
    headword_pairs: Sequence[Tuple[str, str]],
    rus_freq: Counter,
    target_lang: str = "ru",
    exclude: Sequence[Tuple[str, str]] = (),
) -> Optional[Tuple[str, str]]:
    """Best anchored pair for a sense, or None (public alias)."""
    return _best_anchor(sense_equivalents, headword_pairs, rus_freq,
                        target_lang, exclude)


def concordance_fallback(
    headword_pairs: Sequence[Tuple[str, str]],
    exclude: Sequence[Tuple[str, str]] = (),
) -> Optional[Tuple[str, str]]:
    """Shortest pair sharing no source or translation with ``exclude``.

    The concordance backstop for anchor-less senses: still bilingual (the
    source side matched the headword), never a kaikki English-only example.
    Returns None when every candidate repeats an already-used source or
    translation.
    """
    used_src = {_normalize(src) for src, _ in exclude}
    used_tgt = {_normalize(tgt) for _, tgt in exclude}
    rest = [p for p in headword_pairs
            if _normalize(p[0]) not in used_src and _normalize(p[1]) not in used_tgt]
    if not rest:
        return None
    return min(rest, key=lambda p: len(p[0]))


def select_for_sense(
    sense_equivalents: Sequence[str],
    headword_pairs: Sequence[Tuple[str, str]],
    rus_freq: Counter,
    target_lang: str = "ru",
    exclude: Sequence[Tuple[str, str]] = (),
) -> Optional[Tuple[str, str]]:
    """Keep at most one pair for a sense, else fall back to concordance.

    ``headword_pairs`` are this headword's pairs (already matched on the
    source side). The best anchored pair wins; with none anchored, the
    shortest pair ships so the sense is still illustrated — still
    bilingual, never a kaikki English-only example. The anchor always
    checks the target side (tuple position 1), so flipped corpora need no
    code change; ``target_lang`` switches whole-word (`ru`/`en`) vs
    substring (`ja`) matching. Nothing in ``exclude`` (already shown under
    an earlier sense of the same card) is ever reused — neither the pair,
    nor its source sentence, nor its translation: repeating one pair under
    several senses illustrates nothing. A sense with no unused candidate
    at all carries no example.
    """
    if not headword_pairs:
        return None
    anchor = _best_anchor(sense_equivalents, headword_pairs, rus_freq,
                          target_lang, exclude)
    if anchor is not None:
        return anchor
    return concordance_fallback(headword_pairs, exclude)
