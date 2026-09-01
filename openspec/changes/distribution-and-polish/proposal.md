## Why

The app is feature-complete for the v1 scope (search, dictionaries, groups,
full-text search, utilities, quick-lookup), but it is not distributable: it
ships `versionCode 1` with no release pipeline that produces installable,
signed artifacts across real stores, has no app icon or first-run guidance, and
has no path onto Google Play or F-Droid. This change ships the app properly.

## What Changes

- **Signed CI releases.** CI builds a signed **AAB** (for Google Play) and a
  signed **APK** (for GitHub releases and F-Droid sideload), signed with a
  private keystore passed via CI secrets (never committed). `versionCode`/
  `versionName` are derived from the release tag instead of a fixed `0.1.0`.
- **Signing strategy, two distinct channels (design D1):**
  - **Google Play App Signing:** we keep the *upload key*; Google holds the
    *app signing key* and re-signs the AAB for Play delivery.
  - **F-Droid:** we provide our release-key fingerprint/keystore so F-Droid's
    source-built APKs share our signature. (Reproducible builds are a stretch,
    not a v1 commitment.)
- **App icon.** A proper adaptive launcher icon replaces the default, and is
  reused in the notification and home-screen widget.
- **Onboarding + empty states.** A first-run screen and helpful empty states
  (no dictionaries yet; empty full-text search results).

## Capabilities

### New Capabilities
- `distribution-and-polish`: signed release delivery to Google Play / F-Droid /
  sideload, plus first-run onboarding and app identity (icon).

### Modified Capabilities
- none

## Impact

- `app/build.gradle.kts` — versionCode/versionName automation, AAB + signing
  config, adaptive-icon packaging.
- `.github/workflows/` — extend/replace `build-apk.yml` to emit a signed AAB +
  APK; keystore secrets; tag-driven versioning.
- Resources — adaptive launcher icons; onboarding + empty-state Compose UI.
- F-Droid metadata (build recipe / signing note) if added in this pass.
- Docs — signing workflow notes (Play upload vs app-signing key; F-Droid key
  sharing vs reproducible builds).
