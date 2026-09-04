## Context

The app UI lives entirely in a single file: `app/main.qml` (1499 lines). It uses Qt Quick Controls 2 with Material Design 3 theming. There are ~63 interactive elements and ~10 informational elements that need accessibility annotations. Qt's accessibility bridge (`QtQuick.Accessibility`) is already available via the existing `import QtQuick` — no new imports are needed. The `Accessible.name` and `Accessible.role` properties are part of `QtQuick.Accessibility` which is included in the base `QtQuick` module.

## Goals / Non-Goals

**Goals:**
- Add `Accessible.name` and `Accessible.role` to every interactive QML element in `main.qml`
- Use dynamic bindings for state-dependent names (favorites star, dark-mode toggle)
- Cover informational elements (ProgressBar, error labels) with appropriate roles
- Keep annotations consistent: sentence-case names, roles matching Qt's `Accessible.role` enum

**Non-Goals:**
- Modifying the WebView's internal HTML content (upstream concern, out of scope)
- Adding accessibility to the Android Java layer (`widget_search.xml`, etc.) — a separate, smaller effort
- Creating automated UI tests (this change enables them, but does not create them)
- Adding accessibility to the `build.ps1`-generated Gradle files or AndroidManifest.xml

## Decisions

### 1. Single-file change: only `main.qml`

**Decision:** All annotations go in `app/main.qml`. No new files, no new QML components, no refactoring.

**Rationale:** The entire UI is one file. Splitting into components solely for accessibility would add structural complexity with no functional benefit. The annotations are additive properties, not behavioral changes.

**Alternative considered:** Extract interactive elements into reusable QML components with built-in accessibility. Rejected — the existing codebase has no component extraction pattern, and introducing one for accessibility alone would be over-engineering.

### 2. Use `Accessible.name` (not `Accessible.description`) for primary identification

**Decision:** Use `Accessible.name` as the primary identifier on all elements. Use `Accessible.description` only where additional context is needed (e.g., SwipeDelegate swipe hint).

**Rationale:** `Accessible.name` maps to `content-desc` in Android's accessibility tree, which is what UIAutomator uses for element discovery. `Accessible.description` provides supplementary info that TalkBack reads after the name. For most elements, the name alone suffices.

### 3. Dynamic bindings for state-dependent elements

**Decision:** Elements whose meaning changes with app state use QML bindings, not static strings.

Affected elements:
- **Favorites star** (line ~1085): `Accessible.name: engine.isFavorite(root.currentWord) ? "Remove from favorites" : "Add to favorites"`
- **Dark-mode toggle** (line ~213): `Accessible.name: engine.userDarkOverride || engine.systemDark ? "Light mode" : "Dark mode"`

**Rationale:** Static names would be misleading. TalkBack users need accurate information about what the action will do.

### 4. List delegates inherit accessible name from model data

**Decision:** `ItemDelegate` and `SwipeDelegate` inside `ListView` use `Accessible.name: modelData` (or the relevant model field like `modelData.name`, `word`, `headword`). The `Accessible.role` is `Accessible.ListItem` on every delegate.

**Rationale:** The delegate's text content IS its accessible name. Duplicating it in a static string would create maintenance burden and risk staleness.

### 5. No new QML imports required

**Decision:** Do not add `import QtQuick.Accessibility` — it's already part of `import QtQuick`.

**Rationale:** The `Accessible` attached type is part of the base `QtQuick` module since Qt 5.x. No import changes needed.

## Risks / Trade-offs

- **[Risk] Naming inconsistency across panes** → Mitigated by the catalog in this design doc serving as the source of truth. All names follow sentence case, 1–4 words.
- **[Risk] WebView content not accessible through Qt bridge** → Accepted. The WebView's internal HTML accessibility is an upstream concern. The QML-level annotation (`Accessible.role: Accessible.WebView`, `Accessible.name: "Dictionary article"`) gives TalkBack users awareness that a WebView is present, but not the article content itself.
- **[Trade-off] Static vs. dynamic names** → Dynamic bindings (favorites, dark mode) add minor QML complexity but provide accurate information. Worth it.
- **[Trade-off] completeness vs. speed** → The catalog covers 63 interactive + ~10 informational elements. Missing one would leave a gap for TalkBack users. The task list is ordered by pane to ensure completeness.

## Element Catalog (reference)

The complete catalog of elements, their suggested names, roles, and line numbers is documented in the task breakdown. Key groupings:

| Pane | Elements | Key names |
|------|----------|-----------|
| Navigation (TabBar) | 8 | "Main navigation", "Search", "Dictionaries", "Groups", "Full-text search", "History", "Favorites" |
| Top Bar | 2 | "Top toolbar", "Toggle dark mode" |
| Search | 5 | "Search group scope", "Search dictionaries", "Clipboard", "Search suggestions" |
| Dictionaries | 12 | "Add dictionaries", "By Pair", "Remove", "Dictionaries list", "Remove dictionary confirmation" |
| Groups (list) | 9 | "New group name", "Create", "Groups list", "Group options", "Rename", "Delete" |
| Groups (membership) | 9 | "Back", "Group members", "Move up", "Move down", "Remove from group", "Add to group" |
| Article | 4 | "Back", "Add/Remove from favorites", "Article content", "Dictionary article" |
| FTS | 6 | "Full-text search", "Whole words", "Full-text search group scope", "Search", "Full-text search results" |
| History | 4 | "Clear all", "Lookup history", "Delete" |
| Favorites | 3 | "Favorites", "Remove" |
| Onboarding | 2 | "Welcome", "Get started" |
