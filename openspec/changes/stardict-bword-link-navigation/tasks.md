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

- [x] 2.1 Rewrite `bword:` cross-references into the handled lookup scheme where
  StarDict articles are post-processed, following the existing rewrites
- [x] 2.2 Anchor the match to the `href` attribute only, so `bword:` in article
  text is untouched and an already-rewritten link cannot re-match
- [x] 2.3 Reuse the existing query-word extraction so headwords with spaces,
  punctuation and non-ASCII resolve correctly, rather than hand-escaping —
  `Afghanistan Geography` (with a space) round-trips as `gdlookup:Afghanistan
  Geography` and looks up
- [x] 2.4 Ship as a `patches/` deviation patch; do not edit `engine/` in place —
  `patches/0006-stardict-bword-cross-references.patch`, and all six patches now
  apply in order to a pristine `git archive` of the pinned engine

### The actual defect, once measured

Not a missing feature — the engine already tried to handle this and got it
wrong in two ways (`engine/src/dict/stardict.cc`):

1. The link regex's `(bword://)?` group is **optional and expects slashes**.
   A dictionary emitting `bword:Word` (no slashes — what The World Factbook
   does) leaves the scheme attached to the captured word, so
   `link.indexOf(':') < 0` is false and the link falls through to the
   pass-through branch.
2. Even when it did match, the rewrite wrote the link back as **`bword:`** —
   a scheme nothing consumes. So the output could never be tapped either way.

The fix strips either `bword://` or `bword:` prefix, then rewrites to
`gdlookup:`, which the boundary and the QML link poller already resolve. That
also matches the anchor branch directly below it, which already used
`gdlookup://localhost/`.

## 3. Catch it on host

- [x] 3.1 Smoke assertion: looking up a StarDict entry whose article contains a
  `bword:` cross-reference emits HTML with **no** `bword:` href
  (`STARDICT_LINK_NO_BWORD`)
- [x] 3.2 Smoke assertion: the rewritten link resolves to a lookup target
  (`STARDICT_LINK_REWRITTEN`). Confirmed the linked entry itself resolves:
  `gd_lookup("Afghanistan Geography") -> 5565 bytes`, images intact
- [x] 3.3 Extend the StarDict fixture with a cross-reference between two of its
  entries. **This required switching the fixture from a global
  `sametypesequence=m` to per-article type characters**, because the rewrite
  lives in the HTML handling path and a plain-text entry escapes its markup into
  visible text instead of producing a link. The fixture now exercises both
  types: `clot` is HTML with the cross-reference, the others plain
- [x] 3.4 Confirm the existing smoke assertions still pass — full CI-equivalent
  run (`smokec` + `.dsl.dz` + `.dsl.files` + `nested/`): **EXIT=0, zero FAILs**,
  3 dictionaries, all `GROUP_*`, `RESOURCE_*`, `REIMPORT_*`, `REMOVE_*` OK
- [x] 3.5 **Teeth check**: with the fix reverted and the fixture kept, both new
  assertions report FAIL; with it restored, both report OK. The check is not
  vacuous

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
