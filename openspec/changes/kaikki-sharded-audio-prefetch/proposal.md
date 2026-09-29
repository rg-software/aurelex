## Why

The `prefetch-audio` subcommand exists because Wikimedia rate-limits the tool
partway through a long dictionary run, and because a build that has already
rendered its articles cannot go back and fill the gaps it left. It fixes the
*sequencing* problem — fetch the missing audio separately, then rebuild — but
not the *throughput* problem: the fetching is still one serial, polite stream
from one machine at one IP, so filling a large dictionary's gaps takes as long
as the rate limit allows no matter how many machines are available.

Wikimedia's limit is per client, so several machines fetching disjoint parts of
the same work is the obvious way to multiply throughput. The blocker is that
planning the work requires the full snapshot and the audio archive index, which
only makes sense on one machine — while the fetching itself needs nothing but a
list of `name → url` pairs, which is exactly what `prefetch-audio --list` already
writes.

## What Changes

- `prefetch-audio --split N` divides the manifest it would write into N shard
  files, so the job can be planned once and handed out. Shards are disjoint by
  destination name and balanced, so no two machines ever request the same file.
- A new `fetch-list` subcommand downloads one shard file into a cache directory,
  reusing the prefetcher's existing throttle, retry/backoff, atomic `.part`
  write, `.sha256` sidecar, and dead-file recording. It needs no snapshot, no
  audio archive, and no network access to kaikki.org — only Python and the list
  file, so a worker can be a laptop that has never seen the dictionary.
- Worker caches are combined by copying files together, not by a merge command:
  every file is sidecar-verified and content-addressed by name, so an
  overlapping or repeated copy is a no-op. The user copies one cache into
  another the way they would any other directory.
- The workflow ends by re-running the ordinary prefetcher on the machine that
  will do the build, "just in case". That run is the check, and it is free: a
  file the local cache already holds is never requested, so a correct set of
  worker caches produces zero requests and a `done` verdict. It also picks up
  anything a worker could not get, so a partially-successful parallel run
  finishes with one more single-machine pass rather than a gap. No new option is
  needed for this — the local cache's existing skip behaviour already does it,
  and the shard lists likewise already contain only what the local cache lacks.
- A permanently-gone file in a shard is recorded in that worker's dead list and
  otherwise left to the build, which slot-fills past it exactly as it does
  today. This is the one behaviour that is weaker than the single-machine
  prefetcher's, and it is accepted: a worker has no records to re-plan against,
  so a 404 costs that headword one recording rather than triggering a fallback
  fetch.
- `docs/KAIKKI-CONVERSION.md` documents the plan → shard → fetch → copy → build
  workflow, including that a worker cache must be copied into the *building*
  machine's `<cache>/<dump-date>/audio-cache/`, and that dead lists are per-worker
  so a lost dead list costs re-requests, not correctness.

## Capabilities

### New Capabilities

- `sharded-audio-prefetch`: planning the missing-audio fetch as N disjoint,
  balanced shard manifests, and fetching one shard on a machine that has neither
  the snapshot nor the audio archive.

### Modified Capabilities

None. `prefetch-audio` itself is not yet covered by
`openspec/specs/dictionary-conversion/spec.md` — it is uncommitted work in the
tree — so there is no existing requirement to modify, and this change adds a
capability alongside it rather than amending a spec that does not describe it
yet. Writing the baseline prefetch requirement is left to whichever change
lands `prefetch-audio`; if that has not happened by the time this one is
archived, the two need reconciling so `dictionary-conversion` ends up
describing both.

## Impact

- `scripts/kaikki-to-dsl.py` — new `--split` option on `prefetch-audio`; new
  `fetch-list` subcommand and parser; a small refactor so the fetch loop's
  throttle/retry/sidecar/dead-file handling is shared between `prefetch-audio`
  and `fetch-list` rather than duplicated. Dispatch in `main()` grows a third
  mode word.
- `scripts/tests/test_kaikki_to_dsl.py` — coverage for shard disjointness and
  balance, for a worker filling a cache from a list alone, and for the
  build-after-copy path finding the copied files offline.
- `docs/KAIKKI-CONVERSION.md` — the multi-machine workflow.
- No engine, boundary, app, or Android surface is touched. No new dependency:
  the worker path uses the standard library only.
