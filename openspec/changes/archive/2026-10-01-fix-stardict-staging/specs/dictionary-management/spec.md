## MODIFIED Requirements

### Requirement: Dictionary folder selection and scanning
The system SHALL let the user add dictionaries by picking a folder through the
folder-scoped (SAF) picker and importing it: supported dictionary files (mdict
`.mdx`/`.mdd`, DSL `.dsl`/`.dsl.dz`, StarDict `.ifo`) are stage-copied into
app-private storage through the SAF grant and scanned there, because scoped
storage blocks direct path reads of the picked folders. A StarDict dictionary is
a set of sibling files sharing a basename rather than a single file, so staging
SHALL copy the `.ifo` together with the `.idx` and `.dict` files the engine
resolves it against, and the optional `.syn` when present, including the
compressed variants the engine accepts. A StarDict dictionary whose companion
files were not staged MUST NOT be presented as imported, because the engine
cannot open it. The system SHALL NOT require system-wide storage access to add
dictionaries. Unsupported files in a picked location MUST NOT be treated as
dictionaries. There is no persistent "source" abstraction: each pick is a
one-off import and imported dictionaries simply belong to the app's dictionary
set until removed.

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
- **WHEN** the user taps Add and selects a folder inside an allowed
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

#### Scenario: A StarDict dictionary is imported whole
- **WHEN** the user imports a folder containing a StarDict dictionary whose
  `.ifo`, `.idx` and `.dict` share a basename
- **THEN** all of the companion files are staged into app-private storage, and
  the dictionary loads and is searchable rather than being reported as a failed
  import

#### Scenario: StarDict compressed companions are staged
- **WHEN** a StarDict dictionary stores its index or definitions in one of the
  compressed forms the engine accepts (for example a dictzip `.dict.dz`)
- **THEN** that compressed companion is staged alongside the `.ifo`, so the
  dictionary loads

#### Scenario: A StarDict dictionary with missing companions is not presented as imported
- **WHEN** a picked folder contains a StarDict `.ifo` whose index and definition
  files are absent
- **THEN** the app does not list that dictionary as a working entry, and reports
  that it could not be loaded
