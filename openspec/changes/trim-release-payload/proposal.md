## Why

The release artifact ships the entire Qt kit rather than the subset the app can
reach: **140 native libraries totalling 86.32 MB**, of which **96 libraries /
37.97 MB (44%) are never loaded**. `docs/TESTING.md` records this as a known
limitation ("Release APK/AAB currently package every Qt kit library and plugin,
including debug/tooling binaries (`app/build.ps1` staging), rather than a filtered
set"), but nothing has been done about it and nothing measures it, so it cannot
regress visibly either.

The payload is already stripped — `embed-native-debug-symbols` fixed that with
`ndkPath` — so this is the remaining size problem, and it is a pure build-script
change with no engine, boundary, or product impact.

## What Changes

- Stage only the Qt libraries the app can actually reach, instead of copying the
  kit's whole `lib/`, `qml/**` and `plugins/**` trees.
- Apply the same filter to the QML module tree copied into `assets/qml/`, which
  today duplicates the module `.so` files a second time.
- Derive the kept set from the built artifact rather than maintaining it by hand,
  so a Qt upgrade cannot silently widen the payload.
- Extend the release pipeline's existing native-payload assertion (added by
  `embed-native-debug-symbols`, which checks every shipped library is stripped)
  with a total-size ceiling and a reachability guard.

- **Not in scope, explicitly:** stripping the shipped libraries, which already
  works; ABI splitting, which `qtTargetAbiList=arm64-v8a` already settles; and
  dropping `useLegacyPackaging`, which is a separate question about install-time
  extraction rather than payload contents.

## Capabilities

### New Capabilities

None. This change adds no user-facing capability.

### Modified Capabilities

- `distribution-and-polish`: the "Self-contained release builds" requirement
  gains a constraint that the packaged native payload contains only libraries the
  app can reach, that the QML module assets agree with that set, and that an
  unreachable library or an over-budget payload fails the build before
  publication.

## Impact

- `app/build.ps1` — the three wholesale `Copy-Item` calls that stage
  `$KitRoot/lib`, `$KitRoot/qml` and `$KitRoot/plugins` into
  `apk/libs/<abi>/`, and the `Copy-Item "$KitRoot/qml/*"` that stages the QML
  module tree into `apk/assets/qml/`. `Write-QtLibResources` derives
  `bundled_libs`/`qt_libs` from whatever it finds in `apk/libs/<abi>/`, so it
  follows the filter automatically, but it MUST keep mirroring exactly what ships
  — a mismatch there is the documented `Resources$NotFoundException` /
  "Can't create main activity" failure.
- `.github/workflows/release-qt.yml` — the native-payload assertion added by
  `embed-native-debug-symbols`.
- `docs/TESTING.md` — removes the known-limitation line this change retires, and
  gains on-device rows for the filter (the risk here is a QML module that fails
  to load at runtime, which nothing but a launch will reveal).
- No `carve/`, `patches/`, `engine/`, `app/*.cpp`, `app/*.qml`, or
  `app/CMakeLists.txt` change. The app's link line and its QML imports are the
  *inputs* to the filter and must not move.