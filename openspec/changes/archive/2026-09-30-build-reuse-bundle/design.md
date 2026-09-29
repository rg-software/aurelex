## Context

`build()` always assembles the resource bundle after rendering
(`kaikki-to-dsl.py:2386`): it resolves the audio archive, copies cache hits and
extracts archive members into a temp directory, and writes `<base>.dsl.files.zip`.
For a full English dictionary that is tens of thousands of files and the bulk of
a run's wall time. When the only change is to the dictionary text — pruning
definition-less cards, merging split headwords — the set of recordings the
dictionary references can only shrink, so the bundle already on disk still
covers it.

## Goals / Non-Goals

**Goals**

- A `--reuse-bundle` option that renders the dictionary and leaves the existing
  bundle untouched.
- A verification that the reused bundle covers every referenced resource, and a
  clear report when it does not.

**Non-Goals**

- No incremental bundle update (adding only newly-referenced files); the option
  is all-or-nothing and the fallback is a normal rebuild.
- No change to the default behaviour: without the option the bundle is rebuilt.

## Decisions

### D1: The flag skips only the write, not the planning

Audio references are decided during rendering and depend on which recordings the
archive holds, so the run still resolves the archive and its cached name index
and still plans audio per card; only the bundle assembly and write are skipped.
This is what keeps the produced `.dsl.dz` identical to a normal build's.

### D2: Reuse is verified, not assumed

After rendering, the set of names the bundle must hold is exactly the `sources`
map a rebuild would have written (the icons plus every resolved recording). The
existing bundle's entry names are read — the zip central directory, or the
directory listing — and compared; any name in `sources` that is absent is
reported, and an absent bundle is reported as such. The comparison is cheap: it
reads the zip's index, never its contents.

### D3: Missing resources are a warning, not a failure

A rebuild is a render-only convenience; if the bundle is incomplete the user
should re-run without the flag, which the warning says. Failing the run would
lose the rendered dictionary over a resource the user can recover.

## Risks / Trade-offs

- **A renamed recording would not be caught by a name-only check if the old name
  is still present.** Names are derived deterministically, and merging can only
  change a name in a rare basename collision; the check compares the exact names
  the new dictionary references, so a renamed file shows up as missing under its
  new name and is reported.
- **The bundle may hold supersets.** Reuse keeps files the pruned cards no longer
  reference; they are harmless and are not removed, which keeps the option a pure
  read of the existing bundle.
