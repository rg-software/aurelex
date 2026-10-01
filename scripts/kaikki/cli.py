"""CLI"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional, Sequence

from .build import build
from .constants import AUDIO_TAR_URL, RAW_JSONL_URL, _PREFETCH_RETRIES, _PREFETCH_SPACING_SECONDS
from .prefetch import bundle_audio, fetch_list, prefetch_audio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaikki-to-dsl.py",
        usage="kaikki-to-dsl.py [<mode>] [options]",
        description="Build an importable DSL dictionary from a pinned kaikki.org "
        "Wiktionary snapshot for one language.\n\n"
        "Modes (an optional first argument; with no mode word this builds a\n"
        "dictionary):\n"
        "  prefetch-audio  Back-fill the audio the archive lacks; --split N writes\n"
        "                  worker shards\n"
        "  fetch-list      Fetch one shard file on a worker machine\n"
        "  bundle-audio    Rebuild a dictionary's resource bundle without re-rendering\n"
        "Run 'kaikki-to-dsl.py <mode> --help' for a mode's own options.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Notes:\n"
            "  This builds a monolingual explanatory dictionary: the indexed\n"
            "  headwords and their glosses are in the same language, taken from\n"
            "  the data edition for that language. The default edition is the\n"
            "  English Wiktionary, so --source-lang selects which language's\n"
            "  words are indexed but the glosses are English. To build another\n"
            "  language, point --jsonl-url at that language's edition, e.g.\n"
            "    --source-lang ru --jsonl-url \\\n"
            "      https://kaikki.org/ruwiktionary/raw-wiktextract-data.jsonl.gz\n\n"
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
            "  The output is <name>.dsl.dz plus <name>.dsl.files.zip (or the\n"
            "  .files/ directory with --audio-layout dir). The archive holds the\n"
            "  sense-marker icons in addition to any bundled audio, so it is\n"
            "  written even with --no-audio.\n\n"
            "  A recording Wikimedia rate-limits is left out of the article rather\n"
            "  than emitted as a broken link, so a long build can end with gaps.\n"
            "  The 'prefetch-audio' subcommand fills those gaps on its own,\n"
            "  politely and in resumable chunks, so the rate-limited fetching does\n"
            "  not have to share a run with rendering:\n\n"
            "    kaikki-to-dsl.py prefetch-audio --source-lang en \\\n"
            "        --dump-date 2026-09-02 --list      # see what is missing\n"
            "    kaikki-to-dsl.py prefetch-audio --source-lang en \\\n"
            "        --dump-date 2026-09-02 --limit 500  # fetch a chunk\n"
            "    kaikki-to-dsl.py --source-lang en --dump-date 2026-09-02\n"
            "\n"
            "  Several machines can share the back-fill: 'prefetch-audio --split N'\n"
            "  writes N disjoint shard files, each fetched by any machine with\n"
            "  'kaikki-to-dsl.py fetch-list <shard> --into <dir>', and the filled\n"
            "  directories are copied into <cache-dir>/<dump-date>/audio-cache/.\n"
            "\n"
            "  If a build wrote its .dsl.dz but could not finish the audio bundle\n"
            "  (a refused filename, a kill, a full disk), rebuild the bundle from the\n"
            "  dictionary alone without re-rendering:\n\n"
            "    kaikki-to-dsl.py bundle-audio <out>/<name>.dsl.dz \\\n"
            "        --dump-date 2026-09-02 --audio-tar <archive.tar>\n"
            "\n"
            "  The prefetcher must be given the same --source-lang,\n"
            "  --audio-per-word and --audio-lang as the build, because both decide\n"
            "  which recordings an article gets.\n"
        ),
    )
    parser.add_argument("--source-lang", required=True, help="ISO code of the dictionary's language (e.g. en)")
    parser.add_argument("--dump-date", help="pinned kaikki.org dump date (YYYY-MM-DD); required unless --jsonl")
    parser.add_argument("--jsonl", help="use a local wiktextract JSONL(.gz) instead of downloading")
    parser.add_argument("--audio-tar", help="use a local Wiktionary audio tar instead of downloading")
    parser.add_argument("--jsonl-url", default=RAW_JSONL_URL, help="override the JSONL source URL")
    parser.add_argument("--audio-url", default=AUDIO_TAR_URL, help="override the audio archive URL")
    parser.add_argument("--cache-dir", default=os.path.join(os.path.expanduser("~"), ".cache", "aurelex-kaikki"))
    parser.add_argument("--out-dir", default="dist")
    parser.add_argument("--name", help="dictionary/output base name (default kaikki-<source>)")
    parser.add_argument(
        "--title",
        help="display name for the dictionary (defaults to --name); used for the "
             "#NAME metadata, the about article's headword and the description, "
             "while the output files keep the --name base",
    )
    parser.add_argument("--include-inflections", action="store_true", help="also index inflected forms (adds them to suggestions)")
    parser.add_argument("--audio-per-word", type=int, default=3, help="max audio files per headword (default 3)")
    parser.add_argument("--no-audio", action="store_true", help="do not bundle audio (and do not download the archive)")
    parser.add_argument("--audio-lang", help="prefer audio whose tags match this language/accent (e.g. US)")
    parser.add_argument(
        "--no-audio-download",
        action="store_true",
        help="do not fetch audio missing from the archive from Wikimedia (tar only)",
    )
    parser.add_argument(
        "--force-audio-index",
        action="store_true",
        help="rebuild the cached audio-archive name index even if it looks current",
    )
    parser.add_argument(
        "--audio-layout", choices=["zip", "dir"], default="zip",
        help="how to bundle audio (default zip)",
    )
    parser.add_argument(
        "--reuse-bundle", action="store_true",
        help="render the dictionary only and reuse the resource bundle already "
             "beside it, instead of rebuilding it; the existing bundle is checked "
             "to cover every resource the dictionary references",
    )
    parser.set_defaults(audio_downloader=None, force_audio_index=False)
    parser.add_argument("--sample", type=int, help="emit only N headwords")
    parser.add_argument(
        "--sample-mode", choices=["first", "random"], default="first",
        help="how --sample picks headwords: first N in file order, or a "
        "deterministic spread over thousands of headwords (default first). "
        "Both read only a bounded part of the snapshot, so a sample is quick",
    )
    parser.add_argument("--preview", action="store_true", help="also write a human-readable HTML preview")
    parser.add_argument("--force-download", action="store_true", help="re-download cached files")
    parser.add_argument("--skip-date-check", action="store_true", help="skip verifying the dump date against kaikki.org")
    parser.add_argument("--timeout", type=int, default=60, help="network timeout in seconds (default 60)")
    return parser

def _add_snapshot_args(parser: argparse.ArgumentParser) -> None:
    """The options that decide *which* articles, and so which audio, are wanted.

    Shared by the build and the prefetcher: enumerating a different set of
    articles than the build renders is the one way the prefetched cache could end
    up holding files nothing references, or missing files the build asks for.
    """
    parser.add_argument("--source-lang", required=True,
                        help="ISO code of the dictionary's language (e.g. en)")
    parser.add_argument("--dump-date", help="pinned kaikki.org dump date (YYYY-MM-DD); required unless --jsonl")
    parser.add_argument("--jsonl", help="use a local wiktextract JSONL(.gz) instead of downloading")
    parser.add_argument("--audio-tar", help="use a local Wiktionary audio tar instead of downloading")
    parser.add_argument("--jsonl-url", default=RAW_JSONL_URL, help="override the JSONL source URL")
    parser.add_argument("--audio-url", default=AUDIO_TAR_URL, help="override the audio archive URL")
    parser.add_argument("--cache-dir", default=os.path.join(os.path.expanduser("~"), ".cache", "aurelex-kaikki"))
    parser.add_argument("--audio-per-word", type=int, default=3, help="max audio files per headword (default 3)")
    parser.add_argument("--audio-lang", help="prefer audio whose tags match this language/accent (e.g. US)")
    parser.add_argument("--sample", type=int, help="emit only N headwords")
    parser.add_argument(
        "--sample-mode", choices=["first", "random"], default="first",
        help="how --sample picks headwords: first N in file order, or a "
        "deterministic spread over thousands of headwords (default first). "
        "Both read only a bounded part of the snapshot, so a sample is quick",
    )
    parser.add_argument("--no-audio-download", action="store_true",
                        help="do not fetch audio missing from the archive from Wikimedia (tar only)")
    parser.add_argument("--force-audio-index", action="store_true",
                        help="rebuild the cached audio-archive name index even if it looks current")
    parser.add_argument("--force-download", action="store_true", help="re-download cached files")
    parser.add_argument("--skip-date-check", action="store_true",
                        help="skip verifying the dump date against kaikki.org")
    parser.add_argument("--timeout", type=int, default=60, help="network timeout in seconds (default 60)")

def prefetch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaikki-to-dsl.py prefetch-audio",
        description="Fetch the pronunciation recordings a build cannot take from the "
        "audio archive, into the same cache the build reads. Walks the snapshot and, "
        "as each headword's recordings are decided, downloads them at a polite rate. "
        "Nothing is fetched twice, so the command is safe to repeat until the cache "
        "is complete; the build then bundles the whole set with no network I/O.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Notes:\n"
            "  Pass the same --source-lang, --audio-per-word, --audio-lang and\n"
            "  snapshot as the build you are preparing for; those decide which\n"
            "  recordings each article gets, and therefore which files are wanted.\n\n"
            "  Fetching is interleaved with the scan, so the first files land within\n"
            "  seconds and --limit stops before the rest of the snapshot is read.\n"
            "  --list is the exception: it downloads nothing, so it reads everything in\n"
            "  order to write a complete manifest -- the way to size the job before\n"
            "  spending any of your rate limit on it.\n\n"
            "  --split N is how several machines share the job. It records the same work as\n"
            "  N disjoint shard files, each carrying a header saying how to fetch it, and\n"
            "  implies --list. Then, on each machine:\n"
            "    python scripts/kaikki-to-dsl.py fetch-list \\\n"
            "        <cache>/<dump-date>/audio-missing.shard-01-of-04.tsv --into ./cache01\n"
            "  Copy the filled directories into <cache-dir>/<dump-date>/audio-cache/ and\n"
            "  re-run prefetch-audio here to check nothing was missed. See 'fetch-list --help'.\n\n"
            "  Each run ends by saying whether there is anything left to do, and the\n"
            "  exit status agrees: 0 means every recording that exists is cached, 1\n"
            "  means a rate limit or --limit cut the run short. Failures are reported\n"
            "  in two classes, because they want opposite things from you:\n"
            "    * gone (HTTP 404 and similar) -- recorded in <cache>/<dump-date>/\n"
            "      audio-dead.tsv and never requested again. Retrying cannot help, so\n"
            "      these do not count as outstanding work; the build uses the next\n"
            "      candidate instead, and the article keeps a pronunciation.\n"
            "    * rate-limited, blocked or interrupted -- left for the next run.\n"
        ),
    )
    _add_snapshot_args(parser)
    parser.add_argument("--list", dest="list_only", action="store_true",
                        help="write the manifest of missing files and exit without downloading; "
                             "reads the whole snapshot, so it overrides --limit")
    parser.add_argument("--manifest", help="where to write the manifest (default <cache>/<dump-date>/audio-missing.tsv)")
    parser.add_argument("--split", type=int, metavar="N",
                        help="record the outstanding work as N disjoint shard files "
                             "instead of one manifest (missing.tsv becomes "
                             "missing.shard-01-of-04.tsv), for other machines to fetch "
                             "with 'fetch-list'; the shards differ in size by at most "
                             "one file and no two hold the same one, so no machine is "
                             "sent to fetch another's work. Implies --list, since a "
                             "shard is a plan to hand out, and cannot be combined with "
                             "--limit")
    _add_fetch_args(parser)
    return parser

def _add_fetch_args(parser: argparse.ArgumentParser) -> None:
    """The options that shape a fetching run, whichever mode is fetching.

    Shared by the prefetcher and the worker, so a file is fetched the same way
    whichever list it came from. Deliberately *not* the snapshot options: none
    of these change which files are wanted, only how they are asked for.
    """
    parser.add_argument("--limit", type=int,
                        help="attempt at most N files this run, then stop; anything "
                             "left is picked up by the next run. Counts attempts, so "
                             "a run where files are failing cannot outrun its window")
    parser.add_argument("--spacing", type=float, default=_PREFETCH_SPACING_SECONDS,
                        help=f"minimum seconds between requests (default {_PREFETCH_SPACING_SECONDS}; "
                             "Wikimedia asks bulk clients to stay well above 1)")
    parser.add_argument("--retries", type=int, default=_PREFETCH_RETRIES,
                        help=f"attempts per file (default {_PREFETCH_RETRIES})")
    parser.add_argument("--max-backoff", type=float, default=600.0,
                        help="ceiling on a single backoff sleep, honouring Retry-After up to it (default 600)")

def fetch_list_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaikki-to-dsl.py fetch-list",
        description="Fetch the recordings one shard of the outstanding audio lists, into "
        "a cache directory. Needs nothing but the shard file: no dictionary snapshot, no "
        "audio archive, no contact with kaikki.org, so any machine with Python can take "
        "one -- which is the point, since Wikimedia's rate limit is per client and "
        "several machines fetching disjoint parts of a job finish it sooner. Copy the "
        "filled directory into the building machine's audio cache afterwards.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Notes:\n"
            "  A shard is written by 'prefetch-audio --split N', which must be run with\n"
            "  the same --source-lang, --audio-per-word, --audio-lang and snapshot as the\n"
            "  build; those decide which recordings each article gets. Each shard says so\n"
            "  in its own header lines.\n\n"
            "  --into is an ordinary directory: give each shard its own, and copy them all\n"
            "  into <cache-dir>/<dump-date>/audio-cache/ on the machine that builds. Every\n"
            "  file is written with a .sha256 sidecar and an existing verified file is\n"
            "  never re-requested, so copying a directory over another -- or over itself --\n"
            "  is all the combining there is. Re-running 'prefetch-audio' on the building\n"
            "  machine afterwards is the check: it asks for nothing the cache now holds.\n\n"
            "  A file that is permanently gone is recorded and skipped rather than replaced.\n"
            "  The prefetcher can substitute the headword's next candidate because it has\n"
            "  the records; a worker cannot, and the build slot-fills past the gap instead.\n\n"
            "  The summary and exit status are the prefetcher's: 0 means the shard is done,\n"
            "  1 means a rate limit or --limit cut the run short. The dead list is written\n"
            "  beside the shard (<shard>.dead.tsv), never into the cache directory.\n"
        ),
    )
    parser.add_argument("list", help="the shard file to fetch ('prefetch-audio --split N')")
    parser.add_argument("--into", required=True,
                        help="the directory to fill; copy it into <cache-dir>/<dump-date>/"
                             "audio-cache/ on the machine that builds the dictionary")
    parser.add_argument("--dead",
                        help="where to record permanently-gone files (default <shard>.dead.tsv)")
    parser.add_argument("--force-download", action="store_true",
                        help="re-download files already present in the directory")
    parser.add_argument("--timeout", type=int, default=60,
                        help="network timeout in seconds (default 60)")
    _add_fetch_args(parser)
    return parser

def bundle_audio_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaikki-to-dsl.py bundle-audio",
        description="Rebuild the resource bundle of an already-rendered dictionary, "
        "reading the recordings to bundle from the dictionary itself. Recovers a build "
        "that wrote its <name>.dsl.dz but could not finish bundling its audio -- a "
        "refused filename, a killed process, a full disk -- without re-rendering the "
        "snapshot, which is the expensive part of a build.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Notes:\n"
            "  The dictionary is the source of truth: every recording it references\n"
            "  appears in it as a [s]...[/s] link, so the bundle is rebuilt from\n"
            "  those alone. Nothing re-decides which recording an article gets, and\n"
            "  the JSONL snapshot is not read.\n\n"
            "  A recording is looked for in the audio cache first, then in the audio\n"
            "  archive; one found in neither is warned about and left out, exactly as\n"
            "  a build leaves out a recording the archive lacks. The bundle is written\n"
            "  beside the dictionary as <base>.dsl.files.zip (or <base>.dsl.files/ with\n"
            "  --audio-layout dir), the same name and layout a build uses.\n\n"
            "  A recording whose name a filesystem refuses is bundled under the same\n"
            "  safe name a build gives it, and the dictionary's link is rewritten to\n"
            "  match, so no link points at a file that is not there. Passing --audio-tar\n"
            "  makes the whole run offline; only --dump-date/--jsonl and --cache-dir are\n"
            "  read to find the cache, never the snapshot's records.\n"
        ),
    )
    parser.add_argument("dictionary",
                        help="the rendered <name>.dsl.dz to rebuild the bundle for")
    parser.add_argument("--dump-date",
                        help="the snapshot the dictionary was built from, which locates "
                             "the audio cache; pass --jsonl instead for a local-snapshot build")
    parser.add_argument("--jsonl",
                        help="marks a build made from a local --jsonl, whose cache is "
                             "under <cache-dir>/local/; the file itself is not read")
    parser.add_argument("--audio-tar",
                        help="use a local Wiktionary audio tar instead of downloading")
    parser.add_argument("--audio-url", default=AUDIO_TAR_URL,
                        help="override the audio archive URL")
    parser.add_argument("--cache-dir",
                        default=os.path.join(os.path.expanduser("~"), ".cache", "aurelex-kaikki"))
    parser.add_argument("--audio-layout", choices=["zip", "dir"], default="zip",
                        help="how to bundle audio (default zip)")
    parser.add_argument("--force-download", action="store_true",
                        help="re-download a cached audio archive")
    parser.add_argument("--timeout", type=int, default=60,
                        help="network timeout in seconds (default 60)")
    return parser

def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Dispatched by hand rather than through argparse subparsers: the build's
    # options have stayed flat and heavily used since the tool's first release,
    # and a subparser would put them behind a mode word. The two modes that need
    # the snapshot instead share the options that decide which articles -- and so
    # which audio -- are wanted, through _add_snapshot_args. The worker takes
    # neither: it is handed a finished list, so it needs nothing that decides what
    # is wanted, only _add_fetch_args. The rebuild takes the finished dictionary:
    # it needs only where the audio is, not what was wanted.
    if argv and argv[0] == "prefetch-audio":
        return prefetch_audio(prefetch_parser().parse_args(argv[1:]))
    if argv and argv[0] == "fetch-list":
        return fetch_list(fetch_list_parser().parse_args(argv[1:]))
    if argv and argv[0] == "bundle-audio":
        return bundle_audio(bundle_audio_parser().parse_args(argv[1:]))
    args = build_parser().parse_args(argv)
    report = build(args)
    print(report.summary(), file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
