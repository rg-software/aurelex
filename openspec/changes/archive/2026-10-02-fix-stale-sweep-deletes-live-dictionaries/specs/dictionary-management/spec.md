## ADDED Requirements

### Requirement: A staged import is never reclaimed while a dictionary in it loads

A staged import directory that a dictionary loads from SHALL NOT be deleted. This
applies to every reclamation the app performs on its own initiative, including the
reclamation that runs as part of a routine scan, because the staged copy is the only
copy the app owns: a deletion here is permanent and the user is not asked.

Whether a staged directory holds a dictionary SHALL be decided over the whole staged
tree, because both staging and the scan that follows it cover subfolders
recursively. A directory whose only supported dictionary file sits in a subfolder
SHALL be treated as holding a dictionary.

#### Scenario: A nested import is not reclaimed by a routine scan
- **WHEN** a staged import directory holds a supported dictionary file only inside a
  subfolder, and a routine scan loads that dictionary
- **THEN** the staged directory is not deleted, and the dictionary remains loaded and
  searchable

#### Scenario: A nested import survives an app restart
- **WHEN** the app is closed and reopened after importing a folder whose dictionary
  files are in subfolders
- **THEN** the startup scan loads those dictionaries from their staged copies and
  does not delete the staged directory

#### Scenario: The first scan after launch does not reclaim a live import
- **WHEN** the app starts, its startup scan loads dictionaries, and a staged directory
  is a candidate for reclamation
- **THEN** the loaded dictionaries for that scan decide whether the directory is in
  use, so a directory a loaded dictionary reads from is not reclaimed on that first
  scan or on any later one

### Requirement: Reclaiming a staged directory requires positive evidence

A staged directory SHALL be deleted only when the scan positively established that no
dictionary loads from it. A directory SHALL NOT be deleted merely because a load
failure was reported inside it while other dictionaries in the same directory load
successfully, and a reported failure SHALL NOT authorise deleting files that another
loadable dictionary in the directory depends on.

#### Scenario: A directory holding no dictionary file at all is reclaimed
- **WHEN** a staged directory contains no supported dictionary file anywhere beneath
  it and no loaded dictionary reads from it
- **THEN** the directory is deleted, so emptied and abandoned directories do not
  accumulate

#### Scenario: A reported failure does not take a directory's working dictionaries with it
- **WHEN** a staged directory holds a file the engine could not load alongside a
  dictionary that loaded successfully
- **THEN** the staged directory is not deleted, the loadable dictionary keeps working,
  and the failure stays reported

#### Scenario: A partially removed import's leftovers are still reclaimed
- **WHEN** a directory holds no dictionary file because the dictionary that occupied
  it was removed
- **THEN** the directory is reclaimed, so a removal does not leave a directory behind
  that would block re-importing the same dictionary