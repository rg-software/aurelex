## Why

In landscape the bottom navigation dock is invisible on the Search tab — the only
tab that owns the inline article `WebView`. The dock is fine in portrait and on
every other tab, so the fault is inside the Search pane, not the dock.

It is a **QML layout overflow**, not a stale native surface. `searchArticleArea`
carried `Layout.minimumHeight: 300` as the last item of a `ColumnLayout` whose
search row above it cannot shrink. On a landscape phone the Search pane is
shorter than that floor, so the column cannot fit and the overflow spills
**downward**, out of the pane and over the dock. The `WebView` inside is a native
Android child view, which ignores QML `z` and `clip`, so it then paints over the
dock instead of being clipped by it — the whole bottom bar disappears.

Measured on a Motorola ThinkPhone (Android 15, landscape, logical px): the article
area's bottom edge landed at **y = 364** while the dock's top edge is **y = 307** —
57 px of overlap, the dock's full height is 80.

The earlier mitigation (`_geometryInvalid`, an orientation-teardown of both
WebViews) assumed the stale-native-surface theory and never fixed the overflow:
destroying and re-creating the surface re-runs the same layout and produces the
same overspill. It was also expensive for nothing — every rotation flashed the
pane background and rendered the article a second time.

## What Changes

- **`searchArticleArea`'s `Layout.minimumHeight` drops from 300 to 88.** That is
  the whole fix. The floor stays a floor — it keeps the article toolbar from
  inverting its anchors and guarantees a usable band — but it is now smaller than
  the leftover height of a landscape phone, so the column cannot overflow. Measured
  after the change in landscape: article area `y=64 h=180`, WebView `h=134`,
  article bottom **821** vs dock top **856** (device px) — no overlap.
- **The orientation-teardown machinery is deleted**, not repaired:
  `_geometryInvalid`, `_lastGeoW`/`_lastGeoH`, the settle/restore timers and
  `_reconcileGeometry()`, and `!root._geometryInvalid` from the inline loader's
  `active` binding. Measurement proved it unnecessary — with the layout fixed and
  the teardown off, the dock paints. Its cost goes away with it: every rotation
  used to flash the pane background and re-render the article a second time (once
  for the re-created surface, once for the reflow).
- **Kept**, deliberately: `_refreshInsets`'s re-read of the system insets on every
  window size change (the bottom inset genuinely moves on rotation), and the
  separate `_pickerOpen` teardown, which exists so the native surface cannot cover
  the modal group picker.

Not a change: an open article still returns to the top of its scroll position
after a rotation. That is the pre-existing responsive-reflow path
(`articleReloader` re-renders the HTML whenever the WebView's height changes), not
the teardown — measured, and recorded in `docs/TESTING.md` so it is not
re-attributed to this fix.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lookup`: the "Article rendering" requirement gains the guarantee that the Search
  pane's layout never overflows into the bottom dock, and that the inline article
  surface therefore stays clear of the app's own chrome. It states the
  user-visible contract (the dock stays visible and tappable in every orientation,
  the article survives the rotation) without naming the layout floor, which is the
  implementation.

## Impact

- `app/main.qml` only: one layout value, plus deletion of the geometry
  reconciliation in `_refreshInsets`, the `_geometryInvalid` family of properties,
  and the `searchArticleLoader.active` binding.
- No engine, carve, or `gd_*` boundary change; no staging, catalog, or format
  change. Pure QML.
- No new user-visible English text, so no `scripts/update-translations.ps1` run.
- Verified on hardware (Motorola ThinkPhone, Android 15) in both orientations,
  including a cold start in landscape and an IME regression guard — see `tasks.md`
  §5.
