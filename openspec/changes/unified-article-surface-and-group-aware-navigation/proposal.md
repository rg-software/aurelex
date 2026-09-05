## Why

Articles today open in two different surfaces: the Search tab's inline WebView (for search/suggestions) and a separately-created full-pane article WebView (for favorites, full-text search, and share/clipboard/deep links). Facing history and the in-article Back/Forward stack are also unaware of which dictionary group produced each article, so re-opening an item or navigating can silently use the wrong scope (or a group-per-item context is lost). The split surfaces make navigation state (back/forward, group) inconsistent.

## What Changes

- **BREAKING (A):** Retire the separate full-pane article view (`state === 2`, `articleLoader`). *Every* article — regardless of entry point (search, suggestions, history, favorites, FTS, share, clipboard, deep link) — opens in the Search tab's inline article and becomes part of the normal history/browser-style Back-Forward flow. No dedicated article screen exists.
- **BREAKING (B):** History and favorites entries persist the **dictionary group** that produced them (each entry = word + group id; legacy plain-string entries load as group "All" = 0). Opening a history/favorites item switches the active group to its stored one before the lookup; if that group no longer exists, fall back to "All".
- **(C)** The in-WebView **Back/Forward** navigation also restores the group: each stack entry stores the group the article was produced in, and returning/forwarding switches the active group back to that scope before re-rendering.
- **(D)** Selecting a group in the Search group picker re-runs the **candidate suggestions** for what's typed (or re-shows history when empty). It does **not** navigate/relookup any open article and does not touch history/favorites — the scope change only affects the ongoing search surface. (This fixes "switch group does nothing today": the picker sets the engine group but never re-runs suggestions.)
- A revision-log migration note: existing `history.json` / `favorites.json` (plain string arrays) load with group "All"; the JSON schema becomes an array of `{word, group}`.

## Capabilities

### New Capabilities

- none

### Modified Capabilities

- `lookup`: 1) the article is presented in the Search tab's inline surface from every entry point (no separate full-pane article); 2) in-article Back/Forward navigation restores the producing group; 3) a group-scope change re-runs headword suggestions (no re-lookup of the open article).
- `usability-utilities`: history/favorites entries are persisted with the producing group; opening one restores that group (falling back to "All" if deleted) before the lookup.
- `accessibility`: the full-pane article surface and its toolbar are removed; the accessible element inventory updates to the unified inline article + its Back/Forward/star controls.

## Impact

- `app/EngineController.cpp/.hpp` — history/favorites storage schema (`{word, group}`), loading/saving + legacy migration; expose entry group; a `lookupInGroup`-style path used by history/fav/back/forward that sets the active group then looks up.
- `app/main.qml` — remove `articlePane`/`articleLoader`/`state === 2` and the `_forwardFromArticle`/`_backFromArticle` full-pane branches; route favs/FTS/share/deep-link into the inline article; `navStack`/`fwdStack` entries carry `group`; group picker change re-runs `_doSuggest`.
- `docs/ROADMAP.md` — note the deferred "show group label on history/fav rows" idea as a candidate future milestone.
- No upstream `engine/` changes; pure Qt/QML + boundary JSON persistence.