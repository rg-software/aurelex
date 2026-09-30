## Context

The FTS pane submits every search with a hardcoded `mode = 2` (Wildcards) from `app/main.qml::_runFts` and passes the whole-words toggle as a separate boolean. That boolean is consumed only in `EngineController::ftsSearch`, where it decides whether to append `*` to each term. The mode then travels unchanged into `carve/gd_boundary.cc::gd_fts_search` → `Dictionary::Class::getSearchResults` → `FtsHelpers::FTSResultsRequest::run`, which for `searchMode == FTS::Wildcards` sets `Xapian::QueryParser::FLAG_WILDCARD` and `set_max_expansion(100)`. A bare term in that mode is parsed as a wildcard, and Xapian reports it as `Query(WILDCARD SYNONYM ...)` — the observed `vire` → `vaudeville`.

`FTS::SearchMode` (engine/src/fulltextsearch.hh) is `WholeWords = 0` ("Default search using Xapian query syntax"), `PlainText = 1`, `Wildcards = 2`, `RegExp = 3`. Upstream's own UI offers only `Default` (0) and `Wildcards` (2), so mode 0 is the intended exact/default path and is currently unused by the app. The FTS index is written with `Folding::applyForIndex` (diacritic removal + case folding) for both the body and the headword, and the same folding is applied to the query string, so a single folded term is the right exact query.

Search completion is observable in QML: `_runFts` calls `engine.ftsSearch`, and `EngineController` emits `ftsSearchReady(query, results)` when the search future finishes (`app/main.qml` already connects `onFtsSearchReady` and drops replies whose query no longer matches the field). That signal is the natural "results have landed" edge for re-enabling the control.

Clipboard access is centralized in `EngineController::clipboardText()` (`QGuiApplication::clipboard()->text()`); there is no invokable for "does the clipboard have text" and no change notification.

See `proposal.md` for motivation; see the delta specs for required behavior.

## Goals / Non-Goals

**Goals:**
- Make whole words a genuinely distinct search mode so its results are literal.
- Make FTS work happen only on an explicit submit, with a real busy state on the control.
- Make the clipboard control's enabled state follow the clipboard, and its styling read as a primary action.
- Remove the blank error banner.

**Non-Goals:**
- Redesigning FTS result presentation or how results clear between searches (the separately planned FTS review).
- Changing the carve boundary, `patches/`, or the engine submodule. All fixes stay in `app/`.
- Re-theming Material, or giving disabled controls a distinct treatment.

## Decisions

### D1: Whole words selects `SearchMode::WholeWords` (0); prefix keeps Wildcards (2)
`_runFts` chooses the mode from the toggle at submit time: `wholeWords ? 0 : 2`. Rationale: mode 0 is upstream's own "Default" mode and parses a folded term as an exact term, which is exactly "whole words". The alternative — keeping mode 2 and stripping `FLAG_WILDCARD` — was rejected because that flag lives in engine code (out of bounds; `engine/` is never edited), and because `mode` is the boundary's documented knob for this.

The `wholeWords` parameter on `EngineController::ftsSearch` no longer selects the mode. It is removed unless it still carries information the mode cannot; leaving a parameter that lies is worse than deleting it.

### D2: One submit path, three silent triggers that invalidate results
`_runFts` becomes the single submit. The three non-submit paths are removed as *triggers*: typing, the scope change, and the whole-words toggle. Each of them instead **invalidates** the displayed results under the chosen "Option B" rule: results belong to the inputs that produced them, so any change to the query text, the scope group, or the whole-words mode clears `ftsResults`.

Implementation shape: `_runFts` records the inputs it submitted (query, group, whole-words) as an "applied" triple; a change to the live inputs is compared against that triple and clears the list on mismatch. Leaving and returning to the pane changes nothing (the applied triple is unchanged), so the existing "Search state survives navigation" behavior is preserved — only a real input change clears.

The keyboard submit (`ftsInput.onAccepted`) is retained and calls the same `_runFts`, so a physical/IME submit and the button are one path.

*Alternative considered:* leave the stale list visible and rely on the user to notice (option A) — rejected as silently misleading, since the visible query and scope would not describe the rows on screen. *Alternative considered:* keep results and badge them as out of date (option C) — nicer, but it is a presentation feature with a new user-visible string and translations, so it belongs in the planned FTS review rather than here.

### D3: Busy state is driven by the search's own completion signal
Add `property bool ftsSearching` driven by two edges: set `true` in `_submitFts`, and `false` in `onFtsSearchReady`. The control's `enabled` is `!ftsSearching && queryIsNotBlank`.

`ftsSearchReady` is emitted by `EngineController`'s future watcher for the initial query *and* for the on-demand-build re-run (the same watcher path), so the flag clears when the results the user is waiting for land, not merely when the first query returns.

*Alternative considered:* derive busy from `engine.ftsIndexing` / the build state. Rejected — an index build is a long ambiguous phase (it can cover other dictionaries), and the requirement is about the submitted query, not the build.

*Edge case:* a search whose reply is dropped for a stale query would leave the flag set. Guard by comparing the reply's query, and clear on the pane's own re-entry so a stuck flag cannot outlive the pane. Recorded as an implementation check.

### D4: The button is an icon button, reusing the existing `search` glyph
`_runFts`'s control is a Material icon `Button` (`icon("search")`, already in the font and the `icon()` map), styled with `highlighted` for its primary action, sitting inline in the FTS control row next to the group-scope and whole-words controls, with `Accessible.name: "Search"`. It does not use the Material Symbols subset, so no font/subset regeneration.

### D5: Clipboard state needs a signal, because the clipboard is read on demand
Add to `EngineController`:
- `Q_INVOKABLE bool clipboardHasText() const` — `!clipboardText().trimmed().isEmpty()`.
- a `clipboardChanged` signal, emitted from a `QClipboard::dataChanged` connection.

The QML button binds `enabled: engine.clipboardHasText()` and refreshes on `onClipboardChanged`. Clipboard access stays on the C++ side, as `clipboardText()` already is, and no carve surface is added.

*Alternative considered:* style it always-accent and skip detection. Rejected per the decision to reflect real state; a disabled control should not silently no-op.

### D6: The default-vs-disabled sameness is accepted, not fixed
An enabled default-styled control and a disabled control share an appearance. In practice the only place that ambiguity is visible is a modal dialog with an OK/Cancel pair, where the grey `Cancel` matches the platform convention; elsewhere disabled controls are icon buttons that never appear in default styling *and* enabled (the Dicts Remove button is the only hybrid, and its grey is self-consistent with its disabled state). Decision: do not re-theme, and do not spec a general default/disabled/primary distinction. The concrete offenders this change does fix are the two controls that were wrongly default-styled while enabled and primary (clipboard, pencil), which is covered by their own requirements.

### D7: Suppress the blank banner
Bind the banner's `visible` to a trimmed check rather than `.length > 0`. At implementation time, prefer rejecting a blank value where `lastError` is set if a blank message can reach it from an engine call.

## Risks / Trade-offs

- **Mode 0 may behave differently for multi-word queries.** [Mitigation] Upstream's Default mode uses Xapian syntax with `OP_AND`; verify a two-word whole-words query on device and adjust the spec wording if it surprises.
- **"Whole words" still returns words that merely contain the query.** [Resolved, not a defect] The original report was `vire` returning `vaudeville` in whole-word mode. After the mode fix the engine logs a clean `Query(vire@1)` and the remaining hits are legitimate body-text matches: the American Heritage `vaudeville` entry's etymology contains the literal "Vau de **Vire**" and "**virer**", and the other results (`alavireinen`, `pohjavire`, `vires`, `vireen`) contain `vire`. Full-text search is specified to match article *bodies*, not just headwords, so this is correct behaviour. The genuine defect was the wildcard/synonym expansion, which the mode change removed.
- **An explicit submit re-introduces the "long search" concern the user once raised.** [Mitigation] Nothing runs until the user asks, and the busy state plus the existing max-results cap bound the wait; this is the user's explicit decision.
- **A stuck busy flag would disable the control permanently.** [Mitigation] D3's stale-reply guard and pane re-entry clear; add an on-device check.
- **`dataChanged` can fire often.** [Mitigation] The slot recomputes a boolean and emits; the binding is cheap.
- **Android restricts clipboard reads to the focused app.** [Mitigation] The control is reachable only on the focused Search pane; verify the "correct state on first show" scenario on device.
- **Removing the toggle/scope triggers could leave stale results on screen.** [Mitigation] Chosen behavior (D2, option B) clears the list whenever an input differs from the submitted one, so results never disagree with the visible inputs. The clearing may feel abrupt mid-setup; verify on device that it reads as deliberate rather than broken, and only then consider the option-C badge.

## Migration Plan

No data or index migration: the index format is unchanged and the modes only change query parsing. Rollback is reverting `app/main.qml` + `app/EngineController.*`.
