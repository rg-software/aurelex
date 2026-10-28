# Tasks

- [x] 1. Park instead of destroy: loader stays active, WebView parks offscreen-left when `state !== 0` or picker open; document persists
- [x] 2. Trim return paths: no re-render on return, no teardown on leave/picker; keep first-creation blank + height-reflow reloads + overlay refreshes
- [x] 3. Keep the keyboard open across Search↔FTS switches (synchronous focus transfer both ways) so the window never resizes mid-trip — verified: focus moves exactly once per tap, never flaps
- [x] 4. Update the stale comments (inline area contract, loader deferral, picker teardown, onStateChanged return)
- [ ] 5. Device passes on Huawei Android 10: Dicts→Search, FTS→Search with keyboard open, picker open/close, with and without article — no black box
- [ ] 6. Rotation with article open still resets scroll (reflow reload intact); keyboard dock behavior unaffected
- [ ] 7. `openspec validate persist-inline-webview`
