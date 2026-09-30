## 1. Search candidate surface

- [x] 1.1 In `_applySuggestOverlay`, build the `#gd-sugg` panel style per mode: the history branch fills the inline WebView (`top:0; bottom:0`) while the suggestion branch keeps its bounded height.
- [x] 1.2 Add a single submit handler for `input.onAccepted`: if the suggestion surface has a first entry that is not a `(no results...)` placeholder, look that word up; otherwise look up the literal typed text.
- [x] 1.3 Suppress the suggestion overlay while an article lookup is pending for the same query (guard in `onSuggestionsReady`/`_applySuggestOverlay` keyed off `_requestedWord`), clearing it on article loaded and on not-found so a failed lookup still falls back to history.
- [x] 1.4 In `groupPicker`, record that a Search-scope selection started a lookup and skip the `_doSuggest()` re-query in `onClosed` for that case; leave the empty-field (`setActiveGroup` + history) path unchanged.
- [x] 1.5 Verify against the specs: empty field and no-match both show full-height history; suggestions stay a bounded dropdown; Enter opens the top suggestion (else the literal text); switching group with a query shows the article with no dropdown left over it.

## 2. Shared icon-button styling and Search/FTS row layout

- [x] 2.1 Convert the Search clipboard control from `ToolButton` to the standard icon `Button` recipe (icon font, matching fontSize/padding), keeping `Accessible.name: "Clipboard"` and the paste-then-look-up behavior.
- [x] 2.2 Widen `searchGroupButton` and `ftsGroupButton` to 1.3× (`Layout.preferredWidth` 3 → 3.9) while the field stays at 7, for both portrait and landscape.
- [x] 2.3 Remove the FTS Search button row and confirm the remaining triggers (Enter, whole-words toggle, scope change) all still run `_runFts()`.

## 3. Groups pane and membership editor

- [x] 3.1 Add `create_new_folder` (U+E2CC) to the `icon()` map and convert the Groups toolbar Add control to the standard icon button; keep `Accessible.name: "Add group"` and the open-create-dialog behavior.
- [x] 3.2 Convert the membership editor pencil from `ToolButton` to the standard icon button; keep `Accessible.name: "Rename group"` and the rename-dialog behavior.
- [x] 3.3 Add a `byPair` boolean and an icon toggle in the membership editor header (standard icon-button styling, `Accessible.name: "By Pair"`), reusing the Dicts tab's translate glyph.
- [x] 3.4 Build a grouped model for the available-to-add list (pair caption rows + dictionary rows, same pairing as the Dicts tab) when `byPair` is on, rebuilt wherever `groupNonMembers` is assigned; keep `memberList`/`memberModel` and its drag reorder unchanged and keep the available rows non-draggable.
- [x] 3.5 Reserve the trailing icon's width on member and non-member row names (`rightPadding`) so long dictionary names elide in the middle and never run under the add-to-group / remove-from-group icons.
- [x] 3.6 Fix the create-group and rename-group `contentItem` width so the name field and action buttons sit centered within the dialog's padded area and stay fully visible for long labels.

## 4. Verification and documentation

- [x] 4.1 Build the Android app and run the existing tests/smoke checks; run `openspec validate ui-polish`. (Built: `app/build.ps1 -Abi arm64-v8a -Configuration Debug` → `aurelex-debug.apk`, 60.5 MB; `qmlcachegen` compiled `main.qml`, so the QML parses. All 5 host suites pass: article_server, catalog, dictionary_index, index_cleanup, index_migration. `openspec validate` passes.)
- [x] 4.2 On-device pass over every scenario above in both themes, plus a Russian-locale check of the rename dialog and the wider group buttons in portrait and landscape. (Device ZY22HC8LTR, 1080x2400. Verified: FTS pane has no `Search` button; membership editor exposes `By Pair`/`Rename group` icon buttons; By Pair OFF shows no captions and ON shows `English/English` + `English/Japanese` caption rows while all 3 members keep their `Reorder` handles (member list ungrouped); the RU rename dialog is centered with `Отмена`/`Переименовать` fully visible; long names elide clear of the trailing `+`/`✕` icons. No crash/ANR.)
- [x] 4.3 Update the AGENTS.md accessible-element table: remove the FTS Search button row, add the membership-editor `By Pair` control, and note that `Add group` is now an icon control with its name unchanged.
- [x] 4.4 If any Qt source string changed, run `scripts/update-translations.ps1`, update the RU/JA catalogs, and recommit `app/i18n/*.qm`.
