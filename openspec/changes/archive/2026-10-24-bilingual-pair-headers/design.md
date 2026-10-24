# Design

## Context

See proposal.md — Why. `dsl.py` owns the header block; `build.py` owns the
direction; `package.py` is the pass-through between them.

## Goals / Non-Goals

**Goals:**

- Correct `En/Ru` vs `Ru/En` classification for all four bilingual
  dictionaries with zero byte change to en→ru outputs.

**Non-Goals:**

- No new header fields; the engine already reads exactly these two.

## Decisions

### D1. Direction in, names out, at assembly

`assemble(cards, name, title, about, index_lang, contents_lang)` with the
current English/Russian pair as defaults, so every existing caller keeps
working. `build_sample`/`build_pairs` map the direction to the name pair;
the CLI already carries `source_lang` into both modes.

## Risks / Trade-offs

- [ru→en outputs change bytes and need republication] → expected: the
  bytes were wrong. en→ru outputs are provably unchanged (showcase
  rebuild diff).
