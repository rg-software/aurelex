## Context

See `proposal.md` — Why for the symptom and root cause. The relevant current
state in `app/main.qml`:

- `groupsPane.groupMembers` is a plain `var` holding a freshly built JS array.
  `onGroupDictsReady` sorts it by `memberIndex` and assigns the new array
  (`app/main.qml:1811`), which fully resets the member `ListView`.
- The drag gesture is a `MouseArea` inside the member delegate
  (`app/main.qml:2162`). `onPressed` records `mouse.y` in the row's frame;
  `onPositionChanged` computes `round(dy / 44)` and calls
  `engine.groupMoveDict` per boundary; `onReleased` ends the gesture.
- `engine.groupMoveDict` is async and, on success, emits `groupMembersChanged`
  (`app/EngineController.cpp:1035`), which triggers `_refreshMembership()` →
  `engine.groupDicts()` → `onGroupDictsReady` → model replacement. So each move
  resets the list and destroys the pressed delegate mid-gesture.
- A 400 ms `dragWatchdog` (`app/main.qml:1684`) compensates for the lost
  `released` by ending the drag after the finger stops moving.

The engine's `gd_group_move_dict` is an erase+insert over the ordered membership
list (`carve/gd_boundary.cc:996`), so one call can move an item any distance. The
display order equals the engine membership order (the `memberIndex` sort makes
row *i* the group's member *i*), which lets a local row move map onto a single
engine move.

## Goals / Non-Goals

**Goals:**
- A single drag can move a member to any position in the list, in either
  direction, and the list visibly follows the finger across row boundaries.
- The gesture survives every model change it causes (no lost grab, no premature
  end).
- Commit the resulting order to the engine exactly once, so persistence and the
  combined-article order match what the user sees.

**Non-Goals:**
- Smooth pixel-level "ghost" following the finger (explicitly deferred in the
  archived `groups-tab-polish` design). The dragged row still snaps row-by-row.
- Auto-scroll when dragging to the edge of a long list (lists are short in v1).
- Any engine / boundary / `gd_*` change.

## Decisions

**D1. Use a `ListModel` for the member list, not a JS array.**
`ListModel.move(from, to, 1)` relocates the delegate instances in place, so the
`MouseArea` that owns the gesture is never destroyed and keeps its implicit
grab. Reassigning a JS array (today's behavior) forces a full `ListView` reset
that cancels the grab — the root cause.
*Alternatives:* keep the array and reassign optimistically (still resets
delegates → same bug); a persistent overlay gesture item polled from a stable Y
(works, but larger and carries the Android jank risk the archived design already
rejected). `ListModel` is the smallest change that keeps the live-reorder
behavior the spec describes.

Roles: `dictName` (display) and `dictIndex` (the engine dictionary index used by
`groupRemoveDict`). `index` cannot be used as a role name because the delegate
exposes `index` itself; highlight uses the delegate `index` compared to the
drag state.

**D2. Reorder the model locally during the drag; commit once on release.**
`_dragMove` never calls the engine. On each boundary crossing it calls
`memberModel.move(currentIndex, targetIndex, 1)` and updates `_dragIndex`. On
release it calls `engine.groupMoveDict(editingGroup, originIndex, currentIndex)`
once. This removes the async model reset from the middle of the gesture and
matches the engine's erase+insert semantics: moving an item from its original
index to its final index produces exactly the order built by the local moves.
*Alternatives:* call the engine per boundary and suppress `onGroupDictsReady`
while dragging (fragile — the pending refresh still races the gesture); commit
after each move and re-read (defeats D1).

**D3. Derive the target index from the finger mapped into the member list's
coordinate space, and the real row pitch.**
The drag surface maps the finger with
`dragArea.mapToItem(memberList, mouse.x, mouse.y).y`, giving a position in the
list's frame that does not move when the row moves under the finger.
`_dragStartY` stores that at press; `_dragMove` computes
`target = clamp(originIndex + round((listY - _dragStartY) / 46))`. 46 is the true
pitch (44 px delegate height + 2 px `ListView.spacing`; the old code used 44).
The current index is tracked separately from the origin because the item's row
changes as it is moved.
*Alternatives:* `mouse.scenePosition.y` (chosen first — **wrong**: Qt 6.6's
`QQuickMouseEvent` exposes only `x`/`y`, no `scenePosition`, so the handler threw
at runtime and nothing moved); row-local `mouse.y` delta (what the code does
today; the origin moves with the row, so it stalls); mapping to the viewport is
equivalent here because the short lists do not scroll mid-drag.

**D4. Keep the drag surface out of the row's `RowLayout`.**
The `contentItem` is an `Item` holding the `RowLayout` (anchored to fill) and the
drag `MouseArea` (anchored over it, declared last) as *siblings*. Putting the
`MouseArea` inside the `RowLayout` while it also anchored to fill the layout was
an anchors-on-layout-child conflict that resolved nondeterministically: after
some rebuilds the row labels collapsed and middle-elided at the right edge. As a
sibling overlay it cannot influence layout width, and the Remove `ToolButton`
(declared after `contentItem`) still sits above the drag bag.
*Alternatives:* give the `MouseArea` `Layout.fillWidth` (it is not meant to take
layout space); keep it a layout child with `anchors.fill` — the bug.

**D5. End the gesture on `onReleased` / `onCanceled`; delete `dragWatchdog`.**
The watchdog was a workaround for a recycled delegate losing `released`. With
D1 the delegate persists, so `released` is reliable, and `onCanceled` covers the
pane-close / interrupted case. Keeping the 400 ms idle timer would now abort — and
commit — a legitimate slow drag where the finger pauses before continuing.
`preventStealing: true` stays so the `ListView` flick cannot hijack the gesture.

## Risks / Trade-offs

- [Model reset still happens on commit] → It happens on release, after the
  gesture ends, which is harmless; the rebuild in `onGroupDictsReady` remains the
  single write path for engine-originated changes (add/remove/commit).
- [`ListModel` module import] → Resolved: `import QtQml.Models` added and the
  QML compiles/links; verified on-device.
- [`ListModel.move` triggers view animation on Android] → Verified on-device:
  rows reflow without jank on a 28-item list.
- [A drag abandoned without `released`/`onCanceled` (app backgrounded) leaves the
  local order uncommitted] → The next `onGroupDictsReady` rebuild from the engine
  restores the committed order, so the UI self-heals; no data is written.
- [Highlight binding change] → Verified on-device: the dragged row stays marked
  and the highlight follows it across multiple crossings.

## Migration Plan

UI-only; ships with the next app build. No data migration. Rollback = revert the
`app/main.qml` change (and the `.openspec.yaml`/plan artifacts) in one commit.
