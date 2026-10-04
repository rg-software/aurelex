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
  (`NdkOptions$DebugSymbolLevel` = `SYMBOL_TABLE` | `FULL` | `NONE`), so the
  build accepts it — and then produces nothing: the AAB's top-level entries are
  `base`, `BUNDLE-METADATA`, `BundleConfig.pb`, `META-INF`, with no
  `BUNDLE/native-debug-symbols/`, and no symbols artifact anywhere under
  `build/`.

- The inputs would allow it. `build-qtquick/apk/libs/arm64-v8a/libaurelex_arm64-v8a.so`
  keeps `.symtab`, `.strtab` and `.debug_info` (it is unstripped); Qt's own
  libraries arrive already stripped from `androiddeployqt`, so they can
  contribute a symbols entry with little content but should not block one.
- **AGP also declines to strip our library.** A debug build logs, from the
  `:stripDebugDebugSymbols` task:

  ```
  Unable to strip the following libraries, packaging them as they are:
  libaurelex_arm64-v8a.so
  ```

  So the library reaches `base/` unstripped, and there is still no
  `BUNDLE/native-debug-symbols/`. That makes the cause **two independent
  possibilities**, not one: either the `debugSymbolLevel` knob does not reach the
  bundle task in 7.4.1 (D1), or AGP's symbol extraction needs a relationship
  between the stripped library it ships and an unstripped original that this
  library's pass-through breaks. The first task in `tasks.md` exists to tell them
  apart before anything is written, because the fix differs: D1's
  `keepDebugSymbols` switch is only correct under the first reading.

- The Play Developer API v3 has no native-symbols method. The `edits` resources
  are `apks`, `bundles`, `countryavailability`, `deobfuscationfiles`, `details`,
  `expansionfiles`, `images`, `listings`, `testers`, `tracks`. Native symbols go
  up through the Play Console, so the pipeline's job ends at "published and
  documented", not "uploaded".

- AGP is pinned at 7.4.1 with `compileSdk 36` worked around
  (`android.suppressUnsupportedCompileSdk`, an `aapt2FromMavenOverride` to
  build-tools 36), and `androiddeployqt` regenerates `build.gradle` and
  `gradle.properties` on every run, which is why the script re-applies its
  overrides after the deploy step.

## Goals / Non-Goals

**Goals:**

- The release AAB contains `BUNDLE/native-debug-symbols/arm64-v8a/` with the
  symbol tables of the libraries it ships.
- `base/` still ships stripped libraries, so the download size does not regress.
- A symbol-less AAB fails the release rather than shipping.
- The symbols reach a human who can upload them to Play, with the versionCode and
  ABI they belong to recorded.

**Non-Goals:**

- Automating the Play Console upload. The API does not expose it; pretending
  otherwise would produce a script that cannot work.
- Symbolication of *Java* crashes, which Play already handles, and of
  obfuscated code (the release build sets `minifyEnabled false`).
- Adding a crash-reporting SDK, or changing which crash channel is used.
- Making Qt's prebuilt libraries debuggable. They ship stripped from Qt's own
  build; recovering their symbols is a Qt-packaging project, not ours.

## Decisions

**D1 — Retain symbols through the `jniLibs` packaging setting, not
`debugSymbolLevel`.**

`packagingOptions { jniLibs { keepDebugSymbols '**/*.so' } }` is the AGP 7.x
mechanism that both (a) keeps the unstripped input libraries available for the
bundle's symbols entry and (b) strips what goes into `base/`. `debugSymbolLevel`
was the pre-7.x spelling for the same intent and is accepted by the DSL but does
not reach the bundle task in 7.4.1 — which is exactly the bug this change fixes.

*Alternative considered:* keeping `debugSymbolLevel` and adding
`doNotStrip`. Rejected: `doNotStrip` would ship the ~38 MB unstripped engine
library inside the AAB, growing every user's download for a maintainer-only
benefit.

**D2 — Assert on the built AAB's zip entries, in the same place as the existing
vendored-library check.**

`release-qt.yml` already asserts the vendored OpenSSL `.so`s reached the
packaged artifact. The symbols assertion is the same shape: open the AAB, look
for `BUNDLE/native-debug-symbols/<abi>/`, fail before the Play publish step. The
assertion is on the artifact, not on the Gradle flag, because the flag being
present is exactly what already failed silently.

*Alternative considered:* trusting the Gradle log. Rejected: log-scraping is
what let the original change look successful.

**D3 — Assert per shipped ABI, derived from `qtTargetAbiList`.**

The assertion derives the expected ABI list from the same property Gradle is
configured with, so adding an ABI later cannot silently skip the check.

**D4 — Publish the symbols as a release asset; do not attempt the Console
upload.**

The symbols archive (the `BUNDLE/native-debug-symbols/<abi>/` subtree, zipped) is
attached to the GitHub release next to the AAB and APK, and `docs/SIGNING.md`
gains the recipe: which file, which versionCode, which ABI, and that the upload
target is the Play Console's per-ABI native debug symbols upload. Attaching it
also means the symbols survive independently of anyone's Play Console session.

**D5 — Leave the crash channel alone.**

Play vitals symbolicates native crashes from these uploaded symbols, so the
current channel becomes useful once they exist. Crashlytics would consume the
same symbols if it were ever adopted; symbols are not a step toward Crashlytics,
they are a prerequisite for *any* native-crash diagnosis.

## Risks / Trade-offs

- **AGP may not honour `keepDebugSymbols` for bundles either.** → The first task
  is a throwaway release build that prints the AAB's top-level entries and the
  `:stripDebugDebugSymbols` log; if the symbols entry still does not appear, the
  fallback is to run `llvm-strip` ourselves from `llvm-objcopy --only-keep-debug`
  in the build script and zip the result, which is uglier but fully under our
  control. The spec does not change either way.
- **Our library ships unstripped into the AAB.** The strip task declines it, so
  `base/lib/arm64-v8a/libaurelex_arm64-v8a.so` is the ~38 MB unstripped file. That
  is a download-size regression for every user and is invisible in the artifact's
  compressed size. → Treat "is the library actually stripped in the AAB" as an
  explicit assertion alongside the symbols assertion, and if AGP cannot strip it,
  strip it in the build script before packaging rather than shipping the
  pass-through.
- **A larger AAB.** The symbols entry for a ~38 MB engine library is on the order
  of a few MB, uncompressed in the bundle and not part of what users download.
  → Watch the AAB size in the release log; the download size is unaffected
  because `base/` stays stripped.
- **An assertion that fires on a maintainer's local `-Bundle` build.** → Scope
  the assertion to the release workflow (where publication happens), not to
  `app/build.ps1`, so local iteration is not blocked.
- **Qt libraries contribute nothing.** → The scenario is per-ABI presence of the
  symbols entry, not per-library completeness; a maintainer reading a symbolicated
  trace still gets engine frames, which is where the crashes are.