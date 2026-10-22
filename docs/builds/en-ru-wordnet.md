# Building the En→Ru translation dictionary (`au_wordnet_en-ru`)

Source: Princeton WordNet + RuWordNet `ili` links (equivalents, Russian definitions),
Tatoeba eng→rus pairs (one anchored example per sense), kaikki EN audio (verbatim reuse).
Output: `dist/au_wordnet_en-ru.dsl.dz` + `dist/au_wordnet_en-ru.dsl.files.zip` (+ `.ann`).

This is the builder's full mode (`--mode translation`). Design and spec:
`openspec/changes/bilingual-dictionary/`; probe record: `docs/BILINGUAL-EXPERIMENT.md`.

## Prerequisites

- Python 3.9+ (standard library only at runtime) plus the `ruwordnet` package with
  its database (one-time, ~80 MB):

```powershell
pip install ruwordnet
ruwordnet download
```

- Cache populated (see `cache.md`). Variables used below:

```powershell
$CACHE = "C:\Users\Maxim\.cache\aurelex-kaikki"     # kaikki cache (shared, read-only here)
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-17"                  # pinned Tatoeba export
$TAR   = "$CACHE\audio\wiktionary-audios.tar"       # shared bulk audio archive
$SNAP  = "$CACHE\en\2026-09-02\raw-wiktextract-data.jsonl.gz"
$ACACHE = "$CACHE\en\2026-09-02\audio-cache"        # filled by the kaikki EN prefetch
$SCRIPT = "scripts\bilingual-to-dsl.py"
```

## One-time — fetch the Tatoeba export (pinned date, ~45 MB)

```powershell
New-Item -ItemType Directory -Force -Path $TAT | Out-Null
curl -sO https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/eng/eng-rus_links.tsv.bz2 --output-dir $TAT
```

Sizes on 2026-10-17: sentences EN ~25 MB, RU ~15.5 MB, links ~5 MB (831,236 pairs).
The date is part of the path and of provenance — a new export is a new directory.

## Step 0 — sample first (offline except audio fetch)

```powershell
python $SCRIPT --mode translation --all-lemmas --sample 25 --sample-mode first --preview `
  --snapshot $SNAP --kaikki-dump-date 2026-09-02 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-17 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 --audio-lang US `
  --out-dir dist --name au_wordnet_en-ru --title "Aurelex WordNet EN-RU"
```

Open `dist/au_wordnet_en-ru.preview.html` and check article shape
(RU definitions, `[trn]` equivalents, zoned examples, `[s]` audio) before the full run.

## Step 1 — build (offline once the cache is full)

```powershell
python $SCRIPT --mode translation --all-lemmas `
  --snapshot $SNAP --kaikki-dump-date 2026-09-02 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-17 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 --audio-lang US `
  --out-dir dist --name au_wordnet_en-ru --title "Aurelex WordNet EN-RU"
```

The build exits non-zero if any audio reference would not resolve — fix the
cache (re-run the kaikki EN prefetch), do not ship around it.

## Audio and cache reuse notes

- No separate audio prefetch: the build reuses the kaikki EN stage verbatim —
  the same snapshot, archive, and per-language `audio-cache` the `en.md` build
  fills. First build may download recordings the archive lacks into
  `--audio-cache-dir` (sidecar-verified, reused after); re-runs are offline.
- `--audio-lang US` matches the kaikki EN build, so each headword carries the
  same recordings there. A headword silent in `au_kaikki_en-en` is silent here.
- `--no-audio` skips the snapshot and the archive entirely (then `--snapshot`
  is not needed); the dictionary still imports, without pronunciations.
- Rebuilds are deterministic: same inputs yield byte-identical output.

## Verify

```powershell
# import check through the real reader (needs the host smoke build, see below)
.\build-gh\Release\aurelex_smoke.exe <cfg-dir> dist give
```

`gd_lookup("give")` must return the full article with no `unclosed`/`Unknown tag`
warnings. (The smoke tool's own fixture asserts fail against a non-fixture
folder — only the dictionary's own lines matter.)
