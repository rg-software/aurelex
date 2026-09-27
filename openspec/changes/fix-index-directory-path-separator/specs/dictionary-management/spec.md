## MODIFIED Requirements

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
