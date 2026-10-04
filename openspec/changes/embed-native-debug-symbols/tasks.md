## 1. Prove the packaging switch works before touching the pipeline

- [x] 1.1 Build a release bundle locally (`pwsh -File .\app\build.ps1 -Configuration Release -Bundle`) and print the AAB's top-level entries, to reproduce the missing `BUNDLE/native-debug-symbols/` from a clean state.
  Reproduced: top-level entries are `base`, `BUNDLE-METADATA`, `BundleConfig.pb`,
  `META-INF`, with no symbols anywhere in `BUNDLE-METADATA/` and
  `build/intermediates/native_symbol_tables/release/out/` empty.
- [x] 1.2 Capture the `:stripDebugDebugSymbols` output for that build. A debug build already reports `Unable to strip the following libraries, packaging them as they are: libaurelex_arm64-v8a.so`, which means the library currently reaches `base/` unstripped; confirm whether the release build behaves the same.
  The release build behaves the same, and the message lists **all 140** libraries,
  not just ours. `:extractReleaseNativeSymbolTables` *does* run (so the knob
  reaches the bundle task) but `:mergeReleaseNativeDebugMetadata` is `NO-SOURCE`.
- [x] 1.3 Determine which of the two candidate causes applies (design, Context): `debugSymbolLevel` not reaching the bundle task, or AGP's symbol extraction being broken by the unstripped pass-through. Evidence that separates them: with `debugSymbolLevel` already accepted by the DSL and no symbols entry produced, the knob is not the whole story — so check first whether stripping our library ourselves (making the input look like every other jniLib) changes anything.
  Neither of the two candidates: AGP could not find the NDK at all
  (`NdkLocator` looks only at `ndk.dir` and `<sdk>/ndk/<ndkVersion>`; ours is
  outside the SDK tree), so it had no `llvm-strip` (→ nothing stripped) and no
  `llvm-objcopy` (→ nothing extracted). Confirmed by pointing AGP at the NDK and
  watching both halves appear with no other change; the design's Context and D1
  are corrected accordingly.
- [x] 1.4 In `New-BaseBuildGradle` (`app/build.ps1`), apply the fix the evidence points at: the `jniLibs` symbol-retention setting from design D1, re-applied through the same patch path that survives `androiddeployqt` regenerating `build.gradle`.
  Applied the evidence's fix instead of the superseded D1:
  `android { ndkPath "<ndk root>" }` next to the existing
  `ndkVersion` / `ndk { debugSymbolLevel 'SYMBOL_TABLE' }`, emitted by
  `New-BaseBuildGradle` (with a `-NdkPath` parameter) *and* re-applied
  idempotently by the post-deploy patch, anchored on the `ndkVersion` line.
  `keepDebugSymbols` was rejected on the evidence: it tells the strip task to
  leave libraries alone, so it would have prevented the fix.
- [x] 1.5 Rebuild and confirm `BUNDLE/native-debug-symbols/arm64-v8a/` exists **and** that `base/lib/arm64-v8a/libaurelex_arm64-v8a.so` is stripped (`llvm-readelf -S` shows `.symtab` in the symbols copy only). Both halves matter: the symbols entry without a stripped shipped library is a download-size regression.
  Both halves hold. The symbols entry is at the path AGP 7.4.1 actually uses,
  `BUNDLE-METADATA/com.android.tools.build.debugsymbols/arm64-v8a/libaurelex_arm64-v8a.so.sym`
  (15,494,616 B, 44,902 symbols; there is no `BUNDLE/native-debug-symbols/`
  directory in an AGP 7.x bundle). `base/lib/arm64-v8a/libaurelex_arm64-v8a.so`
  went 36,279,360 → 9,442,232 B and `llvm-readelf -S` shows no `.symtab` /
  `.debug_*` there while the `.sym` copy has `.symtab`. AAB 47.5 → 42.1 MB,
  release APK 47.5 → 38.2 MB.
- [x] 1.6 If 1.5 fails, fall back per design D1: extract debug info with `llvm-objcopy --only-keep-debug` in the build script and zip it as the symbols archive. Record which path was taken.
  Not needed — **path taken: D1's `ndkPath`**, no build-script symbol extraction.
  The `llvm-objcopy --only-keep-debug` fallback stays documented as the escape
  hatch if a future AGP/NDK bump regresses it.

## 2. Verify in the release pipeline

- [x] 2.1 Add a step to `.github/workflows/release-qt.yml` that opens the built AAB and asserts `BUNDLE/native-debug-symbols/<abi>/` for every ABI in `qtTargetAbiList`, placed before the Play publish step and shaped like the existing vendored-OpenSSL packaging assertion.
  Added "Assert native debug symbols are in the release artifacts", between the
  vendored-TLS assertion and the artifact upload (so before the GitHub release
  and the Play publish). Same shape and the same `PACKAGED_ABIS` derivation as
  the TLS step; it asserts the real AGP path
  `BUNDLE-METADATA/com.android.tools.build.debugsymbols/<abi>/` and requires
  `libaurelex_<abi>.so.sym` specifically.
- [x] 2.2 Make a missing symbols entry fail the job, so a symbol-less AAB is never published.
  `throw` at the end of the step. Verified locally by running the step's script
  (extracted from the YAML) against a synthesized symbol-less AAB: exit 1 with
  `MISSING AAB symbols …`.
- [x] 2.3 In the same assertion, check that the shipped libraries in `base/` are stripped, so the unstripped pass-through AGP currently logs cannot reach users as a silent download-size regression.
  The same step extracts every `.so` under the AAB's `base/lib/<abi>/` and the
  APK's `lib/<abi>/` (~280 files, chunked 25 at a time) and runs `llvm-readelf -S`
  from the NDK over them, failing on any file that still has a `.symtab`. It
  also refuses to pass when readelf did not report a section table for every
  file, so a tool that silently did nothing cannot read as "all stripped".
  Verified against an APK carrying the unstripped library: exit 1 naming
  `lib\arm64-v8a\libaurelex_arm64-v8a.so`.
- [x] 2.4 Attach the per-ABI symbols archive to the GitHub release alongside the AAB and APK, named so the versionCode and ABI are unambiguous.
  "Package native debug symbols archive" assembles
  `aurelex-native-debug-symbols-<versionCode>-<abi>.zip` (contents
  `<abi>/<library>.so`, `unversioned` when there is no tag-derived versionCode)
  from the AAB, uploads it as the `aurelex-native-debug-symbols` workflow
  artifact, and adds it to the `Create GitHub release` step's `files`.
- [ ] 2.5 Confirm the workflow still publishes to internal testing on a throwaway tag, and that the failure path leaves the signed AAB/APK attached (the existing "publish failure does not lose the build" behavior).
  **Dry-run half done — run 37178228115** (`workflow_dispatch` on `914620d`, exit 0,
  signed with the release keystore). Everything except the Play step is now proven
  on the runner: `Wrote complete build.gradle (carve-subset fresh tree)` means CI
  took the `New-BaseBuildGradle` path and got `ndkPath` from the here-string;
  `:mergeReleaseNativeDebugMetadata` runs instead of `NO-SOURCE`; **`Unable to
  strip` appears 0 times in the whole run** (it was there before, for all 140
  libraries); the assertion printed `OK  AAB symbols
  BUNDLE-METADATA/com.android.tools.build.debugsymbols/arm64-v8a/ (2 file(s),
  15.8 MB)` and `all 254 shipped libraries are stripped`; the packaging step
  produced `aurelex-native-debug-symbols-unversioned-arm64-v8a.zip` and the
  `aurelex-native-debug-symbols` artifact was uploaded. Downloading that artifact
  confirms the release-asset format: `arm64-v8a/libaurelex_arm64-v8a.so` with
  44,195 symbols including `gd_scan_dicts`.

  Still open: the Play internal-testing publish itself, and that the release keeps
  its assets if it fails. Those need a real tag, which burns a versionCode on the
  Play listing (latest release v0.3.3 → 303, so the tag must encode higher).
  Structurally the behaviour is unchanged — `Create GitHub release` still precedes
  `Publish AAB to Play`, and the new assertions run before both — but that is
  reasoning, not a green run.

## 3. Document the manual Play step

- [x] 3.1 Add a section to `docs/SIGNING.md`: what the symbols are for, which file to upload, that the target is the Play Console's per-ABI native debug symbols upload, and that the Play Developer API has no native-symbols method so this step is deliberately manual.
  Corrected while writing it: the API *does* have one
  (`edits.deobfuscationfiles.upload` with `deobfuscationFileType=nativeCode`),
  but it is scoped to `apks/{apkVersionCode}`, an APK the edit uploaded, and
  this project publishes a bundle — so there is nothing to attach it to. The docs
  now state that, plus what Play does automatically (files included in a bundle
  by standard Gradle tasks are associated "without additional work"), and why the
  workflow assembles its own `.so`-named archive instead of using AGP's
  `.so.sym`-named `native-debug-symbols.zip`.
- [x] 3.2 Note in the same section that native symbols are crash-channel-agnostic (they make Play vitals symbolicate native crashes), so this is not a step toward adopting a crash-reporting SDK.
- [x] 3.3 Record the symbol archive's retention rule (keep at least as long as the Play listing can serve crash reports for that versionCode) so a future cleanup does not drop symbols Play still needs.

## 4. Close out

- [x] 4.1 Confirm `openspec validate embed-native-debug-symbols` passes and the delta reads correctly against `openspec/specs/distribution-and-polish/spec.md`.
- [x] 4.2 Note in `docs/TESTING.md` that native-crash symbolication is now verifiable per release (which ABI, which versionCode), so a future release that drops the symbols is caught by the assertion rather than by a maintainer noticing unreadable traces.
