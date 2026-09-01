# Signing, Distribution & App Identity

How Aurelex is signed, where each artifact goes, and how the app presents
itself (icon + notification). Two independent signing channels by design —
Google Play and F-Droid are separate install channels with different
signatures.

## Artifacts produced by CI

On a `vX.Y.Z` tag push, CI (`.github/workflows/build-apk.yml`) builds two signed
artifacts and attaches them to a GitHub release:

| Artifact | Path | Used by |
| --- | --- | --- |
| `.aab` | `app/build/outputs/bundle/release/app-release.aab` | Google Play (upload) |
| `.apk` | `app/build/outputs/apk/release/app-release.apk` | GitHub releases / F-Droid / sideload |

`versionName` is the tag (`vX.Y.Z` → `X.Y.Z`); `versionCode` is derived
deterministically as `major*10000 + minor*100 + patch`. Locally (no props)
builds fall back to `versionCode 1` / `versionName 0.1.0`.

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

- **(a) Our keystore** (chosen for v1) — we give F-Droid our release keystore
  (or its public fingerprint) so every source-built APK carries our signature.
  Requires keeping an offline backup: losing it breaks F-Droid updates.
- **(b) F-Droid's own key** — if we provide none, F-Droid maintains a key; the
  app's identity on F-Droid then belongs to F-Droid, not us.
- **(c) Reproducible build** — F-Droid byte-compares its source build to a
  published APK of ours; identical ⇒ interchangeable, using our signature
  *without* sharing the keystore. **Not achieved for v1**: the Qt/NDK carved
  engine embeds build ids / timestamps, so byte-reproducibility is non-trivial
  (a stretch goal).

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

F-Droid submits a recipe pointing at this repository. For path (a): upload our
keystore to F-Droid's submission form (#F-Droid requests the
`keystore/release signature`). Provide:
- the release keystore (or its SHA256 certificate fingerprint),
- the alias + passwords used by CI.

F-Droid then signs every build it produces from source with our key, keeping
updates compatible with GitHub/Play-upload sideloads.

## App icon & the engine notification

### App icon
The launcher icon is an adaptive icon (`mipmap-anydpi-v26/ic_launcher.xml`,
`app/src/main/res/`) with background, foreground, and monochrome layers; the
same vector foreground is reused in the engine notification and the home-screen
widget. `minSdk 28` (API 26+) means no legacy PNG fallback is needed.

Known gap (polish TODO): the monochrome (themed-dark) layer is a simple tint of
the book glyph — it was added to satisfy adaptive-icon schema, but hasn't been
given a dedicated monochrome shape or verified on a themed launcher.

### Engine notification icon
The `:engine` process runs as a **foreground service** (Android 8+ requires a
persistent notification for any long-lived background service; it also keeps the
engine alive across activity recreation, e.g. after a SAF folder grant restarts
the activity, and during long-running dictionary scanning/indexing).

- Notification builder: `EngineService.onCreate` (channel `aurelex_engine`,
  low importance).
- `setSmallIcon(R.drawable.ic_launcher_foreground)` — the app's book glyph as a
  small monochrome status icon.

**Status / plan:** the small-icon change from the Android default (`ic_menu_search`)
to `ic_launcher_foreground` is in code and the notification posts, but the glyph
is small and monochrome, so it is hard to visually distinguish from the stock
icon in the shade. Two documented follow-ups (deferred to a polish pass):
1. **Dedicated notification glyph** — a purpose-made small icon (sized/styled
   for status-bar rendering) rather than reusing the launcher foreground.
2. **Hide when in foreground (Android 13+)** — consider suppressing the
   notification while the Aurelex UI is visible (the standard pattern for
   always-on engine services), keeping it only in the background.

Nothing here affects signing or distribution; it is cosmetic.