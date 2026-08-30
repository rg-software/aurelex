# Aurelex — the golden lexicon for your pocket

A mobile dictionary app for Android that reuses the [goldendict-ng](https://github.com/xiaoyifang/goldendict-ng)
dictionary engine. Look up words offline in your mdict / DSL / StarDict dictionaries, rendered in a
clean mobile interface.

> **Status: planning.** The engine strategy and scope are locked in
> (`openspec/changes/goldendict-mobile-port/`); no installable build exists yet.

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
| Maybe later | Full-text search, favorites, history screen, dark mode, TTS |

Formats in the first row are easy to convert to StarDict or MDX on a computer using a free tool such
as [pyglossary](https://github.com/ilius/pyglossary), then copy to your phone.

## Getting dictionaries onto the phone

1. Convert any non-supported dictionaries to MDX or StarDict on your computer (optional).
2. Copy your `.mdx`/`.mdd`, `.dsl`, or `.ifo` files to a folder on your phone (USB cable or cloud).
3. In the app, select that folder. The app builds its index on first use.

## Upstream & maintenance

Upstream is pulled in as a Git submodule pinned to a release tag. Only a small patch set deviates
from upstream, and a CI smoke test verifies each upstream update. See `AGENTS.md` for the contract.

## Development

Planning artifacts live in `openspec/`. Design, scope, and the cut register are documented in
`openspec/changes/goldendict-mobile-port/design.md`.

The Android toolchain build (Qt 6 core modules + NDK) is the first milestone; there is no runnable
build to install yet.

## License

GPLv3, mirroring upstream. Dictionary files you bring are your own and are never uploaded.