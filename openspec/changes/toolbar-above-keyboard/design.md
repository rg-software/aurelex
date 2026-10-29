# Design

## Context

At this baseline the bottom dock is anchored to `parent.bottom` with no lift, so on
the `adjust=pan` path (API <= 29) the keyboard covers it. API 30+ lifts it
automatically via window resize, but with a residual gap on some devices (Motorola).
The lift machinery (`visibleBottom`, `displayHeight`, `imeActuallyVisible`,
`_kbdPad`) comes from `b2dbc06` and is being reintroduced in isolation here; the
settled-state IME probe is deliberately NOT included (that is the later
"IME visible" change). See proposal.md.

## Goals / Non-Goals

**Goals:**
- Dock stays visible and tappable above the keyboard on API <= 29 (`adjust=pan`).
- Dock sits flush against the keyboard on API 30+ (no residual gap), including
  Motorola.

**Non-Goals:**
- No IME show/hide changes.
- No WebView parking changes.
- No settled-state probe (deferred to the IME change).

## Decisions

1. **Re-introduce the instantaneous dock lift from `b2dbc06`**: `navDock` gains
   `bottomMargin: root._kbdPad`, and `_refreshInsets()` computes `_kbdPad` from
   `visibleBottom()`/`displayHeight()`/`imeActuallyVisible()`.
2. **API <= 29 keeps `adjust=pan`** (resize destroys the EGL surface). The manual
   pad is the only lift there.
3. **API 30+ keeps resize** as the primary path; `_kbdPad` becomes a corrective
   pad only when resize leaves a gap (Motorola). The pad is a no-op when resize
   already cleared the keyboard.
4. **Instantaneous visibility only.** `imeActuallyVisible()` (not the settled
   probe) gates the lift, since the probe is not yet available. A later change
   swaps in the settled probe.

## Risks / Trade-offs

- [Risk] On API <= 29 the visible-frame comparison may be unreliable on some
  OEMs (Huawei observed toolbar under keyboard). → Mitigation: measure
  `visible.bottom`/`fullBottom`/`stableBottom` on the target device and adjust
  the formula or fall back to a fixed pad.
- [Risk] Double-application if resize and pad both apply. → Mitigation: pad is
  `max(0, occluded)` and computes to ~0 when resize already shrank the window.
- [Trade-off] Instantaneous flag can lie in the fake state; accepted until the
  IME probe lands.