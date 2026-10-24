"""Back up every Aurelex cache folder into a single archive.

The caches live under several top-level directories
(~/.cache/aurelex-kaikki, ~/.cache/aurelex-bilingual, ...). This script
traverses every ``~/.cache/aurelex-*`` directory and writes ONE archive
plus a SHA-256 sidecar, so there is a single backup unit to store.

The big blobs are already compressed, so the default is a plain .tar
(store-only): gzip would spend an hour of CPU for ~zero bytes saved.
``--compress`` switches to .tar.gz. Paths inside the archive are relative
to ~/.cache, so extracting into ~/.cache restores in place.

Archiving uses the standard-library ``tarfile`` (PAX format) rather than
the platform tar: the Windows bsdtar build segfaults (exit 0xC0000005) on
the audio-cache trees, while ``tarfile`` packs the same 100k+ files
cleanly. Nothing is deleted or modified by a backup run.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import sys
import tarfile


def find_roots(home_cache: str) -> list:
    """Every ``aurelex-*`` directory under the shared cache, sorted."""
    roots = [
        os.path.join(home_cache, name)
        for name in sorted(os.listdir(home_cache))
        if name.startswith("aurelex-")
        and os.path.isdir(os.path.join(home_cache, name))
    ]
    if not roots:
        raise SystemExit(f"no Aurelex cache folders under {home_cache}")
    return roots


def build_parser() -> argparse.ArgumentParser:
    today = __import__("datetime").date.today().isoformat()
    parser = argparse.ArgumentParser(
        description="Back up all Aurelex cache folders into one archive.")
    parser.add_argument("--out", default="",
                        help="Archive path to write "
                             f"(default: ~/aurelex-cache-backup-{today}.tar"
                             "[.gz]).")
    parser.add_argument("--roots", nargs="*", default=None,
                        help="Cache roots to include "
                             "(default: every ~/.cache/aurelex-* dir).")
    parser.add_argument("--compress", action="store_true",
                        help="Gzip the archive (slower, smaller).")
    return parser


def main(argv=None) -> int:
    import datetime

    args = build_parser().parse_args(argv)
    home_cache = os.path.join(os.path.expanduser("~"), ".cache")
    roots = list(args.roots) if args.roots else find_roots(home_cache)
    for root in roots:
        if not os.path.isdir(root):
            raise SystemExit(f"cache root does not exist: {root}")

    out = args.out
    if not out:
        stamp = datetime.date.today().isoformat()
        ext = ".tar.gz" if args.compress else ".tar"
        out = os.path.join(os.path.expanduser("~"),
                           f"aurelex-cache-backup-{stamp}{ext}")

    total = 0
    for root in roots:
        size = 0
        for _dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                try:
                    size += os.path.getsize(os.path.join(_dirpath, filename))
                except OSError:
                    pass
        total += size
        print(f"  {root:<60} {size:12,} bytes")
    print(f"total: {total:,} bytes in {len(roots)} root(s)")

    tmp_out = out + ".part"
    if args.compress:
        fileobj = gzip.open(tmp_out, "wb", mtime=0)  # noqa: SIM115
        mode = "w|"
    else:
        fileobj = open(tmp_out, "wb")  # noqa: PTH123, SIM115
        mode = "w|"
    skipped = 0
    try:
        with tarfile.open(fileobj=fileobj, mode=mode,
                          format=tarfile.PAX_FORMAT) as tar:
            for root in roots:
                base = os.path.basename(root.rstrip(os.sep))
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames.sort()
                    for filename in sorted(filenames):
                        path = os.path.join(dirpath, filename)
                        arcname = os.path.join(
                            base, os.path.relpath(path, root))
                        try:
                            tar.add(path, arcname=arcname, recursive=False)
                        except OSError as exc:
                            skipped += 1
                            print(f"  skip {path}: {exc}")
        fileobj.close()
    except BaseException:
        fileobj.close()
        try:
            os.remove(tmp_out)
        except OSError:
            pass
        raise
    if skipped:
        print(f"warning: {skipped} unreadable file(s) skipped")
    os.replace(tmp_out, out)

    digest = hashlib.sha256()
    with open(out, "rb") as f:  # noqa: PTH123
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    hex_digest = digest.hexdigest()
    with open(out + ".sha256", "w", encoding="utf-8") as f:  # noqa: PTH123
        f.write(f"{hex_digest}  {os.path.basename(out)}\n")
    print(f"wrote {out}")
    print(f"sha256: {hex_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
