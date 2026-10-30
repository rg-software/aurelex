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
- Dock stays visible and tappable above the keyboard on every device.
- The lift must work whether or not the window resizes: measured occlusion
  where the platform reports IME insets (Xiaomi, Motorola), focus-based
  estimate where it does not (Huawei/EMUI).

**Non-Goals:**
- No IME show/hide changes.
- No WebView parking changes.
- No settled-state probe (deferred to the IME change).

## Decisions

1. **Re-introduce the instantaneous dock lift from `b2dbc06`**: `navDock` gains
   `bottomMargin: root._kbdPad`, and `_refreshInsets()` computes `_kbdPad` from
   `visibleBottom()`/`displayHeight()`/`imeActuallyVisible()`. Verified on Qt
   6.10.3 (2026-10-29) that NO device resizes the window for the keyboard when
   no `windowSoftInputMode` is set — not even API 35/36 — so the manual pad is
   the lift everywhere, not just on API <= 29. The "no double-application"
   guard (pad computes to ~0 when a resize did shrink the window) stays as a
   safety net.
2. **No `windowSoftInputMode` override.** The manifest sets none; Qt's default
   applies on all API levels. Do NOT set `adjust=resize` (EMUI ignores it) or
   `adjust=pan` (nothing needs it while the pad does the work).
4. **Instantaneous visibility only.** `imeActuallyVisible()` (not the settled
   probe) gates the lift, since the probe is not yet available. A later change
   swaps in the settled probe.

## Huawei fallback (verified 2026-10-29, reverted in 6e764c1 — re-apply after Qt upgrade)

On Huawei/EMUI (API 29) no IME-visibility signal works: `adjust=resize` is
ignored, the visible frame never shrinks, system/stable insets stay 0, and
`InputMethodManager.mInputShown` reflection fails (`NoSuchFieldException`).
The fallback that was verified working (uiautomator: nav row y=2055→y=1149):

1. `_refreshInsets()` gains the pad computation: if `imeActuallyVisible()`,
   measured occlusion (`displayHeight − visibleBottom − systemInsetBottom`);
   else if the field (`input`/`ftsInput`) has focus AND `Qt.inputMethod.visible`,
   fixed pad `round(root.height * 0.4)`; else 0. Gate the whole block on
   `root.state === 0 || root.state === 4` (Search/FTS tabs only — modal dialogs
   must not move the dock); otherwise pad = 0.
2. Triggers: `Connections` on `input.activeFocusChanged`,
   `ftsInput.activeFocusChanged`, `Qt.inputMethod.visibleChanged`, plus an
   unconditional 250 ms `Timer` calling `_refreshInsets()` (catches show/hide
   that missed every signal), plus a double-`callLater` refresh in `_blurActive()`.
3. `navDock`: `bottomMargin: root._kbdPad`.
4. `_oemReportsIme` latch (set once `imeActuallyVisible()` is ever true) to
   disable the fallback on reporting OEMs — prevents midair lifts on
   Motorola/Xiaomi. (With the Qt 6.10 upgrade the Xiaomi fake state should be
   gone, so re-evaluate whether the latch is still needed.)

## Risks / Trade-offs

- [Risk] On API <= 29 the visible-frame comparison may be unreliable on some
  OEMs (Huawei observed toolbar under keyboard). → Mitigation: measure
  `visible.bottom`/`fullBottom`/`stableBottom` on the target device and adjust
  the formula or fall back to a fixed pad.
- [Risk] Double-application if resize and pad both apply. → Mitigation: pad is
  `max(0, occluded)` and computes to ~0 when resize already shrank the window.
- [Trade-off] Instantaneous flag can lie in the fake state; accepted until the
  IME probe lands.
- [Risk] Platform desync on Xiaomi API 36: the three visibility signals
  (inset state, `mInputShown`, actual IME window paint) transiently disagree
  and can wedge. A single tap triggers a show cancelled at
  `PHASE_WM_POST_LAYOUT_NOTIFY_CONTROLS_CHANGED`, then a system
  `CONTROLS_CHANGED` re-request that takes ~440 ms or fails to paint. The
  keyboard paints on the second tap. Attribution unknown (device desync, not Qt
  timing). Tracker IDs: `PHASE_WM_POST_LAYOUT_NOTIFY_CONTROLS_CHANGED`,
  `PHASE_CLIENT_REPORT_REQUESTED_VISIBLE_TYPES`, `PHASE_CLIENT_ANIMATION_CANCEL`,
  `PHASE_WM_GET_CONTROL_WITH_LEASH`/`STATUS_TIMEOUT`. Next experiment: gated
  re-show ~300 ms after focus gain.