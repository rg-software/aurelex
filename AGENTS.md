# AGENTS.md — Working notes for AI agents and contributors

This file tells agents and contributors how to work in this repository safely. Read it before making changes.

## What this project is

Aurelex is an Android port of [goldendict-ng](https://github.com/xiaoyifang/goldendict-ng).
It reuses the upstream C++ dictionary engine (rendered via Android WebView) rather than reimplementing
dictionary formats. The app is a Qt Quick/WebView Android app (`app/`) that consumes
the carved engine in-process via the `gd_*` C boundary. Main is the shipping branch; the earlier
Kotlin/Compose UI was removed. Design is tracked with OpenSpec: the main specs live in
`openspec/specs/` and work-in-progress changes in `openspec/changes/` (see `docs/ROADMAP.md` for the
milestone tracker).

## Golden rules

1. **Never edit upstream engine code in place.** Upstream lives in the `engine/` Git submodule,
   pinned at a release *tag*. Any deviation from upstream must live in `patches/` or in the boundary
   layer outside `engine/`. Long-hand: the goal is that `git diff` between a bump and our tree stays
   tiny, and a CI smoke test catches breakage.
2. **Do not shim Qt types.** The carve compiles with real Qt 6 (Core/XML/Concurrent) for Android.
   Do not write `QString`/`QList`/`QXmlStreamReader` reimplementations on std:: — that would make
   every upstream merge expensive. Reconsidering this is a design decision (see design.md D1), not
   something an agent may do to make a build pass. (D1 lives in the archived goldendict-mobile-port
   design under `openspec/changes/archive/`.)
3. **The boundary is the C API.** The Qt app talks to the engine only through the `gd_*` C boundary
   (the core set in `carve/goldendict.h`, e.g. `gd_init`, `gd_scan_dicts`, `gd_lookup`, `gd_suggest`,
   `gd_get_resource`, `gd_get_audio`, `gd_cleanup`, plus the dict/group/FTS functions it has grown)
   plus whatever the boundary later grows to. New features either:
   - touch the boundary / carve → go through the patch pipeline (`patches/` + CI smoke), or
   - are pure UI/QML → can be added anytime without engine involvement.

## Repository layout (target)

- `engine/` — goldendict-ng submodule, pinned at a release tag, never edited.
- `patches/` — the only deviations from upstream (3 patches: dsl svg-drop, android home, fts wildcard cap). Keep it small.
- `carve/` — the `gd_*` C boundary (`goldendict.h`, `gd_boundary.cc`) + selected engine sources
  compiled once as an object library, shared by the Qt app and the CI smoke tool.
- `app/` — the Qt app (QML + WebView, Android) that consumes the carve in-process.
- `openspec/` — OpenSpec planning artifacts (the design is the source of truth for scope).

## Scope constraints

- **v1 formats:** mdict (`.mdx`/`.mdd`), DSL (`.dsl`/`.dsl.dz`), StarDict (`.ifo`). Other formats are
  converted on a computer (e.g. pyglossary) and copied to the phone.
- **Cut for v1:** network dictionary sources, Zim/EPWING/Aard/SLOB/BGL/SDict/GLS/XDXF natively,
  scan popup, system tray, global hotkeys, TTS, print/PDF. See the v1 design's cut-scope register
  (archived `goldendict-mobile-port` design under `openspec/changes/archive/`) and
  `docs/ROADMAP.md`.
- **Audio:** ogg/mp3/wav play; speex (`.spx`) is unsupported-but-graceful in v1.
- **Storage:** dictionaries are imported one-off via folder-scoped SAF pickers:
  supported files are stage-copied into app-private `files/staged/` and scanned
  recursively. There is no persistent "sources" list and no Rescan; removing a
  dictionary permanently deletes its staged copy and index. No `MANAGE_EXTERNAL_STORAGE`.

## OpenSpec commands

```bash
openspec list --json
openspec status --change <change-name> --json
openspec instructions <artifact-id> --change <change-name> --json
openspec validate <change-name>
```

The schema is `spec-driven`. Spec scenario/requirement format is strict (4-hashtag scenarios,
SHALL/MUST language) — follow the instructions output before writing any artifact.

## Conventions

- Spec capability paths: kebab-case, flat layout (`dictionary-management`, `lookup`, ...).
- Before any upstream bump: build the engine, run the CI smoke test, and update specs only if
  observable behavior changed (never massage specs to fit a refactor).
- Work flows through OpenSpec changes first; implementation does not run ahead of the plan.
- **Localization:** English is the source language. If user-visible English text changes in Qt
  sources (`qsTr`/`tr` arguments) or in `app/android/res/values/strings.xml`, the other shipped
  languages (RU, JA) MUST be updated in the same change: run
  `scripts/update-translations.ps1`, translate the new catalog entries in `app/i18n/*.ts`, mirror
  the change in `values-ru/` + `values-ja/`, and recommit the compiled `app/i18n/*.qm`. Qt catalog
  entries are source-keyed: never edit `<source>` inside a `.ts` (edit the code, then re-extract),
  and changing English retires the old key so its translation must be re-entered per catalog.

## Accessible element IDs (for automated testing)

Every interactive QML element in `app/main.qml` has `Accessible.name` and `Accessible.role`
properties (see `openspec/changes/accessibility-annotations/`). These double as stable element
IDs for UIAutomator / Appium-based on-device testing — the Android accessibility tree exposes
them as `content-desc` (name) and `className` (role). Use the `Accessible.name` values to locate
elements in automated tests:

| Pane | Element | `Accessible.name` |
|------|---------|-------------------|
| Nav | TabBar | `"Main navigation"` |
| Nav | Search tab | `"Search"` |
| Nav | Dictionaries tab | `"Dictionaries"` |
| Nav | Groups tab | `"Groups"` |
| Nav | Full-text search tab | `"Full-text search"` |
| Nav | Favorites tab | `"Favorites"` |
| Nav | Dark-mode toggle | `"Light mode"` / `"Dark mode"` (dynamic); the last (6th) slot in the bottom dock |
| Top | Status strip | No interactive content — paints the edge-to-edge window's top chrome in the app background |
| Search | ComboBox | `"Search group scope"` |
| Search | TextField | `"Search dictionaries"` |
| Search | Clipboard button | `"Clipboard"` |
| Search | Suggestion dropdown | Rendered as an HTML `<a>` panel (`#gd-sugg`) *inside* the article WebView — QML controls can't stack above Android's native WebView surface. Each entry carries a `data-w` word and dispatches via the QML link poller (`engine.lookup`), so no page navigation happens; the panel collapses when the article loads. UIAutomator sees entries via the WebView's own DOM accessibility subtree (content-desc = the word). No separate Qt node. |
| Dicts | Add dict button | `"Add dictionaries"` |
| Dicts | By Pair toggle | `"By Pair"` |
| Dicts | Remove button | `"Remove"` |
| Dicts | Flat list | `"Dictionaries list"` |
| Dicts | Grouped list | `"Dictionaries list by pair"` |
| Dicts | Remove confirmation | `"Remove dictionary confirmation"` |
| Groups | New group input | `"New group name"` |
| Groups | Create button | `"Create"` |
| Groups | ListView | `"Groups list"` |
| Groups | Group row | Named `<group name>`; tapping the row opens the group's membership editor (no separate edit/pencil button in the list) |
| Groups | Delete | `"Delete"` (per-row trash icon, asks for confirmation) |
| Groups | Delete confirmation | `"Delete group confirmation"` (OK/Cancel) |
| Groups | Rename dialog | `"Rename group"` (`"New group name"` field inside) |
| Membership | Back button | `"Back"` |
| Membership | Rename group | `"Rename group"` (header button in the membership editor) |
| Membership | Members list | `"Group members"` |
| Membership | Reorder surface | Whole member row drags to reorder; drag anywhere on the row |
| Membership | Remove from group | `"Remove from group"` |
| Membership | Non-members list | `"Available dictionaries to add"` |
| Membership | Add to group | `"Add to group"` |
| Article | Back button | `"Back"` |
| Article | Forward button | `"Forward"` (enabled only when a backed-out article exists) |
| Article | Favorites star | `"Add to favorites"` / `"Remove from favorites"` (dynamic) |
| Article | Zoom out button | `"Zoom out"` (disabled at the 75% minimum) |
| Article | Zoom in button | `"Zoom in"` (disabled at the 250% maximum) |
| Article | WebView | `"Dictionary article"` (inline in the Search tab; no separate full-pane article surface) |
| FTS | TextField | `"Full-text search"` |
| FTS | Whole words checkbox | `"Whole words"` |
| FTS | Group combo | `"Full-text search group scope"` |
| FTS | Search button | `"Search"` |
| FTS | Results list | `"Full-text search results"` |
| History | Clear all | Rendered as a `data-action="clear-history"` row *inside* the article WebView when the search field is empty |
| History | Word rows | Rendered as `data-w` anchors (tap = lookup) with `data-action="remove-history"` per-row buttons in the WebView; no separate Qt list/tab |
| Favorites | ListView | `"Favorites"` |
| Favorites | Remove button | `"Remove"` (per-row X, no swipe gesture) |
| Onboarding | Dialog | `"Welcome"` |
| Onboarding | Get started | `"Get started"` |

## Git / Commit conventions

- **Remote / MCP**: this repo is hosted on **GitHub** — use the GitHub MCP server (and `gh`) for
  issues, PRs, and remote operations. Do NOT use the Gitea MCP server with this repository.
- Write conventional, structured commit messages so the release pipeline can group them into
  categories (it parses `feat:`/`fix:` prefixes):

- **Format**: Conventional Commits — use a type prefix such as `feat:`, `fix:`, `docs:`,
  `refactor:`, `chore:`. Use a scoped prefix (e.g. `feat(comics):`, `fix(sidebar):`) when a
  subsystem is affected.
- **Mood**: imperative mood in the subject line (e.g. prefer "Add feature" over "Added feature" /
  "Adding feature").
- **Length**: keep the first line under 72 characters.
- **Issue Link**: use `Fixes #<id>` for bug fixes, `Refs #<id>` otherwise. Skip the reference if
  the branch is not issue-based.
- **When to commit**: never commit unless asked.