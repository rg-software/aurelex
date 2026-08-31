## Context

The v1 app is a single-activity Compose app (search → article → dictionaries) with the engine in a separate process (`EngineClient` via Messenger). Lookups currently flow only from the search screen's typed query. This change adds pure-Kotlin conveniences on top of that existing structure — no engine/boundary changes. See proposal.md — Why for motivation; specs for the behavioral contract.

## Goals / Non-Goals

**Goals:**
- External lookups (share sheet, intent, clipboard) reuse the existing article-rendering path.
- History and favorites are simple persisted lists of headwords shown in the existing navigation.
- TTS pronunciation uses the platform `TextToSpeech` API with graceful fallback.

**Non-Goals:**
- No favorites reordering (v1 favorites are insertion-ordered).
- No full-text search or format additions (separate roadmap items).
- No engine/boundary/`patches/` changes.

## Decisions

### D1. External lookup entry points: intent-filter + clipboard action
The app declares an intent-filter for `ACTION_SEND` (text/plain) so Android offers "Look up in Aurelex" from other apps' share sheets, plus handles a `VIEW`/custom intent carrying a word. `MainActivity.onNewIntent` routes the incoming text into the same `MainViewModel.lookup(word)` used by the search screen. The clipboard lookup is a button in the search screen that reads `ClipboardManager` primary clip text and looks it up.
- Alternative: a dedicated `Activity` per entry — rejected (single-activity is simpler; `onNewIntent` + `launchMode=singleTop` suffices).

### D2. History & favorites: persisted headword lists
History and favorites are stored as simple ordered lists of headwords in SharedPreferences (JSON), loaded into the ViewModel at startup and written on every mutation. Successful lookups append to history (dedupe + move-to-front); failed/not-found lookups are not recorded (per spec). Favorites are explicit add/remove, insertion-ordered.
- Alternative: a Room DB — overkill for flat headword lists; SharedPreferences is sufficient and dependency-free.

### D3. TTS: platform `TextToSpeech` with graceful fallback
A `TextToSpeech` instance is created on demand (lazy) and used to speak the current article's headword (`speak(headword, QUEUE_FLUSH, ...)`). If `TextToSpeech` init fails (`ERROR` status) or no engine is installed, the UI shows a non-crashing "TTS unavailable" message. TTS-on/off is a persisted toggle that gates the speak action.
- Alternative: pre-buffer audio via the engine — cut for v1 (the boundary has no TTS); platform TTS is the low-risk path.

### D4. Settings persistence
All persisted state (dark-mode toggle, TTS toggle, history, favorites) is read/written through one small `PreferencesStore` abstraction over SharedPreferences, so future onboarding/settings screens share it. Loading happens in `AurelexApp`/ViewModel init; writes are immediate and async-safe.

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| Share-intent routing races the engine bind (user opens from share before engine ready) | `lookup` already catches engine errors and shows "engine not ready"; resumeScan on the article path re-tries |
| History grows unbounded | Cap history length (e.g. 100) with clear-all available; drop oldest |
| TTS engine quality/absence varies | Graceful "unavailable" message per spec; TTS toggle lets users disable |
| WebView article doesn't expose per-word address for "favorite" | Favorite stores the looked-up headword (the article's word), not a DOM anchor — sufficient for re-look-up |

## Migration Plan

Greenfield — no existing users/data to migrate. Adding persisted prefs is additive; old installs simply start with empty history/favorites and default toggles.

## Open Questions

- Do users want favorites to support a note/annotation? (Defer — not in specs; additive later.)
- Should history dedupe move-to-front or keep insertion order? (Chosen move-to-front in D2; could revisit without spec changes.)