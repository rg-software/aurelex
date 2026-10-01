# TESTING — Aurelex manual verification

Living, manual test checklist for the app. Each item is a concrete recipe: how to
trigger it, and what to expect. Mark items with their status as you verify them so
this doc stays the single source of truth for "what works".

Target: `app/` — the Qt Quick/WebView UI that drives the carved engine in-process
via the `gd_*` C boundary. (Earlier iterations of this doc described the removed
Kotlin/Compose app; the recipes below target the Qt UI.)

Status legend: ✅ verified on device · ⬜ not yet verified · 🔶 known gap

## Build & install

Before testing, the native library and APK must build. Apply the engine
patches and build the Qt app (JDK 17, see `app/build.ps1`):

```powershell
.\scripts\apply-patches.ps1
.\app\build.ps1 -Configuration Debug -Install
```

This adb-installs the result (`-Install`); without it the APK lands in
``build-qtquick/apk/build/outputs/apk/debug/`. The package is
`org.aurelex.pocket.dictionary`.

## Dictionary management (one-off import, folder-scoped SAF)

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 1 | Dictionaries tab → "Add" | The Android folder picker (SAF) opens; pick a folder with mdx / dsl(.dz) / ifo files | ✅ |
| 2 | After picking, check the Dictionaries list | Files scanned recursively (subfolders included); entries listed once imported | ✅ |
| 3 | Watch the Dicts banner during import | "Preparing dictionaries…" → "Scanning dictionaries…" → progress bars while indexing | ✅ |
| 4 | Add an intersecting folder (e.g. a subfolder of an already-imported folder) | The same dictionary is not duplicated (staged-copy dedup) | ✅ |
| 5 | Re-import the same folder again | No duplicate entries (dedup by id), count unchanged | ✅ |
| 6 | Reorder within a group (Groups tab) | Group article order follows membership order | ✅ |
| 7 | Select dictionaries → "Remove" | Entry removed immediately (no confirmation); search no longer returns its words; its staged copy + index are deleted | ✅ |
| 8 | No dictionaries / import a folder with none | Empty state / onboarding hint appears; "no supported dictionaries" is shown | ✅ |
| 8a | Import a folder holding a **StarDict** set (`word.ifo` + `word.idx` + `word.dict`, same basename) | All three companions are staged; the dictionary is listed and its headwords resolve. Before `fix-stardict-staging` only the `.ifo` was copied and the entry failed to load | ✅ |
| 8b | Import a StarDict set packaged with dictzip (`word.dict.dz`) | Loads the same as an uncompressed one | ✅ |
| 8c | Import a folder holding **only** a StarDict `.ifo` (companions absent) | Reports a failed load rather than listing a broken entry that returns nothing | ✅ |
| 8d | Remove an imported StarDict dictionary | Its staged companions and its index are deleted together; lookups stop returning its words | ⬜ |
| 8e | With a failed import reported, tap its trash ("Remove failed import") in the banner | That import's staged files are deleted, the banner clears, and every other dictionary keeps working | ⬜ |
| 8f | Re-import the corrected folder after a failed import of the same folder | The dictionary loads and the previous failure is gone, with no manual storage cleanup | ⬜ |
| 8g | Leave a failed import reported and just restart / rescan | The failure is re-reported and its files are still there — the app never deletes an import on its own | ⬜ |
| 8h | Import a StarDict dictionary that keeps article images in a sibling `res/` folder (e.g. The World Factbook), then open a country's **Geography** entry | The locator and map GIFs render instead of missing-resource placeholders. `stardict-resource-staging` stages `res/` wholesale; before it, every `res/` file was dropped. On host the engine returns the 10310-byte `af_large_locator.gif` through `gd_get_resource` | ✅ |
| 8i | Import a folder that has a directory named `res` but **no** StarDict `.ifo` beside it | Nothing from that `res/` is staged — the name alone is not treated as a dictionary's resources | ✅ |
| 8j | Re-import an already-imported StarDict folder after adding a file to its `res/` tree | The new resource is staged **and** the dictionary's existing files survive. Before the `StagingService` overlay fix the re-import deduped the unchanged files against the folder's own copy and then replaced the directory with the partial temp copy, deleting the dictionary | ✅ |

## Groups

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 10 | Groups tab → "Add group" → enter a name | Group created; membership editor opens immediately | ✅ |
| 11 | Tap a group row | Membership editor: add/remove dicts and drag to reorder; tapping "All" opens reorder-only mode | ✅ |
| 12 | Pick a group with the Search scope button | Lookups only search that group's dicts | ✅ |
| 13 | Delete a non-default group (trailing trash) | Confirmation appears; group removed; "All" (id 0) cannot be deleted | ✅ |

## Lookup

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 14 | Type in the search field | Prefix headword suggestions appear | ✅ |
| 15 | Tap a suggestion / press return | Combined article renders, dictionaries in group order | ✅ |
| 16 | Look up an unknown word | "Word not found" indication, no crash | ✅ |
| 17 | Tap a link inside an article | In-app lookup of the linked word; back returns to previous article | ✅ |
| 18 | Open an article with images from an `.mdd` | Images render | ✅ (device-verified — see #18.1) |
| 19 | Article references a missing resource | Article still renders; broken item shown, no crash | ✅ |
| 20 | Tap a pronunciation anchor (ogg/mp3/wav) | Audio plays; speex (`.spx`) is ignored, no crash | 🔶 (speex is silently skipped, not explicitly indicated) |
| 21 | Look up the same word twice | One history entry (dedupe, moves to front) | ✅ |
| 22 | Look up a word not in any dict | **Not** added to history | ✅ |

### MDict (`.mdx` / `.mdd`)

MDict had **no** CI fixture and no on-device coverage. It now has both: a
generated fixture (`scripts/make-smoke-mdx.py`, wired into `engine-smoke.yml`)
and a real on-device pass, recorded below. `verify-mdx-import` is the change
that covered this.

Two defects were found by doing it, both now fixed, neither specific to MDict
import:

- **The index build hung forever on device** and the app was killed with no
  crash record. `Iconv::convert()` retried without consuming input — measured
  as 517,000 identical iterations with `errno=E2BIG`, `inBytesLeft` stuck at 1.
  Fixed in `fix-iconv-nonprogress-loop` (`patches/0005`). The import that never
  completed now logs `Writing index…` 147 ms after opening the file and finishes
  the scan in 172 ms; its index went from 0 bytes to 88402.
- **Loose MDX assets were never staged.** A set shipping `.css`/`.jpg` beside
  its `.mdx` (and no `.mdd`) lost them, so every article rendered unstyled.
  Fixed by the staging rule in `verify-mdx-import`.

The smoke tool now dumps the **whole** article, fetches **every** resource it
references with byte counts and sniffed magic bytes, and surfaces the engine's
own `qWarning`/`qDebug` on stderr, where before they were silently dropped
(`smoke-surface-engine-diagnostics`). That last one is why the engine's error
text was finally visible. It is re-runnable:

```
build-smoke\Release\aurelex_smoke.exe <cfg> <dicts> <word>
```

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 18.1 | Look up `hand` in **Black's Medical Dictionary** (`.mdx` + 14 MB `.mdd`) | The article references `img/fig_ufig-h_1.jpg`; `gd_get_resource` returns **233245 bytes, `magic=jpeg`** — a real JPEG pulled from a nested path inside the `.mdd`. Hide the `.mdd` and it reports `FAILED TO RESOLVE`, so the check has teeth | ✅ host |
| 18.2 | Import **collinslaw** (`.mdx` + loose `.css`/`.jpg`, **no `.mdd`**) on device | It is listed and `law` resolves. This is the shape that used to hang the index build; the same fixture now indexes in 172 ms | ✅ device |
| 18.3 | Import **demo** (`.mdx` + `.mdd`) on device | Listed and headwords resolve. Note this fixture references **no** resources, so it cannot test the resource path — use 18.1 for that | 🔶 host-verified, device open |
| 18.4 | Confirm the staged layout keeps the `.mdd` beside the `.mdx`, and `collinslaw.css` / `collinslaw2ed.jpg` beside theirs | `files/staged/<id>/` holds `collinslaw2ed.mdx` (498842), `collinslaw.css` (1061) and `collinslaw2ed.jpg` (18896) together | ✅ device |
| 18.5 | Open an MDict article that embeds an image and confirm it renders in the WebView | Image renders rather than a missing-resource placeholder. 18.1 proves the engine serves the bytes; this confirms the WebView path | 🔶 device open |

Three things that look like bugs and are not:

- **A served CSS can be larger than the file on disk.** `collinslaw.css` is
  1061 bytes but serves 1684. `mdx.cc:811` runs `isolate_css()`, which rewrites
  CSS links to rescope them per dictionary. Correct, not corruption.
- **`collinslaw` shows no language pair.** The engine infers the pair from a
  regex over the dictionary's **filename**, falling back to its title
  (`langcoder.cc:276`): it looks for a literal `xx-yy` group of 2–3 letter
  codes. `collinslaw2ed.mdx` / "Collins Dictionary of Law 2ed" contains no such
  pattern, so it correctly reports none and is absent from By-Pair grouping.
  The dictionary still loads, indexes and resolves normally. Renaming the file
  to carry the pair (`…-en-en.mdx`) makes it appear; the content is not
  involved. Other fixtures are named to match (`Genius_En-Jp`,
  `UniversalRuEn`).
- **`collinslaw` references an image it does not ship.**
  `William J. Stewart, Robert Burgess - Collins Dictionary of Law (2001)/Image_106.png`
  is absent from the zip, so it legitimately fails to resolve. Note the path
  contains **spaces and commas** — the smoke tool had to be taught to parse
  quote-delimited URLs for exactly this reason.

Not yet exercised anywhere: **multi-volume `.mdd`** (`demo.1.mdd` … `demo.n.mdd`).
The suffix rule should accept it, but no fixture has proven it.

## Article zoom & reflow

Zoom is a **CSS root font-size** on the open article, not a page scale: the
layout reflows to the new measure instead of scaling a fixed-width column. The
value is stored as `articleZoom` in `files/settings.json`, snapped to 25% steps
and clamped to **75–250%**, so it survives a restart.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 18a | Open an article, tap "Zoom in" twice (100 → 150%) | Text and images grow together; **no** horizontal scrollbar appears; long paragraphs re-wrap to the wider measure rather than being clipped | ⬜ |
| 18b | Tap "Zoom out" to the floor | Stops at 75%; the button greys out and stays there | ⬜ |
| 18c | Tap "Zoom in" to the ceiling | Stops at 250%; the button greys out and stays there | ⬜ |
| 18d | At 150%, look up a *different* word | The new article opens at 150% — zoom is a property of the surface, not of one article | ⬜ |
| 18e | Force-stop at 150%, relaunch, open an article | Still 150% | ⬜ |
| 18f | Zoom in on an article that has an `<img>` and a sense-marker icon | Both scale; the `gd_tag_*` icons stay inline with the text rather than drifting | ⬜ |
| 18g | Zoom to 75% on a long article and scroll to the end | No horizontal overflow at any zoom level | ⬜ |

## Article optional parts (`[*]…[/opt]`)

DSL dictionaries hide author-marked optional content (answers, notes, extra
examples) behind a single `[+]` expander per entry, rendered by the engine as an
`<img class="hidden_expand_opt">` and driven by
`app/android/assets/scripts/gd-article-controls.js`. One expander reveals **all**
of that entry's zones at once. UIAutomator sees it through the WebView's DOM
accessibility subtree, where the state is the `alt` text: `[+]` collapsed,
`[-]` revealed.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 18h | Open a kaikki DSL article that has examples or a `See also` zone | A `[+]` expander is present; the zone content is hidden | ⬜ |
| 18i | Tap the expander | The icon swaps to `[-]` and **every** zone in that entry expands at once | ⬜ |
| 18j | Tap again | Collapses back to `[+]`; the page returns to its previous height | ⬜ |
| 18k | Check the accessibility tree while expanded | `content-desc` reads `[-]`, not `[+]` — the alt text is the state flag | ⬜ |
| 18l | Look up a headword with **no** optional zone | No expander rendered at all (there is nothing to reveal) | ⬜ |

## Article sense-marker icons

The kaikki converter marks common sense tags with four small SVGs
(`gd_tag_countable/uncountable/initialism/obsolete.svg`), referenced from the
article as `[s]gd_tag_*.svg[/s]`. Two independent copies exist **on purpose**:
the converter writes them into every dictionary it builds, and the APK ships its
own set in `assets/icons/`. The engine emits a dictionary-resource URL for them
(`bres://<dict>/.svg`, no existence check), which the app rewrites to its own
asset before it can ever become a resource read — so the app answers from the
APK and never consults the dictionary for these four names. Only those four are
rewritten; see `AGENTS.md` for the rule. **Nothing here has been checked on a
device.**

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 18m | Import a kaikki dictionary **with** its `.files` bundle, open a headword with a marked sense | The sense icons render inline, sized to the surrounding text (not full-size images) | ⬜ |
| 18n | Import the **same dictionary's `.dsl.dz` alone**, with no sibling `.files` bundle, and open the same headword | The icons **still render** — the app falls back to its own copy. This is the case that silently regresses if the rewrite is ever tightened; if the icons 404 here, that rewrite broke | ⬜ |
| 18o | In the same bundle-less dictionary, check the load/scan | The dictionary loads and searches normally despite having no resource bundle | ⬜ |
| 18p | Look up a word from a dictionary with an **ordinary** image (an `.mdd` picture, or a DSL `<dict>.files` image), and check the log | That image still resolves through `bres://` — the rewrite is bounded to the four `gd_tag_*` names and does not swallow other resources | ⬜ |
| 18q | Zoom the article (#18a) on a headword showing icons | The icons scale with the text and stay on the text baseline | ⬜ |

## Theme (dark / light / follow system)

The dock's theme cell cycles **Light → Dark → Follow system → Light**. Its glyph and its
accessibility name both show the theme the **next tap** selects, so the three icons read
"tap to go dark" (moon), "tap to go light" (sun), and "tap to hand control back to the
system" (auto). The stored setting is `themeMode` (`1` light, `2` dark, `-1` follow) in
`files/settings.json`.

Set the phone's theme first, then walk the cycle. Two of the three taps always change the
appearance; the third is the tap that hands control back to a system which may already be
showing what you just left (Dark → Follow on a dark system, or Follow → Light on a light
one). That tap still changes the stored **mode** and the icon, so the control never looks
dead — but do not expect a repaint on it.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 23 | System theme **light**: tap the theme cell three times | Mode goes light → dark → follows-system → light, and the name shows the next tap's target at each step ("Dark mode" → "Follow system theme" → "Light mode") | ✅ |
| 24 | System theme **dark**: tap the theme cell three times | Mode goes dark → follows-system → light → dark, names "Follow system theme" → "Light mode" → "Dark mode" | ✅ |
| 25 | Follow-system: change the phone's theme while the app is in follow-system | App follows the system dark/light setting (JNI system-dark read), without a restart | ✅ |
| 25a | Pinned light, then change the phone's theme to dark (and vice versa) | App stays light — a pinned theme ignores the system, live and after a restart | ✅ |
| 25b | With an article open, tap the theme cell | The open article flips theme in place, keeping the looked-up word (no re-lookup, no empty article) | ✅ |
| 25c | Each of the three modes, in the on-device accessibility tree | Three distinct names, each announcing the next tap's target: "Dark mode" (from Light), "Follow system theme" (from Dark), "Light mode" (from Auto) | ✅ |
| 25d | The glyph in each of the three states | A real icon, not `U+FFFD` tofu. Check all three: sun (`light_mode`) from Auto, moon (`dark_mode`) from Light, auto (`light_mode_auto`) from Dark | ✅ (human eyeball at 18 px: all three read as intended) |
| 25e | Force-stop and relaunch in each of the three modes | The same **mode** comes back, not merely the same resolved theme | ✅ |
| 25f | Migration: with the app stopped, write `files/settings.json` containing only `"darkMode": true`, then launch | Startup is dark, and the stored value becomes mode `2` | ✅ |
| 25g | Migration: same with `"darkMode": false`, then launch | Startup follows the system (mode `-1`) | ✅ |
| 25h | Migration: write an out-of-range `"themeMode": 7` | Falls back to mode `-1` rather than a state the control cannot represent | ✅ |
| 25i | Cold start with a **persisted dark** mode, and do not tap the theme cell | The name reads "Follow system theme" on the very first frame | ✅ (regression: `loadSettings()` runs after the QML binds, so it must emit `themeModeChanged()`) |
| 25j | In each of the three modes, compare the theme cell's glyph and label against the other dock tabs | The "Theme" label baseline matches the tab labels, and the auto glyph is the same size as the sun/moon. The auto glyph comes from the *secondary* subset font, so the subset's vertical metrics must be normalized to the classic font's 1.0 em (`asc=upm`, `desc=0`); otherwise its taller line box pushes the label down ~11 px | ✅ (measured: label top row 2270 for Theme = Search/Dicts/Groups/Favorites across states; auto glyph ink band 30–76 = sun) |
| 26 | Force-stop and relaunch after forcing dark | Dark persists (`themeMode` stored in `files/settings.json`) | ✅ |

## Full-text search

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 27 | FTS tab, run a word from an article **body** | Matched article headword returned | ✅ |
| 28 | Index builds automatically on add | Indexing progress bar shows while building; no manual "Build" button | ✅ |
| 29 | `boo` (prefix, default) | Matches `book` etc. (prefix) | ✅ |
| 30 | Check "Whole words" then `boo` | Exact-term match only (no `book`) | ✅ |
| 31 | Result respects the FTS scope button | Hits limited to the group chosen in the FTS pane's own scope control | ✅ |
| 32 | Tap a result | Opens the normal article for that headword | ✅ |
| 32a | While a large dictionary indexes, look up a word in an already-imported dictionary | Lookup returns within about one indexing slice (not after the whole build); the dictionary being indexed is absent from results until its index completes | ✅ |
| 32b | Tap Remove on a dictionary while it is being indexed | It disappears within a moment; its staged files + index are deleted; other dictionaries keep indexing | ✅ |
| 32c | Import a dictionary above the auto-index size bound, then run a full-text search over it | Import does not build its index; the first search builds it and its hits appear on completion | ✅ |

## Launcher shortcuts (QS tile + home-screen widget)

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 33 | Quick Settings → add the Aurelex tile | Tile present, labeled, with icon | ✅ |
| 34 | Copy text, tap the tile | Article for the copied text opens | ✅ |
| 35 | Tap the tile with an empty clipboard | Search screen opens with focus | ✅ |
| 36 | Home screen → widget (tappable bar) | Tapping opens the app (the widget is a shortcut, not a text field) | ✅ |
| 37 | Widget/tile lookup respects the active group | Article rendered against the applied group | 🔶 (unverified on device) |

## External lookup entry points

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 38 | In another app, select text → system **Share** → share to Aurelex | Article opens for the shared text | ✅ |
| 39 | In another app, select text → long-press selection toolbar → "…" → Aurelex (ACTION_PROCESS_TEXT) | Article opens for the selected text | ✅ |
| 40 | Share / PROCESS_TEXT / clipboard for an unknown word | "Word not found" screen, never a crash | ✅ |
| 41 | In-app search row → "Clipboard" button | Looks up the current clipboard text; blank clipboard is a no-op | ✅ (read path code-reviewed; Android 15 restricts automated clips) |

## History & favorites

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 42 | Clear the search field in the Search tab | Recent lookups appear in the candidate area inside the article WebView, most recent first (no History tab) | ✅ |
| 43 | Tap a history word | Article opens and the word moves to the top | ✅ |
| 44 | Tap a row's ✕ button and the "Clear all" row | Item / all items removed; persists across restart | ✅ |
| 45 | Article → ☆/★ star | Appears in Favorites | ✅ |
| 46 | Favorites: tap to open, tap the row's Remove ✕ | Works; persists across force-stop + relaunch | ✅ |

## Distribution & polish

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 47 | Fresh install | Adaptive launcher icon in the launcher; onboarding screen shows on first launch | ⬜ (icon visual not re-checked; onboarding verified) |
| 48 | After onboarding, no dicts loaded | Empty search state: guidance to add dictionaries | ✅ |
| 49 | Tagged release build | Signed APK + AAB produced on a `vX.Y.Z` tag push and attached to the GitHub release | ✅ (v0.2.5 shipped both assets) |

## Localization (app language)

The app defaults its display language to the system UI language (`Settings` →
Apps → Aurelex → language, or `app.forceShareDeviceLanguage` on later Android
configs), trying the full locale (`ru-RU`) before the language (`ru`) and
falling back to English when no catalog matches. **RU** and **JA** are shipped
as `app/i18n/aurelex_ru.qm` / `aurelex_ja.qm`; the toggling recipe below relies
on a system-language switch that rebuilds the app's locale — on devices that
don't offer per-app language, switch it, and relaunch. The catalog source of
truth and the `update-translations.ps1` lupdate/lrelease workflow are documented
under "Localization" in `docs/DEVELOPMENT.md`.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 50 | Set device UI language to **Russian**, launch | Navigation, search placeholder, dictionary/group/FTS/favorites labels, onboarding, dialogs, banners ("Indexing (…)"), "engine error" wrapper, history "No lookups yet"/"Clear all", Not Found term in Russian; group names/dictionary names stay as-is | ⬜ (needs a device with RU; build.ps1 verified) |
| 51 | Same with **Japanese** | Same set in Japanese | ⬜ (needs a device with JA) |
| 52 | Set device UI language to one without a catalog (e.g. **Finnish**), launch | Falls back to English, no crash, `qInfo` log line "no translation for <lang>… using English" | ⬜ (needs a device with a non-RU/JA locale; install log can confirm the message) |
| 53 | In RU/JA, import a dictionary and let FTS index | Android notifications: channel names ("Dictionary preparation" / "Full-text indexing" under Settings → Apps → Aurelex → Notifications), title, "Preparing dictionaries…", "Indexing (%1 of %2): name" shown in the device language | ⬜ (needs the RU/JA device + a dict import) |
| 54 | In RU/JA, inspect the Quick Settings tile and home-screen widget | Tile/widget labels localize ("Поиск в Aurelex", "Aurelex で検索") | ⬜ (needs the RU/JA device) |
| 55 | UIAutomator / Appium dump in RU or JA | `Accessible.name`/`content-desc`/`className` remain stable English IDs (localization never touches the accessibility names) | ⬜ (re-run the existing on-device flows under any locale) |

## Remote dictionary catalog

"Add from remote" (the cloud button in the Dictionaries toolbar) opens a
full-page catalog pane. Opening it **re-probes automatically** — there is no
refresh button. Nothing is fetched at app start, so an install that never opens
the pane makes no catalog request. Format, manifest and hosting rules:
`docs/REMOTE-CATALOG.md`.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 56 | Dictionaries toolbar → "Add from remote" | The catalog pane opens with the title "Dictionary catalog" and a Back arrow; the manifest is fetched | ⬜ |
| 57 | Wait for the list | Entries appear as rows named `<entry name>` under "Remote catalog list", with attribution/licence beneath | ⬜ |
| 58 | Tap an entry name, then the header download icon | The row highlights, the icon becomes "Cancel download", and a `ProgressBar` plus a non-interactive line appear | ⬜ |
| 59 | Let a download finish | The row goes grey and its accessible name gains `, installed`; the entry then appears in the Dictionaries list after the rescan, and the auto-index banner follows | ⬜ |
| 60 | Back out to the dictionary list while a download runs | The download keeps running; reopening the pane shows its progress | ⬜ |
| 61 | Tap "Cancel download" mid-transfer | The line reads "Download cancelled."; the partially written files never appear as a dictionary and no stray entry is left in the list | ⬜ |
| 62 | Re-install an entry that is already installed | Clean no-op: the row reads `, installed`, is **not** selectable, and no duplicate dictionary row appears | ⬜ |
| 63 | An entry with an optional audio bundle | The row carries a music-note toggle named "Audio for `<name>`"; tapping the note first switches it to "No audio for `<name>`" and the selection downloads the dictionary without audio | ⬜ |
| 64 | An **installed** entry still missing its bundle | Its audio toggle is enabled and tapping it fetches only the bundle into the same directory; audio then plays after the dictionary reloads, with no app restart | ⬜ |
| 65 | With < 512 MiB free, start a download | Refused with the "Not enough free space" dialog naming the need and the free amount; nothing is fetched | ⬜ |
| 66 | With between 512 MiB and 2 GiB free, start a download | "Not much free space" dialog; Cancel aborts, OK proceeds (the index built afterwards also needs room) | ⬜ |
| 67 | Airplane mode, then open the pane | A previously-fetched catalog still renders, with the warning "Showing the last saved catalog. Downloads need a connection to the catalog host."; a per-entry download attempt fails with a stated reason rather than silently | ⬜ |
| 68 | Airplane mode on a **first** run with no cached manifest | "The catalog could not be loaded." with the reason; the app does not crash and the rest of the Dicts tab works | ⬜ |
| 69 | Point the app at a manifest containing an unsupported format (`.epwing`) | The entry is **listed but not selectable**, with "This dictionary's format is not supported by this app version." — the rest of the catalog still loads | ⬜ |
| 70 | Inspect a downloaded dictionary's files | It is a staged copy under `files/staged/<contentHash>/`; re-importing the same folder is still deduped (#4/#5) | ⬜ |
| 71 | Install an `.mdx`+`.mdd` catalog entry | The entry reports installed only once **both** halves have landed | ⬜ |
| 72 | A release build, on a device with no other TLS user | The catalog loads. ⚠️ If it reports "TLS initialization failed" while everything else works, the APK shipped without the vendored `libcrypto_3.so`/`libssl_3.so` — the WebView brings its own TLS, so this is the only feature that notices | ⬜ |

## Known gaps

- Multi-volume `.mdd` (`demo.1.mdd` … `demo.n.mdd`) is untested on either side —
  the suffix rule should accept it, but no fixture has proven it. Single-file
  `.mdd` images are verified on device (#18.1, #18.5).
- QS tile / widget active-group (#37) — inherited from `quick-lookup-shortcuts`.
- Theme control: the tri-state cycle, both migration paths, live system-switch, the
  article in-place flip, the layout alignment and the glyphs are all verified
  (#23–#25j).
- Secondary icon font (`MaterialSymbols-Outlined-subset.ttf`, family "Material Symbols
  Outlined"): it must keep the classic font's 1.0 em vertical metrics, or any Text mixing
  the two families develops a taller line box and drops the sibling label (#25j). The
  subset is built by `build_symbol_subset.py`, which pins `hhea`/OS-2 `asc=upm`,
  `desc=0`, sets `USE_TYPO_METRICS`, and zeroes the `post` underline. Bundled resources
  are declared with `qt_add_resources` in `app/CMakeLists.txt` (not `.qrc` files +
  AUTORCC), because AUTORCC does not track the payload files listed inside a `.qrc` — a
  regenerated `.ttf` silently stayed out of the APK until the resource was rebuilt by an
  unrelated edit.
- Icon codepoints: a wrong-but-real codepoint passes every "is the glyph in the font"
  check. The sun shipped as `U+FFFD` because `icon()` had no `light_mode` key at all, and
  the earlier sun/moon candidates (`0xe2c8`/`0xf6f0`) were really `folder_open`/`match_word`.
  Use the Material Symbols `.codepoints` file as the authority and keep every name passed to
  `icon()`/`symbolIcon()` backed by a map key — `icon()` now warns when it is not.
- External lookup can be dropped after a failed lookup: `_showArticle` rejects a
  reply whose word no longer matches `_requestedWord`.
- Article Back/Forward can lose the group scope it was opened in.
- SAF fallback (`ensureDefaultImportDir`) writes shared `<external>/Aurelex` on
  API 36 and can land on a blocked root instead of app-private storage.
- Speex (`.spx`) audio is silently skipped rather than explicitly indicated (#20).
- Release APK/AAB currently package every Qt kit library and plugin, including
  debug/tooling binaries (`app/build.ps1` staging), rather than a filtered set.
- FTS indexing now interleaves with other engine calls instead of holding the
  engine mutex for the whole build: existing dictionaries stay usable during a
  build, and the dictionary being built is withheld until its index completes.
  A very large dictionary is not auto-indexed during import; its index is built
  on the first full-text search over it (`fts-indexing-performance`).
- The remote catalog has **no on-device coverage at all** (#56–#72). It is the
  largest shipped feature with zero device verification, and the only one that
  depends on TLS working in a release build.
- Article zoom/reflow (#18a–#18g), the optional-parts expander (#18h–#18l) and
  the sense-marker icons (#18m–#18q) are likewise unexercised on a device.
- The compiled-in catalog URL is still the maintainer's temporary self-hosted
  share rather than the documented GitHub Pages address, so a released build
  cannot currently fetch the real catalog (`docs/REMOTE-CATALOG.md` § Hosting).

## Provenance

Device notes captured in archived changes: **Motorola ThinkPhone (Android 15)**.
The baseline pass was 2026-09-03 (folder-scoped SAF storage, recursive scan, FTS
prefix/whole-words, auto-index, history/favorites, theme toggle, external entry
points, tile/widget); later items were verified on later passes — the tri-state
theme control and FTS-indexing interleaving on 2026-09-29, the search-field focus
and floating-label fixes on 2026-10-01. Items still marked ⬜ have **not** been
seen on any device.