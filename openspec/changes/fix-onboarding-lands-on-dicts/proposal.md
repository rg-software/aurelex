## Why

The onboarding card tells the user to add dictionaries, then drops them on the
Search tab. Search is the wrong destination at that moment: it is where you look
a word up, and with no dictionaries loaded it is empty. The next action the card
asked for (tap the Folder or Cloud button, both on the Dicts tab) is behind a
navigation step the user has just been told nothing about.

This is the one onboarding decision that is currently surprising, and it is
purely a starting-tab choice.

## What Changes

- Tapping "Get started" leaves the user on the **Dictionaries** tab, so the
  Folder/Cloud buttons the card named are immediately in front of them, rather
  than switching to Search.
- Every later launch is unchanged: no onboarding → start on Search.
- First launch is unchanged: land on Dicts to host the overlay.

In short, only the post-onboarding destination moves: Search → Dicts (which is
where the user already is — the overlay is dismissed in place).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `distribution-and-polish`: the "First-run onboarding" requirement's dismissal
  scenario changes from "the app switches to the Search tab" to "the app stays on
  the Dictionaries tab". The first-launch and subsequent-launch scenarios are
  unaffected.

## Impact

- `app/main.qml` — the "Get started" handler's final `root.state` value.
- No engine, carve, catalog, Android-resource, or persistence change; the start
  tab is still not persisted, which stays out of scope.
