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
| `.apk` | `build-qtquick/apk/build/outputs/apk/release/*.apk` | GitHub releases / F-Droid / sideload |
| `.aab` | `build-qtquick/apk/build/outputs/bundle/release/*.aab` | Google Play upload |

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