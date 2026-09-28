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

Prebuilt OpenSSL 3 shared libraries for each ABI the app builds:

```
<abi>/libcrypto_3.so
<abi>/libssl_3.so
```

Source: [KDAB/android_openssl](https://github.com/KDAB/android_openssl),
`ssl_3/<abi>/`. These are the same prebuilt libraries the Qt community uses
for Android (the layout and `_3` suffix are what Qt 6 looks for).

## Why vendored

Vendoring keeps builds reproducible and offline: a build never has to fetch a
binary at configure time, and the exact bits that ship are pinned in the repo.

`app/CMakeLists.txt` lists them in the `aurelex` target's
`QT_ANDROID_EXTRA_LIBS`, which makes `androiddeployqt` copy them into the
APK's `lib/<abi>/`.

## Licence

OpenSSL is licensed under the Apache License 2.0 (OpenSSL 3.x). The binaries
here are redistributed under that licence; the OpenSSL copyright and licence
text is available at <https://www.openssl.org/source/license.html>. This is
additive to Aurelex's GPLv3; see the repository `NOTICE`.
