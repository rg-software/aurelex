## Why

The mobile MVP (search, article rendering, dictionary management) works on-device, but it is not yet an app people reach for every day: there is no way to look up a word from another app, no record of recent lookups, no favorites, and no spoken pronunciation. These are the small, pure-Kotlin conveniences that turn a working client into a daily-driver dictionary. They need no engine or boundary changes, so they are low-risk and high-value.

## What Changes

- **Share-sheet / intent lookup**: a "Look up in Aurelex" action offered when text is shared to the app (and an incoming lookup intent), which opens the article screen for that word.
- **Clipboard lookup shortcut**: an in-app action that reads the clipboard and looks up its text.
- **History**: every successful article lookup is recorded; a recent-lookups screen lists them (most recent first), tappable to re-look-up, with per-item and clear-all deletion.
- **Favorites**: an article can be saved as a favorite (and removed); a favorites screen lists them, tappable, reorder not required in v1.
- **Text-to-speech**: the article screen can pronounce a headword using the on-device TTS engine when one is available; graceful fallback when not.
- **Settings persistence**: the above features' state (favorites, history, TTS on/off) persists across app restarts; the existing dark-mode toggle becomes a persisted preference.

## Capabilities

### New Capabilities

- `usability-utilities`: everyday conveniences — giving the app external-lookup entry points (share sheet / intent / clipboard), recording and browsing lookup history, saving and browsing favorites, and on-device text-to-speech pronunciation.

### Modified Capabilities

- `lookup`: a lookup may now be triggered by an external entry point (share intent, clipboard, history/favorites tap) rather than only typing in the search field; these follow the same article-rendering and not-found behavior. Successful article lookups are recorded in history.

## Impact

- Pure Kotlin in `app/src/main/java/aurelex/android/`; no engine/boundary/`patches/` changes, no new native deps.
- `AndroidManifest.xml`: intent-filter for text share/VIEW (for external lookup), and any declared receiver if used.
- `MainViewModel`/`MainActivity`: entry points for external lookup intents; history/favorites/tts state and persistence (SharedPreferences/DataStore).
- Specs: new `usability-utilities` delta; `lookup` delta for external-entry lookup + history recording.