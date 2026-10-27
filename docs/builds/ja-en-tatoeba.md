# Building the Ja→En example-sentences dictionary (`au_tatoeba_ja-en`)

Source: Tatoeba jpn→eng pairs (the same per-pair export as `en-ja-tatoeba.md`,
read in the reverse direction), selected per headword (dedupe → rank →
cap). No equivalents, no audio: headword plus up-to-N sentence pairs rendered
flat. Output: `dist/au_tatoeba_ja-en.dsl.dz` (+ `.ann`, no bundle).

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

The Tatoeba export is the same three files as `en-ja-tatoeba.md` (shared
cache — download once); `--target-lang en` reads the same links file in
the reverse direction, so no second export is needed.

## Step 0 — sample first

Use a words file (UTF-8, one headword per line) — `--word` mangles
non-Latin text through the Windows console:

```powershell
"寿司`n日本`n学校" | Set-Content -NoNewline -Encoding utf8 words-ja.txt
python $SCRIPT --mode pairs --source-lang ja --target-lang en --words-file words-ja.txt --preview `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --keep-pairs 3 --out-dir dist-probe --name au_sample_ja-en --title "Aurelex Sample JA-EN"
Remove-Item words-ja.txt
```

Open the `.preview.html` and check the funnel before the full run.
Japanese matching is substring-based (no word boundaries); single-kanji
headwords are matched, unlike the English one-letter ban.

## Step 1 — build (offline)

```powershell
python $SCRIPT --mode pairs --source-lang ja --target-lang en --all-kaikki --snapshot $SNAP `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --keep-pairs 5 --out-dir dist --name au_tatoeba_ja-en --title "Aurelex Tatoeba JA-EN"
```

## Notes

- `--all-kaikki` iterates the ~111k lexical kaikki JA headwords and keeps
  the ~29k with pairs; the rest ship no card. Published build: 28,639
  cards, ~4.1 MB `.dsl.dz`.
- The dictionary carries no audio and no equivalents; provenance names Tatoeba
  CC BY 2.0 FR only. It imports through the same folder import unchanged.
- Rebuilds are deterministic: same inputs yield byte-identical output.

## Verify

Run the smoke tool over the output folder (any word — the scan, the index
build, and the markup check do not depend on it):

```powershell
.\build-gh\Release\aurelex_smoke.exe <cfg-dir> dist smoke
```

The run must index the dictionary with no `unclosed` / `Unknown tag`
warnings. A full `gd_lookup` of a non-Latin headword is not possible from
the Windows console (the test harness receives `argv` through the ANSI
code page — unrelated to the dictionary or to on-device lookup, where
strings stay UTF-16 end to end); verify Japanese headwords by article
shape in the `.preview.html` sample and, finally, on device.
