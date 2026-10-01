## Context

The spec's "Language-pair selection" requirement accepts a source and a target
language and has a "Bilingual pair" scenario producing target-language
translations; "Article content" has a matching bilingual clause and scenario.
The tool (`scripts/kaikki-to-dsl.py`) is monolingual-only: it has no
`--target-lang`, renders no `[trn]`, and its docstring says so. The gloss
language is in fact fixed by the *data edition* the snapshot was extracted from,
not chosen: the default edition is the English Wiktionary, so `--source-lang ru`
against it yields Russian headwords glossed in English — not a translation
dictionary, and not the monolingual Russian dictionary the flag might imply.

## Goals / Non-Goals

**Goals**

- The spec states only what the tool does: one language, whose headwords and
  glosses come from the same edition.
- The docs and help make the edition/gloss-language relationship explicit.

**Non-Goals**

- No `--target-lang` and no translation output; a translation dictionary is a
  separate future project (BabelNet/Tatoeba/WordNet-style sources), recorded in
  the docs, not built here.
- No change to how records are selected beyond dropping the target language.

## Decisions

### D1: Remove rather than reword the bilingual requirements

"Language-pair selection" and "Article content" are removed and re-added in
monolingual form, because a scenario cannot be deleted by a MODIFIED block, and
the bilingual scenarios are the thing being dropped. The new "Language
selection" keeps the useful scenarios (another language's records excluded; an
unsupported language reported). The re-added article requirement is named
"Article body" because a delta cannot ADD and REMOVE the same name.

### D2: The edition names the language

The dictionary's language is the data edition's; `--source-lang` must match it.
The default edition is English, the Russian edition is `ruwiktionary`, and so on
(`kaikki.org/<edition>wiktionary/rawdata.html`). The help and docs say this, so
`--source-lang ru` against the English edition (English glosses) is understood as
the wrong edition rather than a supported bilingual mode.

### D3: Point at the future translation plan from the docs, not the spec

The spec should not carry a requirement the system does not implement. The
candidate translation sources and their licenses are recorded in
`docs/KAIKKI-CONVERSION.md` (and the backlog) as a plan, so the idea is not lost
without appearing as shipped behavior.

## Risks / Trade-offs

- **Dropping the target language removes a documented-but-unbuilt feature.** It
  was never wired up, and building it on this data was rejected on measurement;
  the plan for doing it properly lives in the docs.
