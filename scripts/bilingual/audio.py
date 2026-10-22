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


def collect_records(snapshot_path: str, words: Sequence[str]) -> Dict[str, List[dict]]:
    """Gather candidate (lexical, non-inflected) EN records per headword.

    One streaming pass over the snapshot; the filter mirrors the records the
    kaikki EN build itself indexes and renders.
    """
    _, ksource = _kaikki()
    wanted = set(words)
    found: Dict[str, List[dict]] = {w: [] for w in words}
    for _line_no, record in ksource.iter_records(snapshot_path, None, "en"):
        if record is None:
            continue
        word = record.get("word")
        if word not in wanted:
            continue
        if not ksource.is_lexical(record) or ksource.is_inflected(record):
            continue
        found[str(word)].append(record)
    return found


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
    names: Dict[str, List[str]] = {}
    if enabled and per_word > 0:
        for word, records in collect_records(snapshot_path, words).items():
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
                found, missing = kaudio.extract_audio(archive_path, wanted, tmp)
                _ = found
                missing_set = set(missing)
                for name in wanted:
                    if name not in missing_set:
                        sources[name] = os.path.join(tmp, name)
        kaudio.write_bundle(sources, dest, layout)
    return dest


def verify(dict_path: str, bundle_path: Optional[str] = None) -> dict:
    """Check every audio ``[s]`` reference resolves in the sibling bundle."""
    kaudio, _ksource = _kaikki()
    return kaudio.verify_bundle(dict_path, bundle_path)
