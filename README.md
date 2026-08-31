# Aurelex — the golden lexicon for your pocket

A mobile dictionary app for Android that reuses the [goldendict-ng](https://github.com/xiaoyifang/goldendict-ng)
dictionary engine. Look up words offline in your mdict / DSL / StarDict dictionaries, rendered in a
clean mobile interface.

> **Status: in development.** The engine carve, C/JNI boundary, and the v1 app (search, article
> rendering, dictionary management) are implemented and buildable (`./gradlew :app:assembleDebug`).
> A release APK signing pipeline is in CI. Tracks are open for on-device validation.

## Why another dictionary app

The desktop GoldenDict-ng is powerful but cannot run on phones. Aurelex ports its engine —
not its interface — keeping the dictionary formats and lookup quality people depend on while cutting
everything that makes no sense on a phone (system tray, hover scanning, global hotkeys, and the
kitchen-sink preferences screen).

## What you get (v1 scope)

- Offline lookup in **mdict (MDX/MDD)**, **DSL (+ .dz)**, and **StarDict** dictionaries
- Search-as-you-type suggestions (prefix + fuzzy)
- Article rendering with images and audio from your dictionary packs
- Audio playback (ogg / mp3 / wav)
- In-article link navigation and history back

## What's intentionally not in v1

| Category | Examples |
| --- | --- |
| Unsupported formats (convert on your computer) | BGL, SDict, XDXF, Aard, SLOB, LSA, Zim, EPWING |
| No sense on mobile | Scan/hover popup, global hotkeys, system tray, print/PDF, external programs |
| Maybe later | Full-text search, favorites, history screen, TTS |

Formats in the first row are easy to convert to StarDict or MDX on a computer using a free tool such
as [pyglossary](https://github.com/ilius/pyglossary), then copy to your phone.

## Getting dictionaries onto the phone

Aurelex reads dictionaries straight from a folder you pick in-app (no broad storage permission).

1. Convert any non-supported dictionaries to StarDict or MDX on your computer (only if needed).
2. Copy your `.mdx`/`.mdd`, `.dsl`, or `.ifo` files into a folder on your phone (USB cable, cloud, or
   the device's file manager).
3. In the app: **Dictionaries → Add dictionaries…**, pick that folder. The app indexes on first use
   (progress shown); later opens reuse the cache unless the files or engine version changed.

### Converting other formats with pyglossary

Supported in v1: **mdict (MDX/MDD), DSL (+ .dz), StarDict (`.ifo`)**. Everything else — BGL, SDict,
XDXF, Aard, SLOB, LSA, Zim, EPWING, Lingvo — converts on a computer:

```bash
pip install pyglossary
# Convert one .bgl to StarDict (produces .ifo/.idx/.dict):
pyglossary --read-format=BGL --write-format=Stardict mydict.bgl mydict.ifo
# Or convert a .dsl to StarDict if you prefer one format everywhere:
pyglossary mydict.dsl mydict.ifo
```

Converted packs copy straight to the phone folder. MDX files you already own are used as-is — no
conversion needed.

> Supported audio: ogg / mp3 / wav. Speex (`.spx`) audio is shown as unsupported rather than
> crashing (v1).

## Building the app

Requirements: JDK 17+, Android SDK/NDK 23.2, Qt 6.6.3 android + desktop kits, vcpkg deps
(`zlib bzip2 liblzma lzo fmt tomlplusplus`). Machine paths go in `local.properties`
(`aurelex.qt.base`, `aurelex.qt.host`, `aurelex.vcpkg.root`); apply the engine patches first
(`.\scripts\apply-patches.ps1` or `./scripts/apply-patches.sh`), then:

```bash
./gradlew :app:assembleDebug
```

The result is `app/build/outputs/apk/debug/app-debug.apk`. A signed release APK is produced by the
CI workflow (`.github/workflows/build-apk.yml`) with `AURELEX_KEYSTORE_*` secrets.

## Upstream & maintenance

Upstream is pulled in as a Git submodule pinned to a release tag. Only a small patch set deviates
from upstream, and a CI smoke test verifies each upstream update. See `AGENTS.md` for the contract.

## Development

Planning artifacts live in `openspec/`. Design, scope, and the cut register are documented in
`openspec/changes/goldendict-mobile-port/design.md`.

Layout: `engine/` (pinned upstream submodule, never edited in place), `patches/` (the only
deviations, applied by `scripts/apply-patches.*`), `app/` (Kotlin UI + JNI + the `gd_*` C boundary).

## License

GPLv3, mirroring upstream. See `LICENSE` and `NOTICE`.
Dictionary files you bring are your own and are never uploaded.