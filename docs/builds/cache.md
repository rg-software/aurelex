# Cache layout and sharing

The converter caches everything under `--cache-dir` (default `~/.cache/aurelex-kaikki`).
A single shared layout keeps one copy of the large audio archive and avoids
per-language collisions on dump dates.

## Recommended layout

```
<CACHE>/                            # e.g. C:\Users\Maxim\.cache\aurelex-kaikki
  audio/                            # SHARED across all languages and dump dates
    wiktionary-audios.tar           # 21.9 GB, single copy
    wiktionary-audios.tar.sha256
    wiktionary-audios.tar.keys.txt  # cached member-name index
  en/
    2026-09-02/                    # one dir per dump date
      raw-wiktextract-data.jsonl.gz
      raw-wiktextract-data.jsonl.gz.sha256
      audio-cache/                  # Wikimedia fallback downloads (per language)
      audio-dead.tsv
      audio-missing.tsv             # from prefetch-audio --list (optional)
      audio-missing.shard-*.tsv     # from prefetch-audio --split (optional)
  ru/
    2026-09-01/
      ...
  ja/
    2026-09-01/
      ...
```

## Why this shape

- **The audio archive is one file for everyone.** `wiktionary-audios.tar` is the
  Wikimedia Commons bulk archive; it does not depend on language or dump date.
  Keeping a single copy under `audio/` and pointing every build at it with
  `--audio-tar <CACHE>\audio\wiktionary-audios.tar` saves ~22 GB and lets every
  dictionary build offline.
- **Per-language dirs prevent dump-date collisions.** English and Japanese both
  use dates that can collide with Russian's; nesting under `<lang>/<dump-date>/`
  keeps `--cache-dir "$CACHE\en"` etc. distinct.
- **Audio-cache stays per language.** The downloaded fallback files have global
  MediaWiki names, but the overlap between languages is tiny (a few files), so
  sharing them is not worth the bookkeeping. Keep them under each dump date.
- **Future: additional audio sources.** The planned `additional-audio-sources`
  change (Lingua Libre) is not implemented yet. When it lands, its source index
  cache will live beside the other caches, keyed by source and corpus language,
  independent of the dump date (see that change's design). No such cache exists today.
- **Dead lists and shards are per build.** They encode which recordings were
  gone and which were fetched; they are small and tied to a dump date + options,
  so leave them where the prefetcher wrote them.

## Sharing across machines

1. Put `<CACHE>` on a shared drive (or sync it).
2. On a new machine, point `--cache-dir` and `--audio-tar` at the shared copy.
3. The build needs only the JSONL and the (shared) tar; with `--no-audio-download`
   it makes zero network requests.
4. Only `prefetch-audio` needs the network. Run it once per language on one
   machine (or shard it with `--split N` across several), then share the filled
   `audio-cache/` directories.

## Bilingual caches (En→Ru builders)

Under a separate root so bilingual downloads never collide with the kaikki
tree (different pinning: Tatoeba weekly exports, RuWordNet releases):

```
<BIL>/                                        # e.g. C:\Users\Maxim\.cache\aurelex-bilingual
  tatoeba/<export-date>/                      # one dir per weekly export
    eng_sentences.tsv.bz2                     # ~25 MB
    rus_sentences.tsv.bz2                     # ~15.5 MB
    eng-rus_links.tsv.bz2                     # ~5 MB, pre-joined pair links
```

Downloaded once with the three `curl` lines in `en-ru-wordnet.md` (verified
2026-10-17: 831,236 pairs). A new export is a new dated directory; the date
travels into provenance. Re-runs and re-builds reuse these files — nothing is
re-downloaded.

| Input | Where it lives | Shared with |
| --- | --- | --- |
| kaikki EN snapshot (`.jsonl.gz`) | `<CACHE>\en\<dump-date>\` | kaikki EN build (read-only here) |
| bulk audio tar | `<CACHE>\audio\wiktionary-audios.tar` | kaikki builds (read-only here) |
| per-language audio cache | `<CACHE>\en\<dump-date>\audio-cache\` | filled by the kaikki EN prefetch; bilingual audio reuses fetched files, may add its own downloads |
| Tatoeba export | `<BIL>\tatoeba\<date>\` | both bilingual recipes |
| RuWordNet sqlite (~80 MB) | `python-ruwordnet` package `static\` dir | one `ruwordnet download`; reused by every build |
| English lemma universe | derived from the RuWordNet EN subset (`--all-lemmas`) | computed, not stored |

Rules: never re-download what the pinned files already hold; never write into
kaikki per-language state from a bilingual run except the shared audio-cache
(which is append-only by design — sidecar-verified downloads are reused).
Builder outputs (`dist/`, previews) are disposable; caches are not.

## Backup (single archive)

The caches live under several top-level directories
(`~/.cache/aurelex-kaikki`, `~/.cache/aurelex-bilingual`, ...), which is
correct per the shared-cache convention but awkward to back up as several
sync-library roots. `scripts/backup-cache.ps1` traverses every
`~/.cache/aurelex-*` directory and writes ONE archive plus a SHA-256
sidecar, so there is a single backup unit to store:

```powershell
pwsh -File scripts/backup-cache.ps1                       # ~/aurelex-cache-backup-<date>.tar
pwsh -File scripts/backup-cache.ps1 -Compress -Out D:\backups\aurelex-cache.tar.gz
```

The default is a plain `.tar` (store-only): the big blobs are already
compressed, so gzip would spend an hour of CPU for ~zero bytes saved.
Paths inside the archive are relative to `~/.cache`, so a restore lands
back where the builders look:

```powershell
tar -xf ~/aurelex-cache-backup-2026-10-24.tar -C ~/.cache
```

Nothing is deleted or modified by a backup run. Re-run after a prefetch or
a resolve-cache refresh; builder outputs need no backup.

## Reorganization performed (2026-10-21)

- Moved one copy of `wiktionary-audios.tar` (+ `.sha256`, `.keys.txt`) to
  `audio/`; deleted the duplicate.
- Moved `2026-09-02/` to `en/2026-09-02/` and `2026-09-01/` to
  `ru/2026-09-01/` (the latter is the Russian edition).
- Deleted the incomplete `wiktionary-audios.tar.part` files under `ja/` and
  `local/` (the shared complete tar replaces them).
- Verified the shared tar's sha256 against its sidecar.

## Disk saved

- Duplicate audio tar: ~21.9 GB.
- Incomplete partial downloads: ~1.6 GB.
