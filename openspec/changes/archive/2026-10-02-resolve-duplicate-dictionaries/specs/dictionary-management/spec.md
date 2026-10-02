## ADDED Requirements

### Requirement: Dictionary identity is name and content, not location
The system SHALL identify a dictionary by its normalized display name together
with a content signature derived from its complete set of source files, and SHALL
NOT treat the directory a dictionary's files happen to occupy as part of its
identity.

Two dictionaries whose normalized display names are equal SHALL be treated as the
same dictionary when deciding whether an import adds something new, regardless of
the format of either one. The system SHALL determine that two dictionaries are
identical by comparing their source-file sets and each file's size and
modification time, within the same tolerance the importer already applies when it
skips unchanged files; it SHALL NOT read file contents to make this determination.
Where the comparison is ambiguous because a file's modification time has drifted
while its size is unchanged, the system SHALL treat the dictionaries as differing.

#### Scenario: Two copies of one dictionary at different paths are one dictionary
- **GIVEN** the same dictionary is present in two stored locations
- **WHEN** the system determines each dictionary's identity
- **THEN** both resolve to the same identity, because their display names are
  equal and their locations are not part of that determination

#### Scenario: A different format of the same name is not a new dictionary
- **GIVEN** a dictionary named "Example Dictionary" is loaded, and a dictionary
  in a different format that also reports the name "Example Dictionary" is
  imported
- **THEN** the system treats it as the same dictionary rather than as a new one

#### Scenario: A small timestamp drift still counts as the same dictionary
- **GIVEN** a dictionary is loaded, and an identical copy of it whose file
  modification times differ by less than the importer's existing tolerance
- **WHEN** the user imports that copy
- **THEN** the system treats the two as the same dictionary, and does not add a
  second one

#### Scenario: A drifted timestamp beyond the tolerance means differing
- **GIVEN** a dictionary is loaded, and a copy of it whose file modification times
  differ by more than the importer's existing tolerance while every file size is
  unchanged
- **WHEN** the system compares the two
- **THEN** it treats them as differing, because the comparison rests on size and
  modification time and the system does not read file contents to decide

### Requirement: An import of an identical dictionary is silently skipped
When an imported dictionary's identity resolves to a dictionary the app already
has, and the two are identical in content, the system SHALL keep the dictionary it
already has, SHALL NOT add a second dictionary to the list, and SHALL delete the
newly imported copy together with the storage it occupied. The system SHALL
report nothing about this outcome: no message, no row, and no prompt.

The dictionary the app already had SHALL be left entirely untouched — the same
object, at the same position in the list, with the same group membership and the
same built indexes — and SHALL remain searchable without a restart.

The deletion SHALL cover the whole imported file set, including a resource tree
belonging to the discarded dictionary, and SHALL NOT remove a stored directory
that still holds another dictionary the system has kept.

#### Scenario: Re-importing a folder that already holds its dictionaries
- **GIVEN** a user keeps their dictionaries in one folder and has imported it, and
  the user later re-imports the same folder
- **WHEN** the import completes
- **THEN** every dictionary in that folder appears once in the list, nothing was
  added, and nothing about the re-import is reported to the user

#### Scenario: A skipped import leaves the existing dictionary untouched
- **GIVEN** a dictionary is loaded, in a group, at a known position in the list,
  and the user imports an identical copy of it from another folder
- **WHEN** the import completes
- **THEN** the dictionary keeps its position and its group membership, keeps its
  built indexes, and is searchable, and no second dictionary appears

#### Scenario: A skipped multi-file dictionary is deleted whole
- **GIVEN** a dictionary consisting of a primary file and its resource files is
  loaded, and the user imports the identical set from a different folder
- **WHEN** the import completes
- **THEN** no dictionary is added, and the discarded copy's primary file and every
  resource file belonging to it are gone, so no orphaned files remain

#### Scenario: A sibling dictionary in the same location survives the skip
- **GIVEN** two dictionaries were imported from one folder
- **WHEN** one of them is skipped as already present
- **THEN** the other remains stored and loaded, and is not affected

### Requirement: A differing same-named import is rejected and reported
When an imported dictionary's identity resolves to a dictionary the app already
has, but the two differ in content, the system SHALL delete the imported copy,
SHALL keep the dictionary the app already has completely unchanged, and SHALL NOT
add a second dictionary with that name. The system SHALL report the rejected
dictionary by name together with the reason, and SHALL NOT ask the user anything
before doing so.

The system SHALL NOT interrupt the rest of the import: the remaining dictionaries
in the same pick SHALL be imported, scanned and indexed as usual, and the
rejection SHALL NOT prevent any other dictionary from being added. The import
SHALL NOT delete, replace or modify the dictionary the app already had, and
SHALL NOT leave any part of the rejected copy in the app's storage.

The user resolves a rejection by removing the dictionary the app already has and
importing again; after that removal the same import succeeds and the new
dictionary is added normally.

#### Scenario: A differing version does not become a second dictionary
- **GIVEN** a dictionary named "Example Dictionary" is loaded from one folder
- **WHEN** the user imports a different build of "Example Dictionary" from
  another folder
- **THEN** exactly one dictionary with that name remains, it is the build already
  present and is unchanged, and the rejected build is reported by name with the
  reason it was not imported

#### Scenario: The rest of the pick is unaffected
- **GIVEN** a picked folder contains one dictionary that clashes with one already
  present and ten that are new
- **WHEN** the user picks that folder
- **THEN** all ten new dictionaries are imported, scanned and indexed, the
  clashing one is reported, and the import is not presented as having failed

#### Scenario: Nothing is deleted before the user is asked
- **GIVEN** an imported dictionary clashes with one already present
- **WHEN** the import completes
- **THEN** the app asks the user nothing, and the dictionary the app already had
  and its stored files are untouched

#### Scenario: Removing the old dictionary then re-importing succeeds
- **GIVEN** a build was rejected because a different build of the same name is
  installed
- **WHEN** the user removes the installed dictionary and imports the rejected
  build again
- **THEN** the dictionary is added, and it no longer clashes with anything

### Requirement: A scan resolves duplicates already present
The system SHALL apply the same identity rule to every scan, including the first
scan after the app starts, so that duplicates already present in storage are
resolved by a scan and do not return on every restart. For each set of loaded
dictionaries sharing an identity:

- where the copies are identical in content, the system SHALL collapse them to a
  single dictionary, keeping one and deleting the others together with the
  storage they occupied, without reporting anything and without asking;
- where the copies differ in content, the system SHALL leave all of them in place
  and report the name as present more than once with different content, because
  no user request distinguishes a new version from an unrelated same-named
  dictionary.

The system SHALL act without asking only where the action cannot lose a
dictionary: collapsing identical copies preserves the dictionary's content exactly.
Where copies differ, the system SHALL NOT remove any of them on its own, and the
user SHALL resolve it by removing one of them through the normal removal path. A
dictionary left in place SHALL remain loaded, searchable, in its position and in
its groups until the user acts.

#### Scenario: Identical duplicates are collapsed on the next scan
- **GIVEN** two identical copies of one dictionary are stored under different
  locations
- **WHEN** a scan runs, including the scan at app start
- **THEN** one dictionary with that name remains, the redundant copy and its
  stored files are deleted, nothing is reported to the user, and the survivor
  keeps its position and its group membership

#### Scenario: Collapsing duplicates repairs an existing installation
- **GIVEN** the app already holds two identically-named identical copies of a
  dictionary before this behaviour is introduced
- **WHEN** the user updates the app and a scan runs
- **THEN** the duplicate is collapsed without a re-import, and the dictionary
  remains listed, searchable and in its groups

#### Scenario: Differing same-named dictionaries are reported, not resolved
- **GIVEN** two stored dictionaries share a display name but differ in content
- **WHEN** a scan runs
- **THEN** both remain in the list, neither is removed, and the name is reported
  as present more than once with different content

#### Scenario: A report does not read as a load failure
- **GIVEN** a same-name conflict has been reported
- **WHEN** later scans run
- **THEN** the app does not tell the user to re-add a folder that is already
  added, and does not report the conflict as a dictionary that failed to load

#### Scenario: The user resolves a conflict by removing one
- **GIVEN** a same-name conflict has been reported
- **WHEN** the user removes one of the two through the normal removal path
- **THEN** that dictionary's stored files are deleted and the other remains
  loaded, searchable and in its groups
