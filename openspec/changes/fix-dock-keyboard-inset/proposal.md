# Proposal

## Why

On Android 9–10 (API 28–29), opening the keyboard while on the Search tab pushes the bottom navigation dock up into mid-screen: the dock grows to ~311dp tall with the tab row stranded at its top, above a white slab, with the keyboard below that. Seen on Huawei VOG-L29 / Android 10 after FTS → Search (the Search field takes focus, the keyboard opens).

The Play build instead keeps the dock bottom-aligned everywhere, so the open keyboard obscures it. That behavior is consistent but leaves navigation unreachable while typing; this change deliberately improves on it: the dock stays visible — bottom when the keyboard is closed, directly above it when open. The current cut of the fix does not achieve that reliably yet (dock position flaps across keyboard transitions); making it settle is part of this change.

## What Changes

- `AurelexActivity.getSystemInsetBottom()`: stop counting the open keyboard as bottom safe-area. API 30+: read `WindowInsets.Type.systemBars()` (already excludes IME). API 28–29: read `getStableInsetBottom()` (nav bar only, never the IME) instead of `getSystemWindowInsetBottom()` (which folds the IME in when it is shown).
- No QML change: with `adjust=resize` the window already shrinks for the keyboard, so the dock at the bottom of the shrunk window sits above the keyboard on its own. The inset must only ever be nav-bar/cutout.

## Capabilities

No spec change: the specified behavior (dock above the system nav area) is unchanged — this restores it on API 28–29. Setting `skip_specs: true`.

## Impact

- `app/android/src/.../AurelexActivity.java` only. No boundary, engine, QML, or spec change.
