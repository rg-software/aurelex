# Aurelex Roadmap

Working milestones for the mobile port of goldendict-ng. Implemented scope is in
`openspec/changes/archive/` (the archived changes) and the main specs under
`openspec/specs/`. This file tracks **candidate** next milestones so nothing is
lost; each is picked up through a new OpenSpec change (proposal → design →
specs → tasks) before implementation.

**The archive is the record; this file is the pointer.** 51 changes are archived
under `openspec/changes/archive/`, and only a handful of them represent a
shipped capability worth naming here. Bug fixes that changed no observable
behaviour are not listed — read the archive for those.

Status legend: 🟢 planned · 🔵 in progress · ✅ done · ⏸ parked

## In progress (not yet archived)

*None.* `openspec/changes/` holds no open change; `openspec list` returns
nothing. If you are starting work, open one — see "How to pick the next
milestone" below.

## Completed

### Foundation

- ✅ Mobile MVP: search + article rendering + dictionary management (mdict/DSL/
  StarDict), in-process carved engine, SAF folder-scoped import, dark mode,
  engine smoke CI. `2026-08-31-goldendict-mobile-port`.
- ✅ Qt Quick/WebView UI for the whole app, replacing the earlier frontend.
  `2026-08-31-engine-architecture-revision` → `2026-09-02-qt-quick-frontend` →
  `2026-09-03-all-qt-ui-port`.
  ⚠️ `2026-09-02-confined-qt-shim` is an **abandoned** experiment archived with
  every task unchecked: it shimmed Qt types on `std::`, which `AGENTS.md` golden
  rule 2 now forbids. Its design doc is history, not a plan.
- ✅ Everyday usability: share-sheet / intent lookup, clipboard lookup, history,
  favorites, settings persistence. `2026-08-31-everyday-usability-utilities`
  (14/14). TTS was subsequently cut from v1 and is absent from the code; see
  `usability-utilities`.

### Dictionary management & formats

- ✅ One-off folder import (no persistent sources list, no Rescan), staged
  private copies, recursive scan, intersecting-source dedup, delete removes the
  staged copy and its index. `2026-09-03-folder-scoped-storage` (24/25) →
  `2026-09-04-one-off-dictionary-import` → `2026-09-01-remove-dictionary` →
  `2026-09-28-fix-dictionary-removal-cleanup` /
  `2026-09-29-fix-dictionary-removal-index-mismatch`.
- ✅ Dictzip `.dsl.dz` verified against a real file.
  `2026-08-31-dsl-dz-support`; the chunk-flush bug that surfaced it is
  `2026-09-28-fix-dictzip-chunk-full-flush`.
- ✅ Dictionaries list grouped by language pair, in place of raw file paths.
  `2026-09-04-dicts-tab-language-pairs`.
- ✅ DSL optional-parts (`[*]…[/opt]`) hidden zone with a `[+]`/`[-]` expander.
  `2026-09-28-dsl-optional-parts-toggle`.
- ✅ Remote dictionary catalog: install from a curated HTTPS-hosted manifest with
  no sideloading — foreground download service, byte-level progress/cancel,
  atomic staging, two-tier free-space preflight, and the existing scan →
  auto-index chain reused unchanged. `2026-09-29-remote-dictionary-catalog`
  (56/56). Manifest format and hosting: `docs/REMOTE-CATALOG.md`.
  ⚠️ Not end-to-end releasable yet — the compiled-in catalog URL is still a
  temporary self-hosted share (see `docs/REMOTE-CATALOG.md` § Hosting).
- ✅ Vendored Android OpenSSL so Qt's TLS works in a release build.
  `2026-09-30-vendor-android-openssl`. Without it the catalog fails with
  "TLS initialization failed" while everything else looks fine.

### Groups & full-text search

- ✅ Multi-group management — group CRUD + reorder via the boundary.
  `2026-09-01-multi-group-management` (12/12) →
  `2026-09-26-group-drag-reorder` → `2026-09-25-groups-tab-polish` (57/57).
- ✅ Full-text search (xapian) — FTS in the carve, `gd_fts_*` boundary calls,
  FTS UI, active-group scoping. `2026-09-01-full-text-search` →
  `2026-09-04-single-fts-batch-engine`.
  - Wildcard expansion: `patches/0003-fts-wildcards-expansion-cap` (upstream caps
    at 1 term → raised to 100).
  - Bulk indexing survives backgrounding; auto-index-missing on scan; the
    per-dict Index button is gone. `2026-09-03-bulk-fts-indexing`.
  - Builds interleave in bounded slices instead of holding the engine mutex for
    the whole run; periodic commits (resume after a kill), atomic-rename publish
    instead of a second `compact()`, cancel-and-reap on removal, and very large
    dictionaries deferred to the first search.
    `patches/0004-fts-sliced-build` + `2026-09-29-fts-indexing-performance`.
  - ⚠️ Indexes used to land *beside* the index directory because the path had no
    trailing separator. Fixed, with a startup sweep moving existing strays.
    `2026-09-28-fix-index-directory-path-separator` (23/23) — see its Migration
    Plan.

### Article surface

- ✅ History moved out of a tab into the empty Search surface, plus
  browser-style in-WebView back/forward with a forward stack.
  `2026-09-06-search-history-and-article-nav`.
- ✅ One article surface: the Search tab's inline WebView is the only article
  view, and navigation is group-aware (history/favorites rows carry a group-name
  line). `2026-09-06-unified-article-surface-and-group-aware-navigation`.
- ✅ Article zoom that **reflows** rather than scaling a fixed-width layout, at
  75–250% in 25% steps, persisted in `settings.json`.
  `2026-09-24-article-zoom-reflow`.
- ✅ Article server hardening: no GUI-thread hang on resources, and resource
  reads resolve off the GUI thread. `2026-09-26-fix-article-server-hang`,
  `2026-09-28-fix-article-server-gui-reentrancy` (covered by
  `article_server_test`).
- ✅ A round of hands-on UI fixes: search-field focus theft, the floating label
  overlapping the field border, icon-button styling, the recent-lookups list
  stopping short of the dock. `2026-10-01-ui-polish`,
  `2026-10-01-control-state-and-fts-whole-words`.

### Theme, accessibility, localization

- ✅ Material palette + dark mode. `2026-09-03-qt-material-ui`.
  ⚠️ Archived with task 3.4 (the on-device dark/light re-palette) not re-run.
- ✅ Tri-state theme control — Light → Dark → Follow system — where the glyph and
  the accessible name both show the theme the **next** tap selects.
  `2026-09-29-tri-state-theme-control`.
- ✅ The Android starting window follows the app theme instead of flashing white.
  `2026-09-30-system-splash-theme`.
- ✅ `Accessible.name`/`Accessible.role` on every interactive element, doubling
  as stable UIAutomator test IDs. `2026-09-05-accessibility-annotations`; the
  table lives in `AGENTS.md`.
- ✅ Russian + Japanese catalogs. `2026-09-25-localization` (27/29).
  ⚠️ Tasks 7.3/7.4 (on-device RU/JA verification) were deferred to release
  testing and are still open — see `docs/TESTING.md` #50–#55.
  `2026-09-28-fix-group-name-localization` fixed group names staying English.

### Distribution

- ✅ Signed release APK + AAB, GitHub/F-Droid, app icon, onboarding/empty state.
  `2026-09-03-distribution-and-polish` + `release-qt.yml`.
- ✅ Automatic upload to Google Play **internal testing** on a release tag.
  `2026-09-26-auto-publish-internal-track`. See `docs/SIGNING.md`.
- ✅ Quick-settings tile / home-screen widget. `2026-09-01-quick-lookup-shortcuts`
  (17/20).
  ⚠️ The widget is a styled shortcut, not a search field (RemoteViews cannot
  capture typed text); tapping it opens the search screen. Tile/widget
  active-group is inherited and unverified on device.

### Dictionary content tooling (kaikki.org)

Not user-facing, but the only way to get a large, well-formed dictionary into
the app. All of `docs/KAIKKI-CONVERSION.md`.

- ✅ `kaikki-to-dsl.py`: wiktextract JSONL → ABBYY Lingvo DSL, monolingual by
  design (the cross-language data does not support an honest bilingual
  dictionary — the measurements are in the doc). `2026-09-26-kaikki-to-dsl`.
- ✅ Article shape specified and implemented: merged parts of speech, sense
  grouping, numbered group headings, sense bullets, per-sense optional zones,
  the `gd_tag_*` sense-marker icons, forms/pronunciation policy.
  `2026-09-28-kaikki-sense-presentation`.
- ✅ Resumable audio prefetch with an explicit done/not-done verdict and exit
  status, worker shards for multi-machine back-fill, and `bundle-audio` to
  rebuild a failed resource bundle without re-rendering.
  `2026-09-29-kaikki-sharded-audio-prefetch`, `2026-09-30-audio-bundle-rebuild`.
- ✅ Build-quality passes: `--reuse-bundle` (re-render without redoing the audio
  archive), card blemish fixes, an archaic-quotation example fallback, and a
  doubled form-of link linked once instead of nested.
  `2026-09-30-build-reuse-bundle`, `2026-09-30-build-card-quality`,
  `2026-09-30-archaic-sense-example-fallback`,
  `2026-10-01-fix-doubled-form-link`.

## Candidate future milestones

- 🟢 **Translate-later / word-list export** — extract headwords/definitions to
  a file/anki. (Not yet proposed.)
- 🟢 **Pre-built desktop-generated index caches** — copy indexes along with
  dictionaries to skip on-device indexing. Boundary (cache format). (Not yet
  proposed.)
- 🟢 **Widget fills search with clipboard** — alternative to the widget-as-
  shortcut limitation: tapping the widget copies the clipboard text into the
  in-app search field (or starts lookup directly), reusing the tile's
  clipboard-read path. Needs an on-device check that the clipboard read happens
  in the foreground activity (Android 10+), same as the tile.
- 🟢 **Group label on history/favorites rows** — history and favorites rows now
  show a small group-name line (implemented in the unified-article-surface
  change). A possible follow-up: make the group name tappable (jump to that
  group, trigger search) in both surfaces.
- 🟢 **Close the open archived tasks** — `docs/TESTING.md` lists the untested
  items (RU/JA on device, `.mdd` images, tile/widget group scoping) and several
  archived changes still carry unchecked verification tasks. These are not new
  features, but they are the gap between "shipped" and "known to work".

## Cut permanently (no future plans)

See the v1 design's cut-scope register (`(a) No sense on mobile`) in
`openspec/changes/archive/2026-08-31-goldendict-mobile-port/`: system tray,
global hotkeys, scan/hover popup, mouse gestures, external-program integration,
print/PDF, full desktop preferences surface. TTS was cut later; see the
`usability-utilities` spec above.

## How to pick the next milestone

1. Open a new OpenSpec change (`openspec new change <name>`).
2. Draft proposal → design → specs → tasks (default `spec-driven` schema).
3. Implement via the OpenSpec apply workflow.
4. Verify on-device, archive, then update this file.

Engine-touching milestones (FTS wildcard patch, pre-built index caches) go
through the patch pipeline (`patches/` + CI smoke); pure-QML milestones
(word-list export, widget clipboard) do not.
