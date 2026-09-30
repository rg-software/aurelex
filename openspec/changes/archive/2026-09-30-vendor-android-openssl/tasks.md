## 1. Track the vendored libraries

- [x] 1.1 Add `!app/openssl/**/*.so` to `.gitignore` immediately after the `*.so` rule on line 26, with a short comment saying the vendored Android OpenSSL is intentionally tracked and is not build output
- [x] 1.2 `git add` the four libraries — `app/openssl/arm64-v8a/libcrypto_3.so`, `app/openssl/arm64-v8a/libssl_3.so`, `app/openssl/x86_64/libcrypto_3.so`, `app/openssl/x86_64/libssl_3.so` — and confirm `git ls-files app/openssl` lists all four
- [x] 1.3 Verify `git check-ignore -v` matches none of the four paths, and that `git clean -xdn` does not list them (the point of the negation: `git clean -xdf` must not be able to delete the vendored libraries)
- [x] 1.4 Confirm the rest of the ignore behavior is unchanged: a scratch `.so` under a build directory is still ignored

## 2. Record the provenance of the committed bits

- [x] 2.1 Establish the exact upstream provenance of the vendored libraries: the KDAB/android_openssl ref or commit the four files were taken from, and the OpenSSL version they report (already confirmed as 3.1.8 in both `libcrypto_3.so` builds)
- [x] 2.2 Add a provenance table to `app/openssl/README.md` giving, per file, the path, byte size, and SHA-256 digest, plus the upstream project, the upstream ref, and the OpenSSL version
- [x] 2.3 Re-read the README's "Why vendored" section and correct any wording that is not true after this change — in particular make explicit that the bits are tracked in the repository and that a build fails without them

## 3. Make a missing vendored library a build error

- [x] 3.1 In `app/CMakeLists.txt`, replace the `message(WARNING "no vendored OpenSSL for ABI ...")` fallback (line 146) with `message(FATAL_ERROR ...)`
- [x] 3.2 Extend the guard so it checks **both** `libcrypto_3.so` and `libssl_3.so` rather than only `libcrypto_3.so` (line 140), so a tree missing only `libssl_3.so` cannot take the success branch
- [x] 3.3 In the error message, name every missing path and point at `app/openssl/README.md`; note the recovery command (`git checkout -- app/openssl`)
- [x] 3.4 Verify the guard: temporarily move `app/openssl/<abi>` aside, confirm configure fails with the new message rather than warning, restore it, and confirm configure passes again
- [x] 3.5 Re-read the `docs/DEVELOPMENT.md:40-43` paragraph on Android TLS and correct it if it describes the vendored libraries as optional

## 4. Verify the packaged artifact before publication

- [x] 4.1 Add a step to `.github/workflows/release-qt.yml` after the "Locate release APK + AAB" step that opens the AAB and the APK as zip archives and asserts the vendored libraries are present for every ABI the workflow builds
- [x] 4.2 Use `System.IO.Compression.ZipFile` in PowerShell (the job is `windows-latest`; `unzip` is not guaranteed), and derive the expected ABI list from what the workflow builds rather than hardcoding it
- [x] 4.3 On failure, print the expected entry paths and the entries actually found, so a layout change in `androiddeployqt` is a one-line fix rather than a mystery
- [x] 4.4 Exercise the check against a real artifact: confirm it passes on a locally built AAB/APK, and confirm it fails when an expected entry is absent

## 5. Verify and land

- [x] 5.1 Run the full `app/build.ps1` locally and confirm the packaged artifact contains the vendored libraries for the built ABI
- [ ] 5.2 Confirm on device that the catalog pane fetches and lists the Seafile catalog entry — the behaviour that was broken in the Play build
- [x] 5.3 Check `git status` shows only the intended paths: `.gitignore`, `app/openssl/`, `app/CMakeLists.txt`, `.github/workflows/release-qt.yml`, optionally `AGENTS.md` / `docs/DEVELOPMENT.md`, and this change's artifacts
- [x] 5.4 Note in `AGENTS.md` that the `app/openssl/` binaries are intentionally tracked despite the blanket `*.so` rule, so a future contributor does not "clean up" the negation or delete them as build output
- [x] 5.5 Confirm no user-visible English text changed, so no `app/i18n/*.ts` or `app/android/res/values*/strings.xml` update is required
- [x] 5.6 Run `openspec validate vendor-android-openssl`
- [x] 5.7 Commit with a conventional message
- [x] 5.8 Leave a note for the maintainer: the already-published Play internal-test build stays broken until a new release tag is cut from this tree (out of scope for this change)

## Verification outcome

Verified against a real build environment (Qt 6.6.3 `android_arm64_v8a` kit,
NDK r23c, CMake 3.22.1):

- **3.4** — the guard was exercised by real `cmake` configures. Both libraries
  present: exit 0. Only `libssl_3.so` removed: exit 1, naming that single path —
  the case the old single-file check would have passed. The whole
  `app/openssl/<abi>` directory renamed aside: exit 1, naming both paths. Restored:
  exit 0 again.
- **4.4** — the step's script was extracted from the workflow and executed against
  the **real** release APK and AAB produced by `app/build.ps1`. Declaring only the
  arm64 kit, as the release job does, it passes, confirming `lib/arm64-v8a/` in
  the APK and `base/lib/arm64-v8a/` in the AAB. Re-run with `android_x86_64` also
  declared it fails, naming the four absent `x86_64` entries, so the pass is a
  real inspection of the archives and not a vacuous one.
- **5.1** — a full `app/build.ps1 -Configuration Release -Bundle` run succeeded,
  producing `aurelex-release.apk` and `aurelex-release.aab` (47.2 MB each).

One bug was found and fixed by fixture testing of the workflow step: the first
draft derived the ABI by stripping `android_` from the Qt kit directory name,
which yields `arm64_v8a` while the packaged directory is `lib/arm64-v8a/`. The
step now uses an explicit kit-name to ABI-name map and refuses to guess on an
unmapped kit.

Not verified:

- **5.2** — the freshly built release APK was installed on a connected device
  (`ZY22HC8LTR`) and the catalog pane opened and listed its **cached** entry
  (`kaikki-en`, marked installed), so the pane itself works, and the APK
  installed on the device was confirmed to contain `libcrypto_3.so`,
  `libssl_3.so`, and `libplugins_tls_qopensslbackend_arm64-v8a.so`. The **live**
  fetch could not be exercised: that device has no network at all
  (`Active default network: none`, Wi-Fi disabled, IP and DNS unreachable), so no
  TLS handshake can happen. The only failure logcat showed was
  `remote catalog unreachable: "Proxy connection refused"`, raised at TCP connect
  — before any TLS handshake — from a stale global proxy `127.0.0.1:8899` with
  nothing listening on it. That is not evidence about TLS in either direction, and
  the absence of "TLS initialization failed" is not evidence of success. This
  task stays open and needs a network-connected device.
