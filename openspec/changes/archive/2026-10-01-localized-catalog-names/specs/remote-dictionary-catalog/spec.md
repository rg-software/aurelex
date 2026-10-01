## MODIFIED Requirements

### Requirement: Browsing the catalog
The system SHALL present the catalog as a list of entries shown in place over the
Dictionaries pane, without adding a navigation destination. Each entry SHALL show
its display name, its source/target language pair, and the size of what will be
downloaded for it, and SHALL indicate whether the entry is already installed. An
entry's display name SHALL be shown in the app's active language when the entry
provides one for it, falling back to the entry's default name. The system SHALL NOT offer entry version comparison, update checks,
or any other catalog-side lifecycle action.

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
- **THEN** the entry is shown as installed and a fresh install is not offered
  for it (only its optional resources can still be added)

#### Scenario: Catalog is a read-only list
- **WHEN** the user views an installed catalog entry
- **THEN** the app offers no action to update, upgrade, or reinstall that entry

#### Scenario: Leaving the catalog
- **WHEN** the user dismisses the catalog
- **THEN** the Dictionaries pane is shown as it was before the catalog opened
