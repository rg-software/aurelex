# Design

## Contract change

The inline WebView used to be destroyed whenever Search was not the visible tab
(loader `active` gated on `state === 0`) or the group picker opened, and
recreated on return — one surface gap plus one blank navigation per round trip,
plus a 311→82→286dp geometry jump during creation (measured). The native view
ignores QML `visible`/`z` (hiding it leaves it covering the screen), but
geometry reaches it, so the view is now parked instead of destroyed.

## Mechanism

- New predicate `_articleParked = state !== 0 || _pickerOpen`.
- Loader `active` drops the state/picker gates (keeps the `inlineWebReady`
  first-creation deferral). `onLoaded` keeps the first-creation blank document
  and the lookup-race render; returns need nothing.
- The WebView swaps `anchors.fill` for explicit geometry: full area when shown,
  `x = -(width + 10)` when parked. Fully left of the window it is clipped —
  draws nothing, takes no taps — with no dependence on status heights or
  `mapToItem`. Height stays full so unparking never re-lays-out the page.
- `onStateChanged` no longer resets `inlineWebReady`/timer on leave; the picker
  no longer nulls `inlineWv` or re-arms readiness. Return-with-article does
  nothing (the document is there); return-with-query still refocuses and
  re-suggests onto the live document.
- Deliberately untouched: height-reflow reloads (`articleReloader` — rotation
  reflow and scroll-reset behavior stays, including rotations performed while
  parked), first-creation blank, overlay injection paths.

## Verification

Empty surface: Dicts→Search, FTS→Search, picker open/close — no black box, no
geometry jump (a11y bounds + screenshots). With an article: instant return, no
reload flash; rotation still resets scroll. Keyboard dock behavior (previous
change) re-checked since the loader area geometry moved lines.
