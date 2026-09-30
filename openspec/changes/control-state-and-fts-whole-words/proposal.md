## Why

On-device review of the FTS, clipboard, and error surfaces found:

- **Whole-words full-text search does not search whole words.** With "Whole words" on, `Vire` returns `vaudeville` and never a literal `vire` entry. The toggle only stops appending `*`; the query is still submitted in Xapian *wildcard* mode (`FLAG_WILDCARD` + a 100-term expansion cap), so a bare term expands to similar indexed terms. Upstream's own "Default (whole words)" mode is `SearchMode::WholeWords` (0), which the app never uses.
- **FTS runs on the wrong triggers.** Search currently fires on typing, on a scope-group change, and on the whole-words toggle. That is surprising: it starts work the user did not ask for, and it makes the search feel self-inflicted. An explicit submit is what the original plan called for.
- **Icon controls read as disabled.** The Search clipboard button and the membership editor's rename (pencil) button are plain Material buttons, so they render in the same grey as a disabled control.
- **An empty engine-error banner paints.** `engine.lastError` can be whitespace-only, which is truthy for `visible: engine.lastError.length > 0`.

## What Changes

- **Whole-words is a real mode.** The toggle selects an exact-term search (`SearchMode::WholeWords`, 0) instead of only suppressing a wildcard suffix; with it off the existing prefix/wildcard behavior is unchanged.
- **FTS gains an explicit search button.** Typing, changing the scope group, and toggling whole words SHALL NOT run a search. A dedicated icon button (Material `search` glyph) submits the query. It is disabled while the query is blank and while a search is in flight, and re-enables when the results land. The keyboard submit action remains a second way to run the same search.
- **Clipboard button reflects the clipboard.** The Search clipboard control is enabled only when the clipboard holds non-whitespace text, tracks clipboard changes while the app is focused, and uses primary (accent) styling when enabled. This needs a small `EngineController` addition; clipboard access stays on the C++ side, with no carve change.
- **Pencil is a primary action.** The membership editor's rename button is styled as an enabled primary action like its neighbours.
- **The empty error banner is suppressed.**
- **Accepted limitation (not fixed):** an enabled default-styled control and a disabled control share an appearance. In practice this only occurs in modal dialogs that carry OK/Cancel buttons, where the grey `Cancel` matches the platform convention, so it is documented rather than re-themed.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `full-text-search`: how a full-text search is triggered (explicit submit only) and what the whole-words toggle does (an exact-term mode, not a suffix).
- `usability-utilities`: the clipboard control's enabled state and styling track whether the clipboard has usable text.

## Impact

- **QML** (`app/main.qml`): `_runFts` mode selection and triggers, a new FTS search button, the clipboard button, the membership editor pencil, the engine-error banner.
- **C++** (`app/EngineController.{hpp,cpp}`): a clipboard-has-text invokable and a clipboard-change signal; the FTS mode/flag handling. No `gd_*` boundary change, no `patches/` entry, no engine edit.
- **Specs**: deltas for `full-text-search` and `usability-utilities`. The `full-text-search` delta must restate the "Search with wildcards" scenario against the corrected whole-words semantics, and replace the trigger requirements and scenarios added by the `ui-polish` change.
- **Accessibility / test IDs**: a new FTS search button needs an `Accessible.name` and the AGENTS.md table row that `ui-polish` removed returns with the new behavior (disabled when blank, disabled while searching).
- **Asset reuse**: the Material `search` glyph (U+E8B6) is already in `app/res/fonts/MaterialIcons-Regular.ttf` and in the `icon()` map — no new font asset or subset.
- **Localization**: the button is icon-only; no new user-visible English. If `ui-polish`'s "Search" catalog entry was retired, re-check the catalogs.
- **Not in scope (deferred to the planned FTS review):** FTS result presentation and how results clear between searches; the `gd_fts_search` `matchCase` argument question.
