## Why

Google Play warns that Aurelex does not support 16 KB memory page sizes, and Play blocks updates that target Android 15+ (API 35+) without it — Aurelex targets API 36. The app ships native code (carved engine, Qt runtime, vendored OpenSSL), so every shipped `.so` must be 16 KB ELF-aligned and zip-aligned, which the current NDK r23c / Qt 6.6.3 / AGP 7.4.1 toolchain cannot produce.

## What Changes

- **Toolchain moves to 16 KB-capable versions.** NDK r23c → r30 LTS (16 KB-aligned by default), AGP 7.4.1 → 8.6.0 (Gradle 8.3 → 8.10, the pair Qt 6.9 itself uses), Qt 6.6.3 → 6.9.3 open-source (confirmed 16 KB-compatible; Qt 6.8.5+ is commercial-only and not installable via aqt).
- **Every shipped native library is rebuilt 16 KB-aligned.** App/carve objects, vcpkg deps (zlib/bzip2/lzma/lzo/fmt), xapian, `libc++_shared.so` (comes with the NDK), Qt runtime staged from the new kit, and the vendored OpenSSL pair (rebuilt sources, re-pinned digests).
- **Packaging switches to 16 KB zip alignment.** Uncompressed native libraries with `PAGE_ALIGNMENT_16K`; the old `useLegacyPackaging true` compressed fallback goes away.
- **CI asserts compliance before publication.** ELF-alignment (`LOAD align 2**14`, RELRO check) and `zipalign -P 16` checks on the APK/AAB join the existing TLS/symbols/payload assertions; payload budget re-baselined for the new Qt kit.
- **Minimum Android version rises 7.0 → 9.0 (minSdk 24 → 28).** Qt 6.9 supports API 28+ only, and the app already ships below Qt 6.6's supported floor (26). `qtMinSdkVersion`, `README.md`, the store listing, and `docs/SIGNING.md` move together; Android 7.0–8.1 devices are dropped.
- **No other user-visible behavior changes.** Same dictionaries, same UI, same signing/publishing flow — only the binaries' alignment (and the OS floor) change.

## Capabilities

### New Capabilities

- None — no new user-facing behavior.

### Modified Capabilities

- `distribution-and-polish`: "Signed release artifacts" / "Self-contained release builds" gain that every shipped native library SHALL be 16 KB ELF-aligned and the artifact SHALL be 16 KB zip-aligned, verified before publication, so Play accepts updates targeting API 35+.

## Impact

- `app/build.ps1` — NDK r30 / Qt 6.9.3 / AGP 8.6.0 / Gradle 8.10, `namespace`, `minSdk 28`, `useLegacyPackaging`, `ndkPath`, payload derivation expectations; `docs/DEVELOPMENT.md` toolchain section.
- `.github/workflows/release-qt.yml` — NDK install, Qt install (aqt version/modules), Gradle version, vcpkg/xapian rebuild, new 16 KB assertions, payload ceiling.
- `app/CMakeLists.txt` / `carve/CMakeLists.txt` — explicit `-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384` belt-and-braces (no-op on NDK r28+, required if ever downgraded).
- `app/openssl/<abi>/*.so` + `app/openssl/README.md` — rebuilt OpenSSL pair, new upstream rev/version/digests.
- `scripts/derive-native-payload.ps1` — re-baseline only if the Qt bump changes the reachable set; no logic change expected.
- `README.md`, `app/android/store-listing/listing.md`, `docs/SIGNING.md` — "Android 7.0+" / `minSdk 24` → Android 9.0 / `minSdk 28`.
- No engine sources, no patches, no QML/boundary changes.
