# Development

Everything a contributor (human or AI agent) needs to build, run, and extend
Aurelex. If you are a user, see the top-level `README.md` instead.

## Repo layout

- `engine/` — goldendict-ng submodule, pinned at a release tag, **never edited in place**.
- `patches/` — the only deviations from upstream (`.patch` files), applied by `scripts/apply-patches.*`.
- `carve/` — the `gd_*` C boundary (`goldendict.h`, `gd_boundary.cc`) + selected engine
  sources compiled once as an object library, shared by the Qt app and the CI smoke tool.
- `app/` — the Qt app (QML + WebView, Android) that consumes the carve in-process.
- `openspec/` — planning artifacts (proposals, specs, design, tasks); the design is the source
  of truth for scope.
- `docs/` — in-repo guidance: `TESTING.md`, `SIGNING.md`, `ROADMAP.md`, `UPSTREAM.md`.
- `scripts/` — `apply-patches.*`, fixture generators, build helpers.

## Working contract (read before changing anything)

The repository rules for agents and contributors live in `AGENTS.md`. Key rules:

- Never edit `engine/` in place. Deviations live in `patches/` or the boundary layer.
- Do not shim Qt types; the carve compiles with real Qt 6.
- The Qt app talks to the engine only through the `gd_*` C boundary.
- Work flows through OpenSpec changes first; implementation does not run ahead of the plan.

## Building the app

The app is a Qt Quick/WebView Android app built from `app/`.
Requirements: JDK 17, Android SDK + NDK r23c, Qt 6.6.3 android + desktop kits, vcpkg deps
(`zlib bzip2 liblzma lzo fmt xapian`), and **PowerShell 7 (`pwsh`)** — the script
uses PS7-only syntax and UTF-8 characters; running it under the legacy
`powershell` 5.1 misdecodes the UTF-8 and fails to parse. Apply the engine
patches first, then run the one-shot build script:

```powershell
pwsh -File .\app\build.ps1 -Configuration Release   # signed/shippable
```

**Iterative on-device flow.** For local device testing and debugging, use the
Debug build with install, so each edit is built, pushed, and launched in one
step:

```powershell
pwsh -File .\app\build.ps1 -Configuration Debug -Install
pwsh -File .\app\build.ps1 -Configuration Debug -SkipConfigure -Install   # skip cmake reconfigure on repeat runs
```

On a fresh tree the Debug path is self-contained: `build.ps1` packages the Qt
`res/values/libs.xml` (QtLoader resources) and writes a complete `build.gradle`
for non-Release configs, so `assembleDebug` works without extra setup.

`build.ps1` derives its toolchain from `AURELEX_*` env vars (or local defaults); pass `-Install`
to adb-install the result. A signed release APK is produced by the CI workflow
(`.github/workflows/release-qt.yml`) on `vX.Y.Z` tag pushes, using `AURELEX_KEYSTORE_*` secrets;
`versionName`/`versionCode` come from the tag. See `docs/SIGNING.md` for the Google Play /
F-Droid signing split.

## Engine smoke test

`carve/` builds a host smoke tool (`AURELEX_BUILD_SMOKE=ON`) exercised by
`.github/workflows/engine-smoke.yml` on every engine/patch/carve change: it scans a fixture
folder (including a nested-subfolder fixture, asserting recursion), looks up a known word, and
checks FTS + group/remove behavior. Any upstream bump must keep the smoke green.

## Upstream & maintenance

Upstream is pulled in as a Git submodule pinned to a release tag; only a small patch set
deviates, and the CI smoke verifies each upstream update. See `docs/UPSTREAM.md` for the pin,
update procedure, and patch-application details.

## OpenSpec workflow

Planning artifacts live in `openspec/`. Features/fixes flow through changes:

1. `openspec new change <name>`
2. Draft proposal → design → specs → tasks (default `spec-driven` schema).
3. Implement via the OpenSpec apply workflow.
4. Verify on-device, archive, then update `docs/ROADMAP.md`.

See `docs/ROADMAP.md` for the milestone tracker and cut register.

## Testing

Manual verification recipes live in `docs/TESTING.md` (build/install, lookup, article rendering,
audio, groups, FTS, history/favorites, storage, external entry points).