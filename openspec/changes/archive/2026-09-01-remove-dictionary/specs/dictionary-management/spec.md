## ADDED Requirements

### Requirement: Remove a loaded dictionary
The system SHALL let the user remove a loaded dictionary from the app's set of
dictionaries, and SHALL remove it consistently from lookups, groups, and
full-text search so no stale results reference it.

#### Scenario: Remove an individual dictionary
- **WHEN** the user removes one loaded dictionary
- **THEN** that dictionary's entry disappears from the dictionary list and future
  lookups no longer include it

#### Scenario: Removal is reflected in groups
- **WHEN** a removed dictionary was a member of the active group or any group
- **THEN** the group's membership no longer lists it, without error

#### Scenario: Removal is reflected in full-text search
- **WHEN** a removed dictionary had a full-text index
- **THEN** full-text search results no longer include matches from it

#### Scenario: Re-add after removal
- **WHEN** the user loads the same folder again after removing a dictionary from it
- **THEN** the dictionary is added back as a fresh entry (re-scan is not blocked
  by the earlier removal)

#### Scenario: Confirmation before removal
- **WHEN** the user triggers a dictionary removal
- **THEN** the app asks for confirmation before the dictionary is removed