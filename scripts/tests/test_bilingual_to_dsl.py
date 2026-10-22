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
                    equivalents=["дарить", "подарить"],
                    synonyms=["present"],
                    example=("What shall I give her?", "Что мне ей подарить?"),
                )
            ],
        )
        text = "\n".join(_dsl.emit_card(card))
        def_pos = text.index("передать нечто в дар")
        trn_pos = text.index("[trn]дарить[/trn]")
        syn_pos = text.index("(syn. present)")
        ex_pos = text.index("[*]")
        self.assertTrue(0 < def_pos < trn_pos < syn_pos < ex_pos)
        self.assertIn("[/*]", text)

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
        )
        html = _preview.render([card], "sample")
        self.assertIn("<h2>bread</h2>", html)
        self.assertIn("сущ.", html)
        self.assertIn("изделие из муки", html)
        self.assertIn("хлеб", html)
        self.assertIn("syn. breadstuff", html)
        self.assertIn("Eat bread.", html)


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

    def test_resolution_counts_and_fallbacks(self):
        from bilingual import equivalents as _eq
        senses = _eq.resolve_word("give", backend=self.FakeBackend())
        self.assertEqual(len(senses), 3)
        self.assertTrue(all(s.linked for s in senses[:2]))
        # definition kept as-is (natural case)
        self.assertEqual(senses[0].definition, "передать нечто в дар.")
        # empty definition falls back to the lowercased title
        self.assertEqual(senses[1].definition, "посвятить (предназначить, отдать)")
        # unlinked sense keeps synonyms, ships nothing, counts as unlinked
        self.assertFalse(senses[2].linked)
        self.assertEqual(senses[2].equivalents, [])
        self.assertEqual(senses[2].synonyms, ["anyway"])

    def test_russian_pos_and_cards(self):
        from bilingual import equivalents as _eq
        senses = _eq.resolve_word("give", backend=self.FakeBackend())
        cards = _eq.to_cards("give", senses)
        self.assertEqual([c.pos for c in cards], ["гл.", "нареч."])
        self.assertEqual([len(c.senses) for c in cards], [2, 1])
        # the headword itself is not its own synonym
        text = "\n".join(_dsl.emit_card(cards[0]))
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

    def test_numbering_is_text_not_tag(self):
        # [m10]+ are unknown tags to the reader (single-digit [mN] only);
        # numbering rides as text on [m1], kaikki-style, at any sense count
        sense = _dsl.Sense(definition="d", equivalents=["x"])
        lines = _dsl.emit_sense(sense, 12)
        self.assertIn("    [m1]12. d[/m]", lines)
        self.assertFalse(any("[m10]" in ln for ln in lines))

    def test_empty_synonyms_no_line(self):
        lines = _dsl.emit_sense(
            _dsl.Sense(definition="d", equivalents=["x"], synonyms=[]), 1)
        self.assertFalse(any("(syn." in ln for ln in lines))

    def test_pairs_card_zone(self):
        card = _dsl.Card(headword="dog",
                         pairs=[("Good dog!", "Хорошая собака!")])
        text = "\n".join(_dsl.emit_card(card))
        self.assertIn("[*]", text)
        self.assertIn("[ex]Good dog![/ex]", text)
        self.assertIn("[ex]Хорошая собака![/ex]", text)
        self.assertIn("[/*]", text)
        self.assertNotIn("[m1]", text)

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
            self.assertEqual(summary["cards"], 3)
            self.assertEqual(summary["unresolved"], [])
            text = _package.read(summary["dz_path"])
            self.assertIn("About Pairs", text)
            self.assertIn("Tatoeba", text)
            self.assertNotIn("RuWordNet thesaurus, non-commercial", text)
            self.assertNotIn("Princeton WordNet", text)
            self.assertIn("[ex]Good dog![/ex]", text)

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

    def test_cli_translation_mode_stubbed(self):
        # Hermetic: stub the RuWordNet backend, no snapshot, no audio, no net.
        from bilingual import build as _build
        from bilingual import equivalents as _eq
        real = _eq.resolve_words

        def fake(words, backend=None):
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
