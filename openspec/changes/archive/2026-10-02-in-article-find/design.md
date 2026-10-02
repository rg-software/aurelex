## Context

See `proposal.md` — Why, and the delta in `specs/lookup/spec.md` for the
required behavior. The constraints below come from the current implementation.

- The article toolbar is QML, not HTML: `inlineArticleToolbar`
  (`app/main.qml:1234`) is a 40 px `Rectangle` holding back / forward /
  favorite / zoom-out / zoom-in `ToolButton`s, right-justified with an empty
  spacer on the left. It is shown only while `root.inlineArticle` is true.
- The article is rendered into a Qt WebView (`root.inlineWv`). Qt WebView wraps
  Android's `android.webkit.WebView` and exposes only `runJavaScript`; there is
  no native `findText`. In-article DOM work is done by injecting script —
  `gdExpandOptPart` (`app/android/assets/scripts/gd-article-controls.js`),
  `gdSetDarkMode` / `gdSetZoom` (`EngineController::rewriteArticleUrls`), and the
  suggestion/history overlay (`main.qml:_applySuggestOverlay`).
- `rewriteArticleUrls` (`app/EngineController.cpp:1857`) strips `mark.min.js` /
  `mark.js` from every article as dead desktop weight, so no highlighter reaches
  the document today.
- The WebView is anchored at `inlineArticleToolbar.height + 6`. `onHeightChanged`
  (`main.qml:1386`) restarts `articleReloader` whenever the WebView's height
  changes while an article is open, and `_loadArticleNow()` replaces the whole
  document — wiping injected DOM state and resetting scroll.
- Each dictionary entry is `<article class="gdarticle">` with a
  `<section class="gdarticlebody">`; DSL hidden content is the `.dsl_opt` class,
  toggled by `gdExpandOptPart`.

## Goals / Non-Goals

**Goals**

- Search the visible text of the open article, highlight matches count them, and
  step through them, without re-rendering the article.
- Reuse the existing toolbar row so the feature costs no extra vertical space
  and does not reflow the article when it opens or closes.
- Keep the document's own behavior intact: in-article links, audio, hidden-content
  toggles, dark mode, and zoom all keep working with marks present.

**Non-Goals**

- Whole-word and case-sensitivity toggles (deferred; the spec only requires
  case-insensitive substring matching).
- Searching collapsed optional content, dictionary resources, or metadata.
- Persisting a find query across article lookups.
- Changing how back/forward navigation works; find mode simply hides those
  controls while it is open.

## Decisions

### D1 — Find bar is QML inside the existing toolbar row

The find bar is a second `RowLayout` inside `inlineArticleToolbar`, shown when a
new `articleFindMode` flag is set, with the nav `RowLayout` hidden. The
container keeps `height: 40` and its id, so `searchArticleLoader.topMargin` and
the landscape floor are untouched — opening or closing find cannot resize the
WebView.

Alternatives considered:

- **HTML find bar injected into the article** (like `#gd-sugg`): keeps
  everything in one process, but requires a text input inside the WebView and
  its own focus/IME handling, and it would collide with the overlay lifecycle.
  Rejected — the QML row already gets native text input and matches "replace the
  toolbar".
- **A second, always-visible strip**: rejected on the proposal's space
  constraint.

The field must be **compact** (no floating label, trimmed vertical padding),
because a default Material `TextField` is ~56 px and would either clip or force
the row taller (which would trigger the reload described in D4).

### D2 — Highlight with a vendored mark.js plus a small find controller

Vendor `mark.js` v9.0.0 (MIT), copied from `engine/src/scripts/mark.min.js`
(same pinned source) into `app/android/assets/scripts/mark.min.js`, and add a
small `article-find.js` controller modelled on `gd-article-controls.js` that
injects the marks and exposes:

- `gdFindSet(query)` — mark all matches, mark the first as current, scroll it
  into view; returns a `"<total>|<index>"` count string.
- `gdFindNext()` / `gdFindPrev()` — move the current mark (wrapping) and scroll
  into view; return the same count string.
- `gdFindClear()` — unmark.

Rationale: the spec requires a match spanning inline markup to count once
(`acrossElements: true`), which is the fiddly part of a hand-rolled `TreeWalker`;
mark.js already solves it and is the same library upstream uses. Options used:
`acrossElements: true`, `caseSensitive: false`, `separateWordSearch: false`,
`iframes: false`, and a `filter` that skips `#gd-sugg` and any `.dsl_opt` that is
currently `display:none` — so collapsed optional content and any stale candidate
overlay are never marked, while revealed optional content becomes searchable
(matching the spec's "until revealed"). mark.js is injected from the
always-on controller block; the engine's own (stripped) `mark.min.js` tag stays
stripped.

Alternatives considered: hand-rolled highlighter — rejected for the
cross-element case and the added test surface.

### D3 — Active match is a class; styling is injected and `!important`

All matches get mark.js's `<mark>`; the current one additionally gets
`data-gd-find-current`. Injected CSS gives `mark` and the current mark distinct
backgrounds/foregrounds with `!important`, so Dark Reader's layered rules cannot
flatten them, and sizes are em-based so `gdSetZoom` reflows them with the text.

### D4 — Height-only resizes must not reload the article (measured: not needed)

**Outcome (measured on device).** ThinkPhone (`ZY22HC8LTR`, 1080x2400), app
0.0.1 Debug. With an article open and the keyboard raised, uiautomator reports
the WebView at `[33,337][1045,2143]` and the root window at `1080x2400`; with the
keyboard dismissed (`mInputShown=false`) the bounds are identical. The IME
overlays the content — it does not resize the app window — so the WebView's
height does not change, `onHeightChanged` is not fired by the IME, and an open
article is not reloaded. **D4 is therefore unnecessary and group 4 is dropped.**
A device that resizes instead of overlaying would reintroduce the hazard; the
manifest pins no `windowSoftInputMode`, so keep the guard below in reserve if
such a device shows up (task 6.2 is where it would surface).

The rejected alternative, for the record: if it did reload, the reload exists to
re-fit reflow after a **width** change
(rotation, which the manifest handles without activity recreation). Change the
trigger to compare the WebView **width** (track `loadedAtWidth` alongside
`loadedAtHeight`) so a height-only change no longer reloads. Rotation changes
both dimensions, so the rotation reflow is preserved. This also makes the
existing "opening the keyboard does not disturb an article" behavior strictly
better.

Fallback if width-keying regresses the native surface: leave the height trigger
alone and instead suppress it while `articleFindMode` is set, restoring scroll
and re-applying the query after the reload.

### D5 — Genuine reloads re-apply the query and match index

Whenever the document is genuinely replaced (`_loadArticleNow`) with find open
and a non-empty query, QML re-calls `gdFindSet(query)` on load-settle and then
advances to the stored index, so rotation/navigation keeps the reader's place.
A fresh lookup (a different word) clears `articleFindMode`, the query, and the
index, per spec.

### D6 — QML owns state, WebView owns DOM

`articleFindMode`, `findQuery`, `findIndex`, and `findTotal` live in QML; the
WebView holds only the injected DOM. Query input is debounced (~150 ms) before a
`gdFindSet` call. Find state resets when `inlineArticle` goes false or the
Search tab is left.

## Risks / Trade-offs

- **A device where the IME resizes the window instead of overlaying it** → the
  measured test device overlays (section 0 of `tasks.md`), so find is safe here,
  but the manifest pins no `windowSoftInputMode`. If task 6.2 fails on such a
  device, apply the reserved width-keyed guard (D4) or suppress the height
  trigger while find is open.
- **mark.js performance on very large combined articles** → debounce, and only
  re-mark on query change, never on scroll. Measure with a large multi-dictionary
  article; if `acrossElements` is too slow, consider disabling it as a
  documented degradation (at the cost of the cross-element scenario).
- **Mark DOM mutation interfering with links/audio/expander** → marks split text
  nodes but leave ancestor elements intact; verify a link whose label is partly
  matched still dispatches, and that `.dsl_opt` filtered text still expands.
- **Dark Reader restyling marks** → `!important` injected styles; verify in dark
  mode on device.
- **Vendored mark.js provenance drift** → record source path/tag/version in a
  comment or small README in `app/android/assets/scripts/`, mirroring the
  openssl provenance practice.

## Migration Plan

Additive feature; no data or index migration. Ships in a normal release. Rollback
is reverting the change (no persisted state depends on it).

## Open Questions

- Exact highlight colors/contrast for both themes — settle during
  implementation against the app palette.
- Whether `acrossElements` is fast enough on the largest catalog dictionaries —
  measure during implementation, degrade if needed.
