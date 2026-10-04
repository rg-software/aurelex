# Signing, Distribution & App Identity

How Aurelex is signed, where each artifact goes, and how the app presents
itself (icon + notification). Two independent signing channels by design —
Google Play and F-Droid are separate install channels with different
signatures.

## Artifacts produced by CI

On a `vX.Y.Z` tag push, CI (`.github/workflows/release-qt.yml`, windows-latest)
builds a signed release APK **and** AAB from the Qt app (`app/`) and
attaches both — plus the native debug symbols archive — to a GitHub release:

| Artifact | Path | Used by |
| --- | --- | --- |
| `.apk` | `build-qtquick/apk/build/outputs/apk/release/*.apk` | GitHub releases / F-Droid / sideload |
| `.aab` | `build-qtquick/apk/build/outputs/bundle/release/*.aab` | Google Play upload |
| native debug symbols | assembled from the AAB into `$RUNNER_TEMP/native-debug-symbols/*.zip` | GitHub release asset (archived, and the fallback upload source — Play needs none; see below) |

The release workflow locates both by glob, not by name, and fails the job if
either glob comes up empty — so the exact Gradle-assigned filename is free to
change and nothing should depend on it.

(`app/build.ps1 -Configuration Release -Bundle` produces the same pair
locally.) `versionName` is the tag (`vX.Y.Z` → `X.Y.Z`); `versionCode` is derived
deterministically as `major*10000 + minor*100 + patch`. Locally (no props)
builds fall back to `versionCode 1` / `versionName 0.0.1`.

## Play publishing policy — tag only

CI publishes to Google Play **only for a well-formed release tag**, and only to
the **internal testing** track. The gate is the same predicate that derives the
versionCode: `vMAJOR.MINOR.PATCH` with each component `< 100`. Everything else —
branch pushes, `workflow_dispatch` dry-runs — builds and attaches artifacts but
publishes nothing. The "each < 100" bound is what keeps the deterministic
versionCode collision-free (`v1.2.3` and `v1.2.03` would otherwise both encode
`10203`), so a tag that cannot be encoded cannot be published. A Play publish
failure fails the workflow but the signed APK + AAB are already attached to the
GitHub release.

## Google Play — Play App Signing (cloud signing)

Play App Signing (mandatory for new apps on Play) uses **two keys**:

1. **Upload key** — ours. Stored in CI secrets, it signs the AAB we upload to
   Play Console. If we lose it, it can be **reset** in Play Console without
   affecting delivered apps.
2. **App signing key** — held by **Google** in their cloud. Play re-signs the
   AAB into per-device APKs, and that is the signature users actually install.
   Google provides key-loss recovery and export.

This is the only "cloud signing" in the stack — it exists on Play, and only for
the final app-signing key. Sideloaded/GitHub APKs are signed with our key, not
Google's.

### Automated upload to internal testing

CI uploads the tagged AAB to the **internal testing** track with
`r0adkll/upload-google-play`, using a **Google Cloud service account**. Setup is
one-time and per-app:

1. In Google Cloud, create a project and a **service account**; enable the
   **Google Play Android Developer API**.
2. Create a JSON key for that service account and store it as the repo secret
   `PLAY_SERVICE_ACCOUNT_JSON` (plain JSON, not base64). Never commit the key.
3. In **Play Console → Users and permissions**, invite the service account's
   email and grant it **release** access to the Aurelex app only (release-only,
   single app — not account admin).
4. The first AAB of the app must already have been uploaded by hand through Play
   Console (it has been — internal testing works today). API uploads are only
   permitted after that initial upload establishes Play App Signing.

Notes:

- Target track is `internal`, release status `completed`; there is no staged
  rollout on this track and release notes may be blank.
- The service account is only used by the release workflow's publish step; the
  keystore secrets above are unchanged.
- **Rotation:** if the key is lost or revoked, create a new JSON key for the
  service account and replace `PLAY_SERVICE_ACCOUNT_JSON`. No app re-keying is
  involved (the app-signing key lives in Play, the upload key is separate).
- Republishing the same tag is rejected by Play (duplicate versionCode); fix a
  bad release with a new patch version, never by re-tagging.

## Native debug symbols — crash symbolication

The app is mostly C++: the carved goldendict-ng engine links into the process, so
almost every crash *is* an engine crash. A stripped native library reports crash
frames as raw addresses, which makes the report useless — so the release AAB
carries each shipped library's symbol table under
`BUNDLE-METADATA/com.android.tools.build.debugsymbols/<abi>/<library>.so.sym`
(AGP's spelling of the AAB's native debug symbols entry; there is no
`BUNDLE/native-debug-symbols/` directory). `SYMBOL_TABLE` level = function names,
which is what a tombstone trace needs. The libraries inside `base/` are shipped
**stripped** — the symbols never reach the user's download.

| | |
| --- | --- |
| Produced by | AGP, from `ndk.debugSymbolLevel 'SYMBOL_TABLE'` + `ndkPath` in the generated `build.gradle` (both applied by `app/build.ps1`) |
| Travels in | the release AAB, so Play associates the symbols with the build automatically — no upload step |
| Also attached to | the GitHub release as `aurelex-native-debug-symbols-<versionCode>-<abi>.zip`, containing `<abi>/<library>.so` |
| Verified by | the release workflow asserts both halves (symbols present per ABI, shipped libs stripped) and refuses to publish otherwise |

`ndkPath` is the load-bearing half, and its absence is silent. AGP runs
`llvm-strip` / `llvm-objcopy` out of an NDK it locates itself, and it only looks
inside the Android SDK (`<sdk>/ndk/<version>`). Ours is installed outside that
tree, so with `ndkVersion` alone AGP finds no toolchain: it logs `Unable to strip
the following libraries, packaging them as they are:` for *every* jniLib (which
ships the ~36 MB unstripped engine binary in `base/`), and extracts no symbols at
all — while the build stays green. Hence the assertion on the artifact rather than
on the Gradle flag.

## Native payload — what actually ships in `lib/<abi>/`

The artifact carries only the Qt libraries the app can reach, not the whole kit.
`app/build.ps1` derives the set with `scripts/derive-native-payload.ps1` (run it
with no arguments to print the kept and dropped libraries with their sizes) and
stages only those, into both `lib/<abi>/` and `assets/qml/`.

| | before | after |
| --- | --- | --- |
| libraries under `lib/<abi>/` | 140 | 52 |
| bytes under `lib/<abi>/` | 86.32 MB | 48.88 MB |
| `assets/qml/` | 696 files / 8.12 MB | 293 files / 1.35 MB |
| release APK | 38.2 MB | 19.9 MB |
| release AAB | 42.1 MB | 23.8 MB |

Measured on Qt 6.6.3, `arm64-v8a`. The 37 MB is unreachable Qt: Designer,
ShaderTools, the Widgets stack, the VirtualKeyboard, three unused Controls
styles, the SQL driver, and the `qmldbg`/`qmllint` developer tooling.

| | |
| --- | --- |
| Produced by | `app/build.ps1` (staging) from `scripts/derive-native-payload.ps1` (the derivation) |
| Verified by | the same release-workflow assertion as above, section 3: a **52 MB** ceiling per ABI plus exact equality between the shipped name set and the derived set |
| On failure | the release is refused before publication |

The **52 MB** ceiling is a backstop for a Qt bump that quietly widens the kit;
exact set equality is the real check, and the workflow re-derives the expected
set through the same script the build stages from, so the two cannot drift. The
ceiling's headroom over the measured 48.88 MB absorbs a patch bump — the smallest
module that could reappear undetected is worth far more than that. Both failure
paths were verified against deliberately broken artifacts: a re-added
`libQt6Designer` fails on reachability, a removed `libqml_QtWebView_*` fails on
absence, and the ceiling fires on size.

### Uploading symbols to Play by hand

Normally you don't. Play associates deobfuscation and symbol files **included in
the app bundle by standard Gradle tasks** with the project and uses them "without
additional work on your part", so an AAB built by this pipeline arrives with its
symbols already attached. The manual route below is the fallback: a release whose
bundle somehow lost them, or a re-upload after the fact.

1. Take `aurelex-native-debug-symbols-<versionCode>-<abi>.zip` from the GitHub
   release (the same run as the AAB).
2. Play Console → the app → **Release** → pick the release whose versionCode
   matches the file name → **App bundle explorer** → the version → **Downloads /
   Native debug symbols** → upload the zip for that ABI. (In the release-review
   screen the same upload lives in the artifacts table's "Assets" row.)
3. Confirm versionCode **and** ABI match before uploading — a symbol file that
   does not belong to the build Play has cannot resolve any of its crash frames.
   The zip must hold the ABI folders at its root (`arm64-v8a/libaurelex_arm64-v8a.so`),
   which is what the workflow produces.

**On the API:** the Play Developer API v3 *does* accept native symbols —
`edits.deobfuscationfiles.upload` with `deobfuscationFileType=nativeCode` — but
its URL is scoped to `apks/{apkVersionCode}`, i.e. it attaches a file to an APK
that the edit uploaded. This project publishes a **bundle**, so there is no such
APK in the edit to attach to; automating that call is not a shape the API offers
for bundle releases. Hence: automatic for the bundle, manual in the Console for
the fallback.

**Which file to use:** not the one Google's docs point at. For APK builds AGP
also writes `build/outputs/native-debug-symbols/release/native-debug-symbols.zip`,
but its members are named `<library>.so.sym` (`arm64-v8a/libaurelex_arm64-v8a.so.sym`),
while the Console's documented layout is `<abi>/<library>.so`. The workflow
therefore assembles its own archive from the bundle's `.sym` entries, renaming
`.sym` → `.so`; the bytes are identical.

Symbols only help crashes Play has already collected, so this matters mostly
*after* a release goes out — the GitHub release asset is the copy to reach for.

### Retention

Keep the symbols archive **at least as long as the Play listing can serve crash
reports for that versionCode** — in practice, keep every release's archive; they
are a few MB each and are the only way to re-symbolicate an old report. Deleting
them makes historical native crash reports unreadable, permanently.

### This is not a crash-reporting SDK

Symbols are a build artifact that feeds *whatever* channel reports crashes. With
them, Android vitals symbolicates native crashes on its own — which is the
channel the README and the privacy policy already describe. Adopting Crashlytics
(or any other reporter) later would *consume the same symbols*, not replace
them, so shipping them is a prerequisite for native-crash diagnosis either way,
not a step toward a particular vendor.

## F-Droid — no cloud signing

F-Droid **has no cloud-key / enrollment service**. It builds the app **from
source** and signs with one of:

- **(a) F-Droid's own key** (default) — F-Droid maintains the signing key; the
  app's F-Droid identity then belongs to F-Droid, not us.
- **(b) Reproducible build / signature copying** — F-Droid rebuilds from source
  and, when the build is reproducible, ships the APK signed with our published
  signature. This does **not** require handing over the private keystore; it
  relies on matching a published APK byte-for-byte (or on F-Droid's
  signature-copying flow). **Not achieved yet**: the Qt/NDK carved engine
  embeds build ids / timestamps, so byte-reproducibility is non-trivial (a
  stretch goal). See `https://f-droid.org/docs/Reproducible_Builds/`.
- **Never give F-Droid the project's private release keystore.** F-Droid does not
  need it, and sharing it would put every GitHub/Play sideload update at risk.
  See `https://f-droid.org/docs/Signing_Process/`.

## Channel separation

Installed signatures differ per channel *by design*:

- Play users get Google's app-signing signature.
- F-Droid / GitHub users get ours.

They are independent install channels; cross-store updates are not expected
(Android blocks an update whose signature differs). To switch channels a user
must uninstall first.

## Keystore hygiene

- Generate the release keystore once (`keytool -genkeypair -v -keystore
  aurelex-release.jks -alias aurelex -keyalg RSA -keysize 4096 -validity 10000`).
- Store it in CI secrets as `AURELEX_KEYSTORE_BASE64` (base64) +
  `AURELEX_KEYSTORE_PASSWORD` / `AURELEX_KEY_ALIAS` / `AURELEX_KEY_PASSWORD`.
- Keep a second, **offline** backup. Losing `AURELEX_KEYSTORE*` (minus what CI
  has) is the single point of failure for F-Droid/GitHub update continuity.
- Never commit the keystore; CI only ever reads it from secrets.

## Letting F-Droid build

F-Droid submits a recipe pointing at this repository and builds from source.
By default F-Droid signs the result with its own key. Do **not** upload the
private release keystore or its passwords. If we later want F-Droid builds to
carry our signature, pursue the reproducible-build / signature-copying path (and
document the exact fingerprint), not keystore sharing.

## App icon & the indexing notification

### App icon

The launcher icon is an adaptive icon (`mipmap-anydpi-v26/ic_launcher.xml`,
`app/android/res/`) with background, foreground, and monochrome layers; the
same vector foreground is reused in the home-screen widget. `minSdkVersion` is
**23** (Qt's default, Android 6.0), so the density-specific
`mipmap-*/ic_launcher.png` legacy fallbacks are kept for API 23–25, which have no
adaptive-icon support. API 26+ uses the adaptive icon.

Known gap (polish TODO): the monochrome (themed-dark) layer is a simple tint of
the book glyph — it was added to satisfy adaptive-icon schema, but hasn't been
given a dedicated monochrome shape or verified on a themed launcher.

### Indexing notification

The engine runs **in-process** in the Qt app (no separate `:engine` process and
no persistent notification). The only notification is the **bulk FTS indexing**
foreground service (`IndexingService`) which shows a transient **"Indexing..."**
notification while a long index build runs, so the build survives the app being
backgrounded. It posts only while indexing is in progress and stops when the
build completes; steady-state lookup has no notification.

- Notification builder: `IndexingService` (channel `aurelex_indexing`, low
  importance), small icon `ic_menu_search`.
- Declared as a foreground service in `AndroidManifest.xml`
  (`FOREGROUND_SERVICE` + `POST_NOTIFICATIONS`).

This is cosmetic and does not affect signing or distribution.