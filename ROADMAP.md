# Aurelex Roadmap

Working milestones for the mobile port of goldendict-ng. Implemented scope is in
`openspec/changes/archive/` (the archived v1 changes) and the main specs under
`openspec/specs/`. This file tracks **candidate** next milestones so nothing is
lost; each is picked up through a new OpenSpec change (proposal → design →
specs → tasks) before implementation.

Status legend: 🟢 planned · 🔵 in progress · ✅ done · ⏸ parked

## Completed (v1 baseline)

- ✅ Mobile MVP: search + article rendering + dictionary management (mdict/DSL/
  StarDict), separate-process engine, SAF scanning, dark mode, engine smoke CI.
  See `openspec/changes/archive/2026-08-31-goldendict-mobile-port/`.

## Next milestone (chosen)

- ✅ **Everyday usability (utilities)** — pure Kotlin, no engine changes:
  - Share-sheet / intent lookup ("Look up in Aurelex" from other apps)
  - Clipboard lookup shortcut
  - History / recent-lookups screen
  - Favorites (swipe-to-save)
  - Text-to-speech pronunciation
  - Settings persistence for the above + existing toggles
  - Rationale: high value per effort, low risk (no boundary/engine changes).
  - Done: OpenSpec change `everyday-usability-utilities` archived 2026-08-31
    (14/14 tasks, verified on Motorola ThinkPhone).

## Candidate future milestones

Set sourced from the design's cut-scope register (design.md "(b) Make sense on
mobile") plus later proposals.

- ✅ **Multi-group management** — engine already supports groups; expose group
  CRUD + reorder via the boundary, add a groups UI (v1 is single-group).
  Done: OpenSpec change `multi-group-management` archived 2026-09-01 (12/12
  tasks plus a post-review navigation/hang fix, verified on Motorola ThinkPhone).
- ✅ **Full-text search (xapian)** — re-enable FTS in the carve: cross-compile
  xapian for Android, add `gd_fts_*` boundary calls, FTS UI. Highest
  power-user value; touches the merge contract (new dep + boundary API).
  Done: OpenSpec change `full-text-search` — implemented through task 7.1,
  verified on Motorola ThinkPhone (prefix matching, auto index build, active
  group). Wildcard expansion needs patch 0003 (upstream caps at 1 term).
- ✅ **Quick-settings tile / home-screen widget** — instant lookup from the
  shelf.
  Done: OpenSpec change `quick-lookup-shortcuts` archived 2026-09-01
  (17/20 tasks; tile clipboard lookup and widget verified on Motorola
  ThinkPhone — active-group respect, rotation/rescale, and restart checks not
  run before archive).
  ⚠️ **Known limitation:** the widget is a styled shortcut, not a search field.
  RemoteViews cannot capture typed text (`EditText` crashes on many launchers),
  so tapping it sends `ACTION_SEARCH` with an empty word and just opens the
  search screen — functionally identical to opening the app icon. See
  `widget_search.xml` comment and design.md D2 (which envisioned an in-widget
  `EditText` that was dropped during implementation).
- 🟢 **Pre-built desktop-generated index caches** — copy indexes along with
  dictionaries to skip on-device indexing.
- 🟢 **Translate-later / word-list export** — extract headwords/definitions to
  a file/anki.
- 🟢 **Widget fills search with clipboard** — alternative to the widget-as-
  shortcut limitation above: tapping the widget copies the clipboard text into
  the in-app search field (or starts lookup directly), reusing the tile's
  clipboard-read path. Needs an on-device check that the clipboard read happens
  in the foreground activity (Android 10+), same as the tile.
- ✅ **Distribution & polish** — signed release APK (GitHub / F-Droid), GitHub
  releases, app icon, onboarding/empty state.
  Done: OpenSpec change `distribution-and-polish` (code) + `release-qt.yml` CI
  (tag-push signed APK) in the all-Qt port; the signed-release path is exercised
  by the `v*` tag push on the Qt app.

## Priority queue (not yet proposed)

| Priority | Feature | Boundary/engine? | Notes |
| --- | --- | --- | --- |
| 1 | Translate-later / word-list export | pure Kotlin | Collect words, share/export list |
| 2 | Pre-built desktop-generated index caches | boundary (cache format) | Copy index caches along with dictionaries |

## Parked (cut for v1, may return)

Remaining (b)-list items from the v1 design's cut-scope register that are
deferred and not yet queued above. (a)-list items (tray, hotkeys, scan popup,
print/PDF, desktop preferences surface) are cut permanently on mobile.

## Cut permanently (no future plans)

See design.md "(a) No sense on mobile": system tray, global hotkeys, scan/hover
popup, mouse gestures, external-program integration, print/PDF, full desktop
preferences surface.

## How to pick the next milestone

1. Open a new OpenSpec change (`openspec new change <name>`).
2. Draft proposal → design → specs → tasks (default `spec-driven` schema).
3. Implement via `openspec-instructions apply`.
4. Verify on-device, archive, then update this file.

Engine-touching milestones (FTS, groups) go through the patch pipeline
(`patches/` + CI smoke); pure-Kotlin milestones (utilities) do not.
