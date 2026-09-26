#!/usr/bin/env python3
"""Build an importable ABBYY Lingvo DSL dictionary from a pinned kaikki.org
Wiktionary (wiktextract) snapshot for a chosen language pair.

The output is a deterministic dictzip-compressed ``<name>.dsl.dz`` plus a
sibling ``<name>.dsl.dz.files.zip`` (or ``.files/`` directory) holding the
referenced pronunciation audio, so it imports through Aurelex's existing
folder import without any app or engine changes.

Highlights:
  * reproducible: a pinned dump date, cached downloads (with sha256 sidecars),
    no plain ``.dsl`` in the output, byte-identical rebuilds
  * source language selects the indexed headwords, target language the
    rendered glosses/translations (source == target is monolingual)
  * base forms are the only indexed headwords by default; ``--include-inflections``
    adds a base word's inflected forms as extra headword lines (they then also
    appear in the suggestion list - there is no hidden-alias concept in DSL)
  * bounded audio (``--audio-per-word``, default 3; ``--no-audio`` disables)
  * ``--sample N`` and ``--preview`` for reviewing article shape and formatting
  * provenance (Wiktionary, CC BY-SA 4.0, wiktextract citation, dump date) is
    embedded in the ``#NAME`` metadata and in an about card

Usage:
  kaikki-to-dsl.py --source-lang en --target-lang ru --dump-date 2026-09-02 \\
      --out-dir dist --sample 200 --preview
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import html
import importlib.util
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple
from urllib.parse import unquote

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_JSONL_URL = "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"
AUDIO_TAR_URL = "https://kaikki.org/dictionary/wiktionary-audios.tar"
RAWDATA_PAGE_URL = "https://kaikki.org/dictionary/rawdata.html"

WIKTIONARY_LICENSE = "CC BY-SA 4.0"
WIKTEXTRACT_CITATION = (
    "Tatu Ylonen: Wiktextract: Wiktionary as Machine-Readable Structured Data, "
    "LREC 2022 (https://kaikki.org)"
)

# Parts of speech that are not lexical headwords in this converter's sense.
NON_LEXICAL_POS = {"soft-redirect", "romanization"}

AUDIO_EXTENSIONS = (
    ".ogg", ".oga", ".mp3", ".wav", ".flac", ".opus", ".m4a", ".spx",
    ".au", ".aac", ".wma", ".mp2", ".mpa",
)

OGG_EXTENSIONS = {".ogg", ".oga", ".opus"}


# ---------------------------------------------------------------------------
# Per-language profiles
# ---------------------------------------------------------------------------
# Every article is shaped by the *source* language's grammar, so anything that
# is specific to one language lives in a profile rather than in the renderer.
# Adding a language means adding a row here (and tests assert that), not
# editing article logic.

class LangProfile:
    """How to read one source language's records into a learner's article.

    ``form_tags``       - tag vocabulary that is part of the standard paradigm;
                          a form qualifies only if every one of its tags is in
                          here (empty = accept any tagged form).
    ``form_noise_tags`` - tags that mean "raw inflection table", never a form.
    ``pron_fields``     - ``sounds[]`` keys that carry a transcription, tried
                          in order; the first non-empty one is shown.
    ``short_tags``      - compact labels for the common grammatical tags.
    ``has_audio``       - whether the source has pronunciation recordings.
    ``strip_forms``     - whether article "Forms:" lines are meaningful.
    """

    def __init__(
        self,
        code: str,
        form_tags: Set[str],
        form_noise_tags: Set[str],
        pron_fields: Sequence[str],
        short_tags: Dict[str, str],
        has_audio: bool = True,
        strip_forms: bool = False,
    ) -> None:
        self.code = code
        self.form_tags = form_tags
        self.form_noise_tags = form_noise_tags
        self.pron_fields = tuple(pron_fields)
        self.short_tags = short_tags
        self.has_audio = has_audio
        self.strip_forms = strip_forms

    def form_qualifies(self, tags: Sequence[str]) -> bool:
        tags = [str(t) for t in tags]
        if any(t in self.form_noise_tags for t in tags):
            return False
        if not tags:
            return False
        if not self.form_tags:
            return True
        return all(t in self.form_tags for t in tags)

    def label_tags(self, tags: Sequence[str]) -> str:
        """Compact human label for a tag set.

        A person tag already implies its number (``third-person`` + ``singular``
        is just "3rd sg."), so the number is dropped when a person is present.
        """
        tags = [str(t) for t in tags]
        if "third-person" in tags or "first-person" in tags or "second-person" in tags:
            tags = [t for t in tags if t not in ("singular", "plural")]
        parts = [self.short_tags.get(t, t.replace("-", " ")) for t in tags]
        return ", ".join(parts)


# English form tags: the core paradigm only. Register/dialect tags
# (archaic, obsolete, dialectal, nonstandard, humorous, ...) are deliberately
# absent, so those forms are dropped rather than shown as equal variants.
_EN_FORM_TAGS = {
    "plural", "singular", "past", "present", "participle",
    "third-person", "first-person", "second-person",
    "comparative", "superlative", "imperative", "infinitive",
    "positive", "attributive", "predicative", "not-comparable",
}
_EN_NOISE = {"table-tags", "inflection-template", "no-table-tags"}
_EN_SHORT_TAGS = {
    "third-person": "3rd sg.", "first-person": "1st", "second-person": "2nd",
    "singular": "sg.", "plural": "pl.",
    "present": "pres.", "past": "past", "participle": "part.",
    "comparative": "comp.", "superlative": "sup.",
    "imperative": "imper.", "infinitive": "inf.",
}

# German forms are dominated by case/number/gender; a global whitelist would
# discard the most useful information, hence a dedicated row.
_DE_FORM_TAGS = {
    "singular", "plural", "nominative", "genitive", "dative", "accusative",
    "strong", "weak", "mixed", "definite", "indefinite", "without-article",
    "with-article", "comparative", "superlative", "positive",
    "present", "past", "participle", "first-person", "second-person",
    "third-person", "imperative",
}
_DE_NOISE = {"table-tags", "inflection-template", "no-table-tags"}
_DE_SHORT_TAGS = {
    "singular": "sg.", "plural": "pl.", "nominative": "nom.",
    "genitive": "gen.", "dative": "dat.", "accusative": "acc.",
    "strong": "strong", "weak": "weak", "mixed": "mixed",
    "present": "pres.", "past": "past", "participle": "part.",
    "comparative": "comp.", "superlative": "sup.",
}

# Japanese has no IPA in this source; readings arrive as forms (`romanization`,
# `hiragana`, ...) so the pronunciation slot is filled from those instead.
_JA_FORM_TAGS: Set[str] = set()  # accept any non-noise tagged form
_JA_NOISE = {"table-tags", "inflection-template", "no-table-tags"}
_JA_SHORT_TAGS = {
    "romanization": "romaji", "hiragana": "hiragana", "katakana": "katakana",
    "kanji": "kanji", "kyūjitai": "kyūjitai", "stem": "stem",
    "imperfective": "imperf.", "continuative": "cont.", "past": "past",
}

LANG_PROFILES: Dict[str, LangProfile] = {
    "en": LangProfile(
        "en", _EN_FORM_TAGS, _EN_NOISE, ("ipa", "enpr"), _EN_SHORT_TAGS,
    ),
    "de": LangProfile(
        "de", _DE_FORM_TAGS, _DE_NOISE, ("ipa", "enpr"), _DE_SHORT_TAGS,
    ),
    "ja": LangProfile(
        "ja", _JA_FORM_TAGS, _JA_NOISE, (), _JA_SHORT_TAGS, has_audio=False,
    ),
}


def get_lang_profile(code: str) -> LangProfile:
    """The source-language profile, or a permissive fallback.

    The fallback keeps any tagged form and shows any transcription the source
    happens to provide, so an unknown source language still produces a sane
    article (and a warning) instead of an empty one.
    """
    profile = LANG_PROFILES.get(code)
    if profile is not None:
        return profile
    print(
        f"warning: no language profile for {code!r}; using a permissive default",
        file=sys.stderr,
    )
    return LangProfile(code, set(), _EN_NOISE, ("ipa", "enpr"), {})


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# dictzip: reuse the writer from make-example-dicts.py (single source of truth)
# ---------------------------------------------------------------------------

def _load_make_example_dicts():
    path = os.path.join(_SCRIPT_DIR, "make-example-dicts.py")
    spec = importlib.util.spec_from_file_location("aurelex_make_example_dicts", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load dictzip writer from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MED = _load_make_example_dicts()
make_dictzip = _MED.make_dictzip


def encode_dsl(text: str) -> bytes:
    """UTF-8 with BOM; the DSL reader detects the encoding from it."""
    return b"\xef\xbb\xbf" + text.encode("utf-8")


# ---------------------------------------------------------------------------
# DSL text tooling
# ---------------------------------------------------------------------------

def escape_dsl(text: Optional[str]) -> str:
    """Escape free text so it cannot form DSL markup.

    Backslash, square brackets, and the ``<<``/``>>`` media delimiters are
    escaped; tabs/newlines collapse to spaces and runs of spaces collapse.
    """
    if not text:
        return ""
    s = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    s = s.replace("\t", " ")
    s = s.replace("\\", "\\\\")
    s = s.replace("[", "\\[")
    s = s.replace("]", "\\]")
    s = s.replace("<<", "\\<\\<").replace(">>", "\\>\\>")
    s = re.sub(r" {2,}", " ", s)
    return s.strip()


def clean_headword(word: Optional[str]) -> str:
    """Sanitise a headword line (column 0, no indentation)."""
    hw = escape_dsl(word)
    hw = hw.lstrip("\t ")
    if hw.startswith("#"):
        hw = "\\" + hw
    return hw


def header_arg(value: Optional[str]) -> str:
    """Sanitise a quoted DSL header argument (no embedded quotes)."""
    return escape_dsl(value).replace('"', "'")


def _flatten(value) -> str:
    """Render an arbitrary wiktextract value as readable text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values() if v is not None)
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v) for v in value if v is not None)
    return ""


def _tags_suffix(tags) -> str:
    if not tags:
        return ""
    return "(" + ", ".join(str(t) for t in tags) + ") "


# ---------------------------------------------------------------------------
# Snapshot model and cached download
# ---------------------------------------------------------------------------

class Snapshot:
    """A pinned kaikki.org snapshot and its local cache locations."""

    def __init__(
        self,
        dump_date: Optional[str],
        cache_dir: str,
        jsonl_url: str = RAW_JSONL_URL,
        audio_url: str = AUDIO_TAR_URL,
    ) -> None:
        self.dump_date = dump_date
        self.cache_dir = cache_dir
        self.jsonl_url = jsonl_url
        self.audio_url = audio_url
        key = dump_date or "local"
        self.dir = os.path.join(cache_dir, key)

    @property
    def jsonl_path(self) -> str:
        return os.path.join(self.dir, os.path.basename(self.jsonl_url.split("?")[0]))

    @property
    def audio_path(self) -> str:
        return os.path.join(self.dir, os.path.basename(self.audio_url.split("?")[0]))


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_sidecar(path: str) -> bool:
    """Verify a downloaded file against its ``.sha256`` sidecar if present."""
    sidecar = path + ".sha256"
    if not os.path.isfile(path):
        return False
    if os.path.getsize(path) == 0:
        return False
    if not os.path.isfile(sidecar):
        return True
    with open(sidecar, "r", encoding="ascii") as f:
        expected = f.read().strip()
    return expected == _sha256_file(path)


def download_cached(url: str, dest: str, force: bool = False, timeout: int = 60) -> str:
    """Download ``url`` to ``dest`` once, writing a sha256 sidecar.

    Reuses an existing, verified file unless ``force`` is set. The write is
    atomic (a ``.part`` file is renamed into place).
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not force and verify_sidecar(dest):
        return dest
    part = dest + ".part"
    print(f"downloading {url} ...", file=sys.stderr)
    request = urllib.request.Request(url, headers={"User-Agent": "aurelex-kaikki-to-dsl/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response, open(part, "wb") as out:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            out.write(block)
    os.replace(part, dest)
    with open(dest + ".sha256", "w", encoding="ascii") as f:
        f.write(_sha256_file(dest))
    return dest


def _fetch_dump_date(timeout: int = 60) -> Optional[str]:
    request = urllib.request.Request(
        RAWDATA_PAGE_URL, headers={"User-Agent": "aurelex-kaikki-to-dsl/1.0"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        page = response.read().decode("utf-8", "replace")
    match = re.search(r"dump dated (\d{4}-\d{2}-\d{2})", page)
    return match.group(1) if match else None


class Progress:
    """A coarse, cheap stderr progress indicator.

    ``tick`` is called once per item; it only formats and writes every
    ``every`` items, so the cost per item is a single comparison. ``done``
    finishes the line so later messages start on a fresh one.
    """

    def __init__(self, label: str, every: int = 200000, total: Optional[int] = None) -> None:
        self.label = label
        self.every = max(1, every)
        self.total = total
        self.count = 0
        self.t0 = time.time()
        self._shown = False

    def tick(self, increment: int = 1) -> None:
        self.count += increment
        if self.count % self.every == 0:
            self._write()

    def _write(self, final: bool = False) -> None:
        if self.total:
            text = f"{self.label}: {self.count:,}/{self.total:,}"
        else:
            text = f"{self.label}: {self.count:,}"
        text += f"  ({time.time() - self.t0:.0f}s)"
        stream = sys.stderr
        stream.write("\r" + text.ljust(72))
        if final:
            stream.write("\n")
        stream.flush()
        self._shown = True

    def done(self) -> None:
        if self._shown:
            self._write(final=True)


# ---------------------------------------------------------------------------
# Reading / filtering records
# ---------------------------------------------------------------------------

def open_text_maybe_gzip(path: str):
    with open(path, "rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "rt", encoding="utf-8", errors="replace")


def iter_records(path: str, progress: Optional["Progress"] = None) -> Iterator[Tuple[int, Optional[dict]]]:
    """Yield ``(line_number, record_or_None)``; ``None`` marks a malformed line."""
    with open_text_maybe_gzip(path) as stream:
        for line_no, line in enumerate(stream, 1):
            if progress is not None:
                progress.tick()
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("not an object")
            except (json.JSONDecodeError, ValueError):
                yield line_no, None
                continue
            yield line_no, record


def is_lexical(record: dict) -> bool:
    if record.get("pos") in NON_LEXICAL_POS:
        return False
    if not record.get("word"):
        return False
    senses = record.get("senses")
    if not isinstance(senses, list) or not senses:
        return False
    return True


def is_inflected(record: dict) -> bool:
    senses = record.get("senses") or []
    return any(isinstance(s, dict) and s.get("form_of") for s in senses)


def iter_candidate_headwords(
    path: str, source_code: str, progress: Optional["Progress"] = None
) -> Iterator[str]:
    """Yield headword candidates (source language, lexical, not inflected)."""
    for _, record in iter_records(path, progress):
        if record is None or record.get("lang_code") != source_code:
            continue
        if not is_lexical(record) or is_inflected(record):
            continue
        word = record.get("word")
        if word:
            yield str(word)


def select_headwords(
    path: str,
    source_code: str,
    sample: Optional[int],
    sample_mode: str,
    progress: Optional["Progress"] = None,
) -> Set[str]:
    """The set of headwords that will be indexed (drives cross-reference safety).

    Without ``--sample`` this is every candidate headword. With ``--sample`` it
    is the emitted subset: the first N *distinct* candidates (``first``) or a
    deterministic random subset chosen by the smallest sha256 keys, so the same
    snapshot and options always select the same words. A word that has several
    records (for example ``run`` as a verb and a noun) is one headword, not
    several, so duplicates never consume a sample slot.
    """
    if not sample:
        return set(iter_candidate_headwords(path, source_code, progress))
    if sample_mode == "first":
        selected: Set[str] = set()
        for word in iter_candidate_headwords(path, source_code, progress):
            selected.add(word)
            if len(selected) >= sample:
                break
        return selected
    heap: List[Tuple[int, str]] = []  # max-heap of (-key, word), size <= sample
    seen: Set[str] = set()
    for word in iter_candidate_headwords(path, source_code, progress):
        if word in seen:
            continue
        key = int.from_bytes(hashlib.sha256(word.encode("utf-8")).digest()[:8], "big")
        if len(heap) < sample:
            heapq.heappush(heap, (-key, word))
            seen.add(word)
        elif (key, word) < (-heap[0][0], heap[0][1]):
            evicted = heapq.heapreplace(heap, (-key, word))
            seen.discard(evicted[1])
            seen.add(word)
    return {word for _, word in heap}


def collect_forms(record: dict) -> List[str]:
    """Grammatical forms of the base word, as ``form (tags)`` strings."""
    forms: List[str] = []
    for form in record.get("forms") or []:
        if not isinstance(form, dict):
            continue
        text = form.get("form")
        if not text:
            continue
        suffix = _tags_suffix(form.get("tags"))
        forms.append((str(text) + (" " + suffix.strip() if suffix else "")).strip())
    return forms


# ---------------------------------------------------------------------------
# Audio planning and extraction
# ---------------------------------------------------------------------------

def _basename(name: str) -> str:
    return os.path.basename(name.split("?")[0].split("/")[-1])


def _url_basename(name: str) -> str:
    """The canonical file name behind a media reference.

    A reference may be a bare name, a URL, or a percent-encoded MediaWiki path
    (``LL-Q1860_%28eng%29-Vealhurl-pub.wav/...wav.ogg``), and it may carry HTML
    entities (``&#45;`` for a hyphen). Decoding it yields the name the audio
    archive stores.
    """
    return html.unescape(unquote(_basename(name)))


def _audio_match_key(name: str) -> str:
    """Normalisation that pairs a reference with an archive member.

    The archive stores MediaWiki names (underscores, percent-encoded), while a
    reference may use spaces and any casing, so both sides are folded before
    comparison.
    """
    return _url_basename(name).replace(" ", "_").casefold()


def _audio_name_variants(name: str) -> List[str]:
    """Ordered archive keys a reference may be stored under.

    The archive keeps a compressed original plus an mp3 transcode; a large
    original (``.wav``/``.flac``) is present only as ``<name>.ogg`` or
    ``<name>.mp3``. The exact key comes first so the best-quality match wins.
    """
    key = _audio_match_key(name)
    if not key:
        return []
    stem, ext = os.path.splitext(key)
    if ext in OGG_EXTENSIONS:
        return [key, key + ".mp3"]
    return [key, key + ".ogg", key + ".mp3", stem + ".ogg", stem + ".mp3"]


def _canonical_audio_name(sound: dict) -> Optional[str]:
    """The name to bundle and reference for one ``sounds`` entry.

    ``audio`` is the raw wiki argument and is unreliable (wrong case, spaces
    instead of underscores, HTML entities); the URL fields carry the canonical
    MediaWiki title, so they are preferred.
    """
    for field in ("ogg_url", "mp3_url", "audio"):
        value = sound.get(field)
        if value:
            return _url_basename(str(value))
    return None


def _audio_sounds(record: dict) -> List[dict]:
    return [
        s
        for s in (record.get("sounds") or [])
        if isinstance(s, dict)
        and any(s.get(f) for f in ("audio", "ogg_url", "mp3_url"))
    ]


class AudioPlan:
    """Assign collision-free final filenames and remember what is referenced.

    When ``available`` is given it is the set of normalised names present in
    the audio archive; only references found in it (or fetched directly from
    Wikimedia, when a URL is known) are planned, so the output never carries a
    link to a file that was not bundled, and a reference that is absent does
    not consume one of the per-word slots.
    """

    def __init__(
        self,
        per_word: int,
        preferred_lang: Optional[str],
        enabled: bool,
        available: Optional[Set[str]] = None,
        downloader=None,
    ) -> None:
        self.per_word = per_word
        self.preferred_lang = preferred_lang
        self.enabled = enabled
        self.available = available
        # ``downloader(url, dest)`` fetches a recording the archive lacks; the
        # default reuses the cached downloader. Tests inject a stub.
        self.downloader = downloader or (
            lambda url, dest: download_cached(url, dest)
        )
        self._owner: Dict[str, str] = {}   # final_name -> source url
        self.referenced: Set[str] = set()
        self.aliases: Dict[str, List[str]] = {}  # final_name -> archive match keys
        self.local: Dict[str, str] = {}    # final_name -> fetched file on disk
        self.missing: Set[str] = set()     # referenced sources not bundled
        self._fetched: Dict[str, Optional[str]] = {}  # source -> local path or None

    def _final_name(self, source: str) -> str:
        base = _basename(source)
        if base not in self._owner or self._owner[base] == source:
            self._owner[base] = source
            return base
        stem, ext = os.path.splitext(base)
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:8]
        candidate = f"{stem}-{digest}{ext}"
        self._owner[candidate] = source
        return candidate

    def _archive_keys(self, source: str, sound: dict) -> List[str]:
        keys: List[str] = []
        for field in ("ogg_url", "mp3_url", "audio"):
            value = sound.get(field)
            if not value:
                continue
            for key in _audio_name_variants(str(value)):
                if key not in keys:
                    keys.append(key)
        if not keys:
            keys = _audio_name_variants(source)
        return keys

    def _is_available(self, keys: List[str]) -> bool:
        if self.available is None:
            return True
        return any(key in self.available for key in keys)

    def _fetch(self, source: str, sound: dict) -> Optional[str]:
        """Download a recording the archive lacks from its Wikimedia URL.

        The result lands in ``download_dir`` through the cached downloader, so
        a later run reuses it instead of fetching it again. Returns the local
        path, or ``None`` when there is no URL or the fetch failed.
        """
        if source in self._fetched:
            return self._fetched[source]
        path: Optional[str] = None
        url = sound.get("ogg_url") or sound.get("mp3_url")
        if self.download_dir and url:
            name = self._final_name(source)
            dest = os.path.join(self.download_dir, name)
            try:
                os.makedirs(self.download_dir, exist_ok=True)
                cached = verify_sidecar(dest)
                self.downloader(str(url), dest)
                if os.path.isfile(dest):
                    path = dest
                    self.local[name] = dest
                    if cached:
                        print(f"audio cached: {source}", file=sys.stderr)
                    else:
                        print(f"audio downloaded: {source} (from {url})", file=sys.stderr)
            except Exception as exc:  # network errors must not abort the run
                print(f"audio download failed for {source}: {exc}", file=sys.stderr)
        self._fetched[source] = path
        return path

    def plan(self, record: dict) -> List[str]:
        """Return the final audio filenames chosen for this record (bounded)."""
        if not self.enabled or self.per_word <= 0:
            return []
        candidates: List[Tuple[int, str, dict]] = []
        for sound in _audio_sounds(record):
            source = _canonical_audio_name(sound)
            if not source:
                continue
            ext = os.path.splitext(source)[1].lower()
            if ext not in AUDIO_EXTENSIONS:
                continue
            score = 0
            if ext in OGG_EXTENSIONS:
                score -= 1
            if self.preferred_lang:
                tags = " ".join(str(t).lower() for t in (sound.get("tags") or []))
                if self.preferred_lang.lower() in tags:
                    score -= 2
            candidates.append((score, source, sound))
        candidates.sort(key=lambda item: (item[0], item[1]))
        chosen: List[str] = []
        seen: Set[str] = set()
        for _, source, sound in candidates:
            if source in seen:
                continue
            seen.add(source)
            keys = self._archive_keys(source, sound)
            if not self._is_available(keys) and self._fetch(source, sound) is None:
                # Unresolvable: note it and let the next recording fill the
                # slot instead of emitting a link to a file we do not have.
                if source not in self.missing:
                    self.missing.add(source)
                    print(f"audio missing: {source}", file=sys.stderr)
                continue
            name = self._final_name(source)
            aliases = self.aliases.setdefault(name, [])
            for key in keys:
                if key not in aliases:
                    aliases.append(key)
            chosen.append(name)
            if len(chosen) >= self.per_word:
                break
        for name in chosen:
            self.referenced.add(name)
        return chosen


def available_audio_keys(audio_path: str, progress: Optional[Progress] = None) -> Set[str]:
    """The set of normalised member names held in the audio archive.

    Streaming the archive once up front lets planning know which recordings can
    actually be bundled, so a missing file never becomes a link in the output.
    """
    keys: Set[str] = set()
    if not os.path.isfile(audio_path):
        return keys
    mode = "r|gz" if audio_path.endswith(".gz") else "r|"
    with tarfile.open(audio_path, mode) as tar:
        for member in tar:
            if progress is not None:
                progress.tick()
            if member.isfile():
                keys.add(_audio_match_key(member.name))
    return keys


def extract_audio(
    audio_path: str,
    wanted: Dict[str, List[str]],
    dest_dir: str,
    progress: Optional[Progress] = None,
) -> Tuple[int, List[str]]:
    """Stream the bulk tar and extract the wanted names into ``dest_dir``.

    ``wanted`` maps each final filename to its ordered candidate archive keys;
    members are matched by the normalised basename. Returns
    ``(found_count, missing_names)``.
    """
    os.makedirs(dest_dir, exist_ok=True)
    remaining = set(wanted)
    found = 0
    key_index: Dict[str, List[str]] = {}
    for name, keys in wanted.items():
        for key in keys:
            key_index.setdefault(key, []).append(name)
    if not wanted or not os.path.isfile(audio_path):
        return 0, sorted(remaining)
    mode = "r|gz" if audio_path.endswith(".gz") else "r|"
    with tarfile.open(audio_path, mode) as tar:
        for member in tar:
            if not member.isfile():
                continue
            owners = key_index.get(_audio_match_key(member.name))
            if not owners:
                continue
            target = next((n for n in owners if n in remaining), None)
            if target is None:
                continue
            data = tar.extractfile(member)
            if data is None:
                continue
            try:
                with open(os.path.join(dest_dir, target), "wb") as out:
                    while True:
                        block = data.read(1024 * 1024)
                        if not block:
                            break
                        out.write(block)
            finally:
                data.close()
            remaining.discard(target)
            found += 1
            if progress is not None:
                progress.tick()
            if not remaining:
                break
    return found, sorted(remaining)


def write_audio_zip(src_dir: str, dest_zip: str) -> None:
    """Write a deterministic zip of ``src_dir``'s files (sorted, fixed times)."""
    names = sorted(
        n for n in os.listdir(src_dir) if os.path.isfile(os.path.join(src_dir, n))
    )
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(os.path.join(src_dir, name), "rb") as f:
                zf.writestr(info, f.read())


# ---------------------------------------------------------------------------
# Rendering records into DSL cards
# ---------------------------------------------------------------------------

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

    def summary(self) -> str:
        return (
            f"headword cards: {self.cards}\n"
            f"source records kept: {self.kept_records}\n"
            f"malformed records skipped: {self.skipped_malformed}\n"
            f"non-lexical records skipped: {self.skipped_nonlexical}\n"
            f"inflected records not indexed: {self.skipped_inflected}\n"
            f"audio files bundled: {self.audio_found}\n"
            f"audio files referenced but missing: {self.missing_audio}"
        )


_LEADING_ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+")


def _normalize_sense_text(value) -> str:
    return re.sub(r"[\s.]+$", "", str(value).strip().lower())


def _contains_word(haystack: str, needle: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack) is not None


def _sense_key_matches_gloss(gloss_part: str, sense_key: str) -> bool:
    """Whether a translation's ``sense`` key describes one gloss part.

    Translation keys are short paraphrases taken from the translation table
    ("public house" for "A public house where ..."), so an exact prefix test
    rejects most of them. Match on either containment direction, after dropping
    a leading article, while keeping whole-word boundaries for the loose case.
    """
    key = _normalize_sense_text(sense_key)
    if not key:
        return True  # a keyless translation applies to any sense
    gloss = _normalize_sense_text(gloss_part)
    if not gloss:
        return False
    if gloss == key:
        return True
    bare = _LEADING_ARTICLE_RE.sub("", gloss)
    if gloss.startswith(key) or bare.startswith(key):
        return True
    if key.startswith(gloss) or key.startswith(bare):
        return True
    if len(key) >= 3 and _contains_word(gloss, key):
        return True
    if len(gloss) >= 3 and _contains_word(key, gloss):
        return True
    return False


def _sense_translations(record: dict, sense: dict, target_code: str) -> List[str]:
    gloss_parts = [str(g) for g in (sense.get("glosses") or []) if g]
    words: List[str] = []
    for tr in record.get("translations") or []:
        if not isinstance(tr, dict) or tr.get("code") != target_code:
            continue
        sense_key = tr.get("sense") or ""
        if sense_key and not any(_sense_key_matches_gloss(g, sense_key) for g in gloss_parts):
            continue
        word = tr.get("word") or tr.get("roman") or tr.get("alt")
        if word:
            words.append(str(word))
    # De-duplicate preserving order.
    seen: Set[str] = set()
    unique = [w for w in words if not (w in seen or seen.add(w))]
    return unique


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


def render_record(record: dict, args, audio: AudioPlan, known: Optional[Set[str]] = None) -> str:
    """Render one wiktextract record as the body lines of a DSL card."""
    lines: List[str] = []
    pos = record.get("pos") or ""
    if pos:
        lines.append(f"\t[p]{escape_dsl(pos)}[/p]")

    n = 0
    for sense in record.get("senses") or []:
        if not isinstance(sense, dict):
            continue
        glosses = [g for g in (sense.get("glosses") or []) if g]
        if not glosses:
            continue
        n += 1
        body = _tags_suffix(sense.get("tags")) + escape_dsl(" ".join(str(g) for g in glosses))
        if args.source_lang != args.target_lang:
            translations = _sense_translations(record, sense, args.target_lang)
            if translations:
                body += "  [trn]" + escape_dsl("; ".join(translations)) + "[/trn]"
        lines.append(f"\t[m{n}]{body}[/m]")
        for example in sense.get("examples") or []:
            if isinstance(example, dict):
                text = example.get("text") or example.get("english") or ""
            else:
                text = str(example)
            if text:
                lines.append(f"\t[ex]{escape_dsl(str(text))}[/ex]")

    forms = collect_forms(record)
    if forms:
        lines.append("\t[com]Forms: " + escape_dsl(", ".join(forms)) + "[/com]")

    refs = _cross_refs(record, known) if known else []
    if refs:
        links = ", ".join("[ref]" + escape_dsl(r) + "[/ref]" for r in refs)
        lines.append("\t[com]See also: " + links + "[/com]")

    sounds = [s for s in (record.get("sounds") or []) if isinstance(s, dict)]
    ipa = next((str(s["ipa"]) for s in sounds if s.get("ipa")), "")
    enpr = next((str(s["enpr"]) for s in sounds if s.get("enpr")), "")
    pron_bits: List[str] = []
    if ipa:
        pron_bits.append(f"IPA: {escape_dsl(ipa)}")
    if enpr:
        pron_bits.append(f"enPR: {escape_dsl(enpr)}")
    for name in audio.plan(record):
        pron_bits.append(f"[s]{escape_dsl(name)}[/s]")
    if pron_bits:
        lines.append("\t[com]" + "  ".join(pron_bits) + "[/com]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Translation (-lang) article
# ---------------------------------------------------------------------------
# For source != target the article is built for a *target* speaker learning the
# *source* language: source-language pronunciation, forms and examples are the
# payload; target-language words are the answer. Source attributes are kept,
# target attributes (transliteration, grammar) are dropped, because a native
# speaker reads their own script and knows their own grammar.

_POS_LABEL = {
    "noun": "сущ.", "verb": "гл.", "adj": "прил.", "adv": "нареч.",
    "pron": "мест.", "prep": "предл.", "conj": "союз", "num": "числ.",
    "intj": "межд.", "phrase": "фраза", "particle": "частица",
    "name": "имя", "abbrev": "сокр.", "contraction": "сокр.",
}

# Sense keys that are a MediaWiki header, not a sense description.
_PLACEHOLDER_SENSE_KEYS = {"", "-", "translations", "translation", "see also"}


def _translation_groups(records: Sequence[dict], target_code: str) -> List[Tuple[str, List[str]]]:
    """Ordered ``(sense_key, target_words)`` groups, de-duplicated.

    Groups are formed by the translation's own ``sense`` key (that is how the
    Wiktionary translation table is authored). Groups whose word lists are
    identical are merged, because a key and a gloss often describe the same
    sense and would otherwise render twice.
    """
    order: List[str] = []
    by_key: Dict[str, List[str]] = {}
    for record in records:
        for tr in record.get("translations") or []:
            if not isinstance(tr, dict) or tr.get("code") != target_code:
                continue
            word = tr.get("word") or tr.get("alt") or tr.get("roman")
            if not word:
                continue
            key = str(tr.get("sense") or "")
            entry = str(word)
            if key not in by_key:
                by_key[key] = []
                order.append(key)
            if entry not in by_key[key]:
                by_key[key].append(entry)

    merged: List[Tuple[str, List[str]]] = []
    seen: List[frozenset] = []
    for key in order:
        words = by_key[key]
        signature = frozenset(words)
        if signature in seen:
            continue
        seen.append(signature)
        merged.append((key, words))
    return merged


def _sense_heading(key: str, glosses: Sequence[str]) -> str:
    """A readable English heading for a sense group.

    Prefer a gloss that the key describes; otherwise use the key itself unless
    it is a MediaWiki placeholder (``Translations``), in which case fall back to
    a gloss or to no heading at all.
    """
    key_text = key.strip()
    usable_key = key_text.lower() not in _PLACEHOLDER_SENSE_KEYS
    if usable_key:
        for gloss in glosses:
            if _sense_key_matches_gloss(gloss, key_text):
                return gloss[0].upper() + gloss[1:] if gloss else gloss
        return key_text[0].upper() + key_text[1:]
    for gloss in glosses:
        return gloss[0].upper() + gloss[1:] if gloss else gloss
    return ""


def collect_profile_forms(record: dict, profile: LangProfile, limit: int = 8) -> List[str]:
    """Standard paradigm forms, compactly labelled and de-duplicated.

    Register/dialect variants and raw inflection tables are dropped, so a
    learner sees ``ran (past)`` and not ``rannest (archaic, 2nd sg.)``.
    """
    forms: List[str] = []
    seen: Set[Tuple[str, Tuple[str, ...]]] = set()
    for form in record.get("forms") or []:
        if not isinstance(form, dict):
            continue
        text = form.get("form")
        if not text:
            continue
        tags = tuple(str(t) for t in (form.get("tags") or []))
        if not profile.form_qualifies(tags):
            continue
        key = (str(text), tags)
        if key in seen:
            continue
        seen.add(key)
        label = profile.label_tags(tags)
        forms.append(f"{text} ({label})" if label else str(text))
        if len(forms) >= limit:
            break
    return forms


def _pronunciation(record: dict, profile: LangProfile) -> List[str]:
    """Transcription (per profile) and audio links for one record."""
    bits: List[str] = []
    for sound in record.get("sounds") or []:
        if not isinstance(sound, dict):
            continue
        for field in profile.pron_fields:
            value = sound.get(field)
            if value:
                bits.append(escape_dsl(str(value)))
                break
        if bits:
            break
    return bits


def _examples(record: dict, limit: int = 2, max_len: int = 160) -> List[str]:
    out: List[str] = []
    for sense in record.get("senses") or []:
        if not isinstance(sense, dict):
            continue
        for example in sense.get("examples") or []:
            if not isinstance(example, dict):
                continue
            text = str(example.get("text") or "").strip()
            if not text or len(text) > max_len:
                continue
            out.append(text)
            if len(out) >= limit:
                return out
    return out


def render_translation_record(
    record: dict,
    args,
    audio: AudioPlan,
    known: Optional[Set[str]],
    profile: LangProfile,
) -> str:
    """One DSL card for a bilingual (source -> target) dictionary."""
    groups = _translation_groups([record], args.target_lang)
    if not groups:
        return ""

    lines: List[str] = []
    pos = record.get("pos") or ""
    glosses = [
        str(g)
        for sense in record.get("senses") or []
        if isinstance(sense, dict)
        for g in (sense.get("glosses") or [])
        if g
    ]

    pron = _pronunciation(record, profile)
    for name in audio.plan(record):
        pron.append(f"[s]{escape_dsl(name)}[/s]")

    if pos:
        label = _POS_LABEL.get(str(pos), str(pos))
        lines.append(f"\t[p]{escape_dsl(label)}[/p]")

    for index, (key, words) in enumerate(groups, 1):
        heading = _sense_heading(key, glosses)
        body = escape_dsl(heading) if heading else ""
        equivalents = "  ".join(escape_dsl(w) for w in words)
        if body:
            lines.append(f"\t[m{index}]{body}[/m]")
            lines.append(f"\t\t{equivalents}")
        else:
            lines.append(f"\t[m{index}]{equivalents}[/m]")

    # Source-language extras: useful for a learner, hidden by default.
    extras: List[str] = []
    for example in _examples(record):
        extras.append(f"\t[ex]{escape_dsl(example)}[/ex]")
    forms = collect_profile_forms(record, profile)
    if forms and not profile.strip_forms:
        extras.append("\t[com]Forms: " + escape_dsl(", ".join(forms)) + "[/com]")
    if known:
        refs = _cross_refs(record, known)
        if refs:
            links = ", ".join("[ref]" + escape_dsl(r) + "[/ref]" for r in refs)
            extras.append("\t[com]See also: " + links + "[/com]")
    if pron:
        extras.append("\t[com]" + "  ".join(pron) + "[/com]")
    if extras:
        lines.append("\t[*]")
        lines.extend(extras)
        lines.append("\t[/opt]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

_PREVIEW_TAGS = {
    "p": ("span", {"class": "pos"}),
    "m": ("div", {"class": "sense"}),
    "ex": ("div", {"class": "example"}),
    "trn": ("span", {"class": "trn"}),
    "com": ("div", {"class": "note"}),
    "b": ("b", {}),
    "i": ("i", {}),
    "u": ("u", {}),
    "ref": ("a", {"href": "#"}),
}

def dsl_to_html(text: str) -> str:
    """A small renderer for the DSL subset this tool emits (for preview only)."""
    from html import escape as _h

    out: List[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            out.append(_h(text[i + 1]))
            i += 2
            continue
        if ch == "[":
            close = text.find("]", i)
            slash = text.find("/]", i)
            if close != -1 and slash == close - 1 and i > 0:
                # closing tag; the optional-zone close maps to its own element
                if text[i + 1:slash].strip() == "opt":
                    out.append("</div>")
                else:
                    out.append("</>")
                i = close + 1
                continue
            if close != -1:
                name = text[i + 1:close]
                base = re.match(r"m\d*", name)
                key = base.group(0) if base else name
                if key.startswith("m"):
                    out.append('<span class="sense">')
                elif key == "*":
                    out.append('<div class="optional"><span class="optlabel">[optional]</span> ')
                elif key == "s":
                    inner_end = text.find("[/s]", close + 1)
                    if inner_end != -1:
                        out.append('<span class="audio">&#9835; ' + _h(text[close + 1:inner_end]) + "</span>")
                        i = inner_end + 4
                        continue
                elif key in _PREVIEW_TAGS:
                    tag, attrs = _PREVIEW_TAGS[key]
                    attr = "".join(f' {k}="{_h(v)}"' for k, v in attrs.items())
                    out.append(f"<{tag}{attr}>")
                i = close + 1
                continue
        out.append(_h(ch))
        i += 1
    html = "".join(out)
    html = html.replace("</>", "")
    return html


def render_preview(name: str, dsl_text: str, dest_html: str) -> None:
    """Write a human-readable HTML preview of the generated cards."""
    lines = dsl_text.splitlines()
    cards: List[Tuple[str, List[str]]] = []
    headword: Optional[str] = None
    body: List[str] = []
    for line in lines:
        if line.startswith("#"):
            continue
        if line and not line[0].isspace():
            if headword is not None:
                cards.append((headword, body))
            headword, body = line, []
        elif headword is not None:
            body.append(line)
    if headword is not None:
        cards.append((headword, body))

    parts = [
        "<!doctype html><meta charset='utf-8'>",
        f"<title>{name} preview</title>",
        "<style>body{font-family:sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}"
        "h2{border-bottom:1px solid #ccc;margin-top:2rem}.pos{font-weight:bold;color:#0a6}"
        ".sense{margin:.2em 0 .2em 1em}.example{color:#555;margin-left:2em;font-style:italic}"
        ".note{color:#777;font-size:.9em}.trn{color:#06c}.audio{color:#a0a}"
        ".optional{border-left:3px solid #cc0;background:#ffd;padding:.4em .6em;margin:.6em 0}"
        ".optlabel{color:#880;font-size:.8em;text-transform:uppercase}</style>",
        f"<h1>{name} — preview</h1>",
    ]
    for headword, body in cards:
        parts.append(f"<h2>{dsl_to_html(headword)}</h2>")
        parts.append("<div>" + "<br>".join(dsl_to_html(b) for b in body) + "</div>")
    with open(dest_html, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")


# ---------------------------------------------------------------------------
# Build pipeline
# ---------------------------------------------------------------------------

def _language_name(record: Optional[dict], code: str) -> str:
    if record and record.get("lang"):
        return str(record["lang"])
    return code.upper()


def _find_target_language_name(jsonl_path: str, source_code: str, target_code: str) -> Optional[str]:
    for _, record in iter_records(jsonl_path):
        if not record or record.get("lang_code") != source_code:
            continue
        for tr in record.get("translations") or []:
            if isinstance(tr, dict) and tr.get("code") == target_code and tr.get("lang"):
                return str(tr["lang"])
    return None


def build(args) -> Report:
    report = Report()

    if not args.target_lang:
        args.target_lang = args.source_lang

    if not args.jsonl:
        if not args.dump_date:
            raise SystemExit("--dump-date is required when downloading (or pass --jsonl)")
        if not args.skip_date_check:
            try:
                current = _fetch_dump_date(args.timeout)
            except (urllib.error.URLError, TimeoutError) as exc:
                raise SystemExit(f"could not verify snapshot date: {exc}")
            if current and current != args.dump_date:
                raise SystemExit(
                    f"pinned dump date {args.dump_date} does not match the current "
                    f"kaikki.org snapshot ({current}); re-run with --dump-date {current} "
                    f"or pass --skip-date-check"
                )

    snapshot = Snapshot(args.dump_date, args.cache_dir, args.jsonl_url, args.audio_url)
    jsonl_path = args.jsonl
    if not jsonl_path:
        jsonl_path = download_cached(
            snapshot.jsonl_url, snapshot.jsonl_path, args.force_download, args.timeout
        )

    want_audio = (not args.no_audio) and args.audio_per_word > 0
    audio_path: Optional[str] = None
    available: Optional[Set[str]] = None
    if want_audio:
        # Resolve the archive up front so planning only references recordings
        # it actually holds; a missing file is logged and left out instead of
        # becoming a dead link, and does not use up a per-word slot.
        audio_path = args.audio_tar
        if not audio_path:
            audio_path = download_cached(
                snapshot.audio_url, snapshot.audio_path, args.force_download, args.timeout
            )
        scan = Progress("scanning audio archive")
        available = available_audio_keys(audio_path, scan)
        scan.done()
        if not available:
            print(
                f"warning: no audio found in {audio_path}; audio will not be bundled",
                file=sys.stderr,
            )
    download_dir = None
    if want_audio and not args.no_audio_download:
        download_dir = os.path.join(snapshot.dir, "audio-cache")
    downloader = args.audio_downloader
    if downloader is None and download_dir is not None:
        timeout = args.timeout

        def downloader(url: str, dest: str) -> str:  # type: ignore[misc]
            return download_cached(url, dest, timeout=timeout)

    audio = AudioPlan(
        args.audio_per_word, args.audio_lang, want_audio, available, downloader
    )
    audio.download_dir = download_dir

    # First pass: the set of indexed headwords, so cross-references never point
    # at words this dictionary does not contain. For a sample this is the
    # emitted subset (deterministic), keeping refs live in sampled output too.
    selecting = Progress("selecting headwords")
    known = select_headwords(
        jsonl_path, args.source_lang, args.sample, args.sample_mode, selecting
    )
    selecting.done()

    header_name = args.name or f"kaikki-{args.source_lang}-{args.target_lang}"

    out_lines: List[str] = []
    header_lines: List[str] = []

    target_name = args.target_lang
    if args.target_lang != args.source_lang:
        target_name = _find_target_language_name(jsonl_path, args.source_lang, args.target_lang) or args.target_lang

    profile = get_lang_profile(args.source_lang)
    translation_mode = args.translation and args.target_lang != args.source_lang
    if args.translation and not translation_mode:
        print(
            "warning: --translation needs a distinct --target-lang; ignoring it",
            file=sys.stderr,
        )

    current_word: Optional[str] = None
    current_records: List[dict] = []
    source_lang_name = args.source_lang.upper()

    def flush() -> None:
        nonlocal current_word, current_records, source_lang_name
        if not current_records:
            return
        record = current_records[0]
        source_lang_name = _language_name(record, args.source_lang)
        headwords = [clean_headword(current_word)]
        if args.include_inflections:
            for form in collect_forms(record):
                form_word = re.split(r"\s+\(", form, maxsplit=1)[0].strip()
                if form_word and form_word != current_word:
                    headwords.append(clean_headword(form_word))
        if translation_mode:
            bodies = [
                render_translation_record(r, args, audio, known, profile)
                for r in current_records
            ]
        else:
            bodies = [render_record(r, args, audio, known) for r in current_records]
        bodies = [b for b in bodies if b]
        if not bodies:
            current_word, current_records = None, []
            return
        out_lines.append("\n".join(headwords))
        out_lines.extend(bodies)
        report.cards += 1
        report.kept_records += len(current_records)
        current_word, current_records = None, []

    source_seen = False
    rendering = Progress("rendering")
    for _, record in iter_records(jsonl_path, rendering):
        if record is None:
            report.skipped_malformed += 1
            continue
        if record.get("lang_code") != args.source_lang:
            report.out_of_pair += 1
            continue
        source_seen = True
        if not is_lexical(record):
            if not is_inflected(record):
                report.skipped_nonlexical += 1
            else:
                report.skipped_inflected += 1
            continue
        if is_inflected(record):
            report.skipped_inflected += 1
            continue
        word = str(record.get("word"))
        if args.sample and word not in known:
            continue
        if word != current_word:
            flush()
            if args.sample and report.cards >= args.sample:
                break
            current_word = word
        current_records.append(record)
    flush()
    rendering.done()

    if not source_seen or report.cards == 0:
        raise SystemExit(
            f"unsupported language pair: no {args.source_lang!r} headwords were found "
            f"in this snapshot ({args.source_lang}/{args.target_lang})"
        )

    contents_name = source_lang_name if args.target_lang == args.source_lang else str(target_name)
    header_lines.append(f'#NAME "{header_arg(header_name)}"')
    header_lines.append(f'#INDEX_LANGUAGE "{header_arg(source_lang_name)}"')
    header_lines.append(f'#CONTENTS_LANGUAGE "{header_arg(contents_name)}"')

    about = [
        clean_headword("About this dictionary"),
        "\t[com]Source: Wiktionary (via kaikki.org / wiktextract)[/com]",
        f"\t[com]License: {WIKTIONARY_LICENSE} (attribution required, share-alike)[/com]",
        f"\t[com]Citation: {escape_dsl(WIKTEXTRACT_CITATION)}[/com]",
        f"\t[com]Snapshot dump date: {escape_dsl(args.dump_date or 'unknown')}[/com]",
        f"\t[com]Language pair: {escape_dsl(args.source_lang)}/{escape_dsl(args.target_lang)}[/com]",
        f"\t[com]Generated by scripts/kaikki-to-dsl.py; this is a derivative work.[/com]",
    ]

    dsl_text = "\n".join(header_lines) + "\n\n" + "\n".join(about) + "\n" + "\n".join(out_lines) + "\n"

    os.makedirs(args.out_dir, exist_ok=True)
    dz_path = os.path.join(args.out_dir, header_name + ".dsl.dz")
    with open(dz_path, "wb") as f:
        f.write(make_dictzip(encode_dsl(dsl_text)))

    if args.preview:
        preview_path = os.path.join(args.out_dir, header_name + ".preview.html")
        render_preview(header_name, dsl_text, preview_path)
        print(f"wrote {preview_path}", file=sys.stderr)

    if want_audio and audio.referenced:
        with tempfile.TemporaryDirectory(prefix="kaikki-audio-") as tmp:
            fetched = {
                name: path
                for name, path in audio.local.items()
                if name in audio.referenced and os.path.isfile(path)
            }
            for name, path in fetched.items():
                shutil.copyfile(path, os.path.join(tmp, name))
            wanted = {
                name: list(audio.aliases.get(name, []))
                for name in sorted(audio.referenced)
                if name not in fetched
            }
            batching = Progress("bundling audio", every=1, total=len(audio.referenced))
            found, missing = extract_audio(audio_path, wanted, tmp, batching)
            batching.done()
            report.audio_found = len(fetched) + found
            if missing:
                print(
                    f"warning: {len(missing)} planned audio file(s) were not found in "
                    f"the archive while bundling",
                    file=sys.stderr,
                )
            if args.audio_layout == "zip":
                write_audio_zip(tmp, dz_path + ".files.zip")
            else:
                dest_dir = dz_path + ".files"
                os.makedirs(dest_dir, exist_ok=True)
                for name in sorted(os.listdir(tmp)):
                    src = os.path.join(tmp, name)
                    if os.path.isfile(src):
                        with open(src, "rb") as fsrc, open(os.path.join(dest_dir, name), "wb") as fdst:
                            fdst.write(fsrc.read())

    report.missing_audio = len(audio.missing)
    print(f"wrote {dz_path}", file=sys.stderr)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaikki-to-dsl.py",
        description="Build an importable DSL dictionary from a pinned kaikki.org "
        "Wiktionary snapshot for a language pair.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Notes:\n"
            "  Base forms are the only indexed headwords by default. With\n"
            "  --include-inflections a base word's inflected forms are added as\n"
            "  extra headword lines on its card; in DSL every indexed word also\n"
            "  appears in the suggestion list (there is no hidden-alias concept),\n"
            "  so enable it only when direct lookup of inflected forms is wanted.\n\n"
            "  Audio is bundled at most --audio-per-word times per headword,\n"
            "  de-duplicated. A recording the archive lacks is fetched from its\n"
            "  Wikimedia URL and cached (--no-audio-download disables that); one\n"
            "  that cannot be resolved is logged and left out rather than emitted\n"
            "  as a broken link, and it does not use up a per-word slot.\n"
            "  --no-audio (or --audio-per-word 0) disables audio entirely and\n"
            "  skips downloading the audio archive.\n\n"
            "  The output is <name>.dsl.dz plus <name>.dsl.dz.files.zip (or the\n"
            "  .files/ directory with --audio-layout dir).\n\n"
            "  --translation builds a dictionary for a speaker of --target-lang\n"
            "  learning --source-lang: senses come from the source's translation\n"
            "  table (grouped by its sense keys), the target words are the answer,\n"
            "  and source pronunciation, forms and examples are tucked into the\n"
            "  collapsible optional zone ([*]...[/opt]).\n"
        ),
    )
    parser.add_argument("--source-lang", required=True, help="ISO code of the indexed headword language (e.g. en)")
    parser.add_argument("--target-lang", help="ISO code of the gloss/translation language (defaults to source)")
    parser.add_argument("--dump-date", help="pinned kaikki.org dump date (YYYY-MM-DD); required unless --jsonl")
    parser.add_argument("--jsonl", help="use a local wiktextract JSONL(.gz) instead of downloading")
    parser.add_argument("--audio-tar", help="use a local Wiktionary audio tar instead of downloading")
    parser.add_argument("--jsonl-url", default=RAW_JSONL_URL, help="override the JSONL source URL")
    parser.add_argument("--audio-url", default=AUDIO_TAR_URL, help="override the audio archive URL")
    parser.add_argument("--cache-dir", default=os.path.join(os.path.expanduser("~"), ".cache", "aurelex-kaikki"))
    parser.add_argument("--out-dir", default="dist")
    parser.add_argument("--name", help="dictionary/output base name (default kaikki-<source>-<target>)")
    parser.add_argument("--include-inflections", action="store_true", help="also index inflected forms (adds them to suggestions)")
    parser.add_argument(
        "--translation",
        action="store_true",
        help="build a learner's translation dictionary (needs a distinct "
             "--target-lang): target-language equivalents per sense, with the "
             "source language's pronunciation, forms and examples hidden in a "
             "collapsible block",
    )
    parser.add_argument("--audio-per-word", type=int, default=3, help="max audio files per headword (default 3)")
    parser.add_argument("--no-audio", action="store_true", help="do not bundle audio (and do not download the archive)")
    parser.add_argument("--audio-lang", help="prefer audio whose tags match this language/accent (e.g. US)")
    parser.add_argument(
        "--no-audio-download",
        action="store_true",
        help="do not fetch audio missing from the archive from Wikimedia (tar only)",
    )
    parser.add_argument("--audio-layout", choices=["zip", "dir"], default="zip", help="how to bundle audio (default zip)")
    parser.set_defaults(audio_downloader=None, translation=False)
    parser.add_argument("--sample", type=int, help="emit only N headwords")
    parser.add_argument(
        "--sample-mode", choices=["first", "random"], default="first",
        help="how --sample picks headwords: first N in file order, or a "
        "deterministic random subset across the whole snapshot (default first)",
    )
    parser.add_argument("--preview", action="store_true", help="also write a human-readable HTML preview")
    parser.add_argument("--force-download", action="store_true", help="re-download cached files")
    parser.add_argument("--skip-date-check", action="store_true", help="skip verifying the dump date against kaikki.org")
    parser.add_argument("--timeout", type=int, default=60, help="network timeout in seconds (default 60)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.target_lang:
        args.target_lang = args.source_lang
    report = build(args)
    print(report.summary(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
