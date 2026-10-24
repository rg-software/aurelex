# Proposal

## Why

Reviewing the built ru-en dictionary turned up content-free numbered
sections: 33,098 of 90,180 senses (37%) carry neither equivalents nor a
definition — e.g. `парк` 1. (empty + one duplicated example), 2.
(park/parkland + gloss), 3. (empty + synonyms). The en-ru dictionary has
zero such senses, so the rule below is a no-op there and the published
output rebuilds byte-identical.

An unlinked sense that reaches the article is a numbered shell around
secondary material (a concordance example, untranslatable synonyms). The
coverage report already counts these senses at resolve time; the article
loses nothing by omitting them, and dropping them also removes the
duplicated fallback examples and lets lone survivors shed their counter.

## What Changes

- Card assembly omits any sense with neither equivalents nor a definition
  (both directions); headwords left with no displayable senses get no card
  and join the existing skipped-empty count.
- `resolve_word`/`resolve_words` and the coverage report are untouched:
  unlinked senses are still resolved and counted.
- No engine, app, boundary, or import-path changes. No new dependencies.

## Capabilities

### New Capabilities

<!-- none: this change corrects an existing capability -->

### Modified Capabilities

- `bilingual-dictionary`: the "Sense-aligned equivalent resolution" and
  "Reverse equivalent resolution" requirements (unlinked senses are
  counted but omitted from the article when they carry neither
  equivalents nor a definition).
