## Context

See `proposal.md` — Why for the symptom. The shape of the problem, and how it was
actually pinned down:

- The Search pane is a `ColumnLayout`: a search row on top, then
  `searchArticleArea` (`Layout.fillHeight`) as the last item. The search row has
  its own fixed content and does not shrink below what it needs.
- `searchArticleArea` is the **last** item, so when the column's children together
  want more height than the pane has, the surplus is pushed out of the **bottom**
  edge — i.e. straight over the bottom dock, which is anchored below the pane. A
  `ColumnLayout` does not clip, and the item is not asked to.
- Inside `searchArticleArea` sits `searchArticleLoader` (a `WebView`), which on
  Android is a **platform view**: a real child of the activity's view hierarchy,
  composited above the Qt scene. A native view ignores QML `z` and `clip`, so
  once the parent item has been pushed over the dock, the native surface paints
  over it as well. That is why the symptom was a *missing dock* rather than a
  *squashed pane*: both the item and its native child were over it.
- Only the Search tab has this surface, which is why only the Search tab lost the
  dock. The Dictionaries/Groups/Full-text/Favorites panes have no such floor.

### How it was measured

Images could not be inspected directly in this environment, so three proxies were
used together:

1. **Accent-pixel count.** The dock's active-tab cell is magenta
   (`Material.primary`). Screenshotting with `adb` and counting pixels close to
   the accent colour inside the dock's y-band answers one question directly: *is
   the dock band painting the accent, or is it the article instead?* Reference
   values: portrait with dock visible **470**; landscape with the bug **15**;
   landscape after the fix **594**. Anything under ~50 means the dock is not
   painting.
2. **`uiautomator dump` bounds.** Gives the dock's real on-screen rect
   (`Main navigation [0,856][1998,1011]`) and therefore its top edge in device px,
   to compare against the article surface's bounds
   (`[33,449][2365,822]` after the fix) — the comparison that actually proves
   "no overlap".
3. **A tap-through.** Tapping a dock tab in landscape navigates. That proves the
   dock is not merely painted but still hit-testable on top of the native surface.

QML's own geometry was read live on device during the diagnosis (temporary
instrumentation, since removed) and produced the numbers below.

| Landscape, logical px | Bug (`minimumHeight: 300`) | Fixed (`: 88`) |
|---|---|---|
| window | 387 tall | 387 tall |
| top bar | 39 | 39 |
| dock `y` / `h` | 307 / 80 | 307 / 80 |
| Search pane height | 268 | 268 |
| article area `y` / `h` | 64 / **300** | 64 / **180** |
| article toolbar `h` | 40 | 40 |
| `searchArticleLoader` `h` | 254 | 134 |
| article area **bottom** | **364** | **244** |
| dock **top** | **307** | **307** |
| overlap | **57 px** | none |

## Goals / Non-Goals

**Goals:**
- The dock is visible and tappable on the Search tab in every orientation, reached
  by rotation *or* by launching into landscape.
- The article that was open is still open afterwards.
- The IME path is untouched: opening the keyboard must not disturb the article or
  its suggestions.
- No engine, carve, or boundary involvement.

**Non-Goals:**
- Redesigning the landscape layout. A landscape side-rail dock was considered and
  rejected — it is a different change, and the report is that chrome is *missing*,
  not that the layout is wrong for the aspect ratio.
- Any runtime detection or reconciliation of the surface's geometry (see Ruled
  out).
- Preserving or restoring scroll position. **Not fixed here, and not made worse**:
  a rotation still returns the open article to the top, because the pre-existing
  responsive reflow (`articleReloader` re-renders whenever the WebView's height
  changes) does that on its own. Measured — see Risks.

## Decisions

**D1 — Lower the layout floor; do not make it responsive.**
`searchArticleArea`'s `Layout.minimumHeight` goes from `300` to `88`.

- *Why 88 and not 0:* the floor's job is to keep the item from being squeezed
  below the point where its own children behave — the 40 px article toolbar plus
  the 6 px top margin must not invert the loader's `anchors.top` against
  `anchors.bottom`. 88 leaves ~42 px of article below the toolbar, which is a
  real (if tight) band, and still fits a landscape phone with room to spare.
- *Why not derive it from the window:* a binding like
  `Math.max(88, pane.height - searchRow.height)` re-introduces exactly the
  ordering hazard the floor causes (a value that changes while the layout is
  resolving). A constant cannot oscillate, and the landscape phone is the tightest
  case that matters; a constant that fits it fits every larger screen.
- *Guard:* the comment at the declaration records the measured numbers and says
  not to raise it without re-measuring, because the failure mode (a silently
  missing dock) is invisible in a screenshot review and only shows up on hardware.

**D2 — Delete the orientation teardown rather than repair it.**
`_geometryInvalid`, `_lastGeoW`/`_lastGeoH`, `geoSettleTimer`, `geoRestoreTimer`,
`_reconcileGeometry()` and `!root._geometryInvalid` in
`searchArticleLoader.active` are removed.

- *Why deleting is safe:* the teardown existed to move a stale native surface. The
  surface was never stale — its QML parent was simply in the wrong place. With the
  layout corrected and the teardown deleted outright, the dock painted (**594**
  accent px in landscape, against **15** with the bug), and tapping a dock tab
  navigated. Nothing the teardown did was contributing.
- *Why not leave it in as a belt-and-braces measure:* it costs a visible flash of
  the pane background on every rotation and a second article re-render (the
  surface re-create renders, and then the responsive reflow renders again because
  the WebView's height changed) — all of it worse than the bug it was guarding
  against. Its trigger (`w > h` flip) also cannot express the landscape-launch
  case. Leaving a machine that has never been shown to help is how the next person
  ends up debugging the wrong thing.

**D3 — Keep the inset re-read and the `_pickerOpen` teardown.**
Two things in the same code are *not* part of the bug and stay:

- `_refreshInsets()` still runs on every `width`/`height` change. The Android
  navigation-bar inset genuinely moves on rotation (the bottom inscription goes to
  a side and the bottom inset becomes 0), so the chrome must keep re-reading it.
  Only the geometry side-effect is gone.
- `_pickerOpen` still destroys the inline surface. That one is not about
  orientation at all: the group picker is a modal QML dialog, and a live native
  WebView covers it. Removing that guard would reintroduce a real, separate bug.

## Ruled out

Recorded so the next person does not re-derive them.

- **"The native surface's bounds go stale after a rotation."** The original theory
  (and the one the deleted code was built on). False: the surface's own item
  geometry was always correct — it is `anchors.fill`-style inside a pane whose
  bottom is the dock's top. What was wrong was the pane's *height*, which is QML
  layout, not native staleness. It is also not detectable from QML: there is no
  readable property for a platform view's native bounds.
- **"Toggle `visible` on the live `WebView` instead of re-creating it."** Cheaper
  and it would keep the DOM, but it treats a symptom of a layout bug with a
  workaround, and it was never needed once the layout was correct. Not worth
  carrying as machinery.
- **Detect the overflow and react to it.** Same objection: the invariant "the
  article area's bottom must be at or above the dock's top" is only enforceable by
  construction (a floor that fits) or by measurement at runtime, and measurement
  would have to be logged to be useful. Construction was available and free.
- **A settled-width reconciliation (the design this change started from).**
  Implemented — creation-time width recorded in `Loader.onLoaded`, compared on a
  ~250 ms debounce off `_refreshInsets`, with the surface destroyed for ~120 ms
  before being rebuilt — and then discarded. With the layout floor corrected it
  changed nothing observable, so it was deleted rather than shipped as inert
  machinery (design D2). It exists in no build.
- **Rebuild the landscape layout** (side rail, or a different dock placement). A
  separate change with its own review; the reported symptom did not ask for it.

## Risks / Trade-offs

- **[A very short landscape window (e.g. a small freeform window, or a landscape
  split-screen) could still make the column overflow, since 88 is a constant.]** →
  Not reachable in this app's supported configurations (full-screen phone/tablet).
  Noted rather than defended against; if it ever is, the fix is the same one —
  lower the floor.
- **[88 px is a tight article band on a landscape phone.]** → Accepted. The dock
  and the tab it belongs to are worth more than 42 px of article, and the article
  is scrollable from there. Portrait is unaffected (it measures ~300 px of band and
  will keep all of it — the floor is a floor, not a fixed height).
- **[An open article still jumps to the top after a rotation.]** → Pre-existing and
  unchanged: `searchArticleView.onHeightChanged` restarts `articleReloader` when
  the height differs from `loadedAtHeight`, and `loadHtml` resets the scroll. That
  is the responsive reflow path, and the removed teardown merely added a *second*
  reset on top of it. Measured on device: scroll down, rotate to landscape and
  back, and the article area is pixel-identical to the unscrolled state (0 % of
  sampled pixels differ from the top screenshot, versus 9.5 % between top and
  scrolled — i.e. the scroll really was lost, and it is the reflow that loses it).
  Fixing it means restoring a DOM scroll offset after the reflow, which is a
  separate change.
- **[Deleting the teardown changes behaviour the code was written to have]** (no
  flash, one render per rotation instead of two). → That is the point, and it is
  verified on device.
- **[Unverified without hardware]** → the change is only claimed fixed once the
  on-device pass in `tasks.md` §5 passes in both orientations.
