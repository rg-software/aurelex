## Why

Dictionary metadata is canonical English (see the `english-metadata` change), so
the Dicts list shows a Russian user `Russian/Russian` and the name the builder
chose. The language pair is the language-specific part of the row; showing it in
the app's active language makes the list read naturally for a Russian (or
Japanese) user without the converter shipping a translated description per
language.

## What Changes

- Show a dictionary's source/target language names in the app's active language
  when the app knows them, falling back to the metadata's English name.
- Apply the same translation to the By-Pair grouping captions.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-management`: the dictionary display-metadata requirement gains
  localization of the language names.

## Impact

- `app/main.qml` (the Dicts row and the By-Pair captions) and the i18n catalogs
  (`app/i18n/*.ts/.qm`, `values-ru`/`values-ja` as applicable) — the language
  names become translated strings.
- **Open question for the user**: the row's *name* (`#NAME`) is free text and
  cannot be translated by the app. Keep it as the builder's brand (this change),
  or derive a localized "{language} dictionary" label from the pair and demote
  `#NAME` to a subtitle. The latter is a larger UX change and would supersede
  this scope.
