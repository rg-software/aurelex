# Building the English dictionary (`au_kaikki_en-en`)

Source: English Wiktionary via kaikki.org. Output: `dist/au_kaikki_en-en.dsl.dz` + `dist/au_kaikki_en-en.dsl.files.zip`.

## Prerequisites

- Python 3.9+ (standard library only).
- Cache populated (see `cache.md`). Variables used below:

```powershell
$CACHE  = "C:\Users\Maxim\.cache\aurelex-kaikki"   # or your shared location
$OUT    = "dist"
$TAR    = "$CACHE\audio\wiktionary-audios.tar"
$SCRIPT = "scripts\kaikki-to-dsl.py"
```

## One-time: verify the shared audio archive

```powershell
python $SCRIPT bundle-audio --help | Out-Null   # sanity check CLI
# verify the tar's sha256 matches audio\wiktionary-audios.tar.sha256
```

## Step 1 — prefetch audio (network; resumable)

Run until it reports `done: every recording that exists is now cached` (exit 0).
Safe to repeat; already-cached files are skipped.

```powershell
python $SCRIPT prefetch-audio `
    --source-lang en `
    --dump-date 2026-09-02 `
    --cache-dir "$CACHE\en" `
    --audio-tar $TAR `
    --audio-per-word 3 `
    --audio-lang US
```

For a multi-machine pool, plan shards instead of fetching here:

```powershell
python $SCRIPT prefetch-audio `
    --source-lang en --dump-date 2026-09-02 `
    --cache-dir "$CACHE\en" --audio-tar $TAR `
    --audio-per-word 3 --audio-lang US `
    --split 4
# then on each worker:
#   python $SCRIPT fetch-list "$CACHE\en\2026-09-02\audio-missing.shard-01-of-04.tsv" --into .\fetch-01
# copy filled dirs into $CACHE\en\2026-09-02\audio-cache\ and re-run prefetch-audio to check.
```

## Step 2 — build (offline once the cache is full)

```powershell
python $SCRIPT `
    --source-lang en `
    --dump-date 2026-09-02 `
    --cache-dir "$CACHE\en" `
    --audio-tar $TAR `
    --audio-per-word 3 `
    --audio-lang US `
    --no-audio-download `
    --skip-date-check `
    --name au_kaikki_en-en `
    --title "Aurelex Kaikki English" `
    --out-dir $OUT
```

Notes:
- `--index-readings` is intentionally omitted: the English profile declares no reading tags, so it would be a no-op.
- `--include-inflections` is intentionally omitted for clean suggestions (add it if direct lookup of inflected forms matters more).
- Drop `--no-audio-download` if you want the build to fetch missing files itself instead of relying on the prefetched cache.
- Add `--preview` to also write `au_kaikki_en-en.preview.html`.

## Rebuild / reuse

- Re-running the build is cheap (CPU + local archive I/O only) once the cache is full.
- `--reuse-bundle` reuses an existing `.files.zip` beside the dictionary instead of rebuilding it; only use it when only the text changed, and verify the bundle covers every referenced resource.
- To rebuild just the bundle from an existing dictionary: `python $SCRIPT bundle-audio $OUT\au_kaikki_en-en.dsl.dz --dump-date 2026-09-02 --audio-tar $TAR --cache-dir "$CACHE\en"`.
