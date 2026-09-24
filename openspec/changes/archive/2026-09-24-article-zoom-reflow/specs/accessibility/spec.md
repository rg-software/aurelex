# Spec Delta

## MODIFIED Requirements

### Requirement: Every interactive QML element SHALL have an Accessible.name

Every element that a user can interact with (buttons, text fields, list items, combo boxes, tabs, checkboxes, dialogs, menus, the WebView) SHALL set an `Accessible.name` property that describes its purpose. Names SHALL be concise (1–4 words) and use sentence case.

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

#### Scenario: Article zoom controls have descriptive accessible names
- **WHEN** TalkBack focuses the article zoom controls
- **THEN** it announces their purpose, e.g. "Zoom in" and "Zoom out", without any raw English zoom-count state in the names

### Requirement: Every interactive QML element SHALL have an Accessible.role

Every interactive element SHALL set an `Accessible.role` matching its semantic function. Roles SHALL use the Qt `Accessible.role` enum values (`Accessible.Button`, `Accessible.EditableText`, `Accessible.List`, `Accessible.ListItem`, `Accessible.TabBar`, `Accessible.TabButton`, `Accessible.ComboBox`, `Accessible.CheckBox`, `Accessible.Dialog`, `Accessible.Menu`, `Accessible.MenuItem`, `Accessible.WebView`, `Accessible.Group`, `Accessible.ToolBar`, `Accessible.ProgressBar`).

#### Scenario: Button role is announced
- **WHEN** TalkBack focuses the "Create" button in the Groups pane
- **THEN** it announces the role as a button

#### Scenario: List role is announced
- **WHEN** TalkBack enters the suggestions ListView in the Search pane
- **THEN** it announces "Search suggestions, list" (name + role)

### Requirement: List container elements SHALL have Accessible.name identifying their content

Every `ListView` SHALL have an `Accessible.name` that describes what list it is (e.g., "Search suggestions", "Dictionaries list", "Groups list", "Lookup history", "Favorites", "Full-text search results", "Group members", "Available dictionaries to add"). Surfaces rendered inside the article WebView (search suggestions and the empty-state lookup history) expose their entries through the WebView's DOM accessibility subtree rather than as Qt list nodes.

#### Scenario: ListView announces its purpose
- **WHEN** TalkBack navigates into a Qt ListView
- **THEN** it announces the list name plus its list role

#### Scenario: WebView-surfaced entries are discoverable
- **WHEN** TalkBack navigates the Search candidate area while it shows suggestions or lookup history inside the article WebView
- **THEN** it announces each entry from the WebView's DOM accessibility subtree (its content-desc)

#### Scenario: Every article uses the unified inline surface
- **WHEN** TalkBack navigates an article opened from any entry point (search, history, favorites, full-text search, share, clipboard)
- **THEN** it is reached through the Search tab's inline article WebView with its Back, Forward, favorites, and zoom controls, and there is no separate full-pane article pane