## Why

A round of hands-on use surfaced a set of small but visible UI problems: the recent-lookups list stops short of the bottom dock, icon controls are styled inconsistently across panes, long dictionary names collide with the trailing add/remove glyphs in the group editor, the rename dialog reads off-center in Russian, and a couple of interactions behave against the user's expectation (switching group with a typed query repaints the suggestion dropdown over the article instead of showing it, and Enter appears not to open an article). None of these is large, but together they make the app feel rough.

## What Changes

- **Recent lookups fill the pane**: the Search tab's history list (shown when the field is empty, or a query matches nothing) fills the whole inline article area down to the bottom dock instead of stopping at 72% height. The bottom dock stays visible; only the history view (not the suggestion dropdown) is enlarged.
- **Consistent icon button**: the Search tab's clipboard control uses the app's standard square icon button (the same `Button` + icon-font style as the Dicts toolbar trash / By Pair toggle) instead of the smaller `ToolButton`.
- **Wider group-scope buttons**: the Search and full-text-search group-name buttons are 1.3× wider, making the adjoining text field correspondingly narrower.
- **No glyph/name collision in the group editor**: long dictionary names in the membership editor elide in the middle and never run under the trailing add-to-group / remove-from-group icons.
- **Predictable Search submission**:
  - Switching the active group from the Search group picker while the field has text shows the article (an article lookup), never a stale suggestion dropdown painted over it.
  - Pressing Enter (the IME action) opens the top (most relevant) suggestion for the typed text; if there are no suggestions, it looks up the literal typed text.
  - A lookup in flight is not overwritten by a late-arriving suggestion response for the same query.
- **Centered group name dialog**: the create/rename group dialog's field and buttons are laid out so they stay centered for every label length, including the longer Russian strings.
- **Icon "Add group"**: the Groups toolbar's Add control becomes the standard icon button using the `create_new_folder` glyph (accessible name stays `Add group`).
- **Group editor control polish**: the header's rename (pencil) control uses the standard icon-button styling, and a `By Pair` toggle sits next to it. By Pair groups the **available-to-add** list under source/target pair captions (the same pairing as the Dicts tab); the member list is left as one flat, fully draggable order so article-order editing stays unambiguous.
- **FTS search has no dedicated button**: the full-text-search Search button is removed. The search runs on Enter, when the scope group changes, and when the Whole words toggle changes.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `lookup`: headword suggestion/submission behavior — Enter opens the top suggestion (falling back to the literal text), and switching group with a query shows the article rather than the suggestion list.
- `full-text-search`: how a full-text search is triggered — by Enter, a scope-group change, or the Whole words toggle, with no dedicated Search button.
- `dictionary-management`: group management UI — icon Add-group control, membership-editor icon controls, By Pair grouping of the available-to-add list, and long-name elision clear of the row icons; centered rename dialog.
- `usability-utilities`: the recent-lookups surface fills the Search pane's candidate area down to the bottom dock.

## Impact

- **QML only** (`app/main.qml`): Search candidate overlay (`_applySuggestOverlay` and the history branch), Search row, FTS pane, groups list and membership editor, group dialogs. No engine/`gd_*` boundary, carve, or patch changes.
- **Specs**: delta files for `lookup`, `full-text-search`, `dictionary-management`, `usability-utilities`. No new capability paths.
- **Accessibility / test IDs**: `Add group` keeps its invariant English accessible name; a new `By Pair` toggle in the membership editor uses the existing `By Pair` name. The AGENTS.md accessible-element table needs those two rows updated (FTS Search button row removed; membership editor gains By Pair).
- **Localization**: the removed FTS Search button retires one catalog entry; the icon-only Add control keeps its dialog title. No new translated strings (By Pair already exists). `app/i18n/*.qm` recommit if catalogs change.
- **No storage, permission, network, or dependency changes.**
