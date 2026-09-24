# Design — Article zoom reflow + persistence

## Context

The inline article is a Qt `WebView` (QtWebView on the native Android WebView) at
`app/main.qml:985`. Article HTML is produced by the engine and rewritten in
`EngineController::rewriteArticleUrls` (`app/EngineController.cpp:844`) before any
render: desktop-only scripts are stripped and a plain-background style plus the
dark-mode controller script are injected into `<head>` — the natural injection
point for a viewport meta and the reflow/zoom CSS+JS. User prefs live in
`settings.json` (`loadSettings`/`saveSettings`, `app/EngineController.cpp:1583/1605`,
currently `userDarkOverride` + `onboarded`). See the proposal for the "why".

## Goals / Non-Goals

**Goals**
- Make article zoom a true text reflow: enlarging text re-wraps to the screen
  width; no horizontal slider at any zoom.
- Expose zoom from the article header (Zoom in / Zoom out), replacing
  native pinch as the zoom input.
- Persist the zoom level across app restarts and reapply it to every rendered article.
- Stay entirely in Qt/QML/WebView/JS — no engine edits (AGENTS.md rule 1) and no new
  `gd_*` boundary surface (AGENTS.md rule 3).

**Non-Goals**
- Per-word or per-dictionary zoom memory (zoom is one global value).
- Keeping native pinch zoom (it is the mechanism that causes the wide page).
- Reflowing non-text content that is inherently fixed-width (huge tables, raw
  images) — those are clamped to the viewport width; see Risks.
- Restricting the Android layout algorithm or driving it via JNI.

## Decisions

### D1: Reflow zoom = CSS font-size scaling, not page scaling
A native pinch on Android's WebView does *visual* page scaling: the fixed-width
article scales up in a larger layout viewport, so the content overflows the screen
width and pans horizontally. Modern Android WebView removed true "single-column"
text reflow, and QtWebView exposes no reflow setting. The reliable equivalent is a
**text-zoom**: change the base `font-size` of the article (`html { font-size: N% }`),
which re-lays out the text at the fixed device-width viewport — lines re-wrap,
no horizontal slider. Zoom in/out therefore map to percentage steps applied
as root font-size.

**Alternatives considered:**
- *Android `WebSettings.textZoom`/`setLayoutAlgorithm` via JNI* — QtWebView's
  internal Android WebView isn't reachable through a stable public surface;
  the codebase only uses JNI for app-shell bridges (playAudio, insets, clipboard).
  Rejected as fragile and non-portable.
- *QML `PinchArea` over the WebView* — the native WebView surface swallows touches;
  QML cannot stack interactive controls above it (same constraint the suggestion
  dropdown works around, see AGENTS.md). Rejected.
- *Keep pinch, clamp overflow* — masks the symptom; content still scales past the
  viewport and wide tables/images clip. Rejected.

### D2: Disable native pinch via an injected viewport meta
Inject `<meta name="viewport" content="width=device-width, initial-scale=1.0,
maximum-scale=1.0, user-scalable=no">` into the article `<head>`. This pins the
layout viewport to the device width and turns off native pinch page-scaling, which
is the precondition for there being no horizontal slider. If the engine HTML already
contains a viewport meta (some dictionary templates do), replace it rather than
duplicating it (use the same remove-then-insert technique as `stripScripts`).

### D3: Reuse the `rewriteArticleUrls` injection pipeline
The reflow CSS and a `gdSetZoom(percent)` controller script are injected beside the
existing plain-CSS and dark-mode blocks (same head-insert point,
`EngineController.cpp:981`), parametrized by the currently-saved zoom so every
freshly-rendered article starts at it. Live changes (button taps) call
`window.gdSetZoom(...)` via `runJavaScript` on the open document — no reload, same
pattern as `gdSetDarkMode` — and the injected CSS consumes the value as a root
font-size and clamps wide content:
- `html { font-size: <N>%; }`
- `html, body { max-width: 100%; overflow-x: hidden !important; }` — the hard pin
  that makes horizontal panning impossible. WebView scrolls horizontally the moment
  the document is even a pixel wider than the viewport (subpixel layout, elastic
  overscroll), which lets a swipe hide the leftmost text off the left border. With
  `overflow-x: hidden`, `scrollX` stays 0 and only the *right* edge can ever clip.
- `.gdarticlebody, .gdarticle, .gdarticles { max-width: 100%; overflow-wrap: break-word; }`
- `img, table { max-width: 100% !important; height: auto; }`
- `.gdarticlebody pre, code { white-space: pre-wrap; }` and `a { overflow-wrap: break-word; }` —
  wrap the common fixed-width/long-link cases instead of clipping them.

This keeps the whole feature inline in `rewriteArticleUrls` (no new assets required),
mirroring how `plainCss` + the dark controller already live.

### D4: Engine owns the value; QML drives it
Follow the existing `userDarkOverride` pattern: `EngineController` owns the zoom
value (member + `Q_PROPERTY` + notify), clamps it (default 100%, range e.g. 75–250%,
step 25%), persists it in `settings.json`, and bakes it into `rewriteArticleUrls`.
QML header buttons call `engine.setArticleZoom(...)`; the `articleZoomChanged`
handler applies the new value to the live document with `runJavaScript`. Solo Qt-side
round-trip keeps the persistence contract with `usability-utilities` where the other
prefs already live.

### D5: Controls live in the article header, annotated for accessibility
Zoom in / Zoom out sit beside Back/Forward/Star, each with
`Accessible.name` ("Zoom in", "Zoom out") and `Accessible.role`
(`Accessible.Button`), disabled at the range bounds. A "reset" is not needed as a
dedicated control since the default 100% is reachable by stepping (100 is on the
75–250 step lattice); `engine.setArticleZoom(100.0)` remains available as an API
and as the persisted default. These become part of the stable accessible element
inventory (AGENTS.md table) for the `accessibility` capability.

## Risks / Trade-offs

- **[Dict HTML with absolute-px typography won't scale with root font-size]** →
  Such entries keep their base size at high zoom (graceful, no reflow violation —
  the viewport is clamped so there is still no horizontal slider). Verified against
  the v1 format set ([.mdx/.mdd](mdict), DSL, StarDict) during the implement task.
- **[Inherently fixed-layout content (very wide tables/`<pre>` blocks) can still
  overflow at any zoom]** →
  `overflow-wrap` + `img, table { max-width: 100% }` mitigate the common cases;
  residual extreme tables clip at the right edge (never pan to the left) because
  `overflow-x: hidden` pins the horizontal scroll position at 0.
  Documented behavior, not a regression — today they overflow at zoom too, and the
  page is no longer zoomable past the device width.
- **[Duplicate/absent viewport meta in engine HTML]** →
  Replaces any existing viewport meta (regex, like `stripScripts`); confirms the
  injected one wins.
- **[`runJavaScript` on a not-yet-loaded WebView silently no-ops]** →
  Reuse the existing load-settle guards (`_ensureInlineBlank`, `onLoadingChanged`
  flush) so zoom is applied only once a document is live; freshly-rendered articles
  get the zoom baked in by D3 anyway.
- **[Zoom change reflows layout and may shift scroll position]** →
  Best-effort keep-scroll (apply in place on the current document); the per-pane
  article reloader (`articleReloader`) already exists for the height-change case and
  is reused if the WebView must re-render. Not spec'd as exact scroll anchoring.
- **[Every button tap writes `settings.json`]** →
  Cheap and consistent with the existing `setUserDarkOverride` save-on-change;
  debounce not required.

## Migration Plan

No data migration: the new `articleZoom` key defaults to 100% when absent
(`loadSettings`), so existing installs are unaffected on upgrade. Rollback of the
feature is a pure UI/C++ revert: removing the key + controls falls back to the
current behavior (page at device-width, header without zoom buttons). No engine or
boundary changes to revert. Verify with the CI smoke path (unchanged) plus an
on-device/emulator check that a DSL and an mdict article reflow at 150% and 200%
zoom with no horizontal scrolling.

## Open Questions

None that change the specs, approach, or task breakdown.