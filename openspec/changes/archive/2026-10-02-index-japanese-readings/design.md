## Context

`--include-inflections` already established the pattern: extra headword lines on
a card, with the documented cost that DSL has no hidden alias, so an indexed word
also lands in the suggestion list. Readings are a different kind of form, which
is why this is a separate flag rather than folding them into that one.

## Decisions

### D1: A second opt-in flag, not a widening of `--include-inflections`

A reading is not an inflection (the profile says so, and the readings-line change
put them on their own line precisely for that reason). Overloading
`--include-inflections` would make its name lie for Japanese and change its
effect for every language.

### D2: Index the hiragana form

A reading is how a word is looked up by sound, and a kana lookup is typed in
hiragana. The source writes on-yomi in katakana (`ベイ`), which a hiragana typist
cannot reach, so readings are folded to hiragana before indexing. The conversion
is a codepoint shift; `ー` is shared by both scripts and is left alone.

### D3: Off by default

It is the same trade as `--include-inflections`: every indexed word also appears
in the suggestion list, and Japanese readings are ambiguous by nature (`しょう`
reaches many articles). The default dictionary stays kanji-indexed; the flag is
for lookup by sound.

## Risks / Trade-offs

- **Suggestion-list growth.** Measured at ~1 extra headword per card (200 random
  headwords → 302 headwords), but the whole dictionary gains on the order of
  33k entries plus the fan-out from ambiguous readings.
- **Katakana input is not answered.** A lookup typed in katakana (rather than the
  hiragana an IME produces) will not match. Indexing both forms was rejected to
  keep the index smaller; it is a one-line change if it turns out to matter.
