# Aurelex

A fast offline dictionary for Android. Look up words in your own StarDict, mdict, and DSL dictionaries, or install one of our
free ones straight from the app. Everything runs on-device. No account, no ads, free and open source.

![Aurelex search and article view](docs/screenshots/main.png)

**[Download the latest release](https://github.com/rg-software/aurelex/releases)** (Android 6.0+, 64-bit ARM)

## Install

Open the APK file on your phone, or push it over `adb`:

```bash
adb install <aurelex-apk>
```

A Google Play release is in progress.

## Quick start

You do not need to own any dictionary files to use Aurelex:

1. Install the app and open it.
2. Go to the **Dicts** tab and tap the cloud icon.
3. Install a dictionary from the catalog.
4. Go to **Search** and start typing.

## Features

- **Offline lookup**. Download a dictionary once, then search it entirely
  on-device.
- **Built-in catalog**. Install free dictionaries straight from the app, with no computer involved.
- **Bring your own collection**. StarDict, mdict, and DSL formats are supported.
- **Groups**. Organize dictionaries into scopes (by language pair or by subject), and search only the ones you need.
- **Full-text search** across every definition in your dictionaries, not just
  headwords.
- **Article rendering** with inline images, pronunciation audio, and cross-reference links.
- **In-article search**. Find any phrase on the page you're reading and jump between matches without leaving it.
- **Search as you type**, with an in-article suggestion panel.
- **Browser-style back / forward** through your lookup history.
- **Article zoom** from 75% to 250% with text reflow.
- **History and favorites**.
- **Light, dark, or follow the system** theme.
- **Look up from anywhere**. Look up text from the clipboard or access dictionaries from the Quick Settings tile, the share menu, or the text-selection toolbar.

## Online catalog

Aurelex online catalog features a selection of dictionaries derived from [Wiktionary](https://www.wiktionary.org) / [kaikki.org](https://kaikki.org). They are heavily processed and cleaned up for comfortable use. The current selection includes:

| Dictionary | Entries | With sound
|---|---|---|
| English (Explanatory) |  883,403 | 9.89% |
| Japanese (Explanatory) | 111,320 | 0.08% |
| Russian (Explanatory) | 454,310 | 4.19% |

Other languages and language pairs are planned.

## Dictionary formats

| Format | Files |
|---|---|
| mdict | `.mdx`, `.mdd` |
| Lingvo DSL | `.dsl`, `.dsl.dz` |
| StarDict | `.ifo`, `.idx`, `.dict` + `res/` |

Anything else (BGL, SDict, XDXF, Aard, SLOB, GLS, Zim, EPWING, LSA) is not read natively. If you have dictionaries in one of those formats, convert them with [pyglossary](https://github.com/ilius/pyglossary) into the StarDict format.

## Importing dictionaries

Aurelex copies dictionaries into its own private storage, so it never needs a storage permission to read them:

1. Open the **Dicts** tab and tap the "folder" button.
2. Pick the folder holding your dictionary files.
3. The app will scan this folder and its subfolders and import all relevant files.

Once the copy finishes, you can delete the original folder. Removing a dictionary in the app deletes its stored copy permanently. Large dictionaries are indexed for full-text search in the background; the app stays usable while that runs.

## Privacy

Everything happens on-device.

- No account/ads/tracking.
- Your dictionaries are yours. They are never uploaded, and no lookup ever
  leaves the phone.
- Two things can touch the network: 1) the remote catalog functionality and 2) remote resources referenced from inside a dictionary article.
- Google Play build may report crashes to the developer.

See also the [full privacy policy](https://rg-software.github.io/aurelex/privacy/).

## Building from source

Requirements: JDK 17, the Android SDK and NDK, Qt 6.6.3 (Android and desktop kits), PowerShell 7, and the vcpkg dependencies listed in the docs.

```powershell
git clone --recursive https://github.com/rg-software/aurelex.git
cd aurelex

.\scripts\apply-patches.ps1                                  # patch the engine tree
pwsh -File .\app\build.ps1 -Configuration Debug -Install     # build, push, launch
```

See full instructions in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). Most functions are planned and implemented via OpenSpec changes under `openspec/`(see [`AGENTS.md`](AGENTS.md) for the working contract).

## License and credits

Aurelex is free software under the GNU GPL v3, see [`LICENSE`](LICENSE) and [`NOTICES.md`](NOTICES.md). Aurelex reuses the [goldendict-ng](https://github.com/xiaoyifang/goldendict-ng) dictionary engine, which is itself derived from the original GoldenDict by K.&nbsp;Isakov. The pinned version of the engine and our patches are recorded in [`docs/ENGINE.md`](docs/ENGINE.md). Aurelex is largely inspired by the discontinued [GoldenDict Mobile](http://goldendict.mobi). The dictionaries offered in the built-in catalog are distributed under CC BY-SA 4.0.
