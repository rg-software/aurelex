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

### Requirement: List container elements SHALL have Accessible.name identifying their content

Every `ListView` SHALL have an `Accessible.name` that describes what list it is (e.g., "Search suggestions", "Dictionaries list", "Groups list", "Lookup history", "Favorites", "Full-text search results", "Group members", "Available dictionaries to add"). Surfaces rendered inside the article WebView (search suggestions and the empty-state lookup history) expose their entries through the WebView's DOM accessibility subtree rather than as Qt list nodes.

#### Scenario: ListView announces its purpose
- **WHEN** TalkBack navigates into a Qt ListView
- **THEN** it announces the list name plus its list role

#### Scenario: WebView-surfaced entries are discoverable
- **WHEN** TalkBack navigates the Search candidate area while it shows suggestions or lookup history inside the article WebView
- **THEN** it announces each entry from the WebView's DOM accessibility subtree (its content-desc)