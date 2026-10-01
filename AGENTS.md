# AGENTS.md — Working notes for AI agents and contributors

This file tells agents and contributors how to work in this repository safely. Read it before making changes.

## What this project is

Aurelex is an **independent** Android dictionary app built on the
[goldendict-ng](https://github.com/xiaoyifang/goldendict-ng) engine. It consumes that engine
verbatim at a pinned release tag (rendered via Android WebView) rather than reimplementing
dictionary formats. The app is a Qt Quick/WebView Android app (`app/`) that drives the carved
engine in-process via the `gd_*` C boundary. We are not a fork of goldendict-ng and do not
contribute back; see `docs/ENGINE.md`.

Design is tracked with OpenSpec: the main specs live in `openspec/specs/`, and completed work is
recorded in `openspec/changes/archive/` — that archive is the record, so read it before assuming
something is unbuilt. Work in progress lives in `openspec/changes/`; if it is empty, nothing is
open.

## Where to look first

- **Building, testing, running → [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).** Read it before
  touching the build; it lists every other doc and what each is for. The short version:

  ```powershell
  .\scripts\apply-patches.ps1                                 # patch the engine tree first
  pwsh -File .\app\build.ps1 -Configuration Debug -Install     # build, push, launch
  ```

- The pinned engine source and the patch set → `docs/ENGINE.md`.
- What has actually been verified on hardware → `docs/TESTING.md`.

## Golden rules

1. **Never edit the engine source in place.** The goldendict-ng engine lives in the `engine/` Git
   submodule, pinned at a release *tag*. Any deviation must live in `patches/` or in the boundary
   layer outside `engine/`. Long-hand: the goal is that `git diff` across a release bump stays
   tiny, and a CI smoke test catches breakage. See `docs/ENGINE.md`.
2. **Do not shim Qt types.** The carve compiles with real Qt 6 (Core/XML/Concurrent) for Android.
   Do not write `QString`/`QList`/`QXmlStreamReader` reimplementations on `std::` — that would make
   every engine release expensive. Reconsidering this is a design decision (see design.md D1), not
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
- `patches/` — the only deviations from the pinned source (4 patches: dsl svg-drop, android home,
  fts wildcard cap, fts sliced build). Keep it small; `docs/ENGINE.md` enumerates them.
- `carve/` — the `gd_*` C boundary (`goldendict.h`, `gd_boundary.cc`) + selected engine sources
  compiled once as an object library, shared by the Qt app and the CI smoke tool.
- `app/` — the Qt app (QML + WebView, Android) that consumes the carve in-process.
  `app/openssl/<abi>/` vendors the prebuilt OpenSSL 3 libs Qt's Android TLS needs
  (the Qt kit does not ship them), wired in via `QT_ANDROID_EXTRA_LIBS`. See
  `app/openssl/README.md` and design D12 of the remote-catalog change.
- `openspec/` — OpenSpec planning artifacts (the design is the source of truth for scope).

## Scope constraints

- **Supported formats:** mdict (`.mdx`/`.mdd`), DSL (`.dsl`/`.dsl.dz`), StarDict (`.ifo`). Other
  formats are converted on a computer (e.g. pyglossary) and copied to the phone.
- **Out of scope, permanently:** online *lookup* (network dictionary sources), Zim/EPWING/Aard/
  SLOB/BGL/SDict/GLS/XDXF natively, scan/hover popup, system tray, global hotkeys, mouse gestures,
  external-program integration, print/PDF, TTS, and a full desktop preferences surface. The remote
  *catalog* is in scope — it downloads a dictionary once, then searches it on-device; see
  `docs/REMOTE-CATALOG.md`. The original cut-scope register is in the archived `goldendict-mobile-port`
  design under `openspec/changes/archive/`.
- **Audio:** ogg/mp3/wav play; speex (`.spx`) is unsupported-but-graceful (skipped without an
  error).
- **Storage:** dictionaries are imported one-off via folder-scoped SAF pickers:
  supported dictionary files (`.mdx`/`.mdd`/`.dsl`/`.dsl.dz`/`.ifo`) are
  stage-copied into app-private `files/staged/` and scanned recursively, and any
  sibling `<dict>.files` resource tree (DSL sounds/images) is copied wholesale so
  pronunciation audio resolves. There is no persistent "sources" list and no Rescan; removing a
  dictionary permanently deletes its staged copy and index. No
  `MANAGE_EXTERNAL_STORAGE` and **no runtime storage permission is requested**:
  the picker is `ACTION_OPEN_DOCUMENT_TREE`, whose per-folder URI grant covers
  the copy (read via `ContentResolver`, not by path). Android refuses to grant
  the storage root / `Download` / `Android/data` (the picker shows "blocked");
  the user must pick a normal folder. If DocumentsUI on a test image gets stuck
  on a blocked root ("Nothing here"), a device reboot clears it.

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
- **`app/openssl/<abi>/*.so` are vendored binaries, not build output — keep them tracked.**
  The repo `.gitignore` has a blanket `*.so` rule for NDK/vcpkg artifacts with one scoped
  negation (`!app/openssl/**/*.so`) for this directory. Do not remove that negation and do not
  delete these files as build output. Qt's Android TLS is the OpenSSL backend and `dlopen()`s
  them at run time, so an artifact built without them has **no working TLS** — the remote
  dictionary catalog silently fails with "TLS initialization failed" while everything else
  looks fine, because the WebView brings its own TLS. The CMake configure step fails hard if
  they are missing, and the release workflow asserts they reached the packaged APK/AAB. Provenance
  (source commit, version, per-file digests) is recorded in `app/openssl/README.md`; an upgrade
  replaces the files and updates that table in the same commit.
- Before any engine release bump: build the engine, run the CI smoke test, and update specs only if
  observable behavior changed (never massage specs to fit a refactor).
- Work flows through OpenSpec changes first; implementation does not run ahead of the plan.
- **Shared article icons live on the app side, not in dictionaries.** Any icon Aurelex itself
  renders inside the article HTML (sense markers, badges, UI glyphs) MUST be shipped in
  `app/android/assets/icons/` and referenced through the static asset route — NOT emitted into a
  dictionary's resource bundle and fetched as `bres://`. The `bres://` path queues on the engine's
  reader slots and unzips the dictionary before answering, so such icons paint after the rest of
  the article and reflow it; the asset route answers immediately. The same asset is therefore
  **shared by every dictionary** (e.g. the kaikki `gd_tag_*.svg` set lives in both
  `scripts/assets/kaikki-tag-icons/` for the converter's preview output and
  `app/android/assets/icons/` for the app, with `EngineController::rewriteArticleUrls` mapping the
  four fixed names to `/icons/`). When adding an icon the engine emits into articles, add the
  asset to `app/android/assets/icons/` and a bounded rewrite (fixed names, not a wildcard) in
  `rewriteArticleUrls`; keep `bres://` for genuinely per-dictionary resources (images, audio).
  The rule is about **Aurelex's rendering path**, not about the artifact a producer emits: the
  converter still writes the `gd_tag_*.svg` set into each generated dictionary's `.files` bundle so
  the output stays self-contained for non-Aurelex consumers (GoldenDict desktop, the standalone
  preview HTML). That is deliberate, and it is not a counterexample — because the rewrite maps all
  four names, the app never fetches the bundled copies. Do not "fix" the converter to stop
  bundling them, and do not treat their presence in a bundle as a reason to skip the asset or the
  rewrite.
- **Localization:** English is the source language. If user-visible English text changes in Qt
  sources (`qsTr`/`tr` arguments) or in `app/android/res/values/strings.xml`, the other shipped
  languages (RU, JA) MUST be updated in the same change: run
  `scripts/update-translations.ps1`, translate the new catalog entries in `app/i18n/*.ts`, mirror
  the change in `values-ru/` + `values-ja/`, and recommit the compiled `app/i18n/*.qm`. Qt catalog
  entries are source-keyed: never edit `<source>` inside a `.ts` (edit the code, then re-extract),
  and changing English retires the old key so its translation must be re-entered per catalog.

## Accessible element IDs (for automated testing)

Every interactive QML element in `app/main.qml` has `Accessible.name` and `Accessible.role`
properties (see `openspec/changes/archive/2026-09-05-accessibility-annotations/`). These double as stable element
IDs for UIAutomator / Appium-based on-device testing — the Android accessibility tree exposes
them as `content-desc` (name) and `className` (role). Use the `Accessible.name` values to locate
elements in automated tests:

| Pane | Element | `Accessible.name` |
|------|---------|-------------------|
| Nav | TabBar | `"Main navigation"` |
| Nav | Search tab | `"Search"` (invariant English test ID; the visible label is localized) |
| Nav | Dictionaries tab | `"Dictionaries"` (label localized) |
| Nav | Groups tab | `"Groups"` (label localized) |
| Nav | Full-text search tab | `"Full-text search"` (label localized) |
| Nav | Favorites tab | `"Favorites"` (label localized) |
| Nav | Theme toggle | `"Dark mode"` / `"Light mode"` / `"Follow system theme"` (dynamic); a plain button that is a SIBLING of the TabBar (not a TabButton) in the last (6th) slot of the bottom dock — never becomes the active tab. Cycles Light → Dark → Follow-system → Light. The glyph AND the name both show the theme the **next tap** selects, not the current one (moon = "tap to go dark", sun = "tap to go light", auto glyph = "tap to hand control back to the system"), so no two modes look alike |
| Top | Status strip | No interactive content — paints the edge-to-edge window's top chrome in the app background |
| Search | Group button | `"Search group scope"` (shows the current group in the magenta accent scheme; always tappable — taps open the modal `Select group` picker, which has no "Groups" subtitle) |
| Search | TextField | `"Search dictionaries"` |
| Search | Clipboard button | `"Clipboard"` (magnifier-over-page glyph, primary accent styling; **disabled while the clipboard holds no usable text** — it is enabled only when the clipboard has non-whitespace text, and tracks clipboard changes live) |
| Search | Suggestion dropdown | Rendered as an HTML `<a>` panel (`#gd-sugg`) *inside* the article WebView — QML controls can't stack above Android's native WebView surface. Each entry carries a `data-w` word and dispatches via the QML link poller (`engine.lookup`), so no page navigation happens; the panel collapses when the article loads. UIAutomator sees entries via the WebView's own DOM accessibility subtree (content-desc = the word). No separate Qt node. |
| Dicts | Add dict button | `"Add"` (icon-only folder-open glyph; imports a dictionary folder) |
| Dicts | By Pair toggle | `"By Pair"` (translate glyph icon; highlighted when on) |
| Dicts | Delete button | `"Remove"` (icon-only trash glyph; deletes the current multi-selection; the only dict deletion path; gray when nothing selected, magenta when a selection exists) |
| Dicts | Failed-import remove | `"Remove failed import"` (per-row trash on the scan-failure banner; deletes the staged files of a dictionary that failed to load — such a dictionary is not in the list, so this is the only way to reach them) |
| Dicts | Flat list | `"Dictionaries list"` |
| Dicts | Grouped list | `"Dictionaries list by pair"` |
| Dicts | Pair header | Tapping a pair (section) header selects/unselects all dictionaries in that pair (shows a check when fully selected) |
| Catalog | Add from remote | `"Add from remote"` (cloud glyph button in the Dicts toolbar, next to Add; opens the full-page catalog pane — no new tab or dock slot; always active except while `processingActive`, so an unreachable catalog is reported by the pane, not by disabling the button) |
| Catalog | Pane title | Static label `"Dictionary catalog"`; the status line under it is not interactive |
| Catalog | Back | `"Back"` (header arrow; returns to the dictionary list) |
| Catalog | Re-probe | No button: opening the pane re-probes the catalog automatically |
| Catalog | Entry list | `"Remote catalog list"` (entries are `Accessible.ListItem` named `<entry name>`, plus `, installed` when installed; an entry whose required format this build cannot load is shown but not selectable) |
| Catalog | Audio toggle | `"Audio for <entry name>"` / `"No audio for <entry name>"` (per-row music-note / music-off glyph; audio is opted out per entry, enabled only when the row is selected or an installed entry is still missing its bundle) |
| Catalog | Free-space dialog | A modal `Dialog`; the OK/Cancel are the standard Material buttons (no custom `Accessible.name`) |
| Catalog | Download progress | A `ProgressBar` with `Accessible.role: ProgressBar`, plus a non-interactive line; no banner/buttons |
| Catalog | Download / cancel | `"Download selected"` (header icon; downloads the selected entries) and `"Cancel download"` (same button becomes an X while a batch runs) |
| Groups | Add button | `"Add group"` (icon-only `create_new_folder` button; opens the name dialog; on OK the group is created and its membership editor opens) |
| Groups | Add-group dialog | `"Add group"` (`"New group name"` field inside; OK/Cancel) |
| Groups | ListView | `"Groups list"` |
| Groups | Group row | Named `<group name>`; tapping the row opens the group's membership editor (no separate edit/pencil button in the list). The `All` row opens the same editor in reorder-only mode (no add/remove/rename): dragging sets the article order used by search |
| Groups | Delete | `"Delete"` (per-row trailing trash icon on non-`All` rows, asks for confirmation) |
| Groups | Delete confirmation | `"Delete group confirmation"` (OK/Cancel) |
| Groups | Rename dialog | `"Rename group"` (`"New group name"` field inside) |
| Membership | Back button | `"Back"` |
| Membership | Rename group | `"Rename group"` (header icon button in the membership editor) |
| Membership | By Pair | `"By Pair"` (header icon toggle; groups the available-to-add list by source/target language pair; hidden on the `All` group) |
| Membership | Members list | `"Group members"` |
| Membership | Reorder surface | Drag the member row's left-hand handle to reorder; the name area scrolls the list, and the trailing `Remove from group` sliver is excluded |
| Membership | Remove from group | `"Remove from group"` |
| Membership | Non-members list | `"Available dictionaries to add"` |
| Membership | Add to group | `"Add to group"` |
| Article | Back button | `"Back"` (disabled at the oldest article; navigates previous/next search results, never opens the suggestion dropdown) |
| Article | Forward button | `"Forward"` (enabled only when a backed-out article exists) |
| Article | Favorites star | `"Add to favorites"` / `"Remove from favorites"` (dynamic) |
| Article | Zoom out button | `"Zoom out"` (disabled at the 75% minimum) |
| Article | Zoom in button | `"Zoom in"` (disabled at the 250% maximum) |
| Article | WebView | `"Dictionary article"` (inline in the Search tab; no separate full-pane article surface) |
| Article | Optional-parts expander | Rendered by the engine as an HTML `<img class="hidden_expand_opt">` *inside* the article WebView, with `alt="[+]"` when the dictionary's `[*]…[/opt]` hidden zone is collapsed and `alt="[-]"` when it is revealed (the `alt` text is the state flag and the icon swaps with it; `assets/scripts/gd-article-controls.js` implements the handler). UIAutomator sees it through the WebView's DOM accessibility subtree as `content-desc = "[+]"` / `"[-]"` — address it by that. Only present for headwords whose entry has a hidden zone. |
| FTS | TextField | `"Full-text search"` |
| FTS | Whole words toggle | `"Whole words"` (Material Symbols "match word" glyph; magenta-filled when on, gray when off) |
| FTS | Group button | `"Full-text search group scope"` (shows the current group in the magenta accent scheme; always tappable; sits inline next to the field, like Search; opens the same modal `Select group` picker) |
| FTS | Search button | `"Search"` (magnifier icon button on its own row below the field; the only way to submit a search — typing, a scope change and the whole-words toggle do not search. Disabled while the query is blank and while a submitted search is running) |
| FTS | Results list | `"Full-text search results"` |
| History | Clear all | Rendered as a `data-action="clear-history"` row *inside* the article WebView when the search field is empty |
| History | Word rows | Rendered as `data-w` anchors (tap = lookup) with `data-action="remove-history"` per-row buttons in the WebView; no separate Qt list/tab |
| Favorites | ListView | `"Favorites"` |
| Favorites | Remove button | `"Remove"` (per-row X, no swipe gesture) |
| Onboarding | Dialog | `"Welcome"` |
| Onboarding | Get started | `"Get started"` |

## Git / Commit conventions

- **Remote**: this repo is hosted on **GitHub** — use the GitHub CLI for
  issues, PRs, and remote operations.
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
