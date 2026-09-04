## Why

The Dicts tab currently shows each dictionary's raw file path as its secondary
line, which is noisy and meaningless to the user. The app knows more useful
metadata — the source/target language pair and the on-disk size — and the
dictionaries would be far easier to scan when grouped by language pair. As the
library grows, a flat alphabetical list loses the "which language am I looking
at" signal entirely.

## What Changes

- Replace the secondary line (file path) on each dictionary row with:
  **SourceLanguage/TargetLanguage** plus an approximate **size** in MB/GB
  (e.g. `English/Russian · 145 MB`). When a dictionary is still being indexed
  and its size isn't known yet, show the pair but omit the size until indexed.
- Add a **"By Pair"** toggle button next to **Add dictionaries** (behaves like
  a checkbox, default off):
  - **Off**: dictionaries sorted alphabetically by name (current behaviour).
  - **On**: dictionaries are grouped under color-highlighted caption rows, one
    per language pair (Source/Target), sorted alphabetically by pair; within a
    pair, dictionaries are sorted alphabetically by name.
- Unknown source/target languages are shown as `?` (or "Unk"/"Und").
- Each pair caption row has a **Remove** button that removes every dictionary
  having that pair.
- **Conditional, small scope** — multi-select batch removal: a **RemoveSelected**
  button (disabled by default) next to By Pair. Tapping a dictionary toggles its
  selection (row highlight); with ≥1 selected the button enables; tapping it
  removes all selected dictionaries. If selection becomes empty the button
  returns to disabled.

## Capabilities

### New Capabilities

- `dictionary-management` (existing, modified below): the change adds
  per-dictionary display metadata (language pair, size) and a grouped
  presentation + multi-select removal in the Dicts tab.

### Modified Capabilities

- `dictionary-management`: the dictionary list's secondary information changes
  from the source file path to the language pair + approximate size; adds an
  optional By-Pair grouping view with per-pair removal, and a batch
  (multi-select) remove action. These are user-visible behaviour changes to the
  dictionary-management capability.

## Impact

- `carve/goldendict.h`, `carve/gd_boundary.cc`: extend the per-dictionary
  metadata the app can query — add language pair (Source/Target, as human
  names) and an approximate size. Likely a new `gd_dict_meta(index, ...)`
  accessor returning lang-from/lang-to names and a size hint, keeping the
  existing `gd_dict_info` (name/source) intact for internal paths.
- `app/EngineController.{hpp,cpp}`: `dictionaries` list items gain
  `langFrom`, `langTo`, `sizeBytes` (computed off-thread, e.g. by stat-ing the
  staged files; hidden until FTS index built if unknown).
- `app/main.qml` (Dicts tab): row secondary line, By Pair toggle, pair caption
  rows with Remove, and the optional multi-select + RemoveSelected button.
- `app/` sorting logic for the pair grouping (or done in QML).
- No change to `engine/` upstream sources; boundary only.
- Size source: stat the dictionary's staged files (primary + resource files);
  `getWordCount`/`getArticleCount` are counts, not bytes, so on-disk size is
  used for "approx MB/GB".

## Open Question (recorded as an assumption)

- The "RemoveSelected" multi-select feature is included on the assumption it is
  a small QML-side change (a selection set + reuse of the existing
  `removeDictionary` per index). If implementation shows it is not small, it can
  be descoped in design without changing the rest.