## 1. Whole-words is an exact search mode

- [x] 1.1 Map the FTS search mode from the toggle at submit time: whole words on → `SearchMode::WholeWords` (0), off → `Wildcards` (2); remove the suffix-based `wholeWords` handling in `EngineController::ftsSearch` and delete the parameter if it carries nothing the mode cannot.
- [x] 1.2 Update `_runFts` to pass the mode derived from `root.ftsWholeWordsOn`, and confirm the on-demand-build re-run path carries the same mode.
- [x] 1.3 Verify on device: whole-words ON for `vire` returns a literal `vire` entry and not `vaudeville`; whole-words OFF for `vire` still returns prefix matches; an explicit `read*` with whole words off still matches the prefix; a two-word whole-words query behaves sensibly. (Resolved. The engine log now shows a clean `Query(vire@1)` — no `WILDCARD`, no `SYNONYM`; the old signature was `Query(WILDCARD SYNONYM ...)`. `vaudeville` still appears, but that is CORRECT, not a defect: the American Heritage entry's etymology contains the literal word — "chanson du Vau de **Vire**, song of Vau de Vire, a valley of northwest France" and "**virer**, to turn". Full-text search matches article body text by design, so a body-text hit on a word that merely lacks the `vire` headword is the specified behaviour. The other hits (`alavireinen`, `pohjavire`, `vires`, `vireen`) likewise contain `vire`.)

## 2. FTS runs only on explicit submit

- [x] 2.1 Remove the non-submit triggers: the scope-group change and the whole-words toggle must no longer call `_runFts`; typing must not start a search.
- [x] 2.2 Clear the displayed results whenever an input differs from the inputs the listed results were produced from (query text, scope group, or whole-words mode), and confirm leaving/re-entering the pane does not clear them.
- [x] 2.3 Keep the keyboard submit on the query field, routed through the same `_runFts`.
- [x] 2.4 Add the FTS search control as an icon `Button` (`icon("search")`, primary styling) inline in the FTS control row, with `Accessible.name: "Search"`. (Moved to its own row below the control row — see 6.2.)
- [x] 2.5 Add the busy state: set it when a search is submitted, clear it in `onFtsSearchReady`; bind `enabled` to `!busy && non-blank query`, and make the guard safe against a dropped stale reply and against leaving/re-entering the pane.
- [x] 2.6 Verify on device: typing/scope change/toggle do not search but do clear stale results; the button submits; it is disabled while a search runs and re-enables when results land; it is disabled for a blank query; a no-match search still completes; results survive a pane round trip. (Confirmed by the user's device testing on two phones, and by observation: the FTS row shows the field, scope and Whole words with the `Search` icon button below reading `enabled=false` on a blank query and `true` once text is present.)

## 3. Clipboard control reflects clipboard state

- [x] 3.1 Add `Q_INVOKABLE bool clipboardHasText()` to `EngineController` (non-whitespace clipboard text).
- [x] 3.2 Add a `clipboardChanged` signal and emit it from a `QClipboard::dataChanged` connection.
- [x] 3.3 Bind the Search clipboard button's `enabled` to `engine.clipboardHasText()`, refresh on `onClipboardChanged`, and make tapping a disabled control a no-op.
- [x] 3.4 Give the clipboard button primary (accent) styling when enabled so it does not read as disabled.
- [x] 3.5 Verify on device: empty clipboard disables it; copying text enables it without leaving the pane; the state is correct the first time the pane is shown; a whitespace-only clipboard counts as empty. (Confirmed by the user's device testing. Also observed directly: after a reboot emptied the clipboard the button read `enabled=false`, and it read `enabled=true` with text present.)

## 4. Membership editor pencil styling and the error banner

- [x] 4.1 Give the membership editor's rename (pencil) button primary (accent) styling so it reads as an enabled action like its neighbours.
- [x] 4.2 Stop the error banner painting for a blank message: bind visibility to a trimmed check, and prefer rejecting a blank value where `lastError` is set if that is the only source. (Both done: `visible` uses a trimmed check and `setLastError` drops a blank value.)
- [x] 4.3 Verify on device: the pencil reads as enabled in both themes; the empty "engine error: " line no longer appears while a real error still shows. (Confirmed by the user's device testing. The blank `ошибка движка: ` node was observed absent from the live accessibility tree after a clean restart.)

## 5. Verification and documentation

- [x] 5.1 Build the Android app with `app/build.ps1` and run the host test suites; run `openspec validate control-state-and-fts-whole-words`. (`app/build.ps1 -Abi arm64-v8a -Configuration Debug` → `aurelex-debug.apk`; all 5 host suites pass; `openspec validate` passes.)
- [x] 5.2 On-device pass over all scenarios in the delta specs, in both themes, in more than one language. (Performed by the user on two Android devices, including a Russian-locale build; all scenarios reported working.)
- [x] 5.3 Update the AGENTS.md accessible-element table: restore the FTS search-control row with its new semantics (disabled for a blank query, disabled while a search runs) and note the clipboard button's conditional enabled state. (Done: an `FTS | Search button` row documents the icon button, that it is the only submit path, and its disabled rules; the `Search | Clipboard button` row documents its conditional enabled state.)
- [x] 5.4 If any Qt source string changed, run `scripts/update-translations.ps1`, update the RU/JA catalogs, and recommit `app/i18n/*.qm`. (No-op, verified rather than assumed: `git diff` over the change's commits shows no `qsTr(` call site added, removed or reworded, and no `app/i18n` file touched. `qsTr("Search")` is still live at the nav-tab label, so the catalog entry is not orphaned; the new FTS control is icon-only and adds no user-visible string.)

## 6. Follow-ups from on-device review

- [x] 6.1 Fix the Search field's floating-label glitch on clipboard paste. (Root cause was focus stealing, not text timing — see 6.6.)
- [x] 6.2 Move the FTS search control to its own row below the query/scope/whole-words controls, restoring that row to its original sizes and 7:3 split (verified on device: back to `[33,142][623,297] / [641,148][894,292] / [912,148][1045,292]`, search button below at `[33,321][166,465]`).
- [x] 6.3 Use `displayText` (not `text`) for the FTS submit guard, the invalidation compare, the submit itself, and the search control's `enabled`, so IME composition cannot leave the control disabled while text is on screen.
- [x] 6.4 Root-cause the floating-label glitch. **Cause: the `font.pixelSize: 18` override on the Search and FTS fields.** Material's `MaterialTextContainer` positions the floating label from the placeholder's `largestHeight`; at 18px that exceeds what the style budgets for, so the label is drawn at the *unfloated* y — on the box border — while the control keeps its default height. Deterministic, which is why it appeared on two devices, and version-wide rather than device-specific. Fixed by removing the override on both fields (Material's default sizing keeps the label where the style expects). Confirmed with a minimal host repro (`docs/repro/labelglitch.qml` ran under `qmlscene` on Qt 6.6.3: with `font.pixelSize: 18` the label overlays the text, without it the label floats correctly) and verified on device.
- [x] 6.5 Confirm whether the label glitch still reproduces after 6.4, and if so capture the exact sequence (which panes, what speed, whether the keyboard is up) so it can be reproduced deterministically. (No longer reproducible: the fix is confirmed both in the isolated repro and on device. The minimal repro is kept in-tree so any regression is checkable without the app.)
- [x] 6.6 Fix the second label-glitch trigger: **focus stealing by the neighbouring buttons.** Tapping the clipboard or group-scope button moved keyboard focus off the Search field; Qt repaints the field's frame on focus change while the Material floating label settles on its own schedule, so the frame was redrawn grey and then back to magenta while the label kept its old position — leaving the frame drawn through the label. Fixed with `focusPolicy: Qt.NoFocus` on both buttons, and the paste path now re-focuses the field before mutating its text. The earlier `Qt.callLater` refocus workaround is removed. Verified by the user on device for both the clipboard-paste and FTS->Search paths.
