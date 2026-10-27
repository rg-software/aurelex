# Building the Ja→Ru translation dictionary (`au_wordnet_ja-ru`)

Source: Japanese WordNet synsets bridged to RuWordNet through the shared
Princeton WordNet id (the PWN-ID pivot: each `ili`-linked RU synset is one
sense with Russian member lemmas and definitions), Tatoeba jpn→rus pairs
(one anchored example per sense), kaikki JA audio (verbatim reuse, such as
it is). Output: `dist/au_wordnet_ja-ru.dsl.dz` +
`dist/au_wordnet_ja-ru.dsl.files.zip` (+ `.ann`).

This is the builder's pivot mode (`--mode translation --source-lang ja
--target-lang ru`). Design and spec:
`openspec/changes/bilingual-en-ja-ja-ru/`; probe record:
`docs/BILINGUAL-EXPERIMENT.md` (JaWN appendix).

## Prerequisites

- Python 3.9+ (standard library only at runtime) plus the `wn` and
  `ruwordnet` packages with their data (one-time;
  `pip install wn ruwordnet`, then the `wnja:2.1` + `omw-en:2.0`
  downloads and `ruwordnet download`).
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

The Tatoeba export is the same three-file set as the wordnet recipes plus
the `jpn-rus` pair (downloaded once into the shared cache):

```powershell
New-Item -ItemType Directory -Force -Path $TAT | Out-Null
curl -sO https://downloads.tatoeba.org/exports/per_language/jpn/jpn_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences.tsv.bz2 --output-dir $TAT
curl -sO https://downloads.tatoeba.org/exports/per_language/jpn/jpn-rus_links.tsv.bz2 --output-dir $TAT
```

Sizes on 2026-10-24: sentences JA ~3.4 MB, RU ~15.5 MB, links ~200 KB (31,578 pairs).

## Step 0 — sample first (offline except audio fetch)

Use a words file (UTF-8, one headword per line) — `--word` mangles
non-Latin text through the Windows console:

```powershell
"寿司`n日本`n学校" | Set-Content -NoNewline -Encoding utf8 words-ja.txt
python $SCRIPT --mode translation --source-lang ja --target-lang ru --words-file words-ja.txt --preview `
  --snapshot $SNAP --kaikki-dump-date 2026-09-01 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 `
  --out-dir dist-sample-jaru --name au_sample_ja-ru --title "Aurelex Sample JA-RU"
Remove-Item words-ja.txt
```

Open the `.preview.html` and check article shape (Russian POS labels,
`[trn]` equivalents common-first, Russian definitions, kana readings line,
zoned examples, `[s]` audio where the JA snapshot has any) before the full
run. There is no `--audio-lang` flag here: that filter is English-only.

## Step 1 — build (offline once the cache is full)

```powershell
python $SCRIPT --mode translation --source-lang ja --target-lang ru --all-kaikki `
  --snapshot $SNAP --kaikki-dump-date 2026-09-01 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 `
  --resolve-cache $BIL\resolve-ja-ru.json `
  --out-dir dist --name au_wordnet_ja-ru --title "Aurelex WordNet JA-RU"
```

`--all-kaikki` iterates the ~111k lexical kaikki JA headwords and keeps the
ones whose JaWN synsets hit the PWN-ID pivot (~27k cards in the published
build, ~4.9 MB `.dsl.dz`). A Japanese headword with no pivot hit gets no
card at all — no content-free entries. The build exits non-zero if any
audio reference would not resolve.

## License note

RuWordNet participates, so the RuWordNet non-commercial terms cover the
whole dictionary: the about article and `.ann` state non-commercial use
and distribution only, with attribution to Princeton WordNet, RuWordNet,
Japanese WordNet (with its site link-back), and Tatoeba.

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
and, finally, on device.
