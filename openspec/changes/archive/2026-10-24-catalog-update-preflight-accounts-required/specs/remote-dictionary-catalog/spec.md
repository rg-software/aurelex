# Spec Delta

## Purpose

Pin the update preflight to count what the update transfer fetches.

## MODIFIED Requirements

### Requirement: Updating an installed catalog entry
On a catalog probe, the system SHALL compare each entry installed from the catalog
against the catalog, and SHALL mark an entry as having an available update when
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
A catalog install SHALL record the batch's file digests at terminal, so the
record survives to the next probe. The free-space preflight for an update SHALL
count the required files plus the optional bundle exactly when audio is
requested — never zero for a genuine update.

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

#### Scenario: A catalog install records its baseline
- **WHEN** a catalog batch completes and its entries land
- **THEN** the requested file digests are recorded for each landed entry, so a
  later probe can compare them against the catalog

#### Scenario: An update preflight counts the update
- **WHEN** the user starts an available update
- **THEN** the free-space preflight counts the entry's required files (plus
  the optional bundle only when audio is requested), so a genuine update is
  never classified as nothing to download
