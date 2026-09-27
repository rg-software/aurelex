## Context

See `proposal.md` — Why. Constraints that shape the approach:

- The engine renders only a fixed DSL tag set. There is **no inline-image tag**;
  the picture path is `[s]file.svg[/s]`, which `dsl.cc:830-840` turns into
  `<img src="bres://<dictId>/file.svg" style="max-width:100%">`. `.svg` is an
  accepted picture extension (`common/filetype.cc:80`).
- `bres://` is resolved by the app through `gd_get_resource`
  (`carve/gd_boundary.cc:667`) into `DslDictionary::getResource`, which serves
  arbitrary files from the dictionary's containing folder, its `.files/`
  directory, or its resource zip (`dsl.cc:1605-1620`). So an article can show a
  bundled image with no app-side resource change and no network.
- The engine emits one expander per article but one `.dsl_opt` span per
  `[*]…[/opt]` zone, and the injected handler toggles all zones of the entry
  (`dsl.cc:790-793`, `dsl.cc:1515`, `assets/scripts/gd-article-controls.js:50`);
  multiple per-sense zones already work.
- `[mN]` renders as a block `<div class="dsl_mN">` with only `padding-left` set
  (`article-style.css:476-515`) — no list marker exists.
- The engine gives an inline `<img>` no class and only `max-width:100%`, so any
  sizing/alignment must be app CSS keyed off the image's URL.
- The Material Symbols SVGs the request named are served as **Kotlin/Compose**
  from the `render/v1/…kt` endpoint and as Android vector XML from `…xml`;
  neither is HTML-usable. The plain SVG lives at
  `fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/<name>/default/24px.svg`
  and defaults to black (no `fill`), which is unreadable on a dark background.

## Goals / Non-Goals

**Goals:**

- Make the article shape already produced by the converter authoritative in
  `dictionary-conversion`, so the spec, not a doc, is the contract.
- Replace a fixed set of noisy tags with small inline icons that render offline
  from a vendored, deterministic icon set.
- Give every leaf sense a visible bullet, entirely dictionary-side.
- Keep the dictionary self-contained: no network at render time, byte-identical
  rebuilds.

**Non-Goals:**

- No engine change and no `patches/` entry; the only app change is one article
  stylesheet rule for inline icon sizing/alignment.
- Not every Wiktionary tag becomes an icon — only the agreed set (§D3). The rest
  keep the abbreviated text form or stay dropped as before.
- No per-theme icon variants, no interactivity, no tooltips on icons (the engine
  cannot attach `title`/`alt` text to a `[s]` image).
- No change to search, groups, audio, or import paths.

## Decisions

### D1. The layout the converter produces is specified as-is

The card layout, same-POS merging, transcription hoisting, card-wide audio
de-duplication, `[mN]` parent/child sense grouping, per-sense optional example
zone, and the card-level `See also` zone move from `docs/KAIKKI-CONVERSION.md`
into `dictionary-conversion` requirements, unchanged. This is a spec-addition
over existing behaviour, not a behaviour change; the doc stays as the user-facing
explanation.

*Why:* the renderer is already ahead of the spec and uncommitted; without this the
next editor cannot tell intended behaviour from accident.

### D2. Tag icons ride the `[s]…[/s]` picture path, with a vendored SVG set

A mapped tag emits `[s]gd_tag_<name>.svg[/s]` inline, which the engine renders as
a `bres://` image served from the dictionary's resource bundle.

*Alternatives rejected:*

- **The Google `render/v1/…kt` URLs as given** — they return Compose Kotlin
  source (and `…xml` returns Android vector XML); they are not images, and the
  `…svg` variant of that endpoint returns HTTP 400. Silently shipping dead icons.
- **Remote SVGs at all** — every article would need the network, breaking the
  offline guarantee and the deterministic build.
- **Material Symbols font glyph via a private-use codepoint** — the article
  WebView has no `@font-face` for the symbol font, and a PUA codepoint in a
  `.dsl` artifact is unreadable and unmaintainable.
- **Unicode characters** — ambiguous glyphs and no guaranteed font coverage.

The icon files are committed under `scripts/assets/kaikki-tag-icons/` and fetched
once from the `short-term/release` endpoint above. Each vendored SVG gets an
explicit neutral `fill` (see D8) and its intrinsic `width`/`height` retained.

### D3. Fixed icon set and tag mapping

| Tag(s) from `senses[].tags` | Icon file | Material symbol |
| --- | --- | --- |
| `countable` | `gd_tag_countable.svg` | `local_drink` |
| `uncountable` | `gd_tag_uncountable.svg` | `water_drop` |
| `initialism`, `abbreviation`, `acronym` | `gd_tag_initialism.svg` | `sell` |
| `obsolete`, `dated`, `archaic` | `gd_tag_obsolete.svg` | `account_balance` |

This supersedes the current policy for these tags: `countable`/`uncountable`
leave `_EN_SENSE_NOISE`, and `alt-of`/`alternative`/`form-of`/`initialism`/
`abbreviation`/`acronym` leave `_STRUCTURAL_SENSE_TAGS`. `alt-of`/`alternative`/
`form-of` stay in the structural drop set — an alternative-form sense gets **no**
marker, because its gloss already reads "Alternative spelling of …" and the
headword it names is linked instead (D10). The remaining structural tags
(`synonym(s)`, `ellipsis`, `clipping`) and noise tags (`transitive`,
`intransitive`, `not-comparable`) keep their current drop behaviour.

**Countability is shown only when it is the marked case.** Samples of the pinned
snapshot show that of English senses carrying a countability tag, most carry
*both* `countable` and `uncountable` (Wiktionary's "can be either", the default
for most nouns), and a minority carry exactly one. So a countability icon is
emitted only when exactly one of the two tags is present; when both are, neither
icon is shown. Emitting one icon per tag would put two glyphs on the majority of
noun senses, which is the noise this change exists to remove.

### D4. Icons carry the tag; one abbreviated text tag may still follow

For a sense, emit its mapped icons (in tag order, de-duplicated by icon), then at
most one abbreviated text tag from the first *unmapped*, non-noise tag. A sense
with no mapped tag is unchanged. Order within a sense:
`bullet · icons · text tag · gloss` (D5 for the bullet).

*Why:* keeps `(fig.)`, `(derog.)`, `(slang)`, `(regional)` readable as text while
the listed tags shed their parentheses; a sense carrying both gets an icon and a
text tag, which is the information the source actually holds.

When an iconised relation is also spelled out at the head of the gloss, the
wording is dropped so the icon does not say the same thing twice: the real
snapshot's initialism/abbreviation senses read "Initialism of gross domestic
product.", "Abbreviation of catapult.", "Acronym of …", and the initialism icon
already carries that. The phrase is removed only for the iconised relation tags
(`initialism`/`abbreviation`/`acronym`); a relation with no icon (a clipping, an
ellipsis) keeps its words. What remains is the headword the gloss names, which is
then linked (D10).

### D11. A transcription is not named when it is the dictionary's primary notation

`_record_transcription` previously prefixed the value with its notation name
(`IPA: /ɹʌn/`). The line always holds a transcription, so the name is redundant;
the primary notation (IPA for the English profile) is now emitted bare. A
secondary notation (`enPR`) keeps its name, because a bare enPR string is not
recognisably a different transcription system.

| Where | Before | After |
| --- | --- | --- |
| Primary (IPA) | `[com]IPA: /ɹʌn/[/com]` | `[com]/ɹʌn/[/com]` |
| Secondary (enPR) | `[com]enPR: wit[/com]` | unchanged |

### D5. The sense bullet is a literal character in the gloss text

Each leaf sense's text is prefixed with `•` (U+2022) inside its `[mN]` tag:
`[m1]• To move swiftly.[/m]`. A grouped parent heading (a sense that has
sub-senses under it) is not bulleted; its `[m2]` children are.

*Alternatives rejected:* app CSS `::before` on `.dsl_mN` — it would restyle every
DSL dictionary in the app, not just this one, and there is no way for a
dictionary to scope it. A literal `*` is impossible: the engine parses `*` as the
optional-zone tag.

*Trade-off accepted:* the bullet becomes part of the article text, so it is
indexed and copied along with the gloss. It is one visible, non-letter character
and the copy result is still readable.

### D6. Inline icon sizing and alignment is one narrowly-scoped injected rule

`EngineController`'s always-injected `plainCss` block (`EngineController.cpp:1145`,
the same block that carries the optional-parts expander override) gains one rule
scoped to the `gd_tag_` filename convention:

```css
.gdarticlebody img[src*="gd_tag_"] { height: 1.1em; vertical-align: -0.15em;
                                    background: transparent !important; }
```

The engine gives an inline `<img>` only `max-width:100%` and no class, so the URL
filename convention is the only stable hook. Injecting it rather than editing
`article-style.css` means it holds for every selectable display style
(classic/modern/lingvo/lingoes-blue), and it is deliberately **namespaced**: the
selector matches only images whose path contains `gd_tag_`, which only this
converter's dictionaries ship files for, so it cannot restyle any other
dictionary's content images. No generic `img`/`.dsl_m` rule is added or changed.

`background: transparent !important` is required because dark mode injects
`.gdarticlebody img { background: white !important; }`
(`EngineController.cpp:1206`), which would otherwise draw a white box behind the
transparent icons on the dark canvas. That rule ties on specificity with a bare
`img[src*="gd_tag_"]` and is injected *later*, so the selector is written as
`.gdarticlebody img[src*="gd_tag_"]` to out-specify it regardless of order.

### D7. Icons join the dictionary resource bundle

Icons are copied into the same resource output as audio —
`<name>.dsl.files.zip` by default (the reader's own first choice: it strips
`.dsl.dz` to form the base name, so `<name>.dsl.dz.files.zip` is only a
fallback), or `<name>.dsl.files/` with `--audio-layout dir`. The bundling gate
changes from "audio was requested" to "there is anything to bundle", so icons are
shipped even under `--no-audio`. The bundle stays deterministic: a fixed file set
with pinned bytes, written in sorted order.

### D8. Vendored SVGs carry a baked neutral fill

Because an `<img>` cannot inherit `currentColor` and one artifact serves both
light and dark articles, each icon's `path` is given an explicit mid-gray fill
(legible on both backgrounds) at vendoring time.

### D9. The about article carries an icon legend

The generated about card gains a short legend mapping each icon to its meaning.
The engine sets an inline icon's `alt` to its filename (no `title` is possible),
so the icon alone is not self-describing to a screen reader or a first-time
reader; the legend is the only place the meaning can be stated in the artifact.
This is extra about-card content beyond attribution, added deliberately.

### D10. Alternative/other-form senses link their base headword

For a sense carrying `alt_of` or `form_of`, the headword that entry names is
rendered as a `[ref]…[/ref]` link inside the gloss, so `swop`'s "Alternative
spelling of swap." carries a tappable `swap`. The gloss text is escaped first and
the link is inserted in place (the target is a plain word, so escaping leaves it
unchanged). The link is emitted only when the target is in the known-headword set
(`known`), matching the existing cross-reference guard, so no link points at an
entry the dictionary does not contain; a sample therefore links only targets it
has already emitted. `_cross_refs` reads record-level `synonyms`/`related`, not
`senses[].alt_of`/`form_of`, so the linked headword is not duplicated in the
card's cross-reference list.

*Alternative rejected:* keeping the "alternative of" icon (D3) — it restates what
the gloss already says and adds a second marker where a link is the useful thing.

### D11a. An optional zone closes with [/*], not [/opt]

The DSL reader nests nodes by tag name and silently drops a closing tag with no
matching opening tag (dsl_details.cc:747-765: `closeTag` scans the open stack
for the name; no hit and the whole block is skipped, only warning at `:786`).
`[*]` opens a node named `*`, and the reader's own supported-tag regex
(`dsl.cc:1332`) is `\[(|/)(p|trn|ex|com|\*|t|br|m[0-9]?)\]` — `opt` is not
in it and no `opt` opening tag exists, so `[/opt]` closed nothing. Every
following sense therefore nested inside the `[*]` span and collapsed with it.
The correct closer is `[/*]` (name `*`, matching the opening tag). This is the
format's rule, not a reader quirk: ABBYY's own Lingvo manual
(`documentation.help/ABBYY-Lingvo8/paragraph_form.htm`) writes the zone as
`[m1][*]@ … [/*][/m]`, and DSL closing tags always repeat the opening tag's name.
`opt` is not a tag name in the language. So the engine is right and the fix
belongs in the generator: emitting `[opt]` as the opener, or teaching the C++ an
`opt` alias, would both be deviations for syntax the format does not have.

*Why it read as a layout bug:* with a single card-level zone (the previous
design) the unclosed span simply ran to the end of the card, so the defect was
invisible. Per-sense zones made it visible: a later sense sat inside an earlier
sense's zone. This also affected the committed `aurelex-basic` smoke fixture.
### D12a. Group headings are numbered per part of speech

A heading that carries sub-senses is prefixed `1. `, `2. ` …, counted within its
part of speech and restarting for the next one; a sense with no sub-senses is left
bulleted but unnumbered, so a card with no groups is unchanged. The marker is
plain text inside the `[mN]` tag — the only place to put it, since the engine
gives `[mN]` no class hook and we do not patch the reader.

*Why:* `[m1]` is overloaded — it is a heading when the sense has children and an
ordinary sense when it does not — so the number is exactly the signal that tells
the two apart, and it makes the top-level sections of a long article scannable
(the bullet alone is not enough once a card runs to dozens of lines). Numbering
only group headings keeps it meaningful: on `work` the parents become 1./2./3.
while the ungrouped senses stay plain bullets.

### D12. A card with one record hoists its transcription too

Transcription hoisting keyed on `len(records) > 1`, so a one-record card placed
its transcription *under* the part of speech while a multi-record card with one
shared transcription placed it *above* - the same word rendered inconsistently by
an implementation detail. Hoisting now keys only on "the card has exactly one
distinct transcription" (`len(distinct_tr) == 1`), which is already what the spec
asks for; a card with differing transcriptions still keeps one per part of speech.

### D13. The language prefilter is a hint; the parsed record decides

`iter_records` prunes lines with a raw-text check for `"lang_code": "<code>"`
before JSON parsing, and the sample path relied on that check alone. A record of
another language can carry a *nested* `"lang_code": "<code>"` (a related word, a
sense's cross-reference), so it passed the substring test — an Old English `seam`
merged its gloss and IPA into the English `seam` article, and a Chinese `縣`
appeared as its own article. Two fixes: the prefilter now accepts either JSON
spacing (so it never rejects a real record), and the parsed `record["lang_code"]`
is checked before yielding, so the prefilter can only ever be too loose, not too
strict. The full-build path already re-checked and was correct; only the sample
path was affected.

### D14. Audio rides on the transcription line

The transcription line and the audio line were adjacent but separate, so "IPA next
to the audio" did not read as one group. They are now merged: each distinct
transcription takes the audio of the first record that carries it
(`/ɹʌn/  [s]...[/s]  [s]...[/s]`), and a part of speech with audio but no
transcription keeps a standalone audio line. Card-wide de-duplication is
unchanged, so each file still prints once. This holds for the hoisted and
per-POS cases alike, so they read the same.

### D15. A blank line separates each part of speech

Sections ran together (`[p]verb[/p]` ... `[p]noun[/p]` with no gap), which read as
one list. A blank line is now emitted before every part of speech except the
first. The preview renderer already tolerates the empty line.

The separator is emitted between blocks, tracked with a `first_pos_seen` flag
rather than "is `lines` non-empty": the earlier form put a blank after a hoisted
transcription and before the first part of speech, where nothing needs
separating. Note that a blank DSL line becomes an empty `<p></p>` (dsl.cc:759),
and the app stylesheet zeroes `.dsl_definition p` margin, so on device the gap
may be invisible rather than a large break — verify which marker gives the
intended separation.

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| Icon meaning is not self-evident (`water_drop` for uncountable, `local_drink` for countable, `account_balance` for obsolete) | The about-card legend (D9); the tags remain in the source data if the mapping is later revised |
| Screen readers get `alt="gd_tag_uncountable.svg"` (engine sets `alt` from the filename, no `title`) | About-card legend; documented limitation; acceptable because the icon is decorative and the gloss carries the meaning |
| Dark mode's DarkReader processes the icon images and may invert/dim them, and its `.gdarticlebody img { background: white }` would box them | The scoped rule forces a transparent background (D6); icon appearance in dark mode is verified on device, and the scoped rule is the only lever needed if DarkReader needs excluding |
| A fixed fill is a compromise in one of the two themes | Mid-gray chosen to pass on both; revisit only if it reads poorly |
| The app CSS change leaks onto other dictionaries | Selector is namespaced `img[src*="gd_tag_"]`; nothing else ships `gd_tag_*` files; a task asserts no generic `img`/`.dsl_m` rule is added |
| Several mapped tags on one sense produce a run of icons | Rare in practice; a cap can be added later without a spec change |
| The bullet pollutes article text / full-text index | Accepted in D5; one non-letter character, and search for the gloss words is unaffected |
| Icons are shipped inside every generated dictionary, duplicating ~2 KB per build | Negligible; keeps dictionaries self-contained and offline |
| Rebuild-shape change breaks consumers of a previously generated dictionary | Only `examples/kaikki-sample/` is committed; users regenerate. Noted in the proposal as an output-shape change |

## Migration Plan

Regenerate `examples/kaikki-sample/` and update `docs/KAIKKI-CONVERSION.md`; the
vendored icon set is added to the repository. Rollback is reverting the commit —
the icon set is inert if unused, and `--no-tags-icons` (if a flag is added) or a
revert restores the prior output. No data migration: dictionaries are generated
artifacts.

## Open Questions

- Exact mid-gray for the baked fill (cosmetic; changeable without touching specs
  or tasks).
- Whether `acronym` belongs with the initialism icon (D3 groups it) or should
  stay dropped — grouped now, trivially changed.
