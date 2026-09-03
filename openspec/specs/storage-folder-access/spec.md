# storage-folder-access Specification

## Purpose

Manages folder-scoped (Storage Access Framework) dictionary sources on Android:
selecting allowed folders, persisting their grants across restarts, resolving
them to physical paths (or staging), and letting the user manage the active
sources — without ever requesting system-wide storage access.

## Requirements

### Requirement: Folder-scoped source selection
The system SHALL let the user add a dictionary source by picking a folder through
the Android Storage Access Framework folder picker, SHALL limit access to the
picked folder (and its subfolders) only, and SHALL NOT request or require
system-wide storage access (All-Files-Access) for this capability.

#### Scenario: Add a folder from the SAF picker
- **WHEN** the user taps Add dictionaries
- **THEN** the Android folder picker opens and the user can select any folder
  whose location the OS grants access to

#### Scenario: No system-wide permission is required
- **WHEN** the user adds or browses a dictionary source
- **THEN** the app does not ask for, and does not depend on, All-Files-Access

### Requirement: Persisted folder grants
The system SHALL keep the SAF grant for each added source so the source remains
available after the app is closed and reopened, and SHALL restore the list of
sources on startup.

#### Scenario: Source survives an app restart
- **WHEN** the user has added a folder and then closes and reopens the app
- **THEN** the folder remains listed as a source and its dictionaries still load

#### Scenario: Grant persists without re-picking
- **WHEN** the app restarts after a folder was added
- **THEN** the app re-scans the previously granted folder without asking the
  user to re-pick it

### Requirement: Multiple sources
The system SHALL let the user add more than one folder source and SHALL scan all
active sources, so dictionaries load from every added location.

#### Scenario: Add a second source
- **WHEN** the user adds a second folder while a first source is active
- **THEN** dictionaries from both sources load and appear together in the
  dictionary list

#### Scenario: Remove a source
- **WHEN** the user removes a folder source
- **THEN** dictionaries from that source no longer appear in the dictionary list,
  lookups, or full-text search, without affecting other sources

### Requirement: Source resolution and staging
The system SHALL resolve a source to a physical path when the provider supports
it (scan in place), and SHALL stage-copy the source's supported dictionary files
into app-private storage and scan them there when the provider cannot be resolved
to a physical path.

#### Scenario: Resolvable source scans in place
- **WHEN** a source is a folder on the device's own storage (resolvable to a
  physical path)
- **THEN** the app scans that folder in place without copying its files

#### Scenario: Unresolvable source is staged
- **WHEN** a source cannot be resolved to a physical path (e.g. a cloud-storage
  provider)
- **THEN** the app copies its supported dictionary files into app-private storage
  and scans those copies

#### Scenario: Nested subfolders are scanned
- **WHEN** a source folder contains dictionaries in nested subfolders
- **THEN** the app scans the whole tree recursively (both in-place and staged
  copies), so dictionaries in subfolders load

#### Scenario: Missing or revoked source
- **WHEN** a previously added source's folder is no longer accessible (e.g. the
  grant was revoked or the media is unmounted)
- **THEN** the app reports the source as unavailable without failing the scan of
  the other sources