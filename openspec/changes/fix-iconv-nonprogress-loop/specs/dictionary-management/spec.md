## MODIFIED Requirements

### Requirement: Index build and validation on device
The system SHALL build a lookup index for each loaded dictionary on the device when that dictionary's index does not yet exist or is out of date, and SHALL show the user the progress of the build.
An index build SHALL terminate: it either completes, or fails with the failure reported to the user, and MUST NOT run without bound. A build that cannot make progress — including one whose character-set conversion of a dictionary's text cannot advance — SHALL be treated as a failure of that dictionary rather than left running, so the app cannot appear to index forever without result.
A dictionary that fails to build an index SHALL NOT prevent the other dictionaries in the same scan from being indexed and becoming available.
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

#### Scenario: An index build terminates
- **WHEN** a dictionary's index is built on the device
- **THEN** the build finishes — either the dictionary becomes available, or the failure is reported — and it does not continue running without result

#### Scenario: A dictionary that cannot be indexed does not block the others
- **WHEN** one dictionary in an import fails to build its index
- **THEN** every other dictionary in the same import is still indexed and searchable, and the failure is reported for the one that could not be built

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
- **THEN** the check confirms the index was written inside the expected index directory, so a regression in index placement fails the build rather than reaching the device
