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
import importlib.util
import json
import os
import re
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple

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


# ---------------------------------------------------------------------------
# Reading / filtering records
# ---------------------------------------------------------------------------

def open_text_maybe_gzip(path: str):
    with open(path, "rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "rt", encoding="utf-8", errors="replace")


def iter_records(path: str) -> Iterator[Tuple[int, Optional[dict]]]:
    """Yield ``(line_number, record_or_None)``; ``None`` marks a malformed line."""
    with open_text_maybe_gzip(path) as stream:
        for line_no, line in enumerate(stream, 1):
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


def iter_candidate_headwords(path: str, source_code: str) -> Iterator[str]:
    """Yield headword candidates (source language, lexical, not inflected)."""
    for _, record in iter_records(path):
        if record is None or record.get("lang_code") != source_code:
            continue
        if not is_lexical(record) or is_inflected(record):
            continue
        word = record.get("word")
        if word:
            yield str(word)


def select_headwords(
    path: str, source_code: str, sample: Optional[int], sample_mode: str
) -> Set[str]:
    """The set of headwords that will be indexed (drives cross-reference safety).

    Without ``--sample`` this is every candidate headword. With ``--sample`` it
    is the emitted subset: the first N candidates (``first``) or a deterministic
    random subset (``random``) chosen by the smallest sha256 keys, so the same
    snapshot and options always select the same words.
    """
    if not sample:
        return set(iter_candidate_headwords(path, source_code))
    if sample_mode == "first":
        selected: Set[str] = set()
        for word in iter_candidate_headwords(path, source_code):
            selected.add(word)
            if len(selected) >= sample:
                break
        return selected
    heap: List[Tuple[int, str]] = []  # max-heap of (-key, word), size <= sample
    for word in iter_candidate_headwords(path, source_code):
        key = int.from_bytes(hashlib.sha256(word.encode("utf-8")).digest()[:8], "big")
        if len(heap) < sample:
            heapq.heappush(heap, (-key, word))
        elif (key, word) < (-heap[0][0], heap[0][1]):
            heapq.heapreplace(heap, (-key, word))
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


def _audio_sounds(record: dict) -> List[dict]:
    return [s for s in (record.get("sounds") or []) if isinstance(s, dict) and s.get("audio")]


class AudioPlan:
    """Assign collision-free final filenames and remember what is referenced."""

    def __init__(self, per_word: int, preferred_lang: Optional[str], enabled: bool) -> None:
        self.per_word = per_word
        self.preferred_lang = preferred_lang
        self.enabled = enabled
        self._owner: Dict[str, str] = {}   # final_name -> source url
        self.referenced: Set[str] = set()

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

    def plan(self, record: dict) -> List[str]:
        """Return the final audio filenames chosen for this record (bounded)."""
        if not self.enabled or self.per_word <= 0:
            return []
        candidates: List[Tuple[int, str, str]] = []
        for sound in _audio_sounds(record):
            source = sound["audio"]
            base = _basename(source)
            ext = os.path.splitext(base)[1].lower()
            if ext not in AUDIO_EXTENSIONS:
                continue
            score = 0
            if ext in OGG_EXTENSIONS:
                score -= 1
            if self.preferred_lang:
                tags = " ".join(str(t).lower() for t in (sound.get("tags") or []))
                if self.preferred_lang.lower() in tags:
                    score -= 2
            candidates.append((score, base, source))
        candidates.sort(key=lambda item: (item[0], item[1]))
        chosen: List[str] = []
        seen: Set[str] = set()
        for _, base, source in candidates:
            if base in seen:
                continue
            seen.add(base)
            chosen.append(self._final_name(source))
            if len(chosen) >= self.per_word:
                break
        for name in chosen:
            self.referenced.add(name)
        return chosen


def extract_audio(audio_path: str, wanted: Set[str], dest_dir: str) -> Tuple[int, List[str]]:
    """Stream the bulk tar and extract the wanted basenames into ``dest_dir``.

    Returns ``(found_count, missing_names)``. Members are matched by basename.
    """
    os.makedirs(dest_dir, exist_ok=True)
    remaining = set(wanted)
    found = 0
    collisions: Set[str] = set()
    if not wanted or not os.path.isfile(audio_path):
        return 0, sorted(remaining)
    mode = "r|gz" if audio_path.endswith(".gz") else "r|"
    with tarfile.open(audio_path, mode) as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = _basename(member.name)
            if name not in remaining:
                continue
            if name in collisions:
                continue
            data = tar.extractfile(member)
            if data is None:
                continue
            try:
                with open(os.path.join(dest_dir, name), "wb") as out:
                    while True:
                        block = data.read(1024 * 1024)
                        if not block:
                            break
                        out.write(block)
            finally:
                data.close()
            remaining.discard(name)
            found += 1
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


def _sense_translations(record: dict, sense: dict, target_code: str) -> List[str]:
    def norm(value: str) -> str:
        return re.sub(r"[\s.]+$", "", str(value).strip().lower())

    gloss = norm(" ".join(str(g) for g in (sense.get("glosses") or []) if g))
    words: List[str] = []
    for tr in record.get("translations") or []:
        if not isinstance(tr, dict) or tr.get("code") != target_code:
            continue
        sense_text = norm(tr.get("sense") or "")
        if gloss and sense_text and not (
            gloss.startswith(sense_text) or sense_text.startswith(gloss)
        ):
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

    sounds = _audio_sounds(record)
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
                # closing tag
                out.append("</>")
                i = close + 1
                continue
            if close != -1:
                name = text[i + 1:close]
                base = re.match(r"m\d*", name)
                key = base.group(0) if base else name
                if key.startswith("m"):
                    out.append('<span class="sense">')
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
        ".note{color:#777;font-size:.9em}.trn{color:#06c}.audio{color:#a0a}</style>",
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
    audio = AudioPlan(args.audio_per_word, args.audio_lang, want_audio)

    # First pass: the set of indexed headwords, so cross-references never point
    # at words this dictionary does not contain. For a sample this is the
    # emitted subset (deterministic), keeping refs live in sampled output too.
    known = select_headwords(jsonl_path, args.source_lang, args.sample, args.sample_mode)

    header_name = args.name or f"kaikki-{args.source_lang}-{args.target_lang}"

    out_lines: List[str] = []
    header_lines: List[str] = []

    target_name = args.target_lang
    if args.target_lang != args.source_lang:
        target_name = _find_target_language_name(jsonl_path, args.source_lang, args.target_lang) or args.target_lang

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
    for _, record in iter_records(jsonl_path):
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
        audio_path = args.audio_tar
        if not audio_path:
            audio_path = download_cached(
                snapshot.audio_url, snapshot.audio_path, args.force_download, args.timeout
            )
        with tempfile.TemporaryDirectory(prefix="kaikki-audio-") as tmp:
            found, missing = extract_audio(audio_path, audio.referenced, tmp)
            report.audio_found = found
            report.missing_audio = len(missing)
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
            "  de-duplicated. --no-audio (or --audio-per-word 0) disables it and\n"
            "  skips downloading the audio archive.\n\n"
            "  The output is <name>.dsl.dz plus <name>.dsl.dz.files.zip (or the\n"
            "  .files/ directory with --audio-layout dir).\n"
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
    parser.add_argument("--audio-per-word", type=int, default=3, help="max audio files per headword (default 3)")
    parser.add_argument("--no-audio", action="store_true", help="do not bundle audio (and do not download the archive)")
    parser.add_argument("--audio-lang", help="prefer audio whose tags match this language/accent (e.g. US)")
    parser.add_argument("--audio-layout", choices=["zip", "dir"], default="zip", help="how to bundle audio (default zip)")
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
