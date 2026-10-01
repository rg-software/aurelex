## Context

The Dicts row shows `dictData.name` (`#NAME`) and, beneath it, `fmtSubLine` =
`langFrom/langTo · size` (`app/main.qml:234`, `:1762`). `langFrom`/`langTo` come
from `gd_dict_meta` — the DSL `#INDEX_LANGUAGE`/`#CONTENTS_LANGUAGE`, now English
after the `english-metadata` change. The By-Pair captions use the same strings
(`fmtPair`). The app's own i18n lives in the Qt catalogs and Android
`values-*/strings.xml`.

## Goals / Non-Goals

**Goals**

- The language pair reads in the user's UI language.

**Non-Goals**

- Not translating `#NAME`: it is free text the builder chooses; the app cannot
  translate arbitrary text. (It could show a derived localized label instead — a
  separate UX decision, see the open question.)
- Not changing the metadata the converter emits (it stays canonical English).

## Decisions

### D1: A small name map with `qsTr` on literals

A QML helper maps the English language name to a localized one via explicit
`qsTr("English")`, `qsTr("Russian")`, … entries — explicit literals so `lupdate`
extracts them — and returns the input unchanged for an unknown name. Used by both
the row and the By-Pair captions.

### D2: The language names enter the catalogs

Each name on the map is added to the RU and JA catalogs as a translation unit, as
the localization rule requires for any new user-visible English string. The
supported set is small (the languages we ship dictionaries for) and grows with
them.

## Risks / Trade-offs

- **A dynamic `qsTr` would not be extracted.** Using explicit literals avoids
  that; the cost is a map that must list each language, which is the same table
  the converter keeps.
- **The name stays `#NAME`.** If the user wants a Russian dictionary *name*, the
  builder sets a Russian `--title`; but that also becomes the `About <title>`
  headword, which is why full name localization pulls in the description
  (rejected as P2). See the open question in the proposal.
