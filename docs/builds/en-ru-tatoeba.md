# Building the En→Ru example-sentences dictionary (`au_tatoeba_en-ru`)

Source: Tatoeba eng→rus pairs, selected per headword (dedupe → rank → cap).
No equivalents, no audio: headword plus up-to-N sentence pairs in one
collapsible zone. Output: `dist/au_tatoeba_en-ru.dsl.dz` (+ `.ann`, no bundle).

This is the builder's pairs mode (`--mode pairs`). Design and spec:
`openspec/changes/bilingual-dictionary/` (D6); probe record:
`docs/BILINGUAL-EXPERIMENT.md`.

## Prerequisites

- Python 3.9+ (standard library only). For `--all-lemmas` only: the `ruwordnet`
  package with its database (one-time, `pip install ruwordnet` + `ruwordnet download`);
  otherwise any `--words-file` works with no extra dependency.
- Cache populated (see `cache.md`). Variables used below:

```powershell
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-17"                  # pinned Tatoeba export
$SCRIPT = "scripts\bilingual-to-dsl.py"
```

## One-time — fetch the Tatoeba export (pinned date, ~45 MB)

Same three files as the wordnet recipe (shared cache — download once):

```powershell
New-Item -ItemType Directory -Force -Path $TAT | Out-Null
curl -sO https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/eng/eng-rus_links.tsv.bz2 --output-dir $TAT
```

Sizes on 2026-10-17: sentences EN ~25 MB, RU ~15.5 MB, links ~5 MB (831,236 pairs).

## Step 0 — sample first

```powershell
python $SCRIPT --mode pairs --words-file words.txt --sample 25 --sample-mode first --preview `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-17 `
  --keep-pairs 3 --out-dir dist --name au_tatoeba_en-ru --title "Aurelex Tatoeba EN-RU"
```

Open `dist/au_tatoeba_en-ru.preview.html` and check the funnel (dedupe → anchored
preference → shortest, keep 3) before the full run.

## Step 1 — build (offline)

```powershell
python $SCRIPT --mode pairs --all-lemmas `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-17 `
  --keep-pairs 3 --out-dir dist --name au_tatoeba_en-ru --title "Aurelex Tatoeba EN-RU"
```

## Notes

- Every headword ships 1–3 pairs (or none, if Tatoeba has no sentence containing
  it) — article size scales with headwords, never with the 831k pair total.
- The dictionary carries no audio and no equivalents; provenance names Tatoeba
  CC BY 2.0 FR only. It imports through the same folder import unchanged.
- Rebuilds are deterministic: same inputs yield byte-identical output.

## Verify

```powershell
.\build-gh\Release\aurelex_smoke.exe <cfg-dir> dist bread
```

`gd_lookup("bread")` must return the pairs article with no `unclosed`/`Unknown tag`
warnings (same smoke-tool caveat as in `en-ru-wordnet.md`).
