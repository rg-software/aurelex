"""Audio prefetch"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from collections import deque
from typing import Deque, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from .audio import AudioPlan, _audio_match_key, _audio_name_variants, _safe_audio_filename, _url_basename, extract_audio, write_bundle
from .constants import RAW_JSONL_URL
from .dictzip import encode_dsl, make_dictzip, read_dictzip
from .dsltext import _ICON_ASSET_DIR, _ICON_FILES, collect_audio_refs, rewrite_audio_refs
from .inputs import _resolve_inputs
from .profiles import get_lang_profile
from .snapshot import Progress, Snapshot, TabularLog, describe_failure, download_cached, failure_is_permanent, verify_sidecar
from .source import iter_candidate_records, sample_headwords


class AudioWishlist:
    """Decides, one headword at a time, which recordings a build would fetch.

    Handed to :class:`AudioPlan` in place of the cached downloader, so planning
    runs the real selection logic and simply records what it *would* have asked
    for instead of asking. Nothing reaches the network from here; the caller
    fetches what :meth:`scan` yields, as it yields it.

    ``probed`` is the raw record of everything planning asked for, which is a
    superset of what any article ends up referencing -- an unresolved candidate
    does not use up a per-word slot, so planning keeps looking past it.
    :meth:`consider` narrows that to the referenced subset.
    """

    def __init__(
        self,
        download_dir: str,
        per_word: int,
        preferred_lang: Optional[str],
        available: Optional[Set[str]] = None,
        dead: Optional[Set[str]] = None,
    ) -> None:
        self.download_dir = download_dir
        self.per_word = per_word
        self.preferred_lang = preferred_lang
        # A private copy of the archive's names: a wanted-but-absent recording is
        # added to it so it counts against the per-word cap (see ``consider``).
        self.reachable: Set[str] = set(available or ())
        # recordings a previous run found permanently gone, by match key. The
        # dead file holds the written file names (case and all), so they are
        # folded here to match the way they are looked up below; a name that is
        # not folded would never equal a match key and the skip would never fire.
        self.dead: Set[str] = {_audio_match_key(name) for name in (dead or ())}
        self.probed: Dict[str, str] = {}  # destination path -> url, in file order
        self.satisfied: Set[str] = set()  # already in the cache before this run
        # A destination is offered once per run. A failure is left for the next
        # run rather than retried here: a rate-limited URL should be left alone.
        self.offered: Set[str] = set()
        self.failed: Set[str] = set()
        # the headword currently being offered, its full candidate set, and the
        # fallback offers a failure has produced for it; the caller drains the
        # latter (see mark_failed)
        self._batch: Sequence[dict] = ()
        self._batch_probed: Set[str] = set()
        self.replacements: List[Tuple[str, str]] = []

    def __call__(self, url: str, dest: str) -> None:
        if os.path.isfile(dest):
            self.satisfied.add(dest)
            return
        self.probed.setdefault(dest, url)
        # ``AudioPlan._final_name`` disambiguates two different recordings that
        # share a basename by suffixing a digest of the source. Enumeration and
        # the build agree on that order only while they see the same records, so
        # a suffixed name also gets recorded under the plain one: whichever name
        # the build settles on, the file is there and no refetch is needed.
        final = os.path.basename(dest)
        plain = _safe_audio_filename(_url_basename(url))
        stem, ext = os.path.splitext(final)
        if plain and plain != final and plain.endswith(ext):
            if stem.startswith(plain[: -len(ext)] if ext else plain):
                alias = os.path.join(self.download_dir, plain)
                if not os.path.isfile(alias):
                    self.probed.setdefault(alias, url)

    def _plan(self, records: Sequence[dict]) -> Set[str]:
        audio = AudioPlan(
            self.per_word, self.preferred_lang, True, self.reachable, self
        )
        audio.download_dir = self.download_dir
        for record in records:
            audio.plan(record)
        return audio.referenced

    def consider(self, records: Sequence[dict]) -> List[Tuple[str, str]]:
        """What one headword's records need fetched, as (destination, url).

        The batch is planned twice. The first pass records every candidate the
        archive lacks. The second treats those as obtainable and replans, which
        is precisely what the build will see once the cache holds them: an
        unresolved candidate does not consume a per-word slot, so the first pass
        alone would keep looking past a file that will in fact be there, and
        would fetch every later candidate too. Replanning through the same
        :meth:`AudioPlan.plan` rather than re-deriving the choice keeps the two
        in step by construction.

        Only the headword's own records are needed, and they are contiguous in
        the snapshot, so this decides each headword as it is read rather than
        waiting for a whole-dictionary pass.
        """
        before = len(self.probed)
        self._plan(records)
        for dest in list(self.probed)[before:]:
            self._batch_probed.add(dest)
            key = _audio_match_key(os.path.basename(dest))
            if key in self.dead:
                # recorded as gone in an earlier run. Deliberately not added to
                # ``reachable``: it will not be there when the build runs either,
                # so the build slot-fills past it, and the replacement it settles
                # on has to be fetched here for the article to come out whole.
                continue
            self.reachable.add(key)
        referenced = self._plan(records)
        offers: List[Tuple[str, str]] = []
        # Over the headword's *whole* candidate set, not just what this pass
        # probed: on a replan after a failure, what needs offering is a candidate
        # the first pass already knew about but had no reason to want yet.
        for dest in self._batch_probed:
            if os.path.basename(dest) not in referenced:
                continue
            # a recording another headword already asked for, or one that has
            # already failed this run, is not offered twice: a rate-limited URL
            # should be retried in the next run, not hammered within this one
            if dest in self.offered or dest in self.failed or os.path.isfile(dest):
                continue
            if _audio_match_key(os.path.basename(dest)) in self.dead:
                continue
            self.offered.add(dest)
            offers.append((dest, self.probed[dest]))
        return offers

    def mark_failed(self, dest: str) -> None:
        """Record a fetch that did not land, and take it out of ``reachable``.

        ``reachable`` stands in for what the build will find, so a name that
        stayed in it after a failure would keep a later headword from slot-
        filling around the gap: that headword would be planned as if the file
        were there, and the recording it actually falls back to would never be
        offered. Withdrawing it lets the next headword consider the same
        candidate list the build will.

        The headword that asked for the file is replanned as well. Both planning
        passes assume every probed candidate lands, so the plan it holds is the
        one for a *successful* fetch; now that this one is known to have failed,
        the build will slot-fill past it, and the recording it falls back to has
        to be fetched here or the article keeps the gap. Its replacement offers
        land in :attr:`replacements` for the caller to drain.
        """
        self.failed.add(dest)
        self.reachable.discard(_audio_match_key(os.path.basename(dest)))
        self._replan_current()

    def mark_dead(self, dest: str) -> None:
        """Record a file that is permanently gone, so no run ever requests it again.

        The headword is replanned exactly as for a transient failure -- the build
        will slot-fill past the gap either way -- but the file leaves the dead
        list, which is what lets a later run report the cache finished instead of
        retrying a 404 forever.

        The withdrawal from ``reachable`` matters here as much as it does for a
        transient failure: a file that only just turned out to be dead was added
        to the set when this headword was first planned, and a replan that still
        believed in it would re-select the dead file and fetch no replacement.
        """
        self.dead.add(_audio_match_key(os.path.basename(dest)))
        self.failed.add(dest)
        self.reachable.discard(_audio_match_key(os.path.basename(dest)))
        self._replan_current()

    def _replan_current(self) -> None:
        if self._batch:
            self.replacements.extend(self.consider(self._batch))

    def take_replacements(self) -> List[Tuple[str, str]]:
        """Drain the offers :meth:`mark_failed` queued, leaving the queue empty."""
        queued, self.replacements = self.replacements, []
        return queued

    def scan(
        self, jsonl_path: str, source_lang: str, sample: Optional[int],
        sample_mode: str,
    ) -> Iterator[Tuple[str, str]]:
        """Yield (destination, url) as each headword's recordings are decided.

        Batches the records by headword the way a build does, so the per-word cap
        is applied over exactly the same set of candidates. Headwords are
        contiguous in the snapshot, so nothing has to be buffered beyond the
        batch in hand.
        """
        if sample:
            sampling = Progress("sampling headwords")
            records: Iterable[dict] = sample_headwords(
                jsonl_path, source_lang, sample, sample_mode, sampling
            )
            sampling.done()
        else:
            records = iter_candidate_records(jsonl_path, source_lang)

        batch: List[dict] = []
        current: Optional[str] = None
        for record in records:
            word = str(record.get("word"))
            if word != current:
                # kept so a failure can be replanned against this headword
                self._batch = batch
                self._batch_probed = set()
                yield from self.consider(batch)
                batch = []
                current = word
            batch.append(record)
        self._batch = batch
        self._batch_probed = set()
        yield from self.consider(batch)

def _collect_wishlist(
    args,
    jsonl_path: str,
    available: Optional[Set[str]],
    download_dir: str,
    dead: Optional[Set[str]] = None,
) -> AudioWishlist:
    """A wishlist over one snapshot, driven with the build's own audio options.

    Which files are wanted follows from the same
    :meth:`AudioPlan.plan` the build uses, over the same records batched the
    same way, so the file *names* here are the names the build references. That
    is why the audio-affecting options (``--audio-per-word``, ``--audio-lang``)
    have to match the build's: a different per-word cap or preference changes
    which candidates are considered and therefore which files are wanted.

    ``dead`` carries the match keys an earlier run found permanently gone, so
    they are neither requested again nor counted as obtainable.

    Nothing is decided here; :meth:`AudioWishlist.scan` yields each headword's
    files as it reads them, so the caller can fetch them immediately.
    """
    return AudioWishlist(
        download_dir, args.audio_per_word, args.audio_lang, available, dead
    )

def shard_paths(manifest_path: str, count: int) -> List[str]:
    """Where the shards of ``manifest_path`` go.

    Derived from the manifest so that one option still names the whole job and
    the names of its parts follow from it: ``missing.tsv`` becomes
    ``missing.shard-01-of-04.tsv``.
    """
    base, ext = os.path.splitext(manifest_path)
    width = len(str(count))
    return [
        f"{base}.shard-{i:0{width}d}-of-{count}{ext or '.tsv'}"
        for i in range(1, count + 1)
    ]

class ShardSet:
    """The outstanding audio work divided into N disjoint shard files.

    Stands in for the manifest where the prefetcher records what it found, so
    the run itself is unchanged: the work is offered one file at a time and this
    decides which file each one goes to.

    Each name goes to the shard that the count of names *accepted so far* names
    as it is offered. That is what makes the shards disjoint and evenly sized:
    the de-duplication :meth:`TabularLog.add` already does is applied first, so
    a name two headwords both asked for is recorded once, and two machines are
    never sent to fetch the same file. Routing on the accepted count rather
    than on the running total is also what balances them: a repeated name does
    not consume a turn, and the counts can differ by at most one.

    Nothing is buffered and the snapshot is still read exactly once, because the
    decision needs nothing but the running count.
    """

    def __init__(
        self,
        manifest_path: str,
        download_dir: str,
        count: int,
        args,
        snapshot: "Snapshot",
    ) -> None:
        self.count = 0
        self.paths = shard_paths(manifest_path, count)
        self._shards = [
            TabularLog(path, download_dir, header=_shard_header(args, snapshot))
            for path in self.paths
        ]

    def add(self, dest: str, url: str) -> bool:
        shard = self._shards[self.count % len(self._shards)]
        if not shard.add(dest, url):
            return False
        self.count += 1
        return True

    def describe(self) -> List[str]:
        lines = [f"  to download:    {self.count:,}, in {len(self._shards)} shard(s):"]
        for path, shard in zip(self.paths, self._shards):
            lines.append(f"    {path}  ({shard.count:,})")
        return lines

    def close(self) -> None:
        for shard in self._shards:
            shard.close()

def _shard_header(args, snapshot: "Snapshot") -> List[str]:
    """The lines that make a shard file explain itself to whoever is handed it.

    A shard leaves this machine and is fetched by a command that knows nothing
    about the snapshot that produced it, so it has to carry the command line
    that fetches it, the options it was planned with -- a different
    ``--audio-per-word`` wants a different set of files, so shards from two
    plans of the same snapshot may overlap -- and what to do with the result.
    """
    plan = [f"--source-lang {args.source_lang}", f"--audio-per-word {args.audio_per_word}"]
    if args.audio_lang:
        plan.append(f"--audio-lang {args.audio_lang}")
    if args.jsonl:
        plan.append(f"--jsonl {args.jsonl}")
    elif args.dump_date:
        plan.append(f"--dump-date {args.dump_date}")
    return [
        "# a shard of the audio a kaikki-to-dsl.py build could not take from the",
        "# Wiktionary archive. Fetch it with:",
        "#   python scripts/kaikki-to-dsl.py fetch-list <this file> --into <dir>",
        f"# planned with: {' '.join(plan)}",
        "# combine the results by copying the filled <dir> into the building",
        "# machine's <cache-dir>/<dump-date>/audio-cache/, then re-run",
        "# 'prefetch-audio' there: it skips every file the cache now holds.",
    ]

class FetchTally:
    """What one run attempted, and the verdict those attempts imply.

    Shared by the two fetch modes -- the prefetcher walking the snapshot and a
    worker walking a shard file (see design D6) -- so that the summary wording
    and the exit status are the same whichever one ran. The user learns to read
    this output, and the docs quote it; a second phrasing would be a second
    thing to learn.

    ``--limit`` bounds *attempts*, not successes: a run in which files are
    failing is the run most at risk of earning a harder rate limit, so it must
    not sail on through the rest of the work.
    """

    def __init__(
        self,
        limit: Optional[int] = None,
        dead_label: str = "audio-dead.tsv",
        done_text: str = "every recording that exists is now cached -- run the build",
    ) -> None:
        self.limit = limit
        self.attempted = 0
        self.fetched = 0
        self.already = 0  # skipped: present and verified before this run
        self.gone: Dict[str, int] = {}  # reason -> how many are permanently gone
        self.gone_held = 0  # skipped: already recorded gone by an earlier run
        self.transient = 0
        self.complete = True
        self._dead_label = dead_label
        self._done_text = done_text

    def spent(self) -> bool:
        """True once the run's attempt budget is used up."""
        return self.limit is not None and self.attempted >= self.limit

    def report(self) -> List[str]:
        """The run's summary lines, in the order the docs show them."""
        lines = [
            f"fetched {self.fetched:,} of {self.attempted:,} "
            f"attempted file(s) this run"
        ]
        # The two kinds of failure are reported apart because they call for
        # opposite action: one is finished business, the other is worth coming
        # back to.
        if self.gone:
            breakdown = ", ".join(
                f"{n} {reason}" for reason, n in sorted(self.gone.items())
            )
            lines.append(
                f"  {sum(self.gone.values()):,} permanently gone ({breakdown}) -- "
                f"recorded in {self._dead_label}, never requested again"
            )
        if self.gone_held:
            lines.append(
                f"  {self.gone_held:,} already known gone (recorded in "
                f"{self._dead_label}) -- not requested again"
            )
        if self.transient:
            lines.append(
                f"  {self.transient:,} rate-limited, blocked or interrupted "
                f"-- re-run later"
            )
        if not self.complete:
            lines.append(
                f"  stopped at --limit {self.limit}; more files remain "
                f"-- re-run to continue"
            )
        elif self.transient:
            lines.append(
                "  not finished: re-run when the rate limit clears, and the files "
                "that did land are skipped"
            )
        else:
            # Every recording that was asked for is on disk. The ones that do
            # not exist cannot be fetched, and the build slot-fills past them, so
            # re-running would only re-read the work to reach the same verdict.
            lines.append(f"  done: {self._done_text}")
        return lines

    def exit_code(self) -> int:
        return 1 if (self.transient or not self.complete) else 0

def fetch_one(
    url: str,
    dest: str,
    args,
    tally: FetchTally,
    dead_log: "TabularLog",
    on_failure=None,
) -> bool:
    """Put one file in the cache, and account for it.

    Returns False *only* when the run's attempt budget is spent, so the caller
    can stop without having touched the network. A file already present and
    verified is not an attempt and is not re-requested, so a re-run over a full
    cache spends nothing.

    One bad file must not end the pass, so every failure is caught and filed
    rather than raised: a file that is *gone* is recorded so no future run asks
    for it again, and one that was merely refused or timed out is left for the
    next run. ``on_failure(dest, permanent)`` is how the prefetcher re-plans the
    headword that wanted the file; a worker has no records to re-plan against
    and passes nothing.
    """
    if not args.force_download and verify_sidecar(dest):
        tally.already += 1
        return True
    if tally.spent():
        return False
    tally.attempted += 1
    try:
        download_cached(
            url, dest, args.force_download, args.timeout,
            args.retries, args.spacing, args.max_backoff,
        )
    except Exception as exc:  # one bad file must not end the pass
        permanent = failure_is_permanent(exc)
        if permanent:
            reason = describe_failure(exc)
            dead_log.add(dest, url, reason)
            tally.gone[reason] = tally.gone.get(reason, 0) + 1
            print(
                f"  gone ({reason}): {os.path.basename(dest)}", file=sys.stderr
            )
        else:
            tally.transient += 1
            print(
                f"  failed, will retry: {os.path.basename(dest)}: {exc}",
                file=sys.stderr,
            )
        if on_failure is not None:
            on_failure(dest, permanent)
        return True
    tally.fetched += 1
    return True

def prefetch_audio(args) -> int:
    """Fetch, politely and resumably, the audio a build cannot take from the tar.

    The build itself has to render the articles that reference a recording, so
    the dictionary is re-rendered after this -- but that pass is pure CPU and
    local archive I/O: every file this command leaves in the cache is found by
    its sha256 sidecar and never requested again. Running it in chunks over
    several rate-limit windows is therefore just a matter of repeating the
    command; each run skips what it already has.

    Fetching is interleaved with the scan rather than deferred until it ends. A
    headword's decision needs only its own records, which are contiguous in the
    snapshot, so there is nothing to wait for: the first files are on disk within
    seconds of starting, and a run stopped by ``--limit`` never reads the rest of
    the snapshot at all.

    ``--split N`` records the same work as N disjoint shard files instead of one
    manifest, for machines other than this one to fetch: see
    :class:`ShardSet` for how they are divided and ``fetch-list`` for the other
    end. Splitting also lists, because a shard is a plan to hand out rather than
    a job to finish here.
    """
    want_audio = args.audio_per_word > 0
    if not want_audio:
        raise SystemExit("--audio-per-word 0 disables audio; nothing to prefetch")
    if not get_lang_profile(args.source_lang).has_audio:
        raise SystemExit(
            f"the {args.source_lang!r} profile declares no pronunciation "
            "recordings; there is nothing to prefetch"
        )
    if args.split is not None:
        if args.split < 1:
            raise SystemExit("--split needs a shard count of at least 1")
        if args.limit is not None:
            raise SystemExit(
                "--split plans the whole job so the shards can be handed out; "
                "--limit would silently drop the rest of it, and belongs on a "
                "fetching run instead"
            )
        # A shard is a plan to give away, so splitting is listing.
        args.list_only = True
    snapshot, jsonl_path, _audio_path, available, download_dir = _resolve_inputs(
        args, True
    )
    if download_dir is None:
        raise SystemExit("--no-audio-download leaves nowhere to cache prefetched audio")
    if not available:
        print(
            "warning: the audio archive holds no known recordings; every audio "
            "file in this dictionary will be fetched one by one",
            file=sys.stderr,
        )

    # The dead-file record is cache *state*, not a report, so it always lives
    # beside the cache rather than following --manifest around.
    dead_path = os.path.join(snapshot.dir, "audio-dead.tsv")
    dead_log = TabularLog(dead_path, download_dir, truncate=False)
    wishlist = _collect_wishlist(
        args, jsonl_path, available, download_dir, dead_log.names
    )
    manifest_path = args.manifest or os.path.join(snapshot.dir, "audio-missing.tsv")
    if args.split:
        work = ShardSet(manifest_path, download_dir, args.split, args, snapshot)
    else:
        work = TabularLog(manifest_path, download_dir)
    print(
        f"audio cache: {download_dir}\n"
        f"  manifest:   {manifest_path}\n"
        f"  gone:       {dead_path} ({len(dead_log.names):,} recorded)",
        file=sys.stderr,
    )
    os.makedirs(download_dir, exist_ok=True)

    tally = FetchTally(args.limit, os.path.basename(dead_path))
    fetching = Progress("fetching audio", every=25)

    def replan(dest: str, permanent: bool) -> None:
        """A file did not land, so the build will slot-fill past it.

        Both classes are replanned the same way -- the build moves on either
        way -- but a gone file also leaves the dead list, which is what lets a
        later run report the cache finished instead of retrying a 404 forever.
        The headword that asked for the file is replanned as well, and the
        replacements it yields are queued, so the article keeps the same
        recording count it would have had if the fetch had worked.
        """
        if permanent:
            wishlist.mark_dead(dest)
        else:
            wishlist.mark_failed(dest)
        queue.extend(wishlist.take_replacements())

    # Offers are pulled one at a time: draining the scan into the queue up front
    # would read the whole snapshot before fetching anything, which is the very
    # thing this avoids. A failed file can queue a replacement for its own
    # headword, so the queue outlives any single headword's offers.
    scan = wishlist.scan(jsonl_path, args.source_lang, args.sample, args.sample_mode)
    queue: Deque[Tuple[str, str]] = deque()
    exhausted = False
    try:
        while True:
            while not queue and not exhausted:
                try:
                    queue.append(next(scan))
                except StopIteration:
                    exhausted = True
            if not queue:
                break
            dest, url = queue.popleft()
            work.add(dest, url)
            if args.list_only:
                continue
            if not fetch_one(url, dest, args, tally, dead_log, replan):
                # stop consuming the scan: the rest of the snapshot does not
                # need reading to know there is more to come
                tally.complete = False
                break
            fetching.tick()
    finally:
        if not args.list_only:
            fetching.done()
        work.close()
        dead_log.close()

    if args.list_only:
        print(f"  already cached: {len(wishlist.satisfied):,}", file=sys.stderr)
        for line in work.describe():
            print(line, file=sys.stderr)
        print("listing only; nothing was downloaded", file=sys.stderr)
        return 0

    for line in tally.report():
        print(line, file=sys.stderr)
    return tally.exit_code()

def iter_list_entries(path: str) -> Iterator[Tuple[str, str]]:
    """Yield ``(name, url)`` for each entry of a manifest or shard file.

    Read as a generator: a full dictionary's outstanding work runs to hundreds
    of thousands of lines, and neither a worker nor ``--limit`` has any use for
    the ones past the end.

    Blank lines and ``#`` comments are skipped, and a third column -- which the
    dead list carries as its reason -- is ignored, so the three file kinds share
    one format. A line with no tab is refused with its number rather than
    skipped: a silently dropped line is a silently missing recording, which is
    the one failure this whole feature exists to avoid. Names are held to being
    relative and inside their directory, so a list file from somewhere else
    cannot write outside ``--into``.
    """
    with open(path, "r", encoding="utf-8") as stream:
        for number, raw in enumerate(stream, 1):
            line = raw.rstrip("\n").rstrip("\r")
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 2 or not fields[1].strip():
                raise SystemExit(
                    f"{path}:{number}: expected 'name<TAB>url', got {line!r}"
                )
            name = fields[0].strip()
            parts = name.replace("\\", "/").split("/")
            if (
                not name
                or name.startswith("/")
                or (len(parts) > 1 and os.path.isabs(name))
                or ".." in parts
            ):
                raise SystemExit(
                    f"{path}:{number}: {name!r} is not a plain relative name"
                )
            yield name, fields[1].strip()

def fetch_list(args) -> int:
    """Fetch one shard of the outstanding audio into a cache directory.

    The other end of ``prefetch-audio --split``, and deliberately much smaller:
    this command needs no snapshot, no audio archive, and no contact with
    kaikki.org, only the shard file, so any machine with Python can take one.

    A recording is written under the name the shard gives it, with the same
    checksum sidecar the prefetcher writes, which is what makes the filled
    directory indistinguishable from one this machine filled itself. The
    directory is therefore combined with the others by copying: the building
    machine's audio cache is a flat set of named, verified files, and a file
    already there is left alone.

    There is no re-planning here. A file that is permanently gone is recorded
    and skipped, where the prefetcher would fetch the headword's next candidate
    instead -- a worker has no records to choose one with. The build slot-fills
    past the gap, and the closing ``prefetch-audio`` run on the building machine
    is the pass that finishes whatever no worker could.
    """
    into = args.into
    if not os.path.isdir(into):
        os.makedirs(into, exist_ok=True)
    dead_path = args.dead or (args.list + ".dead.tsv")
    dead_log = TabularLog(dead_path, into, truncate=False)
    tally = FetchTally(
        args.limit,
        os.path.basename(dead_path),
        done_text=(
            "every recording this shard lists is now cached -- copy the "
            "directory into the building machine's audio cache"
        ),
    )
    print(
        f"audio cache: {into}\n"
        f"  shard:      {args.list}\n"
        f"  gone:       {dead_path} ({len(dead_log.names):,} recorded)",
        file=sys.stderr,
    )
    fetching = Progress("fetching audio", every=25)
    # Names an earlier run of this shard found permanently gone are not asked
    # for again: the worker's own dead file is the record, and honouring it is
    # what makes a re-run over the same shard cheap rather than a re-attempt of
    # every 404 it already classified.
    dead_keys = {_audio_match_key(name) for name in dead_log.names}
    try:
        for name, url in iter_list_entries(args.list):
            if _audio_match_key(name) in dead_keys:
                tally.gone_held += 1
                continue
            dest = os.path.join(into, *name.split("/"))
            if not fetch_one(url, dest, args, tally, dead_log):
                # --limit bounds attempts, so the rest of the list is left for
                # another run -- which costs nothing, because every file already
                # in the directory is skipped
                tally.complete = False
                break
            fetching.tick()
    finally:
        fetching.done()
        dead_log.close()

    print(f"  already cached: {tally.already:,}", file=sys.stderr)
    for line in tally.report():
        print(line, file=sys.stderr)
    return tally.exit_code()

def _bundle_archive_keys(name: str) -> List[str]:
    """Archive keys a bundled recording may be stored under.

    A name disambiguated by :meth:`AudioPlan._final_name` carries a digest before
    its extension that is not part of the archive key -- the plain basename is --
    so the variants of the stripped name are tried as well.
    """
    keys = _audio_name_variants(name)
    stem, ext = os.path.splitext(name)
    stripped = re.sub(r"-[0-9a-f]{8}$", "", stem)
    if stripped != stem:
        for key in _audio_name_variants(stripped + ext):
            if key not in keys:
                keys.append(key)
    return keys

def _resolve_bundle_inputs(args) -> Tuple[str, Optional[str], str]:
    """The archive and cache a rebuild reads, without touching the JSONL.

    The dictionary already fixes which recordings are wanted, so only the
    archive and the download cache are needed. The dump-date check against
    kaikki.org and the JSONL are deliberately skipped, so a rebuild with a local
    archive makes no network request at all.
    """
    if not args.dump_date and not args.jsonl:
        raise SystemExit(
            "pass --dump-date (or --jsonl) so the audio cache directory can be found"
        )
    snapshot = Snapshot(args.dump_date, args.cache_dir, RAW_JSONL_URL, args.audio_url)
    audio_path = args.audio_tar
    if not audio_path:
        audio_path = download_cached(
            snapshot.audio_url, snapshot.audio_path, args.force_download, args.timeout
        )
    return snapshot.dir, audio_path, os.path.join(snapshot.dir, "audio-cache")

def bundle_audio(args) -> int:
    """Rebuild the resource bundle of a rendered dictionary from the dictionary.

    Finishes what a build started when it wrote its ``.dsl.dz`` and then could
    not assemble the resource bundle -- a filename the filesystem refused, a
    killed process, a full disk. The dictionary already references every
    recording its articles want, so there is nothing to re-render: the sound
    links name the files, this locates each in the cache or the archive, and
    writes the same bundle a build would have written, beside the dictionary.
    """
    dict_path = args.dictionary
    if not os.path.isfile(dict_path):
        raise SystemExit(f"no dictionary at {dict_path}")
    text = read_dictzip(dict_path)
    # The about card also links the sense-marker icons as [s] names, and those
    # are bundled unconditionally; only the recordings are looked up.
    refs = [name for name in collect_audio_refs(text) if name not in _ICON_FILES]
    rename = {
        name: safe
        for name in refs
        if (safe := _safe_audio_filename(name)) != name
    }

    _snapshot_dir, audio_path, download_dir = _resolve_bundle_inputs(args)
    res_base = dict_path[:-3] if dict_path.lower().endswith(".dz") else dict_path
    zip_path = res_base + ".files.zip"
    dir_path = res_base + ".files"

    print(
        f"dictionary: {dict_path}\n"
        f"  references: {len(refs):,} recording(s)\n"
        f"  archive:    {audio_path}\n"
        f"  cache:      {download_dir}",
        file=sys.stderr,
    )

    found = 0
    missing: List[str] = []
    written = zip_path if args.audio_layout == "zip" else dir_path
    with tempfile.TemporaryDirectory(prefix="kaikki-res-") as tmp:
        # Icons are referenced from the assets; a cache hit is read straight from
        # the cache. Only archive members need the temporary directory.
        sources: Dict[str, str] = {
            name: os.path.join(_ICON_ASSET_DIR, name) for name in _ICON_FILES
        }
        wanted: Dict[str, List[str]] = {}
        gathering = Progress("gathering audio", every=1, total=len(refs))
        for name in refs:
            safe = rename.get(name, name)
            cached = os.path.join(download_dir, safe)
            if not os.path.isfile(cached) and safe != name:
                cached = os.path.join(download_dir, name)
            if os.path.isfile(cached):
                sources[safe] = cached
                found += 1
            else:
                # The archive stores the raw name, so the keys come from the
                # reference; only the target file is renamed to the safe one.
                wanted[safe] = _bundle_archive_keys(name)
            gathering.tick()
        gathering.done()

        if wanted:
            batching = Progress("extracting audio", every=1, total=len(wanted))
            extracted, missing = extract_audio(audio_path, wanted, tmp, batching)
            batching.done()
            found += extracted
            missing_set = set(missing)
            for name in wanted:
                if name not in missing_set:
                    sources[name] = os.path.join(tmp, name)

        packing = Progress("writing bundle", every=1, total=len(sources))
        write_bundle(sources, written, args.audio_layout, packing)
        packing.done()

    if rename:
        # Point the dictionary at the names actually bundled. Written to a
        # sibling and replaced, so an interrupted rewrite cannot truncate it.
        rewritten = rewrite_audio_refs(text, rename)
        part = dict_path + ".part"
        with open(part, "wb") as f:
            f.write(make_dictzip(encode_dsl(rewritten)))
        os.replace(part, dict_path)
        print(
            f"  rewrote {len(rename):,} reference(s) to filesystem-safe names",
            file=sys.stderr,
        )

    if missing:
        print(
            f"warning: {len(missing)} referenced recording(s) were not found in the "
            f"archive or the cache",
            file=sys.stderr,
        )
    print(f"bundled {found:,} of {len(refs):,} referenced recording(s)", file=sys.stderr)
    print(f"wrote {written}", file=sys.stderr)
    return 0
