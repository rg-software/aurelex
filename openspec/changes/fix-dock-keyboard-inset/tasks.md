# Tasks

- [x] 1. Fix `getSystemInsetBottom()`: API 30+ `Type.systemBars()`, API 28–29 `getStableInsetBottom()`, still unioned with the cutout inset
- [x] 2. Diagnose the remaining flakiness on Huawei Android 10: capture window height + inset + keyboard state across open/close cycles, find which input lags
- [x] 3. Make the dock settle: `SOFT_INPUT_ADJUST_PAN` on API ≤29 so the window never resizes for the keyboard (no surface death); the visible-frame pad is the single lift mechanism. API 30+ keeps the verified resize path
- [ ] 4. Retest on Huawei Android 10: keyboard open/close shows no EGL death in logcat; all tab switches with keyboard open — dock above keyboard, no white slab, no whole-screen blink
- [ ] 5. Regression: keyboard closed → dock at the bottom as before; Android 15 rows unaffected
- [ ] 6. `openspec validate fix-dock-keyboard-inset`
