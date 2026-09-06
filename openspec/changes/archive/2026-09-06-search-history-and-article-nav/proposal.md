## Why

The bottom navigation carries a dedicated History tab, but history is small and contextual — it only makes sense while the user is about to look something up. The same goes for article paging: today users can only go *back* through previously opened articles, with no forward path and an empty "Dictionary article" caption that wastes header space. Both feel heavier than the rest of the app's fluid, in-surfaced design.

## What Changes

- **BREAKING** Remove the bottom "History" tab entirely; the bottom bar drops to five tabs (Search, Dicts, Groups, FTS, Favs) with matching state/index mapping and the top toolbar label ("History (N)") disappears.
- The Search pane surfaces lookup history **in place instead of a separate screen**:
  - When the search field is empty, the candidate surface shows recent lookups (most recent first) instead of suggestions.
  - As soon as the user types, the real suggestion list replaces history.
  - If a typed query produces no suggestions ("no results"), the surface reverts to history again.
  - History remains browsable/tappable (tap = lookup), removable per item, and clearable as a whole; it still persists across restarts. No engine/API change: the existing `engine.history` list is reused.
- **Article navigation becomes browser-like**: keep a back stack *and* a forward (redo) stack.
  - Back goes to the previous article (existing behavior).
  - New **Forward** control re-opens the article the user backed out of, when one exists. Any fresh lookup (typing, suggestion, history/favorites tap, in-article link) clears the forward stack, browser-style.
- Article header redesign (both the inline Search article and the full-pane article view):
  - Remove the "Dictionary article" / current-word caption label.
  - Show **Back, Forward, Star** controls right-justified.
  - Drop the filled/bordered frame so the icons sit directly on the pane background (transparent header, no border).
  - Forward and Back disable when their respective stack is empty; Star keeps its favorites toggle state.

## Capabilities

### New Capabilities

- none

### Modified Capabilities

- `lookup`: In-article link navigation becomes bidirectional (back + forward browser-style stacks); the empty search surface now falls back to history when a typed query matches nothing, and headword suggestions are the surface shown only while typing.
- `usability-utilities`: The lookup-history requirement changes where/how history is browsed (Search empty state instead of a dedicated History tab) while preserving record/browse/remove/clear/persist semantics.
- `accessibility`: The interactive surfaces change — the History tab and its Qt ListView are removed, and history (plus suggestions) render inside the article WebView as DOM-accessible nodes; the accessible element inventory must reflect the new Back/Forward/Star header and the Search empty-state list.

## Impact

- `app/main.qml` — primary surface: `navItems` (remove History, reindex), state/top-bar label mapping, remove `historyPane`, add empty-state history rendering in the Search candidate surface, browser-style back/forward stacks + `_forwardFromArticle`, and the two article toolbars (Back/Forward/Star, right-justified, frameless).
- `app/EngineController.*` — none expected; `engine.history`, `recordHistory`, `removeHistory`, `clearHistory` already cover the behavior. Verify only, no new boundary surface.
- `AGENTS.md` — accessible element ID table updated (History tab removed, Forward button, empty-state history list, revised labels).
- No upstream `engine/` changes; pure Qt/QML + assets.
- Onboarding help copy references the History tab ("switch between Search, Dictionaries, Groups, FTS, History and Favorites") and must be updated.