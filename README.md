# Aurelex — the golden lexicon for your pocket

A mobile dictionary app for Android that reuses the [goldendict-ng](https://github.com/xiaoyifang/goldendict-ng)
dictionary engine. Look up words offline in your mdict / DSL / StarDict dictionaries, rendered in a
clean mobile interface.

> **Status: in development.** Available as an Android APK; see the *Roadmap* for what's planned.

## Why another dictionary app

The desktop GoldenDict-ng is powerful but cannot run on phones. Aurelex ports its engine —
not its interface — keeping the dictionary formats and lookup quality people depend on while cutting
everything that makes no sense on a phone (system tray, hover scanning, global hotkeys, and the
kitchen-sink preferences screen).

## What you get (v1 scope)

- Offline lookup in **mdict (MDX/MDD)**, **DSL (+ .dz)**, and **StarDict** dictionaries
- Search-as-you-type prefix suggestions
- Article rendering with images and audio from your dictionary packs
- Audio playback (ogg / mp3 / wav)
- In-article link navigation and browser-style back / forward
- Full-text search across your dictionaries
- History and favorites
- Dark mode (follows your phone's theme, or a manual dark toggle)
- Quick Settings tile and a home-screen shortcut widget
- No broad storage permission — the app only accesses the folders you choose

## What's intentionally not in v1

| Category | Examples |
| --- | --- |
| Unsupported formats (convert on your computer) | BGL, SDict, XDXF, Aard, SLOB, LSA, Zim, EPWING |
| No sense on mobile | Scan/hover popup, global hotkeys, system tray, print/PDF, external programs |
| Cut for v1 | Text-to-speech |
| Maybe later | Translate-later / word-list export |

Formats in the first row are easy to convert to StarDict or MDX on a computer using a free tool such
as [pyglossary](https://github.com/ilius/pyglossary), then copy to your phone.

## Installing

Install the APK on your Android phone (a release APK is produced on tag pushes; dev builds come from
`app/build.ps1`). When you import a folder, Android shows a folder-scoped grant prompt — a scoped
grant, not blanket storage access.

## Getting dictionaries onto the phone

Aurelex imports dictionaries from a folder you pick in-app, then copies the supported files into
its own private storage and scans the copies (no broad storage permission).

1. Convert any non-supported dictionaries to StarDict or MDX on your computer (only if needed).
2. Copy your `.mdx`/`.mdd`, `.dsl`, or `.ifo` files into a folder on your phone (USB cable, cloud, or
   the device's file manager). A StarDict dictionary needs its `.ifo` together with the matching
   `.idx` and `.dict` files.
3. In the app: **Dictionaries → Add**, pick that folder. The folder is copied once into app-private
   storage and scanned recursively (progress shown).
4. The app keeps working even if your dictionaries live in subfolders (it scans them recursively).

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

> Supported audio: ogg / mp3 / wav. Speex (`.spx`) audio is ignored rather than crashing (v1).

## Privacy

Dictionary files you bring are your own and are never uploaded. Lookups happen entirely on-device.
Aurelex requests no account, no sign-in, and no network permission other than what the WebView needs
to render your local dictionaries.

## License

GPLv3, mirroring upstream. See `LICENSE` and `NOTICE`.

## Roadmap & contributing

- **What's coming next:** see `docs/ROADMAP.md`.
- **Build it / contribute / develop:** see `docs/DEVELOPMENT.md`.
- **How to test:** see `docs/TESTING.md`.