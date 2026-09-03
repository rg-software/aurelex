## MODIFIED Requirements

### Requirement: Dictionary folder selection and scanning
The system SHALL let the user add dictionaries from folder-scoped (SAF) sources,
selected by the user from within allowed locations, and SHALL scan them for
supported dictionary files (mdict `.mdx`/`.mdd`, DSL `.dsl`/`.dsl.dz`, StarDict
`.ifo`). Added sources are scanned from app-private staging: the app copies the
source's supported dictionary files into app-private storage (reading them
through the SAF grant) and scans those copies there, because scoped storage
blocks direct path reads of the picked folders. The system SHALL NOT require
system-wide storage access to add dictionaries. Unsupported files in a scanned
location MUST NOT be treated as dictionaries.

#### Scenario: User selects a valid dictionary folder
- **WHEN** the user picks a folder containing mdict, DSL, or StarDict files
- **THEN** the app lists those dictionaries with their display names and source files

#### Scenario: Folder contains supported and unsupported formats
- **WHEN** the scanned folder contains supported files alongside files in other
  formats (bgl, aard, slob, etc.)
- **THEN** only the supported files are presented, and the others are ignored
  without error

#### Scenario: No supported dictionaries found
- **WHEN** the selected folder contains no supported dictionary files
- **THEN** the app tells the user that no supported dictionaries were found

#### Scenario: User selects a folder via the SAF picker
- **WHEN** the user taps Add dictionaries and selects a folder inside an allowed
  location
- **THEN** the app adds that folder as a dictionary source and scans it without
  requesting system-wide storage access

#### Scenario: Dictionary files are staged into app-private storage
- **WHEN** a source is added via the SAF picker
- **THEN** the app copies the source's supported dictionary files into
  app-private storage and scans those copies, so the dictionaries load regardless
  of where the source folder lives (device storage or a cloud provider)

#### Scenario: Removed a dictionary and re-scans the same source
- **WHEN** the user removes a dictionary and then re-scans its source
- **THEN** the dictionary is added back as a fresh entry (re-scan is not blocked
  by the earlier removal)
