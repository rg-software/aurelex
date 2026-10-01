## Context

Removing a dictionary deletes its primary file and its indexes, but leaves the
rest of its staged copy: measured on device, a StarDict dictionary left behind
`.idx`, `.dict.dz`, `.syn` and an 824-image `res/` tree inside a staged
directory that survived the removal.

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

## The consequence that sets the priority

The leftover is not merely wasted disk — **the dictionary cannot be re-imported**.
Confirmed on device: re-adding The World Factbook after removing it fails,
because the directory still holds `.idx`/`.dict.dz`/`.syn`/`res/` but not the
`.ifo`, and staging's dedup step sees those files already present and does not
re-copy them. The directory therefore never regains the primary file StarDict is
identified by, and the dictionary never loads.

Deleting the orphan by hand made the re-import succeed immediately, which
confirms the mechanism rather than merely correlating with it.

So `Remove a loaded dictionary`'s existing **"Re-add after removal"** scenario is
**failing**, and that is why this change exists.

## Why it never self-heals

`sweepStaleStagedDirs()` reclaims a staged directory only when a scan reported it
as **failed**. A directory whose primary file is gone yields no dictionary and no
failure, so it is never swept. The leak — and the blocked re-import — are
permanent until this is fixed.

## Decision: fix the guard, and make the leftover reclaimable

Two things, because either alone leaves a hole.

**1. Record the removal in the user's path.** A dictionary that has just been
unloaded is still listed until the async refresh lands, and the code already has
a mechanism for that — `m_unloadedSources`, consulted by `liveDictionarySources`.
It was being populated by only **one** of the two removal paths:

| Path | Appended to `m_unloadedSources`? |
| --- | --- |
| `removeDuplicates` (scan-time repair) | yes — `EngineController.cpp:1174` |
| `removeDictionaries` (**the user's Remove**) | **no** |

So a user-initiated removal left the removed dictionary counting as a live user
of its own directory, and the guard kept it. The fix appends the removed source
in `removeDictionaries` **before** deleting files, matching what the duplicate
path already did.

**This was established by measurement, not by reading.** The instrumented build
printed:

```
DIAG liveDict source: ".../70549544/stardict.ifo" excluded= false
DIAG m_unloadedSources: QList()                       <- empty
DIAG MATCHING SOURCE: ".../70549544/stardict.ifo"
```

`m_unloadedSources` empty at that moment is the whole answer. Note what it
rules out: the paths are byte-identical, so the candidate "the excluded value
and the compared value differ" was wrong, and so were the three others
considered from reading the code. Four plausible mechanisms, none of them the
real one — which is exactly why this task required an instrumented run rather
than a patch based on inspection.

**2. A directory holding no primary file must be reclaimable.** Even with the
guard fixed, a directory orphaned by an older removal — including one already on
a real device — has no owner and no failure report. The sweep now checks for a
primary file first, using `StagingRules::isPrimaryDictionaryName`
(`.mdx`/`.dsl`/`.dsl.dz`/`.ifo`). That is deliberately **not**
`isSupportedDictionaryName`, which also accepts companions and resource
archives: a directory holding only companions is precisely the orphan to detect.
The check runs **before** the failed-import test, because such a directory
produces no scan failure to match — it yields no dictionary and no error, which
is why the old condition never caught it.

**Sibling safety is non-negotiable.** The sharing guard must keep working: one
import folder can hold several dictionaries, and removing one must never delete
a surviving sibling's files. The `stale-import-cleanup` design calls this the one
place an externally-supplied path becomes a filesystem deletion, which is why it
has two guards. Nothing here weakens the containment guard, and the sweep now
also declines to run while staging is active, since a directory mid-copy can
transiently hold companions before its primary file lands.

## Scope is probably not StarDict-only

The shape at issue — a primary file plus siblings staged in one directory — is
common:

| Format | Staged together |
| --- | --- |
| StarDict | `.ifo` + `.idx` + `.dict.dz` + `.syn` + `res/` |
| DSL | `.dsl.dz` + `<name>.dsl.files/` |
| MDict | `.mdx` + `.mdd` + loose assets |

StarDict merely exposed it. The re-import failure probably generalises too, since
any format identified by its primary file leaves a directory that looks
populated but loads nothing. Verification must cover more than one format —
otherwise the fix will be written to the example that happened to fail.

## Verification

- **Host**: `StagedCleanupTest` gains the case that failed — a directory whose
  only owner was just removed must be reclaimable, and one shared with a
  surviving dictionary must not be. The predicate is header-only precisely so
  this runs without a device.
- **Device**: remove a StarDict dictionary and confirm the staged directory and
  its `res/` tree are gone; then **re-add it and confirm it loads**, which is the
  behaviour that is broken today; then the same for a DSL dictionary, to check
  the scope claim rather than assume it.

## Risks / Trade-offs

- **[Deleting a sibling's files]** The worst outcome, and the reason the guard
  exists. → The sharing predicate is unchanged in intent, gets a host test for
  both directions, and the containment guard stays.
- **[Sweeping something live]** A sweep that reclaims a directory still being
  written by an in-flight staging run would corrupt an import. → Follow the
  existing sweep's rule of only touching a directory nothing is using, and keep
  the "no primary file" condition narrow.
- **[Scope assumed from one format]** Verified on StarDict only. → The tasks
  require a DSL removal **and re-import** check, because the reporter's concern —
  that this is format-general — is reasonable and untested.
