## 0. Decide first

- [ ] 0.1 Resolve the open question: keep the row name as the builder's `#NAME`
      (this change), or derive a localized "{language} dictionary" label from the
      pair and demote `#NAME` to a subtitle (larger UX change)

## 1. Localize the language names

- [ ] 1.1 Add a QML helper mapping the metadata's English language name to a
      localized one via explicit `qsTr` literals, falling back to the input
- [ ] 1.2 Use it in the Dicts row sub-line and the By-Pair captions

## 2. Translations

- [ ] 2.1 Add the language names to the RU and JA catalogs (`app/i18n/*.ts`) and
      rebuild the `.qm`; mirror any Android strings if needed

## 3. Tests

- [ ] 3.1 A unit/UI check that a known name is localized and an unknown one is
      passed through

## 4. Validation

- [ ] 4.1 Build the app and check the Dicts list in EN and RU
- [ ] 4.2 Run the existing tests
