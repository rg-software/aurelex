## MODIFIED Requirements

### Requirement: Article rendering
The system SHALL render a lookup as HTML built from all loaded dictionaries that contain the headword, presented in the on-screen web view with the dictionaries ordered per the configured group, whether the lookup is initiated by typing in the search field, selecting a suggestion, or an external entry point (share action, clipboard, history, or favorites).
Successful article lookups SHALL be recorded in the lookup history.
Unknown words MUST NOT crash the app.

#### Scenario: Word found in multiple dictionaries
- **WHEN** the user looks up a headword present in several dictionaries
- **THEN** the article displays each dictionary's entry in the configured group order

#### Scenario: Word not found
- **WHEN** the user looks up a headword none of the dictionaries contain
- **THEN** the app shows a "not found" indication and offers a way to continue searching

#### Scenario: Lookup from an external entry point
- **WHEN** the user initiates a lookup via a share action, the clipboard, history, or favorites
- **THEN** the article is rendered the same way as a typed lookup, and the word is added to the lookup history