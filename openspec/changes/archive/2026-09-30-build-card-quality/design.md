## Context

`build()` groups source records into cards by comparing each record's `word` to
the previous one (`kaikki-to-dsl.py:2339`), so only *consecutive* records merge.
The snapshot is not word-sorted — a probe measured 147,235 non-ascending word
transitions in the first 400k records — so a headword whose records are split
across the file is emitted twice, as seen for `winter`, `no`, and 45 others.
Separately, a record whose senses carry no gloss renders a card with only a part
of speech; 1,101 such cards exist, 47 of them the second copy of a split
headword. Cross-references are filtered against `known`, the set of all candidate
headwords, so every candidate currently gets a card and no link ever dangles —
which is exactly what breaks if cards start being omitted.

## Goals / Non-Goals

**Goals**

- One article per indexed headword, regardless of snapshot ordering.
- No definition-less article, except where one is needed to satisfy a link.
- No link to a headword the dictionary does not contain.
- Report the three counts.

**Non-Goals**

- No change to which records are candidates for indexing (`is_lexical`,
  `is_inflected`) or to the per-word audio cap.
- Not sorting the snapshot or buffering all records; the merge is bounded to the
  headwords that are actually split.

## Decisions

### D1: Detect split headwords in the existing selection pass

The full build already makes one selection pass over the snapshot to build the
`known` set (`select_headwords`). It is extended to also return the headwords
whose records begin more than one contiguous run: while streaming candidate
headwords, a word that starts a run it has started before is split. This costs a
set membership test per candidate and nothing else, and reuses the pass that is
already there.

### D2: Merge split headwords by deferring only their records

In the render pass, a record whose headword is split is set aside into a per-word
list instead of being rendered with the current group. After the stream, each
deferred headword is rendered once from all its records, in first-seen order.
Only split headwords' records are held (a few dozen here), so memory stays
bounded and the common case is unchanged.

### D3: Collect cards, then filter, then assemble

`emit` currently appends the rendered card straight to `out_lines`. It instead
appends `(headwords, body, word, record_count)` to a list; once every card is
rendered, the list is filtered and only then flattened into the dictionary text.
This is what makes the omission in D4 possible without re-rendering, and lets the
report count what was kept and dropped. The list holds the same strings
`out_lines` already held, so memory is unchanged.

### D4: A card is definition-less when it has no gloss

A rendered card carries a definition when its body contains a gloss heading
(`[m1]`, `[m2]`, …). A card without one is omitted **unless** another card links
to its headword (D5), in which case it is kept so the link resolves. This drops
the 1,054 standalone engine stubs and leaves the merged cards (which carry their
glosses) in place.

### D5: Keep a definition-less card that is referenced

The set of linked headwords is read from the rendered bodies (`[ref]…[/ref]`,
un-escaped back to the raw headword). A definition-less card whose headword is in
that set is kept. This resolves the tension between pruning stubs and the
existing "no link to an absent headword" requirement without a second render
pass: nothing is dropped that something points at.

### D6: Unlink any reference that still has no target

A candidate headword can render no body at all and so never become a card, yet
still sit in `known` and be linked. After filtering, every remaining `[ref]X[/ref]`
whose target is not an emitted headword is rewritten to plain `X` and counted.
This is the final guarantee behind the no-dangling-link requirement.

### D7: Report the counts

The report gains the number of split headwords merged, definition-less cards
omitted, and references unlinked, so a run says what it pruned rather than
silently shrinking the dictionary.

## Risks / Trade-offs

- **The output for a snapshot changes.** The dictionary gains a guarantee and
  loses ~1,100 empty cards; this is a behaviour change, not a regression, and
  rebuild determinism is unaffected.
- **A stub retained only for a link is still a stub.** That is deliberate: the
  alternative is a broken link. It is rare (only where something points at a
  definition-less headword) and is not separately counted, since the drop count
  already tells the story.
