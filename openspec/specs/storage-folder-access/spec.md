# storage-folder-access Specification

## Purpose

Manages one-off dictionary imports on Android through the Storage Access
Framework (SAF) folder picker: selecting an allowed folder, stage-copying its
supported dictionary files into app-private storage via the grant, and scanning
the copies — without any persistent "sources" list, Rescan, or system-wide
storage access.
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

### Requirement: One-off folder import
The system SHALL import a dictionary folder by picking it through the Android
Storage Access Framework folder picker, copying its supported dictionary files
into app-private storage via the SAF grant, and scanning + indexing the copies.
The system SHALL NOT require or request system-wide storage access for import,
and SHALL limit access to the picked folder (and its subfolders) only. Each pick
is a one-off import: there is no persistent source list, no Rescan action, and
deleting an imported dictionary permanently deletes the app's copy of it.
Installing a dictionary from the curated remote catalog is likewise a one-off
import of a copy into app-private storage: the catalog is a discovery surface
that lists dictionaries available to install, not a registered source of the
user's, so the app SHALL NOT offer a Rescan for it, SHALL NOT take or retain any
storage grant for it, and SHALL NOT track or re-verify an installed dictionary
against the catalog. The app MAY cache the last catalog document and re-probe it
as a discovery surface; that does not make the catalog a dictionary source.

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

#### Scenario: Catalog is not a registered source
- **WHEN** the user installs a dictionary from the remote catalog
- **THEN** the app offers no Rescan for it and takes no storage grant for it,
  and the installed copy is simply a dictionary the app owns until it is removed

#### Scenario: Removing a catalog-installed dictionary
- **WHEN** the user removes a dictionary that was installed from the remote
  catalog
- **THEN** the app permanently deletes its copy, exactly as it does for a
  folder-imported dictionary

