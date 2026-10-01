"""Rendering records into DSL cards"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .audio import AudioPlan
from .dsltext import _USAGE_TAGS, _audio_ref, _link_form_targets, _sense_markers, _strip_relation_prefix, _unescape_dsl, escape_dsl
from .profiles import LangProfile, collect_profile_forms, collect_profile_readings
from .source import _NOTATION_MISMATCH_TAGS, _PRON_LABEL, _UNLABELLED_PRON_FIELDS


class Report:
    def __init__(self) -> None:
        self.kept_records = 0
        self.cards = 0
        self.skipped_malformed = 0
        self.skipped_nonlexical = 0
        self.skipped_inflected = 0
        self.out_of_pair = 0
        self.missing_audio = 0
        self.audio_found = 0
        self.audio_cached = 0
        self.merged_headwords = 0   # headwords merged from non-adjacent records
        self.dropped_cards = 0      # definition-less cards omitted
        self.unlinked_refs = 0      # links left as plain text (target absent)

    def summary(self) -> str:
        return (
            f"headword cards: {self.cards}\n"
            f"source records kept: {self.kept_records}\n"
            f"malformed records skipped: {self.skipped_malformed}\n"
            f"non-lexical records skipped: {self.skipped_nonlexical}\n"
            f"inflected records not indexed: {self.skipped_inflected}\n"
            f"headwords merged from split records: {self.merged_headwords}\n"
            f"cards omitted for having no definition: {self.dropped_cards}\n"
            f"references left unlinked (target absent): {self.unlinked_refs}\n"
            f"audio files bundled: {self.audio_found}\n"
            f"audio files from cache: {self.audio_cached}\n"
            f"audio files referenced but missing: {self.missing_audio}"
        )

_LEADING_ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+")

def _cross_refs(record: dict, known: Set[str], limit: int = 12) -> List[str]:
    """Cross-reference words that are themselves indexed headwords (no dead links)."""
    word = str(record.get("word") or "")
    refs: List[str] = []
    for field in ("synonyms", "related"):
        for item in record.get(field) or []:
            target = item.get("word") if isinstance(item, dict) else item
            if not target:
                continue
            target = str(target)
            if target != word and target in known and target not in refs:
                refs.append(target)
            if len(refs) >= limit:
                return refs
    return refs

#: A card-level link to another headword. The captured text is DSL-escaped.
_CROSS_REF_RE = re.compile(r"\[ref\](.*?)\[/ref\]")

def unlink_absent_refs(body: str, present: Set[str]) -> Tuple[str, int]:
    """Turn any ``[ref]X[/ref]`` whose target is not emitted back into plain ``X``.

    ``known`` holds every candidate headword, but a candidate can render no card
    at all; a link to such a headword would be dead. Returns the body and how
    many links were unlinked. A malformed nested link (``[ref][ref]X[/ref][/ref]``)
    is peeled one layer per pass until only plain text remains.
    """
    unlinked = 0
    while True:
        def replace(match: "re.Match[str]") -> str:
            nonlocal unlinked
            if _unescape_dsl(match.group(1)) in present:
                return match.group(0)
            unlinked += 1
            return match.group(1)

        new_body = _CROSS_REF_RE.sub(replace, body)
        if new_body == body:
            return body, unlinked
        body = new_body

# A rendered sense, the raw examples that illustrate it, and whether the sense's
# own usage (obsolete/dated/archaic) lets an archaic example stand in when no
# readable one qualifies. ``text`` is the gloss line; ``examples`` are the source
# lines, still unfiltered.
SenseEntry = Tuple[str, List[str], bool]

def _extract_examples(sense: dict) -> List[str]:
    """The raw example sentences recorded on one sense."""
    out: List[str] = []
    for example in sense.get("examples") or []:
        if isinstance(example, dict):
            text = example.get("text") or example.get("english") or ""
        else:
            text = str(example)
        text = str(text).strip()
        if text:
            out.append(text)
    return out

def _group_senses(
    senses: Sequence[dict],
    profile: LangProfile,
    known: Optional[Set[str]] = None,
    word: str = "",
) -> List[Tuple[str, List[SenseEntry]]]:
    """Group rendered senses by a shared leading gloss fragment.

    wiktextract splits a Wiktionary definition on ``:`` into a parent phrase
    plus the specific part. Senses that share a parent become one group: the
    parent is rendered once as the heading and each specific part beneath it as
    a child, so ``monkey``'s seven figurative uses do not reprint the parent
    seven times. A sense whose gloss is a single fragment is its own group with
    heading "".

    Groups merge by parent in first-seen order, and a heading or child already
    emitted is dropped — Wiktionary repeats definitions verbatim across
    sub-senses, and printing a repeat says nothing new.

    Each entry carries the examples recorded on the sense it came from, so the
    renderer can keep an example beside the use it illustrates.

    Returns ``(heading, entries)`` pairs.
    """
    groups: Dict[str, List[SenseEntry]] = {}    # heading -> child entries
    # (kind, text, group key, examples, allow_archaic). A group's key is the
    # *raw* parent gloss, which render() may alter (it trims and collapses
    # whitespace, escapes markup, drops a relation prefix, wraps a form-of target
    # in [ref]); the key travels beside the rendered heading so the children can
    # be looked up by the string they were stored under.
    items: List[Tuple[str, str, str, List[str], bool]] = []
    seen: Set[str] = set()

    def fresh(text: str) -> bool:
        key = text.casefold().strip()
        if not key or key in seen:
            return False
        seen.add(key)
        return True

    for sense in senses:
        if not isinstance(sense, dict):
            continue
        parts = [str(g) for g in (sense.get("glosses") or []) if g]
        if not parts:
            continue
        markers = _sense_markers(sense.get("tags"), profile)
        examples = _extract_examples(sense)
        # An archaic/obsolete/dated sense may show an archaic example rather than
        # none; a modern sense may not.
        allow_archaic = bool(_USAGE_TAGS & {str(t) for t in (sense.get("tags") or [])})

        def render(part: str) -> str:
            # drop the relation phrase the icon already conveys, escape the free
            # text, then link the headword a form-of or alt-of sense names
            part = _strip_relation_prefix(part, sense.get("tags"))
            return _link_form_targets(escape_dsl(part), sense, known, word)

        if len(parts) == 1:
            if fresh(parts[0]):
                items.append(("plain", markers + render(parts[0]), "", examples, allow_archaic))
            continue
        parent, children = parts[0], parts[1:]
        if parent not in groups:
            if not fresh(parent):
                continue
            groups[parent] = []
            items.append(("group", render(parent), parent, [], False))
        if children and fresh(children[0]):
            groups[parent].append((markers + render(children[0]), examples, allow_archaic))
        for child in children[1:]:
            if fresh(child):
                groups[parent].append((render(child), [], allow_archaic))

    return [
        (text, groups[key]) if kind == "group" else ("", [(text, ex, allow_archaic)])
        for kind, text, key, ex, allow_archaic in items
    ]

_EXAMPLE_MAX_CHARS = 200

# Two tokens are considered the same word when their first this-many characters
# match, which pairs a headword with a regular inflection (swop/swopping,
# run/running) without a stemmer. Kept short so it does not over-match.
_MIN_STEM = 3

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# CJK text is written without spaces, so the word-token split cannot delimit a
# headword inside it -- a whole clause is a single token. A headword written in a
# CJK script is therefore also matched as a plain substring, where a spaced
# language could not (there, "run" must not match inside "brunch").
_CJK_RE = re.compile(
    "[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]"
)

# At most this many examples survive on one sense; the shortest are kept, which
# favours a crisp illustrative phrase over a paragraph-long quotation.
_EXAMPLE_MAX_PER_SENSE = 1

# Wiktionary cross-reference bookkeeping, not usage: the bare "Citations:work."
# placeholder and the "For quotations using this term, see Citations:work."
# sentence that wraps it.
_CITATION_RE = re.compile(r"Citations?:|^see\s+citations?:", re.IGNORECASE)

# Pre-modern spelling and grammar: a long s, the Early Modern -e endings and
# pronouns of Shakespeare-era quotations, and the Middle English inflections that
# survive in Chaucer. Modern usage contains none of them, so matching any marks
# a quote as archaic.
_ARCHAIC_MARKERS = (
    "ſ", "haue", "hath", "thou", "thee", "thy", "doth", "sayde", "vnto",
    "worke", "euery", "wee ", "knowe", "theſe",
    "wolde", "sholde", "seyde", "kyng", "hyre", "yow ", "dooth",
    "my hede", "nat ", "wher ",
)

def _example_is_bookkeeping(text: str) -> bool:
    """Whether an example is a cross-reference stub that says nothing about use."""
    return bool(_CITATION_RE.search(text))

def _example_is_archaic(text: str) -> bool:
    """Whether an example reads as Early Modern or Middle English."""
    if "ſ" in text:                     # long s: an archaic quote
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in _ARCHAIC_MARKERS)

def _example_is_usable(text: str) -> bool:
    """Whether an example is worth showing a modern learner.

    A cross-reference stub says nothing, and an Early Modern or Middle English
    quotation is hard to read; both are dropped for a modern sense. An
    archaic-marked sense may still show an archaic one (see
    :func:`_sense_examples`).
    """
    return not _example_is_bookkeeping(text) and not _example_is_archaic(text)

def _headword_span(
    text: str, word: str, forms: Sequence[str] = ()
) -> Optional[Tuple[int, int]]:
    """The character span of the first token in ``text`` that matches ``word``.

    Accepts the two matches :func:`_example_shows_word` describes: an exact token
    match against the headword or any listed ``forms[]``, or a shared stem of at
    least ``_MIN_STEM`` characters against the headword alone. Returns ``None``
    when no token matches.
    """
    tokens = list(_WORD_RE.finditer(text))
    if not tokens:
        return None

    def strip_label(form: str) -> str:
        return re.split(r"\s+\(", form, maxsplit=1)[0].strip().lower()

    exact = {strip_label(str(word or ""))}
    exact.discard("")
    exact.update(f for f in (strip_label(v) for v in forms) if f)

    for match in tokens:
        if match.group(0).lower() in exact:
            return match.start(), match.end()

    head = str(word or "").strip().lower()
    # A CJK headword has no space boundary to match against, so try it as a
    # substring; the length guard keeps the index valid when casefolding could
    # change the string's length (it cannot for CJK, but be safe).
    if head and _CJK_RE.search(head) and len(text) == len(text.casefold()):
        at = text.casefold().find(head)
        if at != -1:
            return at, at + len(head)
    if len(head) < _MIN_STEM:
        return None
    candidates = {head, *head.split()}
    for match in tokens:
        token = match.group(0).lower()
        if len(token) >= _MIN_STEM and any(
            candidate[:_MIN_STEM] == token[:_MIN_STEM] for candidate in candidates
        ):
            return match.start(), match.end()
    return None

# Sentence terminators, and the closing punctuation that may follow one before
# the next sentence starts. Deliberately simple: enough to keep a single
# sentence rather than a whole quotation when only one sentence names the word.
# The CJK full stop and full-width marks are included so a Japanese example is
# bounded the way an English one is.
_SENTENCE_END = ".!?\u2026\u3002\uff01\uff1f"
_SENTENCE_CLOSERS = "\"'»”)]}\u300d\u300f\uff09\u3011\u300b\u3009"

def _sentence_span(text: str, start: int, end: int) -> Tuple[int, int]:
    """The span of the sentence in ``text`` that contains ``[start, end)``.

    The left edge is the first non-space after the last sentence terminator
    before the match (opening quotes skipped); the right edge is the first
    terminator at or after the match, with any closing quote or bracket that
    follows it. Text with no terminator is treated as one sentence.
    """
    left = 0
    for i in range(start - 1, -1, -1):
        if text[i] in _SENTENCE_END:
            left = i + 1
            break
    while left < start and text[left] in " \t\n\u00a0\"'\u00ab\u201c\u2018\u300c\u300e\uff08\u3010\u300a\u3008":
        left += 1
    right = len(text)
    for i in range(end, len(text)):
        if text[i] in _SENTENCE_END:
            right = i + 1
            while right < len(text) and text[right] in _SENTENCE_CLOSERS:
                right += 1
            break
    return left, right

def _window_span(text: str, start: int, end: int, limit: int) -> Tuple[int, int]:
    """A ``limit``-wide span of ``text`` that contains ``[start, end)``.

    Centred on the match as far as the text allows, then pulled in from either
    edge to a word boundary so a word is never cut in half.
    """
    span = end - start
    left = max(0, min(start - (limit - span) // 2, len(text) - limit))
    right = left + limit
    if left > 0 and text[left - 1] != " ":
        space = text.find(" ", left, start)
        if space != -1:
            left = space + 1
    if right < len(text) and text[right] != " ":
        space = text.rfind(" ", end, right)
        if space != -1:
            right = space
    return left, right

def _truncate_example(
    text: str, word: str = "", forms: Sequence[str] = (),
    limit: int = _EXAMPLE_MAX_CHARS,
) -> str:
    """Shorten an over-long example so it still shows the word in use.

    Wiktionary quotes can run to a whole paragraph; a learner wants the phrase
    that shows the word, not the surrounding essay. A quote that fits the bound
    is returned unchanged. A longer one keeps the sentence that contains the
    headword (or a listed form); when even that sentence is too long, a window
    of ``limit`` characters is centred on the headword. Trimmed edges get an
    ellipsis. With no headword to anchor on it falls back to cutting at the last
    word boundary that fits.
    """
    if len(text) <= limit:
        return text

    span = _headword_span(text, word, forms) if word else None
    if span is None:
        cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
        return cut + " …"

    left, right = _sentence_span(text, span[0], span[1])
    if right - left > limit:
        left, right = _window_span(text, span[0], span[1], limit)

    piece = text[left:right].strip(" \t\n\u00a0").rstrip(" ,;:")
    prefix = "… " if left > 0 else ""
    suffix = " …" if right < len(text) else ""
    return prefix + piece + suffix

def _example_shows_word(text: str, word: str, forms: Sequence[str] = ()) -> bool:
    """Whether an example actually uses the headword (or a form of it).

    An example that does not contain the word proves nothing about it, so it is
    dropped rather than shown. Two matches count:

    * an exact token match against the headword or any listed ``forms[]`` — this
      catches irregular forms (``ran``, ``children``) that share no stem with
      the headword, and
    * a shared stem of at least ``_MIN_STEM`` characters against the headword
      alone, which pairs it with a regular inflection the ``forms[]`` may not
      list (``swop``/``swopping``, ``run``/``running``).
    """
    return _headword_span(text, word, forms) is not None

def _sense_examples(
    raw: Sequence[str],
    word: str,
    forms: Sequence[str] = (),
    allow_archaic: bool = False,
) -> List[str]:
    """Optional-zone lines for one sense's examples.

    Only examples that actually contain the headword (or one of the record's
    forms) are kept, and a ``Citations:`` stub is never shown. A modern-readable
    example is preferred; when the sense itself is marked obsolete, dated or
    archaic (``allow_archaic``) and nothing readable qualifies, an archaic
    quotation is shown rather than leaving the sense bare. One survives, shortest
    first.
    """
    candidates = [
        text
        for text in (str(t).strip() for t in raw)
        if text and not _example_is_bookkeeping(text)
        and _example_shows_word(text, word, forms)
    ]
    readable = [text for text in candidates if not _example_is_archaic(text)]
    chosen = readable if readable else (candidates if allow_archaic else [])
    chosen.sort(key=len)
    return [
        f"\t[ex]{escape_dsl(_truncate_example(text, word, forms))}[/ex]"
        for text in chosen[:_EXAMPLE_MAX_PER_SENSE]
    ]

def _record_transcription(record: dict, profile: LangProfile) -> str:
    """The IPA/enPR transcription of one record, as inline DSL (or "").

    The common IPA value is emitted without a name — the line it lands on is
    always a transcription — while a less common notation (enPR) keeps its label
    so the two are distinguishable. A sound tagged as a different notation
    (wiktextract files X-SAMPA under ``ipa``) is skipped, so the label is true.
    """
    for field in profile.pron_fields:
        for sound in record.get("sounds") or []:
            if not isinstance(sound, dict) or not sound.get(field):
                continue
            if _NOTATION_MISMATCH_TAGS.intersection(sound.get("tags") or []):
                continue
            value = escape_dsl(str(sound[field]))
            if field in _UNLABELLED_PRON_FIELDS:
                return value
            return f"{_PRON_LABEL.get(field, field.upper())}: {value}"
    return ""

def _group_by_pos(records: Sequence[dict]) -> List[Tuple[str, List[int]]]:
    """Group record indices by part of speech, preserving first-seen order.

    A headword's records can arrive interleaved (``noun``, ``verb``, ``noun``),
    but an article should read one part of speech at a time, so records that
    share a POS are merged into a single block under one heading.
    """
    order: List[str] = []
    groups: Dict[str, List[int]] = {}
    for i, record in enumerate(records):
        pos = str(record.get("pos") or "")
        if pos not in groups:
            groups[pos] = []
            order.append(pos)
        groups[pos].append(i)
    return [(pos, groups[pos]) for pos in order]

def render_card(
    records: Sequence[dict],
    audio: AudioPlan,
    profile: LangProfile,
    known: Optional[Set[str]] = None,
) -> str:
    """Render a headword's records as one DSL card.

    A card is one headword whose records are its parts of speech (``run`` is a
    verb and a noun). Records that share a part of speech are merged into one
    block, so an interleaved ``noun, verb, noun`` reads ``noun, verb``. The
    visible article is part of speech → readings → forms → senses; examples and
    cross-references go into the DSL optional zone (``[*]…[/*]``), which the
    reader expands on demand.

    A single transcription shared across the card is hoisted above the first
    part of speech; differing ones stay under their own part of speech. Audio is
    never hoisted and never repeated: each file prints once, under the first
    part of speech that references it.
    """
    records = [r for r in records if r]
    if not records:
        return ""

    # Audio must be planned exactly once per record (planning mutates the
    # plan's referenced set), so plan for all of them before laying anything
    # out and share the result between the hoisted and per-POS layouts.
    transcriptions = [_record_transcription(record, profile) for record in records]
    readings = [collect_profile_readings(record, profile) for record in records]
    record_audio = [list(audio.plan(record)) for record in records]

    blocks = _group_by_pos(records)

    # The transcription is hoisted above the first POS whenever the whole card
    # has a single one — including a card that is a single record, so the common
    # word does not place its transcription inconsistently below the part of
    # speech; audio is never hoisted but is de-duplicated card-wide, so a word
    # whose parts of speech share one recording prints it once.
    distinct_tr = {t for t in transcriptions if t}
    hoist = len(distinct_tr) == 1

    # Readings (a profile-declared kind of form, e.g. Japanese on/kun-yomi) are
    # hoisted the same way: one line for the card when every record agrees, else
    # one under each part of speech.
    distinct_readings = {r for r in readings if r}
    hoist_readings = len(distinct_readings) == 1

    form_lines: List[List[str]] = []
    words: List[str] = []
    forms_by_record: List[List[str]] = []
    for record in records:
        forms = collect_profile_forms(record, profile)
        words.append(str(record.get("word") or ""))
        forms_by_record.append(forms)
        form_lines.append(
            []
            if (not forms or profile.strip_forms)
            else ["\t[i]" + escape_dsl(", ".join(forms)) + "[/i]"]
        )

    # Cross-references: one card-level line, de-duplicated and capped, rather
    # than one "See also" per record.
    refs_seen: List[str] = []
    for record in records:
        if not known:
            break
        for ref in _cross_refs(record, known):
            if ref not in refs_seen:
                refs_seen.append(ref)
            if len(refs_seen) >= 8:
                break

    # Each audio file is emitted once, under the first block that references it.
    # Audio rides on the pronunciation line — the transcription and its playback
    # controls together — so "IPA next to the audio" holds whether the
    # transcription is hoisted or sits under a part of speech.
    shown_audio: Set[str] = set()

    def audio_bits(idxs: Sequence[int]) -> List[str]:
        bits: List[str] = []
        for i in idxs:
            for name in record_audio[i]:
                if name not in shown_audio:
                    shown_audio.add(name)
                    bits.append(_audio_ref(name))
        return bits

    lines: List[str] = []
    if hoist:
        hoisted_audio = audio_bits(range(len(records)))
        pron = next(iter(distinct_tr))
        if hoisted_audio:
            pron += "  " + "  ".join(hoisted_audio)
        lines.append("\t[com]" + pron + "[/com]")
    if hoist_readings:
        lines.append("\t[com]" + escape_dsl(next(iter(distinct_readings))) + "[/com]")

    # A blank line separates consecutive parts of speech, so their sections read
    # as blocks rather than one list. It goes strictly between them: no blank
    # before the first part of speech, even when a hoisted transcription sits
    # above it.
    first_pos_seen = False
    for pos, idxs in blocks:
        if pos:
            if first_pos_seen:
                lines.append("")
            first_pos_seen = True
            lines.append(f"\t[p]{escape_dsl(profile.pos_labels.get(pos, pos))}[/p]")
        # readings: the block's first record that carries any, unless the whole
        # card shares one line (then it was hoisted above the first POS)
        if not hoist_readings:
            for i in idxs:
                if readings[i]:
                    lines.append("\t[com]" + escape_dsl(readings[i]) + "[/com]")
                    break
        # forms: first record of the block that carries any
        for i in idxs:
            if form_lines[i]:
                lines.extend(form_lines[i])
                break

        # pronunciation: the transcription of the block's records (one per
        # distinct value) with any not-yet-shown audio; hoisted when the whole
        # card shares one transcription. Each distinct transcription takes the
        # audio of the first record that carries it, so a multi-record block
        # without a hoist still keeps its audio beside the pronunciation.
        if not hoist:
            seen_tr: Set[str] = set()
            for i in idxs:
                tr = transcriptions[i]
                if tr and tr not in seen_tr:
                    seen_tr.add(tr)
                    bits = audio_bits([i])
                    pron = tr + ("  " + "  ".join(bits) if bits else "")
                    lines.append("\t[com]" + pron + "[/com]")
            block_audio = audio_bits([i for i in idxs if not transcriptions[i]])
            if block_audio:
                lines.append("\t[com]" + "  ".join(block_audio) + "[/com]")

        # senses: merged across the block's records. Every sense sits at [m1]
        # (one indentation level under its part of speech); a grouped parent
        # gloss is [m1] with its sub-senses at [m2], one level deeper. The
        # engine renders [mN] by indentation, so this nests the children under
        # the parent without a global sense counter. Each leaf sense is prefixed
        # with a bullet; the sense text is already escaped and may carry inline
        # icon markup, so it is not escaped again here.
        #
        # A parent heading (a sense that carries sub-senses) is numbered "1. ",
        # "2. "…, counted per part of speech, so the top-level sections of a long
        # article read as an outline. A heading with no children is an ordinary
        # sense and is left bulleted but unnumbered, so a card that has no groups
        # (most cards) is unchanged.
        group_nom = 0
        for i in idxs:
            for heading, entries in _group_senses(
                records[i].get("senses") or [], profile, known, words[i]
            ):
                if heading:
                    if entries:
                        group_nom += 1
                        heading = f"{group_nom}. {heading}"
                    lines.append(f"\t[m1]{heading}[/m]")
                level = 2 if heading else 1
                for text, raw_examples, allow_archaic in entries:
                    lines.append(f"\t[m{level}]\u2022 {text}[/m]")
                    examples = _sense_examples(
                        raw_examples, words[i], forms_by_record[i], allow_archaic
                    )
                    if examples:
                        lines.append("\t[*]")
                        lines.extend(examples)
                        lines.append("\t[/*]")

    if refs_seen:
        links = ", ".join("[ref]" + escape_dsl(r) + "[/ref]" for r in refs_seen)
        lines.append("\t[*]")
        lines.append("\t[com]See also: " + links + "[/com]")
        lines.append("\t[/*]")

    return "\n".join(lines)

def render_record(
    record: dict,
    audio: AudioPlan,
    profile: LangProfile,
    known: Optional[Set[str]] = None,
) -> str:
    """Render one record as a card (a thin wrapper over :func:`render_card`)."""
    return render_card([record], audio, profile, known)
