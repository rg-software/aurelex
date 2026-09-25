# proposal

## Why

The groups screen is cluttered and its rename action is a stub: the row shows a
useless subtitle (`All dictionaries` / `id=N`), a separate "Dicts" button for
something the row could do itself, and an overflow (`...`) menu whose "Rename"
item just appends `_r` to the name instead of letting the user type one. Also,
after onboarding finishes the user is left on the Dictionaries tab, but the app
should land somewhere useful: Search.

## What Changes

- The starting tab is always **Search** once there is no onboarding screen:
  finishing onboarding ("Get started") routes to Search, and every later launch
  starts on Search.
- Groups list rows are decluttered:
  - The `All dictionaries` / `id=N` subtitle is removed.
  - Tapping the group name opens the membership editor (drill-in restored); the
    per-row pencil is removed — the only per-row control is the delete trash.
  - Delete asks for confirmation (OK/cancel) before removing the group.
  - "Create group" is an icon-only (add/plus) control.
- The membership editor is icon-driven (Back, Rename, Add/Remove are icons), its
  header shows just the group name (no "Group:" prefix), and members reorder by
  **dragging anywhere on the row** (up/down arrows removed). Only the "in this
  group" list is draggable — the "available dictionaries" list isn't. Reorder
  relies on members rendering in group order and the UI re-querying after the
  engine commits each move.
- Rename is implemented for real and lives inside the group's membership editor:
  a `Rename group` button there opens a dialog prefilled with the current name
  (cursor placed at the end — no full selection); OK calls the existing
  `gd_group_rename` path (empty names are rejected) and the editor header updates
  in place. It works for any non-"All" group.
- Group creation moves into an "Add group" dialog: the inline new-group input is
  removed, OK creates the group and jumps straight into its membership editor,
  and duplicate names (case-insensitive) are rejected both in the UI and at the
  engine boundary (`gd_group_create`/`gd_group_rename` return -2 for a taken
  name; the controller emits `groupCreated(id, name)` / `groupNameTaken(name)`).
- Dictionary deletion is a single path: the multi-select "Delete" button is the
  only delete control (per-row and per-pair remove buttons removed). In the
  By-Pair view, tapping a pair header selects/unselects that whole section (with
  a check indicator) as a shortcut for building a deletion selection.

## Capabilities

### New Capabilities

<!-- none -->
- *none*

### Modified Capabilities

- `distribution-and-polish`: first-run onboarding — after "Get started" the app
  lands on Search, and subsequent launches (no onboarding) start on Search.
  Requirement text/scenario updates only; no engine behavior change.
- `dictionary-management`: dictionary groups — the groups list presents each group
  as a clickable row (drill-in to membership) with per-row rename/delete icon
  controls and no id/subtitle line, and groups can be renamed through a dialog.

## Impact

- `app/main.qml` (Qt UI): onboarding button handler, groups list delegate, new
  dialogs, icon map additions, membership editor rows/buttons, member-order fix.
- `app/EngineController.{hpp,cpp}`: new `groupMembersChanged` signal emitted after
  group membership commits (add/remove/move) so QML can re-query without the
  async race. No engine/boundary change (`gd_group_rename` etc. untouched).
- Accessible element IDs documented in `AGENTS.md` are updated (renamed controls,
  removed menu).
- Localization: dialogs/rename strings added; obsolete strings drop out. `.qm`
  catalogs recompiled.