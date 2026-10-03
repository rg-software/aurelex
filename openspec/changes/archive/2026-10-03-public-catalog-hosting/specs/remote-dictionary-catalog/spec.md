## ADDED Requirements

### Requirement: Generated catalog publication
The published dictionary catalog SHALL be generated from a maintained source by
tooling and SHALL be served at one stable HTTPS location compiled into the app.
Every file in the published catalog SHALL carry its size in bytes and a SHA-256
digest, computed during generation rather than maintained by hand. Entry ids and
file names SHALL be stable and append-only: changing a dictionary's content
SHALL NOT change its entry id or any of its file names, and a file's digest SHALL
change when its content changes. The dictionary files the catalog references
SHALL be served from stable HTTPS URLs that are not tied to a branch, tag, or
release that may be deleted, so the URLs do not change when the app publishes a
new release.

#### Scenario: Generated catalog carries size and digest
- **WHEN** the catalog is generated from the maintained source
- **THEN** every file entry has an integer size in bytes and a 64-character
  lowercase hexadecimal SHA-256 digest

#### Scenario: Identity is stable across a content update
- **WHEN** a dictionary's content is updated and the catalog is regenerated
- **THEN** its entry id and its file names are unchanged, and only the affected
  file's digest (and its size, if the size changed) differs

#### Scenario: File URLs survive an app release
- **WHEN** the app publishes a new release
- **THEN** the dictionary-file URLs the catalog references still resolve and are
  unchanged

#### Scenario: Published files are reachable for install
- **WHEN** a user installs an entry from the published catalog
- **THEN** each of its files is fetched over HTTPS from the stable URL the catalog
  declares, with integrity verification applied

### Requirement: Installed catalog content is identifiable
The system SHALL record, for each entry installed from the catalog, the SHA-256
digest of the dictionary files it installed, so the installed content can be
identified against the catalog later without re-reading the files. Recording
this information SHALL NOT introduce any update, upgrade, reinstall, or
version-comparison action: an installed entry remains read-only in the catalog
exactly as before.

#### Scenario: Installing records the installed digests
- **WHEN** a dictionary is installed from the catalog
- **THEN** the system records the installed dictionary files' SHA-256 digests
  persistently

#### Scenario: Recorded digests identify installed content
- **WHEN** the recorded digest for an installed entry's dictionary file matches
  the catalog's digest for that file
- **THEN** the installed content is identifiable as that catalog file's content

#### Scenario: No update action is introduced
- **WHEN** the user views an installed catalog entry
- **THEN** no update, upgrade, reinstall, or version-comparison action is offered
