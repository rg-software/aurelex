## Context

`render_card` emits the part of speech verbatim: `[p]{escape_dsl(pos)}[/p]`
(`kaikki-to-dsl.py:2080`), where `pos` is the source's code (`noun`, `verb`, …).
Sense tags are abbreviated through `profile.sense_short_tags` with a raw-tag
fallback (`:684`). The profile already carries `short_tags` for grammatical form
labels, and Russian is configured with the English sense abbreviations
(`sense_short_tags=_EN_SENSE_SHORT`). The Russian edition supplies Russian
glosses but English `pos`/tags, so the dictionary is half-localized.

## Goals / Non-Goals

**Goals**

- A part of speech and a sense tag show in the dictionary's language when the
  profile provides a label.

**Non-Goals**

- Not changing the grammatical *form* abbreviations for Russian (still the
  conventional Latin `gen.`, `sg.`, …) — a separate, taste-driven choice.
- Not translating tags the profile does not map; an unmapped tag still falls back
  to its source text.

## Decisions

### D1: `pos_labels`, defaulting to the raw code

`LangProfile` gains `pos_labels: Dict[str, str]`, empty by default so English is
unchanged; the render site uses `profile.pos_labels.get(pos, pos)`. This mirrors
how `short_tags` already localizes forms.

### D2: Russian labels live in the profile

The Russian profile gets `pos_labels` (сущ., гл., прил., нареч., мест., числ.,
предл., союз, част., межд., фразеол., собств., сокр., звукоподр.) and its own
sense abbreviations (разг., перен., жарг., устар., арх., ист., шутл., ирон.,
вульг., оскорб., пренебр., редк., лит., поэт., мед., юр., неол., диал., обл.,
ласк., эвф., …), replacing the reused English set. An unmapped tag still falls
back to its English source text, which is the honest default.

## Risks / Trade-offs

- **An unmapped tag shows English.** Acceptable and visible; the common tags are
  mapped, and adding one is a one-line entry.
- **Russian wording is a judgement call** (e.g. нареч. vs нар.). The entries are
  in one table, easy to review and adjust.
