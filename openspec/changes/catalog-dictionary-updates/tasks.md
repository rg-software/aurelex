## 1. Detection and state

- [ ] 1.1 Add a pure comparison of an entry's recorded `catalogInstalledDigests`
      against the manifest's required-file digests, and unit-test it (an entry
      with no record is never update-available)
- [ ] 1.2 Compute per-entry `updateAvailable` in `refreshCatalogEntries()` and
      expose it on the catalog entry map
- [ ] 1.3 Confirm an installed entry whose digests match is not flagged, and one
      with a differing required file is

## 2. Update transfer (reuse the download service)

- [ ] 2.1 Add an `update` request mode to `startCatalogDownload` that selects the
      entry's **required** files for an installed entry when an update is applied
- [ ] 2.2 Add the matching service mode: stream each required file into the
      existing `staged/<contentHash>/` directory via a `.part` and an atomic
      rename over the final name, leaving optional resources in place
- [ ] 2.3 Route the update through the existing free-space preflight, progress
      and cancel; a cancel or failure leaves the installed dictionary intact and
      resumable from scratch
- [ ] 2.4 On a successful update, arm the reload + reindex path (a required-file
      update, not the optional-audio path)

## 3. Reload and full-text rebuild

- [ ] 3.1 Reload the updated dictionary (unload + rescan) so the new bytes take
      effect without an app restart, keeping its list position and groups
- [ ] 3.2 Delete the dictionary's full-text index entries (`index/<id>_FTS_*`)
      before the reload so the rebuild is not short-circuited by the unchanged
      dictionary id
- [ ] 3.3 Let the normal auto-index chain rebuild the full-text index, with the
      existing processing indication

## 4. Catalog UI

- [ ] 4.1 Relabel the header to state the last check ("Last checked %1") and drop
      the "updates" vocabulary from the checking/failure strings
- [ ] 4.2 Add an update affordance on an installed row when `updateAvailable`
      (a stable `Accessible.name`, disabled while processing)
- [ ] 4.3 Add any new `Accessible.name` to the element-ID table in `AGENTS.md`

## 5. Documentation

- [ ] 5.1 Update `docs/REMOTE-CATALOG.md` with the update lifecycle (detection,
      user-confirmed apply, in-place replace, FTS rebuild, catalog-installed only)
- [ ] 5.2 Add `docs/TESTING.md` recipes for detecting and applying an update

## 6. Verification

- [ ] 6.1 Run the detection unit test
- [ ] 6.2 On device: install an entry, publish a catalog whose entry has a new
      digest at the same file names, re-probe, confirm the row offers an update,
      apply it, and confirm the new content serves, the FTS index reflects it, and
      position/groups are preserved
- [ ] 6.3 On device: confirm a folder-imported dictionary is never offered an
      update
- [ ] 6.4 On device: cancel an update mid-transfer and confirm the installed
      dictionary remains usable
- [ ] 6.5 Confirm the catalog header reads as the last check, with no "update"
      wording for a plain check
