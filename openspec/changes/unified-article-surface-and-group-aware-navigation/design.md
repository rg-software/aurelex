## Context

Aurelex is a single `app/main.qml` (Material) app with one in-process engine boundary (`gd_*`). Articles render in a WebView whose HTML comes from `gd_lookup` and is rewritten by `EngineController::rewriteArticleUrls`. Two article surfaces exist today:

- **Inline** in the Search tab (`searchArticleView`), the only one that hosts the suggestion/history candidate overlay.
- **Full-pane** (`articlePane` / `articleLoader`, `state === 2`) used only by Favorites, FTS, and share/deep-link lookups, plus the full-pane Back/Forward articletopbar.

History/favorites are persisted as **plain string arrays** (`history.json`, `favorites.json`); the in-memory article `navStack`/`fwdStack` entries are `{word, html}`. Groups are managed through `engine.setActiveGroup` / `activeGroupId`, and lookups are scoped by the active group (stored key of the article cache is `word|activeGroupId`). The Search group picker is a modal dialog whose selection calls `setActiveGroup` but never re-runs suggestions.

See proposal.md for motivation and the accepted scope decisions (retire full-pane; group-per-item in history/fav/back/forward; group switch only re-runs candidates; legacy JSON → group All).

## Goals / Non-Goals

**Goals:**
- One article surface (Search inline). Every entry point routes there and integrates with the candidate overlay + browser-style back/forward.
- Persist producing group with each history/favorite; restore group (fallback All) on open.
- Back/Forward restore group per stack entry.
- Group picker re-runs suggestions (or history) after switching; no re-lookup/navigation of an open article.

**Non-Goals:**
- No upstream `engine/` edits; boundary surface unchanged (`gd_lookup`/`gd_lookup_in_group`/`gd_group_set_active` already exist).
- No UI label showing a history/favorite's group (deferred per decision; ROADMAP note).
- No swipe gestures; per-row X remove for history/fav rows stays.

## Decisions

### D1: Retire the full-pane article pane entirely
Remove `articlePane`, `articleLoader`, `view`, and the `state === 2` branches in `_showArticle`/`_backFromArticle`/`_forwardFromArticle`/toolbar. `_showArticle` always goes inline (`inlineArticle = true`, `articleLoadTimer.restart()`), i.e. `state` stays 0 while an article is open, and the inline toolbar (Back/Forward/star) is the only article header. Favorites/FTS/share/deep-link lookups switch to the Search tab first (`_navTo(0)` with preserved text) then open inline.
- Alternative rejected: keeping state 2 but routing into inline — that kept two code paths and a redundant pane. Full removal is the smaller correct surface.

### D2: Group-aware history/favorites persistence
Change `history.json`/`favorites.json` from `[ "word", ... ]` to an object array `[ {"word":"...", "group":<int>}, ... ]`. Loader: an element that is a string (legacy) OR missing `group` → `group = 0` (All). Setters keep the member as a `QStringList` for QML display plus preserve group in a parallel structure OR, cleaner, expose to QML as `QVariantList` of `{word, group}` and update the row renderers to read `.word` (rename `engine.history` → entries with `.word`; keep `engine.favorites` similarly). Getters stay: `history`/`favorites` become `QVariantList` of maps; a lightweight `historyWords()`/`favoritesWords()` (or `modelData.word`) for row text.

- `recordHistory(word, group)` captures `activeGroupId` at lookup time; `toggleFavorite(word, group)` likewise.
- Removing an item: pass the entry (match by word+group) → new `removeHistoryEntry(word, group)` / `toggleFavoriteEntry`, or preserve the simple-remove-by-word for history (history may have the same word in different groups — remove should target the exact entry). Decision: **remove matches word+group** (per-entry).

### D3: Group-aware in-memory navigation stacks
`navStack`/`fwdStack` entries become `{word, html, group}`. On push (`_showArticle`), capture `engine.activeGroupId`. On `_backFromArticle`/`_forwardFromArticle`, before rendering, apply the entry's group: if it exists (`engine.groups` contains id) call `engine.setActiveGroup(group)`; else `setActiveGroup(0)` (All). Re-render uses the existing `_showArticle`-free path (set `currentWord`/`currentHtml`, restart `articleLoadTimer`), matching the browser semantics (restore group then render; no history recording, forward cleared by fresh lookups as before).

FTS results already carry their group (lookup in a scoped group); when opening an FTS result the group is set to the FTS combo's selection first, then the lookup happens inline.

### D4: Group picker re-runs candidates only
On picker select: `engine.setActiveGroup(g.id)` then call `searchPane._doSuggest()` (re-suggests typed text) or `_showHistoryOverlay()` when empty. No `engine.lookup`, no stack mutation. This is what D in the spec describes and fixes the "nothing happens" today.

### D5: Share / clipboard / deep-link + Favorites tab still work
Even though the full-pane article is removed, these entry points must land on the Search tab inline article. Route: on `articleLoaded`, if the caller set a "route-to-search" context (fav tap, FTS result, share/deep link), switch `state=0` first then inline-render. Implementation: a small `_routeToSearchForLookup` flag consumed by `_showArticle`.

## Risks / Trade-offs

- **Inline-only reduces screen space for articles** (Search tab has the search row above). [Risk] less reading area vs the old full-pane → Mitigation: accepted by design; the inline band already works well, and removing the second WebView removes the native-surface duplication risk.
- **Persistence migration** — old JSON is a string array; the new loader must handle both. [Risk] misparse → Mitigation: strict type check per element; group defaults 0.
- **Same word in multiple groups in history** — removal and display must disambiguate. [Risk] removing the wrong entry → Mitigation: per-entry remove by (word, group); the row's X uses the entry object.
- **Group restore on navigation** requires an async `setActiveGroup` before lookup; the article cache is group-keyed so the re-lookup after restore remains fast. [Risk] slight delay on back/forward across groups → Mitigation: acceptable; cache avoids rework.

## Migration Plan

Single-APK; `history.json`/`favorites.json` re-read with legacy fallback on next launch (no write-migration run needed — the save path writes the new schema naturally on the next change). Rollback = revert + restore old JSON readers.

## Open Questions

None. (Group ordering/rename does not retro-apply to stored entries — entries keep the numeric group id; if a group is renamed the ids still match. Noted as acceptable.)