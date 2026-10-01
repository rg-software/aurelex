## ADDED Requirements

### Requirement: One dead record, honoured by every run

A recording that is permanently gone SHALL be recorded once and SHALL NOT be
requested again by any later run. A run SHALL skip a recording the record names
instead of fetching it, whether the run is the prefetcher, a re-run of a shard
fetch (its `<shard>.dead.tsv`), or a build. The build SHALL consult the dead
record of its snapshot and SHALL append a recording it finds permanently gone,
so a rebuild makes no request for it. A name in the record SHALL be matched
regardless of the case it was written in. Skipping a recorded recording SHALL
NOT change what an article holds: the per-word slot is filled by the next
candidate exactly as if the fetch had failed, and the recording is still counted
among those missing.

#### Scenario: A rebuild does not repeat a 404

- **WHEN** a build finds a recording permanently gone and records it
- **THEN** a later build of the same snapshot makes no request for that
  recording, and still reports it as missing

#### Scenario: A shard re-run skips what it already classified

- **WHEN** a shard is fetched again into the same directory
- **THEN** the names its `<shard>.dead.tsv` records are not requested

#### Scenario: A dead name matches whatever its case

- **WHEN** the record names a recording as the source spells it (`En-us-…`)
- **THEN** the recording is recognised as gone and is not requested

#### Scenario: A skipped recording still leaves the article whole

- **WHEN** a recording the dead record names would have been a headword's
  preferred candidate
- **THEN** the headword's article carries its next available recording, and the
  missing count includes the recording that was skipped

#### Scenario: A lost dead record costs requests, not correctness

- **WHEN** the dead record is deleted or not carried over from a worker
- **THEN** the affected recordings are requested again, and the build is
  unaffected
