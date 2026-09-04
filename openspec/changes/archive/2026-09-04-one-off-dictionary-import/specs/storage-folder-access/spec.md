## REMOVED Requirements

### Requirement: Persisted folder grants
**Reason**: One-off import no longer keeps a live folder source; the SAF grant
is used only long enough to stage-copy the picked folder into app-private
storage, so there is no source grant to restore across restarts.

**Migration**: Existing installs that had sources will, on first launch after
upgrade, drop the persisted `sources` grant list; their already-staged copies
in app-private storage remain and are re-scanned normally. New additions use
the picker to import once.

### Requirement: Multiple sources
**Reason**: The concept of multiple *live folder sources* with per-source
management and removal is replaced by one-off imports; a folder can be imported
multiple times into app storage, and dictionaries from all imports simply
coexist in the dictionary list, so no explicit source-management requirement
remains.

### Requirement: Source resolution and staging
**Reason**: In-place scanning of a resolvable physical path is removed: every
pick is always staged-copied into app-private storage (the resolvable path was
display-only and the engine can't read it under scoped storage anyway). See the
modified selection/staging requirement below.

## MODIFIED Requirements

### Requirement: One-off folder import
The system SHALL import a dictionary folder by picking it through the Android
Storage Access Framework folder picker, copying its supported dictionary files
into app-private storage via the SAF grant, and scanning + indexing the copies.
The system SHALL NOT require or request system-wide storage access for import,
and SHALL limit access to the picked folder (and its subfolders) only. Each pick
is a one-off import: there is no persistent source list, no Rescan action, and
deleting an imported dictionary permanently deletes the app's copy of it.

#### Scenario: Pick a folder and import it
- **WHEN** the user taps Add dictionaries and selects a folder
- **THEN** the folder's supported dictionary files are copied into app-private
  storage, scanned, and listed as dictionaries (with their display names), and
  then full-text indexed automatically

#### Scenario: No supported dictionaries in the pick
- **WHEN** the selected folder contains no supported dictionary files
- **THEN** the app tells the user no supported dictionaries were found and
  nothing is imported

#### Scenario: Import contains supported and unsupported formats
- **WHEN** the picked folder contains supported files alongside other formats
- **THEN** only the supported files are imported and the others are ignored
  without error

#### Scenario: Nested subfolders in an import
- **WHEN** the picked folder contains supported dictionary files in nested
  subfolders
- **THEN** those files are imported too (staging covers subfolders
  recursively), so the whole picked location is searchable

#### Scenario: Re-importing the same folder
- **WHEN** the user imports a folder that was already imported before
- **THEN** the dictionaries are staged again (deduplicated by content so the
  same dictionary is not loaded twice) and remain available

#### Scenario: App restarts after an import
- **WHEN** the user closes and reopens the app after importing folders
- **THEN** the imported dictionaries still load from app-private storage without
  re-picking the original folders