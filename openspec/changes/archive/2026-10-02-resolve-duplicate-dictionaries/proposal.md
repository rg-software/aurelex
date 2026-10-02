## Why

The app currently derives a dictionary's identity from **where its files live**.
The engine id is an MD5 over the sorted source file paths
(`carve/gd_boundary.cc:556-565`), and the Android importer turns each SAF pick into
a folder named after a hash of the picked tree URI
(`StagingService.java:140`, `files/staged/<sourceId>/…`). Two imports of the same
dictionary therefore produce two paths, two engine ids, and two rows in the
Dictionaries list — the user has two identically-named "Longman Pronunciation
Dictionary (En-En)" entries.

Nothing in the design ever had to answer "is this the same dictionary arriving
from somewhere else?", so the question was never asked. The existing copy-time
dedup (`hasStagedCopy()`, `AurelexActivity.java:663-679`) only avoids re-copying
unchanged files; it cannot collapse two import roots, and it never sees
remote-catalog downloads at all (those land in `files/staged/<contentHash>/`).

Location is not a meaningful property of a dictionary. Two copies of the same
dictionary are the same dictionary regardless of which folder they were picked
from. Identity should be **name + content**.

The commonest way to hit this is not exotic: the user keeps dictionaries in one
folder, drops a new build into it, and re-imports the folder. Everything already
there comes back as a duplicate. The fix has to be invisible for that case.

## What Changes

- **Dictionary identity becomes its normalized display name plus a content
  signature** derived from the dictionary's complete set of source files. Location
  stops being part of the user's-facing identity.
- **An import that resolves to a dictionary already present, with identical
  content, is silently skipped.** The incoming staged copy is deleted and the
  incumbent is left untouched — same object, same position in the list, same
  groups, same indexes, nothing to migrate. This is the common case above, and it
  produces no message, no row, and no prompt.
- **An import that resolves to a same-named dictionary with different content is
  rejected.** The incoming copy is deleted, the incumbent is kept, and the
  dictionary is reported with the reason. This deliberately does **not** prompt:
  an import is an asynchronous batch (stage → scan → index) and a modal in the
  middle of it stalls the whole batch for a decision about one file. The user
  resolves it by removing the old dictionary and re-importing.
- **Nothing is deleted by a prompt.** The only dictionary an import ever deletes
  is its own incoming copy. An import never removes a dictionary the user already
  had, so there is no destructive action to confirm and no confirmation dialog.
- **A scan resolves duplicates already present, including at cold start.**
  Identical same-named copies collapse automatically, because that action cannot
  lose a dictionary — the survivor is byte-equivalent. This is what repairs
  existing installations on upgrade; without it, both copies would reappear on
  every restart, because a cold start has no "candidate" and simply loads the
  staged tree.

Two things this deliberately does **not** do:

- **No content hashing.** If size and mtime differ, the files are not
  byte-identical and hashing cannot change that conclusion. The only case a
  content hash would rescue is "stat says different, content is actually the
  same" — an mtime that drifted on copy or re-extraction — which the user now
  sees and resolves by hand. `size + mtime` with the tolerance already used by
  `hasStagedCopy()` is the whole signature.
- **No format-scoped matching.** If a `.dsl` and an `.mdx` both report "Longman
  Pronunciation Dictionary", scoping the match per format would leave the user
  with the two identically-named rows this change exists to remove.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: identity becomes name plus content; identical imports
  are silently skipped and differing same-named imports are rejected and reported,
  with the incumbent always left untouched; scans resolve duplicates already
  present, collapsing identical copies and reporting differing ones.
- `storage-folder-access`: the existing "Re-importing the same folder" scenario
  promises only per-file content dedup within a pick. It is restated in terms of
  the identity rule, so that picking a folder, or its parent, or a second copy on
  device, has one defined outcome.

## Impact

- **`carve/goldendict.h` / `carve/gd_boundary.cc`** — one additive boundary call
  returning, per loaded dictionary, the display name, the primary file path and
  the content signature over its whole file set. `gd_dict_info` returns a name and
  one file; the signature needs the set. No engine change, no patch, and no change
  to the engine's own id derivation.
- **`app/EngineController.cpp`** — owns the identity grouping, the skip, the
  reject, and the automatic collapse of duplicates found by a scan. Already the
  owner of staged-storage layout and staged-file deletion.
- **Reporting** — a rejected dictionary is reported through the import-results
  surface. That surface is built by the `report-import-results` change; this
  change supplies the clash reason. See that change's proposal for the ordering.
- **Java staging (`StagingService.java`, `AurelexActivity.java`)** — the
  copy-time dedup is subsumed but stays as a cheap `stat()`-only pre-filter that
  avoids copying bytes which would only be deleted. No change to the staging or
  rename flow itself.
- **`carve/smoke/main.cpp`** — gains a same-name/different-path fixture pair, so
  "two dictionaries with one name in the tree" is covered by CI rather than only
  on a device. This gap is why the original bug shipped.
- **No engine impact and no new user-facing strings** beyond the clash reason,
  which belongs to the reporting surface.
