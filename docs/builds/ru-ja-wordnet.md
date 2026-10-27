# Building the Ru→Ja translation dictionary (`au_wordnet_ru-ja`)

Source: RuWordNet synsets bridged to Japanese WordNet through the shared
Princeton WordNet id (the PWN-ID pivot: each JaWN entry with the same id
is one sense with Japanese member lemmas and definitions), Tatoeba
rus→jpn pairs (one anchored example per sense), kaikki RU audio (verbatim
reuse). Output: `dist/au_wordnet_ru-ja.dsl.dz` +
`dist/au_wordnet_ru-ja.dsl.files.zip` (+ `.ann`).

This is the builder's pivot mode (`--mode translation --source-lang ru
--target-lang ja`). Design and spec:
`openspec/changes/bilingual-en-ja-ja-ru/`; probe record:
`docs/BILINGUAL-EXPERIMENT.md` (JaWN appendix).

## Prerequisites

- Python 3.9+ (standard library only at runtime) plus the `wn` and
  `ruwordnet` packages with their data (one-time, see `ja-ru-wordnet.md`).
- Cache populated (see `cache.md`). Variables used below:

```powershell
$CACHE = "C:\Users\Maxim\.cache\aurelex-kaikki"     # kaikki cache (shared, read-only here)
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-24"                  # pinned Tatoeba export
$TAR   = "$CACHE\audio\wiktionary-audios.tar"       # shared bulk audio archive
$SNAP  = "$CACHE\ru\2026-09-01\raw-wiktextract-data.jsonl.gz"
$ACACHE = "$CACHE\ru\2026-09-01\audio-cache"        # filled by the kaikki RU prefetch
$SCRIPT = "scripts\bilingual-to-dsl.py"
```

The Tatoeba export is the same three-file set as `ja-ru-wordnet.md`
(shared cache — download once).

## Step 0 — sample first (offline except audio fetch)

```powershell
'хлеб','вода','книга','собака' | Set-Content -NoNewline -Encoding utf8 words-ru.txt
python $SCRIPT --mode translation --source-lang ru --target-lang ja --words-file words-ru.txt --preview `
  --snapshot $SNAP --kaikki-dump-date 2026-09-01 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 `
  --out-dir dist-sample-ruja --name au_sample_ru-ja --title "Aurelex Sample RU-JA"
Remove-Item words-ru.txt
```

Open the `.preview.html` and check article shape (Japanese POS labels,
`[trn]` equivalents common-first by phrase-count ranking, Japanese
definitions, `[t]` transcriptions, zoned examples, `[s]` audio) before the
full run. There is no `--audio-lang` flag here: that filter is English-only.

## Step 1 — build (offline once the cache is full)

```powershell
python $SCRIPT --mode translation --source-lang ru --target-lang ja --all-kaikki `
  --snapshot $SNAP --kaikki-dump-date 2026-09-01 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 `
  --resolve-cache $BIL\resolve-ru-ja.json `
  --out-dir dist --name au_wordnet_ru-ja --title "Aurelex WordNet RU-JA"
```

`--all-kaikki` iterates the ~462k lexical kaikki RU headwords and keeps
the ones whose RuWordNet synsets hit the PWN-ID pivot (~28k cards in the
published build, ~3.1 MB `.dsl.dz`). The build exits non-zero if any audio
reference would not resolve.

## License note

As in `ja-ru-wordnet.md`: RuWordNet participates, so the whole dictionary
is for non-commercial use and distribution only, with attribution to
Princeton WordNet, RuWordNet, Japanese WordNet, and Tatoeba.

## Verify

Run the smoke tool over the output folder (any word — the scan, the index
build, and the markup check do not depend on it):

```powershell
.\build-gh\Release\aurelex_smoke.exe <cfg-dir> dist smoke
```

The run must index the dictionary with no `unclosed` / `Unknown tag`
warnings. A full `gd_lookup` of a non-Latin headword is not possible from
the Windows console (the test harness receives `argv` through the ANSI
code page, so Cyrillic headwords arrive mangled — unrelated to the
dictionary or to on-device lookup, where strings stay UTF-16 end to end);
the same engine path is fully exercised by the En→Ja `dog` lookup, which
returns Japanese content with working audio and expanders. Verify Russian
headwords by article shape in the `.preview.html` sample and, finally, on
device.
