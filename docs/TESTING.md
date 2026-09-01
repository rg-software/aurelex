# TESTING — Aurelex v1 manual verification

Living, manual test checklist for the v1 feature set. Each item is a concrete
recipe: how to trigger it, and what to expect. Mark items with their current
status as you verify them so this doc stays the single source of truth for
"what works".

Status legend: ✅ verified on device · ⬜ not yet verified · 🔶 known gap

## Build & install

Before testing, the native library and APK must build. The project currently
**fails to build under JDK 25** (Gradle 8.7 + Kotlin DSL 1.9.22 compatible
with JDK 17–21 only). Use JDK 21:

```powershell
$env:JAVA_HOME = "C:\Program Files\OpenJDK\jdk-21.0.2"
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Dictionary management

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 1 | Search → Dictionaries → "Add dictionaries…", pick a folder with mdx / dsl(.dz) / ifo files | Files are scanned; count updates; entries listed with filename | ✅ |
| 2 | Add the same folder again | No duplicate entries (dedup by id), count unchanged | ✅ |
| 3 | Reorder with ↑/↓ | List order changes; article dictionary order follows | ✅ |
| 4 | Remove a dictionary (confirm dialog) | Entry removed; files not deleted; search no longer returns its words | ✅ |
| 5 | Remove the only loaded dictionary | Empty search state appears (see #6 in Distribution) | ✅ |

## Groups

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 6 | Search → Groups → "+ New", name it | Group created; appears in list with 0 dicts | ✅ |
| 7 | Groups → Edit on a group | Membership checkboxes toggle dictionaries in/out | ✅ |
| 8 | Apply a group (tap its name) | "Group:" label on the search screen updates; lookups only search that group's dicts | ✅ |
| 9 | Delete a non-default group | Group removed; "All" (id 0) cannot be deleted | ✅ |

## Lookup

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 10 | Type in the search field | Prefix + fuzzy headword suggestions appear | ✅ |
| 11 | Tap a suggestion / press "Look up" | Combined article renders, dictionaries in group order | ✅ |
| 12 | Look up an unknown word | "Word not found" screen with a way back, no crash | ✅ |
| 13 | Tap a link inside an article | In-app lookup of the linked word; back returns to previous article | ✅ |
| 14 | Open an article with images from an `.mdd` | Images render via `bres://` | ✅ |
| 15 | Article references a missing resource | Article still renders; broken item shown, no crash | ✅ |
| 16 | Tap a pronunciation anchor (ogg/mp3/wav) | Audio plays; speex shows an unsupported notice, no crash | ✅ |
| 17 | Look up the same word twice | One history entry (dedupe, moves to front) | ✅ |
| 18 | Look up a word not in any dict | **Not** added to history | ✅ |

## Dark mode (article + chrome)

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 19 | Article screen → "Dark mode" toggle | Whole screen goes dark — title, chrome **and the article body** (WebView reloads with dark CSS) | ⬜ (recently fixed) |
| 20 | Toggle back to "Light mode" | Article body returns to light styling | ⬜ (recently fixed) |
| 21 | Force-stop and relaunch in dark mode | Dark persists (stored in `PreferencesStore`) | ⬜ |

> Dark mode previously only themed the Compose chrome; the WebView now reloads
> when the same-word article HTML changes (`ArticleWebView.kt`). Verify both
> the Chrome *and* the article body flip.

## Full-text search

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 22 | Search → "Full text", run a word from an article **body** | Matched article headword returned | ✅ |
| 23 | Index list per dictionary | Shows built / missing; "Build" button appears when missing | ✅ |
| 24 | First search on an unindexed dict | Builds index, then returns results | ✅ |
| 25 | `read` (exact) vs `read*` (prefix) | Exact matches only / prefix matches both | ✅ |
| 26 | Result respects the active group | Hits limited to the applied group's dicts | ✅ |
| 27 | Tap a result | Opens the normal article for that headword | ✅ |

## Launcher shortcuts (QS tile + home-screen widget)

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 28 | Quick Settings → add the Aurelex tile | Tile present, labeled, with icon | ✅ |
| 29 | Copy text, tap the tile | Article for the copied text opens | ✅ |
| 30 | Tap the tile with an empty clipboard | Search screen opens with focus | ✅ |
| 31 | Home screen → widget → type a word → submit (IME actionSearch) | Article opens | ✅ |
| 32 | Widget/tile lookup respects the active group | Dyn. article rendered against the applied group, group unchanged | 🔶 (unverified on device) |
| 33 | Rotate/rescale the widget; restart the app, retap the tile | Widget stays tappable; tile still functional | 🔶 (unverified on device) |

## External lookup entry points

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 34 | In another app, select text → system **Share** → share to Aurelex | Article opens for the shared text | ✅ |
| 35 | In another app, select text → long-press **selection toolbar** → "…" → Aurelex (ACTION_PROCESS_TEXT) | Article opens for the selected text | ⬜ (recently added) |
| 36 | Share / PROCESS_TEXT / clipboard for an unknown word | "Word not found" screen, never a crash | ✅ |
| 37 | In-app search row → "Clipboard" button | Looks up the current clipboard text; blank clipboard is a no-op | ✅ (read path code-reviewed; Android 15 restricts automated clips) |

## History & favorites

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 38 | Search → History | Recent lookups, most recent first | ✅ |
| 39 | Tap a history word | Article opens and the word moves to the top | ✅ |
| 40 | Per-item ✕ and "Clear" | Item / all items removed; persists across restart | ✅ |
| 41 | Article → ☆/★ save | Appears in Favorites | ✅ |
| 42 | Favorites: tap to open, ✕ to remove | Works; persists across force-stop + relaunch | ✅ |

## Text-to-speech

> TTS is available only if the device has a TTS engine; Aurelex never crashes
> when it is absent.

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 43 | Article → 🔊 button | Device speaks the headword (engine-dependent) | ✅ |
| 44 | No TTS engine / disabled | Button hidden (TTS toggle) or feature unavailable without crashing | ✅ |

## Distribution & polish

| # | How to test | Expected | Status |
| --- | --- | --- | --- |
| 45 | Fresh install | Adaptive launcher icon (monochrome + color) in launcher, notification, and widget | ⬜ (pending 5.2) |
| 46 | Fresh install, no dictionaries | First-run onboarding screen appears with "Get started" | ⬜ (pending 5.2) |
| 47 | After onboarding, no dicts loaded | Empty search state: "No dictionaries yet" + "Add dictionaries…" | ⬜ (pending 5.2) |
| 48 | Existing install with history/dicts upgrades | Onboarding **skipped** (`PreferencesStore.onboarded` heuristic) | ⬜ (pending 5.2) |
| 49 | Tagged release build | Signed AAB (Play) + signed APK (GitHub/F-Droid) both produced with version from tag | ⬜ (pending 5.3) |

## Known gaps

- QS tile / widget active-group and rotation/restart cases (#32, #33) —
  tracked as `quick-lookup-shortcuts` 5.4/5.5.
- On-device icon/onboarding/empty-state/release-artifact verification (#45–#49)
  — tracked as `distribution-and-polish` 5.2/5.3.

## Provenance

Device notes captured in archived changes: Motorola ThinkPhone (Android 15),
verified 2026-09-01 — share target, history, favorites, TTS (Google TTS),
clipboard path, FTS index/search/prefix, widget, tile.