## ADDED Requirements

### Requirement: Folder additions are serialized, never dropped
The system SHALL accept dictionary folder additions requested while a previous
folder's files are still being staged into app storage, queueing the pending
folder and processing it immediately after the current copy completes, instead
of discarding it.

#### Scenario: Second pick during an active stage copy
- **WHEN** the user picks a second dictionary folder while the first one is
  still being copied into app storage
- **THEN** the second folder is not lost: after the first copy finishes, the
  second is staged and its dictionaries are scanned and indexed

#### Scenario: A single pick that fails is surfaced
- **WHEN** staging a queued folder fails (e.g. the grant was revoked before the
  copy ran)
- **THEN** the app reports the failure and leaves the other dictionaries
  unaffected, without silently discarding the failed folder