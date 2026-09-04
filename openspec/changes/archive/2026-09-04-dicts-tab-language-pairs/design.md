## Context

The Dicts tab shows each dictionary as name + file path. The engine exposes
per-dictionary language metadata (`Dictionary::getLangFrom()/getLangTo()`, which
decode to human names via `LangCoder::decode`) and the app can stat the staged
files for an approximate on-disk size. The carve boundary currently returns only
name + file (`gd_dict_info`); the app's `dictionaries` list carries `name` and
`source` per row.

See proposal.md for motivation; the delta spec defines the behaviour contract.

## Goals / Non-Goals

**Goals:**
- Show Source/Target language + approximate size instead of the file path.
- Add a By-Pair grouping toggle with per-pair captions + per-pair removal.
- Add multi-select + RemoveSelected (small, QML-side).

**Non-Goals:**
- No change to how dictionaries are imported/scanned/indexed.
- No change to lookup/groups/FTS behaviour — only the Dicts presentation.
- No changes to `engine/` upstream sources (boundary-only additions).

## Decisions

### D1. Expose language pair + size via a new boundary accessor
Add `gd_dict_meta(int index, char* lang_from, int lang_from_size, char* lang_to,
int lang_to_size, long long* size_bytes)` (or a small struct-returning call) in
`goldendict.h`/`gd_boundary.cc`:
- `lang_from`/`lang_to`: human names from `LangCoder::decode(getLangFrom()/
  getLangTo())`; empty when unknown (the app renders `?`).
- `size_bytes`: computed by the app by summing the file sizes of the
  dictionary's staged source files (the `source` path plus sibling resource
  files), NOT engine counts — the user asked for "approx size in MB/GB".
  Alternative considered: engine `getWordCount`/`getArticleCount`; rejected
  because those are article/word counts, not byte sizes.

### D2. Size hidden until indexed
`EngineController` already tracks `ftsIndexState` per dict (0 built / 1
missing). The row renders the size only when the dict's FTS index is built
(state 0); otherwise it shows the pair only. Rationale: a size computed from a
partially-staged/being-indexed dictionary would be misleading; the user asked to
omit it until indexed.

### D3. Sorting/grouping
- Flat mode (By Pair off): sort the `dictionaries` list alphabetically by name.
- By-Pair mode: group by `langFrom|langTo` (rendering unknown sides as `?`),
  sort pairs alphabetically, sort dictionaries within a pair alphabetically by
  name. Implement as a QML-side `ListView` with sections (section.property =
  pair, section.criteria = value) OR by producing a grouped `QVariantList`
  from `EngineController`. Prefer QML `ListView.section` — no controller change,
  keeps sorting in one place.
  - Unknown-pair dictionaries share a single `?/?` (or "Und") section.

### D4. Per-pair and multi-select removal
- Per-pair Remove: for the caption's pair, iterate the grouped dicts and call
  the existing `EngineController::removeDictionary(index)` for each.
- Multi-select: QML keeps a `Set`/list of selected dict indices; tapping a row
  toggles membership (row highlighted). A `RemoveSelected` button is enabled
  when the selection is non-empty; tapping removes each selected index via the
  same `removeDictionary`, then clears the selection. Because `removeDictionary`
  already deletes staged files + indexes, batch removal reuses it (small).

### D5. UI layout (Dicts tab)
Row secondary line becomes `Source/Target · 145 MB` (or just `Source/Target`
while indexing). Toolbar row: `Add dictionaries`, `By Pair` (toggle button,
highlighted when active), `RemoveSelected` (disabled when no selection). Pair
caption rows are color-highlighted Labels with a trailing Remove ToolButton.

## Risks / Trade-offs

- [Language names may be long / localized] → elide the row; keep pair caption
  short (`En/Ru` style if names long) — decide at implementation; spec only
  requires human names.
- [Per-pair Remove could delete many dicts] → confirm via the existing
  remove-confirmation dialog before the batch.
- [`RemoveSelected` scope creep] → it reuses `removeDictionary`, so it is small;
  if it proves non-trivial, it can be dropped without affecting the rest.

## Migration Plan

No persisted state. Existing dictionaries gain metadata on next refresh
(`refreshDictionaries` fills lang/size fields). No data migration.

## Open Questions

- Exact pair-caption label format when a side is long (e.g. "English/Russian"
  vs "En/Ru") — defer to implementation; spec allows human names and `?`.
