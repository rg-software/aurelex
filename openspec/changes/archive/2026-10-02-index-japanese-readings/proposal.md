## Why

Japanese lookup today is kanji-only, and most kanji words have no kana page, so
a reader who knows how a word sounds but not how it is written cannot find it.
Measured against the 2026-09-01 jawiktionary extract (124,022 ja headwords):

| | count |
| --- | --- |
| with a hiragana reading | 67,992 |
| whose reading is already its own page | 13,476 (20%) |
| **with a reading that is not a page** | **54,516 (80%)** |
| distinct kana readings that are not pages | 32,747 |

`保護` has no `ほご` page; neither does `四面楚歌` (`しめんそか`). Indexing readings
adds tens of thousands of lookups that the source's own page set does not provide
— the normal way a Japanese speaker searches ("I heard *hogo*").

## What Changes

- A new opt-in `--index-readings`, mirroring `--include-inflections`: a card's
  readings become extra indexed headwords, in **hiragana** (so a katakana on-yomi
  `ベイ` also answers `べい`) with the source's stem hyphen dropped (`すわ-る` →
  `すわる`). Off by default.

## Capabilities

Adds a requirement to **dictionary-conversion**: opt-in reading indexing. It is
the readings counterpart of the existing opt-in inflected-form indexing, and
uses the readings concept added by the readings-line change.

## Impact

- `scripts/kaikki/profiles.py` (`reading_words`), `build.py` (the extra headword
  lines), `cli.py` (the flag and its help).
- `scripts/tests/test_kaikki_to_dsl.py`.
- `docs/KAIKKI-CONVERSION.md`.
