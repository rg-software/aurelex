# Building the Russian dictionary (`au_kaikki_ru-ru`)

Source: Russian Wiktionary via kaikki.org (Russian edition). Output: `dist/au_kaikki_ru-ru.dsl.dz` + `dist/au_kaikki_ru-ru.dsl.files.zip`.

## Variables

```powershell
$CACHE  = "C:\Users\Maxim\.cache\aurelex-kaikki"
$OUT    = "dist"
$TAR    = "$CACHE\audio\wiktionary-audios.tar"
$SCRIPT = "scripts\kaikki-to-dsl.py"
$RU_URL = "https://kaikki.org/ruwiktionary/raw-wiktextract-data.jsonl.gz"
```

## Step 1 — prefetch audio (network; resumable)

```powershell
python $SCRIPT prefetch-audio `
    --source-lang ru `
    --jsonl-url $RU_URL `
    --dump-date 2026-09-01 `
    --cache-dir "$CACHE\ru" `
    --audio-tar $TAR `
    --audio-per-word 3
```

Run until exit 0 (`done: every recording that exists is now cached`).

## Step 2 — build (offline once the cache is full)

```powershell
python $SCRIPT `
    --source-lang ru `
    --jsonl-url $RU_URL `
    --dump-date 2026-09-01 `
    --cache-dir "$CACHE\ru" `
    --audio-tar $TAR `
    --audio-per-word 3 `
    --no-audio-download `
    --skip-date-check `
    --name au_kaikki_ru-ru `
    --title "Aurelex Kaikki Ru" `
    --out-dir $OUT
```

Notes:
- `--index-readings` is intentionally omitted: the Russian profile declares no reading tags.
- `--include-inflections` is intentionally omitted for clean suggestions.
- Add `--preview` to also write `au_kaikki_ru-ru.preview.html`.
- The Russian profile keeps aspect (сов./несов.) on the forms line, unlike English, which is the intended monolingual look.
