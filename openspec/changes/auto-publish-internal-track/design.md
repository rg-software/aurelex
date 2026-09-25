## Context

See `proposal.md` — Why. Constraints that shape the approach:

- The release workflow (`.github/workflows/release-qt.yml`) already exists, is
  tag-gated, and produces the signed AAB (`bundleRelease`) and APK on
  `windows-latest`. The publish step slots into it after the artifacts are
  located.
- The first AAB of the app was already uploaded to Play by hand (internal
  testing works today), so Play App Signing is configured and API uploads are
  permitted. This is a hard prerequisite for any automation and is satisfied.
- `versionCode = major*10000 + minor*100 + patch` is computed in bash from
  `GITHUB_REF_NAME` and is only meaningful for release tags.
- Signing material already lives in CI secrets (`AURELEX_KEYSTORE_*`); this
  change adds one more secret and must not disturb that flow.

## Goals / Non-Goals

**Goals:**
- A `vX.Y.Z` tag push ends with the signed AAB on the internal testing track,
  with no manual Play Console step.
- Master and `workflow_dispatch` runs stay build-only; no store publishing.
- The GitHub release (APK + AAB) is produced regardless of Play outcome.
- The publish credential is used from a secret only.

**Non-Goals:**
- Publishing to closed/open/production tracks, or staged rollouts.
- Publishing the APK anywhere but the GitHub release (F-Droid builds from
  source).
- Changing the tag-derived `versionCode` scheme.
- A human approval gate on the publish step (tag push is the trigger of record).

## Decisions

### D1: Trigger is the tag, and only the tag
Publishing is gated on a successful regex match of `GITHUB_REF_NAME` against
`^v([0-9]+)\.([0-9]+)\.([0-9]+)$` **and** each component `< 100`. The same
predicate that computes the versionCode decides whether the publish step runs,
so "we can encode a version" and "we may publish" can never disagree.
*Alternative considered:* publishing every successful build on master with a
run-number versionCode — rejected: it inflates permanent Play version slots,
contradicts the documented tag-driven channel, and risks shipping unverified
in-progress work (see the discussion that produced this change).

### D2: Service account via Play Developer API, not a Play Console plugin-only flow
Use a Google Cloud service account JSON key (secret `PLAY_SERVICE_ACCOUNT_JSON`)
with release access granted in Play Console, and publish with an existing
action (e.g. `r0adkll/upload-google-play`) or `fastlane supply`.
*Alternatives considered:*
- *Gradle Play Publisher (GPP) plugin* — would require restructuring the
  Qt-generated Gradle project and adding a plugin dependency to CI; the AAB is
  already built by `build.ps1`, so a post-build API upload is less invasive.
- *Manual upload* — the status quo this change removes.

### D3: Internal track, release as a completed release
Publish with `track: internal` and mark the release completed, so the build is
immediately available to internal testers (no staged-rollout semantics on this
track). Release notes may be blank initially.
*Alternative considered:* `draft` release status — rejected as it still requires
a Console action to become visible, defeating the purpose.

### D4: Play failure is non-fatal to the release
The GitHub-release step runs independently of the publish step, and the publish
step is placed after artifact upload. A Play failure fails the workflow (so it
is visible) but the signed artifacts remain attached to the release.
*Alternative considered:* making Play publish a required success before the
GitHub release — rejected: a transient Google API outage should not cost the
release artifacts.

### D5: No concurrency inference from versionCode
Because only tags publish and tags are unique, no explicit concurrency guard is
required beyond what tag gating gives; a re-push of the same tag is the only
duplicate case and Play rejects a repeated versionCode (surfaced as a workflow
failure).

## Risks / Trade-offs

- **Credential expiry / revocation** → publish step fails loudly, release
  artifacts survive (D4); document rotation in `docs/SIGNING.md`.
- **Service account over-privileged** → grant release-only access to this one
  app in Play Console, not account-admin; the key is one file in secrets, never
  in the repo.
- **Tag re-push creates a duplicate versionCode** → Play rejects it; the failure
  is explicit. Deleting and re-tagging a fixed release needs a new patch version.
- **Play API surface changes** → pinned action version; the step is isolated so
  a fix touches only that step.
