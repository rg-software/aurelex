## MODIFIED Requirements

### Requirement: Catalog availability
The system SHALL provide a single curated catalog of installable dictionaries
published as one static document at a location compiled into the app, and SHALL
reach it over HTTPS only. The system SHALL NOT require the user to configure,
supply, or authenticate to a catalog location, and SHALL NOT perform discovery
or scraping of any other source. The system SHALL keep the remote-add action
available regardless of reachability, and SHALL report a catalog that cannot be
reached with a stated reason inside the catalog view rather than disabling the
action. Folder import SHALL continue to be offered and unaffected. A build
distributed to users SHALL have a working TLS transport for the catalog fetch: a
build whose TLS cannot initialize is a build defect, and the system SHALL NOT
ship such a build as a catalog that is merely unreachable.

#### Scenario: Catalog is reachable
- **WHEN** the user opens the Dictionaries pane and the catalog can be fetched
- **THEN** the remote-add action is enabled and the catalog's entries can be listed

#### Scenario: Catalog cannot be reached
- **WHEN** the user opens the remote catalog and it cannot be fetched
- **THEN** the catalog states why it could not be loaded and offers nothing to
  download, while the folder-import action remains available and unaffected

#### Scenario: Catalog was previously read and is now unreachable
- **WHEN** the catalog cannot be fetched but a previously fetched catalog is known
- **THEN** the last known catalog entries remain visible and readable, while
  starting a download reports that the catalog is unreachable

#### Scenario: Catalog is not re-read at app start
- **WHEN** the app starts
- **THEN** the catalog is not fetched as part of startup, and a remote-add
  request fetches it on demand

#### Scenario: A distributed build completes the catalog fetch
- **WHEN** a user runs a build obtained from a release channel rather than one
  produced on a maintainer's machine, and opens the remote catalog
- **THEN** the catalog is fetched over TLS and its entries are listed, with no
  transport-level failure attributable to the build
