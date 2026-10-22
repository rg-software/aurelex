# Design: article-headword-titles

## Context

See proposal.md (Why). A card's body is built by `render_card()` in
`scripts/kaikki/render.py`, which never sees the card's headwords: `emit()` in
`scripts/kaikki/build.py` owns the headword list (primary + aliases) and calls
`render_card(records, audio, profile, known)`. The body therefore cannot name
its own headword, and neither can anything downstream — the engine header shows
only the dictionary, the app only the query.

## Goals / Non-Goals

- Goal: an article reached through an alias lookup says which word it defines.
- Goal: single-headword cards render byte-identically (shipped en/ru rebuilds
  must not change).
- Non-goal: changing lookup, fan-out, suggestion, or engine/app behavior. This
  is a renderer-only change.

## Decisions

1. **Markup: a `[b]…[/b]` first body line** (`\t[b]喧伝[/b]`). Over `[m0]` (not a
   real DSL level; `[mN]` carries indentation semantics a title must not have)
   and over `[c]` (color needs a value and conveys nothing here). `[b]` is core
   DSL, rendered by the engine and the standalone preview, with no indentation.
2. **Plumbing: optional `headwords` parameter on `render_card()`** (default
   `None`). Over prepending the title in `emit()`: all card layout stays in the
   renderer, and the default keeps `render_record()` plus every existing caller
   and test working unchanged.
3. **Condition: title if and only if the card has more than one headword.** Over
   always-titling: base-only cards (the entire shipped en/ru output) stay
   byte-identical, which the determinism requirement makes checkable, and the
   title appears exactly where an alias lookup can land.
4. **No blank line after the title.** The existing blank-line rules govern only
   separation between parts of speech; the title attaches to the top of the
   article, keeping the byte diff to one line per alias card.

## Risks / Trade-offs

- [Risk] The engine might not style `[b]` inside an article body as expected →
  Mitigation: `[b]` is long-standing core DSL markup; the preview suite asserts
  tag balance and renders the sample, and the ja sample build is eyeballed
  before the full rebuild.
- [Risk] On a kanji lookup the title repeats the query → Accepted: paper
  dictionaries head every article with its word, and the repetition is the
  price of attributing the alias case.
- [Trade-off] Homophone fan-out itself (ten けんでん cards) is unchanged; the
  title makes each attributable but does not collapse them. Collapsing distinct
  words would destroy content and is out of scope.

## Migration Plan

Implement → unit tests → ja sample build with `--index-readings` (eyeball 喧伝
card + preview) → full ja rebuild → republish via `publish-catalog.ps1`. The
digest change flows through the installed-dictionary update lifecycle, which
doubles as the on-device verification and retests the greyed-row anomaly.

## Open Questions

None.
