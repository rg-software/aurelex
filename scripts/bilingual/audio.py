"""Dict A pronunciation audio: the kaikki EN stage run verbatim over our headwords.

Dict A headwords are English lemmas, so the kaikki EN build already decided
their recordings. This module reuses that stage unchanged — same
:class:`AudioPlan`, same archive index, same downloader/cache contract, same
``[s]`` references and sibling bundle layout — driven by a headword list
instead of a full snapshot render. Silence lands exactly where the monolingual
EN cards are silent.
"""

from __future__ import annotations

import os
import sys
import tempfile
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import dsl as _dsl


def _kaikki():
    scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from kaikki import audio as kaudio
    from kaikki import source as ksource

    return kaudio, ksource


class _TickPrinter:
    """Duck-typed progress sink for kaikki's tick callbacks.

    Prints ``label: done/total`` every ``every`` ticks (and on the first
    tick) so the silent minutes — tar extraction, bundle zipping — stay
    visible on stderr.
    """

    def __init__(self, label: str, total: int, every: int = 1000) -> None:
        self._label = label
        self._total = total
        self._every = every
        self._done = 0

    def tick(self) -> None:
        self._done += 1
        if self._done == 1 or self._done % self._every == 0:
            print(f"{self._label}: {self._done:,}/{self._total:,}",
                  file=sys.stderr)


_records_cache: Dict[str, Dict[str, List[dict]]] = {}


def collect_records(snapshot_path: str, words: Sequence[str],
                    lang: str = "en") -> Dict[str, List[dict]]:
    """Gather candidate (lexical, non-inflected) records per headword.

    One streaming pass over the snapshot; the filter mirrors the records the
    kaikki build itself indexes and renders. Prints a coarse line count to
    stderr — a full snapshot scan takes minutes. ``lang`` selects the
    snapshot language (the reverse dictionary reuses the RU stage verbatim).
    Results memoize per snapshot path + language in-process, so the audio
    planner and the transcription picker share the single pass.
    """
    key = f"{snapshot_path}\x00{lang}"
    if key in _records_cache:
        return _records_cache[key]
    _, ksource = _kaikki()
    wanted = set(words)
    found: Dict[str, List[dict]] = {w: [] for w in words}
    tick = 0
    for _line_no, record in ksource.iter_records(snapshot_path, None, lang):
        tick += 1
        if tick % 1000000 == 0:
            print(f"snapshot scan: {tick:,} lines", file=sys.stderr)
        if record is None:
            continue
        word = record.get("word")
        if word not in wanted:
            continue
        if not ksource.is_lexical(record) or ksource.is_inflected(record):
            continue
        found[str(word)].append(record)
    _records_cache[key] = found
    return found


def _profile(lang: str):
    scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from kaikki.profiles import get_lang_profile

    return get_lang_profile(lang)


def transcribe_words(words: Sequence[str], snapshot_path: str,
                     lang: str = "en") -> Dict[str, str]:
    """One pronunciation transcription per headword, from the kaikki stage.

    Reuses the memoized snapshot scan: no second pass. Per-record text comes
    from kaikki's own notation picker (IPA unlabeled, enPR labeled,
    X-SAMPA-tagged sounds skipped); across a headword's records the most
    common value wins, first-seen breaking ties, so the choice is
    deterministic for a pinned snapshot. Headwords with no transcribed
    record are absent from the result. Values are raw text (kaikki's picker
    output unescaped); the DSL emitter escapes at render time.
    """
    # Same-repo private reuse, documented: copying this picker would let the
    # notation discipline drift from kaikki's silently.
    from kaikki.render import _record_transcription  # noqa: SLF001
    from . import dsl as _dsl

    profile = _profile(lang)
    out: Dict[str, str] = {}
    for word, records in collect_records(snapshot_path, words, lang).items():
        counts: Dict[str, int] = {}
        order: List[str] = []
        for record in records:
            text = _dsl.unescape_dsl(_record_transcription(record, profile))
            if not text:
                continue
            if text not in counts:
                counts[text] = 0
                order.append(text)
            counts[text] += 1
        if order:
            out[word] = max(order, key=lambda t: (counts[t], -order.index(t)))
    return out


def plan_words(
    words: Sequence[str],
    snapshot_path: str,
    per_word: int = 3,
    audio_lang: Optional[str] = None,
    enabled: bool = True,
    archive_path: Optional[str] = None,
    download_dir: Optional[str] = None,
    downloader=None,
    dead: Sequence[str] = (),
    available: Optional[Set[str]] = None,
    lang: str = "en",
):
    """Run the kaikki audio planner over Dict A headwords.

    Returns ``(names_by_word, planner)``. ``names_by_word`` maps each headword
    to its bounded, deduplicated recording names — the union of what the
    kaikki EN card for that headword carries. The planner's ``referenced``,
    ``aliases`` and ``local`` feed :func:`bundle_for`.
    """
    kaudio, _ksource = _kaikki()
    if available is None and archive_path is not None:
        available = kaudio.available_audio_keys(archive_path)
    planner = kaudio.AudioPlan(
        per_word, audio_lang, enabled, available, downloader, dead=dead
    )
    planner.download_dir = download_dir
    if download_dir is not None:
        def report_cached(count: int) -> None:
            if count == 1 or count % 1000 == 0:
                print(f"audio cached: {count:,}", file=sys.stderr)
        planner.on_cached = report_cached
    names: Dict[str, List[str]] = {}
    if enabled and per_word > 0:
        records_by_word = collect_records(snapshot_path, words, lang)
        total = len(records_by_word)
        for n, (word, records) in enumerate(records_by_word.items(), 1):
            if n == 1 or n % 5000 == 0:
                print(f"audio planned: {n:,}/{total:,}", file=sys.stderr)
            chosen: List[str] = []
            seen: Set[str] = set()
            for record in records:
                for name in planner.plan(record):
                    if name not in seen:
                        seen.add(name)
                        chosen.append(name)
                    if len(chosen) >= per_word:
                        break
                if len(chosen) >= per_word:
                    break
            names[word] = chosen
    else:
        names = {w: [] for w in words}
    return names, planner


def attach_audio(
    cards: Sequence[_dsl.Card], names_by_word: Dict[str, List[str]]
) -> List[_dsl.Card]:
    """Attach per-headword recording names to cards (recordings are per word)."""
    out = []
    for card in cards:
        names = names_by_word.get(card.headword, [])
        out.append(
            _dsl.Card(
                headword=card.headword,
                pos=card.pos,
                transcription=card.transcription,
                senses=card.senses,
                audio=list(names),
            )
        )
    return out


def bundle_for(
    planner,
    dict_path: str,
    layout: str = "zip",
    archive_path: Optional[str] = None,
) -> Optional[str]:
    """Write the sibling resource bundle for the planned references.

    Bundle naming follows the canonical ``<base>.dsl.files.zip`` / ``.files``
    spellings the app resolves. Recordings already fetched sit in the download
    cache and are read straight into the bundle; the rest are extracted from
    the archive. Returns the bundle path, or None when nothing was referenced.
    """
    kaudio, _ksource = _kaikki()
    if not planner.referenced:
        return None
    print(f"bundling {len(planner.referenced):,} recordings", file=sys.stderr)
    base = dict_path[:-len(".dz")] if dict_path.lower().endswith(".dz") else dict_path
    dest = base + ".files.zip" if layout == "zip" else base + ".files"
    fetched = {
        name: path
        for name, path in planner.local.items()
        if name in planner.referenced and os.path.isfile(path)
    }
    sources: Dict[str, str] = dict(fetched)
    with tempfile.TemporaryDirectory(prefix="bilingual-res-") as tmp:
        if archive_path is not None:
            wanted = {
                name: list(planner.aliases.get(name, []))
                for name in sorted(planner.referenced)
                if name not in fetched
            }
            if wanted:
                found, missing = kaudio.extract_audio(
                    archive_path, wanted, tmp,
                    progress=_TickPrinter("extracting audio", len(wanted)),
                )
                _ = found
                print(f"extracting audio: done "
                      f"({len(wanted) - len(missing):,}/{len(wanted):,})",
                      file=sys.stderr)
                missing_set = set(missing)
                for name in wanted:
                    if name not in missing_set:
                        sources[name] = os.path.join(tmp, name)
        kaudio.write_bundle(
            sources, dest, layout,
            progress=_TickPrinter("writing bundle", len(sources)),
        )
        print(f"writing bundle: done ({len(sources):,} files)", file=sys.stderr)
    return dest


def verify(dict_path: str, bundle_path: Optional[str] = None) -> dict:
    """Check every audio ``[s]`` reference resolves in the sibling bundle."""
    kaudio, _ksource = _kaikki()
    return kaudio.verify_bundle(dict_path, bundle_path)
