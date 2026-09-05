## Context

The app is a single `app/main.qml` Material/WebView UI. The Search pane renders its candidate surface (headword suggestions, and now lookup history) as an HTML overlay **inside** the article WebView — QML controls cannot stack above Android's native WebView surface, which is why suggestions already live in-page. Lookup history is provided by `EngineController` (`engine.history`, `engine.removeHistory`, `engine.clearHistory`, `historyChanged`), currently surfaced via a dedicated History tab with a Qt `ListView`. Article navigation today is a single back stack (`navStack`, array of `{word, html}`), no forward/redo. Two article toolbars exist: the inline one in the Search pane and the full-pane article view; both rely on `_backFromArticle()` for Back.

## Goals / Non-Goals

**Goals:**
- Generalize the in-WebView candidate surface to render lookup history when the search field is empty or a typed query yields no suggestions, without a dedicated History tab.
- Make article navigation browser-like (back + forward stacks, forward cleared by fresh lookups).
- Simplify the article header: Back/Forward/Star, frameless, right-justified, no caption.

**Non-Goals:**
- No change to history *semantics* (record/remove/clear/persist already work).
- No engine/C++ boundary changes; this is pure Qt/QML.
- No scroll-position preservation improvements for back/forward beyond today's behavior.
- Keeping a desktop-style History screen or keyboard media keys for forward/back.

## Decisions

### D1: History is another mode of the in-WebView candidate surface, not a Qt ListView

Reuse the existing suggestion-overlay machinery in `main.qml` (`_suggWords` / `_applySuggestOverlay` / `_flushPendingSugg` / `_blankPending` on `onLoadingChanged`). Introduce a surface mode:

- `sugg` — typing: render `engine.suggest` results (existing `#gd-sugg` HTML).
- `history` — input empty **or** suggestions empty: render a history overlay in the same container, most-recent-first, with per-row remove (`data-action="remove-history"`) and a "Clear all" row (`data-action="clear-history"`).

Rationale: history cannot be a QML layer stacked over the WebView (same native-surface constraint that drove suggestions in-page), and toggling WebView visibility to reveal a Qt list reopens the white-screen takeover bug. Keeping one overlay container means the `_blankPending`/load-settle re-apply machinery and the `articleLinkPoller` dispatch all stay unchanged. Alternative (Qt `ListView` replacing the WebView area when input is empty) was rejected for that native-surface risk.

Dispatch via the existing `articleLinkPoller`: new markers `HIST:` (lookup history word), `HISTDEL:` (remove item), `HISTCLEAR:` (clear all), alongside today's `SUGG:`. `engine.historyChanged` re-renders the history overlay when in `history` mode so removal/clear reflect immediately.

### D2: Browser-style back + forward stacks

Add a forward stack alongside `navStack` (both arrays of `{word, html}`):

- `_backFromArticle()`: capture current `{word, html}` → push onto `fwdStack`; pop `navStack` → render. If `navStack` is empty, return to search/clear as today and clear `fwdStack`.
- `_forwardFromArticle()` (new): capture current → push onto `navStack`; pop `fwdStack` → render. Disabled when `fwdStack` is empty.
- `_showArticle()` (all fresh lookups: typed, suggestion, history, favorites, in-article link): push previous onto `navStack` **and clear `fwdStack`** — any new lookup invalidates redo, like a browser.
- Back/forward bypass `_showArticle` (they set `currentWord`/`currentHtml` + `articleLoadTimer.restart()` directly), so the "fresh lookup clears forward" rule holds by construction.

Rationale: minimal delta over the current pop-and-render path; keeps history-avoidance (back/forward don't record into `engine.history` since they don't call `_showArticle`, matching browser semantics).

### D3: Article header — frameless, right-justified, Back/Forward/Star

Both toolbars (inline in Search; full-pane article view) render the same controls:
- Remove the caption `Label` (was `currentWord` / `"Dictionary article"`).
- Drop the toolbar `Rectangle`'s fill and border (transparent header).
- `RowLayout` right-justified: `layoutDirection: Qt.RightToLeft` (or an expanding spacer) so Back, Forward, Star group at the right edge.
- `Forward` enabled when `fwdStack.length > 0`; `Back` keeps today's behavior (disabled-state not required; tapping Back with no stack returns to suggestions, as today).
- New `access_forward` icon; keep colors/star logic unchanged. Accessible names: `"Back"`, `"Forward"`, `"Add to favorites"` / `"Remove from favorites"`.

### D4: Bottom bar loses History, five tabs

Remove the History entry from `navItems` and the `historyPane` block; the internal `state` values (0 search, 1 dicts, 2 article, 3 groups, 4 fts, 6 favorites) stay stable to avoid churn. Tab position is derived by scanning `navItems` for the tab whose `idx == state` via a small helper (`_tabIndexForState()`), used by `TabBar.currentIndex` and the top-bar title. `_navTo(5)` and the `state === 5` label branch are deleted. Onboarding copy that names the History tab is updated.

## Risks / Trade-offs

- **Overlay history limits gestures** — swipe-to-remove (the old Qt ListView pattern) isn't possible in the HTML overlay; per-row × buttons replace it. [Risk] slightly different UX than before → Mitigation: keep a "Clear all" affordance and large touch targets; confirm with the user that × is acceptable before archiving.
- **WebView-surface rules still apply** — any bug that briefly resets the WebView can drop the overlay; the existing `_blankPending`/flush machinery already self-heals on `onLoadingChanged`.
- **Forward re-render resets scroll** — like Back, Forward re-renders the article HTML and loses scroll position (existing behavior). [Risk] jarring for long articles → Mitigation: accept for now (explicit non-goal), can revisit with scroll restoration later.
- **State-mapping regression** — hand-editing `currentIndex`/title mappings is easy to get subtly wrong. [Risk] wrong tab highlight → Mitigation: drive both from the shared `_tabIndexForState()`/`navItems` scan, and keep the five `idx` values first-class in `navItems`.

## Migration Plan

Single-apk change; no data migration (history already persisted in-place). Rollback = revert the commit. Forward stack is in-memory only (does not persist across restarts), consistent with today's non-persistent back stack.

## Open Questions

None blocking. (Marginal: whether history rows should also appear in history mode when it equals the suggestion set — resolved by always preferring suggestions while typing.)