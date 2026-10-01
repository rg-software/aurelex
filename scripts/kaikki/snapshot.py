"""Snapshot model and cached download"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import List, Optional, Sequence, Set
from urllib.parse import quote, urlsplit, urlunsplit

from .constants import AUDIO_TAR_URL, RAWDATA_PAGE_URL, RAW_JSONL_URL, USER_AGENT, _DOWNLOAD_MAX_BACKOFF_SECONDS, _DOWNLOAD_RETRIES, _DOWNLOAD_SPACING_SECONDS


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

_last_request_time = 0.0

def _throttle(gap: Optional[float] = None) -> None:
    """Sleep so consecutive requests to the same host stay polite."""
    global _last_request_time
    spacing = _DOWNLOAD_SPACING_SECONDS if gap is None else gap
    elapsed = time.time() - _last_request_time
    if elapsed < spacing:
        time.sleep(spacing - elapsed)
    _last_request_time = time.time()

def _ascii_url(url: str) -> str:
    """Percent-encode a URL's non-ASCII parts so urllib can send it.

    A wiktextract audio URL may carry a raw Unicode title (``zh-xiàn.ogg``),
    and ``urllib`` writes the request line as ASCII, so sending it unescaped
    fails with ``'ascii' codec can't encode character``. Quote the path and
    query while leaving the scheme, host and existing escapes untouched.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    path = quote(parts.path, safe="/%:@!$&'()*+,;=~")
    query = quote(parts.query, safe="=&%:@!$'()*+,;/?~")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))

def _retry_after_seconds(exc: urllib.error.HTTPError) -> Optional[float]:
    """The server's own requested wait, in seconds, if it sent one.

    Wikimedia sets ``Retry-After`` on a 429 with its robot-policy cooldown, and
    that is the number it will actually hold us to; guessing a shorter backoff
    just earns another 429. Returns ``None`` when the header is absent or
    unparseable, leaving the caller on its own exponential schedule.
    """
    headers = getattr(exc, "headers", None)
    if headers is None:
        return None
    try:
        raw = headers.get("Retry-After")
    except AttributeError:
        return None
    if not raw:
        return None
    try:
        seconds = float(str(raw).strip())
    except ValueError:
        # the header may also be an HTTP-date; we cannot parse one without a
        # full date library, and the exponential fallback is the safe answer
        return None
    return max(0.0, seconds)

def _open_with_retries(
    url: str,
    timeout: int,
    retries: Optional[int] = None,
    spacing: Optional[float] = None,
    max_backoff: Optional[float] = None,
):
    """Open ``url``, retrying rate limits and transient server errors.

    Wikimedia answers an over-eager client with 429 (sometimes with a robot-policy
    message); backing off and retrying turns that into a slow success rather than
    a missing file. A ``Retry-After`` on the response overrides the computed
    backoff, capped by ``max_backoff`` so a hostile or mistaken header cannot
    park the run for hours.

    ``retries``/``spacing``/``max_backoff`` default to the module-level policy;
    the audio prefetcher passes its own, because filling a large cache back is a
    different job from fetching a handful of files during a build.
    """
    last: Optional[Exception] = None
    url = _ascii_url(url)
    attempts = _DOWNLOAD_RETRIES if retries is None else max(1, retries)
    gap = _DOWNLOAD_SPACING_SECONDS if spacing is None else max(0.0, spacing)
    ceiling = _DOWNLOAD_MAX_BACKOFF_SECONDS if max_backoff is None else max_backoff
    for attempt in range(attempts):
        _throttle(gap)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            delay = min(ceiling, gap * (2 ** attempt))
            asked = _retry_after_seconds(exc)
            if asked is not None:
                delay = min(ceiling, max(delay, asked))
            print(f"  rate limited ({exc.code}), retrying in {delay:.0f}s ...",
                  file=sys.stderr)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(min(ceiling, gap * (2 ** attempt)))
    assert last is not None
    raise last

# Statuses a retry cannot fix: the file is gone, or never was there. Anything
# else -- 429, 5xx, 403 from a bot filter, a timeout, a dropped connection -- is
# worth trying again, because the next run might be the one that gets through.
# The split is what lets the prefetcher say "stop" instead of "keep going": a
# dead URL retried on every run never succeeds, so without recording it the run
# could never report itself finished.
PERMANENT_HTTP_STATUS = frozenset({400, 404, 410, 451})

def failure_is_permanent(exc: BaseException) -> bool:
    """Whether retrying ``exc`` could ever succeed.

    Only a definitive HTTP answer counts. A 404 or 410 is a statement about the
    file rather than the moment; everything else -- including statuses that are
    usually temporary -- is treated as worth another try, because the cost of a
    wrong "permanent" is a pronunciation the article silently never gets.
    """
    return isinstance(exc, urllib.error.HTTPError) and exc.code in PERMANENT_HTTP_STATUS

def describe_failure(exc: BaseException) -> str:
    """A short human reason for a failed fetch, for the dead-file record."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return str(exc.reason)
    return type(exc).__name__

def download_cached(
    url: str,
    dest: str,
    force: bool = False,
    timeout: int = 60,
    retries: Optional[int] = None,
    spacing: Optional[float] = None,
    max_backoff: Optional[float] = None,
) -> str:
    """Download ``url`` to ``dest`` once, writing a sha256 sidecar.

    Reuses an existing, verified file unless ``force`` is set. The write is
    atomic (a ``.part`` file is renamed into place), and rate limits are retried
    with backoff.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not force and verify_sidecar(dest):
        return dest
    part = dest + ".part"
    print(f"downloading {url} ...", file=sys.stderr)
    with _open_with_retries(url, timeout, retries, spacing, max_backoff) as response, \
            open(part, "wb") as out:
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
    with _open_with_retries(RAWDATA_PAGE_URL, timeout) as response:
        page = response.read().decode("utf-8", "replace")
    match = re.search(r"dump dated (\d{4}-\d{2}-\d{2})", page)
    return match.group(1) if match else None

class Progress:
    """A coarse, cheap stderr progress indicator.

    ``tick`` is called once per item and only formats and writes on a batch
    boundary (or the first item), so the cost per item is a single comparison.
    ``done`` always reports the final count, so a short run still shows that the
    stage ran rather than staying silent.
    """

    def __init__(self, label: str, every: int = 200000, total: Optional[int] = None) -> None:
        self.label = label
        self.every = max(1, every)
        self.total = total
        self.count = 0
        self.t0 = time.time()
        self._last = 0.0
        self._shown = False

    def tick(self, increment: int = 1) -> None:
        self.count += increment
        if self.count == increment:
            self._write()
            return
        if self.every == 1:
            # A caller that ticks per item on a huge batch must not turn progress
            # into one stderr write per item -- on a console that is orders of
            # magnitude slower than the work itself. Throttle it by time, so
            # updates stay visible and cheap.
            if time.time() - self._last >= 0.1:
                self._write()
            return
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
        self._last = time.time()
        self._shown = True

    def done(self) -> None:
        self._write(final=True)

class TabularLog:
    """A ``name<TAB>url[\\TAB reason]`` record of what a run found.

    Written and flushed per line, so a run that is interrupted still leaves a
    valid record -- which is the point when the run is being cut short by a rate
    limit rather than by finishing.

    ``truncate`` suits the manifest, which describes one run and must not
    accumulate. The dead-file record is cache *state* that carries across runs,
    so it is opened for append and skips names it already holds; that is what
    keeps a file that is gone on Wikimedia from being requested on every future
    run.

    ``header`` lines are written ahead of the first entry, and only when the
    file is created rather than appended to. They exist for the shard files
    (see :class:`ShardSet`), which are handed to another machine and have to
    say how to fetch themselves; the manifest is only ever read by this tool and
    is left in the plain format the tests and the docs describe.
    """

    def __init__(
        self,
        path: str,
        download_dir: str,
        truncate: bool = True,
        header: Sequence[str] = (),
    ) -> None:
        self.path = path
        self.download_dir = download_dir
        self.count = 0  # entries written by this run
        self.names: Set[str] = set()  # every name the file holds
        self._truncate = truncate
        self._header = list(header)
        # read eagerly even though the write is lazy: the caller consults the
        # names already held before offering anything
        if not truncate and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.names = {
                    line.split("\t", 1)[0]
                    for line in f
                    if line.strip() and not line.startswith("#")
                }
        # opened on the first entry, so a run with nothing to record does not
        # leave an empty file behind, and truncating still happens before any
        # line is written
        self._stream = None

    def add(self, dest: str, url: str, reason: Optional[str] = None) -> bool:
        """Record one file. False if the name is already held."""
        name = os.path.relpath(dest, self.download_dir).replace(os.sep, "/")
        if name in self.names:
            return False
        if self._stream is None:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            self._stream = open(
                self.path, "w" if self._truncate else "a", encoding="utf-8"
            )
            if self._truncate:
                for line in self._header:
                    self._stream.write(line + "\n")
                self._stream.flush()

        fields = [name, url] + ([reason] if reason else [])
        self._stream.write("\t".join(fields) + "\n")
        self._stream.flush()
        self.names.add(name)
        self.count += 1
        return True

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def describe(self) -> List[str]:
        """How much work this record turned out to hold, for the run's summary."""
        return [f"  to download:    {self.count:,}"]
