"""Input resolution shared by the build and the audio pre-fetcher."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from typing import Optional, Set, Tuple

from .audio import available_audio_keys
from .snapshot import Progress, Snapshot, _fetch_dump_date, download_cached


def _resolve_inputs(
    args, want_audio: bool
) -> Tuple[Snapshot, str, Optional[str], Optional[Set[str]], Optional[str]]:
    """Resolve the snapshot both the build and the audio prefetcher read.

    Checks the pinned dump date against kaikki.org (unless a local ``--jsonl`` is
    given), downloads the JSONL and the audio archive into the cache if they are
    not there yet, and indexes the archive's member names (itself cached beside
    the archive). Returns
    ``(snapshot, jsonl_path, audio_path, available_names, download_dir)``.

    Every stage is a cached, sidecar-verified download, so a second run over the
    same snapshot does no network I/O at all.
    """
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
        available = available_audio_keys(
            audio_path, scan, snapshot.dir, args.force_audio_index
        )
        scan.done()
        if not available:
            print(
                f"warning: no audio found in {audio_path}; audio will not be bundled",
                file=sys.stderr,
            )
    download_dir = None
    if want_audio and not args.no_audio_download:
        download_dir = os.path.join(snapshot.dir, "audio-cache")
    return snapshot, jsonl_path, audio_path, available, download_dir
