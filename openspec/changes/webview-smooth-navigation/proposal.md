# Proposal

## Why

Returning to the Search tab after visiting another pane (or opening the group
picker) currently destroys and recreates the inline article WebView, which
re-renders the article and flashes the native surface (black blink on Android).
Commit `b2dbc06` fixed this by parking the WebView offscreen instead of
destroying it, but that fix was bundled with a broader GUI redesign that
introduced regressions (shared query editor, focusless nav row, dock lift). This
change isolates the WebView-parking fix so it can be validated on its own before
any of the surrounding redesign is reintroduced.

## What Changes

- Keep the inline article WebView alive across Search-tab leave/return and across
  group-picker open/close: park it offscreen (clipped by the window) instead of
  tearing it down, so its document and scroll position persist.
- On return to the Search tab with an article showing, reuse the persisted
  document instead of re-rendering; only refocus/re-query suggestions when no
  article is shown.
- No change to article lookup, history, favorites, or the suggestion pipeline.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lookup`: adds the "Inline article surface persistence" requirement — the
  inline article surface SHALL survive tab switches and picker sessions without
  re-rendering or a visible flash, and SHALL restore the prior article and its
  scroll position on return.

## Impact

- `app/main.qml` only: the Search-tab inline WebView loader (`searchArticleLoader`)
  and the `onStateChanged` / picker-open handlers that currently tear it down.
- No engine, boundary, patch, or localization changes.
- No change to IME/keyboard behavior (handled by separate changes).