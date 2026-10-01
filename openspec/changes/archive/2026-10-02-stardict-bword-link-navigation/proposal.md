## Why

Links inside StarDict articles do not navigate. The World Factbook splits each
country into ten entries (`Afghanistan Introduction`, `Afghanistan Geography`, …)
and cross-links between them, but tapping one does nothing.

The engine emits those links as `<a href="bword:Afghanistan Geography">`. The
app's in-article link handling recognises only `/gdlookup/` and `gdlookup://`,
and the engine's own list of schemes it consumes
(`main.cc`: `gdlookup, gdau, gico, qrcx, bres, n, gdprg, gdvideo, gdtts,
gdinternal, entry`) does **not** include `bword`. Other dictionaries have their
links rewritten into a handled scheme; StarDict's are passed through untouched.

Measured: the emitted HTML contains `bword:` anchors; a dictionary whose links
are rewritten (kaikki) navigates correctly in the same build, so the failure is
specific to the unhandled scheme rather than to link handling in general.

## What Changes

- **`bword:` links resolve as in-app lookups.** The scheme is either translated
  into the existing handled form or added to the recognised set, so a tap looks
  the word up in the current group like any other article link. Which of the two
  is decided in `design.md`.
- No change to articles that already work: links the engine already rewrites
  must keep behaving identically.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lookup`: the "In-article link navigation" requirement already states that
  tapping a link inside an article performs an in-app lookup, without
  qualification. This change makes that true for StarDict articles, whose links
  currently do nothing, and adds a scenario naming the scheme so the gap cannot
  reopen silently.

## Impact

- `engine/src/main.cc` (the consumed-scheme list) and/or the StarDict article
  path in `engine/src/dict/stardict.cc` — via a `patches/` deviation patch, per
  the merge contract, since this is engine code.
- `carve/smoke/main.cpp` — an assertion that a `bword:` link is present and
  rewritten, so the regression is caught on host rather than only on device.
- No QML, app UI, or staging change.
- Every StarDict dictionary that cross-links between entries is affected, not
  only The World Factbook.
