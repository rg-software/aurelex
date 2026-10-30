# Tasks

## 1. Park the inline WebView instead of destroying it

- [x] 1.1 Make `searchArticleLoader` stay active while the group picker is open (park, not destroy) and verify the WebView instance survives open/close in the Android view hierarchy
- [x] 1.2 Park the WebView offscreen (clipped by the window) on Search-tab leave instead of tearing it down, and verify no native-surface reallocation (no black blink) in a screen recording
- [x] 1.3 On return to the Search tab with an article showing, reuse the persisted document without re-rendering; verify scroll position is preserved
- [x] 1.4 When no article is showing on return, refocus the search field and re-query suggestions; verify suggestions appear

## 2. Validation on target devices

- [ ] 2.1 Device matrix: Motorola API 35 DONE for launch, lookup, tab round trip (article survives, no re-render flash; launch black flashes fixed + frame-verified — splash overlay, WebView canvas paint). Group-picker round trip with article still to verify on device. Huawei API 29 fully pending.
- [x] 2.2 Confirm `openspec validate webview-smooth-navigation` passes