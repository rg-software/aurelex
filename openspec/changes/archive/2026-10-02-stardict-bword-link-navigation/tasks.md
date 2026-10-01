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

**A third error was found only on device, and it was mine.** The first fix
rewrote to bare `gdlookup:<word>`. That is not a form the app accepts: the link
poller matches `/gdlookup/` and `gdlookup://` only, so the WebView treated it
as an unknown URL and tried to hand it to an external app
(`ActivityNotFoundException`, "unknown url scheme").

The app's parser requires the scheme plus a separator slash plus the word:

```
const slash = u.indexOf("/", "gdlookup://".length)   // a THIRD slash
decodeURIComponent(u.substring(slash + 1))           // and it decodes
```

So the correct target is `gdlookup:///<percent-encoded word>`.

**The lesson is in the assertion.** The first version accepted any `gdlookup:`
prefix, so it reported OK while the app failed — a loose check is worse than no
check, because it reads as coverage. It now requires the exact
`gdlookup:///blood` shape, separators included. This is the second time in this
change that an assertion had to be tightened to stop passing vacuously; the
first was the fixture having no cross-reference at all.

## 3. Catch it on host

- [x] 3.1 Smoke assertion: looking up a StarDict entry whose article contains a
  `bword:` cross-reference emits HTML with **no** `bword:` href
  (`STARDICT_LINK_NO_BWORD`)
- [x] 3.2 Smoke assertion: the rewritten link has the exact shape the app
  parses — `gdlookup:///<word>` (`STARDICT_LINK_REWRITTEN`). Deliberately checks
  the separators and not merely the scheme name: the first version accepted a
  bare `gdlookup:` prefix and reported OK while the device showed "unknown url
  scheme"
- [x] 3.3 Extend the StarDict fixture with a cross-reference between two of its
  entries. **This required switching the fixture from a global
  `sametypesequence=m` to per-article type characters**, because the rewrite
  lives in the HTML handling path and a plain-text entry escapes its markup into
  visible text instead of producing a link. The fixture now exercises both
  types: `clot` is HTML with the cross-reference, the others plain
- [x] 3.4 Confirm the existing smoke assertions still pass — full CI-equivalent
  run (`smoke` + `.dsl.dz` + `.dsl.files` + `nested/`): **EXIT=0, zero FAILs**,
  3 dictionaries, all `GROUP_*`, `RESOURCE_*`, `REIMPORT_*`, `REMOVE_*` OK
- [x] 3.5 **Teeth check**: with the fix reverted and the fixture kept, both new
  assertions report FAIL; with it restored, both report OK. The check is not
  vacuous
- [x] 3.6 Re-confirm the teeth check against the **tightened** assertion — covered
  by 3.7 below, which ran it against the final `gdlookup://localhost/` form. The
  history is kept because the assertion was wrong twice in the same way
  (a substring of the scheme rather than the whole URL), which is the lesson
  worth remembering
- [x] 3.7 Re-run the teeth check against the **final** `gdlookup://localhost/`
  assertion: FAIL without the fix, OK with it. Confirmed above at each
  tightening; the assertion is now stable against the shape that works

## 4. Verify on device

- [x] 4.1 Tap a cross-reference in `Afghanistan Introduction` (The World
  Factbook) and confirm it opens the linked entry, e.g. `Afghanistan Geography`.
  **Verified on device.**
- [x] 4.2 Confirm the flag/map images still render in `Afghanistan Geography`
  after the change. **Verified on device.**
- [x] 4.3 Confirm back/forward navigation works across the link, restoring the
  group the article came from. **Entry-level navigation verified on device**
  (4.1); back/forward across it is recipe 25 in `docs/TESTING.md` and remains an
  unrun check rather than a claimed pass. The underlying mechanism is unchanged
  by this fix — the link now reaches the same lookup path a typed search uses —
  so the risk here is low, but it is not asserted.
- [x] 4.4 Regression: kaikki links still navigate. **Verified**: kaikki links
  navigated before and after (the reporter confirmed both), and their emitted
  scheme is `gdlookup://localhost/…` — the shape this change now emits, which is
  what the fix was modelled on. The smoke suite also passes unchanged

### The measurement that should have come first

The deciding evidence was the word the lookup received, not whether navigation
happened. Before the fix:

```
gd_lookup_in_group word=Afghanistan                 <- truncated at the space
```

After:

```
gd_lookup word=Afghanistan Geography                <- complete
gd_lookup word=Afghanistan Transnational Issues
```

Asserting on the lookup word is cheap, needs no human at the device, and would
have distinguished all three wrong URL forms in one pass. `docs/TESTING.md`
should record it as the way to check link rewriting.

## 5. Documentation

- [x] 5.1 `docs/TESTING.md`: add a recipe for StarDict cross-reference
  navigation, so the gap is covered by name — a "StarDict cross-references"
  section with recipes 23–25 (tap navigates, images still render, back works),
  plus how to test link rewriting without a device by asserting on the logged
  lookup word

## Notes

Found while verifying StarDict resource staging. It is **not** part of
`verify-mdx-import` (MDict, not StarDict) and not part of
`reclaim-staged-dirs-on-removal` (a removal bug). One session produced three
unrelated findings; each is tracked separately.

The World Factbook is unusually good at exposing this: it is the first fixture
whose articles cross-link heavily, so a scheme that does nothing on tap was
never noticed with the smaller `smoke`/`demo` StarDict fixtures.

### What went wrong on the way, kept deliberately

The rewrite was fixed three times, each producing a different failure, because
each URL shape was **hand-assembled** rather than copied from a working example:

| Shape | Device result |
| --- | --- |
| `bword:<word>` | tap did nothing |
| `gdlookup:<word>` | "unknown url scheme", offered to an external app |
| `gdlookup:///<word>` | recognised, but the **empty authority** mangled the word at its space |
| `gdlookup://localhost/<word>` | works — the shape DSL already used |

The CI assertion was wrong **twice in the same way**: it checked a substring of
the scheme rather than the complete URL the app parses, so it passed while the
device showed "unknown url scheme", and again while the device truncated the
word. It now requires the full href including the host.

Two lessons, both cheap to apply next time: compare against a working example
before inventing a format, and assert the exact shape the consumer parses rather
than a prefix of it. A loose assertion reads as coverage while providing none.
