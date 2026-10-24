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
    parser.add_argument("--tatoeba-dir", default=None, help="Dir with eng/rus sentences + eng-rus links files")
    parser.add_argument("--tatoeba-date", default="unknown", help="Tatoeba export date (recorded in provenance)")
    parser.add_argument("--kaikki-dump-date", default="unknown", help="Kaikki EN snapshot dump date (recorded in provenance)")
    parser.add_argument("--ruwordnet-pwn", default="Princeton WordNet 3.0", help="PWN version label for provenance")
    parser.add_argument("--ruwordnet-version", default="RuWordNet 2.0 (2021)", help="RuWordNet version label for provenance")
    parser.add_argument("--resolve-cache", default=None, metavar="FILE",
                        help="Cache resolved equivalents here (keyed by thesaurus file + headwords); reruns skip resolution")
    parser.add_argument("--keep-pairs", type=int, default=5, help="Pairs kept per headword in pairs mode (default 5)")
    parser.add_argument(
        "--source-lang",
        choices=("en", "ru"),
        default="en",
        help="Dictionary source side (default: en). ru matches headwords "
        "against the Russian side of the same pairs (needs the "
        "source-language kaikki snapshot via --snapshot); with --mode "
        "translation it walks the ili bridge backwards (RU→EN equivalents).",
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
        words.extend(_eq.english_lemma_universe())
    if getattr(args, "all_kaikki", False):
        if not args.snapshot:
            print("error: --all-kaikki needs --snapshot", file=sys.stderr)
            raise SystemExit(2)
        snap_lang = "ru" if getattr(args, "source_lang", "en") == "ru" else "en"
        words.extend(_eq.kaikki_headwords(args.snapshot, snap_lang))
    seen = set()
    unique = []
    for word in words:
        if word not in seen:
            seen.add(word)
            unique.append(word)
    return unique


def _load_corpus(args: argparse.Namespace):
    import os as _os

    if not args.tatoeba_dir:
        return None
    d = args.tatoeba_dir
    return _tat.acquire(
        _os.path.join(d, "eng_sentences.tsv.bz2"),
        _os.path.join(d, "rus_sentences.tsv.bz2"),
        _os.path.join(d, "eng-rus_links.tsv.bz2"),
        args.tatoeba_date,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    words = read_words(args)
    if args.sample:
        words = _sample.select(words, args.sample, args.sample_mode)

    mode = getattr(args, "mode", "skeleton")
    if mode == "translation":
        corpus = _load_corpus(args)
        direction = "ru-en" if args.source_lang == "ru" else "en-ru"
        if direction == "ru-en" and corpus is not None:
            corpus = corpus.flipped()
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
            audio_lang_code="ru" if direction == "ru-en" else "en",
        )
        print(f"wrote {summary['dz_path']} ({summary['cards']} cards, "
              f"{summary['synsets_linked']}/{summary['synsets']} synsets linked)")
        if summary["unresolved"]:
            print(f"error: {len(summary['unresolved'])} unresolved audio refs",
                  file=sys.stderr)
            return 1
        cards = summary["cards_out"]
    elif mode == "pairs":
        corpus = _load_corpus(args)
        if corpus is None:
            print("error: pairs mode needs --tatoeba-dir", file=sys.stderr)
            return 2
        direction = "ru-en" if args.source_lang == "ru" else "en-ru"
        if direction == "ru-en":
            corpus = corpus.flipped()
        sources = _prov.Sources(
            tatoeba_date=args.tatoeba_date, equivalents=False,
            direction=direction,
        )
        summary = _build.build_pairs(
            words, args.out_dir, args.name, args.title,
            sources=sources, corpus=corpus, keep=args.keep_pairs,
            direction=direction,
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
