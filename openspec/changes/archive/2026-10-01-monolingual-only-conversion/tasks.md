## 1. Spec reconciliation

- [x] 1.1 Remove the bilingual "Language-pair selection" and "Article content" requirements; add monolingual "Language selection" and "Article body"

## 2. Framing

- [x] 2.1 Fix the tool's help epilog so it states the gloss language is the data edition's language (use the edition for the language you want)
- [x] 2.2 Update `docs/KAIKKI-CONVERSION.md`'s monolingual note to name the edition/gloss-language rule and how to build another language (its own edition)

## 3. Future translation plan

- [x] 3.1 Record the translation-dictionary plan: candidate sources (BabelNet, Tatoeba, WordNet / Open Multilingual WordNet) with coverage and license, and the sense-alignment requirement
- [x] 3.2 Add a backlog bullet in `docs/DEVELOPMENT.md` pointing at that plan

## 4. Validation

- [x] 4.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 4.2 Run `openspec validate monolingual-only-conversion --strict` and resolve any findings
