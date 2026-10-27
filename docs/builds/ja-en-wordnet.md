# Building the Ja→En translation dictionary (`au_wordnet_ja-en`)

Source: Japanese WordNet synsets bridged to Princeton WordNet via shared
synset IDs (English equivalents, verbatim PWN glosses as definitions),
Tatoeba jpn→eng pairs (one anchored example per sense), kaikki JA audio
(verbatim reuse, such as it is). Output:
`dist/au_wordnet_ja-en.dsl.dz` + `dist/au_wordnet_ja-en.dsl.files.zip`
(+ `.ann`).

This is the builder's reverse translation mode (`--mode translation
--source-lang ja --target-lang en`). Design and spec:
`openspec/changes/bilingual-en-ja-ja-ru/`; probe record:
`docs/BILINGUAL-EXPERIMENT.md` (JaWN appendix).

## Prerequisites

- Python 3.9+ (standard library only at runtime) plus the `wn` package with
  its data (one-time; see `en-ja-wordnet.md`).
- Cache populated (see `cache.md`). Variables used below:

```powershell
$CACHE = "C:\Users\Maxim\.cache\aurelex-kaikki"     # kaikki cache (shared, read-only here)
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-24"                  # pinned Tatoeba export
$TAR   = "$CACHE\audio\wiktionary-audios.tar"       # shared bulk audio archive
$SNAP  = "$CACHE\ja\2026-09-01\raw-wiktextract-data.jsonl.gz"
$ACACHE = "$CACHE\ja\2026-09-01\audio-cache"        # filled by the kaikki JA prefetch
$SCRIPT = "scripts\bilingual-to-dsl.py"
```

The Tatoeba export is the same one as in `en-ja-wordnet.md` (shared cache —
download once). The kaikki snapshot is the JA one the `ja-ja` monolingual
build uses (dump date 2026-09-01).

## Step 0 — sample first (offline except audio fetch)

Use a words file (UTF-8, one headword per line) — `--word` mangles
non-Latin text through the Windows console:

```powershell
"寿司`n日本" | Set-Content -NoNewline -Encoding utf8 words-ja.txt
python $SCRIPT --mode translation --source-lang ja --target-lang en --words-file words-ja.txt --preview `
  --snapshot $SNAP --kaikki-dump-date 2026-09-01 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 `
  --out-dir dist-sample-jaen --name au_sample_ja-en --title "Aurelex Sample JA-EN"
Remove-Item words-ja.txt
```

Open `dist-sample-jaen/au_sample_ja-en.preview.html` and check article shape
(English POS labels, verbatim EN equivalents and PWN glosses, `[t]`
transcription where the snapshot has one, zoned examples, `[s]` audio)
before the full run. There is no `--audio-lang` flag here: that filter is
English-only, and the JA stage reuses its recordings verbatim.

## Step 1 — build (offline once the cache is full)

```powershell
python $SCRIPT --mode translation --source-lang ja --target-lang en --all-kaikki `
  --snapshot $SNAP --kaikki-dump-date 2026-09-01 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 `
  --resolve-cache $BIL\resolve-ja-en.json `
  --out-dir dist --name au_wordnet_ja-en --title "Aurelex WordNet JA-EN"
```

`--all-kaikki` iterates the ~111k lexical kaikki JA headwords and keeps the
~40k with JaWN-linked synsets; the rest ship no card. Published build:
39,706 cards, ~8.4 MB `.dsl.dz`. Japanese audio is sparse (0.08% in the
monolingual build) and stays sparse here — a headword silent in
`au_kaikki_ja-ja` is silent here. Non-Japanese (e.g. single-kanji) headwords
match as substrings; single-character matches are *kept* for Japanese,
unlike the Latin one-letter ban.

## Verify

Run the smoke tool over the output folder (any word — the scan, the index
build, and the markup check do not depend on it):

```powershell
.\build-gh\Release\aurelex_smoke.exe <cfg-dir> dist smoke
```

The run must index the dictionary with no `unclosed` / `Unknown tag`
warnings. A full `gd_lookup` of a non-Latin headword is not possible from
the Windows console (the test harness receives `argv` through the ANSI
code page, so Japanese headwords arrive mangled — unrelated to the
dictionary or to on-device lookup, where strings stay UTF-16 end to end);
verify Japanese headwords by article shape in the `.preview.html` sample
and, finally, on device. The same engine path is fully exercised by the
En→Ja `dog` lookup, which returns Japanese content with working audio and
expanders.
