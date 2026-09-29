## Purpose

Lets the outstanding audio work of a dictionary build be planned once and then
fetched in parallel on several machines, so a build that Wikimedia rate-limited
is completed faster than one machine can fetch politely.

## ADDED Requirements

### Requirement: Disjoint shard manifests

The system SHALL be able to divide the outstanding audio work into a
user-specified number N of shard files, in place of the single manifest, where
each file records `name<TAB>url` per line in the same format as the unsharded
manifest. Every file in the outstanding work SHALL appear in exactly one shard,
so no two machines are ever asked to fetch the same file. The shards SHALL be
balanced: no shard's file count SHALL exceed another's by more than one file.
Dividing the work SHALL NOT require a second pass over the snapshot.

#### Scenario: Shards are disjoint and complete

- **WHEN** the work is divided into N shards
- **THEN** every name in the unsharded manifest appears in exactly one shard,
  and the shard file counts differ by at most one

#### Scenario: Division happens while planning

- **WHEN** the work is divided while being enumerated
- **THEN** each name is routed to its shard as it is found, and the snapshot is
  read once

#### Scenario: A single shard

- **WHEN** the work is divided into one shard
- **THEN** one file is written, holding every name the unsharded manifest holds

#### Scenario: Nothing outstanding

- **WHEN** there is no outstanding audio work
- **THEN** no shard file is left behind

### Requirement: Fetching a shard without the snapshot

The system SHALL be able to fetch one shard file into a cache directory on a
machine that has neither the dictionary snapshot nor the audio archive. Such a
fetch SHALL download nothing but the files the shard lists, SHALL write each
file into the cache under the name the shard records, and SHALL verify each
downloaded file by a checksum sidecar written beside it, so that a cache
assembled from several machines is indistinguishable from one a single machine
produced. Requests SHALL be spaced and retried with backoff on a rate limit,
and a file that is permanently gone SHALL be recorded with its reason and
reported apart from one that merely failed this run.

#### Scenario: A worker fills a cache from a list alone

- **WHEN** a shard file is fetched into an empty cache directory
- **THEN** every file the shard lists is in the cache, each with its checksum
  sidecar, and no other file is downloaded

#### Scenario: A rate-limited file is retried, not abandoned

- **WHEN** a fetch is refused with a rate limit
- **THEN** it is retried after a backoff honouring the response, and a file
  that still fails is left for a later run rather than recorded as gone

#### Scenario: A permanently gone file is recorded

- **WHEN** a file in the shard is not found on the server
- **THEN** it is recorded in the worker's dead list with the reason, is not
  retried by that worker again, and is reported separately from a file that
  merely failed

#### Scenario: Refetching a shard is safe

- **WHEN** a shard is fetched into a cache that already holds some of its files
- **THEN** the files already present and verified are left alone, and only the
  missing ones are requested

### Requirement: Combining worker caches by copying

The system SHALL treat a cache directory as a set of individually named,
individually verified files, so that caches produced on several machines are
combined by copying files from one into another. A file that is already present
and verified SHALL be left as it is, and copying a file that is already there
SHALL NOT corrupt it or cause it to be re-requested. A build run after the
caches are combined SHALL bundle every recording the combined cache holds
without making a request for the files it holds.

#### Scenario: Combining caches needs no merge step

- **WHEN** a worker cache is copied into the building machine's cache
- **THEN** the combined cache holds the union of both, with each file present
  once and verified

#### Scenario: Re-copying a cache changes nothing

- **WHEN** a cache is copied over itself
- **THEN** every file is still verified and no download is triggered

#### Scenario: The build after combining is offline

- **WHEN** a build runs against a cache holding the combined worker caches
- **THEN** every referenced recording the cache holds is bundled and no request
  is made for it

#### Scenario: A lost dead list costs requests, not correctness

- **WHEN** a worker's dead list is not carried over with its cache
- **THEN** the affected files are requested again by a later run, and the build
  is unaffected

### Requirement: The local cache is the one that counts

The work to be divided SHALL be only what the local machine's own audio cache
does not already hold, so a file that is already downloaded is never re-offered,
never appears in a shard, and is never requested by a worker. When the worker
caches have been copied together, a re-run of the ordinary prefetcher on the
machine that will do the build SHALL request nothing for the files it already
holds, and SHALL report that there is nothing left to do. A re-run MAY still
fetch files that no cache holds, which is how a partially-successful parallel
run is finished.

#### Scenario: Files already held are not re-offered

- **WHEN** the work is planned against a cache that already holds some of the
  recordings
- **THEN** the work contains only the recordings the cache lacks, the count
  already held is reported, and none of them is requested

#### Scenario: The final local re-run is a check

- **WHEN** the prefetcher is re-run after the worker caches have been copied
  together
- **THEN** it makes no request for the files now in the cache and reports that
  there is nothing left to do

#### Scenario: The final local re-run finishes a partial job

- **WHEN** some worker could not fetch a file that the local cache also lacks
- **THEN** the re-run fetches it, so the build does not go without it

### Requirement: A sharded 404 leaves the choice to the build

A file that is permanently gone while fetching a shard SHALL NOT cause the
worker to fetch a replacement, because a worker has no dictionary records to
choose one with. The worker SHALL report the file as gone and stop, and the
build SHALL then select that headword's next candidate in the ordinary way, so
the article keeps a pronunciation and a slot is not left empty while a
substitute exists.

#### Scenario: A gone file does not empty a slot

- **WHEN** a file in a shard is permanently gone and the build runs afterwards
- **THEN** the headword's article carries its next available recording, and its
  audio count is not reduced by the missing file

#### Scenario: A gone file is reported, not silently dropped

- **WHEN** a shard fetch ends with permanently-gone files
- **THEN** the run reports how many there were and where their record was
  written, separately from files that failed for a temporary reason
