## Why

Today the release workflow builds a signed AAB but stops at the GitHub release:
getting it into Google Play's internal testing track is a manual Play Console
upload. For a small team that means every tagged release needs a human in the
loop just to hand the AAB to Play, and the manual step is easy to skip or point
at the wrong track. Publishing to internal testing should be a consequence of
pushing a release tag.

## What Changes

- **Auto-publish the tagged AAB to Play internal testing.** On a `vX.Y.Z` tag
  push, after the signed AAB is built, CI uploads it to the app's **internal**
  testing track via the Google Play Android Developer API, using a service
  account stored as a secret. The signed APK still goes to the GitHub release
  and F-Droid/sideload (APK covers F-Droid/sideload).
- **Tag-only guard.** Publishing runs only for well-formed release tags
  (`vX.Y.Z`, each component `< 100`), so the deterministic
  `versionCode = major*10000 + minor*100 + patch` cannot collide and the
  `workflow_dispatch` dry-run stays a build-only path. Master pushes are never
  published.
- **Non-destructive failure.** If the Play publish fails (bad/expired credential,
  API error), the signed APK + AAB are still attached to the GitHub release; only
  the Play step fails.
- **Docs.** `docs/SIGNING.md` and the distribution spec gain the internal-track
  publishing flow and the service-account setup it requires.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `distribution-and-polish`: the Google Play signing requirement gains
  automatic publication of the tagged release AAB to the internal testing track
  via the Play Developer API, and the signed-artifacts requirement gains the
  tag-format guard that keeps tag-derived versionCodes collision-free.

## Impact

- `.github/workflows/release-qt.yml` — new publish step (Play Developer API)
  gated on a well-formed tag; keeps the existing GitHub-release step.
- CI secrets — a new `PLAY_SERVICE_ACCOUNT_JSON` (Google Cloud service account
  with Play Console release access); no change to the existing keystore secrets.
- `docs/SIGNING.md` — document the service account, Play Console grant, track
  target, and the tag-only policy.
- No application, carve, or engine code changes; no `versionCode` scheme change.
