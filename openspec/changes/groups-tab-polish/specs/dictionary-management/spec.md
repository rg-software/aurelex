## MODIFIED Requirements

### Requirement: Dictionary groups
The system SHALL let the user organize loaded dictionaries into multiple named groups, each an ordered subset, and SHALL let the user select which group is active for lookups. An implicit "All" group containing every loaded dictionary is always available. Managing groups, their membership, their order, and the active group is part of this capability. Groups SHALL persist across app restarts (membership stored by stable dictionary identifier and re-resolved after dictionaries load).

The groups list SHALL present each group as a row tap: tapping a non-"All"
group's name opens its membership editor directly; the "All" group is not
editable (no membership editor, no rename, no delete). Each non-"All" row SHALL
expose only a delete control on the row (rename lives inside the membership
editor; there is no per-row edit/pencil control). The row SHALL NOT show a
technical subtitle (such as an internal id).

#### Scenario: All loaded dictionaries are the default group
- **WHEN** the user first loads dictionaries without creating any group
- **THEN** lookups use an implicit "All" group containing every loaded dictionary

#### Scenario: Create a group
- **WHEN** the user creates a named group and adds some dictionaries to it
- **THEN** the group appears in the groups list with that membership

#### Scenario: Groups survive restart
- **WHEN** the user restarts the app after creating groups
- **THEN** the same named groups, membership, order, and active selection are restored

#### Scenario: Select the active group
- **WHEN** the user picks a group as active
- **THEN** subsequent lookups use only that group's dictionaries, in that group's order

#### Scenario: Reorder dictionaries within a group
- **WHEN** the user drags a group member up or down within the members list (grabbing anywhere on the member row)
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
- **WHEN** the user taps a non-"All" group's name in the groups list
- **THEN** the membership editor for that group opens (add/remove dictionaries and reorder)

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

#### Scenario: The All group is not editable
- **WHEN** the user views the "All" group row in the groups list
- **THEN** it has no edit or delete controls, and it cannot be deleted or renamed