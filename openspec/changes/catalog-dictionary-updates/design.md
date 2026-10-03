## Context

See `proposal.md` — Why. Constraints that shape this design:

- `public-catalog-hosting` already records, per catalog-installed entry, the
  required dictionary files' SHA-256 in `settings.json` under
  `catalogInstalledDigests` (`entryId -> { fileName: sha256 }`). Nothing consumes
  it yet; this change is its first consumer.
- The catalog's file names are stable and append-only, and `contentHash`
  (`md5(id + required file names)`) is name-derived. Replacing a dictionary's
  content therefore yields the **same** staging directory and the **same**
  engine dictionary id; that is what preserves list position and group
  membership across an update.
- The engine's dictionary id is an MD5 over the absolute source path
  (`engine/src/dict/dictionary.cc`), unchanged by new bytes at the same path.
- The full-text index is keyed on that id and **short-circuits when present**
  (`engine/src/ftshelpers.cc` finish-mark check). An update that keeps the id
  therefore keeps a **stale** index unless it is explicitly invalidated. This is
  the load-bearing difference from the audio path, which may skip reindexing
  because article text does not change.
- FTS index files are app-owned: `<appDir>/index/<id>` and `<id>_FTS_*`, and the
  removal path already has a helper that deletes them (`EngineController.cpp`
  around the index-cleanup comment).
- `startCatalogDownload` today refuses an installed entry except to fetch its
  optional bundle; a required-file re-download is a new mode.
- `reloadDictionariesForResources` (`gd_remove_dict` + rescan) is the existing
  "make new bytes take effect without a restart" path, driven by
  `m_audioReloadIds`.

## Goals / Non-Goals

**Goals**

- Detect that an installed catalog entry's content changed, using only the
  already-recorded digests — no new manifest fields, no on-device hashing.
- Apply the update only on explicit user action, replacing content in place and
  rebuilding the index so search reflects the new text.
- Leave folder-imported dictionaries and all non-catalog dictionaries untouched.
- Make the catalog header state the truth (when it was last checked).

**Non-Goals**

- Automatic/background updates; per-entry version numbers; updating
  folder-imported dictionaries; a user-editable catalog URL; pre-built index
  bundles; detecting changed optional (audio) bundles (the existing add-audio
  path still covers those).

## Decisions

### 1. Detection is a digest comparison, computed on each probe

`refreshCatalogEntries()` already rebuilds the entry list from the cached
manifest. Extend it to compute `updateAvailable` per entry: an entry is
update-available when it is installed **and** has a recorded digest **and** at
least one recorded required-file digest differs from the manifest's digest for
the same file name. No network beyond the probe, no device-side hashing, and it
degrades safely: an entry with no record (pre-`public-catalog-hosting` install,
or folder-imported) is simply never update-available.

### 2. Scope is catalog-installed entries only

Detection requires a recorded digest. Folder-imported dictionaries have none, so
they are never offered an update — which is also what the user chose. Reconstruct
the digest for a folder-imported dictionary would mean hashing multi-GB files on
device; explicitly out of scope.

### 3. Apply by replacing the required files in place, then reload + rebuild

The update reuses `DictionaryDownloadService`, with a new request mode (an
`update` flag on the request) that streams the entry's required files into the
**existing** `staged/<contentHash>/` directory, each to a `.part` that is
atomically renamed over its final name, then leaves the directory in place. This:

- keeps `contentHash` and the engine id, so list position and groups survive;
- preserves the entry's optional resources (audio), which are not part of the
  update and are not re-downloaded;
- reuses the service's existing resume (`Range`/`If-Range`), integrity and
  free-space machinery.

After the files are replaced, the app reloads the dictionary and drops its FTS
index: unload + rescan (as the audio path does) **plus** delete the dictionary's
`index/<id>_FTS_*` entries (the helper the removal path already uses). The
auto-index chain then rebuilds the FTS index because it is genuinely missing —
calling `gd_fts_index` on the unchanged id would short-circuit and leave the
stale index in place.

### 4. The action is user-confirmed

Availability is advertised on the row; nothing is transferred until the user
starts the update. This is the scope decision: a multi-GB re-download plus a
full FTS rebuild must not happen unattended. The update reuses the same
free-space preflight and progress/cancel UI as an install.

### 5. Status line says "last checked"

The header's value is the fetch/cache time (`catalogLastFetched`), so the string
becomes "Last checked %1", and the check-in-progress and failure strings drop the
"updates" vocabulary ("Checking the catalog…", "Couldn't check the catalog…").
Update availability is shown per entry, not in the header; the manifest's own
content date stays unused unless a later change needs it.

## Risks / Trade-offs

- **A multi-file in-place replace is not atomic across files.** A crash between
  the per-file renames can leave a mixed set. → Accept: the entry then fails
  digest comparison and is re-detected as update-available, so the update can be
  re-run; no partial file is ever published (each file is `.part` until its own
  rename).
- **Replacing bytes under a loaded dictionary.** mdict is memory-mapped and the
  id is unchanged. → The reload follows immediately; a rename replaces the
  directory entry while the old inode stays mapped until unload, so the engine
  keeps serving old content until the reload, never a torn file.
- **FTS rebuild cost.** An update re-indexes the whole dictionary (the Japanese
  entry measured ~3.5 min on the test device). → Accept: it is user-initiated and
  the existing processing indication covers it.
- **Pre-`public-catalog-hosting` installs have no recorded digest.** → They are
  simply never offered an update (safe default); re-installing records the digest.
- **Two installation sources for the same entry.** A dictionary with the entry's
  file names but imported from a folder has no record, so it is not updated even
  if it "looks" installed. → Intended, per the scope decision.

## Migration Plan

No stored-state migration: the digests this depends on are already written by
`public-catalog-hosting`. Installs older than that have no digest and simply see
no updates. Rollback is removing the update affordance and the detection; the
catalog and installed dictionaries are unaffected.

## Open Questions

- Whether a changed optional (audio) bundle should also be detected during an
  update, or left to the existing add-audio flow. Deferrable; needs no schema
  change.
- Whether the header should also show a count of available updates, beyond the
  per-row marker. Purely additive UI, answerable after the first use.
