## Purpose

Provides semantic accessibility information for all interactive and informational QML elements, enabling screen reader users to navigate and operate the app, and enabling UIAutomator/Appium-based element discovery for automated on-device testing.

## ADDED Requirements

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

### Requirement: Every interactive QML element SHALL have an Accessible.role

Every interactive element SHALL set an `Accessible.role` matching its semantic function. Roles SHALL use the Qt `Accessible.role` enum values (`Accessible.Button`, `Accessible.EditableText`, `Accessible.List`, `Accessible.ListItem`, `Accessible.TabBar`, `Accessible.TabButton`, `Accessible.ComboBox`, `Accessible.CheckBox`, `Accessible.Dialog`, `Accessible.Menu`, `Accessible.MenuItem`, `Accessible.WebView`, `Accessible.Group`, `Accessible.ToolBar`, `Accessible.ProgressBar`).

#### Scenario: Button role is announced
- **WHEN** TalkBack focuses the "Create" button in the Groups pane
- **THEN** it announces the role as a button

#### Scenario: List role is announced
- **WHEN** TalkBack enters the suggestions ListView in the Search pane
- **THEN** it announces "Search suggestions, list" (name + role)

### Requirement: List container elements SHALL have Accessible.name identifying their content

Every `ListView` SHALL have an `Accessible.name` that describes what list it is (e.g., "Search suggestions", "Dictionaries list", "Groups list", "Lookup history", "Favorites", "Full-text search results", "Group members", "Available dictionaries to add").

#### Scenario: ListView announces its purpose
- **WHEN** TalkBack navigates into the history ListView
- **THEN** it announces "Lookup history, list"

### Requirement: Dialogs SHALL have Accessible.name describing their purpose

Every `Dialog` element SHALL set an `Accessible.name` that describes what the dialog is for (e.g., "Remove dictionary confirmation", "Welcome").

#### Scenario: Confirmation dialog is identifiable
- **WHEN** the remove-dictionary confirmation dialog opens
- **THEN** TalkBack announces "Remove dictionary confirmation, dialog"

### Requirement: Informational elements SHALL have appropriate Accessible.role

Elements that convey information but are not interactive (progress bars, section headers, error messages) SHALL have an `Accessible.role` that reflects their function (`Accessible.ProgressBar`, `Accessible.StaticText`, or `Accessible.Group`).

#### Scenario: Progress bar is announced during staging
- **WHEN** the dictionary staging process is running
- **THEN** TalkBack announces the progress bars as progress indicators

### Requirement: The ApplicationWindow root SHALL NOT require Accessible annotations

The `ApplicationWindow` root element does not need explicit `Accessible.*` properties; Qt assigns it a default role. This is a deliberate exclusion.

#### Scenario: Root window is navigable
- **WHEN** TalkBack starts
- **THEN** it can navigate into the app's child elements without requiring annotations on the ApplicationWindow itself
