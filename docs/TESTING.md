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
| 8d | Remove an imported StarDict dictionary | Its staged companions and its index are deleted together; lookups stop returning its words | ✅ |
| 8e | Remove a dictionary, then **import the same folder again** | The re-import succeeds and the dictionary loads. Before `reclaim-staged-dirs-on-removal` the leftover blocked it: the removal deleted only the primary file, so the directory still held companions without a primary file, and staging does not re-copy files already present | ✅ |
| 8f | Stage **several dictionaries in one folder**, then remove one of them | Only that dictionary's file is deleted; the staged directory survives and the siblings keep loading. The reclaim only applies when nothing else uses the directory | ✅ |
| 8g | Import a DSL (`.dsl.dz`) and repeat 8d/8e | Same behaviour as StarDict — the fix is not format-specific. Verified for StarDict and DSL; MDict shares the shape but its removal has not been run on device | ✅ |
| 8e | With a failed import reported, tap its trash ("Remove failed import") in the banner | That import's staged files are deleted, the banner clears, and every other dictionary keeps working | ⬜ |
| 8f | Re-import the corrected folder after a failed import of the same folder | The dictionary loads and the previous failure is gone, with no manual storage cleanup | ⬜ |
| 8g | Leave a failed import reported and just restart / rescan | The failure is re-reported and its files are still there — the app never deletes an import on its own | ⬜ |
| 8h | Import a StarDict dictionary that keeps article images in a sibling `res/` folder (e.g. The World Factbook), then open a country's **Geography** entry | The locator and map GIFs render instead of missing-resource placeholders. `stardict-resource-staging` stages `res/` wholesale; before it, every `res/` file was dropped. On host the engine returns the 10310-byte `af_large_locator.gif` through `gd_get_resource` | ✅ |
| 8i | Import a folder that has a directory named `res` but **no** StarDict `.ifo` beside it | Nothing from that `res/` is staged — the name alone is not treated as a dictionary's resources | ✅ |
| 8j | Re-import an already-imported StarDict folder after adding a file to its `res/` tree | The new resource is staged **and** the dictionary's existing files survive. Before the `StagingService` overlay fix the re-import deduped the unchanged files against the folder's own copy and then replaced the directory with the partial temp copy, deleting the dictionary | ✅ |
| 8k | **Regression — nested import across a restart.** Import a folder whose only supported dictionary files are inside a **subfolder** (e.g. `GoldenDict/English/<Name>/<dict>.dsl.dz`, nothing at the top level), then force-stop and relaunch the app | The dictionaries are **still listed and searchable** after the restart. Before `fix-stale-sweep-deletes-live-dictionaries` the startup sweep classified the staged directory as an orphan, deleted it, and the dictionaries were gone — permanently, since the staged copy was the only copy the app owned. Check `adb logcat`: the line `staged sweep: in-use sources handed to the sweep =` must report a **non-zero** count, and there must be **no** `sweeping staged dir holding no dictionary` or `removing staged dir` for that source | ⬜ |
| 8l | Leave a genuinely empty leftover staged directory in `files/staged/` (an import that staged no dictionary at all), then restart | It is still reclaimed, and logcat shows `sweeping staged dir holding no dictionary`. Confirms the fix did not turn the sweep off: nested imports survive, true orphans do not | ⬜ |

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

### StarDict cross-references

StarDict articles cross-link each other with the `bword:` scheme, and those taps
did nothing until `stardict-bword-link-navigation`. The failure was in the
engine, not the app: the rewrite that turns these into resolvable links built
the URL by hand and produced a form nothing consumed. Three hand-written shapes
were each wrong in a different way — the tap did nothing, then the WebView
offered it to an external app ("unknown url scheme"), then the word was silently
truncated at its **space** (`Afghanistan` instead of `Afghanistan Geography`).
The correct shape was already in the tree: the DSL reader builds its refs as
`gdlookup://localhost/<word>`, and those navigate.

The World Factbook is the fixture that exposes this: it splits each country into
**ten** entries (`Afghanistan Introduction`, `Afghanistan Geography`, …) that
link to each other.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 23 | Open `Afghanistan Introduction` and tap a cross-reference | The linked entry opens (`Afghanistan Geography`, etc.) | ✅ |
| 24 | In `Afghanistan Geography`, check the flag/map images | They render | ✅ |
| 25 | Tap Back after a cross-reference | Returns to `Afghanistan Introduction` | ⬜ |

**Testing link rewriting without a device:** the lookup word is logged. Before
the fix it read `gd_lookup_in_group word=Afghanistan` — truncated. After, it
reads `gd_lookup word=Afghanistan Geography`. Asserting on that line is cheap,
needs no human at the device, and distinguishes all three wrong URL shapes in
one pass; it is the check that should have come first.

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

#### The indexing hang: hypotheses that were measured and ruled out

Recorded so nobody re-investigates them. Each was plausible from reading the
code, and each was **wrong**:

- a bogus record-block count spinning the build — `numRecordBlocks=29`, correct
- a headword block lacking a NUL terminator running `strlen` off the end — the
  block decompresses cleanly and walks to offset 1110 of 32,744
- `MdictParser::open()` as the stall — it completes in about 1 ms
- a `libgoldendict.so` / `DictMdict` crash — those symbols belong to a different
  project and appear in neither this repo nor the shipped APK

The real answer came from instrumentation that printed every iteration of the
charset conversion loop, which is the general lesson: when a device-only hang
resists reading, instrument the loop and read the numbers.

#### MDict indexing is now covered

It was not before this work, on host or device. A generated fixture
(`scripts/make-smoke-mdx.py`) drives the engine's own index build in CI, and the
on-device pass exercises it end to end.

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

Because zoom changes the root size, it scales the text that **inherits** that
size. It cannot scale text whose size a dictionary's own bundled stylesheet pins
in an absolute unit (`px`/`pt`) — such a declaration overrides the root for the
content it matches. That is a property of **that dictionary**, not of its
format: an `.mdx` with no bundled CSS scales exactly like a DSL file. See
"things that look like bugs and are not" below for the known case. This is
recorded as a deliberate limit (`article-zoom-honors-dictionary-css`); the app
does not override a dictionary's own typography to force it to scale.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 18a | Open an article, tap "Zoom in" twice (100 → 150%) | Text and images grow together; **no** horizontal scrollbar appears; long paragraphs re-wrap to the wider measure rather than being clipped | ⬜ |
| 18b | Tap "Zoom out" to the floor | Stops at 75%; the button greys out and stays there | ⬜ |
| 18c | Tap "Zoom in" to the ceiling | Stops at 250%; the button greys out and stays there. Check this on a dictionary that scales (Black's Medical `.mdx` or a DSL fixture) — a dictionary pinning absolute sizes will look unchanged, which is the known limitation, not a failure of the buttons | ⬜ |
| 18d | At 150%, look up a *different* word | The new article opens at 150% — zoom is a property of the surface, not of one article | ⬜ |
| 18e | Force-stop at 150%, relaunch, open an article | Still 150% | ⬜ |
| 18f | Zoom in on an article that has an `<img>` and a sense-marker icon | Both scale; the `gd_tag_*` icons stay inline with the text rather than drifting | ⬜ |
| 18g | Zoom to 75% on a long article and scroll to the end | No horizontal overflow at any zoom level, on a scaling dictionary and on `collinslaw` alike | ⬜ |
| 18r | Over CDP, read `getComputedStyle(document.documentElement).fontSize` at 100% and at 200% | It doubles (16px → 32px). This isolates the **mechanism** from the limitation: if the root does not change, zoom is broken; if it changes but `collinslaw`'s text does not, that is the documented limit | ⬜ |
| 18s | Open `law` in `collinslaw` at 100% and at 200%, reading `.gdarticlebody span`'s computed size | Stays **16px** at both, and its rendered width is unchanged. Expected — the dictionary sets `span { font-size: 16px !important }` | ⬜ |

One thing that looks like a bug and is not:

- **Zoom does nothing to `collinslaw`'s article text.** Its bundled `collinslaw.css`
  (inside the `.mdx`) sets absolute sizes on `span` (16px, `!important`), `body`
  (16px), `.s8` (16px) and `.citou_head` (19px/18px). `span` is what wraps the
  entry body, and it out-specifies the root, so the entry renders identically at
  every zoom level. Measured: at zoom 200 the root is 32px and `span` stays 16px.
  This is the known limitation above — do not file it as a zoom regression, and do
  not "fix" it by overriding the dictionary (that would flatten the citou/body
  size distinction the dictionary intends). The other two `collinslaw` surprises
  (no language pair, and an image it does not ship) are in the MDict section above.


## Article scrollbar clearance

Android's WebView draws **overlay** scrollbars: the thumb is composited over the
page and given no layout space, and `scrollbar-gutter` does not reserve space for
overlay scrollbars (it applies to classic ones only). The app therefore injects
`body { padding-right: 12px !important }` so the entry text stops short of the
right edge the thumb occupies. The strip is painted the article's own background
(synced to the app background), so it does not read as a separate gap
(`reserve-article-scrollbar-space`). Check by screenshotting mid-scroll — swipe,
then capture before the thumb fades — and scanning the pixel columns at the
article's right edge; on a 1080×2400 / 400 dpi device the WebView's right edge is
x=1044 and the thumb occupies the last 11 px, x=1034–1044.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 18t | Open a long article that **scales** (`The World Factbook 2014` → `Zimbabwe`), zoom to the 250% ceiling, scroll, screenshot mid-scroll | The thumb still clears the text: rightmost text ink x≈995, thumb x1034–1044 → ~39 px gap. The 12 px reserve holds at max zoom (measured — the reserve is in px and the text scales into it) | ✅ |
| 18u | At 100% (light), scroll a long article | Thumb x1034–1044 clear of the text; the reserved strip is the article background, no border or gap | ✅ |
| 18v | A short article that does not scroll, in both themes | Nothing drawn at the right edge — uniform `#FFFBFE` light / `#1C1B1F` dark | ✅ |
| 18w | `adb logcat` over the scroll/zoom pass | No `W`/`E`/`F` from the app's pid | ✅ |

`collinslaw` does not scale, so at any zoom its text is unchanged — that is the
known absolute-size limitation above, not a scrollbar-clearance failure.

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

## Orientation (portrait ⇄ landscape)

The Search tab's bottom dock once **disappeared in landscape** and only on that
tab — the one with the inline article `WebView`. The cause was a QML layout
overflow, not a stale native surface: `searchArticleArea` carried
`Layout.minimumHeight: 300` as the last item of a `ColumnLayout` that could not
shrink its search row, so on a landscape phone the column overflowed the pane and
spilled *downward* over the dock — and the `WebView`, being a native Android child
view, painted over it as well (native views ignore QML `z`/`clip`). Fixed by
`fix-article-surface-covers-dock`; the rotation teardown that the earlier
misl diagnosis had added was removed as unnecessary. If a landscape-only
disappearance comes back, check that floor before anything native — see the
measured numbers in that change's `design.md`.

To rotate reliably from a script, pin the rotation; **restore it afterwards**:

```powershell
$adb = "C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe"   # or add to PATH
& $adb shell settings put system accelerometer_rotation 0   # 0 = follow user_rotation
& $adb shell settings put system user_rotation 1            # 1 = landscape, 0 = portrait
& $adb shell settings put system accelerometer_rotation 1   # restore auto-rotate
```

Open an article without typing, for a repeatable cold start:

```powershell
& $adb shell am force-stop org.aurelex.pocket.dictionary
& $adb shell am start -a android.intent.action.VIEW -d "aurelex://lookup?word=law" org.aurelex.pocket.dictionary
```

Two cheap checks that catch this class of bug without eyeballing a screenshot:
`adb shell uiautomator dump` and compare the `Dictionary article` bottom edge with
the `Main navigation` top edge (the article must end **above** the dock), and count
magenta pixels in the dock's bottom band — the active tab paints the accent, so a
band that is the article instead reads near zero (device reference: portrait dock
visible ≈ 470 accent px, the bug ≈ 15, fixed landscape ≈ 594).

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 70 | Search tab with an article open, rotate to landscape | The bottom dock stays fully visible and tappable, and the article ends **above** it | ✅ (measured: article bottom 822 vs dock top 856 in device px; dock tab tap navigates) |
| 71 | Rotate back to portrait | Dock visible again, same article still open | ✅ (470 accent px) |
| 72 | Force-stop with the device **already in landscape**, relaunch, open an article | Dock visible on the first landscape frame — no rotation event needed | ✅ (594 accent px; article bottom 821 < 856) |
| 73 | Rotate twice in a row with an article open, touching nothing | No flicker to a half-drawn dock, no crash, article survives both | ✅ |
| 74 | Rotate on the Dictionaries and Full-text search tabs (no article surface there) | No regression; system insets still correct (the bottom inset goes to 0 on rotation) | ✅ (600 accent px in landscape on both tabs) |
| 75 | Search tab, tap the field, type slowly while the keyboard opens and closes | Headword suggestions appear as you type, the open article is not disturbed, the dock stays visible | ✅ (guard for the removed teardown: `mInputShown=true`, `smok` → suggestions `Smoking` / `Smoke Inhalation`) |
| 76 | Scroll an open article down, then rotate to landscape and back | The article returns to the **top**. This is the pre-existing responsive-reflow path (`articleReloader` re-renders the HTML whenever the WebView's height changes, and `loadHtml` resets the scroll) — not the removed rotation teardown, which only added a second reset. Recorded here so it is not re-attributed to the landscape fix; restoring the offset is a separate change | ✅ (measured: scrolled → rotate → back is pixel-identical to the unscrolled article; 0 % differing vs 9.5 % for top↔scrolled) |
| 77 | Landscape article band | Tight but usable: the article keeps ~42 px below its 40 px toolbar. Portrait is unaffected (the value is a floor, not a fixed height) | ✅ (by construction; the article is scrollable from there) |

## Display cutout (punch-hole camera)

The window always renders edge-to-edge — Android 15 enforces
`layoutInDisplayCutoutMode=always` for this target SDK, so there is no letterbox
to configure. What is checked here is that the app's **content** clears the camera:
the article, the search row and the outermost dock tab must not sit under it.

Measure in numbers, not by eye. The camera's occupied area comes from the
platform and the app's layout comes from the accessibility tree, both in the same
device pixels:

```powershell
adb shell dumpsys window displays | Select-String 'type=displayCutout frame='
adb shell uiautomator dump /sdcard/u.xml; adb pull /sdcard/u.xml .
```

Compare the cutout's frame with the outermost content node's bounds — the article
is `Dictionary article`, the first dock tab is `Search`. Content must start at or
past the cutout edge. Reference on a 1080×2400 device, density 2.5:

| orientation | cutout frame | what to expect |
|---|---|---|
| portrait | `[0,0][1080,110]` (top, full width) | **no** side inset; the camera sits inside the inert top strip, so article `x0` stays at the usual margin |
| landscape, camera left | `[0,0][110,1080]` | left inset applied — article `x0` ≈ 142 |
| landscape, camera right | `[2290,0][2400,1080]` | right inset applied — article `x1` ≈ 2256 |

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 78 | Portrait, article open | The camera area is covered by the non-interactive top strip and **nothing changes** vs. a device with no cutout. Portrait is unchanged by design — the camera's horizontal safe insets are 0 there — so a report that portrait "looks different" is not a regression | ✅ (article `x0=33`, no side inset) |
| 79 | Rotate to landscape with the camera on the **left** | The article, the search field and the leftmost dock tab all start clear of the cutout | ✅ (article `x0=142`) |
| 80 | Rotate to landscape with the camera on the **right** (flip the phone the other way) | The right-hand cells clear the cutout and the left edge is **not** inset — the insets are per-edge, not symmetric | ✅ (article `x1=2256`, right clearance 144 px) |
| 81 | **Flip between the two landscape orientations directly** (`adb shell settings put system user_rotation 1` then `3`, never passing through portrait) | The clearance follows the camera to the other side. This is the case a resize-based re-read silently misses: both landscape orientations are the same window size, so no resize signal fires while the cutout moves sides | ✅ (right clearance 144 px, then left 142 px on the way back) |
| 82 | Force-stop with the device **already** in landscape, relaunch, open an article | Correct clearance on the first frame — no rotation event to react to | ✅ (right clearance 144 px) |
| 83 | Rotate back to portrait | The side margins return to 0 — no leftover inset on either edge | ✅ (article `x0=33`) |
| 84 | Rotate on the Dictionaries, Groups, Full-text search and Favorites tabs | Every pane inherits the same side inset (they share one anchor line) | ✅ (all four report `x0=33 x1=2256`) |
| 85 | Both themes, look at the strip beside the camera | The strip is **indistinguishable** from the neighbouring background — no black band, no unthemed edge | ✅ (light `#FFFBFE`, dark `#1C1B1F`, matching at the left strip, right strip and top strip) |
| 86 | Search tab with the keyboard open in landscape | The inset path does not disturb the open article; the right edge still clears the cutout | ✅ (article `x1=2256` with `mInputShown=true`) |
| 87 | Whole rotation pass, then read the app's logcat | No new warnings from the app's pid, no ANR, no crash | ✅ (only pre-existing `Qt A11Y: empty contentDescription` notices) |

### Two measurement traps

Both of these make a run report a false PASS if you do not notice them:

- **`adb shell am force-stop` resets `user_rotation` to 0 on this device.** If you set the rotation *before* the force-stop, a "cold start already in landscape" run actually launches in portrait and passes trivially. Correct order: force-stop → set rotation → **confirm** the cutout frame is a side edge → launch.
- **Read the element's bounds before tapping it.** The theme cell's position depends on the dock layout (its a11y bounds were `1909..2290` in landscape with the camera on the right), so a tap at a guessed coordinate can land on the boundary and silently do nothing — which then looks like "the theme toggle is broken".

### Known cosmetic difference (not a regression)

The article canvas is **not** the same colour as the app background:
`#FFFFFF` vs `#FFFBFE` in light, `#242526` vs `#1C1B1F` in dark. The WebView paints
its own `--gd-bg` constant while the app uses Material's `background`, so they are
two independent choices of "background". This predates the cutout work, is
unrelated to it, and affects the whole article area rather than any edge — the
inset strips themselves do match the app background exactly (row 85). Matching
them would mean driving `--gd-bg` from the Material palette; not done, because
the light-theme delta is 1/255 and invisible while the dark-theme one is a
cosmetic preference, not a defect.

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

The app defaults its display language to the UI language of its process, trying
the full locale (`ru-RU`) before the language (`ru`) and falling back to English
when no catalog matches. **RU** and **JA** are shipped as
`app/i18n/aurelex_ru.qm` / `aurelex_ja.qm`.

**To switch the language for a run** (no in-app switcher exists — the translator
is installed once at startup, so every switch needs a cold start):

```powershell
$adb = "C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe"   # or add to PATH
$pkg = "org.aurelex.pocket.dictionary"

& $adb shell cmd locale set-app-locales $pkg --user 0 --locales ru-RU   # or ja-JP
& $adb shell am force-stop $pkg                                         # required
& $adb shell am start -n "$pkg/.AurelexActivity"
& $adb shell cmd locale set-app-locales $pkg --user 0 --locales ""     # back to device language
```

That per-app path needs **Android 13+** and an app the system is willing to
re-locale; Aurelex declares no `android:localeConfig`, so it is *not* listed
under *Settings → Apps → Aurelex → Language* and `cmd locale` can be refused
(known gap — see "Switching the display language for testing" in
`docs/DEVELOPMENT.md`). On an older device, or if the switch is refused, change
the **system** language (*Settings → System → Languages & input*) and relaunch.
When checking a language, verify what Qt actually picked instead of trusting the
settings screen:

```powershell
& $adb logcat -d | Select-String "using translation catalog|no matching translation"
```

The catalog source of truth and the `update-translations.ps1` lupdate/lrelease
workflow are documented under "Localization" in `docs/DEVELOPMENT.md`.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 50 | Switch the app (or system) language to **Russian**, relaunch | Navigation, search placeholder, dictionary/group/FTS/favorites labels, onboarding, dialogs, banners ("Indexing (…)"), "engine error" wrapper, history "No lookups yet"/"Clear all", Not Found term in Russian; group names/dictionary names stay as-is | ⬜ (needs a device with RU; build.ps1 verified) |
| 51 | Same with **Japanese**, relaunch | Same set in Japanese | ⬜ (needs a device with JA) |
| 52 | Set the app/system language to one without a catalog (e.g. **Finnish**), relaunch | Falls back to English, no crash, logcat line `[aurelex] no matching translation catalog; using English base strings` | ⬜ (needs a device with a non-RU/JA locale; logcat can confirm the message) |
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
  subset is built by `scripts/build_symbol_subset.py`, which pins `hhea`/OS-2 `asc=upm`,
  `desc=0`, sets `USE_TYPO_METRICS`, and zeroes the `post` underline. It carries **five**
  glyphs: `folder_open`, `match_word`, `light_mode_auto` (the theme toggle), and
  `text_decrease` / `text_increase` (the article toolbar's zoom controls, which use an
  "A-"/"A+" so they state "article text size" instead of reading as a magnifier). Add a
  new secondary glyph by codepoint in that script's `GLYPHS` map and regenerate the
  subset — a glyph referenced in QML but absent from the font renders as tofu. Bundled resources
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