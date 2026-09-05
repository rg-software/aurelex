## 1. Engine: group-aware history/favorites persistence

- [ ] 1.1 Change `history.json`/`favorites.json` writers to emit `[{"word":"...","group":<id>}]`; readers accept both an object array and the legacy plain-string array (legacy entries → group 0/All).
- [ ] 1.2 Represent `engine.history`/`engine.favorites` to QML as `QVariantList` of `{word, group}` maps (keep a `historyWords()`/`favoritesWords()` convenience for row text where needed) and update the member storage + getters.
- [ ] 1.3 `recordHistory(word)` captures the current `activeGroupId`; `toggleFavorite(word)` likewise. Add per-entry removal: `removeHistoryEntry(word, group)` / `toggleFavoriteEntry(word, group)` used by the row X buttons, plus `clearHistory()` unchanged.
- [ ] 1.4 Save on change (historyChange/favoriteChange) with the new schema; confirm existing data migrates on next launch (no destructive read).

## 2. Engine: group-restoring lookup entry point

- [ ] 2.1 Add `lookupInGroupWithSwitch(word, groupId)`: if `groupId` exists in `engine.groups` call `setActiveGroup(groupId)` then `lookupInGroup(word, groupId)`, else `setActiveGroup(0)` + `lookup(word)` — used by history/favorites taps and Back/Forward group restore.
- [ ] 2.2 Ensure `activeGroupChanged` is emitted so QML can react (already exists) and the Search group picker's selected index tracks it.

## 3. QML: retire the full-pane article surface

- [ ] 3.1 Remove `articlePane`, `articleLoader`, `articleViewComponent`, the `view` property, and every `state === 2` branch (toolbar, `_loadArticleNow`, `onArticleLoaded`, accessibility).
- [ ] 3.2 `_showArticle` always routes inline: `inlineArticle = true`, `articleLoadTimer.restart()`; for lookups initiated outside Search (Favorites, FTS, share/deep-link/clipboard) first route to the Search tab then open inline (a `_routeToSearchForLookup` flag consumed by `_showArticle`).
- [ ] 3.3 Ensure the inline toolbar (Back/Forward/star, frameless, right-justified) is the only article header; remove the full-pane counterpart.
- [ ] 3.4 Update any nav-state mapping that referenced `state === 2` (TabBar `currentIndex`, top-bar label).

## 4. QML: group-aware navigation stacks + restore

- [ ] 4.1 `navStack`/`fwdStack` entries carry `group` (captured from `engine.activeGroupId` in `_showArticle`).
- [ ] 4.2 `_backFromArticle`/`_forwardFromArticle`: before rendering, restore the entry's group via `lookupInGroupWithSwitch` semantics (fallback to All if the group is gone), then show the article; continue to record neither history nor mutate the forward path improperly.
- [ ] 4.3 Fresh-lookup-clears-forward behavior retained (already in `_showArticle`).

## 5. QML: history/favorites UI uses group-aware entries

- [ ] 5.1 History overlay rows render from `engine.history` maps (`data-w` = word); the per-row X uses `removeHistoryEntry(word, group)`; "Clear all" unchanged.
- [ ] 5.2 Favorites list rows render from `engine.favorites` maps; tap opens with group restore (`lookupInGroupWithSwitch`); the per-row X uses `toggleFavoriteEntry(word, group)`.
- [ ] 5.3 Back-on-tap of a history/fav row restores the group first (fallback All).

## 6. QML: group picker re-runs candidates

- [ ] 6.1 After `setActiveGroup` in the picker's select handler, call `searchPane._doSuggest()` (typed query) or `_showHistoryOverlay()` (empty field). No re-lookup / no stack mutation.
- [ ] 6.2 Sync `searchGroupCombo.currentIndex` to the restored group after any group-aware navigation.

## 7. Verify + docs

- [ ] 7.1 Build (`pwsh -File .\app\build.ps1 -SkipConfigure`) + install; boot clean, no QML/JS errors.
- [ ] 7.2 Open an article from Favorites and from FTS: it renders in the Search inline article, joins back/forward history, and its group is restored on open.
- [ ] 7.3 Re-run a history item: group restored; a deleted group falls back to All; remove-per-entry removes the exact (word, group) row.
- [ ] 7.4 Back/Forward across articles in different groups restore each group; fresh lookup clears forward.
- [ ] 7.5 Group picker: changing the group re-runs suggestions (typed) or history (empty); open article is not re-looked-up; nav/top-bar state stays coherent (no `state===2`).
- [ ] 7.6 Legacy `history.json`/`favorites.json` (plain words) load as group All on first launch after upgrade.
- [ ] 7.7 Update `AGENTS.md` accessible-element table (remove `Article content` loader row; unify as inline); add ROADMAP note for the deferred "show group on history/fav rows" idea.