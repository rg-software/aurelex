# Building the En→Ja translation dictionary (`au_wordnet_en-ja`)

Source: Princeton WordNet + Japanese WordNet `wnja` 2.1 joined on shared
PWN synset IDs (equivalents, Japanese definitions), Tatoeba eng→jpn pairs
(one anchored example per sense), kaikki EN audio (verbatim reuse).
Output: `dist/au_wordnet_en-ja.dsl.dz` + `dist/au_wordnet_en-ja.dsl.files.zip` (+ `.ann`).

This is the builder's full mode (`--mode translation`). Design and spec:
`openspec/changes/bilingual-en-ja-ja-ru/`; probe record:
`docs/BILINGUAL-EXPERIMENT.md` (JaWN appendix).

## Prerequisites

- Python 3.9+ (standard library only at runtime) plus the `wn` package with
  its data (one-time, ~100 MB):

```powershell
pip install wn
python -c "import wn; print(wn.download('https://github.com/bond-lab/wnja/releases/download/v2.1/wnja-2.1.tar.xz'))"
python -c "import wn; print(wn.download('omw-en:2.0'))"
```

- Cache populated (see `cache.md`). Variables used below:

```powershell
$CACHE = "C:\Users\Maxim\.cache\aurelex-kaikki"     # kaikki cache (shared, read-only here)
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-24"                  # pinned Tatoeba export
$TAR   = "$CACHE\audio\wiktionary-audios.tar"        # shared bulk audio archive
$SNAP  = "$CACHE\en\2026-09-02\raw-wiktextract-data.jsonl.gz"
$ACACHE = "$CACHE\en\2026-09-02\audio-cache"         # filled by the kaikki EN prefetch
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
The date is part of the path and of provenance — a new export is a new directory.

## Step 0 — sample first (offline except audio fetch)

```powershell
python $SCRIPT --mode translation --source-lang en --target-lang ja --word dog --word bread --sample 25 --sample-mode first --preview `
  --snapshot $SNAP --kaikki-dump-date 2026-09-02 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 --audio-lang US `
  --resolve-cache $BIL\resolve-en-ja.sample.json `
  --out-dir dist --name au_wordnet_en-ja --title "Aurelex WordNet EN-JA"
```

Open `dist/au_wordnet_en-ja.preview.html` and check article shape
(Japanese POS labels, `[trn]` equivalents common-first, JA definitions as
subordinate text, zoned examples, `[s]` audio) before the full run.

## Step 1 — build (offline once the cache is full)

```powershell
python $SCRIPT --mode translation --source-lang en --target-lang ja --all-lemmas `
  --snapshot $SNAP --kaikki-dump-date 2026-09-02 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-24 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 --audio-lang US `
  --resolve-cache $BIL\resolve-en-ja.json `
  --out-dir dist --name au_wordnet_en-ja --title "Aurelex WordNet EN-JA"
```

The build exits non-zero if any audio reference would not resolve — fix the
cache (re-run the kaikki EN prefetch), do not ship around it.

## Audio and cache reuse notes

- No separate audio prefetch: the build reuses the kaikki EN stage verbatim —
  the same snapshot, archive, and per-language `audio-cache` the `en.md` build
  fills. `--audio-lang US` matches the kaikki EN build, so each headword carries
  the same recordings there.
- `--no-audio` skips the snapshot and the archive entirely (then `--snapshot`
  is not needed); the dictionary still imports, without pronunciations.
- Rebuilds are deterministic: same inputs yield byte-identical output.
  Rebuilds are also cheap: `--resolve-cache` stores the resolved equivalents
  (keyed by thesaurus versions + headwords); only the first build pays the
  hours-long resolution. Published build: 79,069 cards, ~10 MB `.dsl.dz`.
- Numeric and other non-letter headwords (`0`, `1`, ...) are dropped and
  counted as ill-shaped; a Japanese digit-initial word with kana/kanji
  (10月) is kept.

## License note

No non-commercial thesaurus is involved (PWN + JaWN + Tatoeba are all
permissive): the about article and `.ann` carry attribution with no
distribution restriction, and the catalog entry is listed as
"Free to use with attribution". JaWN attribution includes its site link-back
(`https://bond-lab.github.io/wnja/`).

## Verify

```powershell
.\build-gh\Release\aurelex_smoke.exe <cfg-dir> dist dog
```

`gd_lookup("dog")` must return the full article with no `unclosed`/`Unknown tag`
warnings. (The smoke tool's own fixture asserts fail against a non-fixture
folder — only the dictionary's own lines matter.)
