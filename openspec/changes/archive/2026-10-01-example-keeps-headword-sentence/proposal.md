## Why

A Wiktionary quotation longer than the 200-character bound is cut from the
**start**, and an ellipsis appended. When the headword sits late in the quote,
the fragment left behind is the lead-in and the words that actually show the
word in use are thrown away — the opposite of the documented intent ("the phrase
that shows the word in use, not the surrounding essay").

Seen on the Russian build: the «Хан» card's lake sense carries the citation
«…перевалил Шишалдинский хребет и **вышел к озеру Хан**» — a 290-character
quote whose only tie to the sense is its last four words, all of them past the
cut.

## What Changes

- Shorten an over-long example so the headword stays visible: keep the sentence
  that contains the headword (or one of the record's listed forms), and when even
  that sentence exceeds the bound, keep a window centred on the headword. An
  ellipsis marks a cut edge. A quote with no findable headword falls back to the
  existing head-cut.

## Capabilities

Modifies **dictionary-conversion**: the "Example qualification" requirement
(over-long examples are shortened).

## Impact

- `scripts/kaikki-to-dsl.py`: `_truncate_example` (takes the headword and forms),
  new `_headword_span` / `_sentence_span` / `_window_span` helpers, and the
  `_sense_examples` call site.
- `scripts/tests/test_kaikki_to_dsl.py`: truncation tests.
- `docs/KAIKKI-CONVERSION.md`: the example-shortening paragraph.
