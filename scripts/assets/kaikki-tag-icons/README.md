# kaikki-tag-icons

Small SVG icons with which `scripts/kaikki-to-dsl.py` marks common Wiktionary
sense tags in the dictionary it generates (countable, uncountable,
initialism/abbreviation, obsolete/dated/archaic). See
`docs/KAIKKI-CONVERSION.md` for how they are emitted.

## Provenance

Each file is a Material Symbols (Outlined) icon, fetched once at 24px from:

```
https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/<symbol>/default/24px.svg
```

| File | Material symbol | Meaning in the article |
| --- | --- | --- |
| `gd_tag_countable.svg` | `local_drink` | countable |
| `gd_tag_uncountable.svg` | `water_drop` | uncountable / not countable |
| `gd_tag_initialism.svg` | `sell` | initialism / abbreviation / acronym |
| `gd_tag_obsolete.svg` | `account_balance` | obsolete / dated / archaic |

Alternative/other-form senses (`alt_of`/`form_of`) have no icon: the gloss already
reads "Alternative spelling of …", and the headword it names is linked instead.

The only change from the source files is an added `fill="#7a828c"` on the path:
the engine renders a DSL `[s]icon.svg[/s]` as a bare `<img>` that cannot inherit
the article's text colour, so the icon carries a neutral mid-gray that is legible
on both light and dark article backgrounds.

## License

Material Symbols are Copyright Google LLC and licensed under the Apache License,
Version 2.0 — https://www.apache.org/licenses/LICENSE-2.0. The icon set is
redistributed here (and bundled into each generated dictionary) under that
license; the converter's attribution output points at this file.
