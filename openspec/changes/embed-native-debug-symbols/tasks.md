## 1. Prove the packaging switch works before touching the pipeline

- [ ] 1.1 Build a release bundle locally (`pwsh -File .\app\build.ps1 -Configuration Release -Bundle`) and print the AAB's top-level entries, to reproduce the missing `BUNDLE/native-debug-symbols/` from a clean state.
- [ ] 1.2 Capture the `:stripDebugDebugSymbols` output for that build. A debug build already reports `Unable to strip the following libraries, packaging them as they are: libaurelex_arm64-v8a.so`, which means the library currently reaches `base/` unstripped; confirm whether the release build behaves the same.
- [ ] 1.3 Determine which of the two candidate causes applies (design, Context): `debugSymbolLevel` not reaching the bundle task, or AGP's symbol extraction being broken by the unstripped pass-through. Evidence that separates them: with `debugSymbolLevel` already accepted by the DSL and no symbols entry produced, the knob is not the whole story — so check first whether stripping our library ourselves (making the input look like every other jniLib) changes anything.
- [ ] 1.4 In `New-BaseBuildGradle` (`app/build.ps1`), apply the fix the evidence points at: the `jniLibs` symbol-retention setting from design D1, re-applied through the same patch path that survives `androiddeployqt` regenerating `build.gradle`.
- [ ] 1.5 Rebuild and confirm `BUNDLE/native-debug-symbols/arm64-v8a/` exists **and** that `base/lib/arm64-v8a/libaurelex_arm64-v8a.so` is stripped (`llvm-readelf -S` shows `.symtab` in the symbols copy only). Both halves matter: the symbols entry without a stripped shipped library is a download-size regression.
- [ ] 1.6 If 1.5 fails, fall back per design D1: extract debug info with `llvm-objcopy --only-keep-debug` in the build script and zip it as the symbols archive. Record which path was taken.

## 2. Verify in the release pipeline

- [ ] 2.1 Add a step to `.github/workflows/release-qt.yml` that opens the built AAB and asserts `BUNDLE/native-debug-symbols/<abi>/` for every ABI in `qtTargetAbiList`, placed before the Play publish step and shaped like the existing vendored-OpenSSL packaging assertion.
- [ ] 2.2 Make a missing symbols entry fail the job, so a symbol-less AAB is never published.
- [ ] 2.3 In the same assertion, check that the shipped libraries in `base/` are stripped, so the unstripped pass-through AGP currently logs cannot reach users as a silent download-size regression.
- [ ] 2.3 Attach the per-ABI symbols archive to the GitHub release alongside the AAB and APK, named so the versionCode and ABI are unambiguous.
- [ ] 2.4 Confirm the workflow still publishes to internal testing on a throwaway tag, and that the failure path leaves the signed AAB/APK attached (the existing "publish failure does not lose the build" behavior).

## 3. Document the manual Play step

- [ ] 3.1 Add a section to `docs/SIGNING.md`: what the symbols are for, which file to upload, that the target is the Play Console's per-ABI native debug symbols upload, and that the Play Developer API has no native-symbols method so this step is deliberately manual.
- [ ] 3.2 Note in the same section that native symbols are crash-channel-agnostic (they make Play vitals symbolicate native crashes), so this is not a step toward adopting a crash-reporting SDK.
- [ ] 3.3 Record the symbol archive's retention rule (keep at least as long as the Play listing can serve crash reports for that versionCode) so a future cleanup does not drop symbols Play still needs.

## 4. Close out

- [ ] 4.1 Confirm `openspec validate embed-native-debug-symbols` passes and the delta reads correctly against `openspec/specs/distribution-and-polish/spec.md`.
- [ ] 4.2 Note in `docs/TESTING.md` that native-crash symbolication is now verifiable per release (which ABI, which versionCode), so a future release that drops the symbols is caught by the assertion rather than by a maintainer noticing unreadable traces.