## Context

Removing a dictionary deletes its primary file and its indexes, but leaves the
rest of its staged copy: measured on device, a StarDict dictionary left behind
`.idx`, `.dict.dz`, `.syn` and an 824-image `res/` tree — about 18 MB — inside a
staged directory that survived the removal.

The device log shows why:

```
removed index entry ".../index/e118ce31..."              (correct)
removed staged source file ".../staged/70549544/stardict.ifo"  ok= true
staged dir kept, a loaded dictionary uses it ".../staged/70549544"
```

At that moment only two dictionaries remained loaded, both in **other**
directories. The sharing guard exists to protect a directory that several
dictionaries share inside one imported folder; here it protected a directory
whose only owner had just been removed.

## Why it never self-heals

`sweepStaleStagedDirs()` reclaims a staged directory only when a scan reported it
as **failed**. A directory whose primary file is gone yields no dictionary and no
failure, so it is never swept. The leak is permanent.

## Decision: fix the guard, and make the leftover reclaimable

Two things, because either alone leaves a hole.

**1. The guard must not count the dictionary being removed.** A dictionary that
has just been unloaded is still listed until the async refresh lands; the code
already tries to account for this via `m_unloadedSources`, and that accounting is
not effective here. The exact reason is **not yet established** — candidates
include the source path recorded at unload differing from the one compared
against, and a stale entry matching by prefix. This must be determined by
measurement (instrument the guard, remove one dictionary, read the log) before a
fix is chosen; three plausible mechanisms have already been ruled out by reading
the code, which is the reason to stop reading and start measuring.

**2. A directory holding no primary file must be reclaimable.** Even with the
guard fixed, a directory orphaned by an older removal — including the 18 MB
already leaked on a real device — has no owner and no failure report. The sweep
must recognise "holds no primary file any dictionary loads" and reclaim it. This
is what actually releases the storage users have already lost.

**Sibling safety is non-negotiable.** The sharing guard must keep working: one
import folder can hold several dictionaries, and removing one must never delete
a surviving sibling's files. The `stale-import-cleanup` design calls this the one
place an externally-supplied path becomes a filesystem deletion, which is why it
has two guards. Nothing here may weaken the containment guard.

## Scope is probably not StarDict-only

The shape at issue — a primary file plus siblings staged in one directory — is
common:

| Format | Staged together |
| --- | --- |
| StarDict | `.ifo` + `.idx` + `.dict.dz` + `.syn` + `res/` |
| DSL | `.dsl.dz` + `<name>.dsl.files/` |
| MDict | `.mdx` + `.mdd` + loose assets |

StarDict merely exposed it. Verification must cover more than one format —
otherwise the fix will be written to the example that happened to fail.

## Verification

- **Host**: `StagedCleanupTest` gains the case that failed — a directory whose
  only owner was just removed must be reclaimable, and one shared with a
  surviving dictionary must not be. The predicate is header-only precisely so
  this runs without a device.
- **Device**: remove a StarDict dictionary and confirm the staged directory and
  its `res/` tree are gone; then the same for a DSL dictionary, to check the
  scope claim rather than assume it.

## Risks / Trade-offs

- **[Deleting a sibling's files]** The worst outcome, and the reason the guard
  exists. → The sharing predicate is unchanged in intent, gets a host test for
  both directions, and the containment guard stays.
- **[Sweeping something live]** A sweep that reclaims a directory still being
  written by an in-flight staging run would corrupt an import. → Follow the
  existing sweep's rule of only touching a directory nothing is using, and keep
  the "no primary file" condition narrow.
- **[Scope assumed from one format]** Verified on StarDict only. → The tasks
  require a DSL removal check, because the reporter's concern — that this is
  format-general — is reasonable and untested.
