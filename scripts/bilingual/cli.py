"""Skeleton CLI: builds a dictionary from an explicit headword list.

Source builders (WordNet equivalents, Tatoeba selection, kaikki audio) land in
later tasks; this CLI exists so the packaging path is exercisable and testable
from the start.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import package as _package
from . import preview as _preview
from . import provenance as _prov
from . import sample as _sample
from . import tatoeba as _tat
from . import build as _build


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bilingual-to-dsl.py",
        description="Build an offline En-Ru DSL dictionary (skeleton: "
        "headword-list input; source builders follow).",
    )
    parser.add_argument("--out-dir", default="dist", help="Output directory")
    parser.add_argument("--name", default="bilingual-en-ru", help="Output base name")
    parser.add_argument("--title", default=None, help="Display title (defaults to --name)")
    parser.add_argument(
        "--word",
        action="append",
        default=[],
        help="Headword to include (repeatable; keeps the path testable)",
    )
    parser.add_argument(
        "--words-file",
        default=None,
        help="File with one headword per line (combined with --word)",
    )
    parser.add_argument(
        "--sample", type=int, default=0, help="Emit only N headwords (0 = all)"
    )
    parser.add_argument(
        "--sample-mode",
        choices=("first", "random"),
        default="first",
        help="How --sample picks headwords (default: first)",
    )
    parser.add_argument(
        "--preview", action="store_true", help="Also write <name>.preview.html"
    )
    parser.add_argument(
        "--mode",
        choices=("skeleton", "translation", "pairs"),
        default="skeleton",
        help="Build mode: headword list only (default), full translation "
        "dictionary, or sentence-example dictionary",
    )
    parser.add_argument(
        "--all-lemmas", action="store_true",
        help="Use every English lemma in the RuWordNet EN subset as headwords",
    )
    parser.add_argument(
        "--all-kaikki", action="store_true",
        help="Use every lexical EN headword in --snapshot as headwords "
        "(pairs mode: keeps only headwords with pairs)",
    )
    parser.add_argument("--snapshot", default=None, help="Pinned kaikki EN snapshot (.jsonl.gz) for audio planning")
    parser.add_argument("--audio-tar", default=None, help="Shared bulk audio archive (wiktionary-audios.tar)")
    parser.add_argument("--audio-cache-dir", default=None, help="Download cache dir for recordings the archive lacks")
    parser.add_argument("--no-audio", action="store_true", help="Bundle no audio")
    parser.add_argument("--audio-per-word", type=int, default=3, help="Max audio files per headword (default 3)")
    parser.add_argument("--audio-lang", default=None, help="Prefer audio whose tags match, e.g. US")
    parser.add_argument("--tatoeba-dir", default=None, help="Dir with per-language sentences + per-pair links files (e.g. eng_sentences.tsv.bz2 + eng-jpn_links.tsv.bz2)")
    parser.add_argument("--tatoeba-date", default="unknown", help="Tatoeba export date (recorded in provenance)")
    parser.add_argument("--kaikki-dump-date", default="unknown", help="Kaikki snapshot dump date (recorded in provenance)")
    parser.add_argument("--ruwordnet-pwn", default="Princeton WordNet 3.0", help="PWN version label for provenance")
    parser.add_argument("--ruwordnet-version", default="RuWordNet 2.0 (2021)", help="RuWordNet version label for provenance")
    parser.add_argument("--resolve-cache", default=None, metavar="FILE",
                        help="Cache resolved equivalents here (keyed by thesaurus file + headwords); reruns skip resolution")
    parser.add_argument("--keep-pairs", type=int, default=5, help="Pairs kept per headword in pairs mode (default 5)")
    parser.add_argument(
        "--index-readings", action="store_true",
        help="Also index hiragana reading keys (Japanese sources only; "
        "needs --snapshot): the same article is reachable through its "
        "readings, opening with the primary headword as title.",
    )
    parser.add_argument(
        "--source-lang",
        choices=("en", "ru", "ja"),
        default="en",
        help="Dictionary source side (default: en). ru matches headwords "
        "against the Russian side of the same pairs (needs the "
        "source-language kaikki snapshot via --snapshot); with --mode "
        "translation it walks the ili bridge backwards (RU→EN equivalents). "
        "ja matches against the Japanese side (substring, no word boundaries).",
    )
    parser.add_argument(
        "--target-lang",
        choices=("en", "ru", "ja"),
        default=None,
        help="Dictionary target side (default: ru for --source-lang en, en "
        "otherwise). Supported pairs: en-ru, ru-en, en-ja, ja-en, ja-ru, ru-ja.",
    )
    return parser


def read_words(args: argparse.Namespace) -> list[str]:
    """Headword list from --word, --words-file and --all-lemmas, deduped."""
    from . import equivalents as _eq

    words = list(args.word)
    if args.words_file:
        with open(args.words_file, encoding="utf-8") as f:
            words.extend(ln.strip() for ln in f if ln.strip())
    if getattr(args, "all_lemmas", False):
        tgt = getattr(args, "target_lang", None) or (
            "en" if getattr(args, "source_lang", "en") in ("ru", "ja") else "ru")
        if getattr(args, "source_lang", "en") == "en" and tgt == "ja":
            words.extend(_eq.english_ja_universe())
        else:
            words.extend(_eq.english_lemma_universe())
    if getattr(args, "all_kaikki", False):
        if not args.snapshot:
            print("error: --all-kaikki needs --snapshot", file=sys.stderr)
            raise SystemExit(2)
        snap_lang = getattr(args, "source_lang", "en")
        words.extend(_eq.kaikki_headwords(args.snapshot, snap_lang))
    seen = set()
    unique = []
    for word in words:
        if word not in seen:
            seen.add(word)
            unique.append(word)
    return unique


_SUPPORTED_DIRECTIONS = {"en-ru", "ru-en", "en-ja", "ja-en", "ja-ru", "ru-ja"}


def _resolve_direction(args: argparse.Namespace) -> str:
    """Source→target direction, with backward-compatible defaults.

    Old invocations pass only ``--source-lang`` (en→ru, ru→en); new ones
    pass ``--target-lang`` explicitly for Japanese pairs.
    """
    src = getattr(args, "source_lang", "en")
    tgt = getattr(args, "target_lang", None)
    if tgt is None:
        tgt = "en" if src in ("ru", "ja") else "ru"
    direction = f"{src}-{tgt}"
    if direction not in _SUPPORTED_DIRECTIONS:
        print(f"error: unsupported direction {direction}; "
              f"supported: {sorted(_SUPPORTED_DIRECTIONS)}", file=sys.stderr)
        raise SystemExit(2)
    if src == tgt:
        print("error: source and target languages must differ", file=sys.stderr)
        raise SystemExit(2)
    return direction


def _load_corpus(args: argparse.Namespace, direction: str):
    import os as _os

    if not args.tatoeba_dir:
        return None
    d = args.tatoeba_dir
    src, tgt = direction.split("-", 1)
    # Our codes (en/ru/ja) vs Tatoeba file codes (eng/rus/jpn).
    to_tatoeba = {"en": "eng", "ru": "rus", "ja": "jpn"}
    from_tatoeba = {"eng": "en", "rus": "ru", "jpn": "ja"}
    tsrc, ttgt = to_tatoeba.get(src, src), to_tatoeba.get(tgt, tgt)
    # The link file is stored once per pair (alphabetical Tatoeba order:
    # eng-jpn, eng-rus, jpn-rus). Acquire in file order, then flip when the
    # requested direction is the reverse.
    for links_name in (f"{tsrc}-{ttgt}_links.tsv.bz2",
                       f"{ttgt}-{tsrc}_links.tsv.bz2"):
        links_path = _os.path.join(d, links_name)
        if not _os.path.isfile(links_path):
            continue
        first, _, _ = links_name.partition("_links")
        fsrc_t, _, ftgt_t = first.partition("-")
        fsrc, ftgt = from_tatoeba.get(fsrc_t, fsrc_t), from_tatoeba.get(ftgt_t, ftgt_t)
        src_file = {"en": "eng_sentences.tsv.bz2", "ru": "rus_sentences.tsv.bz2",
                    "ja": "jpn_sentences.tsv.bz2"}.get(fsrc, f"{fsrc}_sentences.tsv.bz2")
        tgt_file = {"en": "eng_sentences.tsv.bz2", "ru": "rus_sentences.tsv.bz2",
                    "ja": "jpn_sentences.tsv.bz2"}.get(ftgt, f"{ftgt}_sentences.tsv.bz2")
        src_path = _os.path.join(d, src_file)
        tgt_path = _os.path.join(d, tgt_file)
        if not (_os.path.isfile(src_path) and _os.path.isfile(tgt_path)):
            continue
        corpus = _tat.acquire(src_path, tgt_path, links_path,
                              args.tatoeba_date,
                              src_lang=fsrc, tgt_lang=ftgt)
        if (fsrc, ftgt) != (src, tgt):
            corpus = corpus.flipped()
        return corpus
    print(f"error: Tatoeba files for {direction} not found in {d} "
          f"(need <src>_sentences + <tgt>_sentences + <pair>_links)", file=sys.stderr)
    raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    words = read_words(args)
    if args.sample:
        words = _sample.select(words, args.sample, args.sample_mode)

    mode = getattr(args, "mode", "skeleton")
    if getattr(args, "index_readings", False) and not args.snapshot:
        print("error: --index-readings needs --snapshot", file=sys.stderr)
        raise SystemExit(2)
    if mode == "translation":
        direction = _resolve_direction(args)
        corpus = _load_corpus(args, direction)
        sources = _prov.Sources(
            pwn=args.ruwordnet_pwn,
            ruwordnet=args.ruwordnet_version,
            tatoeba_date=args.tatoeba_date,
            kaikki_dump_date=args.kaikki_dump_date,
            direction=direction,
        )
        summary = _build.build_sample(
            words, args.out_dir, args.name, args.title,
            sources=sources,
            snapshot_path=args.snapshot,
            corpus=corpus,
            archive_path=args.audio_tar,
            download_dir=args.audio_cache_dir,
            per_word_audio=args.audio_per_word,
            audio_lang=args.audio_lang,
            audio_enabled=not args.no_audio,
            resolve_cache=args.resolve_cache,
            direction=direction,
            audio_lang_code=direction.split("-", 1)[0],
            index_readings=args.index_readings,
        )
        print(f"wrote {summary['dz_path']} ({summary['cards']} cards, "
              f"{summary['synsets_linked']}/{summary['synsets']} synsets linked)")
        if summary["unresolved"]:
            print(f"error: {len(summary['unresolved'])} unresolved audio refs",
                  file=sys.stderr)
            return 1
        cards = summary["cards_out"]
    elif mode == "pairs":
        direction = _resolve_direction(args)
        corpus = _load_corpus(args, direction)
        if corpus is None:
            print("error: pairs mode needs --tatoeba-dir", file=sys.stderr)
            return 2
        sources = _prov.Sources(
            tatoeba_date=args.tatoeba_date, equivalents=False,
            direction=direction,
        )
        summary = _build.build_pairs(
            words, args.out_dir, args.name, args.title,
            sources=sources, corpus=corpus, keep=args.keep_pairs,
            direction=direction,
            snapshot_path=args.snapshot,
            index_readings=args.index_readings,
        )
        print(f"wrote {summary['dz_path']} ({summary['cards']} cards)")
        cards = summary["cards_out"]
    else:
        cards = _package.card_list(words)
        path, _text = _package.build(cards, args.out_dir, args.name, args.title)
        print(f"wrote {path} ({len(cards)} headwords)")

    if args.preview:
        preview_path = os.path.join(args.out_dir, f"{args.name}.preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(_preview.render(cards, args.title or args.name))
        print(f"wrote {preview_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
