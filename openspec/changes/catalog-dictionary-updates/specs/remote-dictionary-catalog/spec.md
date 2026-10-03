## MODIFIED Requirements

### Requirement: Browsing the catalog
The system SHALL present the catalog as a list of entries shown in place over the
Dictionaries pane, without adding a navigation destination. Each entry SHALL show
its display name, its source/target language pair, and the size of what will be
downloaded for it (including optional resources that are currently opted in), and
SHALL indicate whether the entry is already installed and whether an available
update exists for it. An entry's display name SHALL be shown in the app's active
language when the entry provides one for it, falling back to the entry's default
name. The catalog header SHALL state when the catalog was last checked, and SHALL
NOT present that time as a change to the catalog's content.

#### Scenario: Entries are listed
- **WHEN** the user opens the remote catalog
- **THEN** each entry is listed with its name, language pair, and download size

#### Scenario: An entry name follows the app's language
- **WHEN** the app's active language is one an entry provides a display name for
- **THEN** that name is shown instead of the entry's default name

#### Scenario: An entry name falls back
- **WHEN** the app's active language has no entry-provided display name
- **THEN** the entry's default name is shown

#### Scenario: Already-installed entry is marked
- **WHEN** a catalog entry's dictionary files are already present in the app's
  dictionary set
- **THEN** the entry is shown as installed and a fresh install is not offered for
  it (an available update, or its optional resources, can still be offered)

#### Scenario: Catalog is a read-only list
- **WHEN** the user views an installed catalog entry whose content matches the
  catalog
- **THEN** the entry is read-only: no install, update, or reinstall action is
  offered for it

#### Scenario: An available update is marked
- **WHEN** an installed entry's recorded content differs from the catalog's
  current content for it
- **THEN** the entry is shown as having an available update

#### Scenario: The header states when the catalog was last checked
- **WHEN** the catalog has been checked (fetched or served from the cached copy)
- **THEN** the header states when that check happened and does not describe it as
  a change to the catalog's content

#### Scenario: Leaving the catalog
- **WHEN** the user dismisses the catalog
- **THEN** the Dictionaries pane is shown as it was before the catalog opened

### Requirement: Installed catalog content is identifiable
The system SHALL record, for each entry installed from the catalog, the SHA-256
digest of the dictionary files it installed, so the installed content can be
compared against the catalog on a later probe without re-reading the files. The
recorded digests SHALL be the basis for detecting whether an installed entry has
an available update.

#### Scenario: Installing records the installed digests
- **WHEN** a dictionary is installed from the catalog
- **THEN** the system records the installed dictionary files' SHA-256 digests
  persistently

#### Scenario: Recorded digests identify installed content
- **WHEN** the recorded digest for an installed entry's dictionary file matches
  the catalog's digest for that file
- **THEN** the installed content is identifiable as that catalog file's content

#### Scenario: No update action is introduced
- **WHEN** the system records an installed entry's digests at install
- **THEN** recording introduces no user-visible action by itself; the record only
  enables a later comparison

#### Scenario: Recorded digests drive update detection
- **WHEN** a catalog probe compares an installed entry's recorded digest for a
  required file against the catalog's digest for that file
- **THEN** the comparison is what decides whether the entry has an available
  update

## ADDED Requirements

### Requirement: Updating an installed catalog entry
On a catalog probe, the system SHALL compare each entry installed from the catalog
against the catalog, and SHALL mark an entry as having an update available when
any of its required dictionary files' recorded SHA-256 differs from the catalog's.
Update detection SHALL apply only to entries installed from the catalog: a
dictionary with no recorded digest (one not installed from the catalog) SHALL NOT
be offered an update. Applying an update SHALL be user-confirmed — no update
transfer starts until the user starts it. An applied update SHALL download the
entry's required files, replace the installed copies in place so the dictionary
keeps its identity, list position and group membership, reload it without
requiring an app restart, and rebuild its full-text index, because the article
content changed. An update that fails SHALL leave the previously installed
dictionary intact and usable, and SHALL NOT leave a partially written dictionary.

#### Scenario: An update is detected
- **WHEN** an installed catalog entry's recorded digest for a required file
  differs from the catalog's digest for that file
- **THEN** the entry is marked as having an available update

#### Scenario: Current content has no update
- **WHEN** every recorded digest of an installed catalog entry matches the
  catalog's
- **THEN** no update is offered for it

#### Scenario: A folder-imported dictionary is not offered an update
- **WHEN** a dictionary was not installed from the catalog and has no recorded
  digest
- **THEN** no update is offered for it

#### Scenario: Applying an update replaces the content in place
- **WHEN** the user starts an available update and it completes
- **THEN** the dictionary serves the catalog's new content, keeps its name, list
  position and group membership, and needs no app restart

#### Scenario: An update rebuilds the full-text index
- **WHEN** an update replaces an installed dictionary's content
- **THEN** the dictionary's full-text index is rebuilt so search reflects the new
  article text

#### Scenario: An update is user-confirmed
- **WHEN** an entry has an available update and the user has not started it
- **THEN** no bytes are transferred for that update

#### Scenario: A failed update leaves the installed dictionary usable
- **WHEN** an update fails partway
- **THEN** the previously installed dictionary remains loaded and searchable, and
  no partially written dictionary is exposed
