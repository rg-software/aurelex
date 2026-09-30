## ADDED Requirements

### Requirement: Group surfaces use standard icon controls
The Groups list's add control and the membership editor's rename control SHALL be icon buttons in the app's standard icon-button style (an icon glyph with no visible text label), matching the icon controls in the dictionary toolbar. Each SHALL expose the documented invariant English accessible name regardless of the display language — "Add group" for the add control and "Rename group" for the rename control.

#### Scenario: Add control is an icon button
- **WHEN** the user views the Groups list
- **THEN** the add control is an icon button with no visible text label, its accessible name is "Add group", and tapping it opens the new-group name dialog

#### Scenario: Rename control is a standard icon button
- **WHEN** the user opens a non-built-in group's membership editor
- **THEN** its rename control is an icon button in the app's standard icon-button style, its accessible name is "Rename group", and tapping it opens the rename dialog

### Requirement: Membership editor groups available dictionaries by pair
The membership editor SHALL offer a By Pair toggle. When it is on, the available-to-add list SHALL present dictionaries grouped under source/target pair captions using the same pairing as the dictionary list, with pairs sorted alphabetically and dictionaries within a pair sorted alphabetically by name. The member list SHALL NOT be grouped by pair: it SHALL remain a single flat list in the group's order, and dragging SHALL continue to set that order. When the toggle is off, the available-to-add list SHALL be a flat list.

#### Scenario: Toggle on groups the available list by pair
- **WHEN** the user turns By Pair on in a membership editor
- **THEN** the available-to-add list shows pair caption rows and its dictionaries are grouped under the caption matching their source/target pair

#### Scenario: Toggle off shows a flat available list
- **WHEN** the user turns By Pair off in a membership editor
- **THEN** the available-to-add list shows no pair captions

#### Scenario: Member list stays flat and reorderable
- **WHEN** By Pair is on and the user drags a row in the member list
- **THEN** the member list is not grouped into pair sections and the drag still changes the group's article order

#### Scenario: Available dictionaries cannot be reordered
- **WHEN** the user views the available-to-add list with By Pair on
- **THEN** its rows are not draggable, the same as with By Pair off

### Requirement: Membership editor names clear of row controls
A dictionary name shown in the membership editor SHALL be truncated in the middle when it is too long for its row, so that it never overlaps the row's trailing add-to-group or remove-from-group icon and those icons stay fully visible and tappable.

#### Scenario: Long name elides clear of the icon
- **WHEN** a dictionary with a name wider than the row is shown in the membership editor
- **THEN** the name is elided in the middle and does not run under the trailing add-to-group or remove-from-group icon

### Requirement: Group name dialogs stay centered
The create-group and rename-group dialogs SHALL lay out their name field and action buttons centered within the dialog for every label length, including longer translations, so no control is clipped or shifted off-center.

#### Scenario: Labels of any length stay centered
- **WHEN** the rename-group dialog is shown in a language whose action labels are longer than English
- **THEN** the name field and the action buttons remain centered within the dialog and fully visible
