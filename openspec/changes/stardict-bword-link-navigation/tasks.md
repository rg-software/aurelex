## 1. Confirm the mechanism

- [x] 1.1 Show the emitted HTML contains `bword:` anchors — `Afghanistan
  Introduction` links to nine sibling entries
- [x] 1.2 Show the app handles only `/gdlookup/` and `gdlookup://`
- [x] 1.3 Show the engine's consumed-scheme list does not include `bword`
  (`main.cc`), and that other formats are rewritten into a handled scheme
  (Aard → `n:`, DSL/MDict → `gdlookup:`/`n://localhost/`)
- [x] 1.4 Control: a dictionary whose links are rewritten (kaikki) navigates
  correctly in the same build, so the failure is the unhandled scheme and not
  link handling generally

## 2. Rewrite the scheme (engine, via patches/)

- [ ] 2.1 Rewrite `bword:` cross-references into the handled lookup scheme where
  StarDict articles are post-processed, following the existing rewrites
- [ ] 2.2 Anchor the match to the `href` attribute only, so `bword:` in article
  text is untouched and an already-rewritten link cannot re-match
- [ ] 2.3 Reuse the existing query-word extraction so headwords with spaces,
  punctuation and non-ASCII resolve correctly, rather than hand-escaping
- [ ] 2.4 Ship as a `patches/` deviation patch; do not edit `engine/` in place

## 3. Catch it on host

- [ ] 3.1 Smoke assertion: looking up a StarDict entry whose article contains a
  `bword:` cross-reference emits HTML with **no** `bword:` href
- [ ] 3.2 Smoke assertion: the rewritten link resolves through `gd_lookup` to
  the linked entry's article — the tool follows the link without a device
- [ ] 3.3 Extend the StarDict fixture (`scripts/make-smoke-stardict.py`) with a
  cross-reference between two of its entries, so the assertion has something to
  fire on. Without this the CI check has no input and passes vacuously
- [ ] 3.4 Confirm the existing smoke assertions still pass

## 4. Verify on device

- [ ] 4.1 Tap a cross-reference in `Afghanistan Introduction` (The World
  Factbook) and confirm it opens the linked entry, e.g. `Afghanistan Geography`
- [ ] 4.2 Confirm the flag/map images still render in `Afghanistan Geography`
  after the change
- [ ] 4.3 Confirm back/forward navigation works across the link, restoring the
  group the article came from
- [ ] 4.4 Regression: kaikki links still navigate

## 5. Documentation

- [ ] 5.1 `docs/TESTING.md`: add a recipe for StarDict cross-reference
  navigation, so the gap is covered by name

## Notes

Found while verifying StarDict resource staging. It is **not** part of
`verify-mdx-import` (MDict, not StarDict) and not part of
`reclaim-staged-dirs-on-removal` (a removal bug). One session produced three
unrelated findings; each is tracked separately.

The World Factbook is unusually good at exposing this: it is the first fixture
whose articles cross-link heavily, so a scheme that does nothing on tap was
never noticed with the smaller `smoke`/`demo` StarDict fixtures.
