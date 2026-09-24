# Tasks

## 1. Controller: zoom property + persistence

- [x] 1.1 Add `qreal m_articleZoom` (default 100.0) + `Q_PROPERTY(qreal articleZoom READ articleZoom NOTIFY articleZoomChanged)` and a bound-clamped `setArticleZoom(qreal)` in `EngineController.hpp`; verify it builds (host `cmake --build app`)
- [x] 1.2 Persist the key: read `articleZoom` in `loadSettings` (fallback 100.0 when absent) and write it in `saveSettings` alongside `userDarkOverride`/`onboarded`; verify `settings.json` round-trips by setting the value, restarting, and reading it back with the app's own loader
- [x] 1.3 Clamp and step: enforce min/max (75–250%) and 25% step on the setter, no-oping out-of-range writes; verify out-of-range values are clamped at the boundary and `articleZoomChanged` fires only on a real change

## 2. Injection: viewport, reflow CSS, zoom controller

- [x] 2.1 In `rewriteArticleUrls`, strip any existing `<meta name="viewport">` from the engine HTML (regex like `stripScripts`) so the injected meta wins; verify a test article with its own viewport meta ends up with only ours
- [x] 2.2 Inject `<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">` with the other head insertions; verify it disables native pinch on-device (no page scale on two-finger drag)
- [x] 2.3 Inject the reflow CSS + a `window.gdSetZoom(percent)` controller script (html font-size var, `.gdarticlebody` overflow-wrap, `img, table { max-width: 100% }`), parametrized by the current `m_articleZoom`; verify rendered article HTML contains the meta, the CSS, the default font-size, and the script
- [x] 2.4 Confirm the baked default: a freshly looked-up word (after setting + saving a zoom) renders at the saved level without any JS call; verify on-device by reloading the article at 150%

## 3. QML: header zoom controls + live apply

- [x] 3.1 Add Zoom in / Zoom out controls to the article header beside Back/Forward/Star, each icon-only with `Accessible.name` ("Zoom in" / "Zoom out") and `Accessible.role: Accessible.Button`, disabled at the range bounds; verify they render and are reachable in the on-device accessibility tree (content-desc)
- [x] 3.2 Wire the buttons to `engine.setArticleZoom(...)` computed from the current value (step 25%); verify no live change leaks through before a document is loaded (reuse `_ensureInlineBlank`/load-settle guards)
- [x] 3.3 On `articleZoomChanged`, apply the new value to the live open document via `runJavaScript("gdSetZoom(...)")` (mirror the `gdSetDarkMode` flow), and for the inline-surface reload path reuse `articleReloader` so a re-render still honors the zoom; verify the open article reflows instantly on tap with no reload flash and no horizontal slider at 200%
- [x] 3.4 If any control carries a visible (non-icon) label, rerun `scripts/update-translations.ps1`, translate new entries in `app/i18n/*.ts`, mirror in `values-*`, and recommit the `.qm` files per the localization convention; if controls stay icon-only, confirm with the fix-strings task below that no catalog churn is needed

## 4. Accessibility + docs inventory

- [x] 4.1 Update the AGENTS.md accessible-element table (Article pane rows) with the Zoom in / Zoom out entries and their `Accessible.name` values; verify the table matches the landed `main.qml` annotations
- [x] 4.2 Grep-verify no `qsTr` was introduced inside any `Accessible.name` (invariant English test IDs preserved); also grep the diff for engine/ and carve/ paths — must be zero (golden rules)

## 5. End-to-end verification

- [x] 5.1 On device/emulator with one mdict and one DSL dictionary: zoom from 75 to 250; verify each level re-wraps lines to the screen width with no horizontal scrolling, images stay within width, and Back/Forward/Star still work alongside the new controls
- [x] 5.2 Restart the app after setting a non-default zoom and re-open an article; verify it renders at the saved level (persistence survives app reload) and that the control state shows the correct position
- [x] 5.3 Run the CI smoke path (engine build + smoke tool) unchanged and confirm this pure UI/presentation change introduces no failures; report the `git status` shows only app-side artifacts