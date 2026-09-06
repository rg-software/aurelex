# Aurelex Roadmap

Working milestones for the mobile port of goldendict-ng. Implemented scope is in
`openspec/changes/archive/` (the archived changes) and the main specs under
`openspec/specs/`. This file tracks **candidate** next milestones so nothing is
lost; each is picked up through a new OpenSpec change (proposal → design →
specs → tasks) before implementation.

Status legend: 🟢 planned · 🔵 in progress · ✅ done · ⏸ parked

## Completed (baseline)

- ✅ Mobile MVP: search + article rendering + dictionary management (mdict/DSL/
  StarDict), separate-process engine, SAF scanning, dark mode, engine smoke CI.
  See `openspec/changes/archive/2026-08-31-goldendict-mobile-port/`.
- ✅ Everyday usability (utilities) — share-sheet / intent lookup, clipboard
  lookup, history, favorites, TTS, settings persistence. `everyday-usability-utilities`
  archived 2026-08-31 (14/14).
- ✅ Multi-group management — group CRUD + reorder via the boundary.
  `multi-group-management` archived 2026-09-01 (12/12).
- ✅ Full-text search (xapian) — FTS in the carve, `gd_fts_*` boundary calls,
  FTS UI. Prefix matching (`read*`), auto index build, active-group scoping
  verified on-device. `full-text-search` archived 2026-09-01. Wildcard
  expansion is handled by `patches/0003-fts-wildcards-expansion-cap.patch`
  (upstream caps at 1 term → raised to 100), applied and verified on-device.
- ✅ Quick-settings tile / home-screen widget. `quick-lookup-shortcuts` archived
  2026-09-01 (17/20; tile clipboard lookup + widget verified on-device).
  ⚠️ The widget is a styled shortcut, not a search field (RemoteViews cannot
  capture typed text); tapping it opens the search screen.
- ✅ Distribution & polish — signed release APK, GitHub/F-Droid, app icon,
  onboarding/empty state. `distribution-and-polish` + `release-qt.yml` CI.
- ✅ Dark mode — manual toggle + follows-system (JNI system-dark read),
  Material palette. `qt-material-ui` archived (code done; the on-device
  dark/light re-palette task 3.4 was not re-run before archive).
- ✅ Folder-scoped storage — SAF folder picker, one-off import model, recursive
  scan, staged private copies, no All-Files-Access, intersecting-source dedup.
  `folder-scoped-storage`, archived 2026-09-03 (24/25; 5.5 partial); the
  sources/Rescan model was later replaced by one-off import (`one-off-dictionary-import`).

## In progress (not yet archived)

- 🔵 **Bulk FTS indexing background service** (`bulk-fts-indexing`, 6/11
  done): auto-index-missing on scan + dropping the per-dict Index button are
  done; remaining: the foreground `IndexingService` (3.1–3.3) so a long build
  survives backgrounding, and the on-device verification pass (4.1–4.4).

## Recently completed

- ✅ **Search history in the candidate surface + browser-style article
  navigation** (`search-history-and-article-nav`, archived 2026-09-06): the
  History tab was abolished (history shows in the empty/fallback Search
  surface), in-WebView Back/Forward with a forward (redo) stack, and the
  frameless right-justified article header. Main specs synced.

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

## Cut permanently (no future plans)

See the v1 design's cut-scope register (`(a) No sense on mobile`): system tray,
global hotkeys, scan/hover popup, mouse gestures, external-program integration,
print/PDF, full desktop preferences surface.

## How to pick the next milestone

1. Open a new OpenSpec change (`openspec new change <name>`).
2. Draft proposal → design → specs → tasks (default `spec-driven` schema).
3. Implement via the OpenSpec apply workflow.
4. Verify on-device, archive, then update this file.

Engine-touching milestones (FTS wildcard patch, pre-built index caches) go
through the patch pipeline (`patches/` + CI smoke); pure-QML milestones
(word-list export, widget clipboard) do not.