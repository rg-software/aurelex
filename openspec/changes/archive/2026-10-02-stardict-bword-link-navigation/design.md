## Context

StarDict articles cross-link with `<a href="bword:Some Headword">`. The World
Factbook is built entirely this way: a country is ten entries
(`Afghanistan Introduction`, `Afghanistan Geography`, …) that link to each
other, and none of those taps do anything.

## Where the gap is

Two lists have to agree, and this scheme is in neither:

- The engine's consumed schemes (`engine/src/main.cc`):
  `gdlookup, gdau, gico, qrcx, bres, n, gdprg, gdvideo, gdtts, gdinternal,
  entry` — no `bword`.
- The app's link handling (`app/main.qml`): it matches `/gdlookup/` and
  `gdlookup://` only.

Every other format reaches the app in a handled scheme. Aard's links are
rewritten to `n:\2`; DSL and MDict links are rewritten to
`n://localhost/…` or `gdlookup:`. StarDict's `bword:` is passed through
unchanged.

## Decision: rewrite it like the other formats, engine-side

Two options were considered.

**A. Add `bword` to the app's recognised handlers.**
Small and app-only, but it puts a StarDict-specific scheme into the app, which
is meant to know nothing about dictionary formats — the boundary is `gd_*` and
the app's link vocabulary is the engine's (`gdlookup`, `gdau`, `bres`, …).
Adding `bword` there starts a second, format-flavoured vocabulary that the next
format would extend again.

**B. Rewrite `bword:` to the existing handled scheme in the engine**, beside the
rewrites the other formats already do. **Chosen.** It keeps the app's link
vocabulary format-agnostic, matches how Aard/DSL/MDict are already treated, and
is testable on host through the smoke tool without a device.

The rewrite goes wherever the article is post-processed for StarDict, following
the pattern already used for the other formats, and is expressed as a
`patches/` deviation so the pinned engine stays clean.

## The rewrite must be careful

`bword:` values are headwords, and headwords can contain characters a naive
substitution would break: spaces (`Afghanistan Geography`), punctuation, and
non-ASCII. The existing rewrites use regexes over the href attribute; the new
one must match the same shape and produce a URL that resolves through the
existing word-extraction path (`utils.hh`'s query-word helper for the
`n`/`gdlookup` schemes), not a hand-rolled escape.

Also: only the `href` attribute is rewritten. A `bword:` appearing in article
text must be left alone.

## Verification

- **Host**: the smoke tool looks up a factbook entry and asserts the emitted HTML
  contains no `bword:` href, and that the rewritten link resolves — the tool can
  follow the rewritten URL through `gd_lookup` without a device.
- **Device**: tap a cross-reference in `Afghanistan Introduction` and confirm it
  opens `Afghanistan Geography`.
- **Regression**: a dictionary whose links already work (kaikki) must be
  unchanged.

## Risks / Trade-offs

- **[Headwords needing escaping]** A headword with `"`, `<`, `&` or spaces could
  produce a malformed URL. → The rewrite reuses the existing substitution shape
  rather than inventing one, and the host assertion covers a factbook headword
  containing a space.
- **[Double rewriting]** If a later stage also rewrites links, the result could
  be mangled. → The rewrite is anchored to the `bword:` prefix only, so an
  already-rewritten link cannot match.
- **[Engine change via patch]** Keeps the pinned tree clean but adds a fifth
  deviation. → Consistent with the existing four; the smoke assertion is what
  catches a break at the next engine bump.
