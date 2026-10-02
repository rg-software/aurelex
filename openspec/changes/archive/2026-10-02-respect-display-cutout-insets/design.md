## Context

See `proposal.md` — Why for the symptom. What the code already has, and the
constraints that shape the approach:

- **Inset plumbing exists, but only for two edges.** `AurelexActivity`
  (`app/android/src/.../AurelexActivity.java`) exposes two static methods,
  `getSystemInsetTop()` / `getSystemInsetBottom()`, which read
  `getRootWindowInsets().getSystemWindowInset{Top,Bottom}()` with a resource
  fallback. `EngineController` forwards them as `Q_INVOKABLE int systemInsetTop()`
  / `systemInsetBottom()`, and `app/main.qml`'s `_refreshInsets()` divides them by
  the device pixel ratio into `_insetTop` / `_insetBottom`. It is called on
  `onWidthChanged`, `onHeightChanged` and `Component.onCompleted` — i.e. already
  the single place where insets are re-read.
  Consumers: `topBar.height = root._insetTop` and
  `navDock.height = 56 + root._insetBottom`. Nothing else reads them, and no
  horizontal inset exists anywhere.
- **The window is edge-to-edge and cannot opt out.** `dumpsys window` for
  `AurelexActivity` reports `layoutInDisplayCutoutMode=always` and
  `EDGE_TO_EDGE_ENFORCED`; the build targets SDK 36 (`app/build.ps1`,
  `qtTargetSdkVersion=36`), and Android 15 enforces edge-to-edge for that range.
- **What the platform reports, measured** (ThinkPhone, Android 15, 1080×2400,
  density 2.5):

  | | portrait | landscape |
  |---|---|---|
  | `statusBars` frame | `[0,0][1080,110]` | `[0,0][2400,67]` |
  | `displayCutout` frame | `[0,0][1080,110]` | `[0,0][110,1080]` (sideHint `LEFT`) |
  | cutout bounding rect | centred, top | `Rect(0,510 - 110,570)` |

  The portrait case works today because the status-bar inset already *equals* the
  cutout height, so `topBar` covers the camera exactly. Nothing covers the
  landscape case because no horizontal inset is read.
- **`minSdk` is 23** (`qtMinSdkVersion=23`), so `DisplayCutout` and
  `WindowInsets.getDisplayCutout()` (both API 28) need a version guard. Below 28
  there is no cutout to avoid, so the correct answer there is 0, not a guess.
- **The layout is regular where it matters.** Five top-level panes — `searchPane`,
  `dictsPane`, `groupsPane`, `favoritesPane`, `ftsPane` — share one identical
  anchor line, `anchors { top: topBar.bottom; left: parent.left; right:
  parent.right; bottom: navDock.top }`. Everything pane-shaped below them (the
  remote-catalog pane, the group membership editor, the onboarding overlay) is a
  child with `anchors.fill: parent`, so it inherits whatever its pane gets. The
  dock's interactive cells live in a `Row` (`navRow`) inside `navDock`.
- **`ApplicationWindow` sets no `color`.** Anything the panes do not cover paints
  the window's clear colour, so simply insetting a pane would expose a black band
  exactly where the camera is.

## Goals / Non-Goals

**Goals:**
- No article text, search field, tab or button under a system bar or a camera
  cutout, in any orientation or window size.
- The window keeps filling the display, so no black band appears at any edge.
- One re-read point, on the same hook that already exists.
- No new dependency, and no behaviour change on devices without a cutout.

**Non-Goals:**
- Drawing *less* than edge-to-edge. Letterboxing is not a supported mode here.
- Per-edge asymmetry tricks (e.g. "camera goes left in landscape, so flip the
  layout"). The platform already reports which edge is occupied; honour it.
- Cutout avoidance for the splash screen or the launcher icon — separate surfaces
  with their own theming.
- Dialogs: they are centred and width-bounded, so a 110 px side inset cannot
  push one off-screen on any supported window size.

## Decisions

**D1 — Union per edge (the larger of the two insets), never a sum.**
The cutout inset is unioned with the system-bar inset on each edge, per edge
independently: `inset = max(systemBar, cutoutSafeInset)`.

- *Why not sum:* measured, the portrait `statusBars` frame `[0,0][1080,110]` and
  the `displayCutout` frame `[0,0][1080,110]` are the **same rectangle** — the
  platform has already folded the cutout into the status bar there. Summing would
  double-count and push the app's content 110 px below where it belongs, which
  looks like an unexplained gap under the status strip in portrait.
- *Why `max` rather than trusting the platform to fold everything:* the folding is
  an Android 15 behaviour for the top edge. On other versions and other shapes the
  two are independent, and a camera taller than the status bar must still be
  cleared. `max` is correct in every case and is a no-op where the platform
  already folded.

**D2 — Two new invokables, not a "safe insets" object.**
`EngineController::systemInsetLeft()` / `systemInsetRight()` mirror the existing
pair rather than introducing a struct or a single combined value.

- *Why separate values and not one "horizontal inset":* the camera is on **one**
  side — landscape here reports `left = 110`, `right = 0` — so a single symmetric
  value would inset the wrong side and waste 110 px on the far edge.
- *Why no struct:* JNI marshalling for `int` is already in place and tested by
  two working methods; a struct means new glue on both sides for no gain, and QML
  would still destructure it into plain numbers.

**D3 — Read the cutout from the decor view's root insets, guarded by API level.**
`getDisplayCutout()` on the same `RootWindowInsets` the existing methods already
fetch, behind `Build.VERSION.SDK_INT >= 28`, returning 0 below.

- *Why there and not `getWindowVisibleDisplayFrame` or a manual query:* it is the
  same object the existing two methods read, so it cannot disagree with them
  about which window is being measured.
- *Why 0 below API 28:* there is no cutout API there at all, so 0 is the truth,
  not a conservative fallback.
- *Keep `getSystemWindowInsetTop()` as it is* despite the deprecation: it is what
  works across the whole `minSdk` range and is already covered by the existing
  behaviour. Deprecating it is a separate cleanup.

**D4 — Set the window's background to the app background, then inset the panes.**
`ApplicationWindow.color: root.uiBg`, and the five panes gain
`leftMargin: root._insetLeft; rightMargin: root._insetRight` on their shared
anchor line.

- *Why the window background first:* it is what makes the requirement "the area
  that was inset is filled with the app's background" true by construction. Every
  other element (the top strip, the nav strip) already paints `root.uiBg`, so the
  window joins them and the inset strip cannot differ from its neighbours in
  either theme. It also fixes any other uncovered strip for free.
- *Alternative — keep the panes full-bleed and inset each pane's children.* Rejected:
  it is five panes times several children each, the set changes whenever a row is
  added, and the inline article `WebView` would need its own margin — the kind of
  omission that only shows up on a device with a cutout. One edit point on the
  shared anchor line is the whole change.
- *Why `anchors` margins rather than wrapping panes in a safe-area container:* a
  container would have to sit between the panes and their `topBar`/`navDock`
  anchors, i.e. restructure the window's top-level item tree, for the same result
  two extra properties achieve.

**D5 — Inset the dock's cells, not the dock.**
`navDock` keeps its full-bleed `color: root.uiBg` and its
`56 + _insetBottom` height; `navRow` inside it takes the side margins.

- *Why:* the outermost tab cell is interactive, so it has to move clear of the
  camera. But the dock is also the strip that visually terminates the screen; if
  the dock itself were inset, the app background would show below it and the
  bottom edge would stop looking anchored. Splitting "background stays full-bleed,
  controls move" is what both requirements need.

**D6 — Re-read through the existing `_refreshInsets()` hook; add no observer.**
The platform re-reports `displayCutout` on the edge that is now occupied whenever
the window is laid out again, and `_refreshInsets()` already runs on every
`width`/`height` change. So an orientation change, a cold start in landscape, a
multi-window resize and the IME all flow through the same path with no new code.

- *Explicitly not* reintroducing a geometry-change handler (the shape of the
  `_geometryInvalid` machinery deleted in `fix-article-surface-covers-dock`):
  nothing is destroyed or re-created here, so there is nothing to sequence. The
  inset is a number, read fresh.

**D7 — Keep the pixel-ratio conversion.**
Cutout safe insets arrive in the same physical pixels as the system-window insets,
so `_refreshInsets()` divides by `_insetDpr` for all four values exactly as it
does today for two.

## Risks / Trade-offs

- **[A side cutout costs ~110 px of usable width in landscape]** → Accepted: it is
  110 px of a 2400 px screen. The article reflows to the narrower measure (the
  `WebView` resizes; no re-render is needed, and none is triggered — width changes
  deliberately do not restart the reflow path).
- **[A future pane added without the margins regresses silently]** → The five
  panes share one identical anchor line, so the reviewable edit point is a single
  line pattern; `tasks.md` adds a grep check that every
  `top: topBar.bottom` pane carries both margins.
- **[`ApplicationWindow.color` also fills behind dialogs, popups and during the
  first frame]** → That is the app background in both themes, which is what those
  surfaces already assume; the Android starting window keeps its own themed
  `windowBackground`, so the launch look is unchanged.
- **[A device with a cutout on both sides (waterfall / corner cutouts) narrows the
  layout twice]** → Correct behaviour: both margins apply. Worth one manual look
  on a waterfall device if one is ever available.
- **[Multi-window / freeform resize]** → Insets shrink with the window, and
  `_refreshInsets()` already runs on the resize, so the margins follow. No extra
  handling; a `docs/TESTING.md` row covers it.
- **[Only one device and one rotation direction were available for
  measurement]** → The landscape-right case is the same code path with the values
  swapped, but `tasks.md` still tests it by rotating the other way
  (`user_rotation 3`), because "we only ever checked left" is exactly the kind of
  assumption that survives review.

## Migration Plan

None. No persisted state, no stored setting, no protocol. Rollback is deleting the
margins and the two accessors; portrait behaviour is identical either way.

## Open Questions

None. The API-level behaviour below 28, the union-vs-sum question, and the
right-edge rotation case are all resolved above or scheduled as tasks.
