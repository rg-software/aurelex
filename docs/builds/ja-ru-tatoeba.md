# Building the Ja→Ru example-sentences dictionary (`au_tatoeba_ja-ru`)

Source: Tatoeba jpn→rus pairs, selected per headword (dedupe → rank →
cap). No equivalents, no audio: headword plus up-to-N sentence pairs
rendered flat. Output: `dist/au_tatoeba_ja-ru.dsl.dz` (+ `.ann`, no bundle).

This is the builder's pairs mode (`--mode pairs`). Design and spec:
`openspec/changes/bilingual-en-ja-ja-ru/`; probe record:
`docs/BILINGUAL-EXPERIMENT.md`.

## Prerequisites

- Python 3.9+ (standard library only). `--all-kaikki` needs only the kaikki
  JA snapshot below.
- Cache populated (see `cache.md`). Variables used below:

```powershell
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-24"                  # pinned Tatoeba export
$SNAP  = "C:\Users\Maxim\.cache\aurelex-kaikki\ja\2026-09-01\raw-wiktextract-data.jsonl.gz"
$SCRIPT = "scripts\bilingual-to-dsl.py"
```

## One-time — fetch the Tatoeba export (pinned date)

Same three-file pattern as the other pairs recipes, with the `jpn-rus`
pair instead:

```powershell
New-Item -ItemType Directory -Force -Path $TAT | Out-Null
curl -sO https://downloads.tatoeba.org/exports/per_language/jpn/jpn_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/jpn/jpn-rus_links.tsv.bz2 --output-dir $TAT
```

Sizes on 2026-10-24: sentences JA ~3.4 MB, RU ~15.5 MB, links ~200 KB
(31,578 pairs) — roughly 1/26 of the eng-rus slice, so expect a thin
dictionary: every 2+-character probe word still resolves, but single-kanji
headwords often match nothing and ship no card.

## Step 0 — sample first

Use a words file (UTF-8, one headword per line) — `--word` mangles
non-Latin text through the Windows console:

```powershell
"寿司`n日本`n学校" | Set-Content -NoNewline -Encoding utf8 words-ja.txt
python $SCRIPT --mode pairs --source-lang ja --target-lang ru --words-file words-ja.txt --preview `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --keep-pairs 3 --out-dir dist-probe --name au_sample_ja-ru --title "Aurelex Sample JA-RU"
Remove-Item words-ja.txt
```

Open the `.preview.html` and check the funnel before the full run.

## Step 1 — build (offline)

```powershell
python $SCRIPT --mode pairs --source-lang ja --target-lang ru --all-kaikki --snapshot $SNAP `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --keep-pairs 5 --out-dir dist --name au_tatoeba_ja-ru --title "Aurelex Tatoeba JA-RU"
```

## Notes

- `--all-kaikki` iterates the ~111k lexical kaikki JA headwords and keeps
  the ~12k with pairs; the rest ship no card. Published build: 12,196
  cards, ~1.5 MB `.dsl.dz`.
- The dictionary carries no audio and no equivalents; provenance names Tatoeba
  CC BY 2.0 FR only. It imports through the same folder import unchanged.
- Rebuilds are deterministic: same inputs yield byte-identical output.

## Verify

Same smoke procedure and Windows-console caveat as in `ja-en-tatoeba.md`.
