## Why

The release AAB carries no native debug symbols, so Google Play cannot symbolicate a
native crash in any build we ship — and this app is mostly C++ (the carved
goldendict-ng engine runs in-process). Crash reports from Android vitals therefore
arrive as unsymbolicated addresses, which is the one thing that makes them useless
for diagnosis. The intent was already implemented once (`c1db358 feat(build): embed
native symbol tables in release AAB`) but does not work with the current toolchain,
and nothing verifies it.

## What Changes

- Make the release AAB actually carry `BUNDLE/native-debug-symbols/<abi>/`. The
  existing `ndk { debugSymbolLevel 'SYMBOL_TABLE' }` in `New-BaseBuildGradle`
  (`app/build.ps1`) is valid AGP 7.4.1 DSL and is accepted, yet the bundle task
  emits nothing; the replacement is the `jniLibs` packaging symbol-retention
  setting, which keeps the unstripped libraries for the symbols entry while
  `base/` still ships stripped ones.
- Verify it in the release pipeline: CI asserts that the built AAB contains
  `BUNDLE/native-debug-symbols/arm64-v8a/` and fails the release when it does
  not, so a silently symbol-less AAB cannot be published again.
- Publish the symbols where a human can reach them: attach the per-ABI symbols
  archive to the GitHub release and document the one manual Play Console upload.
  The Play Developer API v3 exposes no native-symbols method (its `edits`
  resources are `apks`, `bundles`, `countryavailability`, `deobfuscationfiles`,
  `details`, `expansionfiles`, `images`, `listings`, `testers`, `tracks`), so this
  step cannot be automated the way the AAB upload is.
- Record the symbol-retention setting, its verification and the upload recipe in
  `docs/SIGNING.md`, next to the existing Play publishing policy.

- **Not in scope, explicitly:** adding Firebase Crashlytics or any other
  crash-reporting SDK. Native symbols are a build artifact that feeds *whatever*
  channel reports crashes — with them, Android vitals symbolicates native crashes
  on its own, and a later Crashlytics adoption would consume the same symbols
  rather than replace them. Crash reporting itself stays on Play vitals, which is
  what the README and the privacy policy already describe.

## Capabilities

### New Capabilities

None. This change adds no new user-facing capability; it completes an existing
distribution requirement.

### Modified Capabilities

- `distribution-and-polish`: the signed-release-artifacts requirement gains
  native debug symbols in the release AAB, a CI assertion that they are present
  before publication, and a documented upload path to Play, so that a native
  crash reported through Play arrives symbolicated.

## Impact

- `app/build.ps1` — `New-BaseBuildGradle`: replace the ineffective
  `debugSymbolLevel` line with the packaging setting that retains symbols for the
  bundle. This is the file `androiddeployqt` regenerates, so the change must
  survive the same re-application the existing gradle overrides already do.
- `.github/workflows/release-qt.yml` — an assertion over the built AAB's zip
  entries (same shape as the existing vendored-OpenSSL packaging assertion), and
  attaching the symbols archive to the release.
- `docs/SIGNING.md` — the symbols-in-the-AAB guarantee and the manual Console
  upload recipe, with the reason it is manual.
- No `carve/`, `patches/`, `app/*.cpp` or engine change: this is purely about
  what the packaging step emits.