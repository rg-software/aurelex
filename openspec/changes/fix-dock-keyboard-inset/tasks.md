# Tasks

- [x] 1. Fix `getSystemInsetBottom()`: API 30+ `Type.systemBars()`, API 28–29 `getStableInsetBottom()`, still unioned with the cutout inset
- [x] 2. Diagnose the remaining flakiness on Huawei Android 10: capture window height + inset + keyboard state across open/close cycles, find which input lags
- [x] 3. Make the dock settle: `SOFT_INPUT_ADJUST_PAN` on API ≤29 so the window never resizes for the keyboard (no surface death); pad = occluded height with a 150px dead zone (nav bars stay under ~130px even on high-density screens, keyboards take 400px+ — the size test doubles as the cause test, no IME-state signal needed). Poll re-emits every tick so a mid-animation transient corrects within one interval instead of sticking. API 30+ keeps the verified resize path
- [x] 4. Retest: Huawei keyboard open/close shows no app-surface EGL death (adjustPan stops the resize; remaining 0x3000s are Gboard's own process); both phones: tab switches with keyboard open — dock above keyboard, no white slab, no whole-screen blink
- [x] 5. Regression: keyboard closed → dock matches the Play v0.5.1 position exactly (verified pixel-identical on Motorola); Android 15 rows unaffected by construction (adjustPan is API≤29-only; API 30+ path untouched)
- [ ] 6. `openspec validate fix-dock-keyboard-inset`
