## Why

The Google Play internal-test build cannot fetch the remote dictionary catalog:
every Qt-network HTTPS request fails at runtime with "TLS initialization failed".
The catalog itself is healthy — the compiled-in Seafile share answers `200` with
a valid `schemaVersion: 1` manifest over a trusted certificate — so the defect is
in the shipped artifact, not the catalog.

Root cause: the vendored Android OpenSSL libraries the app's TLS depends on are
**untracked**. `.gitignore` excludes `*.so`, so `git ls-tree HEAD -- app/openssl`
yields only `README.md`; the four `.so` files exist solely in the maintainer's
local working tree. `release-qt.yml` checks the repository out and calls
`app/build.ps1`, which fetches nothing, so CI takes the `message(WARNING)` branch
at `app/CMakeLists.txt:145` and produces an APK/AAB with no `libssl_3.so`. Qt's
Android TLS is the OpenSSL backend and `dlopen()`s those libraries at run time
with no fallback, so the artifact has no working TLS. The WebView is unaffected
(Chromium bundles its own BoringSSL), which is why nothing else in the app looks
broken and the failure presented as a catalog problem.

`app/openssl/README.md` states the intent — "the exact bits that ship are pinned
in the repo" — but the ignore rule silently defeated it, and the guard that
should have caught it was a warning on a build that then published to a store.

## What Changes

- **Track the vendored OpenSSL libraries** for every ABI the app builds
  (`arm64-v8a`, `x86_64`) by adding a negation to `.gitignore` after the blanket
  `*.so` rule, so a fresh `git clone` carries them and CI picks them up.
- **Make a missing vendored TLS library a hard build error.** Replace the
  `message(WARNING)` fallback in `app/CMakeLists.txt` with `message(FATAL_ERROR)`
  for every configuration, so a checkout that cannot produce a working-TLS
  artifact fails at configure time instead of publishing a broken one to a store.
- **Record the upstream provenance** of the committed binaries — the exact
  KDAB/android_openssl ref and the per-file checksums — in `app/openssl/README.md`,
  so the bits that ship are traceable and upgradable rather than merely present.
- **Add a CI assertion that the packaged artifact contains the libraries**, so a
  future packaging or ABI change that drops them is caught by the build that
  publishes, not by a user on a device.

No user-visible behavior changes other than the catalog working as specified in a
distributed build. Not a breaking change.

## Capabilities

### New Capabilities

None. This change hardens how an existing capability is delivered; it introduces
no new user-facing surface.

### Modified Capabilities

- `distribution-and-polish`: adds a requirement that a release build be
  self-contained — the checkout must supply every vendored native library the
  artifact `dlopen()`s at run time, a missing one must fail the build rather than
  warn, and the packaged artifact must be verified to contain them.
- `remote-dictionary-catalog`: adds a scenario to *Catalog availability* stating
  that a build obtained from a release channel — not a developer machine — can
  complete the catalog fetch over TLS, so the transport failure mode is a
  detectable build defect rather than a user-facing catalog outage.

## Impact

- **`.gitignore`**: one negation rule after the `*.so` line; no other ignore
  behavior changes.
- **`app/openssl/`**: four binary files (arm64-v8a ~4.6 MB, x86_64 ~5.8 MB) become
  tracked; `README.md` gains the upstream ref and checksums.
- **`app/CMakeLists.txt`**: the missing-library branch becomes fatal. Every build
  now requires the vendored libraries to be present — which is the point, but it
  does mean a partial or hand-pruned working tree no longer builds.
- **`.github/workflows/release-qt.yml`**: one post-build assertion step. No change
  to the signing, versioning, or Play publish logic.
- **No engine, carve, patch, or boundary change.** This is packaging and CI only,
  so it does not touch `engine/`, `carve/`, or `patches/`.
- **No user-visible strings change**, so no `app/i18n/*.ts` or
  `app/android/res/values*/strings.xml` update is required.
- **Follow-up outside this change**: the already-published Play internal-test
  build stays broken until a new release tag is cut from a fixed tree.
