## Context

The dead record (`<snapshot>/audio-dead.tsv`, or `<shard>.dead.tsv` on a worker)
already exists; the defect is that only one of the three runs that fetch honours
it, and that run compares the names wrongly.

## Decisions

### D1: Fold dead names when loading, not when writing

The file stays human-readable and holds the name as written (that is what the
docs and the shard headers describe). The **lookup** is a folded match key
(`_audio_match_key`: casefold, spaces to underscores), so the loaded set is
folded to match it. Writing folded keys instead would make the file unreadable
and lose the original spelling a person needs to investigate a 404.

`_audio_match_key` is idempotent, so folding an already-folded name is harmless.

### D2: The build shares the prefetcher's file

The build opens the same `<snapshot>/audio-dead.tsv`, appends with `TabularLog`
(non-truncating, so it accumulates across runs and skips names it holds), and
passes its names into `AudioPlan`. There is no second file to keep in step.

### D3: A skipped recording is counted missing, but not printed

`AudioPlan.plan` adds a known-gone candidate to `missing` without the per-file
`audio missing:` line. The count then reads the same on every run (the recording
genuinely is absent), while the log stays quiet — re-printing the same 225 lines
per build is the noise this change exists to remove. A *newly* discovered 404
still prints `audio gone (HTTP 404): …`, once.

## Risks / Trade-offs

- **A dead record that is wrong suppresses a recording forever.** If a file is
  restored upstream, its line must be removed by hand. This is the existing
  contract for `prefetch-audio`; the change only extends the same file to the
  build, so it introduces no new failure mode.
- **`--no-audio-download` writes nothing** — with no fetches there is nothing to
  learn, so the build does not open the record.
