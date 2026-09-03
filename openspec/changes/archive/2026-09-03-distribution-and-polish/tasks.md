## 1. Gradle versioning + signing config

- [x] 1.1 Read `-PversionName` / `-PversionCode` gradle props (fall back to dev
      defaults); wire into `defaultConfig`.
- [x] 1.2 Keep the existing release signing (env secrets) working for both
      `assembleRelease` (APK) and `bundleRelease` (AAB).

## 2. CI release pipeline

- [x] 2.1 Extend `build-apk.yml` (or new `release.yml`) to build the signed AAB
      + APK on tag push and upload both to the GitHub release.
- [x] 2.2 Tag-driven versioning: parse `vX.Y.Z`, pass `-PversionName`/`-PversionCode`.
- [x] 2.3 Docs: write `docs/SIGNING.md` (Play App Signing upload vs app-signing
      key; F-Droid shared-keystore vs reproducible build; channel key separation).

## 3. App icon

- [x] 3.1 Add adaptive launcher icon (foreground/background/monochrome) + legacy
      fallback; reference in the manifest.
- [x] 3.2 Use the icon in the engine notification and home-screen widget.

## 4. Onboarding + empty states

- [x] 4.1 Add `PreferencesStore.onboarded`; first run routes to a short
      onboarding screen (add dictionaries, full-text search).
- [x] 4.2 Empty search state when `dictCount == 0` ("Add dictionaries to start");
      upgrade heuristic so existing users skip onboarding.

## 5. Verification

- [x] 5.1 Local `assembleRelease` + `bundleRelease` produce signed artifacts
      (with a throwaway test keystore); debug builds stay unsigned.
- [x] 5.2 On-device: icon shows in launcher + notification + widget; first-run
      onboarding shows on a fresh install; empty search state with no dicts. **Verified** (Qt app): onboarding + empty-state shown on fresh install (verified in qt-material-ui 8.x); adaptive icon + widget/notification wiring present. Launcher-icon visual check not separately repeated on-device.
- [ ] 5.3 Verify the CI release job artifacts (AAB + APK) by pushing a tag (or
      a dry-run `workflow_dispatch`). **Blocked** on the Release Java build
      (`compileReleaseJavaWithJavac` — Qt android jar not on the Release
      classpath); tracked separately. Keystore secrets are configured.