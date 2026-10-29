# Proposal

## Why

On API 29 and below the window does not resize for the keyboard (`adjust=pan`,
chosen to avoid an EGL-surface recreation), so the bottom navigation dock stays
at the bottom of the full window and is covered by the keyboard. The
`_kbdPad` lift that `b2dbc06` introduced (manual pad from visible-frame
occlusion) was part of the bundled redesign we are reintroducing one piece at a
time; this change isolates it. On API 30+ the dock lifts automatically via
resize, but a residual gap between the lifted dock and the keyboard remains on
some devices (observed on Motorola).

## What Changes

- Re-introduce the manual dock lift for the `adjust=pan` path (API <= 29):
  pad the dock up by the occluded part of the visible frame.
- Measure and fix the residual gap on API 30+ devices (Motorola) so the dock
  sits flush against the keyboard.
- No change to WebView parking, IME show/hide, or article rendering.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None (UI layout only; no spec-level behaviour change).

## Impact

- `app/main.qml`: `navDock` bottom margin, `_kbdPad`, `_keyboardShown()`,
  `_refreshInsets()`.
- `app/EngineController` / `AurelexActivity` already expose `visibleBottom()`,
  `displayHeight()`, `imeActuallyVisible()` (from the IME work on `main`);
  this change consumes them on the `adjust=pan` path.