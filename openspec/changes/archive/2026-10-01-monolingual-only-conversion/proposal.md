## Why

`scripts/kaikki-to-dsl.py` builds monolingual dictionaries on purpose, but the
`dictionary-conversion` spec still carries a *target language* and a "Bilingual
pair" scenario, plus an "Article content" clause and scenario for target-language
translations (`[trn]`). The tool has none of that, so the spec describes a
capability that does not exist and, by decision, will not be built on this data.

## What Changes

- Remove the bilingual requirements ("Language-pair selection" with a target
  language; "Article content"'s translations clause) and replace them with
  monolingual equivalents ("Language selection"; "Article body").
- State the gloss language plainly: it is the data edition's language, so the
  dictionary's language is chosen by which edition you build from.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: the language-selection and article-content
  requirements are narrowed to one language.

## Impact

- `openspec/specs/dictionary-conversion/spec.md`: the two requirements.
- `docs/KAIKKI-CONVERSION.md` and the tool's help epilog: the gloss-language
  framing, and a pointer to where a future translation dictionary is planned.
