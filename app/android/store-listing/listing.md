# Play Store listing copy

The listing text for Google Play, kept here so it is reviewable in git rather
than living only in the Play Console. Paste into
**Grow → Store presence → Main store listing** (per language).

Limits Play enforces: app name 30, short description 80, full description 4000
characters. All three languages below are within them.

## Assets

Everything Play shows for this app is in this directory. None of it is a build
input — no Gradle or CMake rule reads these files; they are the published
artifact, versioned so a re-upload is byte-identical and a copy change is
reviewable in a pull request.

| File | Play slot | Produced by |
|---|---|---|
| `play-store-icon-512.png` | App icon (512×512) | `scripts/make-app-icons.ps1` (from `app/android/icon/aurelex-icon-1024.png`) |
| `feature-graphic-1024x500.png` | Feature graphic | `scripts/make-app-icons.ps1 -FeatureGraphic` |
| `screenshots/NN-*.png` | Phone screenshots (1080×1920) | `scripts/make-store-screenshots.ps1 -Captures <dir>` |

The two icon assets are generated from the master artwork, so re-run the icon
script after replacing it rather than editing the PNGs. The screenshots come
from `adb exec-out screencap -p` on a real device; the `NN-` prefix is the
gallery order (hero first), so re-ordering means renaming captures, and the
converter strips metadata so an unchanged capture re-converts byte-for-byte.

### Constraints Play enforces

`scripts/check-store-assets.py` is the enforcing copy of this table. CI runs it
on any change to this directory, and again in the release workflow, so a mistake
fails in the repository rather than at upload time.

| Asset | Rule Play enforces | Constant in the check |
|---|---|---|
| Phone screenshots | 2–8 per language | `MIN_SCREENSHOTS` / `MAX_SCREENSHOTS` |
| Phone screenshots | 320–3840 px on each side | `MIN_SIDE_PX` / `MAX_SIDE_PX` |
| Phone screenshots | aspect ratio 16:9 or 9:16 (1% tolerance) | `ACCEPTED_RATIOS` / `RATIO_TOLERANCE` |
| Phone screenshots | no two files byte-identical | duplicate-content rule |
| Phone screenshots | `NN-` prefixes unique and contiguous from 1 | ordering rule |
| App icon | 512×512 PNG | `ICON_SIZE` |
| Feature graphic | 1024×500 PNG | `FEATURE_GRAPHIC_SIZE` |

The bounds and ratio are why the converter exists: a phone capture is
1080×2400 (20:9), which Play rejects, so it is scaled and centred on a
1080×1920 canvas. The duplicate rule exists because a renamed capture leaves the
previous file behind, and the upload appends in file order — so the orphan
occupies a gallery slot until someone notices the count is wrong.

**What this check does not cover.** It reads PNG headers, so it validates
*shape*, not *content*. Specifically it does **not** check:

- the listing **text** limits (app name 30, short description 80, full
  description 4000 characters) — those are stated at the top of this file and
  the script never reads this one;
- whether a screenshot is *appropriate* — that it belongs in the gallery, that
  its `NN-` position tells the right story, or that what it shows is true. A
  well-formed capture of the wrong screen passes. The gallery's meaning is
  judged in review, not by the script.

`docs/screenshots/main.png` is unrelated: that is the README image for GitHub,
not a Play asset.

## Facts the copy is allowed to claim

Verified against the source, so the listings cannot drift from the app:

- Formats: MDict `.mdx`/`.mdd`, Lingvo DSL `.dsl`/`.dsl.dz`, StarDict `.ifo`.
- Free catalog: three **monolingual** Wiktionary-derived dictionaries via
  kaikki.org (English, Japanese, Russian), CC BY-SA 4.0, each with an opt-in
  resource bundle (pronunciation audio, images). No cross-language translation
  is offered on purpose — see `docs/KAIKKI-CONVERSION.md`.
- Offline lookup; nothing bundled in the APK.
- No storage permission (folder-scoped SAF import into app-private storage).
- No account, no ads, no analytics, no crash SDK. Network use: the catalog
  (`rg-software.github.io`, downloads from `github.com`) and resources an
  article itself references.
- Requires Android 6.0+ (`minSdk 23`) and a 64-bit **arm64-v8a** device.
- Interface in English, Russian and Japanese.
- Engine derived from goldendict-ng; app is GPL v3.

---

## English (en-US)

**App name:** Aurelex

**Short description**

```
Your own dictionaries, searched offline. No account, no tracking, open source.
```

**Full description**

```
Your own dictionaries, on your phone, at the speed you type.

Aurelex is an offline dictionary for Android. It reads the formats you already own — MDict, Lingvo DSL and StarDict — and searches them entirely on-device. No account, no ads, no tracking, no limits on how much you can look up. A free built-in catalog gets you started without a computer.

GET STARTED IN THREE STEPS
1. Open Aurelex and tap the cloud icon in the Dictionaries tab.
2. Install a free dictionary from the catalog.
3. Tap Search and start typing.

BRING YOUR OWN COLLECTION
Pick a folder of dictionary files; Aurelex copies it into private app storage and indexes it there. No storage permission is involved, and you can delete the original folder afterwards. Supported: .mdx and .mdd (MDict), .dsl and .dsl.dz (Lingvo DSL), .ifo (StarDict). Working in Zim, EPWING, BGL, SDict, XDXF, Aard or another format? Convert it to StarDict on a computer with pyglossary, then import it the same way.

SEARCHING
• Results as you type, with a suggestion panel
• Full-text search across every definition, not just headwords
• Bilingual and monolingual dictionaries together, grouped by language pair
• Groups: search one subject, one language pair, or your own set
• Search history you can clear, and favorites you keep
• Look up from anywhere — clipboard, share menu, text-selection toolbar, or Quick Settings tile.

READING
• Articles keep the dictionary's own images, pronunciation audio and cross-references
• Find in page: every match highlighted, with jump to next and previous
• Zoom from 75% to 250%, with text reflow
• Back and forward through your lookups
• Light, dark, or follow the system theme
• Multilingual interface

FREE DICTIONARIES IN THE CATALOG
The catalog offers several dictionaries derived from Wiktionary via kaikki.org (CC BY-SA 4.0). Each one installs once; pronunciation audio and extra resources are an opt-in toggle during install. Once installed, they work with the network off.

PRIVACY
Everything happens on your phone. Your dictionaries are never uploaded, and no lookup ever leaves the device. Two things can use the network: the dictionary catalog, and images or other resources that a dictionary article itself references. No account, no advertising, no analytics.

OPEN SOURCE
Aurelex is free software, licensed under the GPL v3. The dictionary engine comes from the GoldenDict-NG project; the app, the catalog pipeline and everything around it are open source in the GitHub repository.

Requires Android 6.0 or later on a 64-bit (arm64) device.
```
