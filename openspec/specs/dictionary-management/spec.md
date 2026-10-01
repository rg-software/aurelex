# dictionary-management Specification

## Purpose

Lets a user load offline dictionaries onto an Android device by selecting a dictionary folder, and gives the app a stable, testable contract for which formats are supported and how index caches are built and refreshed on device.
## Requirements
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

### Requirement: Index build and validation on device
The system SHALL build a lookup index for each loaded dictionary on the device when that dictionary's index does not yet exist or is out of date, and SHALL show the user the progress of the build.
Lookup MUST NOT return results for a dictionary until its index build has finished.
A dictionary's index SHALL be written inside the app's index directory, and the system MUST NOT write a dictionary index outside that directory. The index directory given to the engine SHALL be treated as a directory regardless of whether the caller supplies a trailing separator, so a caller that omits it does not cause indexes to be placed beside the directory instead of inside it.

#### Scenario: First-time load triggers indexing
- **WHEN** the user loads a dictionary whose index has never been built
- **THEN** the app shows an indexing progress indication and does not offer results from that dictionary until indexing completes

#### Scenario: Index is up to date
- **WHEN** the user loads a dictionary whose index is already valid
- **THEN** the app skips indexing and makes that dictionary available immediately

#### Scenario: Index is out of date
- **WHEN** the underlying dictionary file has changed or the index format version differs from the engine's
- **THEN** the app rebuilds the index for that dictionary and informs the user that reindexing was needed

#### Scenario: Indexes are contained in the index directory
- **WHEN** a dictionary's index is built
- **THEN** the index file is created inside the app's index directory, and no index file is created beside that directory or anywhere else outside it

#### Scenario: Index directory is used even without a trailing separator
- **WHEN** the index directory is supplied to the engine without a trailing separator
- **THEN** the engine still writes indexes inside that directory, and the directory is not left empty

#### Scenario: A stale index directory is not mistaken for a populated one
- **WHEN** a dictionary's index has been built successfully
- **THEN** the app's index directory is non-empty and contains that dictionary's index

#### Scenario: Index placement is verified automatically
- **WHEN** the build-time engine check imports a dictionary and builds its index
- **THEN** the check fails if the resulting index is not inside the supplied index directory

### Requirement: Continuous processing indication
While the app is working through an import — copying a picked folder into app
storage, scanning it, and automatically building the missing full-text indexes —
the system SHALL keep a single processing indication visible continuously for the
whole chain, rather than toggling it off and on at each phase boundary. The
indication's label MAY change to name the current phase, but it MUST NOT blink
off while any phase of the chain is still running, and it MUST clear once the
whole chain finishes (or fails).

#### Scenario: Import chain shows one uninterrupted indication
- **WHEN** the user imports a folder and the app copies, scans, and indexes it
- **THEN** the processing indication stays visible for the entire chain, changing
  only its label between phases (copying -> scanning -> indexing) and never
  disappearing in between

#### Scenario: Startup scan and index
- **WHEN** the app starts with dictionaries that still need indexing (no folder
  was just picked)
- **THEN** the indication is shown for the scan and the index build and clears
  when both are done

#### Scenario: Nothing to index clears the indication
- **WHEN** an import finishes scanning and every dictionary already has an index
- **THEN** the indication clears instead of remaining visible

#### Scenario: A stalled scan does not leave the indication stuck
- **WHEN** a scan fails to complete and the watchdog intervenes
- **THEN** the processing indication is cleared rather than left visible forever

### Requirement: Dictionary groups
The system SHALL let the user organize loaded dictionaries into multiple named groups, each an ordered subset, and SHALL let the user select which group is active for lookups. An implicit "All" group containing every loaded dictionary is always available. Managing groups, their membership, their order, and the active group is part of this capability. Groups SHALL persist across app restarts (membership stored by stable dictionary identifier and re-resolved after dictionaries load).
The name of the implicit "All" group is not stored by the app; it is derived from
that group's stable identifier and presented in the active language, so every
surface that names a group shows the same string for it. User-created groups keep
the name the user gave them.

Loading or re-scanning dictionaries SHALL NOT change the set of groups: the stored group set is the source of truth and a scan SHALL be idempotent for it, so importing a dictionary never adds, renames, or drops a group. Each group SHALL remain uniquely identifiable by its stored identifier across scans, and a stored group set that already contains the same identifier more than once SHALL be repaired to one group per identifier (keeping the union of their members) rather than being shown as duplicate rows.
A recorded lookup or favorite that refers to a group identifier which no longer
exists SHALL be re-pointed to the implicit "All" group, and the rewrite SHALL be
persisted, so the stored entry never claims a scope that is not there. The word
itself SHALL be kept.

The groups list SHALL present each group as a row tap: tapping a group row opens
its membership editor directly. A non-"All" group's editor supports add, remove,
and reorder; the "All" group opens the same editor in reorder-only mode (no
add/remove/rename, and "All" itself cannot be renamed or deleted). Each non-"All"
row SHALL expose only a delete control on the row (rename lives inside the
membership editor; there is no per-row edit/pencil control). The row SHALL NOT
show a technical subtitle (such as an internal id).

#### Scenario: All loaded dictionaries are the default group
- **WHEN** the user first loads dictionaries without creating any group
- **THEN** lookups use an implicit "All" group containing every loaded dictionary

#### Scenario: Create a group
- **WHEN** the user taps "Add group", types a name in the dialog, and confirms
- **THEN** the group is created and its membership editor opens immediately

#### Scenario: Duplicate group name is rejected
- **WHEN** the user creates a group whose name (case-insensitive) already exists
- **THEN** no group is created and an inline error is shown asking for another name

#### Scenario: Rename to an existing name is rejected
- **WHEN** the user renames a group to a name (case-insensitive) another group already has
- **THEN** the group keeps its old name and an inline error is shown

#### Scenario: Groups survive restart
- **WHEN** the user restarts the app after creating groups
- **THEN** the same named groups, membership, order, and active selection are restored

#### Scenario: Importing a dictionary does not duplicate groups
- **GIVEN** a dictionary that belongs to a group, and a newer build of that same dictionary
- **WHEN** the user imports the newer build and it is indexed
- **THEN** the groups list shows exactly the same groups as before, with no second row for the group the dictionary belongs to

#### Scenario: Repeated scans leave the group set unchanged
- **WHEN** dictionaries are scanned more than once in a session (for example the user imports several dictionaries in a row)
- **THEN** the number of groups, their names, their membership, and their order are identical after every scan
#### Scenario: The built-in group is named in the active language
- **WHEN** the groups list, a group picker, a search scope control, a history row, a favorites row, or the membership editor header names the implicit "All" group
- **THEN** that name is the active language's word for it, not an English literal

#### Scenario: A user-created group keeps its own name
- **WHEN** the user has created a group with a name they typed
- **THEN** that group is presented under the name the user gave it, in every surface

#### Scenario: A lookup recorded against a deleted group is re-pointed
- **GIVEN** a lookup or favorite was recorded in a group that has since been deleted
- **WHEN** the app loads or the group is deleted
- **THEN** that entry is attributed to the implicit "All" group, the word is kept, and the change is persisted

#### Scenario: A re-pointed entry looks up in the group it names
- **GIVEN** a history row was re-pointed to the implicit "All" group
- **WHEN** the user taps that row
- **THEN** the lookup runs in the group the row now names

#### Scenario: Group identity is stable across scans
- **WHEN** dictionaries are scanned again after a group was created
- **THEN** that group still resolves to the same identifier, so selecting it, editing its membership, renaming it, and deleting it all act on the one group the user created

#### Scenario: A stored group set with a repeated identifier is repaired
- **GIVEN** a stored group set in which one group's identifier appears more than once
- **WHEN** the app next loads dictionaries
- **THEN** the groups list shows that group once, containing the members of every entry that shared the identifier, and the stored group set no longer contains the repeat

#### Scenario: Select the active group
- **WHEN** the user picks a group as active
- **THEN** subsequent lookups use only that group's dictionaries, in that group's order

#### Scenario: Reorder dictionaries within a group
- **WHEN** the user drags a group member up or down within the members list (grabbing the row's left-hand drag handle; the name area and the trailing Remove control are not drag surfaces, so a drag starting on them scrolls the list instead)
- **THEN** the combined article for that group respects the new order, the member list re-orders live as the row crosses row boundaries, and the row being dragged stays visually highlighted while the gesture is active

#### Scenario: Reorder affordance is only on group members
- **WHEN** the user views the membership editor
- **THEN** only rows in the "in this group" list are draggable for reordering; dictionaries in the "available to add" list cannot be reordered

#### Scenario: Membership editor exposes icon-based controls
- **WHEN** the user opens a group's membership editor
- **THEN** the back control, the rename control, the remove-from-group control and the add-to-group control are all icons (no text-only action links), and reordering happens by dragging the member rows

#### Scenario: Reorder reflects immediately after a move
- **WHEN** the user drags a member row to a new position
- **THEN** the member list re-orders to the new group order as soon as the engine commits, without needing an extra refresh

#### Scenario: Rename inside the editor keeps the title in sync
- **WHEN** the user renames a group from inside its membership editor
- **THEN** the editor's header (the group name alone, no "Group:" prefix) updates to the new name immediately, without requiring a screen refresh

#### Scenario: Open the membership editor from the group row
- **WHEN** the user taps a group's row in the groups list
- **THEN** the membership editor for that group opens (for non-"All" groups: add/remove dictionaries and reorder; for "All": reorder only)

#### Scenario: Rename a group from within the membership editor
- **WHEN** the user opens a group's membership editor, taps its rename action, and confirms a new non-empty name
- **THEN** the group is renamed and the groups list shows the new name

#### Scenario: Rename rejects an empty name
- **WHEN** the user confirms a rename with a blank name
- **THEN** the group keeps its existing name

#### Scenario: Rename field does not pre-select the whole name
- **WHEN** the rename dialog opens
- **THEN** the current name is prefilled and the cursor is placed in the field, without selecting the whole name

#### Scenario: Delete a group is confirmed before acting
- **WHEN** the user taps the delete control on a non-"All" group row
- **THEN** the app asks for confirmation (OK/cancel) before the group is removed

#### Scenario: Delete a group
- **WHEN** the user confirms deletion of a group
- **THEN** the group no longer appears in the list, and lookups fall back to the "All" group (or the next active group), without error

#### Scenario: Delete a group that is active
- **WHEN** the user deletes the currently active group
- **THEN** the app falls back to the "All" group so lookups keep working

#### Scenario: The All group is reorder-only
- **WHEN** the user opens the "All" group
- **THEN** its editor has no add, remove, rename, or delete controls, and dragging its rows changes the search article order

#### Scenario: Group row opens its membership editor
- **WHEN** the user taps a group's row in the groups list
- **THEN** the membership editor for that group opens (for non-"All" groups: add/remove dictionaries and reorder; for "All": reorder only)

#### Scenario: The "All" group opens in reorder-only mode
- **WHEN** the user taps the "All" group row
- **THEN** the editor opens showing every dictionary in article order, with no add/remove/rename controls; dragging a row changes the search article order

#### Scenario: Delete needs confirmation
- **WHEN** the user taps the trash control on a non-"All" group row
- **THEN** the app asks for confirmation before the group is removed

### Requirement: Remove a loaded dictionary
The system SHALL let the user permanently remove an imported dictionary from the
app, deleting its staged copy and its built indexes, and SHALL remove it
consistently from lookups, groups, and full-text search so no stale results
reference it.

Removal SHALL act on exactly the dictionary or dictionaries the user selected.
The identity of a removed dictionary MUST NOT depend on its position in the
displayed list: the list is sorted for presentation, and that order may differ
from the order the engine loaded the dictionaries in. Removing a multi-selection
SHALL remove each selected dictionary once, and only those dictionaries.

Deleting the staged copy SHALL mean the whole of it: the dictionary's primary
file, every companion file it was staged with, and any resource tree staged
alongside them. Removing a dictionary SHALL NOT leave files of that dictionary
in the staged location, and SHALL NOT leave its staged directory behind holding
those files. A staged directory that was emptied by the removal SHALL be
reclaimed, so removal neither retains the dictionary's storage nor leaves a
directory that no dictionary uses.

A staged directory SHALL NOT be reclaimed while any other loaded dictionary
still reads from it: one imported folder can hold several dictionaries, and
removing one MUST NOT delete a sibling's files. Equally, a staged directory
SHALL NOT be retained on behalf of a dictionary that has itself just been
removed.

Removing a dictionary MUST NOT prevent that dictionary from being imported
again. A removal SHALL NOT leave anything behind that causes a later import of
the same dictionary to fail or to produce a dictionary that cannot be loaded.

The dictionary's indexes SHALL be deleted from the app's index directory - the
directory the engine writes them into, as the dictionary's identifier and its
`_FTS_*` companions - and no pre-fix index left beside that directory for the
same identifier SHALL survive the removal. Removing one dictionary SHALL leave
every other dictionary's indexes untouched. The effect on groups SHALL be
durable immediately, not only after the next scan.

Removal SHALL be available at any time, including while the app is staging,
scanning, or full-text indexing: a removal issued during those phases SHALL be
applied within a bounded time (at most one indexing slice, not the whole chain),
and a removal issued while a full-text index build for that dictionary is
running SHALL cancel or drop that build so the removed dictionary is neither
left holding storage nor reintroduced by the build, while other dictionaries'
builds continue unaffected.

#### Scenario: Remove an individual dictionary
- **WHEN** the user removes one loaded dictionary
- **THEN** that dictionary's entry disappears from the dictionary list, its
  staged files and its indexes are deleted, and it no longer contributes
  results to lookups, groups or full-text search

#### Scenario: All of the dictionary's staged files go, not only the primary one
- **WHEN** a dictionary staged with companion files and a resource tree is removed
- **THEN** its primary file, its companions and its resource tree are all
  deleted, so none of that dictionary's files remain in the staged location

#### Scenario: The emptied staged directory is reclaimed
- **WHEN** a dictionary is removed and no other loaded dictionary reads from its
  staged directory
- **THEN** that staged directory is removed rather than left behind, so the
  removal releases the storage the dictionary occupied

#### Scenario: A removed dictionary can be imported again
- **WHEN** the user removes a dictionary and then imports the same dictionary
  again
- **THEN** the import succeeds and the dictionary loads, rather than being
  blocked by anything the removal left behind

#### Scenario: A leftover from an earlier removal does not block re-import
- **WHEN** a staged directory left behind by a previous removal still holds that
  dictionary's companion files but not its primary file
- **THEN** the dictionary can still be imported and loaded, and that leftover
  directory is reclaimed rather than reused in its incomplete state

#### Scenario: A staged directory shared with a surviving dictionary is kept
- **WHEN** one imported folder holds several dictionaries and the user removes
  one of them
- **THEN** the staged directory survives and the dictionaries that were not
  removed still load and keep working

#### Scenario: The removed dictionary does not itself keep its directory alive
- **WHEN** a dictionary is removed and it was the only dictionary reading from
  its staged directory
- **THEN** the shared-directory guard does not treat the removed dictionary as a
  remaining user of that directory

#### Scenario: A leftover staged directory holding no dictionary is reclaimable
- **WHEN** a staged directory remains that holds no primary file any dictionary
  loads
- **THEN** it is reclaimed rather than accumulating, including one left behind by
  an earlier removal

#### Scenario: Removal targets the selected dictionary regardless of list order
- **WHEN** the user removes a dictionary whose position in the displayed list
  differs from its engine load order
- **THEN** the dictionary that is actually removed is the one selected

#### Scenario: Multi-select removal removes exactly the selection
- **WHEN** the user selects several dictionaries and removes them
- **THEN** exactly those dictionaries are removed, each once, and no other
  dictionary is affected

#### Scenario: The index inside the index directory is deleted
- **WHEN** a loaded dictionary is removed
- **THEN** its index, and the `_FTS_*` companions belonging to it, are deleted
  from the app's index directory

#### Scenario: A pre-fix index beside the index directory is also deleted
- **WHEN** a dictionary is removed whose index was built by a version that placed
  indexes beside the index directory rather than inside it
- **THEN** that stray index is deleted too, so no index for a removed dictionary
  survives

#### Scenario: Other dictionaries keep their indexes
- **WHEN** one dictionary is removed while others remain loaded
- **THEN** every remaining dictionary's index is still present and those
  dictionaries stay searchable

#### Scenario: Removal is reflected in groups
- **WHEN** a removed dictionary belonged to a group
- **THEN** it no longer appears in that group

#### Scenario: Removal's effect on groups survives a restart
- **WHEN** the user removes a dictionary that belonged to a group and then
  restarts the app
- **THEN** the dictionary is still absent from the group, and no stale
  membership referencing it is restored

#### Scenario: Removal is reflected in full-text search
- **WHEN** a dictionary is removed
- **THEN** full-text search no longer returns results from it

#### Scenario: Multi-select removal is immediate
- **WHEN** the user removes a multi-selection of dictionaries
- **THEN** all of them are removed in one action and the list reflects every
  removal without a further interaction

#### Scenario: Re-add after removal
- **WHEN** the user permanently removes a dictionary and then imports the same
  dictionary again
- **THEN** it is added back as a fresh entry with a working index

#### Scenario: Remove control is available during processing
- **WHEN** the app is staging, scanning, or building an index and the user
  removes a dictionary
- **THEN** the removal is applied within a bounded time rather than waiting for
  the whole chain to finish

#### Scenario: Remove while a full-text build is running
- **WHEN** a full-text index build is running for a dictionary and the user
  removes that dictionary
- **THEN** the build is cancelled or dropped, the dictionary is not reintroduced
  by it, and other dictionaries' builds continue unaffected

#### Scenario: Remove while staging or scanning
- **WHEN** the user removes a dictionary while a different import is being
  staged or scanned
- **THEN** the removal takes effect and the in-flight staging or scanning is not
  corrupted by it

### Requirement: Folder additions are serialized, never dropped
The system SHALL accept dictionary folder additions requested while a previous
folder's files are still being staged into app storage, queueing the pending
folder and processing it immediately after the current copy completes, instead
of discarding it.

#### Scenario: Second pick during an active stage copy
- **WHEN** the user picks a second dictionary folder while the first one is
  still being copied into app storage
- **THEN** the second folder is not lost: after the first copy finishes, the
  second is staged and its dictionaries are scanned and indexed

#### Scenario: A single pick that fails is surfaced
- **WHEN** staging a queued folder fails (e.g. the grant was revoked before the
  copy ran)
- **THEN** the app reports the failure and leaves the other dictionaries
  unaffected, without silently discarding the failed folder

### Requirement: Dictionary display metadata
The system SHALL show each dictionary in the Dicts list with its source/target
language pair and an approximate size, instead of its raw file path, so the
list is readable without exposing storage details. For a dictionary installed
from the catalog, the row SHALL show that entry's display name in the app's
active language when it provides one, falling back to the dictionary's own name.
When a dictionary is still being indexed and its size is not yet known, the size
SHALL be omitted (shown once known). When a source or target language is not
known, it SHALL be shown as `?`.

#### Scenario: Row shows language pair and size
- **WHEN** the user opens the Dicts tab
- **THEN** each dictionary row shows its name, then `Source/Target` and an
  approximate size (e.g. `English/Russian · 145 MB`), and never the file path

#### Scenario: A catalog-installed dictionary uses its localized name
- **WHEN** a dictionary installed from the catalog has an entry that provides a
  display name for the app's active language
- **THEN** the row shows that name instead of the dictionary's own name

#### Scenario: A dictionary without a catalog entry keeps its own name
- **WHEN** a dictionary has no catalog entry (it was imported from a folder)
- **THEN** the row shows the dictionary's own name

#### Scenario: Unknown language pair
- **WHEN** a dictionary's source or target language is not known
- **THEN** the unknown side is displayed as `?` (e.g. `English/? · 12 MB`)

#### Scenario: Size hidden while indexing
- **WHEN** a dictionary is still being full-text indexed and its size is unknown
- **THEN** the row shows the language pair without the size, and the size appears
  once indexing finishes and the size is known

### Requirement: By-Pair grouped dictionary list
The system SHALL let the user toggle a "By Pair" grouping on the Dicts tab. When
off, dictionaries are sorted alphabetically by name. When on, dictionaries are
grouped under color-highlighted caption rows, one per source/target language
pair, sorted alphabetically by pair; within each pair the dictionaries are
sorted alphabetically by name.

#### Scenario: Toggle off shows flat alphabetical list
- **WHEN** "By Pair" is off
- **THEN** dictionaries are listed in one flat list sorted alphabetically by name

#### Scenario: Toggle on groups by language pair
- **WHEN** "By Pair" is on
- **THEN** dictionaries are grouped under caption rows labeled by their
  source/target pair, pairs are sorted alphabetically, and dictionaries within a
  pair are sorted alphabetically by name

### Requirement: Batch and per-pair dictionary removal
The system SHALL let the user remove several selected dictionaries at once via a
single "Remove" control; this is the only dictionary-deletion path. There SHALL
be no per-row delete button and no remove-a-whole-pair caption action. In the
By-Pair view, tapping a pair (section) header selects or clears every dictionary
in that pair as a whole, as a shortcut for building a selection to remove.

#### Scenario: Remove a language pair
- **WHEN** the user taps a pair (section) header in the By-Pair view twice
- **THEN** the pair's dictionaries are selected then deselected again — pair
  header taps only select/clear, they never delete; removal uses the selection
  Delete button

#### Scenario: Multi-select and RemoveSelected
- **WHEN** the user taps dictionary rows to select them (at least one) and then
  taps Remove
- **THEN** all selected dictionaries are permanently removed immediately (with no
  confirmation) and the selection is cleared

#### Scenario: RemoveSelected is disabled with no selection
- **WHEN** no dictionary rows are selected
- **THEN** the Remove button is disabled; it becomes enabled once at least one
  dictionary is selected

#### Scenario: No per-row or per-pair delete actions
- **WHEN** the user views the dictionary list (flat or by-pair)
- **THEN** there is no delete control on individual dictionary rows and no remove
  action on pair caption rows; deletion happens only through the selection
  Delete button

#### Scenario: Pair header selects the whole section
- **WHEN** the user taps a pair (section) header in the By-Pair view
- **THEN** every dictionary in that pair becomes selected (the header shows a
  check); tapping again clears the pair's selection

### Requirement: Re-importing an updated dictionary reloads it in the session
When a dictionary's source files are replaced on disk - the ordinary case of importing a newer build of a dictionary already loaded, which keeps the same source path and therefore the same dictionary identity - the system SHALL detect the change on the next scan and reload that dictionary, so the updated content takes effect without restarting the app. The reloaded dictionary SHALL be fully searchable (article lookup and prefix search) immediately after the reload, and a scan SHALL NOT leave a loaded dictionary reading an index that was written for a different version of its content.

Dictionaries whose source files have not changed SHALL NOT be reloaded: a scan over unchanged dictionaries leaves them, and their index state, untouched.

#### Scenario: Re-importing an updated dictionary makes the new data live
- **GIVEN** a dictionary is loaded and searchable, and the user imports a newer build of the same dictionary (same folder and file name)
- **WHEN** the import's scan completes
- **THEN** the dictionary reflects the new content in the running session, so a headword that exists only in the new build resolves without restarting the app

#### Scenario: Search still works after a re-import
- **WHEN** a dictionary is reloaded because its source changed
- **THEN** article lookup and prefix search on that dictionary return results, and neither stalls waiting on an unreadable index

#### Scenario: A scan does not rewrite an index under a loaded dictionary
- **WHEN** the scanner processes a dictionary whose source file changed
- **THEN** the index it rebuilds belongs to the dictionary instance that remains loaded, so no loaded dictionary is left reading an index written for different content

#### Scenario: Unchanged dictionaries are not reloaded
- **GIVEN** a set of loaded dictionaries whose source files are unchanged
- **WHEN** a scan runs
- **THEN** no dictionary is reloaded and their index state is preserved

### Requirement: Dictionaries can be added from the remote catalog
The system SHALL let the user add a dictionary from the curated remote catalog as
an alternative to picking a folder, and SHALL download the entry's files into
app-private dictionary storage and make them available in the dictionary list
through the same scanning and indexing path as a folder import. A
catalog-installed dictionary SHALL require no storage permission and SHALL be
indistinguishable from a folder-imported one afterwards. The system SHALL NOT
request or require system-wide storage access to add a dictionary this way.

#### Scenario: Catalog entry is added
- **WHEN** the user downloads an entry from the remote catalog and the download
  completes
- **THEN** its files are placed in app-private dictionary storage, the
  dictionary is listed with the other dictionaries, and it is indexed
  automatically like a folder-imported dictionary

#### Scenario: Catalog install needs no storage permission
- **WHEN** the user adds a dictionary from the remote catalog
- **THEN** the app requests no storage permission and no system-wide storage
  access

#### Scenario: Download joins the same import path
- **WHEN** a catalog download completes
- **THEN** the downloaded files are picked up by the app's existing dictionary
  scan and full-text indexing, with no separate registration step and no
  separate management surface

#### Scenario: Catalog dictionary survives a restart
- **WHEN** the app is closed and reopened after a catalog dictionary was
  installed
- **THEN** the dictionary loads from app-private storage like any other imported
  dictionary

#### Scenario: Unsupported file in a catalog entry
- **WHEN** a catalog entry names a file in a format the app does not support
- **THEN** the app does not install that file as a dictionary and reports the
  entry as not installable rather than failing silently

### Requirement: Catalog-installed dictionaries are managed like imported ones
The system SHALL treat a dictionary installed from the remote catalog as a
member of the app's dictionary set with no special handling: it SHALL be
permanently removable through the same multi-select removal path, SHALL be
removable while an unrelated download or import is in progress, and SHALL have
its stored files and built indexes deleted on removal. Re-downloading an entry
the app already has SHALL NOT create a duplicate entry.

#### Scenario: Removing a catalog-installed dictionary
- **WHEN** the user selects a catalog-installed dictionary and removes it
- **THEN** it is deleted from the list along with its stored files and indexes,
  and it no longer appears in lookups, groups, or full-text search

#### Scenario: Removal while a download runs
- **WHEN** the user removes a dictionary while an unrelated catalog download is
  in progress
- **THEN** the removal completes and the download continues

#### Scenario: Re-downloading an installed entry
- **WHEN** the user downloads a catalog entry that is already installed
- **THEN** the dictionary appears once in the list, not twice

### Requirement: Late-arriving resources are adopted by a loaded dictionary
The system SHALL make a dictionary pick up resources that arrive after it was
already loaded, when those resources are downloaded for it later, and SHALL
rebuild that dictionary's lookup index as needed to use them. The system SHALL
NOT rebuild the dictionary's full-text index for this, SHALL NOT require the
user to reinstall the dictionary, and SHALL NOT require an app restart. The
dictionary's position in the list and its group membership SHALL be preserved.

#### Scenario: Resources added to a loaded dictionary
- **WHEN** optional resources are downloaded for a dictionary that is already
  loaded and indexed
- **THEN** the dictionary is reloaded so the resources take effect, its lookup
  index is rebuilt, and it remains listed in the same position and in the same
  groups

#### Scenario: Full-text index is preserved
- **WHEN** a loaded dictionary adopts newly downloaded resources
- **THEN** the dictionary keeps its existing full-text index and no full-text
  rebuild is performed for it

#### Scenario: No restart required
- **WHEN** a loaded dictionary adopts newly downloaded resources
- **THEN** the resources are usable without the user restarting the app

### Requirement: Group surfaces use standard icon controls
The Groups list's add control and the membership editor's rename control SHALL be icon buttons in the app's standard icon-button style (an icon glyph with no visible text label), matching the icon controls in the dictionary toolbar. Each SHALL expose the documented invariant English accessible name regardless of the display language — "Add group" for the add control and "Rename group" for the rename control.

#### Scenario: Add control is an icon button
- **WHEN** the user views the Groups list
- **THEN** the add control is an icon button with no visible text label, its accessible name is "Add group", and tapping it opens the new-group name dialog

#### Scenario: Rename control is a standard icon button
- **WHEN** the user opens a non-built-in group's membership editor
- **THEN** its rename control is an icon button in the app's standard icon-button style, its accessible name is "Rename group", and tapping it opens the rename dialog

### Requirement: Membership editor groups available dictionaries by pair
The membership editor SHALL offer a By Pair toggle. When it is on, the available-to-add list SHALL present dictionaries grouped under source/target pair captions using the same pairing as the dictionary list, with pairs sorted alphabetically and dictionaries within a pair sorted alphabetically by name. The member list SHALL NOT be grouped by pair: it SHALL remain a single flat list in the group's order, and dragging SHALL continue to set that order. When the toggle is off, the available-to-add list SHALL be a flat list.

#### Scenario: Toggle on groups the available list by pair
- **WHEN** the user turns By Pair on in a membership editor
- **THEN** the available-to-add list shows pair caption rows and its dictionaries are grouped under the caption matching their source/target pair

#### Scenario: Toggle off shows a flat available list
- **WHEN** the user turns By Pair off in a membership editor
- **THEN** the available-to-add list shows no pair captions

#### Scenario: Member list stays flat and reorderable
- **WHEN** By Pair is on and the user drags a row in the member list
- **THEN** the member list is not grouped into pair sections and the drag still changes the group's article order

#### Scenario: Available dictionaries cannot be reordered
- **WHEN** the user views the available-to-add list with By Pair on
- **THEN** its rows are not draggable, the same as with By Pair off

### Requirement: Membership editor names clear of row controls
A dictionary name shown in the membership editor SHALL be truncated in the middle when it is too long for its row, so that it never overlaps the row's trailing add-to-group or remove-from-group icon and those icons stay fully visible and tappable.

#### Scenario: Long name elides clear of the icon
- **WHEN** a dictionary with a name wider than the row is shown in the membership editor
- **THEN** the name is elided in the middle and does not run under the trailing add-to-group or remove-from-group icon

### Requirement: Group name dialogs stay centered
The create-group and rename-group dialogs SHALL lay out their name field and action buttons centered within the dialog for every label length, including longer translations, so no control is clipped or shifted off-center.

#### Scenario: Labels of any length stay centered
- **WHEN** the rename-group dialog is shown in a language whose action labels are longer than English
- **THEN** the name field and the action buttons remain centered within the dialog and fully visible

### Requirement: An empty error banner is not shown
The engine-error banner SHALL be shown only when the engine reports a non-blank message; a whitespace-only message MUST NOT paint the banner.

#### Scenario: Blank message paints nothing
- **WHEN** the engine reports a message that is empty or only whitespace
- **THEN** no error banner is shown

#### Scenario: A real message is shown
- **WHEN** the engine reports a non-blank message
- **THEN** the error banner is shown with that message

