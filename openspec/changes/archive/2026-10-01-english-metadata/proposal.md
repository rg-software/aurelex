## Why

A non-English edition names its language in its own language in the source (the
Russian extract's records carry `lang` = "Русский"), so a Russian dictionary's
description splices it into English ("a Wiktionary-based Русский dictionary") and
its language fields read "Русский". That is both awkward to read and a problem
for tools that match a language name: GoldenDict categorises a dictionary by the
name it is given. Metadata should be a canonical language, so this makes it
English; the *content* stays in the dictionary's language.

## What Changes

- Name the language in English in the dictionary's metadata (`#INDEX_LANGUAGE`,
  `#CONTENTS_LANGUAGE`, the about article and the `.ann`), whatever edition the
  data came from, falling back to the source's own name for a language we do not
  list.
- The about/`.ann` description reads as plain English (`<title>: a
  Wiktionary-based dictionary`), no longer splicing in a non-English name.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: a new requirement that metadata is in English.

## Impact

- `scripts/kaikki-to-dsl.py`: an English language-name table used by
  `_language_name`.
- `scripts/tests/test_kaikki_to_dsl.py`: a build from a foreign-named record
  names the language in English.

## Follow-up (separate change)

The app shows `#NAME` and the language pair verbatim in the dictionary list, so
with English metadata a Russian user sees English there. Localizing that display
(the list label and the pair) is an app change and is planned separately.
