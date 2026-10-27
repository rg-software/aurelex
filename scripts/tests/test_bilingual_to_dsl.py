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

    def test_pos_sections_mirror_emit_card(self):
        # POS lives per sense in real builds: sections restart numbering and
        # a lone sense carries no counter — exactly like dsl.emit_card.
        card = _dsl.Card(headword="run", senses=[
            _dsl.Sense(definition="d1", equivalents=["e1"], pos="сущ."),
            _dsl.Sense(definition="d2", equivalents=["e2"], pos="сущ."),
            _dsl.Sense(definition="d3", equivalents=["e3"], pos="гл."),
        ])
        html = _preview.render([card], "t")
        self.assertEqual(html.count(">сущ.<"), 1)
        self.assertEqual(html.count(">гл.<"), 1)
        self.assertIn("<b>1.</b>", html)
        self.assertIn("<b>2.</b>", html)
        self.assertNotIn("<b>3.</b>", html)

    def test_preview_renders_readings_line(self):
        card = _dsl.Card(headword="犬", readings="音: ケン　訓: いぬ",
                         senses=[_dsl.Sense(definition="d",
                                            equivalents=["dog"])])
        html = _preview.render([card], "t")
        self.assertIn("音: ケン", html)
        self.assertIn("訓: いぬ", html)


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

    def test_fallback_skips_pairs_used_by_earlier_senses(self):
        # The concordance fallback never repeats a pair already shown under
        # an earlier sense of the same card: the second anchor-less sense
        # takes the next-shortest unused pair, and a sense with nothing
        # unused left carries no example.
        from bilingual import tatoeba as _tat
        freq = _tat.Counter()
        pairs = [("I saw a dog.", "私は一匹の犬を見た。"),
                 ("My dog ran away.", "飼い犬が逃げた。")]
        first = _tat.select_for_sense(["нетакого"], pairs, freq,
                                      target_lang="ja")
        self.assertEqual(first, ("I saw a dog.", "私は一匹の犬を見た。"))
        second = _tat.select_for_sense(["нетакого"], pairs, freq,
                                       target_lang="ja", exclude=[first])
        self.assertEqual(second, ("My dog ran away.", "飼い犬が逃げた。"))
        self.assertIsNone(
            _tat.select_for_sense(["нетакого"], pairs, freq,
                                  target_lang="ja", exclude=[first, second]))
        # Anchored picks also skip the used-set: a later sense takes its
        # next-best unused anchor rather than repeating an earlier sense's.
        self.assertEqual(
            _tat.select_for_sense(["犬", "飼い犬"], pairs, freq,
                                  target_lang="ja", exclude=[first]),
            ("My dog ran away.", "飼い犬が逃げた。"))

    def test_fallback_skips_shared_source_or_translation(self):
        # Same source sentence with a different translation (or vice versa)
        # is still a repeat: the fallback skips both.
        from bilingual import tatoeba as _tat
        freq = _tat.Counter()
        pairs = [("Same here.", "同じだ。"),
                 ("Same here!", "同じだよ。"),
                 ("Other one.", "別のもの。")]
        self.assertEqual(
            _tat.select_for_sense(["ZZZ"], pairs, freq,
                                  target_lang="ja", exclude=[pairs[0]]),
            ("Other one.", "別のもの。"))

    def test_fallback_never_steals_a_later_senses_anchor(self):
        # Card order: sense 1 anchors pair A, sense 2 is anchor-less, sense 3
        # anchors pair B. Greedy fallback would hand B to sense 2 and leave
        # sense 3 repeating it; reservation gives sense 2 the vacant pair C.
        from bilingual import tatoeba as _tat
        freq = _tat.Counter({"EQONE": 5, "EQTWO": 3})
        pairs = [("s1 here", "EQONE here"),
                 ("s2 here now", "EQTWO here now"),
                 ("s3 here now long", "neutral text here")]
        reserved = [
            _tat.best_anchor(["EQONE"], pairs, freq),
            _tat.best_anchor(["ZZZ"], pairs, freq),
            _tat.best_anchor(["EQTWO"], pairs, freq),
        ]
        self.assertEqual(reserved[0], ("s1 here", "EQONE here"))
        self.assertIsNone(reserved[1])
        self.assertEqual(reserved[2], ("s2 here now", "EQTWO here now"))
        used = [p for p in reserved if p is not None]
        self.assertEqual(
            _tat.select_for_sense(["ZZZ"], pairs, freq, exclude=used),
            ("s3 here now long", "neutral text here"))

    def test_card_wide_reservation_end_to_end(self):
        # Three senses, one card: s1 anchors pair A, s2 is anchor-less, s3
        # anchors pair B. The fallback for s2 must take the vacant pair C,
        # not steal B from s3.
        from bilingual import build as _build
        from bilingual import equivalents as _eq
        from bilingual import provenance as _prov

        class ThreeSenseBackend:
            def en_synsets(self, word):
                if word != "here":
                    return []
                return [
                    _eq.EnSynset(pos="noun", lemmas=["here"], groups=[
                        _eq.RuGroup(title="", definition="first",
                                    lemmas=["EQONE"])]),
                    _eq.EnSynset(pos="noun", lemmas=["here"], groups=[
                        _eq.RuGroup(title="", definition="second",
                                    lemmas=["ZZZ"])]),
                    _eq.EnSynset(pos="noun", lemmas=["here"], groups=[
                        _eq.RuGroup(title="", definition="third",
                                    lemmas=["EQTWO"])]),
                ]

        pairs = [("s1 here", "EQONE here"),
                 ("s2 here now", "EQTWO here now"),
                 ("s3 here now long", "neutral text here")]
        with tempfile.TemporaryDirectory() as tmp:
            from bilingual import tatoeba as _tat
            corpus = _tat.Corpus(
                pairs=pairs, lang="en", tgt_lang="ru",
                index=_tat.index_pairs(pairs),
                index_ru=_tat.index_pairs([(t, s) for s, t in pairs],
                                          lang="ru"),
                rus_freq=_tat.Counter({"EQONE": 5, "EQTWO": 3}),
                eng_freq=_tat.Counter())
            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["here"], out, "reserve", "Reserve",
                sources=_prov.Sources(tatoeba_date="2026-10-17",
                                      equivalents=True, direction="en-ru"),
                corpus=corpus, backend=ThreeSenseBackend(), direction="en-ru")
            text = _package.read(summary["dz_path"])
            self.assertIn("[trn]EQONE here[/trn]", text)
            self.assertIn("[trn]EQTWO here now[/trn]", text)
            self.assertIn("[trn]neutral text here[/trn]", text)
            # no pair repeats on the card
            self.assertEqual(text.count("[trn]EQONE here[/trn]"), 1)
            self.assertEqual(text.count("[trn]EQTWO here now[/trn]"), 1)

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
            if word == "пустой":
                return [_eq.EnSynset(pos="noun", lemmas=["пустой"], groups=[])]
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

    def test_junk_headwords_skipped_before_resolution(self):
        # Thesaurus lemma universes contain bare numbers and stray
        # punctuation ("0", "'hood"): not headwords, never resolved.
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["give", "007", "'dog", ""], out, "junk-en-ru", "Junk",
                sources=_prov.Sources(tatoeba_date="2026-10-17"),
                backend=self.FakeBackend())
            self.assertEqual(summary["cards"], 1)
            self.assertEqual(summary["skipped_shape"], 3)
            text = _package.read(summary["dz_path"])
            self.assertNotIn("007", text)

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
            # the unlinked shell (synonyms but no equivalents, no definition)
            # is omitted: no numbered section, no synonyms line for it, and
            # the lone survivor carries no counter
            self.assertNotIn("хлебный злак", text)
            self.assertNotIn("[m1]", text)

    def test_unlinked_only_headword_gets_no_card(self):
        # resolve still counts the unlinked synset (coverage), but with
        # nothing displayable the headword joins skipped_empty
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["пустой"], out, "rev-empty", "Rev",
                sources=_prov.Sources(equivalents=True, direction="ru-en"),
                backend=self.FakeRuBackend(), direction="ru-en")
            self.assertEqual(summary["cards"], 0)
            self.assertEqual(summary["skipped_empty"], 1)
            self.assertEqual(summary["synsets"], 1)
            self.assertEqual(summary["synsets_linked"], 0)

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


class JapaneseBackendTest(unittest.TestCase):
    class FakeJaBackend:
        def en_synsets_ja(self, word):
            from bilingual import equivalents as _eq
            if word != "dog":
                return []
            return [
                _eq.EnSynset(
                    pos="noun", lemmas=["dog"],
                    groups=[_eq.RuGroup(title="", definition="イヌ科の動物",
                                        lemmas=["犬", "イヌ"])]),
                _eq.EnSynset(pos="verb", lemmas=["dog", "chase"], groups=[]),
            ]

        def ja_synsets(self, word):
            from bilingual import equivalents as _eq
            if word != "犬":
                return []
            return [_eq.EnSynset(
                pos="noun", lemmas=["犬"],
                groups=[_eq.RuGroup(title="", definition="a domestic animal",
                                    lemmas=["dog", "domestic dog"])])]

        def ja_to_ru(self, word):
            from bilingual import equivalents as _eq
            if word != "犬":
                return []
            return [_eq.EnSynset(
                pos="noun", lemmas=["犬"],
                groups=[_eq.RuGroup(title="СОБАКА", definition="домашнее животное",
                                    lemmas=["собака"])])]

        def ru_to_ja(self, word):
            from bilingual import equivalents as _eq
            if word != "хлеб":
                return []
            return [_eq.EnSynset(
                pos="noun", lemmas=["хлеб"],
                groups=[_eq.RuGroup(title="", definition="小麦のパン",
                                    lemmas=["パン"])])]

    def test_en_ja_resolution(self):
        from bilingual import equivalents as _eq
        senses = _eq.resolve_word("dog", backend=self.FakeJaBackend(),
                                  direction="en-ja")
        self.assertEqual(len(senses), 2)
        self.assertTrue(senses[0].linked)
        self.assertEqual(senses[0].equivalents, ["犬", "イヌ"])
        self.assertEqual(senses[0].definition, "イヌ科の動物")
        self.assertEqual(senses[0].pos, "noun")
        self.assertFalse(senses[1].linked)
        self.assertEqual(senses[1].synonyms, ["dog", "chase"])

    def test_ja_en_verbatim_gloss(self):
        from bilingual import equivalents as _eq
        senses = _eq.resolve_word("犬", backend=self.FakeJaBackend(),
                                  direction="ja-en")
        self.assertEqual(len(senses), 1)
        self.assertEqual(senses[0].equivalents, ["dog", "domestic dog"])
        self.assertEqual(senses[0].definition, "a domestic animal")

    def test_pivot_both_ways(self):
        from bilingual import equivalents as _eq
        ru = _eq.resolve_word("犬", backend=self.FakeJaBackend(), direction="ja-ru")
        self.assertEqual(len(ru), 1)
        self.assertEqual(ru[0].equivalents, ["собака"])
        self.assertEqual(ru[0].definition, "домашнее животное")
        ja = _eq.resolve_word("хлеб", backend=self.FakeJaBackend(), direction="ru-ja")
        self.assertEqual(len(ja), 1)
        self.assertEqual(ja[0].equivalents, ["パン"])
        self.assertEqual(ja[0].definition, "小麦のパン")

    def test_report_counts_unlinked(self):
        from bilingual import equivalents as _eq
        _cards, report = _eq.resolve_words(
            ["dog", "zzznosuchword"], backend=self.FakeJaBackend(),
            direction="en-ja")
        self.assertEqual(report.words, 2)
        self.assertEqual(report.words_no_en, 1)
        self.assertEqual(report.synsets, 2)
        self.assertEqual(report.synsets_linked, 1)

    def test_japanese_pos_labels(self):
        from bilingual import equivalents as _eq
        self.assertEqual(_eq.japanese_pos("noun"), "名詞")
        self.assertEqual(_eq.japanese_pos("verb"), "動詞")
        self.assertEqual(_eq.japanese_pos("adjective"), "形容詞")
        self.assertEqual(_eq.japanese_pos("adverb"), "副詞")
        self.assertEqual(_eq.japanese_pos("?"), "?")

    def test_english_ja_universe_stub(self):
        from types import SimpleNamespace
        from bilingual import equivalents as _eq

        def syn(sid, lemmas):
            return SimpleNamespace(id=sid, lemmas=lambda: list(lemmas))

        stub = SimpleNamespace(
            ja_suffixes=lambda: {"0001-n"},
            iter_en_synsets=lambda: [syn("x-0001-n", ["dog", "hot_dog"]),
                                     syn("x-0002-n", ["zzz"])],
        )
        self.assertEqual(_eq.english_ja_universe(backend=stub),
                         ["dog", "hot dog"])

    def test_ru_pos_from_ili_empty_means_unlinked(self):
        # Regression: a RU synset with no `ili` rows crashed the POS lookup
        # (empty list indexed as [0]). It must resolve unlinked with the RU
        # part of speech instead.
        from bilingual import equivalents as _eq
        self.assertEqual(_eq._ru_pos_from_ili([], "N"), "noun")
        self.assertEqual(_eq._ru_pos_from_ili([], "V"), "verb")
        self.assertEqual(_eq._ru_pos_from_ili([], "Adj"), "adjective")
        self.assertEqual(_eq._ru_pos_from_ili([], "?"), "?")
        self.assertEqual(_eq._ru_pos_from_ili(["01281782-v"], "N"), "verb")
        self.assertEqual(_eq._ru_pos_from_ili(["10323529-n"], "V"), "noun")

    def test_build_sample_en_ja_pos_and_omission(self):
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["dog", "zzz"], out, "sample-en-ja", "Sample",
                sources=_prov.Sources(equivalents=True, direction="en-ja"),
                backend=self.FakeJaBackend(), direction="en-ja")
            self.assertEqual(summary["cards"], 1)
            text = _package.read(summary["dz_path"])
            self.assertIn("    [p]名詞[/p]", text)
            self.assertIn("[trn]犬[/trn]", text)
            self.assertIn("[i]イヌ科の動物[/i]", text)
            # unlinked verb shell (synonyms, no equivalents, no definition)
            # is omitted: no "chase" line survives
            self.assertNotIn("chase", text)

    def test_rank_equivalents_japanese_phrase_counts(self):
        from bilingual import equivalents as _eq
        freq = {"犬": 1559, "ドッグ": 34, "飼い犬": 19, "洋犬": 0, "戌": 0}
        ranked = _eq.rank_equivalents(
            ["戌", "洋犬", "飼い犬", "ドッグ", "犬"],
            freq, target_lang="ja")
        self.assertEqual(ranked[:2], ["犬", "ドッグ"])
        self.assertEqual(ranked[-2:], ["戌", "洋犬"])

    def test_count_phrases_narrows_through_index(self):
        from bilingual import tatoeba as _tat
        pairs = [("I saw a dog.", "私は一匹の犬を見た。"),
                 ("My dog ran away.", "飼い犬が逃げた。")]
        corpus = _tat.Corpus(
            pairs=pairs, lang="en", tgt_lang="ja",
            index=_tat.index_pairs(pairs, lang="en"),
            index_ru=_tat.index_pairs([(t, s) for s, t in pairs], lang="ja"))
        counts = _tat.count_phrases(["犬", "飼い犬", "不存在"], corpus)
        self.assertEqual(counts["犬"], 2)  # 飼い犬 contains 犬 as a substring
        self.assertEqual(counts["飼い犬"], 1)
        self.assertEqual(counts["不存在"], 0)

    def test_emit_japanese_target_card(self):
        # Japanese-target card: Japanese POS labels, equivalents lead,
        # definition follows, numbering restarts per POS, lone sense bare.
        card = _dsl.Card(headword="犬", senses=[
            _dsl.Sense(definition="d1", equivalents=["e1"],
                       synonyms=["s1"], pos="名詞",
                       example=("a", "b")),
            _dsl.Sense(definition="d2", equivalents=["e2"],
                       synonyms=["s2"], pos="名詞"),
            _dsl.Sense(definition="d3", equivalents=["e3"],
                       synonyms=["s3"], pos="動詞"),
        ])
        text = "\n".join(_dsl.emit_card(card))
        self.assertEqual(text.count("[p]名詞[/p]"), 1)
        self.assertEqual(text.count("[p]動詞[/p]"), 1)
        self.assertIn("[m1]1.[/m]", text)
        self.assertIn("[m1]2.[/m]", text)
        self.assertNotIn("[m1]3.[/m]", text)
        self.assertLess(text.index("[trn]e1[/trn]"), text.index("[i]d1[/i]"))

    def test_cli_direction_ja(self):
        from bilingual import cli as _cli
        args = _cli.build_parser().parse_args(
            ["--source-lang", "ja", "--target-lang", "en"])
        self.assertEqual(_cli._resolve_direction(args), "ja-en")
        args = _cli.build_parser().parse_args(
            ["--source-lang", "ru", "--target-lang", "ja"])
        self.assertEqual(_cli._resolve_direction(args), "ru-ja")

    def test_help_covers_documented_options(self):
        # Every --flag named in docs/BILINGUAL-BUILDER.md must exist in
        # --help, so the option table cannot drift from the CLI.
        import pathlib as _pathlib
        import re as _re
        from bilingual import cli as _cli
        text = _cli.build_parser().format_help()
        doc = (_pathlib.Path(__file__).resolve().parent.parent.parent
               / "docs" / "BILINGUAL-BUILDER.md").read_text(encoding="utf-8")
        for flag in sorted(set(_re.findall(r"--[a-zA-Z][\w-]*", doc))):
            self.assertIn(flag, text, f"{flag} documented but missing from --help")

    def test_provenance_all_four_japanese_directions(self):
        from bilingual import provenance as _prov
        cases = {
            "en-ja": ("an English-Japanese translation dictionary", "eng-jpn", False),
            "ja-en": ("a Japanese-English translation dictionary", "jpn-eng", False),
            "ja-ru": ("a Japanese-Russian translation dictionary", "jpn-rus", True),
            "ru-ja": ("a Russian-Japanese translation dictionary", "rus-jpn", True),
        }
        for direction, (kind, pair_label, noncommercial) in cases.items():
            sources = _prov.Sources(tatoeba_date="D", equivalents=True,
                                    direction=direction)
            text = "\n".join(_prov.description_lines("T", sources, 5))
            self.assertIn(kind, text, direction)
            self.assertIn(f"Tatoeba {pair_label} pairs", text, direction)
            self.assertEqual("Non-commercial use and distribution only" in text,
                             noncommercial, direction)
            self.assertIn("https://bond-lab.github.io/wnja/", text, direction)

    def test_build_sample_ja_en_readings_line(self):
        import json as _json
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "ja.jsonl")
            rec = {"word": "犬", "lang_code": "ja", "lang": "Japanese",
                   "pos": "noun", "senses": [{"glosses": ["dog"]}],
                   "forms": [{"form": "ケン", "tags": ["transliteration", "go-on"]},
                             {"form": "いぬ", "tags": ["transliteration", "kun"]}],
                   "sounds": []}
            with open(snap, "w", encoding="utf-8") as f:
                f.write(_json.dumps(rec) + "\n")
            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["犬"], out, "sample-ja-en", "Sample",
                sources=_prov.Sources(equivalents=True, direction="ja-en"),
                snapshot_path=snap, backend=self.FakeJaBackend(),
                audio_lang_code="ja", direction="ja-en")
            self.assertEqual(summary["cards"], 1)
            text = _package.read(summary["dz_path"])
            self.assertIn("[com]音: ケン　訓: いぬ[/com]", text)

    def test_ja_audio_and_transcription_end_to_end(self):
        import json as _json
        import tarfile as _tarfile
        import zipfile as _zipfile
        from bilingual import audio as _aud
        from bilingual import build as _build
        from bilingual import equivalents as _eq
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "ja-av.jsonl")
            recs = [
                {"word": "inu", "lang_code": "ja", "lang": "Japanese",
                 "pos": "noun", "senses": [{"glosses": ["dog"]}],
                 "forms": [{"form": "いぬ", "tags": ["transliteration"]}],
                 "sounds": [{"audio": "Ja-inu.ogg",
                             "ogg_url": "https://x/Ja-inu.ogg",
                             "ipa": "いぬ"}]},
                {"word": "silent", "lang_code": "ja", "lang": "Japanese",
                 "pos": "noun", "senses": [{"glosses": ["quiet"]}],
                 "forms": [], "sounds": []},
            ]
            with open(snap, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(_json.dumps(r) + "\n")
            tar = os.path.join(tmp, "aud.tar")
            with _tarfile.open(tar, "w") as t:
                blob = b"fake-audio"
                info = _tarfile.TarInfo("Ja-inu.ogg")
                info.size = len(blob)
                import io as _io
                t.addfile(info, _io.BytesIO(blob))

            class JaBackend:
                def ja_synsets(self, word):
                    if word != "inu":
                        return []
                    return [_eq.EnSynset(
                        pos="noun", lemmas=["inu"],
                        groups=[_eq.RuGroup(
                            title="", definition="a domestic animal",
                            lemmas=["dog"])])]

            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["inu", "silent", "zzz"], out, "ja-en-av", "JAAV",
                sources=_prov.Sources(tatoeba_date="2026-10-24",
                                      equivalents=True, direction="ja-en"),
                snapshot_path=snap, archive_path=tar,
                download_dir=os.path.join(tmp, "cache"),
                backend=JaBackend(), audio_lang_code="ja",
                direction="ja-en")
            self.assertEqual(summary["cards"], 1)
            self.assertEqual(summary["unresolved"], [])
            text = _package.read(summary["dz_path"])
            self.assertIn("[s]Ja-inu.ogg[/s]", text)
            self.assertIn("[t]いぬ[/t]", text)
            names = _zipfile.ZipFile(summary["bundle_path"]).namelist()
            self.assertEqual(names, ["Ja-inu.ogg"])
            # transcription is absent, not empty, where the snapshot has none
            self.assertEqual(
                _aud.transcribe_words(["silent"], snap, lang="ja"), {})

    def test_reading_aliases_translation(self):
        import json as _json
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "ja.jsonl")
            rec = {"word": "犬", "lang_code": "ja", "lang": "Japanese",
                   "pos": "noun", "senses": [{"glosses": ["dog"]}],
                   "forms": [{"form": "ケン", "tags": ["transliteration", "go-on"]},
                             {"form": "いぬ", "tags": ["transliteration", "kun"]}],
                   "sounds": []}
            with open(snap, "w", encoding="utf-8") as f:
                f.write(_json.dumps(rec) + "\n")
            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["犬"], out, "sample-ja-en", "Sample",
                sources=_prov.Sources(equivalents=True, direction="ja-en"),
                snapshot_path=snap, backend=self.FakeJaBackend(),
                audio_lang_code="ja", direction="ja-en",
                index_readings=True)
            # primary card plus one alias per hiragana reading
            self.assertEqual(summary["cards"], 3)
            text = _package.read(summary["dz_path"])
            for head in ("\n犬\n", "\nけん\n", "\nいぬ\n"):
                self.assertIn(head, text)
            # aliases open with the primary headword as title
            self.assertEqual(text.count("[b]犬[/b]"), 2)

    def test_reading_alias_collision_keeps_real_card(self):
        from bilingual import build as _build
        from bilingual import dsl as _dsl
        cards = [_dsl.Card(headword="犬",
                           senses=[_dsl.Sense(definition="d",
                                              equivalents=["dog"])]),
                 _dsl.Card(headword="いぬ",
                           senses=[_dsl.Sense(definition="kana dog",
                                              equivalents=["dog"])])]
        out = _build._with_reading_aliases(
            cards, {"犬": ["いぬ", "けん"]})
        self.assertEqual([c.headword for c in out], ["犬", "いぬ", "けん"])
        self.assertEqual(out[2].title, "犬")
        # the real いぬ card keeps its own article, not the alias text
        self.assertIn("kana dog", out[1].senses[0].definition)


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

    def test_headword_hygiene(self):
        # Letter-start everywhere; digit-start native spellings only for
        # Japanese; pure numbers nowhere.
        from bilingual import build as _build
        self.assertTrue(_build.headword_ok("dog", "en"))
        self.assertTrue(_build.headword_ok("хлеб", "ru"))
        self.assertTrue(_build.headword_ok("犬", "ja"))
        self.assertTrue(_build.headword_ok("10代", "ja"))
        self.assertTrue(_build.headword_ok("10月", "ja"))
        self.assertFalse(_build.headword_ok("007", "en"))
        self.assertFalse(_build.headword_ok("1000", "ja"))
        self.assertFalse(_build.headword_ok("10代", "en"))
        self.assertFalse(_build.headword_ok("", "en"))
        self.assertFalse(_build.headword_ok("'dog", "en"))

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

    def test_transcription_line_after_headword(self):
        card = _dsl.Card(headword="bread", transcription="bɹɛd",
                         senses=[_dsl.Sense(definition="d",
                                            equivalents=["хлеб"])])
        lines = _dsl.emit_card(card)
        self.assertEqual(lines[0], "bread")
        self.assertEqual(lines[1], "    [t]bɹɛd[/t]")
        # brackets are escaped once at emit (the picker value is raw)
        card = _dsl.Card(headword="хлеб", transcription="[xlʲep]")
        lines = _dsl.emit_card(card)
        self.assertEqual(lines[1], "    [t]\\[xlʲep\\][/t]")
        self.assertEqual(_dsl.unescape_dsl("\\[xlʲep\\]"), "[xlʲep]")
        # no transcription, no line (and no placeholder)
        bare = _dsl.emit_card(_dsl.Card(headword="x"))
        self.assertEqual(bare, ["x"])

    def test_headers_name_direction_languages(self):
        from bilingual import build as _build
        self.assertEqual(_build._pair_langs("en-ru"),
                         {"index_lang": "English", "contents_lang": "Russian"})
        self.assertEqual(_build._pair_langs("ru-en"),
                         {"index_lang": "Russian", "contents_lang": "English"})
        text = _dsl.assemble([], "n", "T", **_build._pair_langs("ru-en"))
        self.assertIn('#INDEX_LANGUAGE "Russian"', text)
        self.assertIn('#CONTENTS_LANGUAGE "English"', text)
        text = _dsl.assemble([], "n", "T", **_build._pair_langs("en-ru"))
        self.assertIn('#INDEX_LANGUAGE "English"', text)
        self.assertIn('#CONTENTS_LANGUAGE "Russian"', text)


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

    def test_transcribe_words_picks_notation(self):
        import json as _json
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "tr.jsonl")
            recs = [
                {"word": "bread", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["baked"]}],
                 "sounds": [{"audio": "En-us-bread.ogg",
                             "ogg_url": "https://x/En-us-bread.ogg",
                             "ipa": "bɹɛd"}]},
                {"word": "bread", "lang_code": "en", "pos": "verb",
                 "senses": [{"glosses": ["bake"]}],
                 "sounds": [{"ipa": "bɹɛd"},
                            {"ipa": "bred", "tags": ["X-SAMPA"]}]},
                {"word": "lead", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["metal"]}],
                 "sounds": [{"enpr": "lEd"}]},
                {"word": "silent", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["quiet"]}], "sounds": []},
                {"word": "xsampa", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["x"]}],
                 "sounds": [{"ipa": "zzz", "tags": ["X-SAMPA"]}]},
            ]
            with open(snap, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(_json.dumps(r) + "\n")
            got = _aud.transcribe_words(
                ["bread", "lead", "silent", "xsampa", "missing"], snap)
            # most common across records wins; X-SAMPA-tagged sounds are skipped
            self.assertEqual(got["bread"], "bɹɛd")
            # enPR keeps its label, IPA does not take one
            self.assertEqual(got["lead"], "enPR: lEd")
            # no transcribed record: absent, not empty
            self.assertNotIn("silent", got)
            self.assertNotIn("xsampa", got)
            self.assertNotIn("missing", got)

    def test_transcribe_tie_goes_first_seen(self):
        import json as _json
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "tie.jsonl")
            recs = [
                {"word": "w", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["a"]}], "sounds": [{"ipa": "AAA"}]},
                {"word": "w", "lang_code": "en", "pos": "verb",
                 "senses": [{"glosses": ["b"]}], "sounds": [{"ipa": "BBB"}]},
            ]
            with open(snap, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(_json.dumps(r) + "\n")
            self.assertEqual(
                _aud.transcribe_words(["w"], snap), {"w": "AAA"})

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

    def test_collect_records_memo_is_per_word_list(self):
        # A second call with different headwords must not return the first
        # call's word-filtered result (same snapshot, same language).
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = self._fixture(tmp)
            first = _aud.collect_records(snap, ["bread"], lang="en")
            self.assertEqual(set(first), {"bread"})
            self.assertEqual(len(first["bread"]), 1)
            second = _aud.collect_records(snap, ["silent"], lang="en")
            self.assertEqual(set(second), {"silent"})
            self.assertEqual(len(second["silent"]), 1)

    def _ja_readings_fixture(self, tmp):
        import json as _json
        snap = os.path.join(tmp, "ja-read.jsonl")
        recs = [
            {"word": "yomi", "lang_code": "ja", "lang": "Japanese", "pos": "noun",
             "senses": [{"glosses": ["reading"]}],
             "forms": [{"form": "あ", "tags": ["transliteration"]}],
             "sounds": []},
            {"word": "yomi", "lang_code": "ja", "lang": "Japanese", "pos": "noun",
             "senses": [{"glosses": ["reading"]}],
             "forms": [{"form": "あ", "tags": ["transliteration"]}],
             "sounds": []},
            {"word": "yomi", "lang_code": "ja", "lang": "Japanese", "pos": "noun",
             "senses": [{"glosses": ["reading"]}],
             "forms": [{"form": "い", "tags": ["transliteration"]}],
             "sounds": []},
        ]
        with open(snap, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(_json.dumps(r) + "\n")
        return snap

    def test_reading_lines_vote_most_common(self):
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = self._ja_readings_fixture(tmp)
            self.assertEqual(
                _aud.reading_lines(["yomi"], snap, lang="ja"),
                {"yomi": "読み: あ"})

    def test_reading_lines_tie_goes_first_seen(self):
        import json as _json
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "tie.jsonl")
            recs = [
                {"word": "w", "lang_code": "ja", "pos": "noun",
                 "senses": [{"glosses": ["x"]}],
                 "forms": [{"form": "あ", "tags": ["transliteration"]}]},
                {"word": "w", "lang_code": "ja", "pos": "noun",
                 "senses": [{"glosses": ["x"]}],
                 "forms": [{"form": "い", "tags": ["transliteration"]}]},
            ]
            with open(snap, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(_json.dumps(r) + "\n")
            self.assertEqual(
                _aud.reading_lines(["w"], snap, lang="ja"), {"w": "読み: あ"})

    def test_reading_lines_absent_without_readings(self):
        from bilingual import audio as _aud
        with tempfile.TemporaryDirectory() as tmp:
            snap = self._fixture(tmp)
            self.assertEqual(
                _aud.reading_lines(["bread", "silent"], snap, lang="en"), {})

    def test_ja_audio_and_transcription_end_to_end(self):
        import json as _json
        import tarfile as _tarfile
        import zipfile as _zipfile
        from bilingual import audio as _aud
        from bilingual import build as _build
        from bilingual import equivalents as _eq
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "ja-av.jsonl")
            rec = {"word": "inu", "lang_code": "ja", "lang": "Japanese",
                   "pos": "noun", "senses": [{"glosses": ["dog"]}],
                   "forms": [{"form": "いぬ", "tags": ["transliteration", "kun"]}],
                   "sounds": [{"audio": "Ja-inu.ogg",
                               "ogg_url": "https://x/Ja-inu.ogg",
                               "ipa": "いぬ"}]}
            with open(snap, "w", encoding="utf-8") as f:
                f.write(_json.dumps(rec) + "\n")
            tar = os.path.join(tmp, "aud.tar")
            with _tarfile.open(tar, "w") as t:
                blob = b"fake-audio"
                info = _tarfile.TarInfo("Ja-inu.ogg")
                info.size = len(blob)
                import io as _io
                t.addfile(info, _io.BytesIO(blob))

            class JaBackend:
                def ja_synsets(self, word):
                    if word != "inu":
                        return []
                    return [_eq.EnSynset(
                        pos="noun", lemmas=["inu"],
                        groups=[_eq.RuGroup(
                            title="", definition="a domestic animal",
                            lemmas=["dog"])])]

            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["inu", "zzz"], out, "ja-en-av", "JAAV",
                sources=_prov.Sources(tatoeba_date="2026-10-24",
                                      equivalents=True, direction="ja-en"),
                snapshot_path=snap, archive_path=tar,
                download_dir=os.path.join(tmp, "cache"),
                backend=JaBackend(), audio_lang_code="ja",
                direction="ja-en")
            self.assertEqual(summary["cards"], 1)
            self.assertEqual(summary["unresolved"], [])
            text = _package.read(summary["dz_path"])
            self.assertIn("[s]Ja-inu.ogg[/s]", text)
            self.assertIn("[t]いぬ[/t]", text)
            names = _zipfile.ZipFile(summary["bundle_path"]).namelist()
            self.assertEqual(names, ["Ja-inu.ogg"])
            # transcription is absent, not empty, where the snapshot has none
            self.assertEqual(
                _aud.transcribe_words(["zzz"], snap, lang="ja"), {})

    def test_skipped_headword_bundles_no_audio(self):
        # "ghost" has recordings in the snapshot but resolves to no card:
        # its audio must not ride the sibling bundle as dead weight.
        import tarfile as _tarfile
        from bilingual import audio as _aud
        from bilingual import build as _build
        from bilingual import equivalents as _eq
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            snap = self._fixture(tmp)
            rec = {"word": "ghost", "lang_code": "en", "lang": "English",
                   "pos": "noun", "senses": [{"glosses": ["spook"]}],
                   "sounds": [{"audio": "En-ghost.ogg",
                               "ogg_url": "https://x/En-ghost.ogg"}]}
            with open(snap, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            tar = os.path.join(tmp, "aud.tar")
            with _tarfile.open(tar, "w") as t:
                for name in ("En-us-bread.ogg", "En-uk-bread.ogg", "En-ghost.ogg"):
                    blob = name.encode("utf-8")
                    info = _tarfile.TarInfo(name)
                    info.size = len(blob)
                    import io as _io
                    t.addfile(info, _io.BytesIO(blob))

            class Backend:
                def en_synsets(self, word):
                    if word != "bread":
                        return []
                    return [_eq.EnSynset(
                        pos="noun", lemmas=["bread"],
                        groups=[_eq.RuGroup(title="", definition="d",
                                            lemmas=["хлеб"])])]

            out = os.path.join(tmp, "out")
            summary = _build.build_sample(
                ["bread", "ghost"], out, "no-orphan", "NoOrphan",
                sources=_prov.Sources(tatoeba_date="2026-10-17"),
                snapshot_path=snap, archive_path=tar,
                download_dir=os.path.join(tmp, "cache"),
                backend=Backend(), direction="en-ru")
            self.assertEqual(summary["cards"], 1)
            import zipfile as _zipfile
            names = _zipfile.ZipFile(summary["bundle_path"]).namelist()
            self.assertIn("En-us-bread.ogg", names)
            self.assertNotIn("En-ghost.ogg", names)


class JapanesePairsTest(unittest.TestCase):
    def _tat_dir_ja(self, tmp):
        import bz2
        eng = os.path.join(tmp, "eng_sentences.tsv.bz2")
        jpn = os.path.join(tmp, "jpn_sentences.tsv.bz2")
        links = os.path.join(tmp, "eng-jpn_links.tsv.bz2")
        with bz2.open(eng, "wt", encoding="utf-8") as f:
            f.write("1\teng\tGood morning.\n2\teng\tI like sushi.\n")
        with bz2.open(jpn, "wt", encoding="utf-8") as f:
            f.write("10\tjpn\tおはようございます。\n11\tjpn\t寿司が好きです。\n")
        with bz2.open(links, "wt", encoding="utf-8") as f:
            f.write("1\t10\n2\t11\n")
        return tmp

    def _tat_dir_ja_ru(self, tmp):
        import bz2
        jpn = os.path.join(tmp, "jpn_sentences.tsv.bz2")
        rus = os.path.join(tmp, "rus_sentences.tsv.bz2")
        links = os.path.join(tmp, "jpn-rus_links.tsv.bz2")
        with bz2.open(jpn, "wt", encoding="utf-8") as f:
            f.write("1\tjpn\t寿司が好きです。\n")
        with bz2.open(rus, "wt", encoding="utf-8") as f:
            f.write("10\trus\tЛюблю суши.\n")
        with bz2.open(links, "wt", encoding="utf-8") as f:
            f.write("1\t10\n")
        return tmp

    def test_acquire_eng_jpn_order(self):
        from bilingual import tatoeba as _tat
        with tempfile.TemporaryDirectory() as tmp:
            d = self._tat_dir_ja(tmp)
            corpus = _tat.acquire(
                os.path.join(d, "eng_sentences.tsv.bz2"),
                os.path.join(d, "jpn_sentences.tsv.bz2"),
                os.path.join(d, "eng-jpn_links.tsv.bz2"),
                "2026-10-24", src_lang="en", tgt_lang="ja")
            self.assertEqual(corpus.lang, "en")
            self.assertEqual(corpus.tgt_lang, "ja")
            self.assertEqual(len(corpus.pairs), 2)
            self.assertIn(("Good morning.", "おはようございます。"), corpus.pairs)

    def test_japanese_substring_match(self):
        from bilingual import tatoeba as _tat
        pairs = [("寿司が好きです。", "Люблю суши."),
                 ("おはようございます。", "Доброе утро.")]
        corpus = _tat.Corpus(pairs=pairs, lang="ja", tgt_lang="ru",
                             index=_tat.index_pairs(pairs, lang="ja"),
                             index_ru=_tat.index_pairs(
                                 [(t, s) for s, t in pairs], lang="ru"))
        self.assertEqual(_tat.pairs_for("寿司", corpus), [pairs[0]])
        self.assertEqual(_tat.pairs_for("好き", corpus), [pairs[0]])
        # single kanji is a complete word: it matches (no single-char bar)
        self.assertEqual(_tat.pairs_for("日", corpus), [])
        self.assertEqual(_tat.pairs_for("鮨", corpus), [])
        single = [("日本は島国だ。", "Japan is an island country.")]
        corpus1 = _tat.Corpus(pairs=single, lang="ja", tgt_lang="ru",
                              index=_tat.index_pairs(single, lang="ja"))
        self.assertEqual(_tat.pairs_for("日", corpus1), single)
        # latin invisible on the Japanese side
        self.assertEqual(_tat.pairs_for("sushi", corpus), [])

    def test_target_side_dedupe_skips_repeated_translation(self):
        # Two source groups sharing one translation ship once: the first
        # (shortest) group wins and the duplicate leaves room for variety.
        from bilingual import tatoeba as _tat
        pairs = [("Я купил хлеб.", "パン買ったよ。"),
                 ("Я купила хлеб.", "パン買ったよ。"),
                 ("Кто съел хлеб?", "誰がパンを食べたの？")]
        kept = _tat.select(pairs, [], _tat.Counter(), keep=3, target_lang="ru")
        self.assertEqual(kept, [("Я купил хлеб.", "パン買ったよ。"),
                                ("Кто съел хлеб?", "誰がパンを食べたの？")])
        # Same for the Japanese target side (substring discipline).
        pairs_ja = [("It's a book.", "本だ。"),
                    ("It is a book.", "本だ。"),
                    ("It's my book.", "それは僕の本です。")]
        kept_ja = _tat.select(pairs_ja, [], _tat.Counter(), keep=3,
                              target_lang="ja")
        self.assertEqual(kept_ja, [("It's a book.", "本だ。"),
                                   ("It's my book.", "それは僕の本です。")])

    def test_punctuation_variants_share_one_group(self):
        # "Give me water!" vs "Give me water." are the same sentence for
        # selection purposes: one group, one pair, room for variety.
        from bilingual import tatoeba as _tat
        pairs = [("Give me water!", "水をくれ！"),
                 ("Give me water.", "水をくれ。"),
                 ("Water, please.", "水をください。")]
        kept = _tat.select(pairs, [], _tat.Counter(), keep=3, target_lang="ja")
        self.assertEqual(kept, [("Give me water!", "水をくれ！"),
                                ("Water, please.", "水をください。")])
        # Same in the other direction and for the old pair (Russian target).
        pairs_ru = [("Give me water!", "Дай мне воды!"),
                    ("Give me water.", "Дайте мне воды.")]
        self.assertEqual(len(_tat.select(pairs_ru, [], _tat.Counter(), keep=3)),
                         1)

    def test_japanese_anchored_ranking(self):
        from bilingual import tatoeba as _tat
        freq = _tat.Counter({"寿司": 5, "好き": 500})
        self.assertEqual(
            _tat.rank_variants(["寿司が好きです。", "おはようございます。"],
                               ["寿司"], freq, target_lang="ja"),
            "寿司が好きです。")
        self.assertEqual(
            _tat.select_for_sense(["寿司"], [("Good morning.", "おはようございます。"),
                                             ("I like sushi.", "寿司が好きです。")],
                                  freq, target_lang="ja"),
            ("I like sushi.", "寿司が好きです。"))
        # fallback: shortest source ships when nothing anchors
        self.assertEqual(
            _tat.select_for_sense(["存在しない"], [("Good morning.", "おはようございます。"),
                                                   ("Hi.", "やあ。")],
                                  freq, target_lang="ja"),
            ("Hi.", "やあ。"))

    def test_build_pairs_en_ja_headers_and_about(self):
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            d = self._tat_dir_ja(tmp)
            from bilingual import tatoeba as _tat
            corpus = _tat.acquire(
                os.path.join(d, "eng_sentences.tsv.bz2"),
                os.path.join(d, "jpn_sentences.tsv.bz2"),
                os.path.join(d, "eng-jpn_links.tsv.bz2"),
                "2026-10-24", src_lang="en", tgt_lang="ja")
            out = os.path.join(tmp, "out")
            summary = _build.build_pairs(
                ["sushi", "morning", "zzz"], out, "pairs-en-ja", "Pairs",
                sources=_prov.Sources(tatoeba_date="2026-10-24",
                                      equivalents=False, direction="en-ja"),
                corpus=corpus, keep=3, direction="en-ja")
            self.assertEqual(summary["cards"], 2)
            text = _package.read(summary["dz_path"])
            self.assertIn('#INDEX_LANGUAGE "English"', text)
            self.assertIn('#CONTENTS_LANGUAGE "Japanese"', text)
            self.assertIn("English-Japanese", text)
            self.assertIn("eng-jpn", text)
            self.assertIn("[ex]I like sushi.[/ex]", text)
            self.assertIn("[trn]寿司が好きです。[/trn]", text)

    def test_build_pairs_ja_en_flipped(self):
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            d = self._tat_dir_ja(tmp)
            from bilingual import tatoeba as _tat
            corpus = _tat.acquire(
                os.path.join(d, "eng_sentences.tsv.bz2"),
                os.path.join(d, "jpn_sentences.tsv.bz2"),
                os.path.join(d, "eng-jpn_links.tsv.bz2"),
                "2026-10-24", src_lang="en", tgt_lang="ja").flipped()
            self.assertEqual(corpus.lang, "ja")
            out = os.path.join(tmp, "out")
            summary = _build.build_pairs(
                ["寿司", "zzz"], out, "pairs-ja-en", "Pairs",
                sources=_prov.Sources(tatoeba_date="2026-10-24",
                                      equivalents=False, direction="ja-en"),
                corpus=corpus, keep=3, direction="ja-en")
            self.assertEqual(summary["cards"], 1)
            text = _package.read(summary["dz_path"])
            self.assertIn('#INDEX_LANGUAGE "Japanese"', text)
            self.assertIn('#CONTENTS_LANGUAGE "English"', text)
            self.assertIn("[ex]寿司が好きです。[/ex]", text)
            self.assertIn("[trn]I like sushi.[/trn]", text)

    def test_build_pairs_ja_ru(self):
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            d = self._tat_dir_ja_ru(tmp)
            from bilingual import tatoeba as _tat
            corpus = _tat.acquire(
                os.path.join(d, "jpn_sentences.tsv.bz2"),
                os.path.join(d, "rus_sentences.tsv.bz2"),
                os.path.join(d, "jpn-rus_links.tsv.bz2"),
                "2026-10-24", src_lang="ja", tgt_lang="ru")
            out = os.path.join(tmp, "out")
            summary = _build.build_pairs(
                ["寿司", "zzz"], out, "pairs-ja-ru", "Pairs",
                sources=_prov.Sources(tatoeba_date="2026-10-24",
                                      equivalents=False, direction="ja-ru"),
                corpus=corpus, keep=3, direction="ja-ru")
            self.assertEqual(summary["cards"], 1)
            text = _package.read(summary["dz_path"])
            self.assertIn('#INDEX_LANGUAGE "Japanese"', text)
            self.assertIn('#CONTENTS_LANGUAGE "Russian"', text)
            self.assertIn("Japanese-Russian", text)

    def test_choose_case_japanese_no_case(self):
        from bilingual import build as _build
        pairs = [("寿司が好きです。", "Люблю суши.")]
        self.assertEqual(_build._choose_case("寿司", ["寿司"], pairs), "寿司")

    def test_cli_pairs_mode_ja(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._tat_dir_ja(tmp)
            out = os.path.join(tmp, "out")
            rc = _cli.main(["--mode", "pairs", "--tatoeba-dir", d,
                            "--tatoeba-date", "2026-10-24",
                            "--source-lang", "en", "--target-lang", "ja",
                            "--word", "sushi", "--out-dir", out,
                            "--name", "cli-en-ja"])
            self.assertEqual(rc, 0)
            text = _package.read(os.path.join(out, "cli-en-ja.dsl.dz"))
            self.assertIn("[trn]寿司が好きです。[/trn]", text)

    def test_cli_pairs_mode_ja_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._tat_dir_ja(tmp)
            out = os.path.join(tmp, "out")
            rc = _cli.main(["--mode", "pairs", "--tatoeba-dir", d,
                            "--tatoeba-date", "2026-10-24",
                            "--source-lang", "ja", "--target-lang", "en",
                            "--word", "寿司", "--out-dir", out,
                            "--name", "cli-ja-en"])
            self.assertEqual(rc, 0)
            text = _package.read(os.path.join(out, "cli-ja-en.dsl.dz"))
            self.assertIn("[ex]寿司が好きです。[/ex]", text)

    def test_pairs_index_readings_aliases(self):
        import json as _json
        from bilingual import build as _build
        from bilingual import provenance as _prov
        with tempfile.TemporaryDirectory() as tmp:
            rec = {"word": "寿司", "lang_code": "ja", "lang": "Japanese",
                   "pos": "noun", "senses": [{"glosses": ["sushi"]}],
                   "forms": [{"form": "すし", "tags": ["transliteration"]}],
                   "sounds": []}
            snap = os.path.join(tmp, "ja.jsonl")
            with open(snap, "w", encoding="utf-8") as f:
                f.write(_json.dumps(rec) + "\n")
            eng = os.path.join(tmp, "eng.tsv")
            jpn = os.path.join(tmp, "jpn.tsv")
            links = os.path.join(tmp, "links.tsv")
            with open(eng, "w", encoding="utf-8") as f:
                f.write("1\teng\tI like sushi.\n")
            with open(jpn, "w", encoding="utf-8") as f:
                f.write("10\tjpn\t寿司が好きです。\n")
            with open(links, "w", encoding="utf-8") as f:
                f.write("10\t1\n")
            from bilingual import tatoeba as _tat
            corpus = _tat.acquire(jpn, eng, links, "2026-10-24",
                                  src_lang="ja", tgt_lang="en")
            out = os.path.join(tmp, "out")
            summary = _build.build_pairs(
                ["寿司"], out, "pairs-ja-en", "Pairs",
                sources=_prov.Sources(tatoeba_date="2026-10-24",
                                      equivalents=False, direction="ja-en"),
                corpus=corpus, keep=3, direction="ja-en",
                snapshot_path=snap, index_readings=True)
            self.assertEqual(summary["cards"], 2)
            text = _package.read(summary["dz_path"])
            self.assertIn("\n寿司\n", text)
            self.assertIn("\nすし\n", text)
            self.assertIn("[b]寿司[/b]", text)

    def test_cli_index_readings_needs_snapshot(self):
        with self.assertRaises(SystemExit) as ctx:
            _cli.main(["--mode", "pairs", "--index-readings",
                       "--tatoeba-dir", "somewhere",
                       "--word", "寿司"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
