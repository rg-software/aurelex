## MODIFIED Requirements

### Requirement: Dictionary folder selection and scanning
The system SHALL let the user add dictionaries by picking a folder through the
folder-scoped (SAF) picker and importing it: supported dictionary files (mdict
`.mdx`/`.mdd`, DSL `.dsl`/`.dsl.dz`, StarDict `.ifo`) are stage-copied into
app-private storage through the SAF grant and scanned there, because scoped
storage blocks direct path reads of the picked folders. The system SHALL NOT
require system-wide storage access to add dictionaries. Unsupported files in a
picked location MUST NOT be treated as dictionaries. There is no persistent
"source" abstraction: each pick is a one-off import and imported dictionaries
simply belong to the app's dictionary set until removed.

#### Scenario: User selects a valid dictionary folder
- **WHEN** the user picks a folder containing mdict, DSL, or StarDict files
- **THEN** the app imports (stages + scans) them and lists those dictionaries
  with display names

#### Scenario: Folder contains supported and unsupported formats
- **WHEN** the picked folder contains supported files alongside files in other
  formats (bgl, aard, slob, etc.)
- **THEN** only the supported files are imported, and the others are ignored
  without error

#### Scenario: No supported dictionaries found
- **WHEN** the selected folder contains no supported dictionary files
- **THEN** the app tells the user that no supported dictionaries were found and
  nothing is imported

#### Scenario: User selects a folder via the SAF picker
- **WHEN** the user taps Add dictionaries and selects a folder inside an allowed
  location
- **THEN** the app imports that folder's supported files as a one-off
  (stage-copy + scan) without requesting system-wide storage access

#### Scenario: Dictionary files are staged into app-private storage
- **WHEN** a folder is imported via the SAF picker
- **THEN** the app copies the folder's supported dictionary files into
  app-private storage and scans those copies, so the dictionaries load
  regardless of where the original folder lives (device storage or a cloud
  provider)

#### Scenario: Dictionaries in nested subfolders load
- **WHEN** a picked folder contains supported dictionary files in nested
  subfolders
- **THEN** the app imports those files too (staging covers subfolders
  recursively), so the whole picked location is searchable

#### Scenario: Removed a dictionary and re-scans the same source
- **WHEN** the user permanently removes a dictionary and then imports its folder
  again
- **THEN** the dictionary is added back as a fresh entry (removal is not blocked)

### Requirement: Remove a loaded dictionary
The system SHALL let the user permanently remove an imported dictionary from the
app, deleting its staged copy and its built indexes, and SHALL remove it
consistently from lookups, groups, and full-text search so no stale results
reference it.

#### Scenario: Remove an individual dictionary
- **WHEN** the user removes one loaded dictionary
- **THEN** that dictionary's entry disappears from the dictionary list, its
  staged files and index are deleted from app storage, and future lookups no
  longer include it

#### Scenario: Removal is reflected in groups
- **WHEN** a removed dictionary was a member of the active group or any group
- **THEN** the group's membership no longer lists it, without error

#### Scenario: Removal is reflected in full-text search
- **WHEN** a removed dictionary had a full-text index
- **THEN** full-text search results no longer include matches from it, and the
  index is deleted

#### Scenario: Confirmation before removal
- **WHEN** the user triggers a dictionary removal
- **THEN** the app asks for confirmation before the dictionary is removed,
  stating that removal deletes the app's copy of the dictionary

#### Scenario: Re-add after removal
- **WHEN** the user imports the same folder again after removing a dictionary
  from it
- **THEN** the dictionary is imported again as a fresh entry (removal is not
  blocked)