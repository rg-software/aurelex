## 1. Vendored icon set

- [x] 1.1 Add `scripts/assets/kaikki-tag-icons/` containing the four sense icons (`countable`, `uncountable`, `initialism`, `obsolete`), fetched once from the Material Symbols `short-term/release` endpoint at 24px and committed
- [x] 1.2 Give each icon a baked neutral mid-gray `fill` so it is legible in both light and dark articles (the source SVGs default to black)
- [x] 1.3 Record the icon set's provenance and license (Material Symbols, Apache-2.0) in the assets folder, and reference it from the tool's attribution output

## 2. Converter — sense rendering

- [x] 2.1 Add the tag→icon table (countable→`local_drink`, uncountable→`water_drop`, initialism/abbreviation/acronym, obsolete/dated/archaic) and drop those tags from the noise drop set; keep alt-of/alternative/form-of in the structural drop set (no marker for an alternative-form sense)
- [x] 2.2 Emit a sense's mapped icons inline (`[s]gd_tag_<name>.svg[/s]`), in tag order, de-duplicated by icon; keep at most one abbreviated text tag from the first unmapped, non-noise tag; order the sense as bullet · icons · text tag · gloss
- [x] 2.3 Prefix each leaf sense with a literal bullet (U+2022); do not bullet a sense that heads sub-senses
- [x] 2.4 Keep the per-sense optional example zone as the layout of record (one example per sense, no empty zone, `See also` as the single card-level zone)
- [x] 2.4a Close every optional zone with the reader-recognised `[/*]` (`[/opt]` matches no opening tag and left later senses inside the zone)
- [x] 2.5 Link the headword a form-of/alt-of sense names inside its gloss as a `[ref]`, guarded by the known-headword set, so `swop` links `swap`
- [x] 2.6 Drop the "Initialism of"/"Abbreviation of"/"Acronym of" wording an iconised relation already carries, keeping the rest of the gloss (which is linked)
- [x] 2.7 Drop the redundant `IPA:` label from the primary transcription; keep the label for a secondary notation (enPR)
- [x] 2.8 Hoist the transcription above the first part of speech whenever the card has a single distinct transcription, including a one-record card
- [x] 2.9 Put the audio on the transcription line (a standalone line when a part of speech has audio but no transcription)
- [x] 2.10 Separate consecutive parts of speech with a blank line (strictly between them: none before the first or after a hoisted transcription)

## 3. Converter — language filter and bundling

- [x] 3.1 Verify the parsed record's language in `iter_records` (the raw-text prefilter is a hint that a nested `"lang_code"` can defeat) and tolerate either JSON spacing, so a sample cannot admit another language's records
- [x] 3.2 Copy the vendored icons into the dictionary resource bundle alongside audio, using the existing zip/dir layout, and keep the bundle byte-identical across rebuilds (sorted entries, pinned bytes)
- [x] 3.2a Name the resource bundle by the reader's canonical first choice, `<name>.dsl.files.zip` / `<name>.dsl.files/` (the reader strips `.dsl.dz` to form its base name, so `<name>.dsl.dz.files.zip` is only a fallback)
- [x] 3.3 Change the bundling gate so the resource bundle is written when icons are emitted even under `--no-audio`
- [x] 3.4 Add the icon legend to the generated about card, mapping each icon to its meaning

## 4. Converter — preview

- [x] 4.1 Render a `[s]…\.svg[/s]` icon reference in the preview HTML as an inline image (or labelled chip) instead of the audio note glyph, keeping the preview's tag balance

## 5. App — inline icon styling

- [x] 5.1 Add the `.gdarticlebody img[src*="gd_tag_"]` rule (height ≈ text height, matching vertical alignment, `background: transparent !important`) to the always-injected `plainCss` in `EngineController.cpp`; add no generic `img`/`.dsl_m` rule and edit no shared stylesheet

## 6. Tests

- [x] 6.1 Unit-test the tag policy: each mapped tag yields its icon, `countable`/`uncountable` no longer dropped, structural relation tags now iconised, register tags still abbreviated text, noise tags still dropped, and an icon coexisting with a text tag
- [x] 6.2 Unit-test bullets: sibling senses bulleted, a sub-sense heading not bulleted
- [x] 6.3 Unit-test bundling: icons present in the resource bundle with `--no-audio`, and two builds of the same inputs are byte-identical
- [x] 6.4 Update the preview tests for icon rendering, and keep the DSL-escape/tag-balance coverage green
- [x] 6.5 Unit-test the form-of/alt-of link: the target is linked when it is a known headword, left plain when it is not or when it is the word itself; and an alternative-form sense renders no marker
- [x] 6.6 Unit-test that an iconised relation's wording is dropped (and a non-iconised relation's wording is kept), and that the primary transcription is unlabelled while a secondary notation keeps its label
- [x] 6.7 Unit-test that a sample excludes another language's record even when its raw line carries a nested source-language marker, and that a one-record card hoists its transcription above the part of speech
- [x] 6.8 Unit-test that audio rides the transcription line (and stands alone without one), and that a blank line separates only consecutive parts of speech (not before the first or a hoisted transcription)
- [x] 6.9 Unit-test optional-zone nesting: no sense sits inside a zone, every `[*]` is closed by `[/*]`, and `[/opt]` is never emitted

## 7. Docs and committed example

- [x] 7.1 Rewrite the layout/tag/example sections of `docs/KAIKKI-CONVERSION.md` for the icon set, the bullet, the offline bundling, and the about-card legend
- [x] 7.2 Regenerate `examples/kaikki-sample/` from the fixture

## 8. Verification

- [x] 8.1 Run the full converter test suite (`python -m unittest discover -s scripts/tests`) and a real-data spot check (e.g. `work`) to confirm icons and bullets read correctly
- [ ] 8.2 On device: sense icons render inline in light and dark mode with no background box, and the resource bundle resolves them with no network
- [ ] 8.3 On device: an article from a dictionary that emits no sense icons has its images rendered unchanged
