## Context

See proposal.md — Why. The relevant current state:

**Identity is a path hash.** `Dictionary::getId()` upstream is an MD5 over sorted
source file paths. `gd_scan_dicts` dedups on that id
(`carve/gd_boundary.cc:556-565`), so two copies at two paths are two dictionaries
no matter what they are called.

**Import roots are named after a hash of the picked tree URI.**
`StagingService.stageOne` computes
`sourceId = Integer.toHexString(treeUri.toString().hashCode())` and copies into
`files/staged/<sourceId>/` (`StagingService.java:140-143`).
`primary:Dictionaries` and `primary:Dictionaries/Longman` are different URIs, so
the same file reaches two roots. Remote-catalog downloads use a third naming
scheme, `files/staged/<contentHash>/`.

**A stat-based change signal already exists and is trusted.**
`EngineState::sourceStamps` records `(size, mtimeMs)` per source file at load
time, and `dictionarySourceChanged()` (`gd_boundary.cc:207-237`) drops and
reloads a dictionary whose files no longer match. The importer uses the same
signal, at a 5000 ms tolerance, to skip unchanged files
(`AurelexActivity.java:616-622`) and to avoid re-copying a file already staged
under another root (`hasStagedCopy()`, `AurelexActivity.java:663-679`).

**The name is only available after the engine loads the file.** A StarDict `.ifo`
carries `bookname` in plain text, but a DSL's name lives in its binary header
block and an MDX's inside a zlib-compressed XML header. Nothing in the Java
staging layer can read a name cheaply or uniformly. The boundary already exposes
it: `gd_dict_info` returns the display name and the first source file
(`carve/goldendict.h:130`).

**An import is an asynchronous batch.** A pick is staged by a foreground service,
then the C++ poller runs `gd_scan_dicts` over the whole staged root, then
`autoIndexMissing()` builds every missing full-text index
(`EngineController.cpp:385-447`). Nothing in that chain has a user-facing pause
point, and introducing one would stall every other dictionary in the pick.

**The engine is not ours to change.** Per `AGENTS.md`, deviations from the pinned
engine live in `patches/`. Nothing here needs one.

## Goals / Non-Goals

**Goals:**

- One dictionary per identity, no matter how many folders it was picked from.
- Re-importing the folder a user keeps their dictionaries in is a silent no-op for
  what is already there, and adds whatever is new.
- Duplicates that already exist are repaired by a scan, so they do not return on
  every restart.
- No import ever removes a dictionary the user already had.

**Non-Goals:**

- Upgrading a dictionary to a new build by importing over it. Same-folder updates
  already work in place through the existing `sourceStamps` reload; a
  different-folder update takes remove-then-reimport, and that is the deliberate
  cost of never deleting without a selection.
- Letting the user keep two builds of the same dictionary side by side. That needs
  namespaced identities ("Longman (2024)") and a UI for choosing between them.
- Undo. There is no destructive action to undo.
- Changing the engine's id derivation or making engine ids content-based.
- The reporting surface itself — built by `report-import-results`. This change
  supplies the clash reason and depends on that surface existing.

## Decisions

### D1: The policy runs after the load, in C++, not during staging

The name is only knowable once the engine has loaded the file (see Context), so no
Java-side pre-copy check can implement skip or reject. The boundary resolves
names; the app owns staged-storage layout. So the carve exposes the inventory the
policy needs (D2) plus the existing `gd_remove_dict`, and `EngineController`
decides and acts.

*Alternative considered:* parse names in Java per format. Rejected — three header
formats, one compressed, reimplemented outside the engine that already knows them.
It would also leave two name implementations free to disagree.

### D2: Inventory is one additive boundary call

The policy needs, per loaded dictionary: display name, primary file path, and the
**whole file set** it is made of. `gd_dict_info` returns name and one file; the
comparison needs every file.

`gd_dict_identity( index, out, out_size )` returns all of it in one
caller-provided buffer, following the existing `gd_dict_info` / `gd_full_list`
pattern: NUL-terminated, newline-separated, tab-separated records — `D<TAB>name
<TAB>primaryFilePath`, then `F<TAB>basename<TAB>sizeBytes<TAB>mtimeMs` per source
file. Additive only: no existing signature changes, no engine change.

It returns the file records **raw rather than digested**, and the app compares
them component-wise. An earlier draft of this decision called for an MD5 over the
records; that cannot express the mtime tolerance the spec requires, and a digest
is all-or-nothing where "drifted by less than 5 s" has to be neither equal nor
unequal. The set is small by construction — resource trees are not in
`getDictionaryFilenames()` — so a component-wise comparison costs nothing and the
digest bought no speed. Three properties are deliberate:

- **Records carry the basename, never the directory.** That is the whole point:
  the same dictionary in `staged/abc/` and `staged/def/` must compare equal. The
  engine always returns absolute paths, so the directory is stripped before the
  record is emitted.
- **Every file is included, not just the primary.** An `.mdx` plus 14 `.mdd`
  volumes is one dictionary; comparing only the primary would call a
  resource-stripped variant identical to a complete one.
- **A missing file reports `-1` for size and mtime**, matching what
  `sourceStamps` records for an absent file, so the two signals agree on what
  "absent" means.

Sibling resource trees (`<dict>.dsl.files/`) are **not** in
`getDictionaryFilenames()` and are deliberately excluded — they carry no entries,
and comparing tens of thousands of sound files would not be worth it. See Risks.

`gd_dict_identity` returns `-2` for an out-of-range index, distinct from `-1`
(invalid args / buffer too small), so a caller reacting to a concurrent removal
can tell "this dictionary is gone" from "give me a bigger buffer" rather than
retrying forever.

### D3: Skip and reject are the same operation with different text

For a candidate whose identity resolves to a loaded dictionary:

| Signature | Outcome |
|---|---|
| equal | **skip** — unload the candidate, delete its file set, keep the incumbent, report nothing |
| differs | **reject** — unload the candidate, delete its file set, keep the incumbent, report the clash |

The mechanics are identical; only the report differs. Both delete **only the
incoming copy**, so the incumbent's object, position, groups and indexes are never
touched and there is nothing to migrate and nothing to confirm.

This is the direct consequence of dropping the replace-with-confirmation design.
Replacing would have meant deleting a dictionary the user already had, which is the
only destructive thing an import could do, and it is not worth a modal in the
middle of an asynchronous batch (Context). Rejecting costs the user a remove and a
re-import in a rare case; replacing costs every version update a decision point in
a pipeline that has no place for one.

Deletion goes through the existing `StagedCleanup` containment guards, so it can
never reach outside the staged root, and the directory is reclaimed only when no
loaded dictionary remains in it — which is what preserves a sibling dictionary
that shared the pick's folder.

### D4: Nothing is deleted by a prompt

The only dictionary any of this deletes is the import's own incoming copy. This is
why there is no confirmation dialog, no swap machinery, no FTS invalidation on
replacement, and no path-preservation requirement: all four existed solely to make
an import able to remove a dictionary the user already had. Removing that ability
removes them together.

*Alternative considered:* keep the replace, prompt at the **end** of the batch
rather than mid-scan. Rejected — it reintroduces a delete-without-selection, and a
user who approves twenty dictionaries and is then asked to approve a deletion has
been trained to click yes.

### D5: The invariant runs on every scan, and only acts when lossless

D3 is an import-path rule and would not fix an existing installation: at cold
start there is no candidate, the scan just loads the staged tree, and both copies
reappear. So the same grouping runs after **every** scan:

- **Equal signatures → collapse silently.** Keeping one copy loses nothing, since
  the survivor is byte-equivalent by the signature. This is the only automatic
  delete, and it is what repairs existing installs on upgrade.
- **Differing content → report, delete nothing.** A startup scan expresses no
  intent, and the signature cannot distinguish a newer build from an unrelated
  dictionary that shares a name. The user resolves it by removing one.

Governing rule: **act without asking only when the action cannot lose a
dictionary.**

The report must not reuse the wording of a load failure, and specifically must not
repeat the current banner's "Remove it and import the folder again"
(`main.qml:1786`) — that advice is untrue for a clash, where the folder is already
added and the fix is to remove the *other* build.

### D6: No content hashing

If `(name, size, mtime)` differ, the files are not byte-identical and a hash cannot
alter that conclusion — it only grades *how* different. The single case a hash
would rescue is "signature says different, content is actually the same", i.e. an
mtime that drifted on copy or re-extraction. That is now a *visible, user-resolved*
case rather than a silent one, which is a better outcome than a hash would have
produced: the user is told, rather than the app guessing.

Hashing would also add a cache with its own invalidation problem — a cached hash
goes stale exactly when the file changed, which is the only time it is consulted —
and would read every staged dictionary, including multi-GB `.mdd` volumes, on a
path that must stay responsive on a mid-range phone.

### D7: Name is normalized; format is never matched on

Names are compared case-folded after trimming and collapsing internal whitespace,
so a publisher's stray double space does not read as a different dictionary.

Format is **not** part of the match key. Scoping per format family would leave a
`.dsl` and an `.mdx` both reporting "Longman Pronunciation Dictionary" as two rows
in the list — the precise confusion this change removes. They collide, and the
clash is reported.

### D8: The importer's copy-time dedup stays, as a pre-filter

`hasStagedCopy()` and the `alreadyLocal` check remain. They are cheap (`stat()`
only) and avoid copying bytes that would only be deleted, which matters when the
pick is a multi-GB folder. They are not the identity rule and no longer need to
be: they dedup *files*, this rule dedups *dictionaries*.

## Risks / Trade-offs

- **A signature collision across genuinely different dictionaries.** Two same-named
  dictionaries whose files match on `(basename, size, mtime)` collapse silently.
  Requires identical names *and* per-file sizes *and* mtimes within 5 s. → The
  action is lossless by construction, so the worst case is a user who wanted both,
  not data loss. Accepted.

- **Sound-file drift is invisible.** `<dict>.dsl.files/` is outside the signature,
  so a copy missing a pronunciation file compares equal to a complete one and is
  skipped — leaving the incumbent's audio in place. Usually correct. But audio
  cannot *repair* a same-named dictionary through a plain import. → Documented;
  the resource-adoption path (`dictionary-management`: "Late-arriving resources are
  adopted by a loaded dictionary") is the mechanism built for that.

- **Version upgrades need two steps.** A different-folder upgrade is
  remove-then-reimport, and the reimport lands at a new engine id, losing group
  membership and list position. → Accepted for D4's reason. Same-folder updates are
  unaffected and still reload in place. Stated in the specs so it is a documented
  behaviour, not a surprise.

- **Rejections are invisible until the report is read.** The batch continues
  correctly, but a user who does not open the report may believe a dictionary
  updated. → The report names the dictionary and the reason, and the report
  surface persists until dismissed (`report-import-results`). This is the main cost
  of not prompting.

- **Two boundaries to keep consistent.** The signature is computed in the carve and
  compared in the app; drift would silently mis-classify. → One implementation,
  exposed through the single D2 call, and the smoke tool asserts the same
  invariants on host.

- **Cold-start scan does more work.** Grouping is O(dictionaries × files) with no
  I/O beyond what `sourceStamps` already stats. → Negligible.

- **Existing users' duplicates disappear without asking.** Only identical copies,
  so the content is still present exactly once. → Accepted; release-note it as a
  behavior change.

## Migration Plan

1. Ship the boundary inventory call (D2). Additive; nothing consumes it yet.
2. Ship the scan-time invariant and collapse (D5). **This is the step that fixes
   existing installations** — identical duplicates collapse on the first scan
   after upgrade.
3. Ship skip and reject on the import path (D3), reporting into the
   `report-import-results` surface.

Rollback is clean at every step: the boundary call is additive, and all file
operations go through the existing `StagedCleanup` containment checks.

## Open Questions

None. The reporting surface's form is decided in `report-import-results`.
