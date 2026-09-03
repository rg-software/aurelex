## Context

The app currently ships `versionCode 1` / `versionName 0.1.0` hard-coded in
`app/build.gradle.kts`. `build-apk.yml` already signs a release APK with a
keystore from env secrets and drafts a GitHub release on tag push. There is no
AAB output, no versioning automation, no adaptive icon (the engine notification
uses `android.R.drawable.ic_menu_search`), and the first screen is a bare search
field with no guidance.

Motivation and scope: see proposal.md.

## Goals / Non-Goals

**Goals**
- CI emits signed, installable artifacts for Google Play (AAB) and
  GitHub/F-Droid/sideload (APK), with tag-derived versioning.
- Documented, correct signing strategy per channel (this is the crux).
- Adaptive app icon reused in notifications + widget.
- First-run onboarding + helpful empty states.

**Non-Goals**
- Actually submitting to Play Console / F-Droid (accounts + review are manual).
- Reproducible byte-identical native builds (v1 uses the shared-keystore path).
- Store listings/listing copy, screenshots, Play console setup automation.

## Decisions

### D1: Two independent signing channels — Play App Signing vs F-Droid
**Google Play App Signing** uses two keys. We generate an **upload key**
(stored in CI secrets, used to sign the AAB we upload). Google holds the **app
signing key** in their cloud and re-signs the AAB into the APKs users install;
it supports key-loss recovery and export. This is the only "cloud signing"
involved.

**F-Droid has no cloud-signing service.** It builds the app from source and
signs with one of: (a) a keystore we provide, (b) F-Droid's own maintained key
if we provide none, or (c) a reproducible-build match where the source-built
APK byte-matches one we publish, effectively using our signature without us
sharing the keystore. For v1 we choose **(a): provide our release keystore to
F-Droid** (or its public-key fingerprint) so F-Droid builds carry our
signature. (c) is a documented stretch — the Qt/NDK carve embeds build ids and
timestamps, so byte-reproducibility is non-trivial.

Consequence: signatures differ per channel (Play = Google's app-signing key,
F-Droid/GitHub = ours). That is correct and intended; each store is an
independent install channel and cross-store updates are not expected.

### D2: Versioning from the release tag
`versionCode` must be monotonically increasing; `versionName` is human-facing.
CI parses the `vX.Y.Z` tag pushed to GitHub, writes
`-PversionName=X.Y.Z -PversionCode=<N>` to the Gradle build, and `build.gradle.kts`
reads them as gradle properties (falling back to dev defaults). versionCode is
derived deterministically (e.g. `major*10000 + minor*100 + patch*100 + build`,
or an explicit per-release bump).

### D3: Artifact shape + signing config in Gradle
- `assembleRelease` → signed APK (release key from env/secrets) for GitHub +
  F-Droid.
- `bundleRelease` → signed AAB (same keys) for Google Play upload; Play
  re-signs with its app-signing key on ingest.
- The existing `hasSigningConfig` block stays; extend to tag-driven props.
- Keep local unsigned debug builds working (no keystore locally).

### D4: Adaptive launcher icon
Add `mipmap-anydpi-v26/ic_launcher.xml` (adaptive: foreground + background
layers) with a monochrome variant, plus legacy fallbacks. Reference it from the
manifest and reuse it in the engine notification + widget RemoteViews.

### D5: Onboarding + empty states
Add a `PreferencesStore.onboarded` flag. First launch routes to a short
onboarding screen (add dictionaries → full-text search). The search screen
shows an explicit "Add dictionaries to start" empty state when
`dictCount == 0`. Both pure Compose/Kotlin; no engine involvement.

## Risks / Trade-offs

- [Losing the upload key] → Mitigation: Play Console reset exists; keep a
  second private backup (offline), never in CI secrets only.
- [Losing the F-Droid signing key would break updates] → Mitigation: the same
  release keystore we share with F-Droid must be backed up offline; a lost key
  forces F-Droid users to reinstall.
- [Reproducible build not achieved → F-Droid must hold the keystore] →
  Mitigation: accepted trade-off; document that sharing the keystore with
  F-Droid means they hold a copy — adversarial-risk is low for this project;
  revisit reproducible builds later.
- [AAB requires Google to hold app-signing key; can't disable for new apps] →
  Mitigation: accepted; document that Play-installed signatures differ from
  sideload, and that downgrade/re-install from a different channel needs
  uninstall (Play protects with its own signature).
- [Icons/onboarding are cosmetic; could be churned] → Mitigation: keep them
  minimal, single-purpose, and consistent with the current design system.

## Migration Plan

No on-disk schema changes. On first run after upgrade, existing users skip
onboarding via the `onboarded` flag (defaults to true if the flag is absent and
`history`/`scanPath` already exists — a heuristic). Signing keys are generated
once and stored offline + in CI secrets; Play enrollment is a one-time manual
step in Play Console.

## Open Questions

None resolved now would change the specs — Play/F-Droid key provisioning and the
exact tag→versionCode mapping are implementation details contained by D1/D2.