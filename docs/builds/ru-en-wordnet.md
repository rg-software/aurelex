# Building the Ru→En translation dictionary (`au_wordnet_ru-en`)

Source: RuWordNet synsets bridged to Princeton WordNet via `ili`
(equivalents, English glosses as definitions), Tatoeba rus→eng pairs (one
anchored example per sense), kaikki RU audio (verbatim reuse). Output:
`dist/au_wordnet_ru-en.dsl.dz` + `dist/au_wordnet_ru-en.dsl.files.zip` (+ `.ann`).

This is the builder's reverse translation mode (`--mode translation
--source-lang ru`). Design and spec:
`openspec/changes/archive/2026-10-23-bilingual-ru-en-translation/`,
`2026-10-24-bilingual-transcription/` (headword `[t]` lines),
`2026-10-24-bilingual-drop-empty-senses/` (senses with neither equivalents
nor a definition are omitted); probe record:
`docs/BILINGUAL-EXPERIMENT.md`.

## Prerequisites

- Python 3.9+ (standard library only at runtime) plus the `ruwordnet` package with
  its database (one-time, ~80 MB):

```powershell
pip install ruwordnet
ruwordnet download
```

- Cache populated (see `cache.md`). Variables used below:

```powershell
$CACHE = "C:\Users\Maxim\.cache\aurelex-kaikki"     # kaikki cache (shared, read-only here)
$BIL   = "C:\Users\Maxim\.cache\aurelex-bilingual"  # bilingual cache
$TAT   = "$BIL\tatoeba\2026-10-17"                  # pinned Tatoeba export
$TAR   = "$CACHE\audio\wiktionary-audios.tar"       # shared bulk audio archive
$SNAP  = "$CACHE\ru\2026-09-01\raw-wiktextract-data.jsonl.gz"
$ACACHE = "$CACHE\ru\2026-09-01\audio-cache"        # filled by the kaikki RU prefetch
$SCRIPT = "scripts\bilingual-to-dsl.py"
```

The Tatoeba export is the same three files as the en→ru recipes (shared
cache — download once, see `en-ru-wordnet.md`). The kaikki snapshot is the
RU one the `ru-ru` monolingual build uses (dump date 2026-09-01, ~307 MB),
holding ~468k lexical headwords.

## Step 0 — sample first (offline except audio fetch)

```powershell
'хлеб','Москва','собака','говорить' | Set-Content words-ru.txt
python $SCRIPT --mode translation --source-lang ru --words-file words-ru.txt --preview `
  --snapshot $SNAP --kaikki-dump-date 2026-09-01 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-17 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 `
  --out-dir dist-sample-ruen --name au_sample_ru-en --title "Aurelex Sample RU-EN"
Remove-Item words-ru.txt
```

Open `dist-sample-ruen/au_sample_ru-en.preview.html` and check article
shape (English POS labels, verbatim EN equivalents and PWN glosses,
`[t]` transcription under the headword, zoned examples, `[s]` audio)
before the full run. There is no `--audio-lang` flag here: that filter is
English-only, and the RU stage reuses its recordings verbatim.

## Step 1 — build (offline once the cache is full)

```powershell
python $SCRIPT --mode translation --source-lang ru --all-kaikki `
  --snapshot $SNAP --kaikki-dump-date 2026-09-01 `
  --tatoeba-dir $TAT --tatoeba-date 2026-10-17 `
  --audio-tar $TAR --audio-cache-dir $ACACHE --audio-per-word 3 `
  --resolve-cache $BIL\resolve-ru-en.json `
  --out-dir dist --name au_wordnet_ru-en --title "Aurelex WordNet RU-EN"
```

The build exits non-zero if any audio reference would not resolve — fix the
cache (re-run the kaikki RU prefetch), do not ship around it.

## Audio and cache reuse notes

- No separate audio prefetch: the build reuses the kaikki RU stage verbatim —
  the same snapshot, archive, and per-language `audio-cache` the `ru.md` build
  fills. First build may download recordings the archive lacks into
  `--audio-cache-dir` (sidecar-verified, reused after); re-runs are offline.
- A headword silent in `au_kaikki_ru-ru` is silent here.
- `--no-audio` skips the snapshot and the archive entirely (then `--snapshot`
  is not needed); the dictionary still imports, without pronunciations.
- Rebuilds are deterministic: same inputs yield byte-identical output.
  Rebuilds are also cheap: `--resolve-cache` stores the resolved RU→EN
  mapping (keyed by thesaurus file + headword list), so only the first build
  pays the hours-long resolution; later runs reuse it verbatim.
- Expect a long first run on a desktop: one full RU snapshot scan (~10 min),
  per-headword equivalent resolution over ~468k kaikki headwords (most with
  no RuWordNet entry and skipped — the published build keeps 66,690 cards),
  one Tatoeba join over 831k pairs, and archive lookups — the same cost
  class as a kaikki full build.

## Verify

```powershell
.\build-gh\Release\aurelex_smoke.exe <cfg-dir> dist хлеб
```

`gd_lookup("хлеб")` must return the full article with no `unclosed`/`Unknown tag`
warnings. (The smoke tool's own fixture asserts fail against a non-fixture
folder — only the dictionary's own lines matter.)
