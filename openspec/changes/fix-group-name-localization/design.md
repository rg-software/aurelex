# Design: fix-group-name-localization

## Context

Two independent defects, found together because a user saw both at once. See
`proposal.md` for the motivation; the specs carry the requirements.

**Where the group name comes from.** `gd_group_info` returns the built-in group's
name as a C string (`carve/gd_boundary.cc:1036`: `const string n = "All";`), and
`rebuildGroups` constructs it as `QStringLiteral( "All" )`
(`carve/gd_boundary.cc:232`). The carve links no translation catalog, so that
name is English on every device. It reaches the UI as `engine.groups[i].name`.

**Where the other name comes from.** `EngineController::groupName()`
(`app/EngineController.cpp:1780`) walks the loaded group list for a matching id
and, for the built-in group, returns that same untranslated `"All"`. When no
group matches, it falls back to `tr("All")` (`app/EngineController.cpp:1788`) —
a real `tr()` call. `app/i18n/aurelex.ru.ts:9` translates it to `Все`, so
`aurelex_ru.qm` carries `Все` in the committed catalog.

**Why the fallback is reached at all.** History and favorites entries are
`{word, group}` pairs keyed by the active group id at record time
(`app/EngineController.cpp:1984`). Nothing prunes them: `deleteGroup`
(`app/EngineController.cpp:933`) only calls `refreshGroups()` on success, and
`loadHistory`/`loadFavorites` (`app/EngineController.cpp:1662`, `:1702`) only
default a missing `group` key to `0`. So an entry recorded in a group that was
later deleted keeps a dangling id forever, and its row's label comes from the
`tr("All")` fallback. The same entry's `data-group` reaches
`lookupInGroupWithSwitch` (`app/EngineController.cpp:1476`), which does
`groupExists(groupId) ? groupId : 0` — so the tap silently ran in group 0 while
the row claimed otherwise.

**Surfaces that name a group** (all read the untranslated engine name today):

| Surface | Location |
|---|---|
| Groups list row label | `app/main.qml:1890` |
| Groups list row `Accessible.name` | `app/main.qml:1883` |
| `Select group` picker row | `app/main.qml:2816`, `:2819` |
| Search group-scope button | `app/main.qml:891-897` |
| FTS group-scope button | `app/main.qml:2632-2636` |
| History row subtitle | `app/main.qml:373` (via `engine.groupName`) |
| Favorites row subtitle | `app/main.qml:2379` (via `engine.groupName`) |
| Membership editor header | `app/main.qml:2123` (via `editingGroupName`) |

**Ordering constraint.** `loadHistory()`/`loadFavorites()` run at
`app/EngineController.cpp:619-620`, during init. `m_groups` is not populated
until `refreshGroups()` completes, which is kicked off by `runScan()` at
`app/EngineController.cpp:621` and resolves asynchronously into
`EngineController::setGroups` (`app/EngineController.cpp:193`). Any re-point
pass that runs at load time would therefore see an empty group set and re-point
*everything* to group 0.

## Goals / Non-Goals

Goals:

- One group-name string per group per locale, from the app's own catalogs, with
  the engine boundary untouched.
- `Accessible.name` on group rows and picker rows unchanged, so `docs/TESTING.md`
  rows 11 and 13 (which address the group by the name `All`) keep working.
- No stored history or favorites entry left referring to a group that is gone.

Non-goals:

- Renaming or migrating the boundary's C API. The stable id `0` is already
  returned and is a sufficient key; changing `gd_group_info` would need a patch
  in `patches/` plus a CI smoke cycle for no observable gain.
- Localizing user-created group names. Those are the user's own text and are
  stored verbatim; translating them would be wrong.
- Rewriting the *stored* `groups.json`. This change only repairs the app-side
  `{word, group}` entries that point at a group that no longer exists.

## Decisions

### D1 — Localize by id in the UI, not at the boundary

The app maps group id `0` to a catalog string and uses the stored name for every
other id. One QML helper (`root._groupLabel(id)`) is the single source, and all
eight surfaces in the table above call it.

*Alternative considered:* make the boundary emit a translatable name. Rejected —
it needs a `patches/` entry, a rebuild of the carve and a smoke-test cycle
(AGENTS.md golden rule 1), and it would put translation lookup in the engine,
which loads no catalog. The id is the stable contract; the label is a UI concern.

*Alternative considered:* keep `All` untranslated and change the `tr("All")`
fallback to a literal. Rejected — a group name is user-visible text, and
`localization`'s *No inline user-visible strings* requirement would then be
permanently excepted for it. The user chose to localize.

### D2 — `Accessible.name` keeps the literal `All`

`root._groupLabel(id)` feeds visible labels only. The two `Accessible.name`
bindings for group rows and picker rows keep reading a stable English value:
`"All"` for the built-in group, and the stored name for a user group (unchanged
today's behavior — a user group is already its own name in both places).

This is deliberate divergence, and the *Localized display label with an invariant
identifier* scenario pins it. Without it, localizing the label would silently
break UIAutomator addressing of the built-in group.

*Alternative considered:* localize `Accessible.name` too. Rejected — AGENTS.md
documents these values as test IDs, and the localization capability requires them
to be invariant across locales.

### D3 — Re-point, don't drop, and re-point on both triggers

A dangling entry's group id is rewritten to `0` and the file is saved. The word
survives.

*Why re-point rather than drop:* history is a convenience list capped at 500; the
only thing an entry carries that a plain word list would not is its scope, and
group 0 is a superset of the group that was deleted. So a re-pointed tap returns
at least everything the original tap would have.

*Why re-point rather than keep-and-label-unknown:* a label the user can act on is
better, and an unresolvable id has no honest label to show. Keeping the row
would also leave `lookupInGroupWithSwitch`'s silent group-0 fallback in place as
the only way a tap behaves.

*Why both triggers:* the load-time pass repairs entries orphaned by an earlier
session (or by an id shift across a `groups.json` reload); the delete-time pass
repairs the entry the user just orphaned, so the history panel is correct
immediately rather than after a restart.

### D4 — The pass runs from `setGroups`, guarded against an empty group set

The re-point is invoked where `m_groups` is known-good — from
`EngineController::setGroups` (`app/EngineController.cpp:193`) and from
`deleteGroup`'s success path. It is a no-op when `m_groups` is empty, so a
transient empty list (mid-reload) cannot wipe every entry's scope. Id `0` is
never re-pointed, since the built-in group always exists.

`deleteGroup` passes the id it just deleted explicitly: `m_groups` keeps listing
that group until the asynchronous `refreshGroups()` resolves, so the `m_groups`
check alone would not see it as gone at delete time. The `setGroups` caller
relies on `m_groups` alone.

*Alternative considered:* pruning inside `loadHistory`. Rejected by the ordering
constraint above — it runs before groups arrive and would re-point everything.
*Alternative considered:* pruning lazily in the accessor the UI reads. Rejected —
it would re-point on every read, cannot persist from a getter, and hides the cost.

### D5 — `groupName()`'s fallback is no longer a label source

Once every surface resolves through `_groupLabel`, `groupName()` has no remaining
caller that can observe a dangling id, and its `tr("All")` fallback becomes a
second, divergent naming path. The fallback is reduced to the invariant literal
`"All"`, so any future caller that does hit it agrees with the rest of the UI
instead of inventing a third string.

The `Все` entry in `aurelex.ru.ts` stays: it is the translation of the
`qsTr("All")` the UI now uses, which is the point of D1.

## Risks / Trade-offs

- **A user group literally named `All`.** Creating one is already rejected
  (duplicate-name check in the main spec), so a stored name can never collide
  with the built-in label by accident; the id-based mapping is not ambiguous
  either way.
- **Id reuse after deletion.** If a future group is created and lands on a
  recycled id, a re-pointed entry would silently change meaning. Group ids come
  from the boundary's `groupDefs` and are not reused today, so this is
  theoretical; the re-point only ever moves an entry *to* `0`, which is stable.
- **Catalog gap in `ja`.** The `All` translation is new for Japanese; until it is
  entered the Japanese build falls back to the English base string, which is the
  documented behavior of the localization capability, not a defect. Task 4.4
  covers it.
- **Rewriting user data on load.** The re-point is persisted, so a user cannot
  recover the original group id from disk afterwards. Accepted: the group is gone,
  and the alternative (leaving a dangling reference) is the bug.

## Migration Plan

1. Ship the UI label mapping and the fallback change (D1, D2, D5) — behavior-only,
   no data written, safe on its own.
2. Ship the re-point pass (D3, D4). On first launch after the update, entries whose
   group was deleted are rewritten to `0` and `history.json`/`favorites.json` are
   saved once. Idempotent: a second run finds nothing to re-point.
3. Rollback is a code revert. The only on-disk effect is a group id that is now
   `0` instead of dangling; reverting leaves those entries pointing at group 0,
   which is exactly what the old code silently did on tap anyway.

## Open Questions

None. The `ja` wording for `All` is a translation task, not a design question,
and it does not change the approach.
