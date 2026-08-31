## MODIFIED Requirements

### Requirement: Article rendering
The system SHALL render a lookup as HTML built from the dictionaries of the active group that contain the headword, presented in the on-screen web view with the dictionaries ordered per the active group.
Successful article lookups SHALL be recorded in the lookup history.
Unknown words MUST NOT crash the app.

#### Scenario: Word found in multiple dictionaries
- **WHEN** the user looks up a headword present in several dictionaries of the active group
- **THEN** the article displays each dictionary's entry in the active group's order

#### Scenario: Word not found
- **WHEN** the user looks up a headword none of the active group's dictionaries contain
- **THEN** the app shows a "not found" indication and offers a way to continue searching

#### Scenario: Lookup from an external entry point
- **WHEN** the user initiates a lookup via a share action, the clipboard, history, or favorites
- **THEN** the article is rendered against the active group, and the word is added to the lookup history

#### Scenario: Lookup respects the active group
- **WHEN** a word is only present in dictionaries outside the active group
- **THEN** the lookup does not show that dictionary's entry (it is treated as not found for that group)