## 1. Member list becomes a ListModel

- [x] 1.1 Add `import QtQml.Models` to `app/main.qml` if `ListModel` is not already in scope under `import QtQuick` (drop the import if the QML runtime accepts `ListModel` without it).
- [x] 1.2 Declare a `ListModel { id: memberModel }` for the membership editor and replace the `property var groupMembers: []` usage: point `memberList.model` at it and replace `groupsPane.groupMembers.length` in the header with `memberModel.count`.
- [x] 1.3 In `onGroupDictsReady`, populate `memberModel` from the sorted member list using roles `dictName` and `dictIndex` (the engine dict index); clear it first so a reopened group never shows stale rows.
- [x] 1.4 Update the member delegate to read `dictName` / `dictIndex` (drop `rowData`), keep `groupRemoveDict(editingGroup, dictIndex)` working, and bind `highlighted` to `index === groupsPane._dragIndex` (the delegate `index`, which follows the item as it moves).

## 2. Drag gesture: local move, commit on release

- [x] 2.1 Rewrite `_dragBegin(index, listY)` to store the origin row index and the finger's Y mapped into the member list (`dragArea.mapToItem(memberList, mouse.x, mouse.y).y`) as the stable anchor — `QQuickMouseEvent` in Qt 6.6 has no `scenePosition`.
- [x] 2.2 Rewrite `_dragMove(listY)` to compute `target = clamp(originIndex + round((listY - _dragStartY) / 46))` (46 = 44 px row + 2 px spacing) and, when it differs from the tracked current index, call `memberModel.move(current, target, 1)` and update `_dragIndex`; no engine call during the drag.
- [x] 2.3 Rewrite `_dragEnd()` (used by release/cancel) to commit once via `engine.groupMoveDict(editingGroup, originIndex, currentIndex)` only when the position changed, then clear the drag state.
- [x] 2.4 Update the member `MouseArea` handlers to pass the mapped list Y and to end the gesture on both `onReleased` and `onCanceled`.
- [x] 2.5 Delete the `dragWatchdog` `Timer` and its references (the delegate no longer recycles mid-drag, so the idle-timeout workaround would abort a legitimate slow drag).
- [x] 2.6 Apply the same commit-on-release path for the "All" group (`editingGroup === 0`); confirm no add/remove controls are introduced.
- [x] 2.7 Make the drag `MouseArea` a sibling of the row `RowLayout` inside an `Item` `contentItem` (anchored over it) instead of a layout child — the anchors-in-layout conflict collapsed/elided the row labels after some rebuilds.

## 3. Build and validate

- [x] 3.1 Compile the QML (`cmake --build build-qtquick --target aurelex`; full `app/build.ps1` when packaging) and fix any QML errors (unknown type, role/property warnings).
- [x] 3.2 On-device: open a non-"All" group and drag a member across several rows up and down in one gesture; the list must follow across every boundary and the dragged row stays highlighted. (Verified: "All" rows moved 4–5 slots down and 4 slots up; custom group moved 2 slots; `groupMoveDict rc=0`, no QML errors.)
- [x] 3.3 On-device: confirm the new order persists after leaving and reopening the editor (engine commit) and that the combined article for that group reflects it; repeat for the "All" group (article order). (Verified: order persisted after back/reopen and after force-stop/relaunch.)
- [x] 3.4 On-device regression: the "available dictionaries" list is not draggable, and the per-row Remove control still receives its taps (the drag surface still leaves the right sliver clear). (Verified: Remove on a custom-group member fired `groupRemoveDict rc=0` and restored the row to the non-member list; non-member rows have no drag surface.)
- [x] 3.5 Run `openspec validate group-drag-reorder`; confirm the change is coherent (no delta spec is expected — `dictionary-management` already specifies the behavior).
