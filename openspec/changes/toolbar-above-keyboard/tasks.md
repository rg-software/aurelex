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
- [ ] 2.1 Measure the gap on Motorola (API 35) and Huawei (API 29); apply a device-tested correction if needed
- [ ] 2.2 Run the device matrix (Motorola API 35, Huawei API 29, Xiaomi API 36): keyboard open/hide, tab switches, rotation; confirm dock visible and tappable above the keyboard
- [x] 2.3 Confirm `openspec validate toolbar-above-keyboard` passes
