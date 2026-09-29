# TESTING — Aurelex v1 manual verification

Living, manual test checklist for the **Qt app** (the v1 feature set). Each item
is a concrete recipe: how to trigger it, and what to expect. Mark items with
their status as you verify them so this doc stays the single source of truth for
"what works".

Target: `app/` — the Qt Quick/WebView all-Qt UI that drives the
carved engine in-process via the `gd_*` C boundary. (Earlier iterations of this
doc described the removed Kotlin/Compose app; the recipes below target the Qt
UI.)

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
| 18 | Open an article with images from an `.mdd` | Images render | 🔶 (not exercised on-device — no MDX fixture yet) |
| 19 | Article references a missing resource | Article still renders; broken item shown, no crash | ✅ |
| 20 | Tap a pronunciation anchor (ogg/mp3/wav) | Audio plays; speex (`.spx`) is ignored, no crash | 🔶 (speex is silently skipped, not explicitly indicated) |
| 21 | Look up the same word twice | One history entry (dedupe, moves to front) | ✅ |
| 22 | Look up a word not in any dict | **Not** added to history | ✅ |

## Dark mode

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 23 | Toggle the **Dark mode** button in the bottom dock | Whole app re-palettes (Material theme follows `userDarkOverride`/`systemDark`); article re-renders in dark CSS | ✅ |
| 24 | Toggle back | Returns to the previous theme | ✅ |
| 25 | Follow-the-system: change the phone's theme (with the dark override off) | App follows the system dark/light setting (JNI system-dark read) | ⬜ (system switch not re-verified live) |
| 26 | Force-stop and relaunch after forcing dark | Dark persists (`userDarkOverride` stored in `files/settings.json`) | ✅ |

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

## Known gaps

- `.mdd` images not exercised on-device (#18) — needs a real MDict fixture.
- QS tile / widget active-group (#37) — inherited from `quick-lookup-shortcuts`.
- Dark-mode live system-switch (#25), icon visual (#47).
- StarDict import stages the `.ifo` but not its required sibling `.idx`/`.dict`
  files (`isSupportedDictionaryName`), so StarDict dictionaries do not currently
  load; the intended contract remains in `dictionary-management`.
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

## Provenance

Device notes captured in archived changes: Motorola ThinkPhone (Android 15),
verified 2026-09-03 across the Qt build — folder-scoped SAF storage, recursive
scan, FTS prefix/whole-words, auto-index, history/favorites, dark mode (manual
toggle), external entry points, tile/widget.