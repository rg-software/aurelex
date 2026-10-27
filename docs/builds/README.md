# Building dictionaries from kaikki.org

Per-dictionary build recipes and cache sharing notes.

- `cache.md` — cache layout, deduplication, and sharing across machines.
- `en.md` — English (`au_kaikki_en-en`).
- `ru.md` — Russian (`au_kaikki_ru-ru`).
- `ja.md` — Japanese (`au_kaikki_ja-ja`).
- `en-ru-wordnet.md` — En→Ru translation dictionary (`au_wordnet_en-ru`).
- `en-ru-tatoeba.md` — En→Ru example-sentences dictionary (`au_tatoeba_en-ru`).
- `ru-en-wordnet.md` — Ru→En translation dictionary (`au_wordnet_ru-en`).
- `ru-en-tatoeba.md` — Ru→En example-sentences dictionary (`au_tatoeba_ru-en`).
- `en-ja-wordnet.md` — En→Ja translation dictionary (`au_wordnet_en-ja`).
- `en-ja-tatoeba.md` — En→Ja example-sentences dictionary (`au_tatoeba_en-ja`).
- `ja-en-wordnet.md` — Ja→En translation dictionary (`au_wordnet_ja-en`).
- `ja-en-tatoeba.md` — Ja→En example-sentences dictionary (`au_tatoeba_ja-en`).
- `ja-ru-wordnet.md` — Ja→Ru translation dictionary (`au_wordnet_ja-ru`).
- `ja-ru-tatoeba.md` — Ja→Ru example-sentences dictionary (`au_tatoeba_ja-ru`).
- `ru-ja-wordnet.md` — Ru→Ja translation dictionary (`au_wordnet_ru-ja`).
- `ru-ja-tatoeba.md` — Ru→Ja example-sentences dictionary (`au_tatoeba_ru-ja`).

Each recipe is self-contained: set the variables at the top, run Step 1 (prefetch)
until it exits 0, then Step 2 (build). All builds are offline once the cache is
full.

Shared, language-independent inputs live under `<CACHE>\audio\`
(`wiktionary-audios.tar`); per-language inputs live under `<CACHE>\<lang>\<dump-date>\`.
