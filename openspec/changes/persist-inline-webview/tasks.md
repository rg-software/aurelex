# Tasks

- [x] 1. Park instead of destroy: loader stays active, WebView parks offscreen-left when `state !== 0` or picker open; document persists
- [x] 2. Trim return paths: no re-render on return, no teardown on leave/picker; keep first-creation blank + height-reflow reloads + overlay refreshes
- [x] 3. Keep the keyboard open across Search↔FTS switches: nav tabs never take focus (`Qt.NoFocus`, like the group/clipboard buttons). Verified clean on Huawei (no hide/show in IME tracker); residual flicker on Motorola attributed to SwiftKey (QML focus proven clean there too) — accepted as-is
- [x] 4. Update the stale comments (inline area contract, loader deferral, picker teardown, onStateChanged return)
- [x] 5. Device passes on Huawei Android 10 (empty surface): Dicts→Search, FTS→Search with keyboard open, picker open/close — no black flash; FTS entry always focuses the query field (keyboard opens even from a closed state)
- [ ] 6. Rotation with article open still resets scroll (reflow reload intact); keyboard dock behavior unaffected
- [ ] 7. `openspec validate persist-inline-webview`
