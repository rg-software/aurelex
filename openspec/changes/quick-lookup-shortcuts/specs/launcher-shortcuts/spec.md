## Purpose

Lets a user trigger a word lookup from outside the app: a Quick Settings tile
that looks up the current clipboard text, and a home-screen widget with a
search field. Both reuse the existing lookup flow and do not require opening
the app first.

## ADDED Requirements

### Requirement: Quick Settings tile
The system SHALL provide a Quick Settings tile that, when tapped, looks up the
current clipboard text and opens the article for it. The look-up SHALL behave
exactly like a same-text lookup typed into the search field (including the
standard "word not found" handling when the text matches no dictionary).

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

### Requirement: Home-screen search widget
The system SHALL provide a home-screen widget with a search field. Entering a
word and confirming the entry SHALL open the article for that word in the same
way as a typed lookup, including the standard "word not found" handling.

#### Scenario: Widget search opens the article
- **WHEN** the user enters a word in the widget and confirms it
- **THEN** the app opens and shows the article for that word

#### Scenario: Widget opens search screen
- **WHEN** the user taps the widget's search field without a word being confirmed
- **THEN** the app opens to the search screen with focus on the field

#### Scenario: Widget search not found
- **WHEN** the user confirms a word in the widget that matches no dictionary entry
- **THEN** the app opens and shows the standard "word not found" indication

#### Scenario: Add and resize the widget
- **WHEN** the user adds the widget to the home screen
- **THEN** it appears at a standard size and remains usable after the device rescales it

### Requirement: No dictionary interference
Launcher shortcuts SHALL respect the currently active group: a lookup
launched by the tile or widget uses the same group settings as a typed lookup
and must not change the active group or dictionary order.

#### Scenario: Shortcuts respect the active group
- **WHEN** a lookup is launched via the tile or widget while a specific group is active
- **THEN** the article reflects that group's dictionaries and order, and the group selection is unchanged