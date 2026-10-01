## Why

The Russian profile still uses the Latin grammatical abbreviations (`gen.`,
`sg.`, `m.`), so a fully Russian dictionary prints `(sg., nom.)` next to Russian
glosses. The spec already requires a profile to carry its own short labels; this
is the Russian data for that, and no behavior changes.

## What Changes

- Replace the Russian profile's `short_tags` with the Russian Cyrillic
  abbreviations a Russian dictionary uses (`ед.`, `мн.`, `им.`, `род.`, `дат.`,
  `вин.`, `тв.`, `пр.`, `м.`, `ж.`, `с.`, `наст.`, `прош.`, `буд.`, `несов.`,
  `сов.`, `1-е л.`, …).

## Capabilities

No spec-level behavior change: the source-language-profiles requirement already
covers a profile's short labels; this fills in Russian's.

## Impact

- `scripts/kaikki-to-dsl.py`: `_RU_SHORT_TAGS`.
- `scripts/tests/test_kaikki_to_dsl.py`: the expected Russian form labels.
