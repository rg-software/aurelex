## Why

The built-in `All` group is shown with two different names in the same UI, and
only one of them is translated. Its name is produced by the engine boundary as a
hardcoded C string (`"All"`), so the Groups list, the group picker and both
group-scope buttons render English in every locale. A separate code path — the
`groupName()` fallback — uses a real `tr("All")`, which the Russian catalog
translates to `Все`. A user's history therefore showed `Все` next to a built-in
group labelled `All`.

That path is also reached by history and favorites entries whose group id no
longer exists: those entries are never pruned when a group is deleted, so they
masquerade as belonging to `All` while a tap on them silently looks the word up
in group 0 instead of the scope the row claims.

## What Changes

- Render the built-in group's name from the active language's catalog, mapped by
  its stable group id, so every surface that shows a group name reads the same
  string in the same locale. The boundary is unchanged: it already returns a
  stable id (`0`) for the built-in group, so the app maps that id to a
  catalog string instead of consuming the boundary's untranslated name.
- Funnel every group-name surface through that single mapping: the Groups list
  row, the `Select group` picker rows, the Search group-scope button, the
  full-text-search group-scope button, the history rows in the suggestion
  panel, the Favorites list rows, and the membership editor's header.
- Keep `Accessible.name` on the group rows and picker rows as the invariant
  English `All` for the built-in group, so UIAutomator/Appium addressing and
  `docs/TESTING.md` are unaffected.
- Re-point a history or favorites entry whose group id no longer exists to the
  built-in group, and persist the rewrite, so the label is truthful and a tap
  looks the word up in the scope the row now claims.
- **BREAKING** (data): history and favorites files written by a build that
  recorded a deleted group are rewritten on load, replacing the stale group id
  with the built-in group's id.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `localization`: *No inline user-visible strings* — the built-in group's name is
  a user-visible string that currently bypasses the catalog; the requirement
  gains it as a case, plus the invariant-identifier carve-out for it.
  *Accessibility test identifiers remain invariant* gains the case where a
  localized display label and an English `Accessible.name` deliberately diverge.
- `dictionary-management`: *Dictionary groups* — the built-in group's displayed
  name is a localized label derived from its id rather than the boundary's
  untranslated name, and a lookup or favorite recorded against a group that no
  longer exists is re-pointed to the built-in group.

## Impact

- `app/main.qml`: one shared group-label helper replacing the per-surface reads
  of `engine.groups[i].name` and `engine.groupName(...)`; `Accessible.name`
  bindings for the group rows and picker rows keep the literal `All`.
- `app/EngineController.cpp`: `groupName()`'s fallback, and a re-point pass for
  history/favorites entries whose group id is absent from the loaded group set.
  The pass must run when the group set arrives (groups load asynchronously after
  history does) and after a group deletion succeeds.
- `app/i18n/aurelex.{ru,ja}.ts` and the recompiled `.qm`: `All` gains a real
  translation; `ru` already carries `Все`, `ja` needs an entry.
- No change to `carve/`, `patches/`, or the engine boundary, so the CI smoke
  test is unaffected.
