## Context

See `proposal.md` — Why for the motivation. The mechanical facts that shape the
approach:

- `app/CMakeLists.txt:139-148` resolves the vendored TLS libraries from
  `app/openssl/${ANDROID_ABI}` and appends them to `QT_ANDROID_EXTRA_LIBS`, which
  is what makes `androiddeployqt` copy them into the packaged artifact. The
  guard is a `message(WARNING)`, and it tests only `libcrypto_3.so`'s existence,
  not `libssl_3.so`'s.
- `.gitignore:26` is a blanket `*.so`, which is correct for the build output it was
  written for (NDK/vcpkg artifacts) and wrong for the one vendored directory. It
  also means `git clean -xdf` deletes the vendored libraries outright.
- The release workflow checks the repository out and shells out to
  `app/build.ps1`; it installs Qt, the NDK, the SDK, vcpkg, and xapian, and fetches
  nothing else. The `*.so` files were therefore the only build input that a CI
  checkout could not supply — and the only one the build treated as optional.
- This project does not use `qt_add_apk_target` (absent from the installed carve
  subset — see the comment at `app/CMakeLists.txt:149-151`). The artifact is
  packaged manually via `androiddeployqt --no-build`, and the release workflow
  builds `android_arm64_v8a` only. So `CMAKE_BUILD_TYPE` is the sole build-type
  signal available, and it is not reliably set on that path.
- The four vendored files are sound: each is a valid ELF64 shared object whose
  machine type matches its ABI directory (AArch64 for `arm64-v8a`, x86-64 for
  `x86_64`), and both `libcrypto_3.so` builds report OpenSSL 3.1.8.

## Goals / Non-Goals

**Goals:**

- A fresh `git clone` + `app/build.ps1` produces an artifact with working Qt TLS,
  with no step that depends on state outside the checkout.
- A checkout that cannot produce such an artifact fails the build, loudly, in
  every configuration.
- The packaged artifact is verified to contain the libraries before publication.
- The committed binaries are identifiable — upstream project, upstream revision,
  OpenSSL version, and a digest per file.

**Non-Goals:**

- Moving the catalog off the temporary Seafile share, or any other catalog
  hosting change. That is a separate concern with its own decisions.
- Certificate pinning, a custom TLS backend, or any other network hardening.
- Bumping Qt, the NDK, or the vendored OpenSSL version. This change records the
  provenance of what is already vendored; upgrading the bits is its own change.
- `x86_64` in CI. The release workflow builds one ABI; the check is written per
  built ABI rather than hardcoded to a list.

## Decisions

### Commit the binaries; do not fetch them at build time

The libraries go into version control, with a `.gitignore` negation scoping the
exception to `app/openssl/`.

Rationale: it is the only option under which the build has no dependency on
something outside the tree, which is the actual defect being fixed. The repo
already vendors an entire C++ engine as a submodule, so tracked binaries are not
foreign to it, and the total cost is ~10.4 MB (arm64 ~4.6 MB, x86_64 ~5.8 MB) —
small enough that a fetch step would buy nothing. It also keeps builds offline
and reproducible, which is what `app/openssl/README.md` already claims for them.

*Alternative considered — CI fetches the pinned libs from KDAB/android_openssl.*
Keeps the repo lean and allows a checksum-pinned upgrade without a code change.
Rejected: it re-creates the failure class being fixed (the build silently depends
on a step that can be skipped or fail open), it adds a network dependency to a
25-40 minute pipeline, and it leaves local builds on a different code path than CI
— the exact maintainer-only/CI divergence that produced this bug.

### Use a `.gitignore` negation, not a bare force-add

Add `!app/openssl/**/*.so` immediately after the `*.so` rule, then add the files
normally.

Rationale: force-adding alone gets the bytes into the tree, but the paths stay
*ignored*. That means `git clean -xdf` — a normal thing to run when a build goes
weird — silently deletes them again and reproduces this bug from a clean-looking
working tree. The negation makes the vendored directory un-ignored, so `git
clean` leaves it alone, and it self-documents why one directory is exempt from
the rule that protects build output everywhere else.

*Alternative considered — drop `*.so` and re-ignore build output by path.* More
precise, but it widens the diff into ignore rules for NDK/vcpkg output that are
correct today and would need auditing. A narrow negation touches one line.

### Make the missing-library branch fatal in every configuration

Replace the `message(WARNING)` with `message(FATAL_ERROR)`, and check **both**
`libcrypto_3.so` and `libssl_3.so` rather than only the former.

Rationale: with the files tracked, their absence means a broken or hand-pruned
tree, and no configuration in which the app builds without them is useful — the
catalog fetch is the app's only Qt-network feature, so such a binary is broken in
a way nothing else reveals. The error names the missing path and points at
`app/openssl/README.md`.

Extending the check to `libssl_3.so` closes a real hole: the current guard passes
on `libcrypto_3.so` alone, so a checkout missing only `libssl_3.so` takes the
success branch and fails later, further from the cause.

*Alternatives considered.* (a) Fatal only for release/bundle builds: needs a
reliable "is this a release build" signal, and per the Context section
`CMAKE_BUILD_TYPE` is not reliably set on the manual packaging path — a
conditional guard would be unreliable exactly where it matters. (b) Keep the
warning: that is the bug. (c) Add a separate CI-only assertion instead of a CMake
guard: leaves local builds able to produce the same broken artifact, so the
defect survives for anyone not using CI.

### Verify the packaged AAB and APK, per built ABI

After packaging, list the zip entries of the produced AAB and APK and assert that
each contains the vendored libraries for the ABI that was built
(`base/lib/<abi>/libcrypto_3.so` and `libssl_3.so` in the AAB, `lib/<abi>/…` in
the APK). Use `System.IO.Compression.ZipFile` in PowerShell, since the job runs on
`windows-latest` where `unzip` is not guaranteed.

Rationale: verifying the artifact that actually reaches Play is strictly stronger
than verifying the build tree, and it is the check that would have caught this
even if the CMake guard were bypassed. Both outputs are already located by the
existing artifacts step, so this adds one step and no new tooling. Per-ABI rather
than a hardcoded list, so adding an ABI to the workflow needs no edit here.

*Alternative considered — device smoke test.* Would prove the feature end to end,
but needs a device in CI and takes minutes; the whole point is to catch this
without one.

### Record provenance in the README, as a table

Extend `app/openssl/README.md` with the upstream project and exact
KDAB/android_openssl revision the binaries were taken from, the OpenSSL version
they report (3.1.8), and a SHA-256 per file.

Rationale: "the exact bits that ship are pinned in the repo" is only true if the
bits can be identified and checked. Digests also make a future upgrade
reviewable — a diff of the table shows exactly which files moved.

*Alternative considered — a machine-readable `CHECKSUMS` file.* A second file to
keep in sync with the binaries; for four files a table in the existing README is
reviewable in the same diff as the binaries themselves.

## Risks / Trade-offs

- **~10.4 MB added to git history, permanently** → Mitigated by committing once:
  the cost is paid a single time and does not grow per upgrade. Library upgrades
  are infrequent and are single deliberate commits, so the marginal cost is low.
- **The fatal guard blocks a developer whose tree is genuinely broken** →
  Intended, and the error names the path plus the remedy. Recovery is
  `git checkout -- app/openssl`; because the paths are no longer ignored,
  `git clean -xdf` no longer creates the condition in the first place.
- **The packaging check could false-negative if `androiddeployqt` changes the
  artifact layout** → Accepted: the check names the exact expected entries, so a
  layout change fails loudly with a one-line fix, which is strictly better than
  the silent omission this change exists to prevent.
- **Committing third-party binaries raises a supply-chain and licence question** →
  Mitigated: OpenSSL 3.x is Apache-2.0 and the licence is already documented in
  `app/openssl/README.md`; these are the same bits local builds have been shipping
  and device-testing; and the recorded digests make them auditable. The repo's own
  GPLv3 licence is unaffected — the addition is permissive and separately
  attributed.
- **The already-published Play internal-test build stays broken** → Out of scope
  here by decision; it is fixed by cutting a new release tag from the fixed tree
  (see Migration Plan). No user-visible string changes, so no translation work
  is triggered.

## Migration Plan

1. One commit: the `.gitignore` negation, the four binaries, the README
   provenance table, the fatal CMake guard (both files checked), and the CI
   packaging assertion.
2. Verify locally that `app/build.ps1` still configures and packages, and that
   the packaging check passes against a real artifact.
3. Cut a new release tag. The release workflow builds from the fixed tree and
   publishes to Play internal testing, which is what actually replaces the
   currently broken build on users' devices.
4. Confirm on device that the catalog pane lists the entry.

Rollback: revert the commit. There is no operational state to unwind — the
pre-change behavior was a build that passed CI and shipped an artifact with dead
TLS, so reverting restores that, not a working state.
