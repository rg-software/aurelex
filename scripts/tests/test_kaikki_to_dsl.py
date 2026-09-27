#!/usr/bin/env python3
"""Tests for scripts/kaikki-to-dsl.py.

Run with:  python -m unittest discover -s scripts/tests
"""

import gzip
import importlib.util
import io
import json
import os
import re
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
TOOL_PATH = os.path.join(SCRIPTS, "kaikki-to-dsl.py")
FIXTURE = os.path.join(HERE, "fixtures", "sample-en.jsonl")
EDGE_FIXTURE = os.path.join(HERE, "fixtures", "kaikki-edge.jsonl")
AUDIO_LIMIT_FIXTURE = os.path.join(HERE, "fixtures", "kaikki-audio-limit.jsonl")


def load_tool():
    spec = importlib.util.spec_from_file_location("kaikki_to_dsl", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


def read_dz(path):
    with open(path, "rb") as f:
        raw = gzip.decompress(f.read())
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8")


def headword_lines(text):
    return [
        ln for ln in text.splitlines()
        if ln and not ln[0].isspace() and not ln.startswith("#")
        and ln != "About this dictionary"
    ]


def make_tar(path, names):
    with tarfile.open(path, "w") as tar:
        for name in names:
            data = b"OGGDATA-" + name.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


class ConverterTests(unittest.TestCase):
    def args(self, out_dir, *extra):
        return TOOL.build_parser().parse_args(
            [
                "--source-lang", "en",
                "--jsonl", FIXTURE,
                "--out-dir", out_dir,
                "--no-audio",
                *extra,
            ]
        )

    def test_escape_dsl(self):
        self.assertEqual(TOOL.escape_dsl("a[b]c"), r"a\[b\]c")
        self.assertEqual(TOOL.escape_dsl("<<x>>"), r"\<\<x\>\>")
        self.assertEqual(TOOL.escape_dsl("a  b\nc"), "a b c")
        self.assertEqual(TOOL.escape_dsl("back\\slash"), "back\\\\slash")

    def test_default_build_base_forms_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = TOOL.build(self.args(tmp, "--sample", "20"))
            dz = os.path.join(tmp, "kaikki-en.dsl.dz")
            self.assertTrue(os.path.isfile(dz))
            self.assertFalse(os.path.isfile(os.path.join(tmp, "kaikki-en.dsl")))

            text = read_dz(dz)
            self.assertIn('#NAME "kaikki-en"', text)
            self.assertIn('#INDEX_LANGUAGE "English"', text)
            self.assertIn('#CONTENTS_LANGUAGE "English"', text)
            self.assertIn("[p]verb[/p]", text)
            self.assertIn("[p]noun[/p]", text)
            self.assertIn("[m1]", text)
            self.assertIn("[ex]I run every morning.[/ex]", text)
            self.assertIn("Forms: runs", text)
            # in a sample, cross-references are limited to words already
            # emitted, so "runner" (which comes after "run") is not linked
            self.assertNotIn("[ref]runner[/ref]", text)
            self.assertNotIn("[ref]sprint[/ref]", text)
            # base-form policy: the inflected entry "ran" is not a headword
            self.assertNotIn("ran", headword_lines(text))
            # non-lexical + blank word + German + malformed are not headwords
            self.assertNotIn("foo", headword_lines(text))
            self.assertNotIn("laufen", headword_lines(text))
            # the malformed fixture line carries no language marker, so the
            # scan's language prefilter skips it before it is ever parsed; such
            # lines are therefore not counted as malformed (see the full-build
            # counter test, which has no prefilter)
            self.assertGreaterEqual(report.skipped_nonlexical, 1)
            self.assertEqual(report.skipped_inflected, 1)

    def test_full_build_counts_malformed_records(self):
        # without --sample the scan parses every line, so a malformed one is seen
        with tempfile.TemporaryDirectory() as tmp:
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "en", "--jsonl", FIXTURE, "--out-dir", tmp, "--no-audio"]
            )
            report = TOOL.build(args)
            self.assertEqual(report.skipped_malformed, 1)

    def test_include_inflections(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(tmp, "--sample", "20", "--include-inflections"))
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            self.assertIn("ran", headword_lines(text))

    def test_sample_mode_random_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            def build(out):
                args = TOOL.build_parser().parse_args(
                    [
                        "--source-lang", "en",
                        "--jsonl", FIXTURE, "--out-dir", out,
                        "--sample", "3", "--sample-mode", "random", "--no-audio",
                    ]
                )
                return TOOL.build(args)

            out1, out2 = os.path.join(tmp, "a"), os.path.join(tmp, "b")
            build(out1)
            build(out2)
            dz1 = os.path.join(out1, "kaikki-en.dsl.dz")
            dz2 = os.path.join(out2, "kaikki-en.dsl.dz")
            with open(dz1, "rb") as f1, open(dz2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())
            heads = headword_lines(read_dz(dz1))
            self.assertEqual(len(heads), 3)
            for head in heads:
                self.assertIn(head, ["run", "runner", "escape", "multi"])

    def test_unsupported_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "zz", "--jsonl", FIXTURE, "--out-dir", tmp, "--no-audio"]
            )
            with self.assertRaises(SystemExit):
                TOOL.build(args)
            self.assertFalse(os.path.exists(os.path.join(tmp, "kaikki-zz-zz.dsl.dz")))

    def test_audio_zip_and_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["En-us-run.ogg", "En-us-multi.ogg", "En-uk-run.ogg"])

            def build(out):
                args = TOOL.build_parser().parse_args(
                    [
                        "--source-lang", "en",
                        "--jsonl", FIXTURE, "--out-dir", out,
                        "--sample", "20", "--audio-tar", tar_path, "--no-audio-download",
                        "--audio-per-word", "1", "--audio-lang", "US",
                    ]
                )
                return TOOL.build(args)

            out1, out2 = os.path.join(tmp, "a"), os.path.join(tmp, "b")
            report = build(out1)
            build(out2)
            self.assertGreaterEqual(report.audio_found, 1)
            self.assertEqual(report.missing_audio, 0)

            zip1 = os.path.join(out1, "kaikki-en.dsl.dz.files.zip")
            self.assertTrue(os.path.isfile(zip1))
            import zipfile
            with zipfile.ZipFile(zip1) as zf:
                names = sorted(zf.namelist())
            self.assertIn("En-us-run.ogg", names)
            self.assertIn("En-us-multi.ogg", names)
            self.assertNotIn("En-uk-run.ogg", names)

            dz1 = os.path.join(out1, "kaikki-en.dsl.dz")
            dz2 = os.path.join(out2, "kaikki-en.dsl.dz")
            with open(dz1, "rb") as f1, open(dz2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())
            zip2 = os.path.join(out2, "kaikki-en.dsl.dz.files.zip")
            with open(zip1, "rb") as f1, open(zip2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())

    def test_audio_dir_layout_and_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["En-us-run.ogg"])
            args = TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--jsonl", FIXTURE, "--out-dir", tmp,
                    "--sample", "1", "--audio-tar", tar_path, "--no-audio-download",
                    "--audio-per-word", "3", "--audio-layout", "dir", "--preview",
                ]
            )
            TOOL.build(args)
            self.assertTrue(os.path.isdir(os.path.join(tmp, "kaikki-en.dsl.dz.files")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, "kaikki-en.dsl.dz.files", "En-us-run.ogg")))
            preview = os.path.join(tmp, "kaikki-en.preview.html")
            self.assertTrue(os.path.isfile(preview))
            with open(preview, encoding="utf-8") as f:
                self.assertIn("preview", f.read())

    def test_missing_audio_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["something-else.ogg"])
            args = TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--jsonl", FIXTURE,
                    "--out-dir", tmp, "--sample", "20", "--audio-tar", tar_path, "--no-audio-download",
                ]
            )
            report = TOOL.build(args)
            self.assertEqual(report.audio_found, 0)
            self.assertGreater(report.missing_audio, 0)


class EdgeCaseTests(unittest.TestCase):
    """Regressions for the real kaikki snapshot's looser data shapes."""

    def args(self, out_dir, *extra):
        return TOOL.build_parser().parse_args(
            [
                "--source-lang", "en",
                "--jsonl", EDGE_FIXTURE,
                "--out-dir", out_dir,
                "--no-audio",
                *extra,
            ]
        )

    def test_audio_match_key_is_normalized(self):
        # case, spaces and percent-encoding all fold to the archive's form
        self.assertEqual(
            TOOL._audio_match_key("en-us-pub.ogg"),
            TOOL._audio_match_key("En-us-pub.ogg"),
        )
        self.assertEqual(
            TOOL._audio_match_key("En-au-herbed up.ogg"),
            TOOL._audio_match_key("En-au-herbed_up.ogg"),
        )
        self.assertEqual(
            TOOL._audio_match_key("LL-Q1860_%28eng%29-Vealhurl-pub.wav"),
            TOOL._audio_match_key("LL-Q1860 (eng)-Vealhurl-pub.wav"),
        )

    def test_audio_name_variants_cover_transcodes(self):
        # a compressed original is stored with an mp3 transcode beside it
        self.assertEqual(
            TOOL._audio_name_variants("En-us-pub.ogg")[:2],
            ["en-us-pub.ogg", "en-us-pub.ogg.mp3"],
        )
        # a wav original is only present transcoded
        self.assertIn("ll-..._(eng)-x.wav.ogg", TOOL._audio_name_variants("LL-... (eng)-x.wav"))

    def test_ipa_comes_from_a_separate_sound_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(tmp, "--sample", "20"))
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            self.assertIn("IPA: /pʌb/", text)

    def test_sample_counts_distinct_headwords(self):
        # "run" carries two records; a sample of N must still be N distinct words
        words = list(TOOL.iter_candidate_headwords(EDGE_FIXTURE, "en"))
        self.assertLess(len(set(words)), len(words))
        distinct = len(set(words))
        with tempfile.TemporaryDirectory() as tmp:
            report = TOOL.build(
                self.args(tmp, "--sample", str(distinct), "--sample-mode", "random")
            )
            heads = headword_lines(read_dz(os.path.join(tmp, "kaikki-en.dsl.dz")))
            self.assertEqual(len(heads), distinct)
            self.assertEqual(len(set(heads)), distinct)
            self.assertEqual(report.cards, distinct)

    def test_duplicate_records_share_one_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = TOOL.build(self.args(tmp, "--sample", "20"))
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            self.assertEqual(headword_lines(text).count("run"), 1)
            self.assertGreater(report.kept_records, report.cards)

    def test_audio_archive_name_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, [
                "audios/En-us-pub.ogg",
                "audios/En-au-herbed_up.ogg",
                "audios/En-au-sello.ogg.mp3",
                "audios/LL-Q1860_%28eng%29-Yangolin-bulk_carrier.wav.ogg",
            ])
            args = TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--jsonl", EDGE_FIXTURE,
                    "--out-dir", tmp, "--sample", "20", "--audio-tar", tar_path, "--no-audio-download",
                    "--audio-per-word", "2", "--no-audio-download",
                ]
            )
            report = TOOL.build(args)
            self.assertEqual(report.audio_found, 4)
            self.assertEqual(report.missing_audio, 0)
            import zipfile
            zip_path = os.path.join(tmp, "kaikki-en.dsl.dz.files.zip")
            with zipfile.ZipFile(zip_path) as zf:
                names = set(zf.namelist())
            self.assertEqual(names, {
                "En-us-pub.ogg",
                "En-au-herbed_up.ogg",
                "En-au-sello.ogg",
                "LL-Q1860_(eng)-Yangolin-bulk_carrier.wav.ogg",
            })
            # every bundled file is referenced under exactly its bundled name
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            for name in names:
                self.assertIn("[s]" + name + "[/s]", text)


class AudioResolutionTests(unittest.TestCase):
    """Missing audio is dropped, does not use a slot, and can be fetched."""

    def build(self, tmp, tar_names, *extra):
        tar_path = os.path.join(tmp, "audios.tar")
        make_tar(tar_path, tar_names)
        args = TOOL.build_parser().parse_args(
            [
                "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                "--out-dir", os.path.join(tmp, "out"), "--audio-tar", tar_path, "--no-audio-download",
                "--audio-per-word", "3", "--no-audio-download", *extra,
            ]
        )
        return TOOL.build(args)

    def test_unresolved_audio_is_not_linked(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.build(
                tmp,
                ["audios/En-au-limitword.ogg", "audios/En-uk-limitword.ogg"],
            )
            text = read_dz(os.path.join(tmp, "out", "kaikki-en.dsl.dz"))
            self.assertIn("[s]En-au-limitword.ogg[/s]", text)
            self.assertIn("[s]En-uk-limitword.ogg[/s]", text)
            # the two absent recordings are reported, never referenced
            self.assertNotIn("gone1", text)
            self.assertNotIn("gone2", text)
            self.assertNotIn("En-us-limitword.ogg", text)
            self.assertEqual(report.missing_audio, 3)
            self.assertEqual(report.audio_found, 2)

    def test_missing_audio_does_not_consume_a_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            # only these three of five exist; the limit of three must be filled
            report = self.build(
                tmp,
                [
                    "audios/En-au-limitword.ogg",
                    "audios/En-uk-limitword.ogg",
                    "audios/En-us-limitword.ogg",
                ],
            )
            text = read_dz(os.path.join(tmp, "out", "kaikki-en.dsl.dz"))
            refs = re.findall(r"\[s\](.*?)\[/s\]", text)
            self.assertEqual(len(refs), 3)
            self.assertEqual(
                set(refs),
                {"En-au-limitword.ogg", "En-uk-limitword.ogg", "En-us-limitword.ogg"},
            )
            self.assertEqual(report.audio_found, 3)
            self.assertEqual(report.missing_audio, 2)

    def test_missing_audio_is_downloaded_and_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []

            def stub_downloader(url, dest):
                calls.append((url, dest))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(b"FAKE-" + os.path.basename(dest).encode())

            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])
            args = TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                    "--out-dir", os.path.join(tmp, "out"), "--audio-tar", tar_path,
                    "--audio-per-word", "3",
                ]
            )
            args.audio_downloader = stub_downloader
            args.cache_dir = os.path.join(tmp, "cache")
            report = TOOL.build(args)

            # the two recordings the archive lacks came from their Wikimedia URLs
            self.assertEqual(len(calls), 2)
            self.assertTrue(all("upload.wikimedia.org" in u for u, _ in calls))
            import zipfile
            with zipfile.ZipFile(os.path.join(tmp, "out", "kaikki-en.dsl.dz.files.zip")) as zf:
                names = set(zf.namelist())
            # the limit of three is filled from the tape and the two downloads
            self.assertEqual(names, {
                "En-au-limitword.ogg",
                "En-uk-limitword.ogg",
                "En-us-limitword-gone1.ogg",
            })
            self.assertEqual(report.audio_found, 3)
            self.assertEqual(report.missing_audio, 0)
            # the fetched files were cached for the next run
            cache = os.path.join(tmp, "cache", "local", "audio-cache")
            self.assertTrue(os.path.isdir(cache))
            self.assertEqual(len(os.listdir(cache)), 2)

    def test_failed_download_omits_audio_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            def failing(url, dest):
                raise OSError("no network")

            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])
            args = TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                    "--out-dir", os.path.join(tmp, "out"), "--audio-tar", tar_path, "--no-audio-download",
                    "--audio-per-word", "3",
                ]
            )
            args.audio_downloader = failing
            report = TOOL.build(args)
            self.assertEqual(report.audio_found, 1)
            self.assertEqual(report.missing_audio, 4)
            text = read_dz(os.path.join(tmp, "out", "kaikki-en.dsl.dz"))
            self.assertEqual(re.findall(r"\[s\](.*?)\[/s\]", text), ["En-au-limitword.ogg"])


class LangProfileTests(unittest.TestCase):
    """Language-specific behaviour lives in the profile, not the renderer."""

    def test_english_profile_keeps_paradigm_and_drops_register(self):
        en = TOOL.get_lang_profile("en")
        self.assertTrue(en.form_qualifies(("past",)))
        self.assertTrue(en.form_qualifies(("present", "singular", "third-person")))
        self.assertFalse(en.form_qualifies(("archaic", "past")))
        self.assertFalse(en.form_qualifies(("nonstandard", "plural")))
        self.assertFalse(en.form_qualifies(("table-tags",)))

    def test_german_profile_keeps_case(self):
        de = TOOL.get_lang_profile("de")
        # a global English whitelist would have thrown case away
        self.assertTrue(de.form_qualifies(("dative", "singular")))
        self.assertTrue(de.form_qualifies(("genitive", "plural")))
        self.assertFalse(de.form_qualifies(("table-tags",)))

    def test_japanese_profile_accepts_its_own_tags(self):
        ja = TOOL.get_lang_profile("ja")
        self.assertTrue(ja.form_qualifies(("continuative",)))
        self.assertTrue(ja.form_qualifies(("imperfective", "stem")))
        self.assertFalse(ja.has_audio)

    def test_compact_labels_are_per_language(self):
        self.assertEqual(TOOL.get_lang_profile("en").label_tags(("past",)), "past")
        self.assertEqual(
            TOOL.get_lang_profile("de").label_tags(("dative", "singular")),
            "dat., sg.",
        )

    def test_unknown_language_and_renderer_is_profile_driven(self):
        profile = TOOL.get_lang_profile("xx")
        self.assertTrue(profile.form_qualifies(("anything",)))  # permissive
        # the renderer consults the profile object, not the language code
        record = {
            "word": "w", "pos": "noun",
            "forms": [{"form": "f", "tags": ["past"]}],
        }
        self.assertEqual(
            TOOL.collect_profile_forms(record, TOOL.get_lang_profile("en")),
            ["f (past)"],
        )
        self.assertEqual(
            TOOL.collect_profile_forms(record, TOOL.get_lang_profile("ja")),
            ["f (past)"],
        )


class PreviewRenderTests(unittest.TestCase):
    """The preview must nest exactly as the DSL does (balanced tags)."""

    def assert_balanced(self, html):
        for tag in ("div", "span"):
            opened = len(re.findall(rf"<{tag}\b", html))
            closed = len(re.findall(rf"</{tag}>", html))
            self.assertEqual(
                opened, closed,
                f"unbalanced <{tag}> in {html!r}: {opened} open, {closed} closed",
            )

    def test_every_emitted_tag_is_closed(self):
        text = (
            "\t[p]сущ.[/p]\n"
            "\t[m1]A gloss[/m1]\n"
            "\t\tбар  паб\n"
            "\t[*]\n"
            "\t[ex]An example.[/ex]\n"
            "\t[com]Forms: pubs (pl.)[/com]\n"
            "\t[/opt]"
        )
        self.assert_balanced(TOOL.dsl_to_html(text))

    def test_sibling_blocks_do_not_nest(self):
        html = TOOL.dsl_to_html("\t[com]one[/com]\n\t[com]two[/com]")
        self.assert_balanced(html)
        # two notes, neither inside the other
        self.assertEqual(html.count("<div"), 2)
        self.assertEqual(html.count("</div>"), 2)
        self.assertLess(html.index("</div>"), html.index(">two<"))

    def test_article_bodies_render_independently(self):
        head = TOOL.dsl_to_html("\t[p]сущ.[/p]")
        body = TOOL.dsl_to_html("\t[m1]gloss[/m1]")
        self.assertNotIn("<div", head)
        self.assertNotIn("<div", body)

    def test_audio_tag_does_not_swallow_following_text(self):
        html = TOOL.dsl_to_html("[s]x.ogg[/s] after")
        self.assertIn("x.ogg</span>", html)
        self.assertIn("after", html)

    def test_unbalanced_input_is_still_closed(self):
        html = TOOL.dsl_to_html("\t[*]\n\t[com]left open")
        self.assert_balanced(html)


class SenseGroupingTests(unittest.TestCase):
    """A shared parent gloss is rendered once, with sub-senses beneath it."""

    EN = None

    def setUp(self):
        self.EN = TOOL.get_lang_profile("en")

    def test_children_share_one_heading(self):
        senses = [
            {"glosses": ["A number of places in the US:", "One in Merced County."]},
            {"glosses": ["A number of places in the US:", "One in Bates County."]},
            {"glosses": ["A number of places in the US:", "One in Jefferson County."]},
        ]
        groups = TOOL._group_senses(senses, self.EN)
        self.assertEqual(len(groups), 1)
        heading, children = groups[0]
        self.assertEqual(heading, "A number of places in the US:")
        self.assertEqual(children, [
            "One in Merced County.", "One in Bates County.", "One in Jefferson County.",
        ])

    def test_single_fragment_sense_has_no_heading(self):
        groups = TOOL._group_senses([{"glosses": ["A penis."]}], self.EN)
        self.assertEqual(groups, [("", ["A penis."])])

    def test_non_adjacent_parents_are_separate_groups(self):
        senses = [
            {"glosses": ["Parent:", "First child."]},
            {"glosses": ["Other."]},
            {"glosses": ["Parent:", "Second child."]},
        ]
        groups = TOOL._group_senses(senses, self.EN)
        self.assertEqual(len(groups), 3)

    def test_context_tags_land_on_the_child_not_the_heading(self):
        # a lone tag-bearing sense keeps its own tag prefix
        groups = TOOL._group_senses(
            [{"glosses": ["The Dutch government."], "tags": ["metonymically"]}],
            self.EN,
        )
        self.assertEqual(groups[0][1][0], "(metonymically) The Dutch government.")

    def test_shared_parent_with_different_tags_merges(self):
        # monkey's figurative senses share a parent but each carries tags; the
        # parent must be printed once and the tags kept on the children
        senses = [
            {"glosses": ["A human considered to resemble monkeys, including:",
                         "A naughty person."], "tags": ["figuratively", "informal"]},
            {"glosses": ["A human considered to resemble monkeys, including:",
                         "Synonym of idiot."], "tags": ["derogatory", "figuratively"]},
            {"glosses": ["A human considered to resemble monkeys, including:",
                         "Synonym of puppet."], "tags": ["derogatory", "slang"]},
        ]
        groups = TOOL._group_senses(senses, self.EN)
        self.assertEqual(len(groups), 1)
        heading, children = groups[0]
        self.assertEqual(heading, "A human considered to resemble monkeys, including:")
        self.assertEqual(children, [
            "(figuratively, informal) A naughty person.",
            "(derogatory, figuratively) Synonym of idiot.",
            "(derogatory, slang) Synonym of puppet.",
        ])

    def test_rendered_article_shows_the_parent_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "senses.jsonl")
            records = [
                {"word": "place", "lang": "English", "lang_code": "en", "pos": "name",
                 "senses": [
                     {"glosses": ["A number of places in the US:", "One in Merced."]},
                     {"glosses": ["A number of places in the US:", "One in Bates."]},
                     {"glosses": ["A number of places in the US:", "One in Jefferson."]},
                 ]},
            ]
            with open(path, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "en", "--jsonl", path, "--out-dir", tmp, "--no-audio"]
            )
            TOOL.build(args)
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            self.assertEqual(text.count("A number of places in the US:"), 1)
            self.assertIn("One in Merced.", text)
            self.assertIn("One in Bates.", text)


class FormPolicyTests(unittest.TestCase):
    """Standard paradigms are kept; register/dialect variants are dropped."""

    def setUp(self):
        self.EN = TOOL.get_lang_profile("en")

    def test_ordinary_paradigm_is_kept(self):
        for tags in (["past"], ["plural"], ["present", "singular", "third-person"],
                     ["comparative"], ["participle", "past"]):
            self.assertTrue(self.EN.form_qualifies(tags), tags)

    def test_bookkeeping_tags_do_not_disqualify(self):
        # "canonical" and similar are not grammatical, so they must not drop a form
        self.assertTrue(self.EN.form_qualifies(["plural", "canonical"]))

    def test_register_and_dialect_variants_are_dropped(self):
        for tags in (["archaic", "past"], ["nonstandard", "plural"],
                     ["dialectal", "plural"], ["obsolete"], ["pronunciation-spelling"]):
            self.assertFalse(self.EN.form_qualifies(tags), tags)

    def test_table_machinery_is_dropped(self):
        self.assertFalse(self.EN.form_qualifies(["table-tags"]))
        self.assertFalse(self.EN.form_qualifies(["inflection-template"]))
        self.assertFalse(self.EN.form_qualifies([]))

    def test_labels_are_compact_and_drop_bookkeeping(self):
        self.assertEqual(self.EN.label_tags(("past",)), "past")
        self.assertEqual(self.EN.label_tags(("plural", "canonical")), "pl.")
        self.assertEqual(
            self.EN.label_tags(("present", "singular", "third-person")),
            "pres., 3rd sg.",
        )


class SpoilerTests(unittest.TestCase):
    """Examples, forms, refs and pronunciation live in the optional zone."""

    def test_extras_are_hidden_and_senses_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._build(tmp)
            self.assertIn("[*]", text)
            self.assertIn("[/opt]", text)
            # the sense text is outside the optional zone
            self.assertLess(text.index("To move swiftly on foot."), text.index("[*]"))
            for extra in ("Forms:", "See also:", "[ex]", "IPA:"):
                self.assertGreater(text.index(extra), text.index("[*]"), extra)

    def _build(self, tmp):
        args = TOOL.build_parser().parse_args(
            [
                "--source-lang", "en", "--jsonl", FIXTURE, "--out-dir", tmp,
                "--no-audio",
            ]
        )
        TOOL.build(args)
        return read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))


class SampleSelectionTests(unittest.TestCase):
    """--sample reads a bounded part of the snapshot and still yields N words."""

    def test_first_mode_takes_the_first_distinct_words(self):
        records = TOOL.sample_headwords(FIXTURE, "en", 3, "first")
        words = []
        for r in records:
            w = str(r["word"])
            if w not in words:
                words.append(w)
        self.assertEqual(words, ["run", "runner", "escape"])

    def test_random_mode_fills_the_request(self):
        records = TOOL.sample_headwords(FIXTURE, "en", 3, "random")
        words = []
        for r in records:
            w = str(r["word"])
            if w not in words:
                words.append(w)
        self.assertEqual(len(words), 3)
        self.assertEqual(len(set(words)), 3)

    def test_small_file_is_not_over_strided(self):
        # a fixture with fewer candidates than the random window must still
        # yield every distinct word it has
        all_words = set(TOOL.iter_candidate_headwords(FIXTURE, "en"))
        records = TOOL.sample_headwords(FIXTURE, "en", 99, "random")
        got = {str(r["word"]) for r in records}
        self.assertEqual(got, all_words)

    def test_random_selection_is_deterministic(self):
        a = [str(r["word"]) for r in TOOL.sample_headwords(FIXTURE, "en", 3, "random")]
        b = [str(r["word"]) for r in TOOL.sample_headwords(FIXTURE, "en", 3, "random")]
        self.assertEqual(a, b)

    def test_multi_record_words_are_sampled_once(self):
        records = TOOL.sample_headwords(FIXTURE, "en", 3, "first")
        run_records = [r for r in records if str(r["word"]) == "run"]
        # run has a verb and a noun record; both come with the one headword
        self.assertEqual(len(run_records), 2)


class AudioIndexCacheTests(unittest.TestCase):
    """The audio-archive name index is cached and never served stale."""

    def _archive(self, tmp, names):
        path = os.path.join(tmp, "audios.tar")
        make_tar(path, names)
        return path

    def test_index_is_built_then_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._archive(tmp, ["audios/A.ogg", "audios/B.ogg"])
            first = TOOL.available_audio_keys(path, cache_dir=tmp)
            self.assertEqual(first, {"a.ogg", "b.ogg"})
            self.assertTrue(os.path.isfile(path + ".keys.txt"))
            # second read must come from the cache and agree
            second = TOOL.available_audio_keys(path, cache_dir=tmp)
            self.assertEqual(second, first)

    def test_changed_archive_invalidates_the_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._archive(tmp, ["audios/A.ogg"])
            self.assertEqual(TOOL.available_audio_keys(path, cache_dir=tmp), {"a.ogg"})
            # replace the archive with different content
            time.sleep(1.1)  # ensure a distinct mtime even on coarse clocks
            make_tar(path, ["audios/A.ogg", "audios/C.ogg"])
            fresh = TOOL.available_audio_keys(path, cache_dir=tmp)
            self.assertEqual(fresh, {"a.ogg", "c.ogg"})

    def test_different_archives_do_not_share_a_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            d1 = os.path.join(tmp, "one")
            d2 = os.path.join(tmp, "two")
            os.makedirs(d1)
            os.makedirs(d2)
            one = self._archive(d1, ["audios/A.ogg"])
            two = self._archive(d2, ["audios/B.ogg"])
            self.assertEqual(TOOL.available_audio_keys(one, cache_dir=tmp), {"a.ogg"})
            self.assertEqual(TOOL.available_audio_keys(two, cache_dir=tmp), {"b.ogg"})

    def test_force_rebuilds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._archive(tmp, ["audios/A.ogg"])
            TOOL.available_audio_keys(path, cache_dir=tmp)
            cache = path + ".keys.txt"
            with open(cache, "w", encoding="utf-8") as f:
                f.write("bogus\n")
            # a corrupt cache header is ignored and the index rebuilt
            self.assertEqual(TOOL.available_audio_keys(path, cache_dir=tmp), {"a.ogg"})
            self.assertEqual(TOOL.available_audio_keys(path, cache_dir=tmp, force=True), {"a.ogg"})


class DownloadPolicyTests(unittest.TestCase):
    """Requests identify the tool and back off politely on rate limits."""

    def test_user_agent_identifies_the_tool_and_a_contact(self):
        self.assertIn("Aurelex", TOOL.USER_AGENT)
        self.assertIn("http", TOOL.USER_AGENT)

    def test_rate_limit_is_retried_then_succeeds(self):
        calls = []

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self, n=-1):
                return b""

        def fake_urlopen(request, timeout):
            calls.append(request.get_header("User-agent"))
            if len(calls) < 3:
                raise urllib.error.HTTPError(
                    request.full_url, 429, "Too many requests", {}, None
                )
            return FakeResponse()

        original = TOOL.urllib.request.urlopen
        original_sleep = TOOL.time.sleep
        TOOL.urllib.request.urlopen = fake_urlopen
        TOOL.time.sleep = lambda _s: None
        try:
            with TOOL._open_with_retries("https://example.invalid/x", 5):
                pass
        finally:
            TOOL.urllib.request.urlopen = original
            TOOL.time.sleep = original_sleep
        self.assertEqual(len(calls), 3)
        self.assertIn("Aurelex", calls[0])

    def test_non_retryable_error_is_raised_immediately(self):
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

        original = TOOL.urllib.request.urlopen
        original_sleep = TOOL.time.sleep
        TOOL.urllib.request.urlopen = fake_urlopen
        TOOL.time.sleep = lambda _s: None
        try:
            with self.assertRaises(urllib.error.HTTPError):
                TOOL._open_with_retries("https://example.invalid/x", 5)
        finally:
            TOOL.urllib.request.urlopen = original
            TOOL.time.sleep = original_sleep


class ProgressTests(unittest.TestCase):

    def test_progress_reports_periodically(self):
        stream = io.StringIO()
        original = sys.stderr
        sys.stderr = stream
        try:
            progress = TOOL.Progress("work", every=2)
            for _ in range(5):
                progress.tick()
            progress.done()
        finally:
            sys.stderr = original
        out = stream.getvalue()
        self.assertIn("work: 2", out)
        self.assertIn("work: 4", out)
        self.assertTrue(out.endswith("\n"))

    def test_progress_reports_a_total(self):
        stream = io.StringIO()
        original = sys.stderr
        sys.stderr = stream
        try:
            progress = TOOL.Progress("work", every=1, total=3)
            for _ in range(3):
                progress.tick()
            progress.done()
        finally:
            sys.stderr = original
        out = stream.getvalue()
        self.assertIn("work: 3/3", out)


if __name__ == "__main__":
    unittest.main()
