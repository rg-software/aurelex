# Building the Japanese dictionary (`au_kaikki_ja-ja`)

Source: Japanese Wiktionary via kaikki.org (jawiktionary combined dump, filtered to `ja`). Output: `dist/au_kaikki_ja-ja.dsl.dz` + `dist/au_kaikki_ja-ja.dsl.files.zip`.

## Variables

```powershell
$CACHE  = "C:\Users\Maxim\.cache\aurelex-kaikki"
$OUT    = "dist"
$TAR    = "$CACHE\audio\wiktionary-audios.tar"
$SCRIPT = "scripts\kaikki-to-dsl.py"
$JA_URL = "https://kaikki.org/jawiktionary/raw-wiktextract-data.jsonl.gz"
```

## Step 1 — prefetch audio (network; resumable)

Japanese has almost no pronunciation audio in jawiktionary (~0.08% of entries, 84 of 111,320), so this step is quick and mostly a no-op. Run it for completeness / to capture the few recordings that exist.

Note: an additional audio source (Lingua Libre, via the planned `additional-audio-sources` change) is designed to add ~715 more recordings (~0.72%, ~9x), but that change is not implemented yet — the published dictionary's 0.08% is the current state, and no Lingua Libre cache exists. Once implemented, enable it with the source flag documented in that change and re-run both steps.

```powershell
python $SCRIPT prefetch-audio `
    --source-lang ja `
    --jsonl-url $JA_URL `
    --dump-date 2026-09-01 `
    --cache-dir "$CACHE\ja" `
    --audio-tar $TAR `
    --audio-per-word 3 `
    --skip-date-check
```

## Step 2 — build (offline once the cache is full)

```powershell
python $SCRIPT `
    --source-lang ja `
    --jsonl-url $JA_URL `
    --dump-date 2026-09-01 `
    --cache-dir "$CACHE\ja" `
    --audio-tar $TAR `
    --audio-per-word 3 `
    --skip-date-check `
    --index-readings `
    --name au_kaikki_ja-ja `
    --title "Aurelex Kaikki Ja" `
    --out-dir $OUT
```

Notes:
- `--index-readings` is the flag that adds hiragana lookup keys (e.g. `ほご` reaches `保護`). Coverage is ~76% of kanji headwords; the remaining ~24% (mostly compounds, four-character idioms, abbreviations and named entities) have no reading in jawiktionary and get no key. See the earlier discussion for examples.
- `--no-audio-download` is deliberately NOT passed: it means tar-only *and*
  cache-blind (the prefetched/downloaded cache is never consulted), so it
  would silently drop every recording the bulk archive lacks — for Japanese,
  ~80 of ~85. With a full cache the build makes no network requests anyway
  (sidecar-verified files are reused without a request), so omitting the flag
  is both complete and offline in practice. Pass `--no-audio-download` only
  for a strict tar-only build, accepting the reduced coverage.

Notes:
- `--index-readings` is the flag that adds hiragana lookup keys (e.g. `ほご` reaches `保護`). Coverage is ~76% of kanji headwords; the remaining ~24% (mostly compounds, four-character idioms, abbreviations and named entities) have no reading in jawiktionary and get no key. See the earlier discussion for examples.
- `--include-inflections` is intentionally omitted for clean suggestions. Add it if direct lookup of inflected forms (e.g. `喧伝する`) matters more than clean suggestions.
- The Japanese profile prints readings (音/訓/読み) on the article itself regardless of `--index-readings`.
- Add `--preview` to also write `au_kaikki_ja-ja.preview.html`.

## Rebuild / reuse

- Re-running the build is cheap once the cache is full.
- To rebuild just the bundle: `python $SCRIPT bundle-audio $OUT\au_kaikki_ja-ja.dsl.dz --dump-date 2026-09-01 --audio-tar $TAR --cache-dir "$CACHE\ja" --jsonl-url $JA_URL`.
