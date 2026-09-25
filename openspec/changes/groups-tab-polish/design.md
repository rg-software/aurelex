# design

## Context

Pure-QML UI change (see proposal.md — Why). The engine boundary already exposes
`gd_group_rename`/`gd_group_delete` through `EngineController`; the existing QML
"Rename" menu item called `engine.renameGroup(id, name + "_r")` — a stub that
appended a suffix instead of prompting. The work is confined to `app/main.qml` +
localization catalogs + `AGENTS.md` element-ID table.

The QML file deliberately runs with legacy component behavior (no
`pragma ComponentBehavior: Bound`), so delegates use implicit `modelData`/`index`
and `ItemDelegate` background clicks coexist with child `ToolButton`s — the same
pattern already used by the favorites and dicts row delegates.

## Goals / Non-Goals

**Goals:**
- Search is the start tab whenever onboarding is not showing.
- Groups rows: static name, per-row membership-edit + confirmed-delete controls,
  no subtitle, no overflow menu.
- A real, usable rename dialog backed by the existing `gd_group_rename` path,
  reachable from inside the group's membership editor.

**Non-Goals:**
- No changes to the engine, the carve boundary, group membership, or persistence.
- No new backend persistence for the start tab (state is already unpersisted and
  defaults to Search; only the post-onboarding nav needed wiring).

## Decisions

### 1. Start-tab-on-launch: route from the async `onboardedChanged`, not on QML load
`EngineController::initialize` runs `gd_init` + `loadSettings()` **asynchronously**
(`QtConcurrent::run`), so `engine.onboarded` is still its default `false` when the
QML `Component.onCompleted` fires. The pre-fix code set `state = 1` whenever
`!engine.onboarded` — i.e. on EVERY launch, because the real persisted value had
not arrived yet. That is why returning users (onboarded, no welcome card) still
started on Dicts.

The initial tab is therefore routed from the authoritative async
`onBoardedChanged` signal, once, guarded by `_bootRouted`. First run
(`onboarded == false`) lands on Dicts so the welcome card overlays it; every
other launch (`onboarded == true`) lands on Search. The "Get started" button
still flips `root.state = 0` directly (the guard prevents the second
`onboardedChanged` from undoing any later navigation).
- Alternative rejected: persisting a `lastTab` setting — adds storage for no
  observable benefit; the spec only requires starting on Search.

### 2. Group name row is the membership-editor entry point
The group row is tappable: `onClicked` on the row opens the membership editor
(guarded to non-"All"), so there is no pencil/edit control on the row — the only
per-row control is the delete trash. `rightPadding` keeps the name clear of that
one icon. Rename lives inside the editor (header pencil button).

### 2.5 Membership editor is all-icon, reorder by dragging the whole row
Back (arrow_back), Rename (edit) and Remove-from-group (close) are icon-only
`ToolButton`s; Add-to-group (add) likewise. The editor header shows just the
group name (no redundant "Group:" prefix). Reordering is by **drag across the
whole member row**: a full-width `MouseArea` bags the row (`anchors.fill`), so
grabbing anywhere on a member starts a reorder — no 40px handle strip. The
handle's `onPressed` arms the move immediately, `onPositionChanged` recomputes
the target row from the finger Y delta (`Math.round(dy / 44)` row height —
delta-based, so it works regardless of list scroll offset) and calls
`engine.groupMoveDict`, and `onReleased` ends the gesture. `preventStealing:
true` keeps the ListView's flick-scroll from hijacking the gesture (the Remove
button sits above the bag and still gets its taps). The "available dictionaries"
list has no drag surface and no drag behaviour (you cannot reorder what isn't in
the group yet). The up/down arrow buttons were removed once the gesture was
verified on-device.

### 3. Stale editor title after rename
Renaming from inside the membership editor updated the engine and the groups
list, but the editor's `Group: %1` header (bound to `editingGroupName`, captured
when the editor opened) stayed stale until a re-render. The rename dialog's
`onAccepted` now also writes the new name into `editingGroupName` when the
renamed group is the one being edited, so the header updates in place. (The
engine's `refreshGroups()` still reconciles the list itself.)

### 3. Why reorder previously failed (both arrows and drag depend on this)
Device testing found the reorder UI initially "did nothing". Two bugs:
1. **Display order ignored the group's order** — `onGroupDictsReady` pushed
   members in the *global dictionary order* the engine lists them, so reorder
   changes never showed. Members are now insertion-sorted by `memberIndex`
   (the position inside the group's membership).
2. **Async race** — the UI called `engine.groupMoveDict()` (async on
   `QtConcurrent`) and refreshed immediately, which could read the order
   *before* the mutation committed. `groupAddDict`/`Remove`/`Move` now emit a new
   `groupMembersChanged` signal after the engine commits; QML listens and only
   then re-queries `groupDicts`. Both the (now removed) arrows and the drag
   gesture rely on this commit-then-refresh ordering.

### 3.5 Rename lives inside the membership editor; field not pre-selected
The membership editor header adds a "Rename group" button (pencil ToolButton)
that opens the modal rename `Dialog` (prefilled `TextField` + standard OK/Cancel).
`onAccepted` trims and guards against empty (mirrors `gd_group_rename`'s own
null/empty check) and `id <= 0`. On success `EngineController.renameGroup` already
calls `refreshGroups()`, so the list updates with no extra QML wiring.
The dialog places the caret at the end of the prefilled name instead of
`selectAll()`: full selection risks an accidental overwrite of the whole name
with one keystroke — the user only asked for the cursor to be in the field.
- Alternative rejected: inline rename (TextInput swap on the row) — more QML
  machinery for a modal the user explicitly placed behind the editor button.

### 4. Delete is confirmed, not immediate
The trash ToolButton now opens a modal `Delete group confirmation` dialog
(OK/cancel) instead of deleting instantly — a group delete removes its
membership/order with no undo. `visible` is bound to a `deleteGroupId > -1`
pick state, mirroring the remove-dictionary confirmation dialog.

### 4.5 Group creation via dialog + unique names
The inline "new group" row is gone. "Add group" opens a modal dialog with a name
field + inline error label. OK calls `engine.createGroup`; the async success
result comes back as `groupCreated(id, name)` and QML opens that group's
membership editor directly (no need to wait for the group list refresh). The
engine boundary now enforces case-insensitive unique names — `gd_group_create`
and `gd_group_rename` return `-2` for a taken name — and the controller maps
`-2` to a `groupNameTaken(name)` signal so QML re-opens the dialog with an
inline "already exists" error. This keeps the invariant even for the CI smoke
tool (which still creates one fresh name).

### 4.6 Dicts: single deletion path + pair-header select-all
Per-row remove buttons (flat + by-pair) and the per-pair "Remove pair" action
are removed; the multi-select "Remove" button is the only delete control. In the
By-Pair view the section header becomes a tap target that selects/clears every
dictionary in that pair (`_toggleSelectPair`) with a check indicator
(`_pairSelected`), as a shortcut for assembling a deletion selection. The
remove-dictionary confirmation dialog and its per-row trigger are deleted.
The import control is re-labelled "Add" with a folder-open glyph (the custom
`contentItem` labels use `Material.primaryHighlightedTextColor` — `Material.accent`
would be invisible on the accent-filled highlighted RoundButton) and the delete
button sits next to it, tinted like the By Pair toggle (gray when no selection,
magenta when selected). "By Pair" becomes a translate (文/A) glyph-only button.

### 4.6b Tab idempotency for the article pane
Switching away from the Search tab (to Dicts/Groups/FTS/Favs) used to call
`_clearInlineArticle()` — wiping `currentWord`/`currentHtml` — so returning to
Search showed an empty pane and refocused the search field. Articles now
survive the round trip: `_navTo` no longer clears inline article state when
leaving, and `onStateChanged` skips its re-suggest/refocus when `inlineArticle`
is still set. The loader's `onLoaded` re-renders `currentHtml` on return (the
WebView is torn down on leave by the `active` binding and rebuilt on return).
The no-article case (typed query / suggestions / history) keeps the old
refocus-and-re-suggest behavior.

### 4.7 Force member-list redraw on group open
The membership editor could open with blank dict rows when a group was reopened:
stale `groupMembers` lingered and the recycled ListViews didn't redraw. Two
changes: `_openMembership` clears both member arrays (fresh bindings), and
`onGroupDictsReady` schedules `forceLayout()` on both lists (`Qt.callLater`),
guarding that the editor still targets the same group.

### 4.8 Compact group-scope buttons in Search and FTS
Both input rows keep the search field and group scope in a 7:3 RowLayout. The
scope is an arrowless Button showing only the current group's name, painted in
the app's standard accent scheme (Material accent fill, white label text) so it
reads as tappable; taps always open the shared modal `Select group` picker, even
when only the `All` group exists (an `enabled: groups.length > 1` guard left the
button dead on a fresh install with no custom groups). Search follows the active
group, while FTS keeps its own scope for the current query. The FTS row also
replaces the "Whole words" checkbox with a checkable match-word glyph icon button
(like the Search clipboard button) with `checked` toggling whole-word matching.
The search button remains below, disabled while the FTS build is running.

### 4.9 Bottom-dock theme cell is a TabBar sibling; icon sizes stay fixed
The dark-mode toggle must not look like the selected tab. A `TabButton` inside
the `TabBar` is silently added to its exclusive selection group (tapping it sets
`checked`/`currentIndex`), and a plain `Button` inside the `TabBar` wasn't laid
out as a tab. The dock is therefore a plain `Row`: the `TabBar` takes 5/6 and the
theme `Button` is a SIBLING taking 1/6, so it can never become the active tab.
The nav icons render at a fixed 18 px again: an earlier per-glyph normalization
(`iconSize()`) made the short `manage_search` glyph visibly *larger* than the
rest, so it was reverted pending a better approach.

### 5. Icon set, localization, element IDs
Adds Material glyphs to the root `icon()` map (family already registered):
`edit` (`0xe150`), `drag_handle` (`0xe25d`); `add`/`close`/`arrow_back` already
existed. New `qsTr` strings: `Delete group`, `Delete group "%1"?`, and the
delete-confirmation body; `Rename group` (dialog title) is already catalogued.
Obsolete strings (`Create`, `<- Back`, `Up`, `Down`, `Add`, `All dictionaries`,
`id=%1`, menu `Rename`/`Delete`) drop via `lupdate -no-obsolete`. `AGENTS.md`
element-ID rows for Groups are rewritten to the new controls (member rows expose
a `Reorder` drag handle; no more Move-up/Move-down buttons).

## Risks / Trade-offs

- [Rename moved behind an extra tap] → Deleting that tap was the user's explicit
  call (row is static); the membership editor is one pencil-tap away and rename
  is a header button there.
- [Delete confirmation modal on a destructive act] → Intended; mirrors the
  remove-dictionary confirmation and gives an undo-free action a decision point.
- [Name label underlaps the right-aligned icons] → `rightPadding: 108` reserves
  room; long names also elide (`Text.ElideMiddle`).
- [Rename dialog IME / focus] → prefilled + `forceActiveFocus` on open mirrors the
  group-create field; keyboard appears with the dialog, which is acceptable since
  the remove-dict dialog also focuses its content.
- [Drag is not "smooth" (row doesn't glide under the finger)] → The member
  ListView recycles delegates and Qt Quick 6.6 exposes no per-row ghost/translate
  API, so a fluid follow-the-finger animation would need a custom (non-recycled)
  layout or a parallel overlay item polled from `mouse.y` — real Android jank
  risk for a borderline UX gain. Accepted: reorder happens live at row
  boundaries instead of a smooth glide; the row under the finger IS marked
  (`groupsPane._dragIndex` bound to the member delegate's `highlighted`), so the
  active line is always visible while dragging. Because the ListView recycles the
  delegate mid-drag (the MouseArea's `released` can be lost), ending the drag does
  NOT rely on release: a single-shot 400 ms watchdog restarts on every
  press/move and finalizes the drag when the finger goes still — so the highlight
  always clears after the finger lifts. Revisit the smooth glide only if the
  user decides the cost is worth it.

## Migration Plan

- UI-only; ships with the next app build. No data migration. Rollback = revert the
  QML + catalog + AGENTS.md changes in one commit.

## Open Questions

- None. (Device install/build steps are toolchain concerns, not design decisions.)