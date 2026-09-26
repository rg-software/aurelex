## ADDED Requirements

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
