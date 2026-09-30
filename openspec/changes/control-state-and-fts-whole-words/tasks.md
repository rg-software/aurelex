## 1. Whole-words is an exact search mode

- [ ] 1.1 Map the FTS search mode from the toggle at submit time: whole words on → `SearchMode::WholeWords` (0), off → `Wildcards` (2); remove the suffix-based `wholeWords` handling in `EngineController::ftsSearch` and delete the parameter if it carries nothing the mode cannot.
- [ ] 1.2 Update `_runFts` to pass the mode derived from `root.ftsWholeWordsOn`, and confirm the on-demand-build re-run path carries the same mode.
- [ ] 1.3 Verify on device: whole-words ON for `vire` returns a literal `vire` entry and not `vaudeville`; whole-words OFF for `vire` still returns prefix matches; an explicit `read*` with whole words off still matches the prefix; a two-word whole-words query behaves sensibly.

## 2. FTS runs only on explicit submit

- [ ] 2.1 Remove the non-submit triggers: the scope-group change and the whole-words toggle must no longer call `_runFts`; typing must not start a search.
- [ ] 2.2 Clear the displayed results whenever an input differs from the inputs the listed results were produced from (query text, scope group, or whole-words mode), and confirm leaving/re-entering the pane does not clear them.
- [ ] 2.3 Keep the keyboard submit on the query field, routed through the same `_runFts`.
- [ ] 2.4 Add the FTS search control as an icon `Button` (`icon("search")`, primary styling) inline in the FTS control row, with `Accessible.name: "Search"`.
- [ ] 2.5 Add the busy state: set it when a search is submitted, clear it in `onFtsSearchReady`; bind `enabled` to `!busy && non-blank query`, and make the guard safe against a dropped stale reply and against leaving/re-entering the pane.
- [ ] 2.6 Verify on device: typing/scope change/toggle do not search but do clear stale results; the button submits; it is disabled while a search runs and re-enables when results land; it is disabled for a blank query; a no-match search still completes; results survive a pane round trip.

## 3. Clipboard control reflects clipboard state

- [ ] 3.1 Add `Q_INVOKABLE bool clipboardHasText()` to `EngineController` (non-whitespace clipboard text).
- [ ] 3.2 Add a `clipboardChanged` signal and emit it from a `QClipboard::dataChanged` connection.
- [ ] 3.3 Bind the Search clipboard button's `enabled` to `engine.clipboardHasText()`, refresh on `onClipboardChanged`, and make tapping a disabled control a no-op.
- [ ] 3.4 Give the clipboard button primary (accent) styling when enabled so it does not read as disabled.
- [ ] 3.5 Verify on device: empty clipboard disables it; copying text enables it without leaving the pane; the state is correct the first time the pane is shown; a whitespace-only clipboard counts as empty.

## 4. Membership editor pencil styling and the error banner

- [ ] 4.1 Give the membership editor's rename (pencil) button primary (accent) styling so it reads as an enabled action like its neighbours.
- [ ] 4.2 Stop the error banner painting for a blank message: bind visibility to a trimmed check, and prefer rejecting a blank value where `lastError` is set if that is the only source.
- [ ] 4.3 Verify on device: the pencil reads as enabled in both themes; the empty "engine error: " line no longer appears while a real error still shows.

## 5. Verification and documentation

- [ ] 5.1 Build the Android app with `app/build.ps1` and run the host test suites; run `openspec validate control-state-and-fts-whole-words`.
- [ ] 5.2 On-device pass over all scenarios in the delta specs, in both themes, in more than one language.
- [ ] 5.3 Update the AGENTS.md accessible-element table: restore the FTS search-control row with its new semantics (disabled for a blank query, disabled while a search runs) and note the clipboard button's conditional enabled state.
- [ ] 5.4 If any Qt source string changed, run `scripts/update-translations.ps1`, update the RU/JA catalogs, and recommit `app/i18n/*.qm`.
