## Context

`build()` writes `<out>/<name>.dsl.dz` at `kaikki-to-dsl.py:2252` and only then
assembles the resource bundle in a temporary directory (`:2264`), finally
writing `<name>.dsl.files.zip` (or `.files/`). The set of recordings to bundle —
`audio.referenced` and the archive-key aliases in `audio.aliases` — is built in
memory while rendering, so when bundling fails the process dies holding it, and
there is no command that can reproduce just that step. The rendered dictionary,
however, is on disk and every recording it wants appears in it as a
`[s]name[/s]` link, which is enough to rebuild the bundle.

This change adds that rebuild, reachable as a `bundle-audio` mode word beside
`prefetch-audio` and `fetch-list`.

## Goals / Non-Goals

**Goals**

- Rebuild `<base>.dsl.files.zip` (or `.files/`) from an existing `.dsl.dz`
  without re-rendering and without reading the JSONL snapshot.
- Produce a bundle indistinguishable from the one a successful build writes for
  the same dictionary: same filenames, same layout, same icons.
- Keep the dictionary and its bundle consistent when a filename has to be made
  filesystem-safe, so no `[s]` link points at a file that is not there.
- Make the operation offline when a local audio archive is given, and safe to
  repeat.

**Non-Goals**

- No resumption of a partially-written `.dsl.dz`; the mode only finishes the
  bundle for a dictionary that was written completely.
- No re-planning of which recordings an article gets; the dictionary has already
  decided, and the mode trusts it.
- No preview regeneration and no change to the build or prefetch behavior.

## Decisions

### D1: The dictionary's `[s]` references are the source of truth

The recordings to bundle are read from the `.dsl.dz` itself, not re-derived from
the snapshot. Re-deriving would mean reading records and re-running the exact
planning (per-word cap, language preference, collision disambiguation) that
produced the dictionary, which is the expensive render this mode exists to
avoid, and could drift from what the dictionary actually contains. Parsing the
links is exact: a link exists only because the build chose that recording.

References are matched with a non-greedy `\[s\](.*?)\[/s\]` and the captured
name is un-escaped (`\[`, `\]`, `\\`, `\<\<`, `\>\>`, the inverse of
`escape_dsl`). Because `escape_dsl` escapes `[` and `]`, a name cannot contain a
bare `[/s]`, so the non-greedy match cannot stop early.

### D2: Sanitise, and rewrite only when a reference changes

Each referenced name is put through the same `_safe_audio_filename` a build uses,
so the bundle a rebuild writes matches what a build would write. When that
changes the name, the dictionary is re-encoded with the reference updated;
otherwise it is written back unchanged. Rewriting only on change keeps the
common case a pure read of the dictionary, and keeps the guarantee that a
rebuilt dictionary equals a freshly built one.

### D3: Reuse the build's primitives

`_audio_name_variants` derives the archive keys from a name,
`extract_audio` streams the tar into the temporary bundle directory, and
`write_audio_zip`/the directory branch write it out — the same code a build
uses, so the layout, ordering and zip metadata cannot diverge. A small
`read_dictzip` (gzip-decode and drop the BOM; dictzip is gzip-compatible for a
full read) is added, since only the writer existed.

### D4: Cache first, then archive

A recording that the archive lacked was downloaded into the cache and never
entered the tar, so the cache is checked first for each name; a hit is copied
and the name is dropped from the set handed to `extract_audio`. This mirrors the
build, which copies `audio.local` before streaming the archive.

### D5: Resolve only the cache location and the archive

The mode needs the audio tar and the cache directory, nothing else. It builds
the same `Snapshot` the build uses from `--dump-date` (or the `local` marker when
`--jsonl` is passed) and `--cache-dir`, but skips the dump-date check against
kaikki.org and never downloads the JSONL, so it works offline. `--audio-tar`
avoids even resolving the archive by URL.

### D6: Digest-suffixed names are resolved best-effort

`AudioPlan._final_name` disambiguates two sources that share a basename by
inserting an eight-hex digest before the extension. Such a name has no archive
key of its own — the plain basename is the key — so for an unresolved name the
mode also tries `_audio_name_variants` on the name with that suffix removed.
A name that still cannot be located is reported and omitted, like a name missing
from the archive in a build.

### D7: A missing file is a warning, not a failure

Matching the build's bundling step, a recording that cannot be found is counted
and warned about, and the bundle is written without it. A rebuild is a recovery
tool; refusing to produce anything because one recording is unfindable would be
worse than producing the bundle and saying what is missing.

## Risks / Trade-offs

- **The dictionary may reference a recording that no longer exists.** Then the
  rebuild cannot recover it; it warns and omits it, exactly as a build would when
  the archive is missing a member. The user sees the same missing count a build
  would report.
- **Rewriting the `.dsl.dz` changes the dictionary file.** This is deliberate —
  it is the only way a name illegal on the filesystem can be bundled and still
  referenced — and it is limited to dictionaries that actually carry such a name.
  The rewrite is a full re-encode of the same text, so nothing else changes.
- **Extracting the references cannot tell the per-word cap.** It does not need
  to: the dictionary already reflects the cap.

## Migration Plan

None. A new mode word; existing invocations are unchanged.
