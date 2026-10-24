# Design

## Context

See proposal.md — Why. What shapes the approach:

- The toolchain is pinned in three places that must move together: `app/build.ps1` (NDK r23c, Qt 6.6.3, AGP 7.4.1, Gradle 8.3, `ANDROID_PLATFORM=android-30`), `.github/workflows/release-qt.yml` (same NDK/Qt/Gradle installs, vcpkg + xapian build, TLS/symbols/payload assertions), and `docs/DEVELOPMENT.md` (documents the same pins).
- Google's recipe is fixed: AGP ≥ 8.5.1 + NDK ≥ r28 + 16 KB-compatible prebuilts → compliant by default. NDK r28 aligns ELF by default; r27 and below need explicit `-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384`.
- Qt is the largest prebuilt surface: 6.6.3 predates the 16 KB fix (Qt ships it in 6.8.5, Oct 2025, and in 6.10). Every staged Qt `.so` must come from an aligned kit — flags on our own code cannot fix the kit.
- OpenSSL is the second prebuilt surface: `app/openssl/<abi>/*.so` (KDAB `b71f147`, 3.1.8) predates the fix; Qt-interest reports confirm those prebuilts are non-compliant. It must be rebuilt, not flagged.
- The release pipeline already asserts TLS/symbols/payload on the packaged artifact — 16 KB checks join that pattern, not a new harness.

## Goals / Non-Goals

**Goals:**

- One cutover: after this change every build (local + CI, Debug + Release) produces 16 KB-aligned artifacts from a fresh checkout.
- Keep the existing assertion pattern: new checks fail the release before publication, with the same per-ABI shape as the TLS/symbols checks.
- Re-baseline the native-payload budget for the new Qt kit rather than silently widening it.

**Non-Goals:**

- No `PAGE_SIZE` code fixes in engine/carve: no hard-coded 4 KB assumptions are known; the 16 KB emulator run confirms rather than redesigns.
- No multi-ABI expansion, no 32-bit work, no `extractNativeLibs` redesign beyond the `useLegacyPackaging` flip.
- No Play-deadline exception handling or backcompat-mode (`android:pageSizeCompat`) opt-outs.

## Decisions

**D1 — NDK: r30 LTS (`30.0.16248370`, Sep 2026).**
NDK r28+ aligns ELF by default, so r30 (latest LTS) removes the flag-fragility for our own objects; older NDKs need per-target flags on every link. Newer-than-Qt's-build-NDK is the safe direction (Qt 6.9 was built with r26b/r27c; an older NDK than Qt's risks missing symbols, a newer one does not). Alternatives (stay on r23c + flags) cannot fix the kit/vcpkg/OpenSSL prebuilts and leaves `libc++_shared.so` unaligned. `ANDROID_PLATFORM=android-30` stays (still present in r30 sysroots); `libc++_shared.so` staging in `build.ps1` is re-pointed at the new NDK layout.

**D2 — Qt 6.9.3 (open-source, 16 KB-confirmed), not 6.8 LTS.**
Qt 6.8.5+ has the fix but is commercial-only and not installable via `aqtinstall`; open-source 6.8 stops before the fix. Qt 6.9.3 is the minimal mechanical jump from 6.6.3 with confirmed 16 KB support (forum-verified; also covers Android 16 / API 36). Accepted trade-off: upstream standard support for 6.9 has ended, and 6.9's supported floor is API 28 — which forces D8. Installed via the same `aqtinstall` lines with the version bumped; 6.12 LTS stays a future option, not this change.

**D3 — AGP 8.6.0 + Gradle 8.10 (Qt 6.9's own pair), `useLegacyPackaging false`, add `namespace`.**
AGP 8.5.1+ emits `PAGE_ALIGNMENT_16K` with uncompressed libraries; below that the bundle carries 4 KB-aligned `.so` even when ELF is right. So `packagingOptions.jniLibs.useLegacyPackaging true` (the pre-8.5 compressed fallback) flips to `false`, and the `aapt2FromMavenOverride` + `suppressUnsupportedCompileSdk` pins stay (AGP 8.6 still predates SDK 36) — re-pinned only if unneeded. AGP 8.x mandates `namespace` in `build.gradle`, so the template gains `namespace "org.aurelex.pocket.dictionary"`. JDK 17 already satisfies AGP 8.x; `lintOptions`/`buildToolsVersion` DSL stays (deprecated warnings at most).

**D4 — Explicit linker flags in `app/CMakeLists.txt` (and carve) as belt-and-braces.**
`target_link_options(... "-Wl,-z,max-page-size=16384" "-Wl,-z,common-page-size=16384")` on the app link (covering the carve objects linked in). No-op under NDK r28+, but makes a future NDK downgrade fail loudly at link rather than silently ship 4 KB. Alternative (rely on NDK default alone) was rejected: the failure mode is a Play rejection weeks later.

**D5 — OpenSSL: already compliant at the pinned revision; verify, don't rebuild.**
The pinned KDAB revision `b71f147` (Jan 2026) postdates upstream's 16 KB rebuild
(`32ebe30`, Oct 2025) and keeps its flags: all four vendored `.so` report
`LOAD align 0x4000` with a page-safe RELRO (verified with `llvm-readelf` during
this change). So the binaries stay byte-identical and only `app/openssl/README.md`
gains the 16 KB provenance note. If the pin ever moves, the new revision must be
re-checked the same way before vendoring. `app/CMakeLists.txt`
(`QT_ANDROID_EXTRA_LIBS`) and the CI TLS assertion are unchanged.

**D6 — vcpkg + xapian rebuild; cache keys roll.**
No script change: both build from the NDK in the environment, so the NDK bump rebuilds them. The vcpkg cache key (`release-qt.yml`) hashes the workflow file, so the NDK/URL edit invalidates it automatically; confirm the restored-tree bootstrap path still works under the new NDK before relying on a warm cache.

**D7 — Verification joins the release assertions, per ABI.**
After the existing TLS/symbols/payload steps: extract `lib/<abi>/*.so`, run `llvm-readelf` (`LOAD align 2**14`, RELRO formula), run `zipalign -c -P 16` on the APK and `bundletool dump config | grep PAGE_ALIGNMENT_16K` on the AAB. Payload ceiling re-baselined by measuring the new kit once (`derive-native-payload.ps1` output + ~headroom), not by deleting the check.

**D9 — Qt 6.8 made `QtNative.activity()` package-private; cache the activity.**
`AurelexActivity`'s static JNI entry points reached the activity through
`QtNative.activity()`, which does not compile under Qt 6.9 (found by the CI
`compileReleaseJavaWithJavac` failure, v0.4.2). The fix holds the instance in a
`private static volatile Activity sActivity` set in `onCreate` (cleared in
`onDestroy`) and uses it in the 13 static call sites — no JNI signature changes,
no behavior change. Alternative (pass the activity from C++ via
`QNativeInterface::QAndroidApplication::context()`) was rejected: it would
change every JNI call site on both sides for no gain.

**D8 — minSdk 24 → 28; user-facing copy moves in the same change.**
Qt 6.9 supports API 28+ only, so `qtMinSdkVersion` 24 → 28 in `build.ps1` (template + patch regex). The app already ships below Qt 6.6's supported floor (26), so this makes the floor honest rather than newly risky. `README.md` ("Android 7.0+"), `app/android/store-listing/listing.md` (both spots), and `docs/SIGNING.md` (`minSdkVersion` 24) all move to Android 9.0 / API 28 together — a store listing that promises 7.0 while the manifest requires 9.0 is the failure this avoids.

**D10 — Qt 6.9.3 `loadHtml` renders percent-encoded; load baseless + CORS the server.**
Qt 6.9.3's Android `loadHtml` passes `QUrl::toPercentEncoding(html)` into
`loadDataWithBaseURL`, whose data path does not decode — the article shows as
encoded text (found on device, tagged release). Qt fixed it upstream in 6.12
(raw html with an http base, encoded only for empty/data bases). Until the Qt
bump, `main.qml` calls `loadHtml(html, "")`: the empty base takes the
decoding `loadData` path on both Qt versions, and every subresource URL is
already absolute so no base is needed for resolution. The page origin becomes
opaque, so `ArticleServer` now sends `Access-Control-Allow-Origin: *` on every
reply and answers OPTIONS preflights (204) — otherwise Dark Reader's
stylesheet fetch is CORS-blocked in dark mode. Covered by
`article_server_test` (CORS header assertion + preflight check).

## Risks / Trade-offs

- [Qt bump widens/changes the reachable set] → Re-run `derive-native-payload.ps1`, update the 52-lib/52 MB expectations and the ceiling in the same change; CI set-equality check catches drift.
- [Qt 6.9 behavior drift (Controls/Material, WebView, QML imports — 6.6→6.9)] → Full `docs/TESTING.md` pass on hardware; no spec changes expected but visual diffs are possible.
- [Qt 6.9 upstream support ended] → Accepted: the app pins Qt per release and re-bumps yearly; 6.12 LTS is the tracked next step, not this change.
- [AGP 8.x migration fallout (`namespace`, DSL removals, build-tools)] → Migrate `build.gradle` template minimally, keep `resConfigs en/ru/ja` patch; dry-run `workflow_dispatch` build before any tag.
- [xapian/vcpkg rebuild time on cold cache (~25–40 min)] → Accept; warm cache restores after first green run.
- [`aapt2FromMavenOverride` / `suppressUnsupportedCompileSdk` stale] → Remove only if the new AGP links SDK 36 natively; otherwise re-pin to the new build-tools.

## Migration Plan

1. Land toolchain + flags + OpenSSL + packaging flip + CI checks + docs in one change (no staged rollout; old and new artifacts are not install-compatible for Play purposes anyway).
2. Verify: local Debug `-Install` on a 16 KB emulator (`getconf PAGE_SIZE` → `16384`), `check_elf_alignment.sh` + `zipalign -P 16` clean, no backcompat dialog.
3. Dry-run release workflow (`workflow_dispatch`, unsigned) → assertions green → tag a release → Play warning clears.
4. Rollback: revert the change; previously published artifacts are unaffected (Play keeps serving the last compliant upload).

## Open Questions

- None remaining: Qt 6.9.3 + NDK r30 + AGP 8.6.0/Gradle 8.10 + minSdk 28 all resolved with the user.
- Q2 carried into implementation: whether KDAB has published 16 KB-aligned prebuilts (decides D5's first vs. second branch; checked during implementation).
