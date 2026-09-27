## MODIFIED Requirements

### Requirement: Dictionary groups
The system SHALL let the user organize loaded dictionaries into multiple named groups, each an ordered subset, and SHALL let the user select which group is active for lookups. An implicit "All" group containing every loaded dictionary is always available. Managing groups, their membership, their order, and the active group is part of this capability. Groups SHALL persist across app restarts (membership stored by stable dictionary identifier and re-resolved after dictionaries load).

Loading or re-scanning dictionaries SHALL NOT change the set of groups: the stored group set is the source of truth and a scan SHALL be idempotent for it, so importing a dictionary never adds, renames, or drops a group. Each group SHALL remain uniquely identifiable by its stored identifier across scans, and a stored group set that already contains the same identifier more than once SHALL be repaired to one group per identifier (keeping the union of their members) rather than being shown as duplicate rows.

The groups list SHALL present each group as a row tap: tapping a group row opens
its membership editor directly. A non-"All" group's editor supports add, remove,
and reorder; the "All" group opens the same editor in reorder-only mode (no
add/remove/rename, and "All" itself cannot be renamed or deleted). Each non-"All"
row SHALL expose only a delete control on the row (rename lives inside the
membership editor; there is no per-row edit/pencil control). The row SHALL NOT
show a technical subtitle (such as an internal id).

#### Scenario: All loaded dictionaries are the default group
- **WHEN** the user first loads dictionaries without creating any group
- **THEN** lookups use an implicit "All" group containing every loaded dictionary

#### Scenario: Create a group
- **WHEN** the user taps "Add group", types a name in the dialog, and confirms
- **THEN** the group is created and its membership editor opens immediately

#### Scenario: Duplicate group name is rejected
- **WHEN** the user creates a group whose name (case-insensitive) already exists
- **THEN** no group is created and an inline error is shown asking for another name

#### Scenario: Rename to an existing name is rejected
- **WHEN** the user renames a group to a name (case-insensitive) another group already has
- **THEN** the group keeps its old name and an inline error is shown

#### Scenario: Groups survive restart
- **WHEN** the user restarts the app after creating groups
- **THEN** the same named groups, membership, order, and active selection are restored

#### Scenario: Importing a dictionary does not duplicate groups
- **GIVEN** a dictionary that belongs to a group, and a newer build of that same dictionary
- **WHEN** the user imports the newer build and it is indexed
- **THEN** the groups list shows exactly the same groups as before, with no second row for the group the dictionary belongs to

#### Scenario: Repeated scans leave the group set unchanged
- **WHEN** dictionaries are scanned more than once in a session (for example the user imports several dictionaries in a row)
- **THEN** the number of groups, their names, their membership, and their order are identical after every scan

#### Scenario: Group identity is stable across scans
- **WHEN** dictionaries are scanned again after a group was created
- **THEN** that group still resolves to the same identifier, so selecting it, editing its membership, renaming it, and deleting it all act on the one group the user created

#### Scenario: A stored group set with a repeated identifier is repaired
- **GIVEN** a stored group set in which one group's identifier appears more than once
- **WHEN** the app next loads dictionaries
- **THEN** the groups list shows that group once, containing the members of every entry that shared the identifier, and the stored group set no longer contains the repeat

#### Scenario: Select the active group
- **WHEN** the user picks a group as active
- **THEN** subsequent lookups use only that group's dictionaries, in that group's order

#### Scenario: Reorder dictionaries within a group
- **WHEN** the user drags a group member up or down within the members list (grabbing the row's left-hand drag handle; the name area and the trailing Remove control are not drag surfaces, so a drag starting on them scrolls the list instead)
- **THEN** the combined article for that group respects the new order, the member list re-orders live as the row crosses row boundaries, and the row being dragged stays visually highlighted while the gesture is active

#### Scenario: Reorder affordance is only on group members
- **WHEN** the user views the membership editor
- **THEN** only rows in the "in this group" list are draggable for reordering; dictionaries in the "available to add" list cannot be reordered

#### Scenario: Membership editor exposes icon-based controls
- **WHEN** the user opens a group's membership editor
- **THEN** the back control, the rename control, the remove-from-group control and the add-to-group control are all icons (no text-only action links), and reordering happens by dragging the member rows

#### Scenario: Reorder reflects immediately after a move
- **WHEN** the user drags a member row to a new position
- **THEN** the member list re-orders to the new group order as soon as the engine commits, without needing an extra refresh

#### Scenario: Rename inside the editor keeps the title in sync
- **WHEN** the user renames a group from inside its membership editor
- **THEN** the editor's header (the group name alone, no "Group:" prefix) updates to the new name immediately, without requiring a screen refresh

#### Scenario: Open the membership editor from the group row
- **WHEN** the user taps a group's row in the groups list
- **THEN** the membership editor for that group opens (for non-"All" groups: add/remove dictionaries and reorder; for "All": reorder only)

#### Scenario: Rename a group from within the membership editor
- **WHEN** the user opens a group's membership editor, taps its rename action, and confirms a new non-empty name
- **THEN** the group is renamed and the groups list shows the new name

#### Scenario: Rename rejects an empty name
- **WHEN** the user confirms a rename with a blank name
- **THEN** the group keeps its existing name

#### Scenario: Rename field does not pre-select the whole name
- **WHEN** the rename dialog opens
- **THEN** the current name is prefilled and the cursor is placed in the field, without selecting the whole name

#### Scenario: Delete a group is confirmed before acting
- **WHEN** the user taps the delete control on a non-"All" group row
- **THEN** the app asks for confirmation (OK/cancel) before the group is removed

#### Scenario: Delete a group
- **WHEN** the user confirms deletion of a group
- **THEN** the group no longer appears in the list, and lookups fall back to the "All" group (or the next active group), without error

#### Scenario: Delete a group that is active
- **WHEN** the user deletes the currently active group
- **THEN** the app falls back to the "All" group so lookups keep working

#### Scenario: The All group is reorder-only
- **WHEN** the user opens the "All" group
- **THEN** its editor has no add, remove, rename, or delete controls, and dragging its rows changes the search article order

#### Scenario: Group row opens its membership editor
- **WHEN** the user taps a group's row in the groups list
- **THEN** the membership editor for that group opens (for non-"All" groups: add/remove dictionaries and reorder; for "All": reorder only)

#### Scenario: The "All" group opens in reorder-only mode
- **WHEN** the user taps the "All" group row
- **THEN** the editor opens showing every dictionary in article order, with no add/remove/rename controls; dragging a row changes the search article order

#### Scenario: Delete needs confirmation
- **WHEN** the user taps the trash control on a non-"All" group row
- **THEN** the app asks for confirmation before the group is removed
