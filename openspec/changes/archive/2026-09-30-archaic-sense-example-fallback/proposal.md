## Why

Archaic, obsolete and dated senses are kept and marked with the usage icon, but
the example filter is era-blind: it drops Early Modern and Middle English
quotations everywhere. On a *modern* sense that is right — a readable example is
preferred and the rule stops old quotations drowning it. On an archaic sense
there is usually no other example, so the sense is left bare for no gain: about
1 in 5 archaic/obsolete/dated senses that carry a quotation lose it (76.1% of
`obsolete` senses keep one), even though archaic senses are otherwise better
illustrated than modern ones.

## What Changes

- On a sense marked obsolete, dated or archaic, fall back to one archaic example
  when no modern-readable example qualifies, so the sense is illustrated rather
  than bare. A readable example is still preferred when one exists.
- Cross-reference bookkeeping (`Citations:`) is still dropped everywhere, still
  at most one example per sense, still shortened at the length bound.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: the example-qualification requirement gains a
  fallback for senses marked as archaic use.

## Impact

- `scripts/kaikki-to-dsl.py`: the example filter splits into bookkeeping vs
  archaic; a per-sense "archaic example allowed" flag travels with the sense's
  examples to the renderer.
- `scripts/tests/test_kaikki_to_dsl.py`: tests for the fallback, the preference
  for a readable example, and the unchanged bookkeeping drop.
