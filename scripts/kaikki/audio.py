"""Audio planning and extraction"""

from __future__ import annotations

import hashlib
import html
import os
import shutil
import sys
import tarfile
import zipfile
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote

from .constants import AUDIO_EXTENSIONS, OGG_EXTENSIONS
from .snapshot import Progress, describe_failure, download_cached, failure_is_permanent, verify_sidecar


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

#: Characters a filename may not carry on Windows. The archive's MediaWiki
#: names are not filenames, and a run that extracts one verbatim dies on the
#: first recording that uses a quote.
_UNSAFE_FILENAME_CHARS = '<>:"/\\|?*'

#: Windows device names that cannot be used as a file stem, extension or not.
_RESERVED_FILENAME_STEMS = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)

def _safe_audio_filename(name: str) -> str:
    """Make a bundled recording's name usable as a file on every platform.

    The name is also the DSL reference to the bundled file, so it has to be
    both a legal filename and identical in the article and the archive. Every
    character the filesystem refuses becomes ``_`` (Windows rejects ``"``,
    ``:``, ``*`` and friends outright, so extracting a recording that used one
    aborted the whole run); a trailing space or dot, which Windows silently
    strips, is dropped; and a device name such as ``CON`` is prefixed so it
    does not name a device. The mapping is deterministic, and any collision it
    introduces is resolved by the digest suffix in
    :meth:`AudioPlan._final_name`.
    """
    cleaned = "".join(
        "_" if ch in _UNSAFE_FILENAME_CHARS or ord(ch) < 0x20 else ch
        for ch in name
    )
    cleaned = cleaned.rstrip(" .")
    if not cleaned:
        return "audio"
    stem = os.path.splitext(cleaned)[0]
    if stem.upper() in _RESERVED_FILENAME_STEMS:
        return "_" + cleaned
    return cleaned

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
        dead: Optional[Set[str]] = None,
        on_gone=None,
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
        # Recordings an earlier run found permanently gone, by match key. A
        # definitive refusal is not worth repeating, so such a candidate is
        # neither requested nor allowed to consume a per-word slot; the next
        # candidate fills it, exactly as if the fetch had just failed. The keys
        # are folded when loaded, matching how they are looked up.
        self.dead: Set[str] = {_audio_match_key(name) for name in (dead or ())}
        # ``on_gone(dest, url, reason)`` records a newly-dead file so a later run
        # can skip it; without one the build cannot learn across runs.
        self.on_gone = on_gone
        self._owner: Dict[str, str] = {}   # final_name -> source url
        self.referenced: Set[str] = set()
        self.aliases: Dict[str, List[str]] = {}  # final_name -> archive match keys
        self.local: Dict[str, str] = {}    # final_name -> fetched file on disk
        self.missing: Set[str] = set()     # referenced sources not bundled
        self._fetched: Dict[str, Optional[str]] = {}  # source -> local path or None
        self.cached_hits = 0               # recordings served from the local cache
        self.on_cached = None              # optional callback(count) for progress

    def _final_name(self, source: str) -> str:
        base = _safe_audio_filename(_basename(source))
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

    def _is_gone(self, source: str) -> bool:
        """Whether an earlier run found this recording permanently gone."""
        return _audio_match_key(self._final_name(source)) in self.dead

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
                        # Served from the cache: this can happen tens of
                        # thousands of times over a large dictionary, and one
                        # console line each would dominate the run. Count them
                        # and let the caller show a coarse progress instead.
                        self.cached_hits += 1
                        if self.on_cached is not None:
                            self.on_cached(self.cached_hits)
                    else:
                        print(f"audio downloaded: {source} (from {url})", file=sys.stderr)
            except Exception as exc:  # network errors must not abort the run
                if failure_is_permanent(exc):
                    # A definitive answer: the file is gone, not merely refused,
                    # so record it and let no later run ask for it again.
                    reason = describe_failure(exc)
                    self.dead.add(_audio_match_key(name))
                    if self.on_gone is not None:
                        self.on_gone(dest, str(url), reason)
                    else:
                        print(f"audio gone ({reason}): {source}", file=sys.stderr)
                else:
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
            if not self._is_available(keys):
                if self._is_gone(source):
                    # Known permanently gone: still counted as missing, so the
                    # article's shortfall is reported the same every run, but
                    # never requested again -- the next recording fills the slot.
                    self.missing.add(source)
                    continue
                if self._fetch(source, sound) is None:
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

def _archive_identity(audio_path: str) -> str:
    """A cheap fingerprint of the archive, for validating a cached index.

    Records the absolute path plus size, mtime and (when present) the sha256
    sidecar. Any of these changing means the archive was replaced or
    re-downloaded, so a cached name index is stale and must be rebuilt. The path
    is included so two different archives can never share a cache entry.
    """
    st = os.stat(audio_path)
    parts = [
        "path=" + os.path.abspath(audio_path),
        f"size={st.st_size}",
        f"mtime={int(st.st_mtime)}",
    ]
    sidecar = audio_path + ".sha256"
    if os.path.isfile(sidecar):
        with open(sidecar, "r", encoding="ascii") as f:
            parts.append("sha256=" + f.read().strip())
    return "|".join(parts)

def available_audio_keys(
    audio_path: str,
    progress: Optional[Progress] = None,
    cache_dir: Optional[str] = None,
    force: bool = False,
) -> Set[str]:
    """The set of normalised member names held in the audio archive.

    Streaming the archive once up front lets planning know which recordings can
    actually be bundled, so a missing file never becomes a link in the output.
    Because the archive is large and never changes for a given dump date, the
    resulting name set is cached beside it and keyed to the archive's identity
    (size, mtime and sha256 sidecar), so it is rebuilt only when the archive
    actually changes.
    """
    keys: Set[str] = set()
    if not os.path.isfile(audio_path):
        return keys

    # The index lives beside the archive it describes, so two archives can never
    # share an entry even when a caller points at a different one.
    cache_path = (audio_path + ".keys.txt") if cache_dir else None
    identity = _archive_identity(audio_path)
    if cache_path and not force and os.path.isfile(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                header = f.readline().rstrip("\n")
                if header == identity:
                    for line in f:
                        name = line.rstrip("\n")
                        if name:
                            keys.add(name)
                    print(
                        f"audio index: {len(keys):,} names (cached)",
                        file=sys.stderr,
                    )
                    return keys
        except OSError:
            keys = set()

    keys = set()
    mode = "r|gz" if audio_path.endswith(".gz") else "r|"
    with tarfile.open(audio_path, mode) as tar:
        for member in tar:
            if progress is not None:
                progress.tick()
            if member.isfile():
                keys.add(_audio_match_key(member.name))

    if cache_path:
        try:
            part = cache_path + ".part"
            with open(part, "w", encoding="utf-8") as f:
                f.write(identity + "\n")
                for name in sorted(keys):
                    f.write(name + "\n")
            os.replace(part, cache_path)
        except OSError as exc:
            print(f"warning: could not cache the audio index: {exc}", file=sys.stderr)
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

def write_bundle(
    sources: Dict[str, str],
    dest: str,
    layout: str,
    progress: Optional[Progress] = None,
) -> None:
    """Write the resource bundle from a name -> source-path map.

    The caller hands the *location* of every entry -- an icon in the assets, a
    recording in the download cache, or one extracted from the archive into a
    temporary directory -- so a file already sitting in the cache is read once,
    into the bundle, instead of being copied into a staging directory first.

    A zip bundle is written deterministically (names sorted, fixed timestamps)
    and **stored, not deflated**: it is almost all audio that is already
    compressed, so deflating tens of thousands of files spends minutes of CPU
    for no size gain. Each entry is streamed rather than read whole, so peak
    memory does not track the largest recording. The directory layout copies
    each source to ``dest`` under its bundle name.
    """
    names = sorted(sources)
    if layout == "zip":
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as zf:
            for name in names:
                path = sources[name]
                info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o644 << 16
                info.file_size = os.path.getsize(path)
                with open(path, "rb") as f, zf.open(info, "w") as entry:
                    shutil.copyfileobj(f, entry, 1024 * 1024)
                if progress is not None:
                    progress.tick()
        return
    os.makedirs(dest, exist_ok=True)
    for name in names:
        with open(sources[name], "rb") as fsrc, open(
            os.path.join(dest, name), "wb"
        ) as fdst:
            shutil.copyfileobj(fsrc, fdst, 1024 * 1024)
        if progress is not None:
            progress.tick()

def bundle_entry_names(path: str) -> Optional[Set[str]]:
    """The entry names of an existing resource bundle, or None when absent.

    Reads only the zip's index (central directory) or the directory listing,
    never a resource, so it is cheap enough to check a bundle for reuse.
    """
    if os.path.isfile(path):
        try:
            with zipfile.ZipFile(path) as zf:
                return set(zf.namelist())
        except (OSError, zipfile.BadZipFile):
            return None
    if os.path.isdir(path):
        return {
            n for n in os.listdir(path) if os.path.isfile(os.path.join(path, n))
        }
    return None
