## Why

Every produced dictionary carries an `About this dictionary` article, so a user
with several dictionaries sees several identically named pseudo-headwords. The
DSL header vocabulary has no description field, but the reader does support
Lingvo's sibling `.ann` annotation, which the engine reads
(`engine/src/dict/dsl.cc` derives `<base>.ann` and exposes it as the dictionary
description). The converter writes neither a self-describing about headword nor
that annotation.

## What Changes

- Name the about article after the dictionary (`About kaikki-en`) instead of the
  fixed `About this dictionary`, so several produced dictionaries are
  distinguishable.
- Write a sibling plain-text annotation file `<base>.ann` (Lingvo's convention,
  read by goldendict-ng) carrying the same attribution, for readers that surface
  a dictionary description.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: the provenance-and-attribution requirement gains a
  self-describing about headword and a sibling annotation file.

## Impact

- `scripts/kaikki-to-dsl.py`: the about article's headword uses the dictionary
  name; a new `write_annotation` writes `<base>.ann` on every build.
- `scripts/tests/test_kaikki_to_dsl.py`: the about-headword filter and tests for
  the annotation file.
- `docs/KAIKKI-CONVERSION.md`: the output-layout note.
