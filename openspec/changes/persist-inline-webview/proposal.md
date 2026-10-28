# Proposal

## Why

Switching away from Search and back (or opening/closing the group picker) destroys and recreates the article WebView every time: one navigation per switch plus a 311→82→286dp geometry jump during creation, each flashing the native surface black — visible as a black box blinking several times, even in Light mode. Measured on-device: exactly one create + one blank navigation per round trip.

## What Changes

- Keep the inline WebView alive across tab switches and picker sessions: instead of deactivating the loader, park the native view offscreen-left (`x = -(width + 10)`) whenever Search is not the visible tab or the picker is open. Geometry reaches the native view (unlike `visible: false`, which leaves it covering the screen); offscreen it draws nothing and receives no taps.
- The document persists, so returning needs zero navigations: the article/suggestions/history are simply still there. Remove the re-render-on-return paths; keep the first-creation blank document (JS context) and the height-reflow reloads (rotation reflow + scroll reset).
- No spec change: article rendering, suggestions, history and find behavior are unchanged — only the teardown policy goes away.

## Capabilities

None — existing scenarios hold unchanged (`skip_specs: true`).

## Impact

- `app/main.qml` only: loader activation predicate, WebView geometry, return/picker paths, comments. No boundary, engine, Java, or spec change.
