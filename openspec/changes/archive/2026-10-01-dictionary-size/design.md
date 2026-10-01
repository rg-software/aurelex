## Context

`build()` knows the card count before it assembles the dictionary: after the
render/filter step, `report.cards` is the number of headword cards emitted (the
about article is not one of them). The about article is then built
(`kaikki-to-dsl.py:2494`) and `write_annotation` is called after the `.dsl.dz` is
written, so the count is available to both.

Lingvo reports "headings" (headword lines) and "entries" (cards). With
`--include-inflections` a card carries several headword lines, so headings >
entries. The card count is the honest "how many words can I look up" number here.

## Goals / Non-Goals

**Goals**

- The about article and the `.ann` both state the dictionary's entry count.

**Non-Goals**

- No separate "headings" count; the entry (card) count is the meaningful total,
  as agreed.
- No change to what counts as an entry.

## Decisions

### D1: One number, the card count

State `report.cards` — the number of headword cards — as the dictionary's size,
in both surfaces. It is already computed and excludes the about article, so the
number is honest and needs no extra bookkeeping.

### D2: The annotation takes it as a parameter

`write_annotation` gains a `card_count` argument that `build()` fills from
`report.cards`, so the function stays a pure writer of the facts it is given.

## Risks / Trade-offs

- **A reader may expect "headings / entries" like Lingvo.** We print one number
  with the word "Entries", which is that number's Lingvo meaning and avoids the
  ambiguity the user noted.
