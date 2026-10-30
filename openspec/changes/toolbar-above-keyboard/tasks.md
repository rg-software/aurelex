# Tasks

## 1. Re-introduce the dock lift plumbing (from b2dbc06)

> NOTE (2026-10-29): 1.1–1.3 were implemented and verified on Huawei (nav row
> lifted y=2055→y=1149), then reverted in commit 6e764c1 to keep the tree clean
> for the Qt 6.10 upgrade (the Xiaomi fake state is QTBUG-140897, fixed
> upstream — no workaround should ship for it). Re-apply on top of the upgraded
> kit. The verified recipe is in design.md ("Huawei fallback (verified)").

- [x] 1.1 Add `visibleBottom()`, `displayHeight()`, `imeActuallyVisible()` to `AurelexActivity` + `EngineController` (instantaneous, no probe) and verify JNI calls return sane values on device
- [x] 1.2 Add `_kbdPad` property and lift `navDock` via `bottomMargin: root._kbdPad` in `main.qml`
- [x] 1.3 Compute `_kbdPad` in `_refreshInsets()` from visible-frame occlusion, gated on `imeActuallyVisible()`; verify no double-application with resize

## 2. Huawei fallback + validation

- [x] 2.0 Re-apply the Huawei fallback per design.md ("Huawei fallback (verified)"): focus-based 40% pad, `onQueryTab` gating, focus-change + `Qt.inputMethod.visible` triggers, unconditional 250 ms poll; verify nav row lifts on Huawei again
- [x] 2.1 Motorola half DONE 2026-10-30: dock flush above Gboard in all kb-up states (screenshots); the earlier gap report was pre-lift-code state — withdrawn, no correction needed. Huawei half still open (needs dock-gap measurement on device).
- Historical (Xiaomi API 36, verified 2026-10-29/30, blur+refocus era): dock flush above Gboard, single tap, clean `onShown` (screenshot). Return-to-Search verified: focused + keyboard + lifted dock. Query-tab transfer verified: Search->FTS kept keyboard up; entry timer stood down when transfer worked. NOTE: show-only reshow + API gate landed after — Xiaomi needs a re-check.
- [ ] 2.2 Device matrix: Motorola API 35 DONE (`bc80b9a`, `1a2df4c`, follow-ups through `e408351` — taps, transfers, re-tap no-op, rotation, FTS flows, launch flashes; see TESTING.md). Huawei API 29 + Xiaomi API 36 still pending (Xiaomi: show-only reshow re-check; Huawei: full matrix).
- [x] 2.3 Confirm `openspec validate toolbar-above-keyboard` passes
