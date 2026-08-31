# dictionary-management Specification

## Purpose

Lets a user load offline dictionaries onto an Android device by selecting a dictionary folder, and gives the app a stable, testable contract for which formats are supported and how index caches are built and refreshed on device.

## Requirements

### Requirement: Dictionary folder selection and scanning
The system SHALL let the user select a folder containing dictionaries and SHALL scan it for supported dictionary files (mdict `.mdx`/`.mdd`, DSL `.dsl`/`.dsl.dz`, StarDict `.ifo`).
Unsupported files in that folder MUST NOT be treated as dictionaries.

#### Scenario: User selects a valid dictionary folder
- **WHEN** the user picks a folder containing mdict, DSL, or StarDict files
- **THEN** the app lists those dictionaries with their display names and source files

#### Scenario: Folder contains supported and unsupported formats
- **WHEN** the scanned folder contains supported files alongside files in other formats (bgl, aard, slob, etc.)
- **THEN** only the supported files are presented, and the others are ignored without error

#### Scenario: No supported dictionaries found
- **WHEN** the selected folder contains no supported dictionary files
- **THEN** the app tells the user that no supported dictionaries were found

### Requirement: Index build and validation on device
The system SHALL build a lookup index for each loaded dictionary on the device when that dictionary's index does not yet exist or is out of date, and SHALL show the user the progress of the build.
Lookup MUST NOT return results for a dictionary until its index build has finished.

#### Scenario: First-time load triggers indexing
- **WHEN** the user loads a dictionary whose index has never been built
- **THEN** the app shows an indexing progress indication and does not offer results from that dictionary until indexing completes

#### Scenario: Index is up to date
- **WHEN** the user loads a dictionary whose index is already valid
- **THEN** the app skips indexing and makes that dictionary available immediately

#### Scenario: Index is out of date
- **WHEN** the underlying dictionary file has changed or the index format version differs from the engine's
- **THEN** the app rebuilds the index for that dictionary and informs the user that reindexing was needed

### Requirement: Single dictionary group
The system SHALL present all loaded dictionaries as one lookup group, ordered by the user, matching goldendict's "unfiltered" group behavior.
Managing multiple named groups is not part of v1.

#### Scenario: All loaded dictionaries participate in lookup
- **WHEN** the user performs a lookup after loading multiple dictionaries
- **THEN** results combine entries from all loaded dictionaries in their configured order

#### Scenario: Dictionary order is adjustable
- **WHEN** the user changes the ordering of the loaded dictionaries
- **THEN** the combined article respects that order in subsequent lookups
