# ROADMAP

Ordered feature backlog for the v1 app. Each item flows through the normal
OpenSpec change pipeline (propose → specs → design → tasks) before
implementation; this doc records intended order and priority only.

Source of truth for scope remains the v1 design's cut-scope register
(`openspec/changes/archive/2026-08-31-goldendict-mobile-port/design.md`).

## In progress

- `distribution-and-polish` — signed CI releases (AAB + APK), versioning,
  signing strategy, app icon, onboarding + empty states. Remaining: on-device
  verification (5.2) and CI release artifact verification (5.3).

## Done (from the original (b) cut-scope register)

Items that no longer need proposing — shipped via archived changes and live in
main specs + code:

| Feature | Change | Notes |
| --- | --- | --- |
| History / recent lookups | `everyday-usability-utilities` | Persisted, dedupe+move-to-front, cap ~100 |
| Dark mode for the article view | `everyday-usability-utilities` | Persisted toggle, `setDarkMode` |
| Share-sheet / intent lookup | `everyday-usability-utilities` | `ACTION_SEND` + `onNewIntent` |
| Clipboard lookup | `everyday-usability-utilities` | Search-screen action |
| Favorites | `everyday-usability-utilities` | Swipe/save + list |
| Text-to-speech | `everyday-usability-utilities` | Graceful, on-device |
| Multi-group management | `multi-group-management` | |
| Launcher shortcuts / widget | `quick-lookup-shortcuts` | Tile + search widget |
| Full-text search | `full-text-search` | xapian re-enabled |

## Priority queue (not yet proposed)

| Priority | Feature | Boundary/engine? | Notes |
| --- | --- | --- | --- |
| 1 | Translate-later / word-list export | pure Kotlin | Collect words, share/export list |
| 2 | Pre-built desktop-generated index caches | boundary (cache format) | Copy index caches along with dictionaries |

## Parked (cut for v1, may return)

Remaining (b)-list items that were deferred and are not yet queued above.
(a)-list items (tray, hotkeys, scan popup, print/PDF, desktop preferences
surface) are cut permanently on mobile.