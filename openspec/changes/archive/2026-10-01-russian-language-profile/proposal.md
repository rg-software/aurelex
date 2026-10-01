## Why

The converter has profiles only for English, German and Japanese. Building
Russian (`--source-lang ru`) falls back to a permissive English-shaped default
and prints `warning: no language profile for 'ru'`, so grammatical forms are
labelled with raw, unabbreviated tags and the English sense-tag noise set does
not match Russian. The Russian extract is in the same snapshot, so only the
profile is missing.

## What Changes

- Add a Russian (`ru`) language profile: the grammatical form vocabulary and
  short labels (case, number, gender, animacy, verb forms, aspect), the tags
  that disqualify a form (table machinery, transliterations, the canonical lemma
  entry, register/dialect), the pronunciation field (IPA), and the sense-tag
  noise/abbreviation sets.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: a requirement that each supported source language has
  a profile, and that an unsupported one falls back and says so.

## Impact

- `scripts/kaikki-to-dsl.py`: a `ru` entry in `LANG_PROFILES` and its tag tables.
- `scripts/tests/test_kaikki_to_dsl.py`: a Russian profile test alongside the
  English/German/Japanese ones.
