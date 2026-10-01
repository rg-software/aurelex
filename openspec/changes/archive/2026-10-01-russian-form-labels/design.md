## Context

`_RU_SHORT_TAGS` maps the Russian profile's grammatical tags to labels; it
currently uses the Latin abbreviations (`gen.`, `sg.`, `m.`). The tag vocabulary
is English for every edition (measured from the snapshot), and the labels are the
profile's data.

## Decisions

### D1: The conventional Russian abbreviations

Use what a printed Russian dictionary uses: number `ед.`/`мн.`; case `им.`,
`род.`, `дат.`, `вин.`, `тв.`, `пр.`, `местн.`, `частичн.`; gender `м.`/`ж.`/`с.`;
animacy `одуш.`/`неодуш.`; verb `наст.`, `прош.`, `буд.`, `пов.`, `инф.`,
`прич.`, `деепр.`, `действ.`, `страд.`, `несов.`, `сов.`, `1-е л.`, `2-е л.`,
`3-е л.`; `сравн.`, `прев.`, `кр.`, `возвр.`, `неправ.`, `личн.`, `нескл.`,
`только мн.`. An unmapped tag still falls back to its source text.

## Risks / Trade-offs

- **The choice of abbreviation is a judgement call** (`пр.` for prepositional vs
  `предл.` for the preposition part of speech; `с.` for neuter). The entries are
  one table, easy to review, and the grammatical labels no longer mix Latin into
  a Russian dictionary.
