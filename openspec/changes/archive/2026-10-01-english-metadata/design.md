## Context

`_language_name(record, code)` (`kaikki-to-dsl.py`) returns the record's `lang`
field, which is the edition's own name for the language: the English extract says
`English`/`Russian`, but the Russian extract says `Русский`. That name flows into
`#INDEX_LANGUAGE`/`#CONTENTS_LANGUAGE`, the about article and the `.ann`, so a
non-English edition produces non-English metadata.

## Goals / Non-Goals

**Goals**

- Metadata (`#NAME` aside) names the language in English regardless of edition.
- Content stays in the dictionary's language.

**Non-Goals**

- No localization of the metadata *into* the dictionary's language (that was P2,
  rejected as low-value for generic boilerplate).
- No change to the app; it displays `#NAME` and the pair today, and localizing
  that is a separate app change.

## Decisions

### D1: A small English name table, source name as fallback

`LANGUAGE_NAMES` maps the language codes the tool is likely to build in (the four
profiles plus common ones) to English names; `_language_name` returns the table's
name when the code is present, else the record's own `lang`, else the code. The
table is the one place to extend, and an unlisted language still reads better than
a raw code.

### D2: The description drops the language word

`description_lines` becomes `<title>: a Wiktionary-based dictionary` rather than
embossing the language into the sentence, so the first line needs no declension or
agreement in any language. The language is still listed below (`Language:
English (en)`).

## Risks / Trade-offs

- **The app's language-pair sub-line becomes English** (`Russian/Russian`) until
  the app localizes its display, since it renders those header strings verbatim.
  That is the intended P1 split: the artifact carries canonical English metadata,
  the app owns the localized presentation.
