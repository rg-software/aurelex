## Why

The Russian Wiktionary extract has Russian glosses but its structural data is
English: `pos` is `noun`/`verb`/`adj`, and the tags are `colloquial`,
`figuratively`, `genitive`. So a Russian dictionary built from it prints
`[p]noun[/p]` and `(colloq.)` in the middle of Russian text. The profile already
localizes grammatical *form* labels, but not the part of speech or the sense
tags, because `pos_labels` does not exist and the Russian profile reuses the
English sense abbreviations.

## What Changes

- Give a language profile the display labels for its parts of speech, so a part
  of speech shows in the dictionary's language instead of the raw English code.
- Give the Russian profile its own sense-tag abbreviations (Russian), rather than
  reusing the English ones.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: the source-language-profiles requirement now covers
  the part-of-speech and sense-tag labels, not only the grammatical forms.

## Impact

- `scripts/kaikki-to-dsl.py`: `LangProfile.pos_labels` and its use at the `[p]`
  render site; a Russian `pos_labels` and `sense_short_tags`.
- `scripts/tests/test_kaikki_to_dsl.py`: a Russian POS/sense label test.
