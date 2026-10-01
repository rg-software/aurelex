## Context

`_sense_examples` keeps at most one qualifying example per sense and passes it
to `_truncate_example`, which cut the first `_EXAMPLE_MAX_CHARS` (200) at a word
boundary. The example was chosen because it contains the headword; the new job
is to make sure the *shown part* still contains it.

## Decisions

### D1: Keep the headword's sentence, then a window around it

`_truncate_example` now locates the headword (or a listed form) and returns the
sentence around it; only if that sentence is itself over the bound does it fall
back to a window of `limit` characters centred on the headword. Sentence
detection is punctuation-only (`.!?…` plus trailing closers) — enough to keep a
single sentence instead of a whole quotation, without a real sentence tokenizer.

### D2: One span helper, shared with the qualification check

`_headword_span` returns the match span and encodes the exact two matches
`_example_shows_word` already accepted (exact token against the headword or a
listed form; shared `_MIN_STEM` stem against the headword). `_example_shows_word`
becomes `_headword_span(...) is not None`, so what decides "the example uses the
word" and what decides "where the word is" cannot drift apart.

## Risks / Trade-offs

- **Naive sentence splitting** can break at an abbreviation (`В. В.`), so the
  kept sentence may start mid-clause. Acceptable: it is a shortening heuristic,
  and the result still reads as a phrase and still contains the headword.
- **A cut edge is marked with an ellipsis**, so `… ` / ` …` may add two
  characters over the bound.
