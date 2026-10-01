## Context

A `LangProfile` (`kaikki-to-dsl.py:119`) decides how a language's records become
an article: which tags label a form (`form_tags`), which disqualify one
(`form_noise_tags`), which fields carry a transcription (`pron_fields`), the
short labels (`short_tags`), and the sense-tag noise/abbreviations. `LANG_PROFILES`
has `en`, `de`, `ja`; anything else gets a permissive fallback with English tag
tables and a warning.

## Goals / Non-Goals

**Goals**

- A Russian profile grounded in the tags the snapshot actually uses, so a build
  needs no fallback warning and forms/senses read correctly.

**Non-Goals**

- Not a general "profile per language" framework — just the `ru` entry, built on
  the existing `LangProfile`.
- No change to the fallback for languages still without a profile.

## Decisions

### D1: Derive the tag vocabulary from the snapshot

The profile's tag sets come from measuring `ru` records in the cached snapshot
(`forms[].tags`, `senses[].tags`), not from memory: cases
nominative/genitive/dative/accusative/instrumental/prepositional (and
locative/partitive), singular/plural, masculine/feminine/neuter,
animate/inanimate, present/past/future, imperative/infinitive, participle/
adverbial, active/passive, imperfective/perfective, first/second/third-person,
comparative/superlative/short-form, and the frequent derivational labels
(reflexive, diminutive, augmentative, collective, …).

### D2: Disqualify table machinery, transliterations and the lemma entry

`_RU_NOISE` extends the shared register/table noise with `canonical`,
`romanization`, `class`, and the `error-*` tags: the canonical form is the
headword, a romanization is a transliteration (Russian has IPA), and the rest are
bookkeeping. So the forms line lists real inflections, not those.

### D3: Abbreviate with the conventional Russian-dictionary terms

`_RU_SHORT_TAGS` maps the grammatical tags to the abbreviations a printed Russian
dictionary uses (`nom.`, `gen.`, `dat.`, `acc.`, `instr.`, `prep.`, `sg.`, `pl.`,
`m.`, `f.`, `n.`, `impf.`, `pf.`, `3rd`, …). Sense abbreviations reuse the shared
English-tag wording (`_EN_SENSE_SHORT`) because the source's tag vocabulary is
English for every language; only the grammatical form labels are Russian-specific.

### D4: Drop the unremarkable mood/case tags on a sense

`_RU_SENSE_NOISE` = indicative (the unmarked mood) plus the transitive/
intransitive/not-comparable set, which say nothing a Russian noun/verb entry does
not already imply; aspect (imperfective/perfective) is *kept* — it is meaningful
for Russian.

### D5: A form the profile cannot label is not listed

Russian `forms` mix inflections with derivations and bookkeeping, and some carry
tags outside the grammatical vocabulary. `collect_profile_forms` now drops a form
whose label comes out empty rather than printing it bare, so the forms line holds
only forms the profile can describe. This is language-agnostic and improves every
profile; the permissive fallback is unaffected because it labels from the raw
tags and so is never empty.

## Risks / Trade-offs

- **The tag sets are a snapshot of this dump.** A later snapshot could introduce
  a tag not in `form_tags`; `label_tags` drops unknown tags from a label rather
  than failing, so the article degrades gracefully.
