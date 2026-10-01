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
compressed variants the engine accepts. A StarDict dictionary keeps the images its articles reference in a
sibling resource location, which the engine reads from a `res` directory
beside the dictionary, a `res.zip` beside it, or a `<base>.res.zip`;
staging SHALL copy whichever of those the picked folder provides, so the
dictionary's article images resolve after import rather than being dropped.
A StarDict dictionary whose companion
files were not staged MUST NOT be presented as imported, because the engine
cannot open it. The system SHALL NOT require system-wide storage access to add
dictionaries. Unsupported files in a picked location MUST NOT be treated as
dictionaries. There is no persistent "source" abstraction: each pick is a
one-off import and imported dictionaries simply belong to the app's dictionary
set until removed.

When a staged dictionary file cannot be loaded, the system SHALL report that
failure to the user naming the affected file, and SHALL continue loading the
other dictionaries in the same scan. The reported failure SHALL be actionable:
the user SHALL be able to remove that failed import from the app, and the removal
SHALL delete the files it staged so the failure is not re-raised and its storage
is not retained. A failed import MUST NOT be unremovable merely because it never
became a loaded dictionary.

Re-importing a folder whose previous import ended in a failed load SHALL
supersede that failed import: after the re-import the failure SHALL no longer be
reported, and the stale staged copy SHALL NOT remain to be re-attempted on later
scans.

Cleanup of a failed import SHALL NOT delete files belonging to a loaded
dictionary, and SHALL NOT delete a staging location that still holds another
loaded dictionary's files, since one import folder can carry several
dictionaries. Removing a failed import SHALL NOT be performed automatically as a
side effect of scanning; it happens only in response to the user's action.

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

#### Scenario: A failed import does not stop the rest of the scan
- **WHEN** a scan encounters a dictionary file that cannot be loaded alongside
  others that can
- **THEN** the failing file is reported and every loadable dictionary in the same
  scan is still loaded and usable

#### Scenario: A failed import can be removed
- **WHEN** the user acts on a reported load failure to remove it
- **THEN** the files that import staged are deleted, the failure stops being
  reported, and later scans no longer attempt that file

#### Scenario: Removing a failed import leaves loaded dictionaries alone
- **WHEN** the user removes a failed import whose folder also holds a dictionary
  that loaded successfully
- **THEN** the loaded dictionary's files remain and it keeps working

#### Scenario: Re-importing a folder clears a previous failed import
- **WHEN** the user re-imports a folder whose earlier import failed to load
- **THEN** the new import is staged and loaded, and the previously reported
  failure is no longer shown

#### Scenario: A superseded failed import leaves no stale copy
- **WHEN** a failed import is superseded by a successful re-import of the same
  folder
- **THEN** the stale staged copy from the failed attempt is gone, so subsequent
  scans do not retry it or report it again

#### Scenario: Failures are not cleaned up without the user asking
- **WHEN** a scan reports a load failure and the user takes no action
- **THEN** the staged files are still present and the failure is still reported;
  the app does not delete an import on its own

#### Scenario: A StarDict dictionary's article images resolve after import
- **WHEN** the user imports a StarDict dictionary whose articles reference images
  held in its resource location
- **THEN** the resource files are staged, and an article that references one
  renders that image rather than a missing resource

#### Scenario: StarDict resource archives are staged
- **WHEN** a StarDict dictionary ships its resources as a `res.zip` or a
  `<base>.res.zip` archive beside it
- **THEN** that archive is staged, so the engine can read the resources it
  contains

#### Scenario: An unrelated res directory is not staged as resources
- **WHEN** a picked folder contains a directory named `res` but no StarDict
  dictionary beside it
- **THEN** that directory's contents are not staged as a dictionary's resources
