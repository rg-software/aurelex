"""Build pipeline"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from typing import Dict, List, Optional, Set, Tuple

from .audio import AudioPlan, bundle_entry_names, extract_audio, write_bundle
from .constants import WIKTEXTRACT_CITATION, WIKTIONARY_LICENSE
from .dictzip import encode_dsl, make_dictzip
from .dsltext import _ICON_ASSET_DIR, _ICON_FILES, _ICON_LEGEND, _icon_ref, _unescape_dsl, clean_headword, escape_dsl, header_arg
from .inputs import _resolve_inputs
from .preview import render_preview
from .profiles import collect_profile_forms, get_lang_profile, reading_words
from .render import Report, _CROSS_REF_RE, render_card, unlink_absent_refs
from .snapshot import Progress, TabularLog, download_cached
from .source import is_inflected, is_lexical, iter_records, sample_headwords, select_headwords_and_splits


LANGUAGE_NAMES = {
    "en": "English", "ru": "Russian", "de": "German", "ja": "Japanese",
    "fr": "French", "es": "Spanish", "it": "Italian", "pt": "Portuguese",
    "zh": "Chinese", "la": "Latin", "nl": "Dutch", "pl": "Polish",
    "uk": "Ukrainian", "sv": "Swedish", "fi": "Finnish", "ca": "Catalan",
    "ar": "Arabic", "he": "Hebrew", "hi": "Hindi", "tr": "Turkish",
    "el": "Greek", "cs": "Czech", "ro": "Romanian", "hu": "Hungarian",
    "ko": "Korean", "vi": "Vietnamese", "fa": "Persian", "da": "Danish",
    "no": "Norwegian", "bg": "Bulgarian", "sr": "Serbo-Croatian",
}

def _language_name(record: Optional[dict], code: str) -> str:
    if code in LANGUAGE_NAMES:
        return LANGUAGE_NAMES[code]
    if record and record.get("lang"):
        return str(record["lang"])
    return code.upper()

def description_lines(
    title: str,
    language_name: str,
    language_code: str,
    dump_date: Optional[str],
    card_count: int,
) -> List[str]:
    """The dictionary's description, shared by the about article and the .ann.

    One source so the two cannot drift: the title, a canned derivative-work line
    naming the source and snapshot, the wiktextract reference, then the license,
    language and entry count. Plain text; the about article wraps each line in
    ``[com]…[/com]`` and adds the sense-icon legend, the annotation uses it as is.
    """
    return [
        f"{title}: a Wiktionary-based dictionary",
        "",
        f"This is a derivative work, based on Wiktionary / kaikki.org, snapshot {dump_date or 'unknown'}",
        f"See also: {WIKTEXTRACT_CITATION}",
        "",
        f"License: {WIKTIONARY_LICENSE}",
        f"Language: {language_name} ({language_code})",
        f"Entries: {card_count:,}",
    ]

def write_annotation(
    path: str,
    title: str,
    language_name: str,
    language_code: str,
    dump_date: Optional[str],
    card_count: int,
) -> None:
    """Write the dictionary's Lingvo-style annotation beside it.

    A DSL reader derives ``<base>.ann`` from the dictionary filename and reads it
    as the dictionary's description (goldendict-ng does, splitting it by
    ``#LANGUAGE`` sections when present). The header block has no description
    field, so this sibling is where a reader finds the attribution; it is plain
    text, not DSL markup.
    """
    lines = description_lines(title, language_name, language_code, dump_date, card_count)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def build(args) -> Report:
    report = Report()

    profile = get_lang_profile(args.source_lang)

    # A language whose profile declares no recordings (Japanese, say) downloads
    # no audio archive and bundles none, exactly as with an explicit --no-audio:
    # the source has nothing to offer, so fetching the 20 GB archive would only
    # find that nothing is referenced.
    want_audio = (
        (not args.no_audio) and args.audio_per_word > 0 and profile.has_audio
    )
    snapshot, jsonl_path, audio_path, available, download_dir = _resolve_inputs(
        args, want_audio
    )

    downloader = args.audio_downloader
    if downloader is None and download_dir is not None:
        timeout = args.timeout

        def downloader(url: str, dest: str) -> str:  # type: ignore[misc]
            return download_cached(url, dest, timeout=timeout)

    # The dead record is cache state shared with 'prefetch-audio': a recording
    # Wikimedia says is gone will be gone on every later run too, so the build
    # skips what an earlier run found gone and appends what it finds gone now.
    # Without this a 404 would be re-attempted on every build, forever.
    dead_log = None
    if download_dir is not None:
        dead_log = TabularLog(
            os.path.join(snapshot.dir, "audio-dead.tsv"), download_dir, truncate=False
        )

    def on_gone(dest: str, url: str, reason: str) -> None:
        if dead_log is not None:
            dead_log.add(dest, url, reason)
        print(f"audio gone ({reason}): {os.path.basename(dest)}", file=sys.stderr)

    audio = AudioPlan(
        args.audio_per_word, args.audio_lang, want_audio, available, downloader,
        dead=(dead_log.names if dead_log is not None else None),
        on_gone=on_gone,
    )
    audio.download_dir = download_dir

    def report_cached(count: int) -> None:
        # A coarse progress for cache hits: the exact total is not known until
        # the snapshot has been scanned, so this is a running count, not a
        # fraction. One line per cached file would be tens of thousands of
        # writes; one every thousand is enough to see it moving.
        if count == 1 or count % 1000 == 0:
            print(f"audio cached: {count:,}", file=sys.stderr)

    audio.on_cached = report_cached

    # Output file name (dictionary, bundle, annotation) vs the display title used
    # for #NAME, the about headword and the description. The title defaults to the
    # output name, so an invocation that sets neither is unchanged.
    header_name = args.name or f"kaikki-{args.source_lang}"
    title = args.title or header_name

    out_lines: List[str] = []
    header_lines: List[str] = []

    current_word: Optional[str] = None
    current_records: List[dict] = []
    source_lang_name = args.source_lang.upper()
    # Words already emitted. In sample mode this is the only set cross-references
    # may point at, so a sample never links to a headword it does not contain.
    known: Set[str] = set()
    # Rendered cards, held as data until every card is rendered: a card that ends
    # up with no definition, and that nothing links to, is dropped, so the
    # dictionary never describes a headword with an empty article.
    cards: List[Tuple[str, str, str, int]] = []  # (headwords, body, word, records)

    def emit(word: str, records: List[dict]) -> None:
        nonlocal source_lang_name
        if not records:
            return
        record = records[0]
        source_lang_name = _language_name(record, args.source_lang)
        headwords = [clean_headword(word)]
        if args.include_inflections:
            for form in collect_profile_forms(record, profile):
                form_word = re.split(r"\s+\(", form, maxsplit=1)[0].strip()
                if form_word and form_word != word:
                    headwords.append(clean_headword(form_word))
        if args.index_readings:
            # A reading is how the word is looked up by sound (Japanese kana for
            # a kanji entry), so it becomes an extra headword of the same card.
            for reading in reading_words(record, profile):
                reading_head = clean_headword(reading)
                if reading_head and reading_head not in headwords:
                    headwords.append(reading_head)
        body = render_card(records, audio, profile, known)
        if not body:
            return
        cards.append(("\n".join(headwords), body, word, len(records)))
        known.add(word)

    def flush() -> None:
        nonlocal current_word, current_records
        if not current_records:
            return
        emit(str(current_word), current_records)
        current_word, current_records = None, []

    merged_order: List[str] = []
    if args.sample:
        # Single bounded pass over the snapshot: the whole-file selection the
        # full build needs would make a sample take minutes, and a sample only
        # has to show article shape.
        sampling = Progress("sampling headwords")
        sampled = sample_headwords(
            jsonl_path, args.source_lang, args.sample, args.sample_mode, sampling, report
        )
        sampling.done()
        for record in sampled:
            word = str(record.get("word"))
            if word != current_word:
                flush()
                current_word = word
            current_records.append(record)
        flush()
    else:
        # Full build: the indexed-headword set drives cross-reference safety, so
        # every reference points at a word the dictionary actually contains. The
        # snapshot is not word-sorted, so a headword's records can be split by
        # other words; those headwords are merged into one card afterwards.
        selecting = Progress("selecting headwords")
        known, split_words = select_headwords_and_splits(
            jsonl_path, args.source_lang, selecting
        )
        selecting.done()

        deferred: Dict[str, List[dict]] = {}
        rendering = Progress("rendering")
        for _, record in iter_records(jsonl_path, rendering):
            if record is None:
                report.skipped_malformed += 1
                continue
            if record.get("lang_code") != args.source_lang:
                report.out_of_pair += 1
                continue
            if not is_lexical(record) or is_inflected(record):
                if is_inflected(record):
                    report.skipped_inflected += 1
                else:
                    report.skipped_nonlexical += 1
                continue
            word = str(record.get("word"))
            if word in split_words:
                if word not in deferred:
                    deferred[word] = []
                    merged_order.append(word)
                deferred[word].append(record)
                continue
            if word != current_word:
                flush()
                current_word = word
            current_records.append(record)
        flush()
        for word in merged_order:
            emit(word, deferred[word])
        rendering.done()

    # Drop the cards that describe nothing, unless something links to them; then
    # leave no link pointing at a headword that did not survive. A card carries a
    # definition when it has a gloss heading ([m1], [m2], ...).
    referenced: Set[str] = set()
    for _, body, _, _ in cards:
        for match in _CROSS_REF_RE.finditer(body):
            referenced.add(_unescape_dsl(match.group(1)))
    kept: List[Tuple[str, str, str, int]] = []
    for headwords_text, body, word, count in cards:
        if "[m" not in body and word not in referenced:
            report.dropped_cards += 1
            continue
        kept.append((headwords_text, body, word, count))
    report.merged_headwords = len(merged_order)
    present = {word for _, _, word, _ in kept}
    for headwords_text, body, _word, count in kept:
        body, unlinked = unlink_absent_refs(body, present)
        report.unlinked_refs += unlinked
        out_lines.append(headwords_text)
        out_lines.append(body)
        report.cards += 1
        report.kept_records += count

    if report.cards == 0:
        raise SystemExit(
            f"no {args.source_lang!r} headwords were found in this snapshot"
        )

    header_lines.append(f'#NAME "{header_arg(title)}"')
    header_lines.append(f'#INDEX_LANGUAGE "{header_arg(source_lang_name)}"')
    header_lines.append(f'#CONTENTS_LANGUAGE "{header_arg(source_lang_name)}"')

    about = [clean_headword(f"About {title}")]
    for line in description_lines(
        title, source_lang_name, args.source_lang, args.dump_date, report.cards
    ):
        if line:
            about.append(f"\t[com]{escape_dsl(line)}[/com]")
    about.append("\t[com]Sense icons (Material Symbols, Google; Apache-2.0):[/com]")
    for icon_name, meaning in _ICON_LEGEND:
        about.append(f"\t[com]{_icon_ref(icon_name)} {escape_dsl(meaning)}[/com]")

    dsl_text = "\n".join(header_lines) + "\n\n" + "\n".join(about) + "\n" + "\n".join(out_lines) + "\n"

    os.makedirs(args.out_dir, exist_ok=True)
    dz_path = os.path.join(args.out_dir, header_name + ".dsl.dz")
    # The resource bundle is named after the dictionary file *without* the
    # dictzip suffix: the reader looks for "<base>.dsl.files.zip" first
    # (dsl.cc:1743, where baseName drops ".dsl.dz"), so that is the canonical
    # name; "<base>.dsl.dz.files.zip" is only its fallback.
    res_base = os.path.join(args.out_dir, header_name + ".dsl")
    with open(dz_path, "wb") as f:
        f.write(make_dictzip(encode_dsl(dsl_text)))

    # The dictionary's description lives in a Lingvo-style sibling annotation
    # (the DSL header block has no description field). Metadata, so it is written
    # on every build, unlike the resource bundle which --reuse-bundle skips.
    write_annotation(
        os.path.join(args.out_dir, header_name + ".ann"),
        title,
        source_lang_name,
        args.source_lang,
        args.dump_date,
        report.cards,
    )

    if args.preview:
        preview_path = os.path.join(args.out_dir, header_name + ".preview.html")
        render_preview(header_name, dsl_text, preview_path)
        print(f"wrote {preview_path}", file=sys.stderr)

    # Resource bundle: the sense-marker icons (always) plus pronunciation audio
    # (when enabled), written as one archive by default or a directory on request.
    # Bundling is unconditional because the about card always references the icon
    # set, so the icons must resolve even when audio is disabled.
    bundle_dest = (
        res_base + ".files.zip" if args.audio_layout == "zip" else res_base + ".files"
    )
    if args.reuse_bundle:
        # Render only: keep the bundle already beside the dictionary. A build's
        # references only shrink when cards are pruned or merged, so the existing
        # bundle normally covers the new dictionary; it is checked rather than
        # assumed, and only its entry names are read.
        required = set(_ICON_FILES)
        required.update(audio.referenced)
        present = bundle_entry_names(bundle_dest)
        if present is None:
            print(
                f"warning: --reuse-bundle, but there is no resource bundle at "
                f"{bundle_dest}; the dictionary references resources that are not "
                f"present",
                file=sys.stderr,
            )
        else:
            absent = sorted(required - present)
            if absent:
                print(
                    f"warning: the reused bundle {bundle_dest} lacks "
                    f"{len(absent)} referenced resource(s); re-run without "
                    f"--reuse-bundle to rebuild it",
                    file=sys.stderr,
                )
            else:
                print(
                    f"reused resource bundle: {bundle_dest} ({len(present):,} files)",
                    file=sys.stderr,
                )
        report.audio_found = len(audio.referenced)
    else:
        # Every entry is named by its source path, so a recording already in the
        # download cache is read straight into the bundle rather than copied into
        # a staging directory first; only archive members are extracted to ``tmp``.
        sources: Dict[str, str] = {
            name: os.path.join(_ICON_ASSET_DIR, name) for name in _ICON_FILES
        }
        with tempfile.TemporaryDirectory(prefix="kaikki-res-") as tmp:
            if want_audio and audio.referenced:
                fetched = {
                    name: path
                    for name, path in audio.local.items()
                    if name in audio.referenced and os.path.isfile(path)
                }
                sources.update(fetched)
                wanted = {
                    name: list(audio.aliases.get(name, []))
                    for name in sorted(audio.referenced)
                    if name not in fetched
                }
                batching = Progress("bundling audio", every=1, total=len(wanted))
                found, missing = extract_audio(audio_path, wanted, tmp, batching)
                batching.done()
                missing_set = set(missing)
                for name in wanted:
                    if name not in missing_set:
                        sources[name] = os.path.join(tmp, name)
                report.audio_found = len(fetched) + found
                if missing:
                    print(
                        f"warning: {len(missing)} planned audio file(s) were not found in "
                        f"the archive while bundling",
                        file=sys.stderr,
                    )
            packing = Progress("writing bundle", every=1, total=len(sources))
            write_bundle(sources, bundle_dest, args.audio_layout, packing)
            packing.done()

    report.missing_audio = len(audio.missing)
    report.audio_cached = audio.cached_hits
    if dead_log is not None:
        dead_log.close()
    print(f"wrote {dz_path}", file=sys.stderr)
    return report
