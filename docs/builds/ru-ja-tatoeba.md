# Building the Ru→Ja example-sentences dictionary (`au_tatoeba_ru-ja`)

Source: Tatoeba rus→jpn pairs (the same per-pair export as
`ja-ru-tatoeba.md`, read in the reverse direction), selected per headword
(dedupe → rank → cap). No equivalents, no audio: headword plus up-to-N
sentence pairs rendered flat. Output:
`dist/au_tatoeba_ru-ja.dsl.dz` (+ `.ann`, no bundle).

This is the builder's pairs mode (`--mode pairs`). Design and spec:
`openspec/changes/bilingual-en-ja-ja-ru/`; probe record:
`docs/BILINGUAL-EXPERIMENT.md`.

## Prerequisites

- Python 3.9+ (standard library only). `--all-kaikki` needs only the kaikki
  RU snapshot below.
- Cache populated (see `cache.md`). Variables used below:

```powershell
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-24"                  # pinned Tatoeba export
$SNAP  = "C:\Users\Maxim\.cache\aurelex-kaikki\ru\2026-09-01\raw-wiktextract-data.jsonl.gz"
$SCRIPT = "scripts\bilingual-to-dsl.py"
```

The Tatoeba export is the same three files as `ja-ru-tatoeba.md` (shared
cache — download once); `--target-lang ja` reads the same links file in
the reverse direction, so no second export is needed.

## Step 0 — sample first

```powershell
'хлеб','вода','книга','собака' | Set-Content -NoNewline -Encoding utf8 words-ru.txt
python $SCRIPT --mode pairs --source-lang ru --target-lang ja --words-file words-ru.txt --preview `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --keep-pairs 3 --out-dir dist-probe --name au_sample_ru-ja --title "Aurelex Sample RU-JA"
Remove-Item words-ru.txt
```

Open the `.preview.html` and check the funnel before the full run.

## Step 1 — build (offline)

```powershell
python $SCRIPT --mode pairs --source-lang ru --target-lang ja --all-kaikki --snapshot $SNAP `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --keep-pairs 5 --out-dir dist --name au_tatoeba_ru-ja --title "Aurelex Tatoeba RU-JA"
```

## Notes

- `--all-kaikki` iterates the ~462k lexical kaikki RU headwords and keeps
  the ~7.6k with pairs; the rest ship no card. Published build: 7,606
  cards, ~1 MB `.dsl.dz`.
- The dictionary carries no audio and no equivalents; provenance names Tatoeba
  CC BY 2.0 FR only. It imports through the same folder import unchanged.
- Rebuilds are deterministic: same inputs yield byte-identical output.

## Verify

Same smoke procedure and Windows-console caveat as in `ja-en-tatoeba.md`.
