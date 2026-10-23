#!/usr/bin/env python3
"""Tests for scripts/bilingual-to-dsl.py.

Run with:  python -m unittest discover -s scripts/tests -p "test_bilingual*"
"""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import bilingual
from bilingual import cli as _cli
from bilingual import dsl as _dsl
from bilingual import package as _package
from bilingual import preview as _preview
from bilingual import sample as _sample


class EscapeTest(unittest.TestCase):
    def test_brackets_do_not_form_markup(self):
        self.assertEqual(_dsl.escape_dsl("a [b] c"), "a \\[b\\] c")

    def test_headword_hash_is_escaped(self):
        self.assertEqual(_dsl.clean_headword("#hashtag"), "\\#hashtag")

    def test_multiline_collapses(self):
        self.assertEqual(_dsl.escape_dsl("a\nb\tc"), "a b c")


class CardTest(unittest.TestCase):
    def test_layout_order(self):
        card = _dsl.Card(
            headword="give",
            pos="гл.",
            senses=[
                _dsl.Sense(
                    definition="передать нечто в дар",
                    equivalents=["дарить", "подарить", "презентовать"],
                    synonyms=["present"],
                    example=("What shall I give her?", "Что мне ей подарить?"),
                ),
                _dsl.Sense(
                    definition="давать корм",
                    equivalents=["кормить"],
                    synonyms=["feed"],
                ),
            ],
        )
        text = "\n".join(_dsl.emit_card(card))
        num_pos = text.index("[m1]1.[/m]")
        trn_pos = text.index("[trn]дарить[/trn]")
        def_pos = text.index("[i]передать нечто в дар[/i]")
        ex_pos = text.index("[*]")
        syn_pos = text.index("(syn. present)")
        # equivalents lead, definition follows, example before trailing synonyms
        self.assertTrue(0 < num_pos < trn_pos < def_pos < ex_pos < syn_pos)
        self.assertIn("[/*]", text)
        self.assertIn("[trn]Что мне ей подарить?[/trn]", text)

    def test_single_sense_has_no_counter(self):
        card = _dsl.Card(
            headword="monkey",
            senses=[_dsl.Sense(definition="обезьяна", equivalents=["обезьяна"])],
        )
        text = "\n".join(_dsl.emit_card(card))
        self.assertNotIn("[m1]", text)
        self.assertIn("[trn]обезьяна[/trn]", text)
        self.assertIn("[i]обезьяна[/i]", text)

    def test_multi_pos_single_card_restarts_numbering(self):
        card = _dsl.Card(headword="run", senses=[
            _dsl.Sense(definition="d1", equivalents=["e1"], pos="сущ."),
            _dsl.Sense(definition="d2", equivalents=["e2"], pos="сущ."),
            _dsl.Sense(definition="d3", equivalents=["e3"], pos="гл."),
        ])
        text = "\n".join(_dsl.emit_card(card))
        self.assertEqual(text.count("[p]сущ.[/p]"), 1)
        self.assertEqual(text.count("[p]гл.[/p]"), 1)
        # numbering restarts in each POS section; the lone verb sense is unnumbered
        self.assertEqual(text.count("[m1]1.[/m]"), 1)
        self.assertEqual(text.count("[m1]2.[/m]"), 1)
        self.assertNotIn("[m1]3.[/m]", text)
        self.assertEqual(text.index("[p]сущ.[/p]"), text.index("[p]сущ.[/p]"))
        self.assertLess(text.index("[p]сущ.[/p]"), text.index("[p]гл.[/p]"))

    def test_equivalent_cap(self):
        sense = _dsl.Sense(definition="d", equivalents=[f"w{i}" for i in range(20)])
        lines = _dsl.emit_sense(sense, 1)
        self.assertEqual(sum(1 for ln in lines if "[trn]" in ln), 8)

    def test_no_example_no_zone(self):
        lines = _dsl.emit_sense(_dsl.Sense(definition="d", equivalents=["x"]), 1)
        self.assertFalse(any("[*]" in ln or "[/*]" in ln for ln in lines))
        # the doc-shorthand closer matches no opening tag and would leave later
        # senses inside the zone (kaikki fixed the same mistake): never emit it
        frame = "\n".join(_dsl.emit_card(_dsl.Card(
            headword="w", senses=[_dsl.Sense(definition="d", example=("e", "п"))])))
        self.assertNotIn("[/opt]", frame)


class DeterminismTest(unittest.TestCase):
    def _cards(self):
        return [
            _dsl.Card(headword="bread", pos="сущ.", senses=[_dsl.Sense(definition="изделие")]),
            _dsl.Card(headword="give", pos="гл.", senses=[_dsl.Sense(definition="дар")]),
        ]

    def test_two_builds_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            p1, _ = _package.build(self._cards(), d1, "test-en-ru")
            p2, _ = _package.build(self._cards(), d2, "test-en-ru")
            with open(p1, "rb") as f1, open(p2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())

    def test_input_order_does_not_matter(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            p1, _ = _package.build(self._cards(), d1, "test-en-ru")
            p2, _ = _package.build(list(reversed(self._cards())), d2, "test-en-ru")
            with open(p1, "rb") as f1, open(p2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, text = _package.build(self._cards(), tmp, "test-en-ru")
            self.assertEqual(_package.read(path), text)

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = _cli.main(["--out-dir", tmp, "--name", "cli-en-ru",
                            "--word", "bread", "--word", "give"])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "cli-en-ru.dsl.dz")))


class SampleTest(unittest.TestCase):
    def test_first_takes_prefix(self):
        self.assertEqual(_sample.select(["a", "b", "c"], 2, "first"), ["a", "b"])

    def test_reruns_agree(self):
        words = [f"w{i}" for i in range(50)]
        for mode in ("first", "random"):
            self.assertEqual(
                _sample.select(words, 10, mode), _sample.select(words, 10, mode)
            )

    def test_random_spreads(self):
        words = [f"w{i}" for i in range(50)]
        first = set(_sample.select(words, 10, "first"))
        random = set(_sample.select(words, 10, "random"))
        self.assertEqual(len(random), 10)
        self.assertTrue(random - first, "random sample never leaves the prefix")

    def test_cli_sample_and_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            words_file = os.path.join(tmp, "words.txt")
            with open(words_file, "w", encoding="utf-8") as f:
                f.write("bread\ngive\ntime\n")
            rc = _cli.main(["--out-dir", tmp, "--name", "smp-en-ru",
                            "--words-file", words_file,
                            "--sample", "2", "--sample-mode", "first",
                            "--preview"])
            self.assertEqual(rc, 0)
            preview = os.path.join(tmp, "smp-en-ru.preview.html")
            self.assertTrue(os.path.isfile(preview))
            with open(preview, encoding="utf-8") as f:
                html = f.read()
            self.assertIn("bread", html)
            self.assertIn("give", html)
            self.assertNotIn("time", html)


class PreviewTest(unittest.TestCase):
    def test_shape_matches_probe(self):
        card = _dsl.Card(
            headword="bread",
            pos="сущ.",
            senses=[
                _dsl.Sense(
                    definition="изделие из муки",
                    equivalents=["хлеб", "хлебушек"],
                    synonyms=["breadstuff"],
                    example=("Eat bread.", "Ешьте хлеб."),
                )
            ],
            audio=["En-us-bread.ogg"],
        )
        html = _preview.render([card], "sample")
        self.assertIn("<h2>bread</h2>", html)
        self.assertIn("сущ.", html)
        self.assertIn("изделие из муки", html)
        self.assertIn("хлеб", html)
        self.assertIn("syn. breadstuff", html)
        self.assertIn("Eat bread.", html)
        self.assertIn("audio: En-us-bread.ogg", html)
        # preview mirrors article order: equivalents, definition, example, synonyms
        self.assertLess(html.index("хлеб"), html.index("изделие из муки"))
        self.assertLess(html.index("Eat bread."), html.index("syn. breadstuff"))


class TatoebaTest(unittest.TestCase):
    def _fixture(self, tmp):
        eng = os.path.join(tmp, "eng.tsv")
        rus = os.path.join(tmp, "rus.tsv")
        links = os.path.join(tmp, "links.tsv")
        with open(eng, "w", encoding="utf-8") as f:
            f.write("1\teng\tEat bread.\n2\teng\tI like bread.\n3\teng\tOrphan.\n")
        with open(rus, "w", encoding="utf-8") as f:
            f.write("10\trus\tЕшь хлеб.\n11\trus\tЛюблю хлеб.\n")
        with open(links, "w", encoding="utf-8") as f:
            f.write("1\t10\n2\t11\n3\t99\n99\t10\n")
        return eng, rus, links

    def test_acquire_joins_and_pins_date(self):
        from bilingual import tatoeba as _tat
        with tempfile.TemporaryDirectory() as tmp:
            eng, rus, links = self._fixture(tmp)
            corpus = _tat.acquire(eng, rus, links, "2026-10-17")
            self.assertEqual(corpus.date, "2026-10-17")
            self.assertEqual(len(corpus.pairs), 2)
            self.assertIn(("Eat bread.", "Ешь хлеб."), corpus.pairs)

    def test_index_matches_regex_scan(self):
        from bilingual import tatoeba as _tat
        pairs = [("Eat bread.", "Ешь хлеб."), ("I like bread.", "Люблю хлеб."),
                 ("Breads are nice.", "Хлеба хороши."), ("Good dog!", "Хорошая собака!")]
        corpus = _tat.Corpus(pairs=pairs, index=_tat.index_pairs(pairs))
        # 'bread' must not match 'Breads'; multiword falls back to full scan
        self.assertEqual(_tat.pairs_for("bread", corpus),
                         [("Eat bread.", "Ешь хлеб."), ("I like bread.", "Люблю хлеб.")])
        self.assertEqual(_tat.pairs_for("hot dog", corpus), [])
        self.assertEqual(_tat.pairs_for("dog", corpus), [("Good dog!", "Хорошая собака!")])

    def test_absent_token_skips_scan(self):
        from bilingual import tatoeba as _tat
        pairs = [("Eat bread.", "Ешь хлеб.")]
        corpus = _tat.Corpus(pairs=pairs, index=_tat.index_pairs(pairs))
        # 'xyzzy' occurs nowhere: must return [] without scanning
        self.assertEqual(_tat.pairs_for("xyzzy", corpus), [])
        self.assertEqual(_tat.pairs_for("bread xyzzy", corpus), [])

    def test_flipped_view_matches_russian(self):
        # the ru->en view searches the Russian side with the Russian tokenizer
        from bilingual import tatoeba as _tat
        pairs = [("Eat bread.", "Ешь хлеб."), ("I like bread.", "Люблю хлеб.")]
        corpus = _tat.Corpus(
            pairs=pairs, index=_tat.index_pairs(pairs),
            index_ru=_tat.index_pairs([(ru, en) for en, ru in pairs], lang="ru"))
        ru = corpus.flipped()
        self.assertEqual(ru.lang, "ru")
        self.assertEqual(
            _tat.pairs_for("хлеб", ru),
            [("Ешь хлеб.", "Eat bread."), ("Люблю хлеб.", "I like bread.")])
        self.assertEqual(
            _tat.pairs_for("ешь", ru), [("Ешь хлеб.", "Eat bread.")])
        self.assertEqual(_tat.pairs_for("я", ru), [])  # single-char: nothing
        self.assertEqual(_tat.pairs_for("dog", ru), [])  # latin invisible here

    def test_flipped_select_dedupes_russian_side(self):
        # dedupe key and variant roles follow tuple position, not language
        from bilingual import tatoeba as _tat
        kept = _tat.select(
            [("Ешь хлеб.", "Eat bread."), ("Ешь хлеб.", "Кушай хлеб.")],
            [], _tat.Counter(), keep=3)
        self.assertEqual(kept, [("Ешь хлеб.", "Eat bread.")])

    def test_single_char_headword_never_matches(self):
        # 'A' (ampere) must not match the article in "Be a man": a one-letter
        # token in running text is never the abbreviation sense.
        from bilingual import tatoeba as _tat
        pairs = [("Be a man.", "Будь мужчиной."), ("Buy vitamin A.", "Купи витамин А.")]
        corpus = _tat.Corpus(pairs=pairs, index=_tat.index_pairs(pairs))
        self.assertEqual(_tat.pairs_for("A", corpus), [])
        self.assertEqual(_tat.pairs_for("I", corpus), [])
        # two-letter words still match normally
        self.assertEqual(_tat.pairs_for("Be", corpus), [("Be a man.", "Будь мужчиной.")])

    def test_dedupe_one_variant_per_sentence(self):
        from bilingual import tatoeba as _tat
        pairs = [("Eat bread.", "Ешь хлеб."), ("Eat bread.", "Кушай хлеб."),
                 ("I like bread.", "Люблю хлеб.")]
        kept = _tat.select(pairs, ["хлеб"], _tat.Counter(), keep=3)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len([p for p in kept if p[0] == "Eat bread."]), 1)

    def test_word_boundary_no_substring_match(self):
        # 'давать' must not count as anchored inside 'сдаваться' — the probe's
        # false positive. The anchored variant wins; an anchor-less EN text
        # still keeps its shortest variant (length ranks, never filters).
        from bilingual import tatoeba as _tat
        freq = _tat.Counter({"давать": 10})
        self.assertEqual(
            _tat.rank_variants(["Давайте сдаваться.", "Зачем давать его мне."],
                               ["давать"], freq),
            "Зачем давать его мне.")
        self.assertEqual(
            _tat.rank_variants(["Давайте сдаваться."], ["давать"], freq),
            "Давайте сдаваться.")

    def test_distinctive_anchor_wins(self):
        from bilingual import tatoeba as _tat
        freq = _tat.Counter({"уйти": 5000, "посвятить": 3})
        variants = ["Пора уйти.", "Решил посвятить себя делу."]
        self.assertEqual(
            _tat.rank_variants(variants, ["уйти", "посвятить"], freq),
            "Решил посвятить себя делу.")

    def test_rank_equivalents_common_first(self):
        from bilingual import equivalents as _eq
        from bilingual import tatoeba as _tat
        freq = _tat.Counter({"парламент": 500, "страны": 400, "высший": 30,
                             "законодательный": 5, "орган": 300,
                             "государства": 100, "национальный": 20})
        ranked = _eq.rank_equivalents(
            ["высший законодательный орган государства", "национальный парламент",
             "парламент страны", "неизвестноеслово", "парламент страны"], freq)
        # exact dupes gone, common-first, unknown last
        self.assertEqual(ranked[0], "парламент страны")
        self.assertEqual(ranked[-1], "неизвестноеслово")
        self.assertEqual(len(ranked), len(set(ranked)))

    def test_cap_and_length_ranks_not_filters(self):
        from bilingual import tatoeba as _tat
        pairs = [(f"Sentence number {i} here.", f"Предложение {i}.") for i in range(5)]
        kept = _tat.select(pairs, ["нетакогослова"], _tat.Counter(), keep=2)
        self.assertEqual(len(kept), 2)
        long_only = [("A very long English sentence " * 10 + "here.", "Длинно.")]
        self.assertEqual(len(_tat.select(long_only, ["нетакого"], _tat.Counter(), keep=1)), 1)

    def test_sense_select_anchored_then_fallback(self):
        from bilingual import tatoeba as _tat
        freq = _tat.Counter({"хлеб": 900, "идти": 400})
        pairs = [("Eat bread.", "Ешь хлеб."), ("I go.", "Иду.")]
        self.assertEqual(
            _tat.select_for_sense(["хлеб"], pairs, freq),
            ("Eat bread.", "Ешь хлеб."))
        # anchor-less sense still ships the shortest pair, never nothing
        self.assertEqual(
            _tat.select_for_sense(["нетакого"], pairs, freq),
            ("I go.", "Иду."))

    def test_sense_select_works_on_flipped_pairs(self):
        # reverse direction: pairs are (source, target) = (ru, en), so the
        # anchor always checks the second element — no code change needed
        from bilingual import tatoeba as _tat
        flipped = [("Ешь хлеб.", "Eat bread."), ("Иду.", "I go.")]
        self.assertEqual(
            _tat.select_for_sense(["bread"], flipped, _tat.Counter()),
            ("Ешь хлеб.", "Eat bread."))
        self.assertEqual(
            _tat.select_for_sense(["нетакого"], flipped, _tat.Counter()),
            ("Иду.", "I go."))


class EquivalentsTest(unittest.TestCase):
    class FakeBackend:
        def en_synsets(self, word):
            from bilingual import equivalents as _eq
            if word != "give":
                return []
            return [
                _eq.EnSynset(
                    pos="verb",
                    lemmas=["give", "present"],
                    groups=[
                        _eq.RuGroup(title="ДАРЕНИЕ", definition="передать нечто в дар.",
                                    lemmas=["ДАРИТЬ", "ПОДАРИТЬ"]),
                        _eq.RuGroup(title="ПОСВЯТИТЬ (ПРЕДНАЗНАЧИТЬ, ОТДАТЬ)",
                                    definition="", lemmas=["ПОСВЯТИТЬ"]),
                    ],
                ),
                _eq.EnSynset(pos="adverb", lemmas=["anyway"], groups=[]),
            ]

    class FakeRuBackend:
        def ru_synsets(self, word):
            from bilingual import equivalents as _eq
            if word != "хлеб":
                return []
            return [
                _eq.EnSynset(
                    pos="noun",
                    lemmas=["хлеб", "хлебушек"],
                    groups=[
                        _eq.RuGroup(title="", definition="food made from dough",
                                    lemmas=["bread", "breadstuff"]),
                    ],
                ),
                _eq.EnSynset(pos="noun", lemmas=["хлебный злак"], groups=[]),
            ]

    def test_reverse_resolution_verbatim_gloss(self):
        from bilingual import equivalents as _eq
        senses = _eq.resolve_word("хлеб", backend=self.FakeRuBackend(),
                                  direction="ru-en")
        self.assertEqual(len(senses), 2)
        self.assertTrue(senses[0].linked)
        # EN equivalents verbatim, gloss untouched, RU lemmas as synonyms
        self.assertEqual(senses[0].equivalents, ["bread", "breadstuff"])
        self.assertEqual(senses[0].definition, "food made from dough")
        self.assertEqual(senses[0].synonyms, ["хлеб", "хлебушек"])
        self.assertEqual(senses[0].pos, "noun")
        # unlinked RU synset: synonyms only, no equivalents
        self.assertFalse(senses[1].linked)
        self.assertEqual(senses[1].equivalents, [])
        self.assertEqual(senses[1].synonyms, ["хлебный злак"])

    def test_resolution_counts_and_fallbacks(self):
        from bilingual import equivalents as _eq
        senses = _eq.resolve_word("give", backend=self.FakeBackend())
        self.assertEqual(len(senses), 3)
        self.assertTrue(all(s.linked for s in senses[:2]))
        # definition kept as-is (natural case)
        self.assertEqual(senses[0].definition, "передать нечто в дар.")
        # empty definition falls back to the sentence-cased title
        self.assertEqual(senses[1].definition, "Посвятить (предназначить, отдать)")
        # unlinked sense keeps synonyms, ships nothing, counts as unlinked
        self.assertFalse(senses[2].linked)
        self.assertEqual(senses[2].equivalents, [])
        self.assertEqual(senses[2].synonyms, ["anyway"])

    def test_russian_pos_and_cards(self):
        from bilingual import equivalents as _eq
        senses = _eq.resolve_word("give", backend=self.FakeBackend())
        text = "\n".join(_dsl.emit_card(_dsl.Card(
            headword="give",
            senses=[_dsl.Sense(definition=s.definition,
                               equivalents=list(s.equivalents),
                               synonyms=[x for x in s.synonyms if x != "give"],
                               pos=_eq.russian_pos(s.pos)) for s in senses])))
        # the headword itself is not its own synonym
        self.assertNotIn("(syn. give,", text)
        self.assertIn("(syn. present)", text)

    def test_report_counts_unlinked(self):
        from bilingual import equivalents as _eq
        _cards, report = _eq.resolve_words(
            ["give", "zzznosuchword"], backend=self.FakeBackend())
        self.assertEqual(report.words, 2)
        self.assertEqual(report.words_no_en, 1)
        self.assertEqual(report.synsets, 2)
        self.assertEqual(report.synsets_linked, 1)

    def test_resolve_cache_hit_miss_and_corrupt(self):
        import json as _json
        from bilingual import equivalents as _eq

        class ExplodingBackend:
            def en_synsets(self, word):
                raise AssertionError("must not resolve on a cache hit")

        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "resolve.json")
            first, _ = _eq.resolve_words(
                ["give"], backend=self.FakeBackend(),
                cache_path=cache, cache_id="db-v1")
            self.assertTrue(os.path.isfile(cache))
            # hit: backend would explode, cached cards come back identical
            second, rep = _eq.resolve_words(
                ["give"], backend=ExplodingBackend(),
                cache_path=cache, cache_id="db-v1")
            self.assertEqual(
                [s.equivalents for s in second["give"]],
                [s.equivalents for s in first["give"]])
            self.assertEqual((rep.words, rep.synsets), (1, 2))
            # stale key (different words / new db): rebuilds through the backend
            third, _ = _eq.resolve_words(
                ["give", "zzz"], backend=self.FakeBackend(),
                cache_path=cache, cache_id="db-v1")
            self.assertEqual(set(third), {"give", "zzz"})
            # corrupt cache file: ignored, rebuilt
            with open(cache, "w", encoding="utf-8") as f:
                f.write("{not json")
            fourth, _ = _eq.resolve_words(
                ["give"], backend=self.FakeBackend(),
                cache_path=cache, cache_id="db-v1")
            self.assertEqual(
                [s.equivalents for s in fourth["give"]],
                [s.equivalents for s in first["give"]])

    def test_progress_callback_fires(self):
        from bilingual import equivalents as _eq
        seen = []
        words = ["w%d" % i for i in range(2500)]
        _eq.resolve_words(words, backend=self.FakeBackend(),
                          progress=lambda done, total: seen.append((done, total)))
        self.assertEqual(seen, [(1000, 2500), (2000, 2500)])

    def test_case_variant_lookup_finds_capitalized(self):
        import sqlite3
        from bilingual import equivalents as _eq
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "wn.db")
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE wn_sense (key TEXT, name TEXT, synset_id TEXT)")
            con.executemany("INSERT INTO wn_sense VALUES (?,?,?)", [
                ("amsterdam%1:15:00::", "Amsterdam", "08949737-n"),
                ("dog%1:05:00::", "dog", "02084071-n"),
            ])
            con.commit()
            con.close()
            self.assertEqual(_eq.find_case_variant_synsets(db, "Amsterdam"),
                             ["08949737-n"])
            self.assertEqual(_eq.find_case_variant_synsets(db, "AMSTERDAM"),
                             ["08949737-n"])
            # exact-lowercase names match too (harmless: the main lookup path
            # wins first, so the fallback never fires for them in practice)
            self.assertEqual(_eq.find_case_variant_synsets(db, "dog"),
                             ["02084071-n"])
            self.assertEqual(_eq.find_case_variant_synsets(db, "zzz"), [])
            self.assertEqual(_eq.find_case_variant_synsets(db, ""), [])

    def test_empty_headword_gets_no_card(self):
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["give", "zzznosuchword"], out, "empty-en-ru", "Empty",
                sources=_prov.Sources(tatoeba_date="2026-10-17"),
                backend=self.FakeBackend())
            self.assertEqual(summary["cards"], 1)
            self.assertEqual(summary["skipped_empty"], 1)
            text = _package.read(summary["dz_path"])
            self.assertIn("\ngive\n", text)
            self.assertNotIn("zzznosuchword", text)

    def test_reverse_sample_build_end_to_end(self):
        # ru->en through build_sample: flipped corpus, RU resolver, English
        # POS labels, EN-anchored example, RU audio untouched (no snapshot)
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            import sys as _sys
            _sys.path.insert(0, SCRIPTS)
            from bilingual import tatoeba as _tat
            pairs = [("Eat bread.", "Ешь хлеб."), ("I go.", "Иду.")]
            corpus = _tat.Corpus(
                pairs=pairs, index=_tat.index_pairs(pairs),
                index_ru=_tat.index_pairs([(ru, en) for en, ru in pairs],
                                          lang="ru")).flipped()
            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["хлеб", "zzz"], out, "rev-en-ru", "Rev",
                sources=_prov.Sources(tatoeba_date="2026-10-17",
                                      equivalents=True, direction="ru-en"),
                corpus=corpus, backend=self.FakeRuBackend(),
                direction="ru-en")
            self.assertEqual(summary["cards"], 1)
            self.assertEqual(summary["skipped_empty"], 1)
            text = _package.read(summary["dz_path"])
            self.assertIn("\nхлеб\n", text)
            self.assertIn("    [p]noun[/p]", text)
            self.assertIn("[trn]bread[/trn]", text)
            self.assertIn("[i]food made from dough[/i]", text)
            self.assertIn("(syn. хлебушек)", text)
            self.assertIn("[ex]Ешь хлеб.[/ex]", text)
            self.assertIn("[trn]Eat bread.[/trn]", text)
            self.assertIn("a Russian-English translation dictionary", text)

    def test_numbering_is_text_not_tag(self):
        # [m10]+ are unknown tags to the reader (single-digit [mN] only);
        # numbering rides as text on [m1], kaikki-style, at any sense count
        sense = _dsl.Sense(definition="d", equivalents=["x"])
        lines = _dsl.emit_sense(sense, 12)
        self.assertIn("    [m1]12.[/m]", lines)
        self.assertIn("    [i]d[/i]", lines)
        self.assertFalse(any("[m10" in ln for ln in lines))

    def test_empty_synonyms_no_line(self):
        lines = _dsl.emit_sense(
            _dsl.Sense(definition="d", equivalents=["x"], synonyms=[]), 1)
        self.assertFalse(any("(syn." in ln for ln in lines))

    def test_pairs_card_flat_with_marked_translation(self):
        card = _dsl.Card(headword="dog",
                         pairs=[("Good dog!", "Хорошая собака!")])
        text = "\n".join(_dsl.emit_card(card))
        # pairs ARE the article: no zone, no sense numbering; the Russian
        # line is marked as a translation, not an example
        self.assertNotIn("[*]", text)
        self.assertNotIn("[m1]", text)
        self.assertIn("[ex]Good dog![/ex]", text)
        self.assertIn("[trn]Хорошая собака![/trn]", text)

    def test_pairs_preview(self):
        html = _preview.render([_dsl.Card(headword="dog",
                                          pairs=[("Good dog!", "Хорошая собака!")])],
                               "t")
        self.assertIn("Good dog!", html)


class PairsBuildTest(unittest.TestCase):
    def _tat_dir(self, tmp):
        import bz2
        eng = os.path.join(tmp, "eng_sentences.tsv.bz2")
        rus = os.path.join(tmp, "rus_sentences.tsv.bz2")
        links = os.path.join(tmp, "eng-rus_links.tsv.bz2")
        with bz2.open(eng, "wt", encoding="utf-8") as f:
            f.write("1\teng\tGood dog!\n2\teng\tI like bread.\n")
        with bz2.open(rus, "wt", encoding="utf-8") as f:
            f.write("10\trus\tХорошая собака!\n11\trus\tЛюблю хлеб.\n")
        with bz2.open(links, "wt", encoding="utf-8") as f:
            f.write("1\t10\n2\t11\n")
        return tmp

    def test_build_pairs_end_to_end(self):
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            tat_dir = self._tat_dir(tmp)
            import sys as _sys
            _sys.path.insert(0, SCRIPTS)
            from bilingual import tatoeba as _tat
            corpus = _tat.acquire(
                os.path.join(tat_dir, "eng_sentences.tsv.bz2"),
                os.path.join(tat_dir, "rus_sentences.tsv.bz2"),
                os.path.join(tat_dir, "eng-rus_links.tsv.bz2"),
                "2026-10-17")
            out = os.path.join(tmp, "out")
            summary = _build.build_pairs(
                ["dog", "bread", "zzz"], out, "pairs-en-ru", "Pairs",
                sources=_prov.Sources(tatoeba_date="2026-10-17", equivalents=False),
                corpus=corpus, keep=3)
            self.assertEqual(summary["cards"], 2)
            self.assertEqual(summary["unresolved"], [])
            text = _package.read(summary["dz_path"])
            self.assertIn("About Pairs", text)
            self.assertIn("Tatoeba", text)
            self.assertNotIn("RuWordNet thesaurus, non-commercial", text)
            self.assertNotIn("Princeton WordNet", text)
            self.assertIn("[ex]Good dog![/ex]", text)

    def test_junk_headwords_skipped(self):
        # stray quotes, suffix fragments, numbers and empties never get cards
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            tat_dir = self._tat_dir(tmp)
            import sys as _sys
            _sys.path.insert(0, SCRIPTS)
            from bilingual import tatoeba as _tat
            corpus = _tat.acquire(
                os.path.join(tat_dir, "eng_sentences.tsv.bz2"),
                os.path.join(tat_dir, "rus_sentences.tsv.bz2"),
                os.path.join(tat_dir, "eng-rus_links.tsv.bz2"),
                "2026-10-17")
            out = os.path.join(tmp, "out")
            summary = _build.build_pairs(
                ["dog", "'dog", "-er", "007", ""], out, "junk",
                sources=_prov.Sources(tatoeba_date="2026-10-17", equivalents=False),
                corpus=corpus, keep=3)
            self.assertEqual(summary["cards"], 1)
            self.assertEqual(summary["skipped_shape"], 4)
            text = _package.read(summary["dz_path"])
            self.assertIn("\ndog\n", text)
            self.assertNotIn("'dog", text)

    def test_case_variants_merge_to_attested_form(self):
        # maduro/Maduro with identical bodies collapse into one card; the
        # lowercase form wins when the pairs spell it lowercase (common noun),
        # otherwise the capitalized form stands (proper noun: Sisyphus)
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            eng = os.path.join(tmp, "eng.tsv")
            rus = os.path.join(tmp, "rus.tsv")
            links = os.path.join(tmp, "links.tsv")
            with open(eng, "w", encoding="utf-8") as f:
                f.write("1\teng\tGood dog!\n2\ten\tSisyphus pushes rock.\n"
                        "3\ten\tAA and Aa play.\n")
            with open(rus, "w", encoding="utf-8") as f:
                f.write("10\trus\tХороший пёсик!\n11\trus\tСизиф толкает камень.\n"
                        "12\trus\tАА и Аа играют.\n")
            with open(links, "w", encoding="utf-8") as f:
                f.write("1\t10\n2\t11\n3\t12\n")
            import sys as _sys
            _sys.path.insert(0, SCRIPTS)
            from bilingual import tatoeba as _tat
            corpus = _tat.acquire(eng, rus, links, "2026-10-17")
            out = os.path.join(tmp, "out")
            summary = _build.build_pairs(
                ["Dog", "dog", "Sisyphus", "AA", "Aa", "zzz"], out, "case",
                sources=_prov.Sources(tatoeba_date="2026-10-17", equivalents=False),
                corpus=corpus, keep=3)
            self.assertEqual(summary["cards"], 3)
            text = _package.read(summary["dz_path"])
            for head in ("\ndog\n", "\nSisyphus\n", "\nAA\n"):
                self.assertIn(head, text)
            for head in ("\nDog\n", "\nAa\n"):
                self.assertNotIn(head, text)

    def test_cli_pairs_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            tat_dir = self._tat_dir(tmp)
            out = os.path.join(tmp, "out")
            rc = _cli.main(["--mode", "pairs", "--tatoeba-dir", tat_dir,
                            "--tatoeba-date", "2026-10-17",
                            "--word", "dog", "--out-dir", out,
                            "--name", "cli-pairs", "--preview"])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(os.path.join(out, "cli-pairs.dsl.dz")))
            self.assertTrue(os.path.isfile(os.path.join(out, "cli-pairs.preview.html")))

    def test_build_pairs_russian_direction(self):
        # flipped view: Russian headwords match the RU side, case merges on
        # the RU spelling, junk is dropped, roles render [ex]RU/[trn]EN
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            tat_dir = self._tat_dir(tmp)
            import sys as _sys
            _sys.path.insert(0, SCRIPTS)
            from bilingual import tatoeba as _tat
            corpus = _tat.acquire(
                os.path.join(tat_dir, "eng_sentences.tsv.bz2"),
                os.path.join(tat_dir, "rus_sentences.tsv.bz2"),
                os.path.join(tat_dir, "eng-rus_links.tsv.bz2"),
                "2026-10-17").flipped()
            out = os.path.join(tmp, "out")
            summary = _build.build_pairs(
                ["Хлеб", "хлеб", "007", "dog"], out, "pairs-ru-en", "Pairs",
                sources=_prov.Sources(tatoeba_date="2026-10-17",
                                      equivalents=False, direction="ru-en"),
                corpus=corpus, keep=3)
            self.assertEqual(summary["cards"], 1)
            self.assertEqual(summary["skipped_shape"], 1)
            text = _package.read(summary["dz_path"])
            self.assertIn("\nхлеб\n", text)
            self.assertNotIn("\nХлеб\n", text)
            self.assertIn("[ex]Люблю хлеб.[/ex]", text)
            self.assertIn("[trn]I like bread.[/trn]", text)
            self.assertIn("Russian-English", text)
            self.assertIn("rus-eng", text)

    def test_cli_pairs_mode_source_lang_ru(self):
        with tempfile.TemporaryDirectory() as tmp:
            tat_dir = self._tat_dir(tmp)
            out = os.path.join(tmp, "out")
            rc = _cli.main(["--mode", "pairs", "--tatoeba-dir", tat_dir,
                            "--tatoeba-date", "2026-10-17",
                            "--source-lang", "ru",
                            "--word", "хлеб", "--out-dir", out,
                            "--name", "cli-ru-en"])
            self.assertEqual(rc, 0)
            text = _package.read(os.path.join(out, "cli-ru-en.dsl.dz"))
            self.assertIn("\nхлеб\n", text)
            self.assertIn("[ex]Люблю хлеб.[/ex]", text)
            self.assertIn("[trn]I like bread.[/trn]", text)
            self.assertIn("Russian-English", text)

    def test_cli_translation_mode_stubbed(self):
        # Hermetic: stub the RuWordNet backend, no snapshot, no audio, no net.
        from bilingual import build as _build
        from bilingual import equivalents as _eq
        real = _eq.resolve_words

        def fake(words, backend=None, progress=None, **_kw):
            cards = {"dog": [("сущ.", "домашнее животное",
                               ["собака"], ["doggo"], True)]}
            from bilingual import equivalents as _e2
            out = {}
            rep = _e2.ResolutionReport(words=len(words))
            for w in words:
                rep.synsets += 1
                rep.synsets_linked += 1
                out[w] = [_e2.ResolvedSense(pos="noun", definition="домашнее животное",
                                            equivalents=["собака"], synonyms=["doggo"],
                                            linked=True)] if w == "dog" else []
            return out, rep

        _eq.resolve_words = fake
        try:
            with tempfile.TemporaryDirectory() as tmp:
                rc = _cli.main(["--mode", "translation",
                                "--word", "dog", "--out-dir", os.path.join(tmp, "o"),
                                "--name", "cli-tr", "--no-audio", "--preview"])
                self.assertEqual(rc, 0)
        finally:
            _eq.resolve_words = real

    def test_lemma_universe_from_fixture_db(self):
        import sqlite3
        from bilingual import equivalents as _eq
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "wn.db")
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE wn_sense (key TEXT, name TEXT, synset_id TEXT)")
            con.executemany("INSERT INTO wn_sense VALUES (?,?,?)",
                            [("a%1", "dog", "1-n"), ("b%1", "hot_dog", "2-n"),
                             ("c%1", "dog", "1-n")])
            con.commit()
            con.close()
            self.assertEqual(_eq.english_lemma_universe(db), ["dog", "hot dog"])

    def test_kaikki_headwords_from_fixture_snapshot(self):
        import json as _json
        from bilingual import equivalents as _eq
        recs = [
            {"word": "bread", "lang_code": "en", "pos": "noun",
             "senses": [{"glosses": ["baked"]}]},
            {"word": "ran", "lang_code": "en", "pos": "verb",
             "senses": [{"glosses": ["past"], "form_of": [{"word": "run"}]}]},
            {"word": "pain", "lang_code": "fr", "pos": "noun",
             "senses": [{"glosses": ["bread"]}]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "s.jsonl")
            with open(snap, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(_json.dumps(r) + "\n")
            self.assertEqual(_eq.kaikki_headwords(snap), ["bread"])
            # language filter follows the snapshot language, not the default
            recs.append({"word": "хлеб", "lang_code": "ru", "pos": "noun",
                         "senses": [{"glosses": ["хлеб"]}]})
            with open(snap, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(_json.dumps(r) + "\n")
            self.assertEqual(_eq.kaikki_headwords(snap), ["bread"])
            self.assertEqual(_eq.kaikki_headwords(snap, "ru"), ["хлеб"])
            self.assertEqual(_eq.kaikki_headwords(snap, "fr"), ["pain"])

    def test_all_kaikki_needs_snapshot(self):
        with self.assertRaises(SystemExit) as ctx:
            _cli.main(["--mode", "pairs", "--all-kaikki"])
        self.assertEqual(ctx.exception.code, 2)

    def test_comments_emit_after_audio(self):
        card = _dsl.Card(headword="About X", comments=["line one", "line two"])
        text = "\n".join(_dsl.emit_card(card))
        self.assertIn("[com]line one[/com]", text)
        self.assertIn("[com]line two[/com]", text)


class ProvenanceTest(unittest.TestCase):
    ITEMS = ["Princeton WordNet", "RuWordNet", "Non-commercial",
             "Tatoeba", "CC BY 2.0 FR", "2021", "2026-10-17", "2026-09-02"]

    def test_three_artifacts_carry_all_items(self):
        from bilingual import provenance as _prov
        sources = _prov.Sources(
            pwn="Princeton WordNet 3.0", ruwordnet="RuWordNet 2.0 (2021)",
            tatoeba_date="2026-10-17", kaikki_dump_date="2026-09-02")
        with tempfile.TemporaryDirectory() as tmp:
            path, _text = _package.build(
                [_dsl.Card(headword="bread")], tmp, "prov-en-ru", "Prov",
                about=_prov.about_card("Prov", sources, 1))
            dsl_text = _package.read(path)
            # metadata headers identify the dictionary
            self.assertIn('#NAME "Prov"', dsl_text)
            # about article carries every item
            for item in self.ITEMS:
                self.assertIn(item, dsl_text, f"about card lacks {item!r}")
            # sibling annotation carries every item
            ann = os.path.join(tmp, "prov-en-ru.ann")
            _prov.write_annotation(ann, "Prov", sources, 1)
            with open(ann, encoding="utf-8") as f:
                ann_text = f.read()
            for item in self.ITEMS:
                self.assertIn(item, ann_text, f"annotation lacks {item!r}")
            # distribution statement present in both
            self.assertIn("Non-commercial use and distribution only", dsl_text)
            self.assertIn("Non-commercial use and distribution only", ann_text)

    def test_about_opens_dictionary(self):
        from bilingual import provenance as _prov
        sources = _prov.Sources()
        with tempfile.TemporaryDirectory() as tmp:
            _path, text = _package.build(
                [_dsl.Card(headword="bread")], tmp, "prov-en-ru", "Prov",
                about=_prov.about_card("Prov", sources, 1))
            self.assertLess(text.index("About Prov"), text.index("\nbread\n"))

    def test_reversed_direction_names_it(self):
        from bilingual import provenance as _prov
        sources = _prov.Sources(tatoeba_date="2026-10-17", equivalents=False,
                                direction="ru-en")
        text = "\n".join(_prov.description_lines("R", sources, 5))
        self.assertIn("a Russian-English example-sentences dictionary", text)
        self.assertIn("Tatoeba rus-eng pairs, snapshot 2026-10-17", text)
        self.assertNotIn("eng-rus", text)
        # default direction keeps the old wording verbatim
        old = "\n".join(_prov.description_lines(
            "E", _prov.Sources(tatoeba_date="2026-10-17", equivalents=False), 5))
        self.assertIn("an English-Russian example-sentences dictionary", old)
        self.assertIn("Tatoeba eng-rus pairs", old)

    def test_reversed_translation_names_it(self):
        from bilingual import provenance as _prov
        sources = _prov.Sources(tatoeba_date="2026-10-17", kaikki_dump_date="2026-09-01",
                                equivalents=True, direction="ru-en")
        text = "\n".join(_prov.description_lines("R", sources, 5))
        self.assertIn("a Russian-English translation dictionary", text)
        self.assertIn("Tatoeba rus-eng pairs, snapshot 2026-10-17", text)
        self.assertIn("Non-commercial use and distribution only", text)
        # default direction keeps the old wording verbatim
        old = "\n".join(_prov.description_lines(
            "E", _prov.Sources(tatoeba_date="2026-10-17", equivalents=True), 5))
        self.assertIn("an English-Russian translation dictionary", old)
        self.assertIn("Tatoeba eng-rus pairs", old)


class AudioTest(unittest.TestCase):
    def _fixture(self, tmp):
        snap = os.path.join(tmp, "sample.jsonl")
        recs = [
            {"word": "bread", "lang_code": "en", "lang": "English", "pos": "noun",
             "senses": [{"glosses": ["baked food"]}],
             "sounds": [
                 {"audio": "En-us-bread.ogg",
                  "ogg_url": "https://upload.wikimedia.org/x/En-us-bread.ogg",
                  "mp3_url": "https://upload.wikimedia.org/x/En-us-bread.mp3",
                  "tags": ["US"]},
                 {"audio": "En-uk-bread.ogg",
                  "ogg_url": "https://upload.wikimedia.org/x/En-uk-bread.ogg"},
                 {"audio": "notes.txt",
                  "ogg_url": "https://upload.wikimedia.org/x/notes.txt"},
                 {"audio": "En-us-bread.ogg",
                  "ogg_url": "https://upload.wikimedia.org/x/En-us-bread.ogg"},
             ]},
            {"word": "silent", "lang_code": "en", "lang": "English", "pos": "noun",
             "senses": [{"glosses": ["no sound"]}], "sounds": []},
        ]
        with open(snap, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        return snap

    def _stub_downloader(self, payload=b"fake-audio"):
        def dl(url, dest):
            with open(dest, "wb") as f:
                f.write(payload)
            return dest
        return dl

    def test_plan_matches_kaikki_decisions(self):
        # Same planner over the same records: bilingual wiring must decide
        # exactly what the kaikki EN card would carry.
        # exactly what the kaikki EN card would carry.
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = self._fixture(tmp)
            names, _planner = _aud.plan_words(
                ["bread", "silent"], snap, per_word=3, audio_lang="US",
                download_dir=os.path.join(tmp, "cache"),
                downloader=self._stub_downloader(), available=set())
            # bread: US ogg preferred, uk ogg second; .txt skipped, dupe merged
            self.assertEqual(names["bread"], ["En-us-bread.ogg", "En-uk-bread.ogg"])
            self.assertEqual(names["silent"], [])

    def test_collect_records_follows_snapshot_language(self):
        # the reverse dictionary reuses the RU stage: same filter, RU records
        import json as _json
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "ru.jsonl")
            recs = [
                {"word": "хлеб", "lang_code": "ru", "pos": "noun",
                 "senses": [{"glosses": ["хлеб"]}],
                 "sounds": [{"audio": "Ru-хлеб.ogg",
                             "ogg_url": "https://upload.wikimedia.org/x/Ru-хлеб.ogg"}]},
                {"word": "bread", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["baked"]}], "sounds": []},
            ]
            with open(snap, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(_json.dumps(r) + "\n")
            found = _aud.collect_records(snap, ["хлеб", "bread"], lang="ru")
            self.assertEqual(set(found), {"хлеб", "bread"})
            self.assertEqual(len(found["хлеб"]), 1)
            self.assertEqual(found["bread"], [])
            self.assertEqual(
                _aud.collect_records(snap, ["хлеб"], lang="en"), {"хлеб": []})

    def test_verbatim_against_kaikki_planner(self):
        # Independent cross-check: kaikki's own AudioPlan over the same fixture
        # records must yield the same per-word sets the wiring returns.
        import sys as _sys
        from bilingual import audio as _aud
        _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from kaikki.audio import AudioPlan
        from kaikki.source import is_inflected, is_lexical
        with tempfile.TemporaryDirectory() as tmp:
            snap = self._fixture(tmp)
            names, _planner = _aud.plan_words(
                ["bread"], snap, per_word=3, audio_lang="US",
                download_dir=os.path.join(tmp, "cache"),
                downloader=self._stub_downloader(), available=set())
            import json as _json
            ref: list[str] = []
            seen: set[str] = set()
            planner = AudioPlan(3, "US", True, set(), self._stub_downloader())
            planner.download_dir = os.path.join(tmp, "cache2")
            with open(snap, encoding="utf-8") as f:
                for line in f:
                    record = _json.loads(line)
                    if record.get("word") != "bread" or not is_lexical(record) \
                            or is_inflected(record):
                        continue
                    for name in planner.plan(record):
                        if name not in seen:
                            seen.add(name)
                            ref.append(name)
            self.assertEqual(names["bread"], ref[:3])

    def test_card_refs_and_bundle_resolve(self):
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = self._fixture(tmp)
            names, planner = _aud.plan_words(
                ["bread", "silent"], snap, per_word=3, audio_lang="US",
                download_dir=os.path.join(tmp, "cache"),
                downloader=self._stub_downloader(), available=set())
            cards = _aud.attach_audio(
                [_dsl.Card(headword="bread", pos="сущ.",
                           senses=[_dsl.Sense(definition="d")]),
                 _dsl.Card(headword="silent", pos="сущ.",
                           senses=[_dsl.Sense(definition="d")])],
                names)
            text = "\n".join(l for c in cards for l in _dsl.emit_card(c))
            self.assertIn("[s]En-us-bread.ogg[/s]", text)
            path = os.path.join(tmp, "t-en-ru.dsl.dz")
            import gzip as _gzip
            with open(path, "wb") as f:
                f.write(_gzip.compress(text.encode("utf-8")))
            bundle = _aud.bundle_for(planner, path, "zip", archive_path=None)
            self.assertIsNotNone(bundle)
            check = _aud.verify(path, bundle)
            self.assertEqual(check["unresolved"], [])

    def test_disabled_means_no_audio(self):
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = self._fixture(tmp)
            names, planner = _aud.plan_words(["bread"], snap, enabled=False)
            self.assertEqual(names, {"bread": []})
            self.assertIsNone(_aud.bundle_for(planner, os.path.join(tmp, "x.dsl.dz")))


if __name__ == "__main__":
    unittest.main()
