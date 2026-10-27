# Building the En→Ja example-sentences dictionary (`au_tatoeba_en-ja`)

Source: Tatoeba eng→jpn pairs, selected per headword (dedupe → rank → cap).
No equivalents, no audio: headword plus up-to-N sentence pairs rendered flat
(the pairs are the whole article, never collapsed). Output:
`dist/au_tatoeba_en-ja.dsl.dz` (+ `.ann`, no bundle).

This is the builder's pairs mode (`--mode pairs`). Design and spec:
`openspec/changes/bilingual-en-ja-ja-ru/`; probe record:
`docs/BILINGUAL-EXPERIMENT.md`.

## Prerequisites

- Python 3.9+ (standard library only). `--all-kaikki` needs only the kaikki
  snapshot below. Any `--words-file` works with no extra dependency.
- Cache populated (see `cache.md`). Variables used below:

```powershell
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-24"                  # pinned Tatoeba export
$SNAP  = "C:\Users\Maxim\.cache\aurelex-kaikki\en\2026-09-02\raw-wiktextract-data.jsonl.gz"
$SCRIPT = "scripts\bilingual-to-dsl.py"
```

## One-time — fetch the Tatoeba export (pinned date)

```powershell
New-Item -ItemType Directory -Force -Path $TAT | Out-Null
curl -sO https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/jpn/jpn_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/eng/eng-jpn_links.tsv.bz2 --output-dir $TAT
```

Sizes on 2026-10-24: sentences EN ~25 MB, JA ~3.4 MB, links ~1.4 MB (280,551 pairs).

## Step 0 — sample first

```powershell
python $SCRIPT --mode pairs --word dog --word sushi --word love --sample 25 --sample-mode first --preview `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --keep-pairs 3 --out-dir dist-probe --name au_sample_en-ja --title "Aurelex Sample EN-JA"
```

Open `dist-probe/au_sample_en-ja.preview.html` and check the funnel (dedupe
on both sides, shortest-first, keep 3) before the full run.

## Step 1 — build (offline)

```powershell
python $SCRIPT --mode pairs --source-lang en --target-lang ja --all-kaikki --snapshot $SNAP `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --keep-pairs 5 --out-dir dist --name au_tatoeba_en-ja --title "Aurelex Tatoeba EN-JA"
```

## Notes

- `--all-kaikki` iterates the lexical kaikki EN headwords and keeps the
  ~32k with pairs; the rest ship no card. Published build: 32,358 cards,
  ~4.4 MB `.dsl.dz`.
- Every headword ships 1–5 pairs — article size scales with headwords, never
  with the pair total. Headwords must start with a letter (stray quotes,
  suffix fragments and bare numbers are dropped and counted).
- A translation whose target duplicates an already-kept one is skipped, so
  the same Japanese sentence never repeats under one headword; single-kanji
  headwords are exempt from the single-character ban (a kanji is a word).
- The dictionary carries no audio and no equivalents; provenance names Tatoeba
  CC BY 2.0 FR only. It imports through the same folder import unchanged.
- Rebuilds are deterministic: same inputs yield byte-identical output.

## Verify

```powershell
.\build-gh\Release\aurelex_smoke.exe <cfg-dir> dist dog
```

`gd_lookup("dog")` must return the pairs article with no `unclosed`/`Unknown tag`
warnings (same smoke-tool caveat as in `en-ru-wordnet.md`).
