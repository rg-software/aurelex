# Building the Ru→En example-sentences dictionary (`au_tatoeba_ru-en`)

Source: Tatoeba rus→eng pairs (the same pinned export as en→ru),
selected per headword (dedupe → rank → cap). No equivalents, no audio:
headword plus up-to-N sentence pairs rendered flat. Output:
`dist/au_tatoeba_ru-en.dsl.dz` (+ `.ann`, no bundle).

This is the builder's pairs mode with `--source-lang ru`
(`--mode pairs --source-lang ru`). Design and spec:
`openspec/changes/bilingual-ru-en-pairs/`; probe record:
`docs/BILINGUAL-EXPERIMENT.md`.

## Prerequisites

- Python 3.9+ (standard library only). Any `--words-file` works with no
  extra dependency; `--all-kaikki` needs only the kaikki RU snapshot below.
- Cache populated (see `cache.md`). Variables used below:

```powershell
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-17"                  # pinned Tatoeba export (shared with en→ru)
$SNAP  = "C:\Users\Maxim\.cache\aurelex-kaikki\ru\2026-09-01\raw-wiktextract-data.jsonl.gz"
$SCRIPT = "scripts\bilingual-to-dsl.py"
```

The Tatoeba export is the same three files as the en→ru recipes (shared
cache — download once). The kaikki snapshot is the RU one the `ru-ru`
monolingual build uses (dump date 2026-09-01, ~307 MB), holding ~468k
lexical headwords.

## Step 0 — sample first

```powershell
python $SCRIPT --mode pairs --source-lang ru --all-kaikki --snapshot $SNAP `
  --kaikki-dump-date 2026-09-01 --tatoeba-dir $TAT --tatoeba-date 2026-10-17 `
  --sample 200 --sample-mode random --preview `
  --keep-pairs 5 --out-dir dist-sample-ruen --name au_sample_ru-en --title "Aurelex Sample RU-EN"
```

Open `dist-sample-ruen/au_sample_ru-en.preview.html` and check the shape
(`[ex]` Russian example / `[trn]` English translation, flat, no zone)
before the full run. The 200-sample keeps roughly a dozen cards (about 1
in 20 headwords has pairs — same density as en→ru).

## Step 1 — build (offline)

```powershell
python $SCRIPT --mode pairs --source-lang ru --all-kaikki --snapshot $SNAP `
  --kaikki-dump-date 2026-09-01 --tatoeba-dir $TAT --tatoeba-date 2026-10-17 `
  --keep-pairs 5 --out-dir dist --name au_tatoeba_ru-en --title "Aurelex Tatoeba RU-EN"
```

## Notes

- `--all-kaikki` iterates the lexical kaikki RU headwords (~468k; needs
  `--snapshot $SNAP`) and keeps those with pairs; the rest ship no card.
  Expect low tens of thousands of cards at the sampled density.
- Every rule is the en→ru one, mirrored: pairs match the Russian side with
  the Russian tokenizer; dedupe keys on the Russian text; headwords must
  start with a letter (stray quotes, suffix fragments and bare numbers are
  dropped and counted); headwords differing only in case merge into one
  card, keeping the lowercase form when the pairs spell it lowercase and
  the capitalized form otherwise; single-character headwords match nothing.
- The dictionary carries no audio and no equivalents; provenance names
  Tatoeba rus-eng pairs, CC BY 2.0 FR only. It imports through the same
  folder import unchanged.
- Rebuilds are deterministic: same inputs yield byte-identical output
  (`random` sampling spreads by sha256 key, so re-runs agree).

## Verify

```powershell
.\build-gh\Release\aurelex_smoke.exe <cfg-dir> dist хлеб
```

`gd_lookup("хлеб")` must return the pairs article with no `unclosed`/`Unknown tag`
warnings (same smoke-tool caveat as in `en-ru-wordnet.md`).
