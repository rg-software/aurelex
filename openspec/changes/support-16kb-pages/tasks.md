# Tasks

## 1. Toolchain bump (NDK r30, Qt 6.9.3, AGP 8.6.0/Gradle 8.10)

- [x] 1.1 Bump NDK r23c → r30 (`30.0.16248370`) in `app/build.ps1` defaults and `.github/workflows/release-qt.yml` install step (URL `android-ndk-r30-windows.zip`, `NDK_ROOT` dir name), and verify `llvm-readelf --version` runs from the new NDK in CI.
- [x] 1.2 Bump Qt 6.6.3 → 6.9.3 in `app/build.ps1` defaults, `release-qt.yml` aqt lines (desktop + both android kits), and `docs/DEVELOPMENT.md`, and verify `androiddeployqt.exe` exists at the new kit path in CI.
- [x] 1.3 Bump AGP 7.4.1 → 8.6.0 in `New-BaseBuildGradle` plus Gradle 8.3 → 8.10 in the CI install step, add `namespace "org.aurelex.pocket.dictionary"` to the `android {}` block (mandatory under AGP 8), and verify `assembleDebug` configures under JDK 17.
- [x] 1.4 Flip `qtMinSdkVersion` 24 → 28 in the `gradle.properties` template and the patch regex in `app/build.ps1`, and verify the packaged APK's manifest reports `minSdkVersion 28`.

## 2. Native-code 16 KB alignment

- [x] 2.1 Add explicit `-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384` link options in `app/CMakeLists.txt` (covering carve objects linked in) and verify `ninja -n` shows the flags on the app link.
- [x] 2.2 Rebuild vcpkg deps + xapian under NDK r30 via the CI workflow (cache auto-busts on the workflow change) and verify the build completes without old-NDK paths.
- [x] 2.3 Re-point `libc++_shared.so` staging in `app/build.ps1` at the NDK r30 layout and verify the staged file's `LOAD` segments report `align 2**14`.

## 3. Vendored OpenSSL re-pin

- [x] 3.1 Verified the vendored OpenSSL pair is already 16 KB-aligned: the pinned KDAB revision `b71f147` postdates the upstream 16 KB rebuild (`32ebe30`), and `llvm-readelf` reports `LOAD align 0x4000` with page-safe RELRO on all four `.so` — no binary change needed.
- [x] 3.2 Recorded the 16 KB provenance in `app/openssl/README.md` (postdates `32ebe30`, alignment verified) without touching the binaries or their digests.

## 4. Packaging flip to 16 KB zip alignment

- [x] 4.1 Flip `packagingOptions.jniLibs.useLegacyPackaging true` → `false` in `New-BaseBuildGradle` (plus the androiddeployqt-template patch path if present), and verify `bundletool dump config` reports `PAGE_ALIGNMENT_16K` on a CI-built AAB.
- [x] 4.2 Keep the `aapt2FromMavenOverride` + `suppressUnsupportedCompileSdk` pins (AGP 8.6 still predates SDK 36) re-pinned to build-tools 36.0.0, and verify `assembleRelease` + `bundleRelease` succeed.

## 5. CI 16 KB assertions and payload re-baseline

- [x] 5.1 Add a release-workflow step asserting every `lib/<abi>/*.so` is ELF 16 KB-aligned (`llvm-readelf` `LOAD`/`RELRO` check) plus `zipalign -c -P 16` (APK) and `PAGE_ALIGNMENT_16K` (AAB), failing before publication, and verify it fails on a deliberately unaligned fixture `.so`.
- [x] 5.2 Re-derive the reachable set with `scripts/derive-native-payload.ps1` under Qt 6.9.3, update the payload ceiling and expected lib list, and verify the set-equality + budget checks pass on the new artifact.

## 6. User-facing copy for the new OS floor

- [x] 6.1 Update `README.md` ("Android 7.0+" → "Android 9.0+"), `app/android/store-listing/listing.md` (both 7.0 spots → 9.0 / `minSdk 28`), and `docs/SIGNING.md` (`minSdkVersion` 24 → 28), and verify the three agree with the packaged manifest's `minSdkVersion 28`.

## 7. Device verification

- [ ] 7.1 Boot a 16 KB emulator image (or 16 KB developer option), confirm `adb shell getconf PAGE_SIZE` returns `16384`, install the Release APK, and verify launch with no backcompat dialog plus a dictionary lookup rendering an article.
- [ ] 7.2 Run the `docs/TESTING.md` hardware pass (lookup, article, audio, groups, FTS, catalog TLS) on the 16 KB build and verify no regressions vs. the 4 KB baseline.
