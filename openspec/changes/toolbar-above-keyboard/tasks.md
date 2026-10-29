# Tasks

## 1. Re-introduce the dock lift plumbing (from b2dbc06)

- [ ] 1.1 Add `visibleBottom()`, `displayHeight()`, `imeActuallyVisible()` to `AurelexActivity` + `EngineController` (instantaneous, no probe) and verify JNI calls return sane values on device
- [ ] 1.2 Add `_kbdPad` property and lift `navDock` via `bottomMargin: root._kbdPad` in `main.qml`
- [ ] 1.3 Compute `_kbdPad` in `_refreshInsets()` from visible-frame occlusion, gated on `imeActuallyVisible()`; verify no double-application with resize

## 2. Fix the residual gap and validate

- [ ] 2.1 Measure the gap on Motorola (API 35) and Huawei (API 29); apply a device-tested correction if needed
- [ ] 2.2 Run the device matrix (Motorola API 35, Huawei API 29, Xiaomi API 36): keyboard open/hide, tab switches, rotation; confirm dock visible and tappable above the keyboard
- [ ] 2.3 Confirm `openspec validate toolbar-above-keyboard` passes