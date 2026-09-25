# Signing, Distribution & App Identity

How Aurelex is signed, where each artifact goes, and how the app presents
itself (icon + notification). Two independent signing channels by design —
Google Play and F-Droid are separate install channels with different
signatures.

## Artifacts produced by CI

On a `vX.Y.Z` tag push, CI (`.github/workflows/release-qt.yml`, windows-latest)
builds a signed release APK **and** AAB from the Qt app (`app/`) and
attaches both to a GitHub release:

| Artifact | Path | Used by |
| --- | --- | --- |
| `.apk` | `build-qtquick/apk/build/outputs/apk/release/aurelex-release.apk` | GitHub releases / F-Droid / sideload |
| `.aab` | `build-qtquick/apk/build/outputs/bundle/release/aurelex-release.aab` | Google Play upload |

(`app/build.ps1 -Configuration Release -Bundle` produces the same pair
locally.) `versionName` is the tag (`vX.Y.Z` → `X.Y.Z`); `versionCode` is derived
deterministically as `major*10000 + minor*100 + patch`. Locally (no props)
builds fall back to `versionCode 1` / `versionName 0.0.1`.

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

## F-Droid — no cloud signing

F-Droid **has no cloud-key / enrollment service**. It builds the app **from
source** and signs with one of:

- **(a) F-Droid's own key** (default) — F-Droid maintains the signing key; the
  app's F-Droid identity then belongs to F-Droid, not us.
- **(b) Reproducible build / signature copying** — F-Droid rebuilds from source
  and, when the build is reproducible, ships the APK signed with our published
  signature. This does **not** require handing over the private keystore; it
  relies on matching a published APK byte-for-byte (or on F-Droid's upstream
  signature-copying flow). **Not achieved for v1**: the Qt/NDK carved engine
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
same vector foreground is reused in the home-screen widget. `minSdk 28` (API 26+)
means no legacy PNG fallback is needed.

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