## Context

``_link_form_targets`` (`kaikki-to-dsl.py:482`) iterates a sense's ``alt_of`` and
``form_of`` entries in turn and, for each, wraps the first occurrence of the
target word in the gloss with ``[ref]…[/ref]``. When the same target is named by
both relations, the second pass matches the ``ho`` inside the ``[ref]ho[/ref]``
the first pass just inserted (its neighbours, ``]`` and ``[``, are non-word
characters, so the ``(?<!\w)…(?!\w)`` guard does not stop it) and wraps it again,
yielding ``[ref][ref]ho[/ref][/ref]``.

That malformed link also slips past ``unlink_absent_refs`` (`:1627`): its pattern
captures ``[ref]ho`` as the target text, which is not an emitted headword, so it
substitutes the capture — which itself contains ``[ref]`` — leaving a link in
place. Two cards in the full build (`ho ho`, `ho ho ho`) are affected; `ho` is a
real headword, so the correct rendering is a single link.

## Goals / Non-Goals

**Goals**

- A related headword named by any number of relations is linked exactly once.
- Unlinking an absent target can never leave ``[ref]`` markup behind.

**Non-Goals**

- No change to which targets get links (the known-headword guard is unchanged).
- No change to the cross-reference list.

## Decisions

### D1: De-duplicate targets before wrapping

Collect the distinct target words from ``alt_of`` and ``form_of`` (and within
each list) first, then wrap each once. The double wrap is only reachable when the
same target is seen twice, so de-duplication removes it at the source. Distinct
targets cannot nest in practice: the word-boundary guard means one target is not
matched inside another's wrapped text.

### D2: Make the unlink safety net markup-free

``unlink_absent_refs`` strips ``[ref]``/``[/ref]`` from the text it substitutes,
so even a nested or otherwise malformed link is reduced to plain text rather
than a link with its outer layer removed. This is defence in depth behind D1.

## Risks / Trade-offs

- **A gloss that genuinely wants two links to the same word** would now get one.
  A relation gloss names the word once; a second link to the same article adds
  nothing, so this is the intended reading.
