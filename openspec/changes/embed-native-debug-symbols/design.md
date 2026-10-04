## Context

See `proposal.md` — Why for the motivation. The facts that shape the approach,
all verified against the 2026-09-30 local release build and the tooling:

- `app/build.ps1`'s `New-BaseBuildGradle` emits, inside
  `buildTypes { release { … } }`:

  ```groovy
  release {
      minifyEnabled false
      ndk { debugSymbolLevel 'SYMBOL_TABLE' }
  }
  ```

  `debugSymbolLevel` exists on AGP 7.4.1's `NdkOptions`
  (`NdkOptions$DebugSymbolLevel` = `SYMBOL_TABLE` | `FULL` | `NONE`), and it does
  reach the bundle pipeline: `:extractReleaseNativeSymbolTables` runs. Yet the
  AAB's top-level entries are `base`, `BUNDLE-METADATA`, `BundleConfig.pb`,
  `META-INF`, with no symbols under `BUNDLE-METADATA/`, and no symbols artifact
  anywhere under `build/`.

- **The actual cause (verified 2026-10-04, supersedes the earlier reading that
  the knob itself was inert):** AGP runs its native toolchain — `llvm-strip` for
  `:stripReleaseDebugSymbols`, `llvm-objcopy` for
  `:extractReleaseNativeSymbolTables` — out of an NDK *it* locates, and
  `NdkLocator` (AGP 7.4.1) looks in exactly two places: `ndk.dir` in
  `local.properties`, and `<sdk>/ndk/<androidNdkVersion>`. Our NDK is installed
  outside the SDK tree (`C:\Program Files (x86)\Android\AndroidNDK\android-ndk-r23c`
  locally, `$GITHUB_WORKSPACE/ndk/android-ndk-r23c` in CI), so AGP found **no NDK
  at all**. Consequences, both observed in one build log:
  - `:stripReleaseDebugSymbols` logs `Unable to strip the following libraries,
    packaging them as they are: …` for **all 140** libraries, not just ours —
    ours is simply the only input that was not already stripped, because Qt's
    arrive stripped from `androiddeployqt`.
  - `:extractReleaseNativeSymbolTables` runs with an empty objcopy map, writes an
    empty output directory, and `:mergeReleaseNativeDebugMetadata` is `NO-SOURCE`
    — which is why the AAB carries no symbols even though the task ran.

  So this was never "the setting is accepted but ignored"; it was "the tool the
  setting needs was never found", and the build stayed green throughout.

- Where AGP 7.4.1 puts the symbols once it has a toolchain:
  `BUNDLE-METADATA/com.android.tools.build.debugsymbols/<abi>/<library>.so.sym`
  (the `.sym` is the input library with DWARF removed, `.symtab`/`.strtab`
  intact). There is no `BUNDLE/native-debug-symbols/` directory in an AGP 7.x
  bundle — that guess in an earlier draft of this change was simply wrong, and the
  CI assertion has to name the real path.

- The inputs would allow it. `build-qtquick/apk/libs/arm64-v8a/libaurelex_arm64-v8a.so`
  keeps `.symtab`, `.strtab` and `.debug_info` (it is unstripped); Qt's own
  libraries arrive already stripped from `androiddeployqt`, so they can
  contribute a symbols entry with little content but should not block one.

- Play associates deobfuscation and symbol files included in a bundle by standard
  Gradle tasks with the build automatically ("without additional work on your
  part"), so the symbols travel by riding inside the AAB. The Developer API v3
  does expose a native-symbols upload — `edits.deobfuscationfiles.upload` with
  `deobfuscationFileType=nativeCode` — but it is scoped to `apks/{apkVersionCode}`,
  i.e. an APK the edit uploaded, and this project publishes a bundle, so there is
  no such APK to attach to. Hence "published and documented": the AAB carries the
  symbols, and the Console upload stays a documented manual fallback.

- AGP is pinned at 7.4.1 with `compileSdk 36` worked around
  (`android.suppressUnsupportedCompileSdk`, an `aapt2FromMavenOverride` to
  build-tools 36), and `androiddeployqt` regenerates `build.gradle` and
  `gradle.properties` on every run, which is why the script re-applies its
  overrides after the deploy step.

## Goals / Non-Goals

**Goals:**

- The release AAB contains
  `BUNDLE-METADATA/com.android.tools.build.debugsymbols/arm64-v8a/` with the
  symbol tables of the libraries it ships.
- `base/` still ships stripped libraries, so the download size does not regress.
- A symbol-less AAB fails the release rather than shipping.
- The symbols reach a human who can upload them to Play, with the versionCode and
  ABI they belong to recorded.

**Non-Goals:**

- Automating the Console fallback upload. The API *has* a native-symbols method,
  but it attaches to an uploaded APK, which a bundle release does not produce; a
  script built on it would not work for this pipeline.
- Symbolication of *Java* crashes, which Play already handles, and of
  obfuscated code (the release build sets `minifyEnabled false`).
- Adding a crash-reporting SDK, or changing which crash channel is used.
- Making Qt's prebuilt libraries debuggable. They ship stripped from Qt's own
  build; recovering their symbols is a Qt-packaging project, not ours.

## Decisions

**D1 — Point AGP at the NDK with `ndkPath`, and keep
`ndk.debugSymbolLevel 'SYMBOL_TABLE'`.**

`android { ndkPath "<ndk root>" }` is what makes AGP find a toolchain; with it,
the *existing* `debugSymbolLevel 'SYMBOL_TABLE'` starts producing
`BUNDLE-METADATA/com.android.tools.build.debugsymbols/<abi>/*.so.sym` and
`stripReleaseDebugSymbols` starts stripping. One setting, both halves of the
requirement. `ndkPath` takes precedence over `ndkVersion`, works in AGP 7.4.1
(`BaseExtension.setNdkPath`), and emits no deprecation warning — unlike
`ndk.dir` in `local.properties`, which resolves the same NDK but logs
`CXX5106 … deprecated` once *per library* (~140 lines per build). Both spellings
were tried; the build log and AAB agree on `ndkPath`.

Measured on the local release bundle: `base/lib/arm64-v8a/libaurelex_arm64-v8a.so`
36,279,360 → 9,442,232 bytes (stripped; no `.symtab`, no `.debug_*`), AAB
47.5 MB → 42.1 MB, and the symbols entry appears with 44,902 symbols in the
`.sym` — i.e. the download shrinks *and* the crash reports become readable.

*Alternatives considered and rejected:*

- `packagingOptions { jniLibs { keepDebugSymbols '**/*.so' } }`. This was the
  original D1, on the assumption that `debugSymbolLevel` was inert. It only tells
  the strip task to leave a library alone, so under the real root cause it would
  have **prevented** the fix: it ships the unstripped library and extracts nothing.
- `doNotStrip`. Same objection, stated at the time: shipping the ~36 MB
  unstripped engine library inside the AAB for a maintainer-only benefit.
- Extracting the symbols in `build.ps1` with `llvm-objcopy --only-keep-debug` and
  injecting them into the AAB by hand. Kept as the documented fallback (task 1.6),
  unneeded: AGP does it correctly once it can find its tools, and a hand-built
  `BUNDLE-METADATA/` entry is a bundle format we would own.

**D2 — Assert on the built AAB's zip entries, in the same place as the existing
vendored-library check.**

`release-qt.yml` already asserts the vendored OpenSSL `.so`s reached the
packaged artifact. The symbols assertion is the same shape: open the AAB, look
for `BUNDLE-METADATA/com.android.tools.build.debugsymbols/<abi>/` (and for
`libaurelex_<abi>.so.sym` specifically — a symbols entry holding only
`libc++_shared` is worthless, every crash frame that matters is in the engine),
fail before the Play publish step. The same step walks every `.so` the AAB ships
under `base/lib/<abi>/` and every `.so` in the APK's `lib/<abi>/` through
`llvm-readelf -S` from the NDK and fails on any that still has a `.symtab`, so
the unstripped pass-through cannot reach users either. The assertion is on the
artifact, not on the Gradle flag, because the flag being present is exactly what
already failed silently.

*Alternative considered:* trusting the Gradle log. Rejected: log-scraping is
what let the original change look successful.

**D3 — Assert per shipped ABI, derived from the same ABI the build was invoked
with.**

The assertion reuses the workflow's existing `PACKAGED_ABIS` output, which the
artifacts step derives from the same `AURELEX_ABI` passed to `app/build.ps1`
(`arm64-v8a`, which mirrors `qtTargetAbiList=arm64-v8a`), so adding an ABI later
cannot silently skip the check.

**D4 — Publish the symbols as a release asset; do not attempt the Console
upload.**

The symbols archive — the AAB's
`BUNDLE-METADATA/com.android.tools.build.debugsymbols/<abi>/*.so.sym` entries,
renamed to `<lib>.so` and zipped as `<abi>/<lib>.so`, the layout Play's
per-ABI native debug symbols upload expects — is attached to the GitHub release
next to the AAB and APK, and `docs/SIGNING.md` gains the recipe: which file,
which versionCode, which ABI, and that the upload target is the Play Console's
per-ABI native debug symbols upload. Attaching it also means the symbols survive
independently of anyone's Play Console session.

**D5 — Leave the crash channel alone.**

Play vitals symbolicates native crashes from these uploaded symbols, so the
current channel becomes useful once they exist. Crashlytics would consume the
same symbols if it were ever adopted; symbols are not a step toward Crashlytics,
they are a prerequisite for *any* native-crash diagnosis.

## Risks / Trade-offs

- **AGP may not produce the symbols entry even with a toolchain.** → Task 1.1–1.5
  settled it the other way: with `ndkPath` set, both halves work on the first try
  (16.1 MB of `.sym` in the bundle, engine library stripped to 9.4 MB). The
  `llvm-objcopy --only-keep-debug` fallback in the build script stayed unused;
  it remains the documented escape hatch if a future AGP/NDK bump regresses it,
  and the spec does not change either way.
- **Silent regression is the real risk, not a red build.** Nothing about the
  missing NDK fails loudly — the build is green and only a log line and the
  artifact reveal it. → Hence the assertion: symbols present per ABI **and** no
  `.symtab` left in anything the artifact ships. Both halves are asserted because
  each has already been true on its own (symbols missing *and* unstripped libs).
- **A larger AAB.** The symbols entry for a ~38 MB engine library adds ~16 MB
  uncompressed in the bundle and is not part of what users download; the measured
  net was a *shrink* (47.5 → 42.1 MB), because stripping `base/` gives back more
  than the symbols cost. → Watch the AAB size in the release log either way.
- **An assertion that fires on a maintainer's local `-Bundle` build.** → Scope
  the assertion to the release workflow (where publication happens), not to
  `app/build.ps1`, so local iteration is not blocked. `docs/TESTING.md` documents
  the equivalent manual check.
- **Qt libraries contribute nothing.** → The scenario is per-ABI presence of the
  symbols entry, not per-library completeness; a maintainer reading a symbolicated
  trace still gets engine frames, which is where the crashes are.