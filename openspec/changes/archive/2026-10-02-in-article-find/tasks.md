## 0. Spike - confirm the IME reload path (done)

- [x] 0.1 Measured on device (ThinkPhone, app 0.0.1 Debug): raising the IME does not resize the app window. The WebView bounds are `[33,337][1045,2143]` with the keyboard up (`mInputShown=true`) and down (`mInputShown=false`), and the root window stays `1080x2400`. The IME overlays the content rather than resizing it
- [x] 0.2 The marker was not needed: the geometry measurement was unambiguous
- [x] 0.3 Outcome recorded in the D4 section of `design.md`
- [x] 0.4 Outcome applied: the IME does not change the WebView height, so `onHeightChanged` does not fire from it and D4 is unnecessary. Group 4 is dropped

## 1. Highlight controller (article side)

- [x] 1.1 Vendor mark.js v9.0.0 from `engine/src/scripts/mark.min.js` into `app/android/assets/scripts/mark.min.js`; record its provenance (source path, version, license) in a comment or a short README next to it
- [x] 1.2 Add `app/android/assets/scripts/article-find.js` exposing `window.gdFindSet(query)`, `gdFindNext()`, `gdFindPrev()`, and `gdFindClear()`, built on `Mark` with `acrossElements: true`, `caseSensitive: false`, `separateWordSearch: false`, and collapsed optional/overlay content filtered out
- [x] 1.3 Make `gdFindSet` / `gdFindNext` / `gdFindPrev` return `"<total>|<index>"`; wrap next/prev at both ends; mark the current match with `data-gd-find-current` and scroll it into view
- [x] 1.4 Inject `mark.min.js` then `article-find.js` from the always-on controller block in `EngineController::rewriteArticleUrls` (keep the engine's own `mark.min.js` tag in the strip-list)
- [x] 1.5 Add injected CSS for `mark` and `mark[data-gd-find-current]` with distinct, theme-aware colors using `!important` and em-based sizing so Dark Reader and `gdSetZoom` do not defeat them

## 2. Find mode in the article toolbar (QML)

- [x] 2.1 Add find state to the root: `articleFindMode`, `findQuery`, `findIndex`, `findTotal`, plus reset rules (article closed / Search tab left / fresh lookup)
- [x] 2.2 Add the leftmost magnifier control to the nav `RowLayout` that sets `articleFindMode`
- [x] 2.3 Add a find `RowLayout` inside `inlineArticleToolbar` (shown when `articleFindMode`) with a compact, no-floating-label query field, the `n / total` counter, previous/next buttons, and the magnifier turned into an X that closes find; keep the container id and `height: 40`
- [x] 2.4 Debounce query input (~150 ms) before searching; treat the field's submit as next match

## 3. QML <-> WebView wiring and lifecycle

- [x] 3.1 Call `runJavaScript` for set/next/prev/clear and parse the returned count string into `findIndex` / `findTotal`
- [x] 3.2 Clear highlights and find state when a new article loads, the article is dismissed, or the tab changes
- [x] 3.3 On a genuine reload while find is open with a query (e.g. rotation), re-apply the query on load-settle and restore the stored `findIndex`

## 4. (Dropped) Stop height-only reloads

Dropped after the spike in section 0: the IME overlays rather than resizes the app
window on the test device, so the height-triggered reload is not reachable from
find and no change to the reload path is needed. Cross-device caveat: the
manifest pins no `windowSoftInputMode`; if a device that resizes the window
surfaces, revisit with the width-keyed guard described in design D4.

## 5. Accessibility, localization, docs

- [x] 5.1 Give every new control an `Accessible.name` and `Accessible.role` (find toggle/close, find field, previous match, next match, counter if interactive)
- [x] 5.2 Wrap new user-visible strings in `qsTr`, run `scripts/update-translations.ps1`, translate the new entries in `app/i18n/*.ts`, recommit the compiled `.qm`, and mirror any `strings.xml` changes into `values-ru/` + `values-ja/`
- [x] 5.3 Record the new accessible element IDs in the `AGENTS.md` table

## 6. Verification on device

- [x] 6.1 Open a multi-dictionary article, enter a query, and confirm every visible match highlights, the counter reads `n / total`, and next/previous move and wrap
- [x] 6.2 Confirm opening find and typing does not reset the article's scroll position (the IME path)
- [x] 6.3 Rotate with find open and confirm the query and current match are restored
- [x] 6.4 Confirm highlights are legible in light and dark mode with Dark Reader active
- [x] 6.5 Confirm in-article links, audio controls, and the optional-parts expander still work with marks present
- [x] 6.6 Confirm a query that occurs only inside a collapsed `[*]…[/opt]` zone is not matched or counted
- [x] 6.7 Check find responsiveness on the largest available dictionary/article and degrade `acrossElements` only if measured unusably slow
