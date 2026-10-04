## Why

The release AAB carries no native debug symbols, so Google Play cannot symbolicate a
native crash in any build we ship — and this app is mostly C++ (the carved
goldendict-ng engine runs in-process). Crash reports from Android vitals therefore
arrive as unsymbolicated addresses, which is the one thing that makes them useless
for diagnosis. The intent was already implemented once (`c1db358 feat(build): embed
native symbol tables in release AAB`) but does not work with the current toolchain,
and nothing verifies it.

The same build also logs `Unable to strip the following libraries, packaging them
as they are: …` — for every one of the 140 libraries it packages, not just ours
(Qt's arrive pre-stripped, so ours is the only one it shows up on) — so the
shipped engine library is ~36 MB unstripped instead of ~9 MB. Both halves of the
native-debug story — "symbols Play can use" and "libraries users download" — are
therefore unverified today, and the release pipeline asserts neither.

## What Changes

- Make the release AAB actually carry native debug symbols. The root cause is not
  the Gradle knob but the toolchain it needs: AGP runs `llvm-strip` /
  `llvm-objcopy` out of an NDK it locates itself, and it only looks inside the
  Android SDK (`<sdk>/ndk/<version>`), while our NDK is installed outside that
  tree. With no toolchain found, AGP strips nothing (it logs `Unable to strip the
  following libraries, packaging them as they are:` for every jniLib) and extracts
  no symbols, so the existing `ndk { debugSymbolLevel 'SYMBOL_TABLE' }` in
  `New-BaseBuildGradle` (`app/build.ps1`) has nothing to act on. Adding
  `android { ndkPath "<ndk root>" }` alongside it makes both halves work: the AAB
  gains `BUNDLE-METADATA/com.android.tools.build.debugsymbols/<abi>/*.so.sym`,
  and `base/` ships stripped libraries again.
- Verify it in the release pipeline: CI asserts, for every ABI the build ships,
  that the AAB carries that library's symbol table and that no library in the
  artifact was left unstripped, and fails the release when either is untrue, so a
  silently symbol-less AAB cannot be published again.
- Publish the symbols where a human can reach them: attach the per-ABI symbols
  archive to the GitHub release and document the manual Play Console upload as
  the fallback. Play associates symbol files included in a bundle by standard
  Gradle tasks automatically, so the release path itself needs no extra call; and
  the API's native-symbols method (`edits.deobfuscationfiles.upload` with
  `deobfuscationFileType=nativeCode`) is scoped to `apks/{apkVersionCode}` — an
  APK the edit uploaded — which a bundle-based release does not produce.
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

- `app/build.ps1` — `New-BaseBuildGradle` plus the idempotent `build.gradle`
  patch: add `ndkPath` next to the existing `ndkVersion` /
  `ndk { debugSymbolLevel 'SYMBOL_TABLE' }`, so the change survives the same
  re-application the existing gradle overrides do after `androiddeployqt`
  regenerates `build.gradle`.
- `.github/workflows/release-qt.yml` — an assertion over the built AAB's zip
  entries and the shipped libraries' ELF sections (same shape as the existing
  vendored-OpenSSL packaging assertion), plus assembling and attaching the
  per-ABI symbols archive.
- `docs/SIGNING.md`, `docs/TESTING.md` — the symbols-in-the-AAB guarantee and the
  manual Console upload recipe, with the reason it is manual; the local
  equivalent of the CI check.
- No `carve/`, `patches/`, `app/*.cpp` or engine change: this is purely about
  what the packaging step emits.