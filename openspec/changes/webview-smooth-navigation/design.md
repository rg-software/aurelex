# Design

## Context

At this baseline (`a1df606`), the Search tab's inline article WebView is created by
`searchArticleLoader` (active only on the Search tab with `inlineWebReady`) and
destroyed on leave, so returning re-creates the native surface and re-renders
`currentHtml` — the black blink. The genuine fix from `b2dbc06` was to keep that
WebView alive across tab switches and picker sessions by parking it offscreen
instead of destroying it. This design isolates that fix from the rest of the
`b2dbc06` redesign (shared query editor, focusless nav row, dock lift), which
are tracked as separate changes.

## Goals / Non-Goals

**Goals:**
- Eliminate the WebView re-creation / re-render flash on Search-tab return and
  picker close.
- Preserve the article document and scroll position across those transitions.

**Non-Goals:**
- No IME/keyboard changes (tracked separately).
- No nav-row redesign or dock-lift changes.
- No change to article lookup, history, or favorites logic.

## Decisions

1. **Park instead of destroy.** The loader stays active and the WebView is moved
   offscreen (clipped by the window) while another pane or the modal picker is
   up, keeping its native surface and document intact. Alternative (re-create on
   return) is the status quo and causes the flash; rejected.
2. **Keep `inlineWebReady` deferral.** The WebView is still created only after the
   Search tab is measured (420 ms timer), so a freshly created surface locks to
   the correct band size rather than the full window. Reusing this avoids
   reintroducing the full-window-surface bug.
3. **Restore article on return without re-render.** When returning with an
   article showing, do nothing beyond letting the persisted document remain; only
   refocus/re-query suggestions when no article is showing. Alternative
   (re-render `currentHtml` on return) re-introduces the flash; rejected.

## Risks / Trade-offs

- [Risk] A parked (but alive) native WebView can overlay other panes if geometry
  is wrong. → Mitigation: clip fully offscreen-left; the loader's `active` binding
  still gates creation on `state === 0`.
- [Risk] Memory: one extra native surface kept alive. → Mitigation: only while
  the app is in the foreground; acceptable on target devices.
- [Trade-off] Scroll position is preserved by the native surface, but a future
  WebView recreation (e.g. on config change) still re-renders; accepted.

## Open Questions

None blocking. Device validation on Motorola (API 35) and Huawei (API 29) is
the acceptance gate.