# audio-bundle-rebuild Specification

## Purpose

Rebuilds the resource bundle of an already-rendered dictionary from the
dictionary file itself, so a build interrupted after its `.dsl.dz` was written
recovers cheaply instead of re-rendering the whole snapshot.

## Requirements

### Requirement: Rebuild the bundle from the rendered dictionary

The system SHALL be able to write the resource bundle for an already-rendered
`<name>.dsl.dz` without re-rendering and without reading the dictionary
snapshot's records, taking the set of recordings to bundle from the
dictionary's own `[s]…[/s]` references. The bundle SHALL hold the sense-marker
icons and every referenced recording that can be located.

#### Scenario: References are the source of truth

- **WHEN** the bundle is rebuilt for a rendered dictionary
- **THEN** it contains exactly the recordings that dictionary references, and
  no recording it does not reference

#### Scenario: No snapshot records are read

- **WHEN** only the rendered dictionary, the audio archive and the cache are
  available, and the JSONL snapshot is not
- **THEN** the bundle is still rebuilt

#### Scenario: Icons are always present

- **WHEN** a bundle is rebuilt
- **THEN** it contains the sense-marker icons, as a build's bundle does

#### Scenario: Nothing referenced

- **WHEN** the dictionary references no recordings
- **THEN** the bundle is still written and holds the icons

### Requirement: Recordings are located in the cache or the archive

The system SHALL locate each referenced recording first in the local audio
cache and then in the audio archive, and SHALL report and omit a recording
found in neither.

#### Scenario: From the archive

- **WHEN** a referenced recording is present in the audio archive
- **THEN** it is extracted from the archive into the bundle

#### Scenario: From the cache

- **WHEN** a referenced recording is present in the local audio cache and not
  in the archive
- **THEN** it is copied from the cache into the bundle

#### Scenario: A recording found nowhere is reported

- **WHEN** a referenced recording is in neither the cache nor the archive
- **THEN** the run counts it and warns, and the bundle omits it

### Requirement: References stay consistent with the bundle

The system SHALL give each bundled recording the same filesystem-safe name a
build gives it, and SHALL rewrite the dictionary's reference when that name
differs from the reference, so every `[s]` link names a file in the bundle. A
dictionary whose references already match SHALL be left unchanged.

#### Scenario: An unsafe reference is rewritten

- **WHEN** a reference carries a character a filesystem refuses
- **THEN** the recording is bundled under the sanitised name and the dictionary
  is rewritten to reference that name

#### Scenario: An already-safe dictionary is untouched

- **WHEN** every reference is already filesystem-safe
- **THEN** the dictionary is not modified

#### Scenario: Reference and file agree

- **WHEN** a bundle is rebuilt
- **THEN** every recording in it is referenced under exactly its bundled name

### Requirement: The rebuilt bundle matches a build's output

The system SHALL write the bundle beside the dictionary under the same name and
layout a build uses (`<base>.dsl.files.zip`, or `<base>.dsl.files/` with
directory layout), and repeating the operation SHALL be safe.

#### Scenario: Zip beside the dictionary

- **WHEN** a bundle is rebuilt with the default layout
- **THEN** `<base>.dsl.files.zip` is written beside the `.dsl.dz`

#### Scenario: Directory layout

- **WHEN** the directory layout is requested
- **THEN** `<base>.dsl.files/` is written holding the same files

#### Scenario: Repeating is safe

- **WHEN** the rebuild is run a second time
- **THEN** it succeeds and leaves the same bundle

### Requirement: Rebuilding does not need the network

The system SHALL not contact kaikki.org and SHALL not read the JSONL snapshot;
when a local audio archive is given it SHALL make no network request at all.

#### Scenario: Offline with a local archive

- **WHEN** the audio archive is supplied locally
- **THEN** no network request is made

#### Scenario: Only the cache location is resolved

- **WHEN** the cache directory is resolved
- **THEN** only the dump date or local marker and the cache directory are read,
  not the snapshot's records
