## Why

Japanese had a profile in name only, and it showed in a real build:

- **no `pos_labels`** — every part of speech printed as the source's English code
  (`noun`, `verb`, `adj_noun`, …) in an otherwise Japanese article;
- **an empty form vocabulary** — every reading (`transliteration` + `go-on`/
  `kun`/…) and every inflection was listed as a "form" labelled with raw English
  tags, because `form_tags` was empty and nothing was labelled;
- **no sense-tag labels** — `figuratively` rendered as `(figuratively)`;
- **no CJK awareness in examples** — a Japanese clause is one whitespace token, so
  the headword only matched when it began a clause, and `。` was not a sentence
  terminator, so a long quotation was never bounded to its sentence (an archaic
  pre-war passage survived on a modern sense);
- the profile's `has_audio=False` was **dead**: the flag was never read.

## What Changes

- **A full Japanese profile**: parts of speech in Japanese (名詞, 動詞, 形容動詞,
  助詞, …); readings labelled as readings (読み, 呉音, 漢音, 唐音, 訓, 常用) rather
  than as bare "transliteration" forms; conjugations labelled as a Japanese
  grammar prints them (未然形, 連用形, 終止形, 連体形, 仮定形, 命令形, …); Japanese
  sense-tag labels (比喩, 口語, 俗語, 方言, …).
- **`has_audio` is honoured**: a language whose profile declares no recordings
  fetches no audio archive, in the build and in `prefetch-audio` alike.
- **CJK example handling**: `。！？` end a sentence and CJK brackets/quotes are
  skipped as punctuation; a CJK headword is matched as a substring, because it
  has no word boundary to match against.

## Capabilities

Modifies **dictionary-conversion**: the "Source-language profiles" requirement
(the profile's audio declaration) and the "Example qualification" requirement
(CJK substring matching and sentence punctuation).

## Impact

- `scripts/kaikki-to-dsl.py`: the `ja` profile constants, `_headword_span`
  (CJK substring match), `_sentence_span` (CJK terminators), `build` and
  `prefetch_audio` (`has_audio`).
- `scripts/tests/test_kaikki_to_dsl.py`.
- `docs/KAIKKI-CONVERSION.md`.
