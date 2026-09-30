## ADDED Requirements

### Requirement: Clipboard control reflects clipboard state
The Search pane's clipboard control SHALL be enabled only while the clipboard holds usable (non-whitespace) text, and SHALL be disabled while the clipboard is empty or holds only whitespace. Its enabled state SHALL track the clipboard while the app is running in the foreground, and SHALL be correct when the pane is first shown. When disabled, the control SHALL NOT paste or run a lookup. While it is enabled the control SHALL use the app's primary-action styling, so it does not read as a disabled control.

#### Scenario: Empty clipboard disables the control
- **WHEN** the clipboard is empty and the Search pane is shown
- **THEN** the clipboard control is disabled and tapping it does nothing

#### Scenario: Whitespace-only clipboard is treated as empty
- **WHEN** the clipboard contains only whitespace
- **THEN** the clipboard control is disabled

#### Scenario: Clipboard text enables the control
- **WHEN** the clipboard holds text
- **THEN** the clipboard control is enabled and tapping it pastes that text into the search field and looks it up

#### Scenario: A clipboard change updates the control live
- **WHEN** the clipboard becomes empty (or gains text) while the Search pane is on screen
- **THEN** the clipboard control's enabled state follows without leaving the pane

#### Scenario: Correct state on first show
- **WHEN** the user first switches to the Search pane
- **THEN** the clipboard control's enabled state already reflects the clipboard rather than a stale default
