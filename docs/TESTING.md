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
`build-qtquick/apk/build/outputs/apk/debug/`. The package is `aurelex.android`.

## Dictionary management (one-off import, folder-scoped SAF)

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 1 | Dictionaries tab → "Add dictionaries" | The Android folder picker (SAF) opens; pick a folder with mdx / dsl(.dz) / ifo files | ✅ |
| 2 | After picking, check the Dictionaries list | Files scanned recursively (subfolders included); entries listed once imported | ✅ |
| 3 | Watch the Dicts banner during import | "Preparing dictionaries…" → "Scanning dictionaries…" → progress bars while indexing | ✅ |
| 4 | Add an intersecting folder (e.g. a subfolder of an already-imported folder) | The same dictionary is not duplicated (staged-copy dedup) | ✅ |
| 5 | Re-import the same folder again | No duplicate entries (dedup by id), count unchanged | ✅ |
| 6 | Reorder within a group (Groups tab) | Group article order follows membership order | ✅ |
| 7 | Remove a dictionary (confirm dialog) | Entry removed; search no longer returns its words; its staged copy + index are deleted (Reload after removal confirms it's gone) | ✅ |
| 8 | No dictionaries / import a folder with none | Empty state / onboarding hint appears; "no supported dictionaries" is shown | ✅ |

## Groups

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 10 | Groups tab → "New group name" → enter | Group created; appears in the list | ✅ |
| 11 | Groups → "Dicts" on a group | Membership editor: add/remove/move dicts in the group | ✅ |
| 12 | "Active" on a group | Active-group id changes; lookups only search that group's dicts | ✅ |
| 13 | Delete a non-default group | Group removed; "All" (id 0) cannot be deleted | ✅ |

## Lookup

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 14 | Type in the search field | Prefix + fuzzy headword suggestions appear | ✅ |
| 15 | Tap a suggestion / press return | Combined article renders, dictionaries in group order | ✅ |
| 16 | Look up an unknown word | "Word not found" indication, no crash | ✅ |
| 17 | Tap a link inside an article | In-app lookup of the linked word; back returns to previous article | ✅ |
| 18 | Open an article with images from an `.mdd` | Images render | 🔶 (not exercised on-device — no MDX fixture yet) |
| 19 | Article references a missing resource | Article still renders; broken item shown, no crash | ✅ |
| 20 | Tap a pronunciation anchor (ogg/mp3/wav) | Audio plays; speex shows an unsupported notice, no crash | ✅ |
| 21 | Look up the same word twice | One history entry (dedupe, moves to front) | ✅ |
| 22 | Look up a word not in any dict | **Not** added to history | ✅ |

## Dark mode

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 23 | Toggle the top-bar **D** button | Whole app re-palettes (Material theme follows `userDarkOverride`/`systemDark`); article re-renders in dark CSS | ✅ |
| 24 | Toggle back | Returns to the previous theme | ✅ |
| 25 | Follow-the-system: change the phone's theme (or set dark override off) | App follows the system dark/light setting (JNI system-dark read) | ⬜ (system switch not re-verified live) |
| 26 | Force-stop and relaunch in dark the override was forced | Dark persists (`userDarkOverride` stored in `files/settings.json`) | ✅ |

## Full-text search

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 27 | FTS tab, run a word from an article **body** | Matched article headword returned | ✅ |
| 28 | Index builds automatically on add | Indexing progress bar shows while building; no manual "Build" button | ✅ |
| 29 | `boo` (prefix, default) | Matches `book` etc. (prefix) | ✅ |
| 30 | Check "Whole words" then `boo` | Exact-term match only (no `book`) | ✅ |
| 31 | Result respects the active group | Hits limited to the applied group's dicts | ✅ |
| 32 | Tap a result | Opens the normal article for that headword | ✅ |

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
| 42 | History tab | Recent lookups, most recent first | ✅ |
| 43 | Tap a history word | Article opens and the word moves to the top | ✅ |
| 44 | Per-item swipe ✕ and "Clear all" | Item / all items removed; persists across restart | ✅ |
| 45 | Article → ☆/★ star | Appears in Favorites | ✅ |
| 46 | Favorites: tap to open, swipe ✕ to remove | Works; persists across force-stop + relaunch | ✅ |

## Distribution & polish

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 47 | Fresh install | Adaptive launcher icon in the launcher; onboarding screen shows on first launch | ⬜ (icon visual not re-checked; onboarding verified) |
| 48 | After onboarding, no dicts loaded | Empty search state: guidance to add dictionaries | ✅ |
| 49 | Tagged release build | Signed APK produced on a `vX.Y.Z` tag push | ⬜ (Release Java build fixed + verified locally; first signed CI run pending a tag push — keystore secrets configured) |

## Known gaps

- `.mdd` images not exercised on-device (#18) — needs a real MDict fixture.
- QS tile / widget active-group (#37) — inherited from `quick-lookup-shortcuts`.
- Dark-mode live system-switch (#25), icon visual (#47), signed-release artifact (#49 — Release Java build fixed; CI run pending).

## Provenance

Device notes captured in archived changes: Motorola ThinkPhone (Android 15),
verified 2026-09-03 across the Qt build — folder-scoped SAF storage, recursive
scan, FTS prefix/whole-words, auto-index, history/favorites, dark mode (manual
toggle), external entry points, tile/widget.