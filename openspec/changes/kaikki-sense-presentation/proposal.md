## Why

The converter's *output shape* — how a kaikki record becomes a DSL article — is
not specified. `dictionary-conversion` only fixes the high-level contract (base
forms, article contains POS/glosses/examples/forms, bounded audio, provenance,
determinism); every layout decision made so far (same-POS merging, transcription
hoisting, parent/child sense grouping into `[mN]`, the tag policy, the per-sense
example zone) lives only in `docs/KAIKKI-CONVERSION.md` and the code. A working
tree of uncommitted renderer changes is already ahead of the spec, so the next
person has nothing authoritative to build against.

At the same time the rendered senses are hard to read: register/grammar tags
(`(uncountable)`, `(obs.)`, `(fig.)`) are mixed into the gloss text as noise, and
sibling senses are only distinguished by indentation, so a list of definitions
reads as a paragraph. Making common tags small inline icons and giving each sense
a bullet removes most of that noise without losing the information.

## What Changes

- **Specify the article layout the converter already produces**: a card is
  POS → forms → senses; records sharing a POS merge into one block; a card-wide
  transcription is hoisted above the first POS; audio is emitted once, under the
  first POS that references it; a wiktextract `glosses[]` split on `:` becomes a
  `[m1]` parent heading with `[m2]` sub-senses; each sense carries its own
  `[*]…[/opt]` optional zone holding at most one example; a single card-level zone
  holds `See also` cross-references.
- **Specify the sense-tag policy**: structural tags (`alt-of`, `form-of`,
  `initialism`, …) and unmarked-case tags (`countable`, `transitive`) are
  currently dropped, and at most one register/context tag survives, abbreviated.
- **Add tag icons**: a fixed set of common tags renders as small inline SVG icons
  instead of parenthetical text — `countable`, `uncountable`,
  initialism/abbreviation, and obsolete/dated/archaic. The icon files are
  vendored in the repository and bundled into each dictionary's resource bundle,
  so articles stay offline and self-contained; tags outside the set keep the
  abbreviated text form. An alternative/other-form sense gets no marker.
- **Link related headwords**: an alternative/other-form sense links the headword
  it names inside its gloss (`swop` → "Alternative spelling of *swap*"), so
  tapping opens that article; the link is emitted only when the dictionary
  contains the headword.
- **Drop wording the markers already carry**: an initialism/abbreviation/acronym
  gloss drops the "Initialism of …" phrase the icon conveys, and a transcription
  line drops its redundant `IPA:` label (a secondary notation keeps its name).
- **Fix two faults found reviewing a sample build**: a one-record card now hoists
  its transcription above the part of speech like every other card, and the
  sample build no longer admits records of another language (an Old English
  `seam` was merging into the English one, and a Chinese `縣` appeared at all)
  because the raw-text language prefilter is now backed by a check of the parsed
  record.
- **Add a sense bullet**: each leaf sense is prefixed with a literal bullet so
  sibling definitions are visually separated. **BREAKING** for the article shape
  of previously generated dictionaries (not for any persisted app API).
- **App**: an inline sense icon in an article renders legibly — sized to and
  aligned with the surrounding text — rather than as a full-size block image.
- **Preview and docs**: the preview renders tag icons as images, and
  `docs/KAIKKI-CONVERSION.md` describes the icon set and bullet.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-conversion`: adds requirements for the rendered article layout,
  the sense-tag policy, per-sense example zones, and sense markers (tag icons
  plus the sense bullet), and states that the icon set ships with the output.
- `lookup`: adds a requirement that an inline sense icon referenced by an article
  is rendered as a legible inline image sized to the article text.

## Impact

- `scripts/kaikki-to-dsl.py` — sense rendering (tag icons, bullets), icon
  vendoring/bundling, preview rendering, resource packaging.
- `scripts/tests/test_kaikki_to_dsl.py` — layout, tag-policy and marker tests.
- New vendored SVG icon set (repository path decided in design).
- `app/EngineController.cpp` — one `img[src*="gd_tag_"]`-scoped rule in the
  always-injected article CSS for icon sizing, alignment and dark-mode
  background (no engine/`patches/` change, no shared stylesheet edit).
- `docs/KAIKKI-CONVERSION.md`, `examples/kaikki-sample/` — regenerated.
- `openspec/specs/dictionary-conversion/spec.md`,
  `openspec/specs/lookup/spec.md` — requirement deltas.
