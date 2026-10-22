# Building dictionaries from kaikki.org

Per-dictionary build recipes and cache sharing notes.

- `cache.md` — cache layout, deduplication, and sharing across machines.
- `en.md` — English (`au_kaikki_en-en`).
- `ru.md` — Russian (`au_kaikki_ru-ru`).
- `ja.md` — Japanese (`au_kaikki_ja-ja`).
- `en-ru-wordnet.md` — En→Ru translation dictionary (`au_wordnet_en-ru`).
- `en-ru-tatoeba.md` — En→Ru example-sentences dictionary (`au_tatoeba_en-ru`).

Each recipe is self-contained: set the variables at the top, run Step 1 (prefetch)
until it exits 0, then Step 2 (build). All builds are offline once the cache is
full.

Shared, language-independent inputs live under `<CACHE>\audio\`
(`wiktionary-audios.tar`); per-language inputs live under `<CACHE>\<lang>\<dump-date>\`.
