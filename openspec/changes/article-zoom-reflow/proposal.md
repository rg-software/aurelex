# Proposal

## Why

Zooming into a dictionary article is broken on narrow Android screens: the WebView scales the whole page (fixed-width article layout), so the zoomed content is wider than the viewport and the user has to pan horizontally to read it. Reflow keeps the text column at the screen width while zooming, so enlarged text re-wraps instead of overflowing. Separately, the zoom level is ephemeral — closing the app forgets the user's chosen reading size, forcing them to re-zoom on every launch.

## What Changes

- **Article zoom reflows instead of horizontally panning.** Zooming an article no longer scales a fixed-width layout past the viewport; text enlarge/fit behavior re-wraps lines to the screen width so there is no horizontal slider. This is presentational only — no engine or dictionary data changes.
- **Zoom is driven from the article header, not native pinch.** The native WebView pinch (which produces the wide page) is disabled via viewport configuration, and the article header gains **Zoom in / Zoom out** controls that scale article text with CSS text reflow. This mirrors the existing Back/Forward/Star header layout and stays fully within Qt/WebView/JS (matches AGENTS.md rule 2/3: no engine or boundary changes).
- **Zoom level persists across app reloads.** The user-chosen zoom is saved to the existing user prefs (`settings.json`) and reapplied automatically when the app restarts and when articles (re)render. It joins the preferences the app already persists (dark mode, etc.).
- **Zoom stays per-device, not per-dictionary:** the saved level applies uniformly to all articles; there is no per-word or per-dictionary memory. (Keeping per-word zoom is out of scope for this change.)

## Capabilities

### New Capabilities

- none — this is behavior of the existing article rendering and preference surfaces.

### Modified Capabilities

- `lookup`: The article rendering requirement gains the zoom/reflow behavior — zoomed articles reflow to the screen width instead of producing a horizontally scrollable page, with zoom controlled from the article header.
- `usability-utilities`: The settings-persistence requirement extends its persisted-preferences list to include the article zoom level (reapplied after app restart).
- `accessibility`: The article header gains new interactive zoom controls, which must carry `Accessible.name`/`Accessible.role` and be documented in the element inventory; the unified inline-surface scenario updates its cited control set.

## Impact

- `app/EngineController.cpp` / `.hpp` — extend the `settings.json` load/save round-trip (`loadSettings`/`saveSettings`, `EngineController.cpp:1583`) with the article zoom level; expose it to QML as a property/invokable and fold it into `rewriteArticleUrls` (`EngineController.cpp:844`) so re-rendered articles apply the saved zoom.
- `app/main.qml` — article header gains the zoom in/out controls (with `Accessible.name`/`role`); the article `WebView` (`main.qml:985`) is configured with a fit-width/reflow viewport (native pinch disabled) and applies the zoom to the live document; user zoom changes are written back through the controller.
- `app/android/assets/` — article chrome CSS/JS additions for the reflow + viewport configuration, mirroring the existing dark-mode injection pattern in `rewriteArticleUrls`.
- `AGENTS.md` — accessible element ID table gains the zoom control entries (and any header-layout note).
- No upstream `engine/` changes; no new `gd_*` boundary surface. Pure UI/presentation + preferences.