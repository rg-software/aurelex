# tasks

## 1. Start tab on Search

- [x] 1.1 Route "Get started" (onboarding button) to the Search tab (`root.state = 0`) after setting `engine.onboarded`
- [x] 1.2 Start-tab on launch routes from the async `onboardedChanged` (guarded by `_bootRouted`) — `engine.onboarded` is only authoritative after EngineController's async `gd_init` + `loadSettings()`, so `Component.onCompleted` must not decide the first-run/returning-user tab

## 2. Groups list declutter

- [x] 2.1 Remove the row subtitle (`All dictionaries` / `id=N` label)
- [x] 2.2 Remove the "Dicts" button and the group-name drill-in; the row is static
- [x] 2.3 Remove the "..." overflow menu and its `Menu`/`MenuItem`s
- [x] 2.4 Pencil button opens the membership editor (`Accessible.name "Edit group dictionaries"`), trash requests delete confirmation — both right-justified, `visible` only for non-"All"
- [x] 2.5 Add the `edit` Material glyph (`0xe150`) to the root `icon()` map
- [x] 2.6 Add the `Delete group` confirmation dialog (OK/cancel; `_requestDeleteGroup`/`_confirmDeleteGroup`/`_cancelDeleteGroup`)

## 3. Working rename inside the membership editor

- [x] 3.1 Add `renameGroupId`/`renameGroupName` state + `_openRename(id, name)` to the groups pane
- [x] 3.2 Add the `Rename group` modal dialog: prefilled field with cursor at end (no full selection), standard OK/Cancel, empty-name guard, calls `engine.renameGroup`
- [x] 3.3 Add a `Rename group` button to the membership editor header, wired to `_openRename(editingGroup, editingGroupName)`

## 4. Docs, a11y, i18n

- [x] 4.1 Update `AGENTS.md` accessible-element table (Groups rows: static row, edit-dictionaries pencil, delete confirmation, rename dialog; Membership: rename-group button)
- [x] 4.2 Refresh Qt catalogs: run `scripts/update-translations.ps1`; add RU/JA for `Rename group` + the delete strings; recompile `.qm`
- [x] 4.3 Static-check `app/main.qml` with `qmllint` (no new error classes)

## 5. Membership editor: icons + reorder fix

- [x] 5.1 Convert Back/Rename/Remove/Add to icon-only `ToolButton`s
- [x] 5.2 Sort `groupMembers` by `memberIndex` in `onGroupDictsReady` (members displayed in group order — reorder changes were previously invisible)
- [x] 5.3 Add `EngineController::groupMembersChanged` signal emitted after add/remove/move commit; QML re-queries on it instead of refreshing immediately (fixes the async race)
- [x] 5.4 Convert the "Create group" button to an icon-only control

## 6. Drag-to-reorder + cleanup

- [x] 6.1 Add whole-row drag reorder to member rows (`MouseArea` over the full row): `onPressed` arms, `onPositionChanged` moves by row index, `onReleased` ends; `preventStealing: true` so the list's flick-scroll doesn't steal the gesture
- [x] 6.2 Remove the Move up / Move down arrow buttons and their icon-map entries once the drag gesture was verified on-device (Phrasebook↔Basic drag works)
- [x] 6.3 Remove the drag handle from the "available dictionaries" (non-member) rows — no dragging needed there
- [x] 6.4 Fix stale group-name header after rename: `onAccepted` writes the new name into `editingGroupName` when the renamed group is the one being edited

## 7. Group-row drill-in + header cleanup

- [x] 7.1 Make the group name row tappable again (`onClicked` → `_openMembership`, non-"All" only); remove the per-row pencil button (rename stays in the editor)
- [x] 7.2 Remove the `"Group:"` prefix from the membership editor header (just the name)
- [x] 7.3 Drop the now-obsolete `Group: %1` string from the Qt catalogs
- [x] 7.4 Decided: smooth drag-follow-finger is DEFERRED (ListView recycles delegates + no per-row ghost/translate API → overlay-ghost or non-recycled layout = high effort, Android jank risk, borderline benefit). Live reorder at row boundaries is the accepted behavior; the dragged row is HIGHLIGHTED via `_dragIndex` → member delegate `highlighted`, and cleared by a 400 ms no-motion watchdog (the MouseArea `released` can be lost when the ListView recycles its delegate mid-drag). See design.md Risks.

## 8. Verify on device

- [x] 8.1 Build the Debug APK (`app/build.ps1 -Configuration Debug`)
- [x] 8.2 Installed + verified on the attached device: Search start tab, group-row tap opens membership, header shows just the name (no "Group:"), rename inside editor updates the header, delete asks for confirmation, whole-row drag reorder works in both directions (drag active row is highlighted), Remove button still works (drag surface leaves the right sliver clear), add/remove/icons all present, no per-row pencil in the list