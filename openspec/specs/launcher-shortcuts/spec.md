## Purpose

Lets a user trigger a word lookup from outside the app: a Quick Settings tile that looks up the current clipboard text. It reuses the existing lookup flow and does not require opening the app first.

## Requirements

### Requirement: Quick Settings tile
The system SHALL provide a Quick Settings tile that, when tapped, looks up the current clipboard text and opens the article for it. The look-up SHALL behave exactly like a same-text lookup typed into the search field (including the standard "word not found" handling when the text matches no dictionary).

#### Scenario: Tile looks up clipboard text
- **WHEN** the user copies text, opens Quick Settings, and taps the Aurelex tile
- **THEN** the app opens and shows the article for that text

#### Scenario: Clipboard is empty
- **WHEN** the user taps the tile but the clipboard contains no text
- **THEN** the app opens to the search screen and does not error

#### Scenario: Tile lookup not found
- **WHEN** the user taps the tile and the clipboard text matches no dictionary entry
- **THEN** the app shows the standard "word not found" indication

#### Scenario: Tile usability
- **WHEN** the user opens the Quick Settings shade
- **THEN** the tile is present, visible, and discoverable with a label and icon

### Requirement: No dictionary interference
Launcher shortcuts SHALL respect the currently active group: a lookup launched by the tile uses the same group settings as a typed lookup and must not change the active group or dictionary order.

#### Scenario: Shortcuts respect the active group
- **WHEN** a lookup is launched via the tile while a specific group is active
- **THEN** the article reflects that group's dictionaries and order, and the group selection is unchanged