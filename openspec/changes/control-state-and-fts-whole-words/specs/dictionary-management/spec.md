## ADDED Requirements

### Requirement: An empty error banner is not shown
The engine-error banner SHALL be shown only when the engine reports a non-blank message; a whitespace-only message MUST NOT paint the banner.

#### Scenario: Blank message paints nothing
- **WHEN** the engine reports a message that is empty or only whitespace
- **THEN** no error banner is shown

#### Scenario: A real message is shown
- **WHEN** the engine reports a non-blank message
- **THEN** the error banner is shown with that message
