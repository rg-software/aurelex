# Proposal

## Why

The kaikki monolingual dictionaries show a headword pronunciation
transcription; the bilingual ones show only `[s]` playback. The
transcription text is already in hand — the audio planner iterates the
headword's kaikki records, whose `sounds[]` carry `ipa` (and `enpr`) —
and the reader renders `[t]` natively, so this is builder-only work for
both translation directions.

## What Changes

- One `[t]…[/t]` line per card, right under the headword: the most common
  transcription across the headword's kaikki records (first-seen wins
  ties), picked with kaikki's own per-record notation discipline (IPA
  unlabeled, enPR labeled, X-SAMPA-tagged sounds skipped).
- Present with or without audio; silent cards keep the text. Pairs
  (examples-only) cards are out of scope — minimal by design.
- `Card.transcription` field, `[t]` added to the builder's tag allowlist,
  mirrored in the HTML preview.

## Capabilities

### New Capabilities

<!-- none: this change extends an existing capability -->

### Modified Capabilities

- `bilingual-dictionary`: new "Headword pronunciation" requirement under
  the translation dictionaries.
