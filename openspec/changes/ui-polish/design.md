## Context

The Search tab's candidate surface (headword suggestions / recent lookups) is not a QML list: it is an HTML panel (`#gd-sugg`) rendered inside the inline article WebView, because QML controls cannot stack above Android's native WebView surface (`app/main.qml`, `_applySuggestOverlay`). Both modes share one div and one style string, currently capped at `max-height:72%`. The group-scope picker is a modal `Dialog` that tears the inline WebView down while open and, on close, re-runs `_doSuggest()` when the field has text. Article lookups are requested through `engine.lookup*` and answered asynchronously via `onArticleLoaded`, with `_requestedWord` guarding stale replies.

Several panes now have two visually different icon controls: the dictionary toolbar uses `Button` + the icon font (`root.icon(...)`), while the Search clipboard and the membership editor's pencil use `ToolButton`. The membership editor's member/non-member rows draw their trailing icon as an overlay anchored to the delegate's right edge while the name content fills the delegate, so long names run underneath. The group name dialogs override `contentItem` with a `ColumnLayout { width: parent.width }`.

See `proposal.md` for motivation and the delta specs for the required behavior.

## Goals / Non-Goals

**Goals:**
- Make the Search tab's interaction model match the specs: a submitted query opens an article, and a group switch with a query opens an article instead of leaving a suggestion dropdown over it.
- Unify icon-button styling and fix the layout collisions/centering with the smallest QML changes.
- Add the membership-editor By Pair toggle that groups only the available-to-add list.

**Non-Goals:**
- No changes to the engine, the `gd_*` boundary, the carve, or `patches/`.
- No new capability, no new font asset, no new dependency.
- Not changing how suggestions are computed or ordered (the top suggestion is whatever the engine already returns first).

## Decisions

### D1: Full-height history is a per-mode overlay style, not a new surface
`_applySuggestOverlay` already branches on `_suggMode`. Keep one `#gd-sugg` element, but build the height style per mode: history gets `top:0;bottom:0` (fills the WebView, which is itself bounded above by the search row and below by the bottom dock), while suggestions keep the bounded `max-height`. **Why not a QML list:** a QML list cannot render above the native WebView, and the history entries already work as in-page `data-action="open-history"` anchors. **Alternative considered:** a separate full-pane QML history view — rejected, it would fork the history rendering and the tap dispatch.

### D2: Submission precedence lives in one place and suppresses the overlay
Route keyboard submission through a single helper: if `_suggMode === "sugg"` and `_suggWords` has a first entry that is not a `(no results...)` placeholder, look that word up; otherwise look up the literal typed text. Then set the pending-lookup guard (`_requestedWord`) and do **not** re-query suggestions for that query.

`onSuggestionsReady` and `_applySuggestOverlay` check a shared helper: the query in the box is "owned by an article" when the pending lookup word (`_requestedWord`) equals it **or** an article is already rendered whose word (`currentWord`) equals it. The second condition is required because `onArticleLoaded` clears `_requestedWord` *before* the article is shown, so a pending-word-only guard would stop suppressing exactly when a late suggestion reply lands after the article paints — which is the bug being fixed. `onArticleNotFound` clears `_requestedWord` too (with the same stale-reply guard as `onArticleLoaded`), so a failed lookup still falls back to history per the existing spec.

**Why not always look up the literal text:** the spec previously said so, but a partial prefix with no exact headword then shows not-found while the engine already has the intended candidate. **Why not wait for `engine.suggest` to return on Enter:** it adds a round-trip and a new race; the top suggestion is already rendered in the dropdown the user is looking at.

### D3: The group switch must not re-arm suggestions on close
The picker's `onClicked` for the Search target already calls `engine.lookupInGroupWithSwitch`. The problem is `groupPicker.onClosed`, which unconditionally calls `_doSuggest()` when the field has text — so a fresh suggestion query is launched after the lookup and can land on top of the article. Fix: record that the picker selection started a lookup (a flag set in the picker's `onClicked`) and, in `onClosed`, skip the `_doSuggest()` re-query for that case; leave the surface as the pending history/suggestion state the article render will replace. The empty-field branch (`setActiveGroup` + `_showHistoryOverlay`) is unchanged.

### D4: One icon-button recipe, reused
Standard icon button = `Button` with `text: root.icon("<name>")`, `font.family: root.iconFontFamily`, `font.pixelSize` in the toolbar range, `highlighted` only for a primary/active state. Apply it to: the Search clipboard control (was `ToolButton`), the membership editor pencil (was `ToolButton`), and the Groups Add control (was a text `Button`). The `create_new_folder` glyph (U+E2CC) is already present in the bundled `app/res/fonts/MaterialIcons-Regular.ttf`, so it goes in the existing `icon()` map — no font subset/subset regeneration.

### D5: Group-scope buttons widen by changing the flex ratio
Both `searchGroupButton` and `ftsGroupButton` use `Layout.preferredWidth` against the field's `7`. Change the buttons from `3` to `3.9` (1.3×); the field stays `7`, so the field gets narrower by exactly the width the buttons gain. No fixed pixel widths, so it scales with the pane.

### D6: Membership-editor By Pair groups only the available list
The member list keeps `memberModel` and the drag reorder untouched — it is one ordered list (the article order), and grouping it would make pair headers repeat and "drag across pairs" ill-defined. The available list gets a flattened model of `{type: "header", pair}` / `{type: "dict", ...}` rows, mirroring the Dicts tab's by-pair model, rebuilt whenever `groupNonMembers` is set. The toggle is a plain `Button` driven by an external `groupsPane.byPair` boolean (same pattern as the Dicts toggle) with accessible name `By Pair`.

### D7: Reserve trailing space instead of overlaying the name
The trailing icon is already an overlay anchored to the delegate's right; the name content just needs right padding equal to the icon's width (the group row already does this with `rightPadding: 56`). Add matching right padding to the member row's content `RowLayout`/label and to the non-member row's `Label`, both already `elide: Text.ElideMiddle`. This keeps the icon tappable and the name clear of it at any width.

### D8: Dialog content width binds to the padded content area
The create/rename dialogs set `contentItem: ColumnLayout { width: parent.width }`. The popup positions the content item inside its padding, so binding it to the full popup width makes the column overhang the padding (visible with the longer Russian action labels). Bind the column to the popup's available content width (popup width minus horizontal padding), or drop the explicit width and let the content size to the popup. Keep the Material right-aligned action row. Verified on device in English and Russian.

### D9: FTS loses its submit button, keeps its triggers
Delete the `ftsSearchBtn` row. The three triggers the spec names already exist and call `_runFts()`: `ftsInput.onAccepted`, the whole-words `onClicked` (guarded by a non-empty field), and the picker's FTS branch. No extra debounce is added: the existing max-results cap bounds an unintended search, per the proposal.

## Risks / Trade-offs

- **Suppression could hide legitimate suggestions.** [Mitigation] The guard is keyed to a filled `_requestedWord` and is cleared on `onArticleNotFound`, so a failed lookup returns to the spec'd history/suggestion behavior.
- **Full-height history could hide the field or dock.** [Mitigation] The overlay lives inside the WebView, which is laid out below the search row and above the bottom dock, so it can only fill the WebView's own bounds.
- **Enter-on-top-suggestion opens an unexpected word.** [Mitigation] Only the engine's first suggestion is used, the same one shown first in the dropdown, and a `(no results...)` placeholder falls back to the literal text.
- **By-Pair available list can go stale after a membership change.** [Mitigation] Rebuild the grouped model in the same path that assigns `groupNonMembers`, which already refreshes on `onGroupMembersChanged`.
- **Widening the group buttons shrinks the field in a narrow/landscape layout.** [Mitigation] The ratio is relative and the field still fills the remainder; verify in landscape.
- **Dialog centering fix could regress the add dialog.** [Mitigation] Both dialogs share the same content structure; verify both in English and Russian.

## Migration Plan

No data, storage, or API migration. Pure QML behavior/layout change; rollback is reverting the QML edit. Update the AGENTS.md accessible-element table (remove the FTS Search button row; add the membership-editor By Pair control, keep `Add group` on the icon control) and the localization catalogs if the extraction changes.
