## Context

See proposal.md for the motivation. The current state that shapes this design:

- `prefetch-audio` already separates *planning* from *fetching*. Planning calls
  `_resolve_inputs` (snapshot + audio-tar index + a full pass over the JSONL)
  and then walks headwords, yielding `(dest, url)` offers lazily. Fetching is a
  loop over those offers: `download_cached` (throttle, retry/backoff, atomic
  `.part` rename, `.sha256` sidecar), with failures split into permanent (`404`
  → `audio-dead.tsv`, never requested again) and transient (left for the next
  run), and a summary whose exit status says whether to run again.
- A planned offer is written to the manifest through `TabularLog.add`, which
  already returns `False` for a name it holds, and opens the file only on the
  first entry. So the manifest is a de-duplicated, lazily-created, flushed-per-
  line record of `name<TAB>url`.
- The audio cache is a *flat* directory of individually named files. The build
  picks up whatever is there (`verify_sidecar` → `AudioPlan._fetch` reuses it),
  the bundler copies the referenced names out, and nothing in the build knows or
  cares which machine fetched a file.
- `main()` dispatches mode words by hand (`prefetch-audio` vs. the flat build
  options), sharing snapshot options through `_add_snapshot_args`.

Two constraints follow. A worker must be able to run with *only* a list file, so
`fetch-list` cannot touch `_resolve_inputs`, `AudioWishlist`, or the JSONL at
all. And shards must be disjoint by destination name, because two machines
racing on one destination would both write `<name>.part` in a shared cache.

## Goals / Non-Goals

**Goals:**

- Plan once, fetch on N machines, with no machine needing the snapshot except
  the planner.
- Keep the two fetch paths (prefetcher and worker) saying the same things in the
  same words — same failure classes, same summary, same exit status — because
  the docs quote that output and users learn to read it.
- Add no new dependency, and no new concept the user has to learn beyond "copy a
  folder" and "run it again at the end".
- Leave the local machine's existing cache semantics alone: it already skips
  what it holds, which is both what keeps the shards down to the true remainder
  and what makes the closing re-run a free check.
- Stay streaming: a full-dictionary manifest is hundreds of thousands of lines,
  and must never be held in memory.

**Non-Goals:**

- No merge/verify command. Copying is the merge.
- No second cache location. Files are joined by copying them into the one
  directory the tool already uses (D8).
- No parallelism inside one process (see D5).
- No change to the article format, the build, the engine, or the app.
- No re-planning of a headword's candidates on a worker (see D4).

## Decisions

### D1 — Shard by round-robin over accepted names, as they are found

`--split N` makes the planner hold N `TabularLog`s and route each name to
`shard = accepted_count % N`, where `accepted_count` counts names `TabularLog`
*accepted*. Because a name is offered to the manifest once (repeats are rejected
by `add`), routing on the accepted count is what makes the shards disjoint:
contending names collapse onto the first claimant's shard, and the modulo never
sees them. Counts therefore differ by at most one, with no buffering and no
second pass — the manifest is already produced in one streaming pass.

*Alternatives.* Contiguous ranges (a shard is a headword range) would need the
total up front or a rebalancing buffer, and give no balance guarantee when
neighbouring headwords differ in how many recordings they want. Hashing the name
makes shards independent, so a worker could be assigned shard *i* without the
planner writing files at all, but balance becomes statistical and a dedup set is
still needed for disjointness — strictly more machinery for a worse guarantee.

### D2 — `--split N` implies listing; shards are named after the manifest

Division is a planning operation, so `--split` sets list-only. The shard paths
are derived from the manifest path (`audio-missing.tsv` →
`audio-missing.shard-01-of-04.tsv`), so `--manifest` still names the whole job
and the derived names are predictable for whoever is handed a shard.

*Alternative.* A separate `--shard-dir`. Rejected: it introduces a second place
to look for a job's files, and the manifest path is already the handle users are
given.

### D3 — `fetch-list` is a third mode word with its own small parser

`kaikki-to-dsl.py fetch-list <file> --into <dir>`, dispatched next to
`prefetch-audio` in `main()`. It takes **no** snapshot options at all: no
`--source-lang`, no `--dump-date`, no `--audio-per-word`, none of the four
options `_add_snapshot_args` shares, because none of them change what a list
says. It takes the fetch-shaping options the two paths genuinely share
(`--timeout`, `--spacing`, `--retries`, `--max-backoff`, `--force-download`),
plus `--limit` with the same "attempts, not successes" meaning, and
`--into`, which is **required** because a worker has no snapshot directory to
derive a default from.

It parses lines as `name<TAB>url`, tolerating a third column (the dead list's
reason) and rejecting a line with no tab, naming the line number — a silently
skipped line is a silent audio gap, which is the failure mode this whole feature
exists to avoid. Names are joined with `os.path.join(dir, *name.split("/"))` so a
shard planned on Linux is usable on Windows. The file is read as a generator;
`--limit` stops the generator rather than the file being slurped.

### D4 — A gone file is the build's problem; the worker does not substitute

The prefetcher's second planning pass exists because it *has* records: on a 404
it replans the headword and fetches the next candidate so the article keeps its
full count. A worker has only `name → url`, so substituting is not available
without putting each headword's whole candidate list in the shard file.

Chosen: the worker records the 404 in its dead list and moves on; the build's own
slot-fill picks the next candidate, which is what it already does for a
recording the archive lacks. The cost is that a build run with
`--no-audio-download` after a sharded fetch can show fewer than `--audio-per-word`
recordings for the affected headwords.

*Alternative.* Put every probed candidate (not just the referenced ones) in the
shard, with the per-headword grouping, and let the worker walk the list. This
preserves the count exactly and is the right answer if audio gaps turn out to
matter; it is rejected now only because it grows the shard file by the probed
factor (a headword with 12 candidates contributes 12 lines, not 3) and needs a
grouped format that is no longer the manifest format — a format change to
document and keep compatible. Recorded as an open question below.

### D5 — No in-process concurrency

Wikimedia's limit is per client, and `_throttle` is a single process-global
spacing. N threads either keep the same aggregate request rate — no speedup, more
complexity — or raise it and earn a harder 429. The parallelism has to come from
distinct clients, which is the entire point of the change. The docs will say so,
because "run it on four machines" is only faster if those are four egress IPs.

### D6 — One fetch implementation, two entry points

The per-file work is pulled out of `prefetch_audio` into a shared helper used by
both modes: attempt a download, classify the exception as permanent or transient,
record it in the worker's dead log, tally it, and return the classification. The
run summary and exit-status rule become a small accumulator both modes render.
The prefetcher keeps its interleaved-scan loop and its replacement queue; the
worker keeps a line generator; both drive the same helper with the same options.

*Alternative.* Duplicate the loop in `fetch-list`. Rejected: it would fork the
failure taxonomy, the summary wording, and the exit-status contract — the three
things most worth keeping identical — and the docs quote them.

### D7 — The dead list is a per-worker file beside the list

`fetch-list` writes `<list>.dead.tsv` by default (overridable), *not* inside the
cache directory: the cache directory is the thing users copy between machines and
bundle from, and a stray TSV in it would be copied and possibly zipped for no
reason. Losing this file costs re-requests in a later run and nothing else; the
spec says so explicitly so it is a documented trade rather than a surprise. To
keep the "never requested again" property across machines, the user concatenates
it into the planner's `audio-dead.tsv`.

## D8 — The local machine's own cache is the only cache that matters

The user's flow is: plan and split, fetch the shards independently, copy the
caches together, re-run the ordinary prefetcher locally "just in case", build.
Nothing in that needs a second cache location. The local prefetcher already
skips what its own cache holds (`AudioWishlist.__call__` and the
`os.path.isfile` guard in `consider`), so the shard lists contain only the local
cache's remainder, and the closing re-run makes no request for anything the
copied caches supplied. The re-run is the check, and it doubles as the way a
partially-successful parallel run is finished: whatever no cache holds, that one
pass fetches.

*Alternative considered and rejected:* naming other local directories as extra
cache, so a pile of previously downloaded recordings could be reused in place.
It needs the same option on the build as on the prefetcher, because excluding a
file the build cannot find turns a re-request into a permanent gap — and the
whole benefit evaporates as soon as the user copies those files into their own
cache, which they are doing anyway in step 3. Not worth a new option, a
three-way resolution rule, and a documented way to get it wrong.

## Risks / Trade-offs

- **Machines behind one NAT share one rate-limit budget** → the run is no faster
  than a single machine, and the user has paid for the complexity. Mitigation:
  state it in the docs next to the workflow, before the commands.
- **A worker dies holding a `<name>.part`** → the file is simply absent, another
  worker's copy of that name (or a later run) fetches it. `.part` is never
  mistaken for a finished file because only the `os.replace` into place creates
  the real name. The closing local re-run is the backstop for every such loss.
- **Two shards generated for different option sets overlap** (e.g. planned with
  different `--audio-per-word`) → two machines may fetch the same name. Harmless
  when the caches are copied together, wasteful only if a worker is told to fetch
  a name another already has. Mitigation: the shard header records the planning
  options, and the docs require one plan per option set.
- **A headword's count drops after a sharded 404** (D4) → the build still
  bundles a recording; the count is only short when the build also runs with
  `--no-audio-download`. Mitigation: documented; the fix is the D4 alternative.
- **A worker's dead list is not copied** → those files are requested again by the
  closing local re-run, which reports them as transient rather than silently
  dropping them. Costs requests, not correctness.
- **Filenames legal on Linux but not Windows** (MediaWiki titles may contain
  characters Windows rejects) → such a file cannot be fetched on a Windows
  worker. This is pre-existing for the cache's flat namespace and not introduced
  here; it merely becomes visible when caches cross machines. Mitigation: none
  proposed, but the fetch error names the file so the offending name is obvious.

## Migration Plan

None needed: `--split` is opt-in, `fetch-list` is a new mode word, and the
unsharded `prefetch-audio` path keeps its exact behaviour and output. Rollback
is deleting the option and the mode; shard files are inert text that nothing
reads unless asked.

## Open Questions

- Whether shards should carry each headword's full candidate list so a worker can
  substitute after a 404 (D4). It would need a grouped shard format — no longer
  the manifest format — and can be answered later without changing the split,
  the worker mode, or the cache-composition rules, only the shard format's
  contents and one extra fallback loop.
