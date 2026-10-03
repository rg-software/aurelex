# Third-party notices

Aurelex is free software under the GNU General Public License, version 3 or
later (see [`LICENSE`](LICENSE)). It is built from, links against, or
redistributes the third-party components listed below. Each remains under its
own license; nothing here changes those terms.

The Corresponding Source for the GPL-licensed components Aurelex compiles in is
this repository together with the exact upstream revision it pins — see
[`docs/ENGINE.md`](docs/ENGINE.md) and the `engine/` submodule.

## Compiled / linked components

| Component | Version | License | Notes |
|---|---|---|---|
| [goldendict-ng](https://github.com/xiaoyifang/goldendict-ng) engine | pinned tag (see `docs/ENGINE.md`) | GPL-3.0-or-later | Selected sources are compiled into `carve/`; the submodule keeps its own `LICENSE.txt` and copyright notices. |
| [Qt](https://www.qt.io/) | 6.6.3 | LGPL-3.0 (or GPL-3.0 / commercial) | Modules used: Core, Gui, Widgets, Xml, Concurrent, Network, Qml, Quick, QuickControls2, WebView. Qt is dynamically linked. |
| [Xapian](https://xapian.org/) (xapian-core) | 1.4.22 | GPL-2.0-or-later | Full-text search index. |
| [zlib](https://zlib.net/) | per vcpkg baseline `2026.07.29` | Zlib | Deflate; used by the dictionary formats and the engine. |
| [bzip2](https://sourceware.org/bzip2/) | per vcpkg baseline `2026.07.29` | bzip2-1.0.6 (BSD-like) | Compression. |
| [XZ Utils](https://tukaani.org/xz/) (liblzma) | per vcpkg baseline `2026.07.29` | Public domain | LZMA compression (dictzip). Newer upstream releases are 0BSD. |
| [LZO](https://www.oberhumer.com/opensource/lzo/) (liblzo2) | per vcpkg baseline `2026.07.29` | GPL-2.0-or-later | Compression. |
| [{fmt}](https://fmt.dev/) | per vcpkg baseline `2026.07.29` | MIT | Formatting. |
| [OpenSSL](https://www.openssl.org/) | 3.1.8 | Apache-2.0 | Prebuilt libraries vendored under `app/openssl/` for Qt's Android TLS backend. Provenance and digests in [`app/openssl/README.md`](app/openssl/README.md). |

Versions marked "per vcpkg baseline" are resolved by the pinned
[vcpkg](https://github.com/microsoft/vcpkg) baseline recorded in
`.github/workflows/release-qt.yml`; the license is stable across the versions
that baseline selects. The full license text for each is available from the
linked upstream project.

## Platform components (not distributed)

- **Android System WebView** (Chromium) renders dictionary articles. It is a
  component of the device's operating system, not redistributed with Aurelex.
- **AndroidX / Android platform libraries** are used by the app at run time as
  provided by the OS and the Android SDK; their licenses travel with the SDK.

## Dictionary data (downloaded, not bundled)

The dictionaries offered in the built-in catalog are derived from Wiktionary
(by way of [kaikki.org](https://kaikki.org)) and are licensed
**CC BY-SA 4.0**. Aurelex downloads them on the user's explicit request and does
not bundle them in the app; each catalog entry carries its attribution and
license. The conversion tooling in `scripts/` is part of this repository.

## Reporting

If you believe a component's attribution or license is missing or incorrect,
please open an issue.
