## Context

See `proposal.md` — Why for the motivation and the reproduction. The shape of the
pre-change code that constrains the approach:

The `DICT_IDENTITY_*` block is the **last** block in `carve/smoke/main.cpp`, and it
was the only block that wrote into the fixture folder it was asked to scan:

```cpp
const QString dupDir = dictQDir.filePath( QStringLiteral( "dupcheck" ) );
QDir().mkpath( dupDir );
const QString copy  = QDir( dupDir ).filePath( QFileInfo( primary ).fileName() );
QFile::remove( copy );                 // return value discarded
const bool copied = QFile::copy( primary, copy );
...
QFile::remove( copy );                 // return value discarded
```

The second `remove` was assumed to restore the folder. It cannot. **`MdictParser::open`
allocates `file_ = new QFile(...)`** (`engine/src/dict/mdictparser.cc:98-111`) and
stores it in a `QPointer` that is never deleted, so the handle on the copied
dictionary's source file lives for the whole **process** — not for the life of the
backend object. This was verified during implementation, not assumed:

| teardown attempted | `QFile::remove( copy )` |
| --- | --- |
| immediately after the block | fails (handle open) |
| after `gd_remove_dict()` of the copy | fails — and `gd_remove_dict` also rewrites `groups.json`, so it mutates harness state as a side effect |
| after `gd_cleanup()` | still fails — the `QFile` is leaked, not owned by the destroyed backend |

`MdxDictionary::dictFile` (`engine/src/dict/mdx.cc:308-311,320-327`) *is* released by
`gd_cleanup()`, but that is not the handle in the way. The DSL fixture leaks
identically and nothing owns its `.dsl` handle at all (see Open Questions).

So the "restore the fixture" shape that this change originally specified is
**empirically impossible**: there is no point in the tool's lifetime at which the
delete can succeed. The design below is the one that survives that finding.

One other property of the surrounding code matters for scoping: the re-import block
*does* write into the fixture folder, but it appends a headword to the **original**
in place (`main.cpp:669-681`) rather than adding a second path. That is pre-existing
and benign — the file stays loadable and in the same place — so "the tool leaves the
shared folder's *dictionary set* untouched" is the property to assert, not
"byte-identical".

## Goals / Non-Goals

**Goals:**

- Make the identity block hermetic: after the tool exits, the shared fixture folder
  holds the same dictionary set it was found with, so repeated invocations against
  one folder are independent. That is the property CI depends on and never had.
- Make any pollution of the shared folder **loud and correctly attributed**, so a
  harness fault can never again be reported as an identity regression.

**Non-Goals:**

- Not making the engine close files earlier. That would be an engine change, and
  the engine is pinned and patched-only (`AGENTS.md` golden rule 1). The host-only
  leak is the harness's to design around, not to fix here.
- Not changing what the identity check asserts (`SAME` / `DIFF` semantics). They
  are correct and they pass on a clean folder.
- Not restructuring the workflow's three-invocation shape. Running the MDX folder
  repeatedly is *good* — it is precisely what caught this.

## Decisions

### D1 — The duplicate copy goes under the **config dir**, never the shared fixture folder

`dupcheck/` is created under the per-invocation `configDir` instead of under
`dictDir`, and the block rescans `configDir` to pick the copy up (the original is
already loaded from the `dictDir` scan the tool starts with).

**Why:** hermeticity becomes **structural** rather than dependent on a cleanup that
provably cannot run. Nothing ever scans the config dir twice — each invocation gets
a fresh one from the workflow (`cfg`, `cfg-mdx`, `cfg-mdx-blood`, `cfg-mdx-cafe`) —
so a copy that cannot be deleted is harmless by construction. The property under
test is untouched: the two dictionaries still have the same name and byte-identical
content at **different paths**, which is the entire point of the comparison, and the
app's grouping depends on exactly that record shape.

**Alternatives considered:**

- **Restore the copy after `gd_cleanup()`.** This was the original D1 of this change
  and it is **falsified**: the table above is the measurement that killed it. Any
  design resting on it would have shipped a cleanup step whose result is always
  `false` — the same discarded-return-value bug, one refactor later.
- **`gd_remove_dict()` the drifted copy first, then delete.** Fails for the same
  reason, and additionally rewrites `groups.json` via `saveGroupsLocked()`
  (`gd_boundary.cc:1081`), so a mechanical cleanup step would mutate group state the
  test never meant to touch.
- **Retry the delete in a loop, or open with `FILE_SHARE_DELETE`.** The former is
  timing-dependent and papers over the real constraint; the latter is not expressible
  through `QFile` and would mean bypassing the boundary's own file access.
- **Fix the leak in the engine patch set.** Out of scope by `AGENTS.md` golden rule 1,
  and it would not help any format whose handle owner is unknown (see Open Questions).

### D2 — Assert the shared folder was left untouched, and give it a name

The tool prints `DICT_IDENTITY_CLEANUP=OK|FAIL` and folds it into the exit code. On
`FAIL` the message names the offending path under the fixture folder.

**Why:** the entire bug class here is an unasserted side effect. A cleanup whose
result is discarded will fail silently again, and the *next* process is the one that
reports it, two runs later, as something else entirely. This mirrors
`fix-smoke-fixture-scoping`, which added explicit assertions for exactly this reason
(a skip that is merely tolerated lets a run pass vacuously). The assertion also
serves as the **proof that D1 holds**: it is checked against the real fixture folder
every run, so a future edit that moves the copy back under `dictDir` fails loudly on
the same run that introduces it, instead of two runs later.

**Alternative — fix the removal and say nothing.** Not available (D1) and in any case
it fixes this instance while leaving the harness one unasserted mutation away from
the next identical failure.

### D3 — A polluted fixture folder is reported as pollution, not as identity drift

No separate entry guard is needed. Because the copy no longer lands in the shared
folder (D1), the block's own numbers — `copies=`, `scan+`, `SAME`, `DIFF` — are
always derived from the state the block created, and the leftover from *any* other
cause is caught by the D2 assertion instead.

**Why:** an earlier draft of this design put a stale-`dupcheck/` guard at the top of
the block, printing `DICT_IDENTITY_CLEANUP=FAIL (stale dupcheck/ from a previous run)`
and skipping the check. Once D1 landed it was strictly redundant: the D2 assertion
names the same leftover and the same path, and does so for **any** file in the
fixture folder rather than only a `dupcheck/` entry. It was dropped rather than kept
as belt-and-braces, because two gates reporting the same condition is two things to
keep in step for no extra coverage.

The property that mattered for the original failure — *every number in the block
describes a known state* — now holds structurally. Verified by planting a leftover
by hand: the run reports `SAME=OK` / `DIFF=OK` (the block's numbers describe only
what it created) and `DICT_IDENTITY_CLEANUP=FAIL` with the path, exiting non-zero.

### D4 — Gate the new line in both workflow runs

`DICT_IDENTITY_CLEANUP=OK` is asserted for the MDX-only run and the combined run, in
the existing per-line style, and deliberately **not** added to the `SKIP` list.

**Why:** the combined folder is scanned exactly once, so its DSL leak is currently
invisible there (see `proposal.md`). The gate is what stops that from staying
invisible — it is the assertion that would have caught the leak at the point it was
introduced. The MDX folder is scanned three times, so its gate is the one that
actually carries weight today.

## Risks / Trade-offs

- **[A leaked copy now survives under the config dir instead of the fixture dir]**
  → That is the point (D1): the config dir is per-invocation and discarded by the
  workflow, whereas the fixture dir is shared across three invocations. The residual
  is verified by inspection (`cfg/dupcheck/<name>` at 385 bytes for the DSL fixture)
  and costs nothing. `QFile::remove` is still attempted first, as best-effort tidying.
- **[The assertion is weaker than "byte-identical", because the re-import block
  appends a headword to the original DSL in place]**
  → Scoped deliberately to the **dictionary set** (no added paths), which is the
  property the next invocation depends on. The re-import mutation is pre-existing,
  idempotent in effect, and out of scope for a cleanup fix; asserting byte-identity
  would have meant failing the combined run on every invocation.
- **[The identity block's scan target changed from `dictDir` to `configDir`]**
  → Verified against the combined folder (`gd_scan_dicts -> 3`, `gd_scan_dicts(again)
  -> 0`, `INDEX_PLACEMENT=OK`, and every pre-existing gate green) so the blocks before
  it are not perturbed. The MDX folder is the sharper case and is scanned three times
  by CI precisely to catch this class of thing.
- **[A format whose handle survives to the end of the process leaks into the config
  dir instead of failing]**
  → Intended. The config dir is never rescanned, so there is nothing for the leak to
  break; and if a future format *does* pollute the shared folder, D2 fails with the
  path named.
- **[One more `grep -q` per run to keep in step]** → It is one line per run, matching
  the ~30 the workflow already carries, and it gates a failure mode that has twice
  cost a full 27-minute red build.

## Migration Plan

None — CI wiring and a host-only diagnostic tool. Rollback is a revert; nothing
persists.

## Open Questions

- **Which object holds the source-file handle for the DSL fixture?** MDX is
  explicit (`MdictParser::open` leaks it outright; `MdxDictionary::dictFile` is
  separate and is released), but `DslDictionary` has no `QFile` member
  (`engine/src/dict/dsl.cc:121-145`) — `File::Index idx` covers the index file, not
  the `.dsl`. Deferred deliberately: the answer does not change D1, which works
  precisely because it stops depending on *which* object holds the handle. Worth
  resolving only if a future format turns out to pollute a rescanned directory.
