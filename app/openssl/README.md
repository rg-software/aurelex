# Vendored Android OpenSSL

Qt's TLS on Android is its OpenSSL backend: `libQt6Network` / the
`qopensslbackend` plugin `dlopen()` `libcrypto_3.so` and `libssl_3.so` at run
time. The Qt 6.6.3 Android kit does **not** ship these libraries, and Android's
own TLS (BoringSSL) is not usable by Qt. Without them every
`QNetworkAccessManager` HTTPS request fails immediately with
`QSslSocket::connectToHostEncrypted: TLS initialization failed`, with no
fallback.

The WebView is unaffected (Chromium brings its own TLS), so the app worked
until the remote dictionary catalog introduced the first Qt-network HTTPS
request.

## Contents

Prebuilt OpenSSL 3 shared libraries, per ABI directory:

```
<abi>/libcrypto_3.so
<abi>/libssl_3.so
```

Only the ABI the release is built for (`arm64-v8a`) is packaged today — the
dependency chain is arm64-only (vcpkg `arm64-android`, xapian for `arm64-v8a`,
`qtTargetAbiList=arm64-v8a`). The `x86_64/` copies are vendored ahead of an
emulator ABI so adding one is a build-config change, not a vendoring task; they
are not shipped, and the release workflow asserts the TLS libraries only for
the ABIs the build actually targets.

These files are **tracked in version control**, not build output. The repository
`.gitignore` has a blanket `*.so` rule for the NDK/vcpkg build artifacts it was
written for, with a single scoped negation (`!app/openssl/**/*.so`) for this
directory. Do not "clean up" that negation and do not delete these files as build
output: `app/CMakeLists.txt` fails the configure step if either library is absent
for the ABI being built, precisely because a build without them produces an app
with no working TLS.

## Provenance

Upstream: [KDAB/android_openssl](https://github.com/KDAB/android_openssl),
directory `ssl_3/<abi>/`, branch `master` at commit
`b71f1470962019bd89534a2919f5925f93bc5779`. These are the same prebuilt
libraries the Qt community uses for Android (the layout and `_3` suffix are what
Qt 6 looks for). OpenSSL version reported by both `libcrypto_3.so` builds:
**3.1.8**.

| File | Bytes | SHA-256 |
|------|-------|---------|
| `arm64-v8a/libcrypto_3.so` | 4030424 | `1e6c12ae0c2dadfe9d178d7f80f0ab248a1877a234066098bf5594e5205e5740` |
| `arm64-v8a/libssl_3.so` | 634680 | `01d2bd0baac626efd3309f35f99c4b826dd9b885a7e4d14d5b12b3603d3a407f` |
| `x86_64/libcrypto_3.so` | 5090592 | `bc4bdd31835659e639c2dc8f0a722342f51230074c23ee3dd6d1fa2353d72db1` |
| `x86_64/libssl_3.so` | 679864 | `2af32571317adf90fb7a007756a17dd15cd2469da9ebbd4e973883f8753369c1` |

Each file was verified byte-identical to the upstream commit above by comparing
git blob hashes (`git hash-object` against the upstream blob SHA), so the digests
are not merely a local record — they identify these exact upstream bytes.

To upgrade: replace the files from a newer upstream commit, then update the
commit SHA, the version, and this table in the same commit. The diff of the table
is the reviewable record of what moved.

## Why vendored

Vendoring keeps builds reproducible and offline: a build never has to fetch a
binary at configure time, and the exact bits that ship are pinned in the
repository, so a fresh `git clone` produces the same artifact as any other
checkout. This is also why the files are tracked rather than downloaded by the
release workflow: a build input that only exists on one machine is a build input
that CI silently lacks, which is how a release artifact once shipped with no TLS
at all.

`app/CMakeLists.txt` lists them in the `aurelex` target's
`QT_ANDROID_EXTRA_LIBS`, which makes `androiddeployqt` copy them into the
APK's `lib/<abi>/`. The release workflow additionally asserts they are present in
the packaged APK and AAB before publication, so an omission fails the build that
would have shipped it instead of surfacing on a user's device.

## Licence

OpenSSL is licensed under the Apache License 2.0 (OpenSSL 3.x). The binaries
here are redistributed under that licence; the OpenSSL copyright and licence
text is available at <https://www.openssl.org/source/license.html>. This is
additive to Aurelex's own GPLv3 licence.
