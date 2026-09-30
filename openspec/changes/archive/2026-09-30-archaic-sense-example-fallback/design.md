## Context

`_sense_examples` (`kaikki-to-dsl.py:1837`) selects the one example a sense may
show: it keeps those that contain the headword and pass `_example_is_usable`,
which rejects a long-s `ſ`, a set of Early Modern/Middle English pronouns and
verb forms (`thou, thee, hath, doth, …`), and `Citations:` line. The rule is
about readability, and it is applied without regard to the sense's own register.

The grouping step (`_group_senses`) carries each sense's raw examples to the
renderer as a `(text, examples)` pair (`SenseEntry`); the renderer then filters
them with the word and its forms. The filter is where the era-blindness lives,
and the sense's tags are known when the pair is built but not when it is
filtered.

## Goals / Non-Goals

**Goals**

- A sense marked obsolete, dated or archaic shows an archaic example when it has
  no modern-readable one, instead of showing nothing.
- Modern senses are unchanged: an archaic example is still dropped there, and a
  readable one is preferred where both exist.

**Non-Goals**

- No change to which senses are kept or how their usage is marked.
- No change to the length bound or the one-example-per-sense cap.
- Bookkeeping (`Citations:`) examples are still dropped everywhere, even on an
  archaic sense.

## Decisions

### D1: Split the filter into bookkeeping and archaic

`_example_is_usable` mixed three rejections. It becomes two predicates:
`_example_is_bookkeeping` (the `Citations:` stub, dropped unconditionally) and
`_example_is_archaic` (long-s or the Early Modern/Middle English markers).
`_example_is_usable` is kept as their conjunction for the existing behavior and
tests, but the selection no longer routes through it.

### D2: Carry "archaic allowed" with the sense's examples

The `SenseEntry` payload gains a third field, a boolean that is true when the
sense carries one of the usage tags whose icon is `gd_tag_obsolete.svg`
(obsolete, dated, archaic). It is computed in `_group_senses` from the sense's
tags, travels beside the raw examples, and is passed to `_sense_examples`. This
keeps the tag information available at filter time without re-deriving it from
the rendered markup or storing the whole sense.

### D3: Readable first; archaic is a fallback, not a peer

`_sense_examples` first collects examples that show the word and are not
bookkeeping. It keeps the shortest of the modern-readable ones; only when there
are none and the sense allows it does it keep the shortest archaic one. The cap
and the length bound are unchanged, so the fallback can never multiply examples
or exceed the bound.

### D4: The tag set is the icon set

"Marked archaic" means the tags that render the usage icon (obsolete, dated,
archaic); keying off the icon mapping keeps the fallback aligned with what the
reader sees on the card, rather than inventing a second notion of archaic.

## Risks / Trade-offs

- **Some recovered examples are genuinely hard to read** (early spellings). That
  is the point of the trade: on an archaic sense the alternative is no example,
  and the fallback is limited to exactly those senses.
- **The payload tuple gains a field.** Small and internal; the two test helpers
  that unpack an entry are updated with it.
