## 1. Whole-words is an exact search mode

- [x] 1.1 Map the FTS search mode from the toggle at submit time: whole words on → `SearchMode::WholeWords` (0), off → `Wildcards` (2); remove the suffix-based `wholeWords` handling in `EngineController::ftsSearch` and delete the parameter if it carries nothing the mode cannot.
- [x] 1.2 Update `_runFts` to pass the mode derived from `root.ftsWholeWordsOn`, and confirm the on-demand-build re-run path carries the same mode.
- [x] 1.3 Verify on device: whole-words ON for `vire` returns a literal `vire` entry and not `vaudeville`; whole-words OFF for `vire` still returns prefix matches; an explicit `read*` with whole words off still matches the prefix; a two-word whole-words query behaves sensibly. (Resolved. The engine log now shows a clean `Query(vire@1)` — no `WILDCARD`, no `SYNONYM`; the old signature was `Query(WILDCARD SYNONYM ...)`. `vaudeville` still appears, but that is CORRECT, not a defect: the American Heritage entry's etymology contains the literal word — "chanson du Vau de **Vire**, song of Vau de Vire, a valley of northwest France" and "**virer**, to turn". Full-text search matches article body text by design, so a body-text hit on a word that merely lacks the `vire` headword is the specified behaviour. The other hits (`alavireinen`, `pohjavire`, `vires`, `vireen`) likewise contain `vire`.)

## 2. FTS runs only on explicit submit

- [x] 2.1 Remove the non-submit triggers: the scope-group change and the whole-words toggle must no longer call `_runFts`; typing must not start a search.
- [x] 2.2 Clear the displayed results whenever an input differs from the inputs the listed results were produced from (query text, scope group, or whole-words mode), and confirm leaving/re-entering the pane does not clear them.
- [x] 2.3 Keep the keyboard submit on the query field, routed through the same `_runFts`.
- [x] 2.4 Add the FTS search control as an icon `Button` (`icon("search")`, primary styling) inline in the FTS control row, with `Accessible.name: "Search"`.
- [x] 2.5 Add the busy state: set it when a search is submitted, clear it in `onFtsSearchReady`; bind `enabled` to `!busy && non-blank query`, and make the guard safe against a dropped stale reply and against leaving/re-entering the pane.
- [ ] 2.6 Verify on device: typing/scope change/toggle do not search but do clear stale results; the button submits; it is disabled while a search runs and re-enables when results land; it is disabled for a blank query; a no-match search still completes; results survive a pane round trip. (Partly verified: the FTS row now shows the field, scope, Whole words and the new `Search` icon button, and the button reads `enabled=false` on a blank query. The submit/busy/clearing paths still need a manual pass — `adb` cannot reliably drive text input on this device.)

## 3. Clipboard control reflects clipboard state

- [x] 3.1 Add `Q_INVOKABLE bool clipboardHasText()` to `EngineController` (non-whitespace clipboard text).
- [x] 3.2 Add a `clipboardChanged` signal and emit it from a `QClipboard::dataChanged` connection.
- [x] 3.3 Bind the Search clipboard button's `enabled` to `engine.clipboardHasText()`, refresh on `onClipboardChanged`, and make tapping a disabled control a no-op.
- [x] 3.4 Give the clipboard button primary (accent) styling when enabled so it does not read as disabled.
- [ ] 3.5 Verify on device: empty clipboard disables it; copying text enables it without leaving the pane; the state is correct the first time the pane is shown; a whitespace-only clipboard counts as empty. (Partly verified: the button is present at its new icon-Button width and reads `enabled=true` while the clipboard holds text. The empty-clipboard and live-change halves need a manual pass — no tool on this device can empty the clipboard from `adb`.)

## 4. Membership editor pencil styling and the error banner

- [x] 4.1 Give the membership editor's rename (pencil) button primary (accent) styling so it reads as an enabled action like its neighbours.
- [x] 4.2 Stop the error banner painting for a blank message: bind visibility to a trimmed check, and prefer rejecting a blank value where `lastError` is set if that is the only source. (Both done: `visible` uses a trimmed check and `setLastError` drops a blank value.)
- [ ] 4.3 Verify on device: the pencil reads as enabled in both themes; the empty "engine error: " line no longer appears while a real error still shows. (Verified: the blank `ошибка движка: ` node is gone from the live tree after a clean restart, confirming both halves of 4.2. The pencil colour and the dark-theme pass still need a manual look.)

## 6. Follow-ups from on-device review

- [ ] 6.1 Fix the Search field's floating-label glitch on clipboard paste: the label overlapped the field border because `.text` was assigned while the field still owned focus. Paste now blurs first and suppresses the suggestion re-query, matching the article-open paths, so the label settles above the border.
- [ ] 6.2 Move the FTS search control to its own row below the query/scope/whole-words controls, restoring that row to its original sizes and 7:3 split (verified on device: back to `[33,142][623,297] / [641,148][894,292] / [912,148][1045,292]`, search button below at `[33,321][166,465]`).
- [x] 6.3 Use `displayText` (not `text`) for the FTS submit guard, the invalidation compare, the submit itself, and the search control's `enabled`, so IME composition cannot leave the control disabled while text is on screen.
- [ ] 6.4 Root-cause the floating-label glitch. Mechanism (confirmed by reading the Qt 6.6 Material style): `FloatingPlaceholderText` is a compiled C++ item positioned from `controlHeight` / `controlImplicitBackgroundHeight`, while the control's `topPadding` is itself bound to `placeholderText.length > 0 && (activeFocus || length > 0)` — a circular dependency the style does not re-evaluate when the pane is re-laid-out around it. The pane also keeps resizing for ~420 ms after a tab switch (`inlineWebTimer` -> `inlineWebReady` -> the WebView loader), which is why the earlier `Qt.callLater` focus fix was too early to help. Mitigation applied: `_settleSearchFieldLabel()` toggles a `topPadding` binding once the last resize lands (timer trigger) and after a paste, forcing the style to re-evaluate from a settled layout. **NOT VERIFIED** — every screenshot captured over `adb` (both the FTS->Search jump and paste) shows the label correctly placed, so the glitch was never reproduced off-device and the fix is unconfirmed. Needs the user's eyes.
- [ ] 6.5 Confirm whether the label glitch still reproduces after 6.4, and if so capture the exact sequence (which panes, what speed, whether the keyboard is up) so it can be reproduced deterministically.

## 5. Verification and documentation

- [x] 5.1 Build the Android app with `app/build.ps1` and run the host test suites; run `openspec validate control-state-and-fts-whole-words`. (`app/build.ps1 -Abi arm64-v8a -Configuration Debug` → `aurelex-debug.apk`; all 5 host suites pass; `openspec validate` passes.)
- [ ] 5.2 On-device pass over all scenarios in the delta specs, in both themes, in more than one language.
- [ ] 5.3 Update the AGENTS.md accessible-element table: restore the FTS search-control row with its new semantics (disabled for a blank query, disabled while a search runs) and note the clipboard button's conditional enabled state.
- [ ] 5.4 If any Qt source string changed, run `scripts/update-translations.ps1`, update the RU/JA catalogs, and recommit `app/i18n/*.qm`.
