## 1. Pin the baseline before changing anything

- [x] 1.1 Build a release artifact from the current tree (`pwsh -File .\app\build.ps1 -Configuration Release -Bundle`) and record the packaged native payload: the file count and total bytes under the AAB's `base/lib/<abi>/` and the APK's `lib/<abi>/`. Confirm the recorded total matches the 140 libs / 86.32 MB measured from `stripped_native_libs/release`, and record the per-library breakdown as the change's baseline.
  `aurelex-release.apk` 40,038,405 B and `aurelex-release.aab` 44,175,753 B
  (APK 38.2 MB, AAB 42.1 MB — matching `embed-native-debug-symbols` task 1.5).
  **140 `.so` / 86.32 MB** in both, with identical basename sets. Confirmed the
  design baseline exactly. Largest: `libaurelex` 9.00, `libQt6Gui` 7.06,
  `libQt6Widgets` 6.45, `libQt6Quick` 6.06, `libQt6Core` 5.64, `libQt6Designer`
  5.12, `libcrypto_3` 3.84, `libQt6ShaderTools` 3.38 MB.
- [x] 1.2 Confirm the baseline artifact has no library with a `.symtab`, i.e. that `embed-native-debug-symbols` is landed and stripping works. If it does not, stop: that change owns stripping and this one must not absorb it.
  **0 of 140** packaged libraries have a `.symtab`, and `llvm-readelf -S`
  reported a section table for all 140 (so a silently-failing readelf cannot
  read as "stripped"). `embed-native-debug-symbols` is landed; not absorbing it.
- [x] 1.3 Commit the derivation script (design D5) so the kept/dropped set is reviewable before it is wired into the build. It walks `DT_NEEDED` from `apk/libs/<abi>/libaurelex_<abi>.so`, unions the app's QML import modules and the curated root list from design D2, and prints kept/dropped with sizes. Run it against the baseline and confirm it reproduces the 44 kept / 96 dropped split, including that `libcrypto_3.so`, `libssl_3.so` and `libc++_shared.so` are **kept** (they are `dlopen`'d or injected and have no link edge — dropping them is the trap in design D2).
  Added `scripts/derive-native-payload.ps1` (`-Mode Derive|List|Json`). Running
  it found two bugs that a hand-written list would have shipped:
  1. **The candidate set was the kit only**, so `libcrypto_3.so`, `libssl_3.so`
     and `libc++_shared.so` all came out **dropped**. They are staged from
     outside the kit (`app/openssl/<abi>/` and the NDK) and have no link edge,
     so nothing would have put them back. Now indexed explicitly. All three
     report KEPT.
  2. **`readelf -d` was parsed without filtering on `NEEDED`.** It also prints
     `SONAME` in brackets and a library's SONAME is its own filename, so every
     library looked like it linked itself. Fixed; this was firing the
     ShaderTools assertion spuriously.

  Result: candidate 140 (matches the staged set exactly), **KEEP 47 / 48.43 MB,
  DROP 93 / 37.89 MB** — a **37.89 MB (43.9%)** reduction. Not the 44/96 split
  the proposal predicted: following `qmldir` `depends`/`import` chains (design
  D2) correctly keeps three more QML module plugins — `QtQml`'s metatype, Base
  and WorkerScript, reached because `main.qml` imports `QtQml.Models` — for
  0.12 MB. `design.md` Context corrected to 47/48.43 and 93/37.89.
- [x] 1.4 Record the two individually-checked calls from design Context as assertions in the script's comments: `libQt6Widgets` is reachable only via the `qandroidstyle` widget plugin, and no library in the staged set has `libQt6ShaderTools` in its `DT_NEEDED`. If a future kit changes either, the derivation should visibly change its answer rather than quietly keeping or dropping them.
  Both are in `scripts/derive-native-payload.ps1` as `Write-Warning` assertions
  with the reasoning in comments, not silent behaviour. The ShaderTools
  assertion is what caught the SONAME parse bug; the `qandroidstyle` assertion
  re-checks each run that no curated plugin links `libQt6Widgets`, so if a kit
  ever makes the widget plugin reachable the derivation says so instead of
  quietly dropping a needed library. Neither fires on the current kit.

## 2. Filter the staging step

- [x] 2.1 Replace the three wholesale `Copy-Item` calls in the `[3/5] stage app .so + Qt runtime/QML libs` step of `app/build.ps1` with the derived keep-set, applied to `$KitRoot/lib`, `$KitRoot/qml/**/libqml_*.so` and `$KitRoot/plugins/**/libplugins_*.so`. Log the kept and dropped counts and bytes so a build says out loud what it did.
  One loop over the three sources, each file kept only if its name is in the
  derived set, plus a build log line:
  `Qt kit: 136 candidates -> kept 43 (34.01 MB), dropped 93 (37.89 MB)`.
  The derivation is called with the paths build.ps1 already resolved, and the
  build **fails** if it does not resolve the app library or the platform plugin
  — shipping "only what was derived" with a broken derivation would produce an
  APK that cannot start. Two guards on the edge-less libraries: `libc++_shared.so`
  is asserted right after the NDK copy, and the vendored OpenSSL pair after the
  `androiddeployqt` step that stages them. The first version of the OpenSSL
  assertion sat *before* that step and correctly failed the build — the trap in
  design D2 caught at build time instead of at catalog-open time.
- [x] 2.2 Apply the same filter to the `Copy-Item "$KitRoot/qml/*"` that stages the asset tree, pruning by module directory against the same reachable set (design D3). Do not filter the two destinations independently — a module reachable in one and missing from the other fails worse than an absent module.
  Pruning is **per module**, driven by the same `$keep`. Two wrong approaches
  first, both caught by inspecting the staged tree:
  1. `Copy-Item -Recurse` on the shallowest reachable directories copied
     `QtQuick/Controls` whole, which dragged in its nested Fusion/, Imagine/,
     Universal/ and Basic/impl modules — 41 of 52 modules, unchanged byte count.
  2. Walking up to the first *reachable* ancestor re-admitted the same nested
     modules, because their parent is reachable.
  Correct rule: build the set of all module dirs (those with a `qmldir`) and
  the reachable subset (those holding a kept plugin `.so`), then copy a file
  when its **nearest** module dir at or above it is reachable — the walk stops
  at a module boundary, so a nested module vetoes its parent, while a
  non-module subdirectory still counts as its module's content.
  Result: `assets/qml: 12 of 52 modules reachable, copied 288 files (1.43 MB)`,
  down from 696 files / 8.12 MB. Verified **0** `.so` under `assets/qml` that
  are outside the keep-set.
- [x] 2.3 Determine empirically whether the QML engine resolves module plugins from `apk/libs/<abi>/` alone, which would make the 5.45 MB duplicated copy under `assets/qml/` removable. Test by removing one module `.so` from `assets/qml/` only and launching. Record which way it went and either drop the duplicate or record why both copies are required.
  **Redundant — dropped from the asset tree.** Measured on the ThinkPhone:
  with all 16 `assets/qml/*.so` removed, `logcat` shows the QML engine loading
  every module plugin from `base.apk!/lib/arm64-v8a/` (jniLibs), and the app
  starts and renders the same `Zimbabwe` article identically.
  The prize is far smaller than the design assumed: design D3 quoted 5.45 MB of
  duplicated `.so`, but that was measured before the module filter, and most of
  it belonged to modules that are no longer staged at all. After the filter the
  duplicate is **0.18 MB**. Worth removing anyway — it removes the chance of the
  two copies disagreeing — but it is not where the 37 MB was.
  `build.ps1` now skips `.so` when copying `assets/qml/`, with the measurement
  recorded in the comment.
- [x] 2.4 Verify `Write-QtLibResources` still mirrors the staged set exactly, since it derives `bundled_libs`/`qt_libs` from `apk/libs/<abi>/` and a mismatch is the documented `Resources$NotFoundException` / "Can't create main activity" failure. Rebuild and diff the emitted `res/values/libs.xml` against the expected filtered list.
  `Write-QtLibResources` is **untouched** (the build.ps1 diff is four hunks, all
  in the staging paths), and it derives from `libs/`, so it followed the filter
  automatically. Emitted arrays, checked against the 47 staged `.so`:
  `qt_libs` 43 (= the 43 kept kit libs exactly), `bundled_libs` 45
  (+ `c++_shared` + the app library), `load_local_libs` 1 (the app library).
  **0 entries dangle** — every name in every array resolves to a staged `.so`.
  The 2 staged libraries absent from all three arrays are `libcrypto_3.so` and
  `libssl_3.so`, which is correct: Qt `dlopen`s them by plain name, so
  `QtLoader` must not try to preload them.
  *Pre-existing, out of scope, noted for a follow-up:* the comment above
  `Write-QtLibResources` says `load_local_libs` entries "are used verbatim ...
  so it keeps the full filename (`libaurelex_arm64-v8a.so`)", but the generator
  emits the same `<abi>;<bare stem>` form as the other two arrays. The app
  builds and runs today, so the emitted form works and the comment is what is
  wrong — not introduced here, and not touched by this change.
- [x] 2.5 Rebuild and confirm the packaged native payload drops from 140 libs / 86.32 MB to ~44 libs / ~48.34 MB, and that no dropped library is reachable per the derivation.
  **52 libs / 48.88 MB** packaged (not the 44 the proposal predicted — see 1.3
  and 2.2 for why the closure is larger than a link-only walk). Both artifacts
  agree: APK `lib/arm64-v8a/` and AAB `base/lib/arm64-v8a/` each hold 52 `.so`
  totalling 48.88 MB. **0** staged libraries outside the keep-set and **0**
  keep-set entries missing, in both directions. Stripping still holds after the
  filter: **0 of 52** packaged libraries have a `.symtab`. `assets/qml` holds
  **0** `.so`.
  Artifact sizes: APK 38.2 → **19.9 MB**, AAB 42.1 → **23.8 MB**; `assets/qml`
  696 files / 8.12 MB → 293 files / 1.35 MB.

## 3. Guard it in the release pipeline

- [x] 3.1 Extend the native-payload assertion that `embed-native-debug-symbols` added to `.github/workflows/release-qt.yml` — do not add a second step — with a total-bytes ceiling for `lib/<abi>/`, recorded as a number next to the derivation that produced it (design D4).
  Added as section `3.` inside the existing "Assert native debug symbols are in
  the release artifacts" step (not a new step), summing every `lib/<abi>/*.so`
  in both artifacts per ABI. Ceiling **52 MB**, recorded inline with its
  provenance (`scripts/derive-native-payload.ps1`) and the measured 48.88 MB,
  and with the size of the modules it is meant to catch (Widgets 6.45,
  Designer 5.12, VirtualKeyboard 4.60, ShaderTools 3.38).
- [x] 3.2 In the same step, assert the shipped library name set equals the derived reachable set, so a filter that silently drops a needed library fails the build rather than the app. Reuse the step's existing `PACKAGED_ABIS` derivation and its chunked extraction.
  The step re-derives the expected set by invoking
  `scripts/derive-native-payload.ps1 -Mode List` with `AURELEX_QT_BASE` /
  `AURELEX_NDK_ROOT` (both already set as workflow env) and the built app
  library, so the pipeline and `build.ps1` cannot drift apart. Missing script or
  missing app library is a **failure**, not a skip — passing unchecked is what
  this repo's other assertions refuse to do. Reports both directions: shipped
  but unreachable, and reachable but not shipped.
- [x] 3.3 Verify the failure path: run the step's script against an artifact carrying a known-dead library and one over the ceiling, and confirm each exits non-zero naming the offending library or the measured size.
  Four cases, all behaving correctly:
  - real artifact, ceiling 52 MB → **PASS**
  - `libQt6Designer` re-added into `lib/arm64-v8a/` → **FAIL**, "shipped but
    unreachable: libQt6Designer_arm64-v8a.so"
  - `libqml_QtWebView_qtwebviewquickplugin` removed → **FAIL**, "reachable but
    NOT shipped"
  - real artifact against a 20 MB ceiling → **FAIL**, "arm64-v8a ships 48.88 MB,
    over the 20 MB ceiling"

## 4. Verify on device, then retire the limitation

- [x] 4.1 Run the on-device matrix in `docs/TESTING.md` against a filtered release build before archiving: app start in both themes, a lookup in each supported format, an article with embedded imagery (exercises the retained image formats from design D2), audio playback, the remote catalog (exercises the `dlopen`'d vendored TLS from design D2), and a full-text search.
  Installed `aurelex-release.apk` (19.9 MB, 52 libs) on the ThinkPhone and
  exercised it. **Verified:**
  - App start, full UI, Russian locale, all six dock tabs.
  - **Both themes**: dark, then light via the theme control — the whole surface,
    the article and the accent all invert correctly.
  - Dictionary scan: **3 dictionaries** — two kaikki `.dsl.dz` (Japanese,
    Russian) and `The World Factbook 2014` (`.ifo`). dictzip and StarDict both
    load.
  - `gd_suggest`: the suggestion dropdown populated with real headwords from the
    Factbook (`Zimbabwe`, `Zimbabwe Economy`, `Zimbabwe Geography`, …).
  - `gd_lookup` + article server + WebView: `Zimbabwe` renders the full
    "Zimbabwe Introduction" article, dictionary header chip, styled `Background`
    heading and body text.
  - Article toolbar (find/back/forward/favourite/A−/A+) present.
  - **Full-text search**: `Mugabe` returned two real hits (`Zimbabwe Government`,
    `Zimbabwe Introduction`) with the source named, index built on demand
    (`fts progress 1/1`, `gd_fts_search rc= 2`).
  - **Remote catalog pane** opens, parses the manifest, and shows correct
    localized names, sizes, `Установлено` state and audio toggles.
  - No QML errors, no `UnsatisfiedLinkError`, no native crash in any run.
  - **Remote catalog, online — TLS verified.** The device had no network, so the
    first attempt only reached DNS (`remote catalog unreachable: "Host
    rg-software.github.io not found"`), which says nothing about TLS. Brought it
    online with a PC-side CONNECT tunnel: a minimal forward proxy on the PC,
    `adb reverse tcp:8888 tcp:8888`, and `settings put global http_proxy
    127.0.0.1:8888`. CONNECT passes bytes through untouched, so the handshake
    and certificate validation happen end to end against the real host — this
    exercises the app's own TLS stack rather than intercepting it.
    Result: proxy logged `CONNECT rg-software.github.io:443` → `tunnel
    established`, the app logged `fetching remote catalog:
    "https://rg-software.github.io/aurelex/catalog/catalog.json"` then
    **`remote catalog ok: 3 entries`**, and the pane switched from the cached
    fallback to **`Обновлено 04.10.2026 15:12`** with the orange
    "could not check for updates" banner gone. `libplugins_tls_qopensslbackend`
    and `libplugins_tls_qcertonlybackend` loaded from the APK, and
    `libcrypto_3.so`/`libssl_3.so` are the `dlopen`'d curated roots the filter
    keeps — so the design D2 trap is verified end to end, not just asserted.
    Device state restored afterwards: `http_proxy` back to `:0`, `adb reverse`
    removed, proxy process stopped.

  **Closed by maintainer check.** The two remaining items — audio playback and
  an article with embedded imagery — were verified by hand on the same filtered
  build and reported working. That matters for the record: it means the image
  format plugins retained deliberately in design D2 (`qjpeg`, `qgif`, `qico`,
  `qsvg`, 0.87 MB) render real dictionary artwork, and that audio plays. Both
  were the only kept-because-reasoned-about libraries not otherwise exercised
  at run time.
- [x] 4.2 Delete the `docs/TESTING.md` known-limitation line "Release APK/AAB currently package every Qt kit library and plugin, including debug/tooling binaries (`app/build.ps1` staging), rather than a filtered set." — this change is what it was waiting for. Add a gotcha entry recording that the filter is derived, that a new `import` or Qt link widens the payload automatically, and that a hand-edit to the staged set will be undone by the next build.
  Line removed. Added a "Native payload filtering" entry to **Known gaps**
  covering: the set is derived (hand edits are overwritten); the module closure
  must follow `.qml` imports as well as `qmldir`, with the exact
  `QtQuick.Window` failure it causes; the three edge-less libraries and what
  breaks if they are dropped; the `readelf -d` `SONAME` parsing trap; the
  deliberate non-duplication of module plugins; and where the pipeline asserts
  both halves.
- [x] 4.3 Note the measured before/after payload numbers in `docs/SIGNING.md` next to the existing packaging assertions, so the ceiling in the workflow has a documented provenance.
  New "Native payload — what actually ships in `lib/<abi>/`" section next to the
  native-symbols one: before/after table (140→52 libraries, 86.32→48.88 MB,
  `assets/qml` 696 files/8.12 MB → 293/1.35 MB, APK 38.2→19.9 MB, AAB
  42.1→23.8 MB), what is being dropped and why, the produced-by/verified-by
  rows, the 52 MB ceiling with its measured value and its headroom rationale, and
  the three verified failure paths.
- [x] 4.4 Confirm this change landed **after** `embed-native-debug-symbols`: both edit the generated `build.gradle` and the same workflow step, and `androiddeployqt` regenerates that file. Check that the post-deploy patch in `app/build.ps1` re-applies every override idempotently on top of the other change's, in a fresh tree and in one with stale state.
  Confirmed, and the two changes turn out not to overlap. `git diff` on
  `app/build.ps1` touches **no** gradle line — no `ndkPath`, no
  `debugSymbolLevel`, no `signingConfig`, no `useLegacyPackaging`, no
  `New-BaseBuildGradle` — so `embed-native-debug-symbols`' post-deploy override
  patch is untouched and there is nothing to re-apply on top of. This change only
  edits the two staging paths, both of which run **before** `androiddeployqt`
  (steps `[3/5]` and `[4/5]`), and the derivation runs after `[2/5] ninja build`
  because it needs the freshly built `libaurelex_<abi>.so`.
  Stale-state idempotency verified by re-running `build.ps1` over an existing
  build tree with no clean: identical output (48 kept / 88 dropped, 293 files /
  1.35 MB, APK 19.9 MB, AAB 23.8 MB), no accumulation in `libs/` or
  `assets/qml/`.