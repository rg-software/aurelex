## 1. Release workflow: tag-only publish gate

- [x] 1.1 Extend the tag-derivation step in `.github/workflows/release-qt.yml` so a well-formed `^v([0-9]+)\.([0-9]+)\.([0-9]+)$` tag with every component `< 100` sets a positive publish gate (e.g. `AURELEX_PUBLISH=1`); any other ref leaves it unset.
- [x] 1.2 Verify a non-release ref (manual `workflow_dispatch` and a branch push) produces a build with no publish gate and no store publish.

## 2. Play publish step

- [x] 2.1 Add a publish step after artifact upload, gated on the publish gate, using a pinned `r0adkll/upload-google-play` (or `fastlane supply`) version, `track: internal`, completed release, reading `PLAY_SERVICE_ACCOUNT_JSON`.
- [x] 2.2 Confirm the step cannot run when the gate is unset and cannot run before the signed AAB is located.
- [x] 2.3 Ensure a publish failure fails the workflow but the GitHub-release step has already attached APK + AAB.

## 3. Secrets and Play Console setup (manual, one-time)

- [x] 3.1 Create a Google Cloud service account with the Play Android Developer API enabled and store its JSON key as the `PLAY_SERVICE_ACCOUNT_JSON` repo secret.
- [x] 3.2 Grant that service account release access to the Aurelex app in Play Console (release-only, single app).

## 4. Docs

- [x] 4.1 Update `docs/SIGNING.md`: the service account, Play Console grant, internal-track target, tag-only policy, and credential rotation.
- [x] 4.2 Note the tag-only policy and the new secret in the `release-qt.yml` header comment.

## 5. Verification

- [x] 5.1 Dry-run the publish path against a throwaway tag on a fork/test Play listing (or `workflow_dispatch` with the gate forced), confirming the AAB reaches the internal track and the release still carries both artifacts.
- [x] 5.2 Confirm the real next `vX.Y.Z` tag publishes automatically with no manual Play Console step.
