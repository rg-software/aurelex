## 1. Manifest

- [x] 1.1 Add an optional localized-names map to a catalog entry, `name` staying the fallback; document it in `docs/REMOTE-CATALOG.md`
- [x] 1.2 Parse it in `RemoteCatalog`, exposing the name for a given UI language (falling back to `name`)

## 2. App

- [x] 2.1 Show the active-language name in the catalog pane
- [x] 2.2 For an installed dictionary, prefer its catalog entry's active-language name in the Dicts row, falling back to the dictionary's own name

## 3. Tests

- [x] 3.1 A malformed/absent map falls back to `name`
- [x] 3.2 An entry with a name for the active language selects it; another language selects `name`
- [x] 3.3 An installed catalog dictionary resolves to its entry's localized name; a folder import keeps its own

## 4. Validation

- [ ] 4.1 Build the app and check the catalog and the Dicts list in EN and RU (needs an on-device build)
- [x] 4.2 Run the existing app tests (`catalog_test` passes, including the new checks)
