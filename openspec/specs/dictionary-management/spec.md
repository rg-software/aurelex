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

### Requirement: Dictionary groups
The system SHALL let the user organize loaded dictionaries into multiple named groups, each an ordered subset, and SHALL let the user select which group is active for lookups. An implicit "All" group containing every loaded dictionary is always available. Managing groups, their membership, and their order is part of this capability.

#### Scenario: All loaded dictionaries are the default group
- **WHEN** the user first loads dictionaries without creating any group
- **THEN** lookups use an implicit "All" group containing every loaded dictionary

#### Scenario: Create a group
- **WHEN** the user creates a named group and adds some dictionaries to it
- **THEN** the group appears in the groups list with that membership

#### Scenario: Select the active group
- **WHEN** the user picks a group as active
- **THEN** subsequent lookups use only that group's dictionaries, in that group's order

#### Scenario: Reorder dictionaries within a group
- **WHEN** the user changes the order of dictionaries inside a group
- **THEN** the combined article for that group respects the new order

#### Scenario: Delete a group
- **WHEN** the user deletes a group
- **THEN** the group no longer appears in the list, and lookups fall back to the "All" group (or the next active group), without error

#### Scenario: Delete a group that is active
- **WHEN** the user deletes the currently active group
- **THEN** the app falls back to the "All" group so lookups keep working
