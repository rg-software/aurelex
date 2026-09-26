## Why

Dragging a dictionary in a group's membership editor only ever moves it one
position: the row can be swapped with its immediate neighbour, but it cannot be
dragged two or more slots up or down. The engine call supports arbitrary
distances (`gd_group_move_dict` is a single erase+insert), so this is purely a
gesture bug in the QML membership editor — and it makes the existing
`dictionary-management` contract ("the member list re-orders live as the row
crosses row boundaries") untrue for any drag longer than one row.

Root cause: the drag `MouseArea` lives inside the `ListView` delegate. Every
`engine.groupMoveDict` call asynchronously re-queries the group and assigns a
brand-new array to `groupsPane.groupMembers`, which resets the `ListView` and
destroys the pressed delegate. Qt Quick cancels the mouse grab with the
destroyed item, so no further `onPositionChanged` events reach the gesture —
exactly one boundary crossing per drag. The delta is also measured in the
dragged row's own (moving) coordinate frame, so it stalls at the first boundary.

## What Changes

- **Member list becomes a `ListModel`.** The editor's "in this group" list is
  driven by a `ListModel` instead of a reassigned JS array, so reordering uses
  `ListModel.move()` — delegates are relocated, not destroyed, and the pressed
  `MouseArea` keeps its grab for the whole gesture.
- **Reorder locally while dragging, commit once on release.** Crossing a row
  boundary moves the item in the local model only; when the gesture ends the
  final order is committed to the engine with a single
  `engine.groupMoveDict(groupId, originalIndex, finalIndex)`. No async engine
  round-trip happens mid-drag, so the model never resets under the finger.
- **Measure travel in the list's coordinate space.** The drop index is derived
  from the finger mapped into the member `ListView`'s frame with `mapToItem`
  (that frame is fixed while the row moves under the finger) and the real row
  pitch (44 px row + 2 px spacing = 46), so a single drag can span any number of
  rows. (`QQuickMouseEvent` in Qt 6.6 has no `scenePosition`.)
- **Drag surface is an overlay, not a layout child.** The `MouseArea` is a
  sibling of the row's `RowLayout` inside the delegate `contentItem` (anchored
  over it) rather than a child of the layout, so it cannot fight the layout for
  width — an anchors-in-layout conflict that made row labels collapse/elide
  nondeterministically.
- **Drop the 400 ms idle watchdog.** It existed only because a recycled delegate
  could lose `released`; with a non-recycling `ListModel` the gesture ends on
  `onReleased` / `onCanceled`, so a slow drag is no longer aborted (and committed)
  early.

No engine, boundary, or spec-contract change: the behavior is what
`dictionary-management` already documents. This is a UI-only fix.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- none: the existing dictionary-management scenario "Reorder dictionaries
     within a group" already requires live multi-boundary reorder; this change
     makes the implementation satisfy it. skip_specs is set in .openspec.yaml. -->

## Impact

- `app/main.qml` — membership editor: replace the `groupMembers` JS array with a
  `ListModel`, rewrite `_dragBegin`/`_dragMove`/`_dragEnd` for local moves and
  commit-on-release, update the member delegate to use model roles, remove the
  `dragWatchdog` timer. Add `import QtQml.Models` if `ListModel` is not already
  in scope under `import QtQuick`.
- `app/EngineController.*` — unchanged; existing `groupDicts` / `groupMoveDict`
  APIs are reused as-is.
- No user-visible English text changes, so no RU/JA catalog work.
