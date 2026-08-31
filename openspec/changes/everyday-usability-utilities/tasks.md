## 1. External lookup entry points

- [x] 1.1 Add intent-filter for `ACTION_SEND` text/plain (+ `VIEW`/custom word intent) and `launchMode="singleTop"` in the manifest; read incoming text in `MainActivity.onNewIntent` and route to `MainViewModel.lookup`.
- [x] 1.2 Add a clipboard-lookup action on the search screen (read `ClipboardManager` primary clip; look up non-blank text).

## 2. Lookup history

- [x] 2.1 Add a persisted history list (SharedPreferences) loaded at startup; record successful lookups with dedupe+move-to-front, cap length (~100); not-found lookups not recorded.
- [x] 2.2 Add a History screen: list recent lookups (most recent first), tap-to-look-up, per-item remove, clear-all; navigate via existing back-stack.
- [x] 2.3 Expose history removal/clear so the shared preferences stay consistent.

## 3. Favorites

- [x] 3.1 Add a persisted favorites list (SharedPreferences): save current article's word, remove, insertion-ordered.
- [x] 3.2 Add a Favorites screen: list, tap-to-look-up, remove; navigate via existing back-stack.
- [x] 3.3 Add save/remove-favorite action on the article screen reflecting current state.

## 4. Text-to-speech

- [x] 4.1 Add a platform `TextToSpeech` helper (lazy init, speak(headword, QUEUE_FLUSH)); graceful "TTS unavailable" when init fails or no engine present; always release in onDestroy.
- [x] 4.2 Add a pronounce action on the article screen gated by a TTS-on/off persisted toggle.

## 5. Settings persistence

- [x] 5.1 Add a small `PreferencesStore` over SharedPreferences for dark-mode toggle, TTS toggle, history, and favorites; load at startup, write on change.
- [x] 5.2 Make the existing dark-mode toggle persist through preferences.

## 6. Verification

- [x] 6.1 Host/build: `assembleDebug` passes; unit-verify persistence logic where feasible.
- [x] 6.2 On-device: share text to Aurelex → article opens; clipboard lookup → article opens; lookups appear in history; favorite save/remove/list works; pronunciation speaks (or shows unavailable when no engine); preferences survive restart.

On-device (Motorola ThinkPhone Android 15):
- **Share intent** `ACTION_SEND` EXTRA_TEXT="water" → article screen "From Aurelex Basic / [!trn]aqua / [note]Drink more water." ✅
- **History**: "hello" recorded, listed, tap-to-look-up → article, Clear button present ✅
- **Favorites**: "hello" saved via article ☆, listed on Favorites screen, persists across force-stop+relaunch ✅
- **TTS**: 🔊 triggers GoogleTTSService synthesis ("Synthesis request for locale rus-RUS") — speaks ✅
- **Clipboard**: button present on second search row; handler reads ClipboardManager and routes through the proven lookup path (system clipboard-set from adb is restricted on Android 15, so the read itself was verified by code review + shared-path test, not an automated tap)