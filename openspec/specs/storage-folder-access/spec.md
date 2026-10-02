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
The system SHALL import a dictionary folder by picking it through the Android Storage Access Framework folder picker, copying its supported dictionary files into app-private storage via the SAF grant, and scanning + indexing the copies. The system SHALL NOT require or request system-wide storage access for import, and SHALL limit access to the picked folder (and its subfolders) only. Each pick is a one-off import: there is no persistent source list, no Rescan action, and deleting an imported dictionary permanently deletes the app's copy of it.
Installing a dictionary from the curated remote catalog is likewise a one-off import of a copy into app-private storage: the catalog is a discovery surface that lists dictionaries available to install, not a registered source of the user's, so the app SHALL NOT offer a Rescan for it, SHALL NOT take or retain any storage grant for it, and SHALL NOT track or re-verify an installed dictionary against the catalog. The app MAY cache the last catalog document and re-probe it as a discovery surface; that does not make the catalog a dictionary source.

A picked folder is an origin for copies, not an identity: which folder a
dictionary was picked from, and whether it was picked directly or as part of a
folder that contains it, SHALL NOT affect whether the import adds a dictionary.
When a pick resolves to a dictionary the app already has, the import SHALL follow
the identity rule in `dictionary-management`: it SHALL silently skip the
dictionary when the content is identical, and SHALL reject and report it when the
content differs. Where a pick contains both dictionaries already present and new
ones, the app SHALL import the new ones and resolve the present ones by that
rule, and SHALL NOT let the presence of an already-present dictionary in the pick
prevent any other dictionary in it from being imported and indexed.

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
- **THEN** the dictionaries already present are silently skipped and the same
  dictionary is never loaded twice

#### Scenario: Re-importing a folder after adding a new dictionary to it
- **GIVEN** a user keeps their dictionaries in one folder, has imported it, and
  later adds a new dictionary to that same folder
- **WHEN** the user re-imports the folder
- **THEN** the new dictionary is added, the dictionaries already present are
  skipped silently, and the user is not asked to choose between them

#### Scenario: Picking a folder that contains an already-imported folder
- **GIVEN** a dictionary was imported from one folder, and the user later picks a
  different folder that contains that first folder
- **THEN** the dictionary is not imported a second time, and it appears once in
  the list

#### Scenario: Picking the same dictionary from a second location
- **GIVEN** a dictionary was imported from one folder
- **WHEN** the user picks a different folder containing an identical copy of that
  dictionary
- **THEN** the dictionary is skipped silently, and the copy is not kept in the
  app's storage

#### Scenario: Picking a different build of a present dictionary
- **GIVEN** a dictionary was imported from one folder
- **WHEN** the user picks a different folder containing a different build of that
  same dictionary
- **THEN** the picked build is not added, the dictionary the app already has is
  kept unchanged, and the app reports that a different build of that name is
  installed, without asking the user anything

#### Scenario: A pick mixing present and new dictionaries
- **GIVEN** a picked folder contains one dictionary the app already has and one it
  does not
- **WHEN** the user picks that folder
- **THEN** the new dictionary is imported, scanned and indexed, and the
  already-present dictionary does not prevent the import of the other

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

### Requirement: An imported folder's staged copy is stable across restarts

Once the app has staged a picked folder, the staged copy SHALL be treated as the
durable record of that import. Routine app maintenance that runs without user action
— a startup scan, index maintenance, or reclamation of directories nothing reads —
SHALL NOT delete a staged directory whose dictionaries load successfully, and a
dictionary imported from a nested subfolder SHALL be as durable as one imported from
the top level of the picked folder.

#### Scenario: A nested import is still present after a restart
- **WHEN** the user picked a folder whose supported dictionary files are in nested
  subfolders, and the app is restarted
- **THEN** those dictionaries are still listed and searchable, and no re-pick of the
  original folder is needed

#### Scenario: A routine scan does not delete the staged copy of an import
- **WHEN** a scan runs without any user action on the import
- **THEN** the staged copy of every import that loads successfully is left in place

#### Scenario: Re-importing is still required only for a removed dictionary
- **WHEN** a staged directory is deleted automatically
- **THEN** it is one that no dictionary loaded from, so every dictionary the user
  still sees can be re-imported from its original folder and no import the app
  reported as healthy has been discarded

