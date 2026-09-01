# ROADMAP

Ordered feature backlog for the Aurelex Android dictionary app. Each item
flows through the normal OpenSpec change pipeline (propose → specs → design →
tasks) before implementation; this doc records intended order and priority
only. Source of truth for scope is the v1 design's cut-scope register
(`openspec/changes/archive/2026-08-31-goldendict-mobile-port/design.md`).

## In progress

- `distribution-and-polish`: signed CI releases (AAB + APK), versioning,
  signing strategy, app icon, onboarding + empty states.

## Done (shipped via archived changes)

- Lookup, dictionary management (mdict / DSL / StarDict), groups
- Multi-group management
- Full-text search (xapian re-enabled)
- Launcher shortcuts: Quick Settings tile + home-screen search widget
- History, favorites, text-to-speech, clipboard lookup
- Share-sheet / intent lookup and `ACTION_PROCESS_TEXT` selection lookup
- Dark mode for the article view (WebView reload on same-word HTML change;
  verified on-device)

## Priority queue (not yet proposed)

| # | Feature | Boundary/engine? | Notes |
| --- | --- | --- | --- |
| 1 | **Dictionary storage: sandbox folder by default, system-wide as explicit opt-in** | pure Kotlin (storage/SAF) | On Android 15 the system folder picker only lets an app use folders once the user grants "All files access" (Settings → All files access). Dictionary files can be arbitrary and live anywhere, so default to a **private sandbox** the user can reach (expose app storage via a FileProvider/DocumentsProvider `content://` URI so the Files app can copy dictionaries in, plus a "Scan sandbox" action). Optionally keep **system-wide file locations** as a user-granted setting that wakes the full folder picker. Model: sandbox = default & safe; full access = explicit, user-granted. |
| 2 | **Dark mode follows system setting** | pure Kotlin | Currently dark is only a manual in-app toggle. Make it default to / follow the system `isSystemInDarkTheme()`, keeping the manual override. |
| 3 | **Remove the persistent engine notification; keep it only during indexing** | Kotlin (service lifecycle) | **Problem:** the app always shows a foreground-service notification ("engine running") even when the user is just looking up words. The engine is a separate process (`EngineService` runs under `android:process=":engine"`) because the carve links real Qt 6 (`libQt6Gui`) and loading it into the Compose/WebView UI process previously broke HWUI rendering (blank UI — see commit `2b106f2`, and the "Do not shim Qt types" rule in AGENTS.md). That separation forces *some* host component (a Service) to own the engine's lifecycle, but it does **not** require a persistent notification. **Fix (recommended):** make `EngineService` a **bound** service (`BIND_AUTO_CREATE`) bound from the app/UI process, and only elevate it to a foreground service **during long-running work** — first dictionary scan/index and FTS index builds (`startForegroundService` + `startForeground()` at task start, `stopForeground()` at completion). Steady-state lookups then run with no notification; when the user backgrounds the app, Android may kill the engine process and the existing `MainViewModel.resumeScan` re-scans the staged folder on return (self-healing, though a large bundle re-inits). **Rejected alternatives:** (a) merging the engine into the UI/Application process via JNI to skip the Service entirely is **not viable as-is** — it reintroduces Qt-into-UI-process crashes and needs a carve/architecture design decision first; (b) coupling `bind`/`unbind` strictly to the Activity lifecycle would re-init the engine on every Home/Recents round-trip, which is worse for everyday use. |
| 4 | Translate-later / word-list export | pure Kotlin | Collect words, share/export a list. |
| 5 | Pre-built desktop-generated index caches | boundary (cache format) | Copy index caches along with dictionaries. |

## Parked (cut for v1, may return)

Remaining (b)-list items from the cut-scope register not yet queued above.
(a)-list items (tray, hotkeys, scan popup, print/PDF, desktop preferences
surface) are cut permanently on mobile.