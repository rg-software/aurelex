## Why

The `qt-quick-frontend` experiment proved on-device (all three gates) that the
entire app can be one Qt process: the carved engine, a Qt Quick (QML) UI, and the
thin Java shell (QS tile) coexisting in a single pid — no `:engine` process, no
JNI/Messenger boundary, no foreground-service notification. This removes the
architecture's largest source of complexity (the client/server seam) and the
confusing "background running" indicator. This change executes the decision: port
the full v1 feature set from the Kotlin/Compose UI to Qt Quick, in slices, with
the Kotlin app "on pause" (no removal work) until the Qt app reaches parity and
replaces it completely.

## What Changes

- **Promote the experiment into the port vehicle.** `experiments/qtquick` grows
  into the real QML app (package `com.aurelex.experiment` during development);
  at parity, it replaces the shipped `app/` (package `aurelex.android`).
- **Sliced milestones (each lands testable on device):**
  1. Core lookup: search field + suggestions, article rendering via QtWebView,
     in-article links (`gdlookup://`), dictionary loading (sandbox staged dir).
  2. Dictionary management: add (sandbox folder scan), remove, reorder; dict info.
  3. Groups: create/rename/delete, membership editing, active group.
  4. Full-text search: index states, build, search modes, results → article.
  5. History + favorites (persisted, same SharedPreferences keys so user data
     survives the eventual swap).
  6. Onboarding + empty states; dark mode (manual toggle; system-follow is a
     follow-up roadmap change); share/clipboard/PROCESS_TEXT entry points.
  7. Java shell: QS tile, home-screen widget, SAF folder access for the opt-in
     storage mode; release packaging (signed APK) + CI.
- **Article bridge rework** (the known Gate-2 gap): serve engine resources in-process
  over a local HTTP loopback server (`bres://`, `gdau://`, `qrc:///` assets) so
  QtWebView can fetch everything without custom-scheme interception.
- **BREAKING (internal only):** the `:engine` process, `EngineService`/`EngineClient`
  Messenger IPC, and `jni_bridge.cc` become unused by the Qt app (they remain in
  the tree untouched while the Kotlin app is paused; removed at replacement time).

## Capabilities

### New Capabilities

None — `skip_specs`: the port targets **behavior parity** with the existing main
specs (`lookup`, `dictionary-management`, `usability-utilities`, `full-text-search`,
`launcher-shortcuts`); requirements do not change, only the UI stack. The roadmap
behavior changes (sandbox storage default, dark mode follows system) land as their
own follow-up changes against the QML app.

### Modified Capabilities

None.

## Impact

- `experiments/qtquick/` → grows into the full QML app (CMake, QML pages, C++
  controller classes exposing engine state to QML).
- New in-process article bridge (local loopback HTTP server + asset mirroring).
- Reuses unchanged: `engine/` carve, `gd_*` boundary, vcpkg deps, asset mirror
  (scripts/stylesheets/icons/flags), `PreferencesStore` key format.
- Untouched while paused: `app/` Kotlin UI, `EngineService`/`EngineClient`,
  `jni_bridge.cc`, `patches/`.
- CI (later milestone): release workflow builds the Qt app (Qt android kits +
  androiddeployqt + JDK 17), replaces the Kotlin `assembleRelease` path at swap.
- User data: history/favorites/settings SharedPreferences keys stay identical so
  the final package swap preserves them.