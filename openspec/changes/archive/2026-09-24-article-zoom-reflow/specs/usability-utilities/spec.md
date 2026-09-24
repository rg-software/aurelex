# Spec Delta

## MODIFIED Requirements

### Requirement: Settings persistence
The system SHALL persist user preferences (favorites, history, text-to-speech enabled, the article dark-mode toggle, and the article zoom level) across app restarts.

#### Scenario: Preferences survive restart
- **WHEN** the user changes a preference (e.g. dark mode, TTS on/off, article zoom) or modifies favorites/history and then restarts the app
- **THEN** the preferences and lists retain the user's changes

#### Scenario: Zoom level survives restart
- **WHEN** the user sets an article zoom level and restarts the app
- **THEN** articles render at the stored zoom level without the user re-setting it