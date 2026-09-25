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

## 9. Group-creation dialog + duplicate names

- [x] 9.1 Remove the inline "new group" input; "Add group" button opens a name dialog (OK/Cancel)
- [x] 9.2 On OK: create the group and open its membership editor immediately (`groupCreated` signal carries the id)
- [x] 9.3 Unique group names: `gd_group_create`/`gd_group_rename` reject case-insensitive duplicates (rc -2); `groupNameTaken` signal shows an inline error and re-opens the dialog
- [x] 9.4 Force member-list redraw on group open (`forceLayout` after `onGroupDictsReady`; reset member arrays in `_openMembership`) — fixes dictionary names sometimes not shown

## 10. Dicts: single deletion path + pair-header select-all

- [x] 10.1 Remove per-row and per-pair delete controls; the multi-select "Remove" button is the only deletion path
- [x] 10.2 Pair (section) header tap selects/unselects all dictionaries in that pair; a check indicator reflects full selection
- [x] 10.3 Rename the import button "Add dictionaries" → "Add" (folder-open glyph + "Add" label); move "Remove" next to "Add" (gray when disabled, magenta when a selection exists); "By Pair" becomes a translate (文/A) glyph icon
- [x] 10.4 Tab idempotency: switching away from Search preserves an inline article and restoring it on return (no wipe + refocus); the no-article case still re-suggests

## 10.5 FTS layout mirrors Search

- [x] 10.5.1 Put the FTS input + group-scope button side by side in one row (like Search)
- [x] 10.5.2 Replace the "Whole words" checkbox with a match-word glyph icon button (pressed when on, like Search's clipboard)
- [x] 10.5.3 High-contrast pressed style: active = magenta background + white glyph (mirrors the Add button; reads in light & dark), inactive = gray glyph
- [x] 10.5.4 Replace the Search and FTS group selectors with arrowless, always-tappable buttons showing only the current group in the magenta accent scheme, and route taps through the shared modal picker

## 10.6 Material Symbols font (correct glyphs)

- [x] 10.6.1 Build a Material Symbols Outlined subset (instanced wght 400) with just `folder_open` (U+E2C8) + `match_word` (U+F6F0); ~2 KB, shipped as `MaterialSymbols-Outlined-subset.ttf`
- [x] 10.6.2 Register it in `fonts.qrc` + `main.cpp` as the "Material Symbols" family
- [x] 10.6.3 Add `symbolIcon()` / `symbolFontFamily`; use Material Symbols glyphs on the Dicts "Add" button (open folder) and the FTS whole-words toggle (ab-with-underscore)

## 10.7 Article Back/Forward never shows the dropdown

- [x] 10.7.1 `Back` disabled when there is no previous search result; remove the `_backFromArticle` fallback that cleared the article and popped the suggestion/history dropdown
- [x] 10.7.2 Back/Forward only step previous/next search results

## 11. Docs, a11y, i18n

- [x] 11.1 Update `AGENTS.md` accessible-element table (Dicts: Delete only, pair-header select-all; Groups: Add-group button/dialog; Article Back disabled at oldest; FTS whole-words styling)
- [x] 11.2 Refresh Qt catalogs (`Add group`, `A group named "%1" already exists`; drop `Remove`/`Remove pair`/remove-dialog strings); recompile `.qm`
- [x] 11.3 Static-check `app/main.qml` with `qmllint`

## 12. Verify on device

- [x] 12.1 Build the Debug APK
- [x] 12.2 Install and verify: Add-group dialog creates+opens membership, duplicate name rejected inline, group open always shows dict names, pair-header select-all toggles, only the Delete selection button deletes
- [x] 12.3 Verify: Add button shows open-folder glyph; whole-words toggle shows ab-with-underscore and magenta/white when pressed (light+dark); article Back/Forward step results without opening the dropdown

## 13. FTS polish + nav UX

- [x] 13.1 FTS tab idempotence: don't clear `ftsResults` in `_openFts` (results survive tab switches)
- [x] 13.2 Theme control is a plain `Button` that is a SIBLING of the TabBar (not a TabButton) in the 6th dock slot — never becomes the selected tab; nav tabs take 5/6, theme 1/6
- [x] 13.3 FTS group scope opens the same modal `Select group` picker as Search (`_pickerTarget` "fts" vs "search"); picker subtitle removed
- [x] 13.4 Whole-words toggle is a `Button` with `highlighted` (accent fill when ON) like the By Pair switch; explicit `contentItem` Label so the Material Symbols glyph renders
- [x] 13.5 Nav icon sizes reverted to a fixed 18 px (the `iconSize()` normalization over-corrected; revisit later)
- [x] 13.6 Verified: theme toggles dark mode without becoming the active tab; FTS toggle has correct fill + glyph; Search/FTS group pickers both open with no subtitle