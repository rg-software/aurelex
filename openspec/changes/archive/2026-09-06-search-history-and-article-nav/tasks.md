## 1. Bottom bar: remove History tab

- [x] 1.1 Remove the History entry from `navItems` in `app/main.qml` (keep Search 0, Dicts 1, Groups 3, FTS 4, Favs 6).
- [x] 1.2 Add a `_tabIndexForState()` helper that returns the nav-tab position whose `idx` matches the current `state` (-1 for the article pane), and use it for `TabBar.currentIndex` and the top-toolbar title label; delete the `state === 5` title branch and the `_navTo(5)` branch.
- [x] 1.3 Remove the `historyPane` block and `_openHistory()`.
- [x] 1.4 Update the onboarding/help copy that lists the bottom tabs (remove "History", keep "Search, Dictionaries, Groups, FTS and Favorites").

## 2. History in the Search candidate surface

- [x] 2.1 Generalize the in-WebView candidate overlay: repurpose `_applySuggestOverlay` to render either suggestions (`sugg` mode) or lookup history (`history` mode) in the same `#gd-sugg` container, preserving the `_blankPending` / `onLoadingChanged` flush machinery from `_flushPendingSugg`.
- [x] 2.2 Build the history overlay rows: most-recent-first words from `engine.history`, each a tappable `data-w` anchor; add a per-row remove control (`data-action="remove-history"`) and a "Clear all" row (`data-action="clear-history"`); show a small empty-state message when history is empty.
- [x] 2.3 Switch the surface to `history` mode when the search field is empty (`_doSuggest` empty path) and when a typed query yields no suggestions (empty `suggestionsReady` result); switch back to `sugg` mode as soon as the user types.
- [x] 2.4 Extend `articleLinkPoller` dispatch with `HIST:` (lookup the history word), `HISTDEL:` (call `engine.removeHistory(word)`), and `HISTCLEAR:` (call `engine.clearHistory()`).
- [x] 2.5 Re-render the history overlay on `engine.historyChanged` while in `history` mode so removals/clears update immediately; clear history mode when a lookup starts (reuse `_showArticle`'s existing overlay hide).

## 3. Browser-style article back/forward

- [x] 3.1 Add a `fwdStack` property (array of `{word, html}`) alongside `navStack`.
- [x] 3.2 Rework `_backFromArticle()`: push the current article onto `fwdStack`, pop `navStack`, render the previous article; when `navStack` is empty keep today's behavior and clear `fwdStack`.
- [x] 3.3 Add `_forwardFromArticle()`: push current onto `navStack`, pop `fwdStack`, render; clear nothing else.
- [x] 3.4 In `_showArticle()` (all fresh lookups), clear `fwdStack` after pushing the previous article onto `navStack`.
- [x] 3.5 Clear `fwdStack` when entering the Search empty-state / clearing inline article, keeping state consistent.

## 4. Article header redesign

- [x] 4.1 Inline article toolbar (Search pane): remove the caption `Label` (`"Dictionary article"` / `currentWord`), make the header frameless (no fill/border), right-justify the controls, and add the **Forward** `ToolButton` (icon `arrow_forward`/`access_forward`, `Accessible.name: "Forward"`) with `enabled: fwdStack.length > 0`; keep Back and Star logic + accessible names.
- [x] 4.2 Full-pane article toolbar (state 2): apply the same frameless/right-justified/Back/Forward/Star treatment.
- [x] 4.3 Register the forward icon glyph in the `icon()` map (`arrow_forward` ≈ 0xe5c8, or `access_forward`).

## 5. Verify

- [x] 5.1 Build (`pwsh -File .\app\build.ps1 -SkipConfigure`) + install on device; boot clean with no QML/JS errors.
- [x] 5.2 Verify empty Search tab shows history (most-recent-first); typing switches to suggestions; a no-result query reverts to history; tapping a history word looks it up; per-row remove and Clear all update the overlay and persist after restart.
- [x] 5.3 Verify five bottom tabs only, no History, correct highlight for each tab and the top-bar title.
- [x] 5.4 Verify Back/Forward through several in-article links (back re-opens previous, forward re-opens backed-out article, a fresh lookup clears forward); Back clears the article in inline mode; both toolbars show the frameless right-justified Back/Forward/Star.
- [x] 5.5 Update `AGENTS.md` accessible-element table (History tab row removed, Forward button, empty-state history list note) and sanity-check the changed rows with uiautomator.