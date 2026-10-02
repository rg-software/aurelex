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
compressed variants the engine accepts. A StarDict dictionary keeps the images
its articles reference in a sibling resource location, which the engine reads
from a `res` directory beside the dictionary, a `res.zip` beside it, or a
`<base>.res.zip`; staging SHALL copy whichever of those the picked folder
provides, so the dictionary's article images resolve after import rather than
being dropped. An MDict dictionary MAY ship its article assets either inside its
`.mdd` archive or loose, beside the `.mdx`, and the engine resolves a loose asset
from the dictionary folder before consulting the archive, so staging SHALL copy
those assets when the picked folder provides them beside a `.mdx`. Because a
stylesheet or image name is common, staging SHALL recognise such a file as a
dictionary's asset ONLY when a `.mdx` sits beside it in the same folder, and only
for the extensions an article embeds, so an unrelated asset elsewhere in a
picked tree is not staged. A StarDict dictionary whose companion
files were not staged MUST NOT be presented as imported, because the engine
cannot open it. The system SHALL NOT require system-wide storage access to add
dictionaries. Unsupported files in a picked location MUST NOT be treated as
dictionaries. There is no persistent "source" abstraction: each pick is a
one-off import and imported dictionaries simply belong to the app's dictionary
set until removed.

When a staged dictionary file cannot be loaded, the system SHALL report that
failure to the user and SHALL continue loading the other dictionaries in the same
scan. A staged source that cannot be loaded has no value to the user and cannot
become valid, so the system SHALL delete that source's files without waiting for
the user to act, and SHALL report it as deleted. That deletion SHALL be scoped to
the failing source's own files, so it applies even when the import folder holds
dictionaries that did load, and it SHALL NOT delete files belonging to a loaded
dictionary or a staging location that still holds another loaded dictionary's
files. Automatic deletion is confined to sources the engine has reported as
unloadable; it SHALL NOT delete any dictionary that loaded successfully, and the
user SHALL NOT be asked to confirm a deletion of their own import.

Re-importing a folder whose previous import ended in a failed load SHALL
supersede that failed import: after the re-import the failure SHALL no longer be
reported, and the stale staged copy SHALL NOT remain to be re-attempted on later
scans.

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
- **WHEN** a scan reports a source that cannot be loaded
- **THEN** the files that import staged are deleted, the failure stops being
  reported as needing the user's attention, and later scans no longer attempt
  that file

#### Scenario: Removing a failed import leaves loaded dictionaries alone
- **WHEN** the cleanup of a failed import runs in a folder that also holds a
  dictionary that loaded successfully
- **THEN** only the failing source's files are deleted, and the loaded
  dictionary's files remain and it keeps working

#### Scenario: A dictionary the user asked for is never deleted on its own
- **WHEN** a scan completes, however it reports its results
- **THEN** the app does not delete a dictionary that loaded successfully, and does
  not delete any part of a dictionary the user asked for, without the user acting
  on that dictionary

#### Scenario: Failures are not cleaned up without the user asking
- **WHEN** a scan reports that a source could not be loaded and the user takes no
  action
- **THEN** the only files deleted are those of the source that could not be loaded;
  the report stays until the user dismisses it or imports again, and nothing else
  is deleted on the app's initiative

> **Naming note for archive.** This scenario's name still says "not cleaned up",
> which the automatic deletion in this change makes misleading — the name survives
> only because OpenSpec requires a MODIFIED block to carry a current scenario's
> name verbatim. The body is the narrower guarantee that does survive: nothing but
> the unloadable source is deleted, and nothing the user asked for is deleted at
> all. Rename it to match (e.g. "Only an unloadable source is deleted without the
> user asking") in a later docs change.

#### Scenario: Re-importing a folder clears a previous failed import
- **WHEN** the user re-imports a folder whose earlier import failed to load
- **THEN** the new import is staged and loaded, and the previously reported
  failure is no longer shown

#### Scenario: A superseded failed import leaves no stale copy
- **WHEN** a failed import is superseded by a successful re-import of the same
  folder
- **THEN** the stale staged copy from the failed attempt is gone, so subsequent
  scans do not retry it or report it again

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

#### Scenario: An MDX set's loose assets are staged
- **WHEN** the user imports a folder containing an `.mdx` whose stylesheet or
  images sit beside it rather than inside a `.mdd`
- **THEN** those files are staged, and an article that references one is styled
  and shows its image rather than reporting a missing resource

#### Scenario: A loose asset is recognised only beside an MDX dictionary
- **WHEN** a picked folder contains a stylesheet or image but no `.mdx` beside it
- **THEN** that file is not staged as a dictionary's asset

#### Scenario: Files beside an MDX dictionary that no article embeds are not staged
- **WHEN** a folder holds an `.mdx` alongside files that are not article assets,
  for example a text note or an unrelated archive
- **THEN** only the dictionary files and the assets its articles embed are
  staged

## ADDED Requirements

### Requirement: Import results are reported in a purely informational banner
The system SHALL present the results of an import in the Dictionaries pane as a
notification that is informational only. The banner SHALL contain no control that
deletes stored files, because by the time it is shown nothing that the import
failed on is left to delete.

Each row SHALL name what did not get imported and why. Where a result has a
dictionary name, the row SHALL show that name rather than a file name, because a
file name inside app-private storage is not something the user recognises; a file
name SHALL be shown only where no dictionary name exists. The system SHALL
distinguish, in the wording of a row, between a source that could not be loaded,
a dictionary that was already present and therefore not added again, and a
dictionary that was not added because a different dictionary with the same name is
installed.

The banner SHALL be dismissed by a single control that removes it from view and
changes nothing else. Starting another import SHALL clear results from earlier
imports before the new results are shown, so the banner never describes a batch
other than the most recent one. The user SHALL be able to ignore the banner and
use the rest of the app as usual, and SHALL resolve anything actionable by removing
a dictionary through the normal Dictionaries list.

#### Scenario: A row names the dictionary and the reason
- **GIVEN** an import did not add a dictionary
- **WHEN** the user reads the banner
- **THEN** each row names the dictionary or file concerned and states the reason
  it was not added, in wording specific to why it was not added

#### Scenario: The banner deletes nothing
- **WHEN** an import reports a result
- **THEN** the banner offers no control that deletes stored files, and the stored
  files it refers to are in the state the app's own rules put them in

#### Scenario: Dismissing removes the banner and nothing else
- **WHEN** the user activates the banner's dismiss control
- **THEN** the banner is no longer shown, and no stored file and no dictionary is
  changed by dismissing it

#### Scenario: A new import clears stale results
- **GIVEN** a banner is showing results from an earlier import
- **WHEN** the user imports again
- **THEN** the earlier results are no longer shown, and the banner shows only the
  outcome of the import just performed

#### Scenario: The user carries on using the app
- **GIVEN** a banner is showing results
- **WHEN** the user navigates, searches, groups or removes dictionaries without
  dismissing it
- **THEN** every one of those actions works normally, and the banner does not
  block or change them

### Requirement: The import-results banner does not crowd out the dictionary list
The banner SHALL be shown in the Dictionaries pane above the dictionary list, and
SHALL be shown alongside it rather than in place of it. Its height SHALL be bounded
so that a large number of results cannot push the dictionary list out of view, and
its results SHALL scroll within that bound. The number of results SHALL always be
visible, so results that are scrolled out of view are still accounted for.

The banner SHALL NOT be shown when there is nothing to report, and it SHALL NOT be
shown for a purely successful outcome that the user has nothing to act on.

#### Scenario: Many results keep the dictionary list visible
- **GIVEN** an import produced more results than fit in the banner
- **WHEN** the user views the Dictionaries pane
- **THEN** the dictionary list is still visible below the banner, the results
  scroll within the banner, and the total number of results is shown

#### Scenario: Few results take only the space they need
- **WHEN** an import produced a small number of results
- **THEN** the banner is only as tall as its results, and the dictionary list
  takes the remaining space

#### Scenario: The banner is hidden when there is nothing to report
- **WHEN** there is nothing to report
- **THEN** the banner is not shown and does not occupy any space

#### Scenario: A fully successful import shows no banner
- **WHEN** an import added every dictionary it contained and nothing was skipped
  or rejected
- **THEN** the user is not given a results banner to dismiss

### Requirement: The import-results banner is announced to assistive technology
The banner's dismiss control SHALL expose an accessible name and role, and the
name SHALL be the same invariant English string in every shipped display language,
so that the control can be located reliably by accessibility-based automated
testing. The name SHALL describe dismissing the results rather than removing a
file, because the control deletes nothing.

#### Scenario: The dismiss control is reachable by its accessible name
- **WHEN** an accessibility client inspects the Dictionaries pane while the banner
  is showing
- **THEN** the dismiss control is present with its documented accessible name and
  role, in the invariant English form regardless of the display language

#### Scenario: The name does not describe a deletion
- **WHEN** the dismiss control is exposed to assistive technology
- **THEN** its accessible name refers to dismissing the results, not to removing or
  deleting a file
