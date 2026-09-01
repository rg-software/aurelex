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
- 🔵 **Full-text search (xapian)** — re-enable FTS in the carve: cross-compile
  xapian for Android, add `gd_fts_*` boundary calls, FTS UI. Highest
  power-user value; touches the merge contract (new dep + boundary API).
  In progress: OpenSpec change `full-text-search` — done through device
  verification (host smoke + APK build pass; on-device checks pending).
- ✅ **Quick-settings tile / home-screen widget** — instant lookup from the
  shelf.
  Done: OpenSpec change `quick-lookup-shortcuts` archived 2026-09-01
  (17/20 tasks; tile clipboard lookup and widget verified on Motorola
  ThinkPhone — active-group respect, rotation/rescale, and restart checks not
  run before archive).
- 🟢 **Pre-built desktop-generated index caches** — copy indexes along with
  dictionaries to skip on-device indexing.
- 🟢 **Translate-later / word-list export** — extract headwords/definitions to
  a file/anki.
- 🟢 **Distribution & polish** — signed release APK, GitHub releases + F-Droid
  metadata, app icon, onboarding/empty state.

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
