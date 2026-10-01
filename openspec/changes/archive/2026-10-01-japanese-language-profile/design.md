## Context

The profile object is the only per-language surface, so all of this is a data
change plus two renderer rules that were English-shaped.

## Decisions

### D1: Readings stay in the forms line, labelled `読み`

Japanese readings (`ショウ`, `あお`) arrive in `forms[]`, not in `sounds[]`, so
they cannot ride the pronunciation line without a new profile concept. They are
kept where they are and labelled as readings (`読み, 呉音, 常用`), which is where a
reader looks and what the existing renderer already does for forms.

### D2: Conjugation-class tags drop from the label, not from the form

`sa-row`, `godan`, `ichidan` and friends name the conjugation class; they appear
on almost every inflected form and would repeat on each. They are simply left out
of `form_tags` (the label whitelist), so the form still qualifies — only its
label is the conjugation (未然形, 連用形, …). Putting them in `form_noise_tags`
would have dropped the forms themselves, since the blocklist drops a form that
carries any noise tag.

### D3: CJK substring matching is limited to CJK headwords

A generic "headword as substring" rule would let English `run` match inside
`brunch`. The fallback therefore applies only when the headword itself contains a
CJK character, where there is no word boundary to match against anyway.

### D4: `has_audio` gates the archive, not the article

When the profile says the language has no recordings, `build` treats it as
`--no-audio` (no archive downloaded, no audio planned) and `prefetch-audio`
refuses. The article is unaffected; there was simply nothing to fetch.

## Risks / Trade-offs

- **A short CJK headword matches loosely.** `は` occurs inside many words, so
  substring matching qualifies examples generously. That is the honest behaviour
  for a language without word breaks; a real morphological tokenizer is out of
  scope.
- **Unmapped sense tags still fall back to English** (e.g. a rare `Germany`
  context label). The map covers everything common in the snapshot.
