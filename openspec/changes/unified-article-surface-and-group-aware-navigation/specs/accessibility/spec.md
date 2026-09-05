## MODIFIED Requirements

### Requirement: Every interactive QML element SHALL have an Accessible.name

Every element that a user can interact with (buttons, text fields, list items, combo boxes, tabs, checkboxes, dialogs, menus, the WebView) SHALL set an `Accessible.name` property that describes its purpose. Names SHALL be concise (1-4 words) and use sentence case.

#### Scenario: TextField has descriptive accessible name
- **WHEN** TalkBack focuses the search input field
- **THEN** it announces "Search dictionaries" (not "text field")

#### Scenario: TabButton has descriptive accessible name
- **WHEN** TalkBack focuses the Search tab
- **THEN** it announces "Search" (not "tab" or "icon plus label")

#### Scenario: Dynamic accessible name reflects state
- **WHEN** the current word is NOT in favorites and TalkBack focuses the star button
- **THEN** it announces "Add to favorites"
- **WHEN** the current word IS in favorites and TalkBack focuses the star button
- **THEN** it announces "Remove from favorites"

#### Scenario: Forward button has a descriptive accessible name
- **WHEN** TalkBack focuses the article forward button
- **THEN** it announces "Forward"

#### Scenario: Every article uses the unified inline surface
- **WHEN** TalkBack navigates an article opened from any entry point (search, history, favorites, full-text search, share, clipboard)
- **THEN** it is reached through the Search tab's inline article WebView with its Back, Forward, and favorites controls, and there is no separate article pane to enter