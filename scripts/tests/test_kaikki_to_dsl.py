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


def sense_texts(entries):
    """Just the glosses of a ``_group_senses`` entry list.

    Each entry is a ``(gloss, examples)`` pair; grouping tests that only care
    about the glosses compare through this so they do not have to spell out the
    example list every time.
    """
    return [text for text, _examples in entries]


def sense_examples(entries):
    """The raw example strings carried by a ``_group_senses`` entry list."""
    return [examples for _text, examples in entries]


def zip_names(path):
    """The entry names of a resource archive."""
    import zipfile

    with zipfile.ZipFile(path) as zf:
        return set(zf.namelist())


def only_audio(names):
    """Drop the sense-marker icons from a set of bundled resource names."""
    return {n for n in names if not n.startswith("gd_tag_")}


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
            self.assertIn("[i]runs (3rd sg.)", text)
            self.assertNotIn("Forms:", text)
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

            zip1 = os.path.join(out1, "kaikki-en.dsl.files.zip")
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
            zip2 = os.path.join(out2, "kaikki-en.dsl.files.zip")
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
            self.assertTrue(os.path.isdir(os.path.join(tmp, "kaikki-en.dsl.files")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, "kaikki-en.dsl.files", "En-us-run.ogg")))
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
            self.assertIn("/pʌb/", text)

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
            zip_path = os.path.join(tmp, "kaikki-en.dsl.files.zip")
            with zipfile.ZipFile(zip_path) as zf:
                names = set(zf.namelist())
            # the archive also carries the sense-marker icons
            self.assertTrue(set(TOOL._ICON_FILES) <= names)
            self.assertEqual(only_audio(names), {
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
            refs = [
                r for r in re.findall(r"\[s\](.*?)\[/s\]", text)
                if not r.startswith("gd_tag_")
            ]
            # the three planned files are referenced exactly once each, beside
            # the part of speech they belong to
            self.assertEqual(refs, [
                "En-au-limitword.ogg",
                "En-uk-limitword.ogg",
                "En-us-limitword.ogg",
            ])
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
            with zipfile.ZipFile(os.path.join(tmp, "out", "kaikki-en.dsl.files.zip")) as zf:
                names = set(zf.namelist())
            # the limit of three is filled from the tape and the two downloads
            self.assertEqual(only_audio(names), {
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
            audio_refs = [
                r for r in re.findall(r"\[s\](.*?)\[/s\]", text)
                if not r.startswith("gd_tag_")
            ]
            self.assertEqual(audio_refs, ["En-au-limitword.ogg"])


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
            "\t[/*]"
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

    def test_sense_icon_renders_as_an_inline_image(self):
        html = TOOL.dsl_to_html("[s]gd_tag_countable.svg[/s] a thing")
        # an <img> with the SVG inlined as a data URI, not the audio glyph
        self.assertIn('<img class="senseicon"', html)
        self.assertIn("data:image/svg+xml;base64,", html)
        self.assertNotIn("&#9835;", html)
        self.assertIn("a thing", html)
        self.assert_balanced(html)

    def test_unbalanced_input_is_still_closed(self):
        html = TOOL.dsl_to_html("\t[*]\n\t[com]left open")
        self.assert_balanced(html)


class SenseIconBundleTests(unittest.TestCase):
    """The icon set is vendored, bundled with every dictionary, and advertised."""

    def test_icon_files_exist_in_the_repository(self):
        for name in TOOL._ICON_FILES:
            self.assertTrue(
                os.path.isfile(os.path.join(TOOL._ICON_ASSET_DIR, name)), name
            )

    def test_bundle_holds_the_icons_with_audio_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "en", "--jsonl", FIXTURE, "--out-dir", tmp,
                 "--no-audio"]
            )
            TOOL.build(args)
            names = zip_names(os.path.join(tmp, "kaikki-en.dsl.files.zip"))
            self.assertTrue(set(TOOL._ICON_FILES) <= names)

    def test_resource_bundle_uses_the_canonical_name(self):
        # the reader looks for "<base>.dsl.files.zip" before
        # "<base>.dsl.dz.files.zip" (dsl.cc:1743, baseName drops ".dsl.dz"), so
        # the canonical name is the one to emit for both layouts
        with tempfile.TemporaryDirectory() as tmp:
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "en", "--jsonl", FIXTURE, "--out-dir", tmp,
                 "--no-audio"]
            )
            TOOL.build(args)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "kaikki-en.dsl.files.zip")))
            self.assertFalse(
                os.path.exists(os.path.join(tmp, "kaikki-en.dsl.dz.files.zip"))
            )

        with tempfile.TemporaryDirectory() as tmp:
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "en", "--jsonl", FIXTURE, "--out-dir", tmp,
                 "--no-audio", "--audio-layout", "dir"]
            )
            TOOL.build(args)
            self.assertTrue(os.path.isdir(os.path.join(tmp, "kaikki-en.dsl.files")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "kaikki-en.dsl.dz.files")))

    def test_bundle_dir_layout_holds_the_icons(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "en", "--jsonl", FIXTURE, "--out-dir", tmp,
                 "--no-audio", "--audio-layout", "dir"]
            )
            TOOL.build(args)
            dest = os.path.join(tmp, "kaikki-en.dsl.files")
            for name in TOOL._ICON_FILES:
                self.assertTrue(os.path.isfile(os.path.join(dest, name)), name)

    def test_about_card_lists_each_icon_and_its_meaning(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "en", "--jsonl", FIXTURE, "--out-dir", tmp,
                 "--no-audio"]
            )
            TOOL.build(args)
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            for name, meaning in TOOL._ICON_LEGEND:
                self.assertIn(f"[s]{name}[/s] {meaning}", text)


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
        self.assertEqual(sense_texts(children), [
            "One in Merced County.", "One in Bates County.", "One in Jefferson County.",
        ])

    def test_single_fragment_sense_has_no_heading(self):
        groups = TOOL._group_senses([{"glosses": ["A penis."]}], self.EN)
        self.assertEqual(groups, [("", [("A penis.", [])])])

    def test_each_entry_carries_its_own_examples(self):
        # an example belongs to the sense that illustrates it, so it travels
        # with that sense's entry rather than pooling at the card
        senses = [
            {"glosses": ["Parent:", "First child."],
             "examples": [{"text": "The first child ran."}]},
            {"glosses": ["Parent:", "Second child."],
             "examples": [{"text": "The second child walked."}]},
        ]
        groups = TOOL._group_senses(senses, self.EN)
        self.assertEqual(sense_examples(groups[0][1]), [
            ["The first child ran."], ["The second child walked."],
        ])

    def test_non_adjacent_parents_merge_into_one_group(self):
        # the same parent seen again, even after an unrelated sense, joins its
        # group rather than starting a second copy of the heading
        senses = [
            {"glosses": ["Parent:", "First child."]},
            {"glosses": ["Other."]},
            {"glosses": ["Parent:", "Second child."]},
        ]
        groups = TOOL._group_senses(senses, self.EN)
        self.assertEqual([g[0] for g in groups], ["Parent:", ""])
        self.assertEqual(sense_texts(groups[0][1]), ["First child.", "Second child."])
        self.assertEqual(sense_texts(groups[1][1]), ["Other."])

    def test_repeated_glosses_are_deduped(self):
        # a verbatim repeat of a heading and of a child is printed once
        senses = [
            {"glosses": ["A task:", "Physical work."]},
            {"glosses": ["A task:", "Physical work."]},
            {"glosses": ["A task:", "Mental work."]},
        ]
        groups = TOOL._group_senses(senses, self.EN)
        self.assertEqual(len(groups), 1)
        self.assertEqual(sense_texts(groups[0][1]), ["Physical work.", "Mental work."])

    def test_context_tags_land_on_the_child_not_the_heading(self):
        # a lone tag-bearing sense keeps its own tag prefix (abbreviated)
        groups = TOOL._group_senses(
            [{"glosses": ["The Dutch government."], "tags": ["metonymically"]}],
            self.EN,
        )
        self.assertEqual(groups[0][1][0][0], "(meton.) The Dutch government.")

    def test_noise_and_structural_tags_are_dropped(self):
        # a verb is transitive unless said otherwise, and a structural tag
        # repeats what the gloss already says
        for tags in (["transitive"], ["intransitive"], ["not-comparable"],
                     ["synonym"], ["synonyms"], ["ellipsis"], ["clipping"]):
            self.assertEqual(
                TOOL._sense_markers(tags, self.EN), "", tags,
            )
        # a meaningful register tag survives, abbreviated
        self.assertEqual(TOOL._sense_markers(["figuratively"], self.EN), "(fig.) ")

    def test_iconised_tags_render_as_icons_not_text(self):
        cases = {
            "countable": "gd_tag_countable.svg",
            "uncountable": "gd_tag_uncountable.svg",
            "initialism": "gd_tag_initialism.svg",
            "abbreviation": "gd_tag_initialism.svg",
            "acronym": "gd_tag_initialism.svg",
            "obsolete": "gd_tag_obsolete.svg",
            "dated": "gd_tag_obsolete.svg",
            "archaic": "gd_tag_obsolete.svg",
        }
        for tag, icon in cases.items():
            markers = TOOL._sense_markers([tag], self.EN)
            self.assertEqual(markers, f"[s]{icon}[/s] ", tag)
            self.assertNotIn(f"({tag})", markers)

    def test_alternative_form_tags_render_no_marker(self):
        # the gloss already says "Alternative spelling of ...", and the headword
        # it names is linked instead of marked
        for tags in (["alt-of"], ["alternative"], ["form-of"],
                     ["alt-of", "alternative"]):
            self.assertEqual(TOOL._sense_markers(tags, self.EN), "", tags)

    def test_countability_icon_only_when_the_sole_case(self):
        # Wiktionary marks most nouns both countable and uncountable; that is the
        # unmarked "can be either" case, so neither icon is shown
        both = TOOL._sense_markers(["countable", "uncountable"], self.EN)
        self.assertEqual(both, "")
        self.assertEqual(
            TOOL._sense_markers(["countable"], self.EN),
            "[s]gd_tag_countable.svg[/s] ",
        )
        self.assertEqual(
            TOOL._sense_markers(["uncountable"], self.EN),
            "[s]gd_tag_uncountable.svg[/s] ",
        )

    def test_an_icon_and_a_register_tag_coexist(self):
        markers = TOOL._sense_markers(["obsolete", "figuratively"], self.EN)
        self.assertEqual(markers, "[s]gd_tag_obsolete.svg[/s] (fig.) ")

    def test_the_same_icon_is_not_repeated(self):
        markers = TOOL._sense_markers(["initialism", "abbreviation"], self.EN)
        self.assertEqual(markers, "[s]gd_tag_initialism.svg[/s] ")

    def test_form_of_target_is_linked_when_known(self):
        groups = TOOL._group_senses(
            [{"glosses": ["Alternative spelling of swap."],
              "tags": ["alt-of", "alternative"],
              "alt_of": [{"word": "swap"}]}],
            self.EN, {"swap"}, "swop",
        )
        self.assertEqual(
            groups[0][1][0][0], "Alternative spelling of [ref]swap[/ref]."
        )

    def test_form_of_target_is_plain_when_absent(self):
        groups = TOOL._group_senses(
            [{"glosses": ["Alternative spelling of swap."],
              "tags": ["alt-of"],
              "alt_of": [{"word": "swap"}]}],
            self.EN, {"other"}, "swop",
        )
        self.assertEqual(groups[0][1][0][0], "Alternative spelling of swap.")

    def test_form_of_target_is_not_linked_to_itself(self):
        groups = TOOL._group_senses(
            [{"glosses": ["Alternative spelling of swap."],
              "form_of": [{"word": "swap"}]}],
            self.EN, {"swap"}, "swap",
        )
        self.assertEqual(groups[0][1][0][0], "Alternative spelling of swap.")

    def test_shared_parent_with_different_tags_merges(self):
        # monkey's figurative senses share a parent but each carries tags; the
        # parent must be printed once and one tag kept on each child
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
        # only the first tag of each set is shown, abbreviated; structural tags skipped
        self.assertEqual(sense_texts(children), [
            "(fig.) A naughty person.",
            "(derog.) Synonym of idiot.",
            "(derog.) Synonym of puppet.",
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


class CardLayoutTests(unittest.TestCase):
    """A card merges same-POS records, dedupes audio and bounds examples."""

    EN = None

    def setUp(self):
        self.EN = TOOL.get_lang_profile("en")

    class _Audio:
        def plan(self, record):
            return [s["audio"] for s in (record.get("sounds") or []) if "audio" in s]

    def test_same_pos_records_merge_into_one_block(self):
        records = [
            {"word": "swop", "pos": "noun",
             "senses": [{"glosses": ["First noun sense."]}],
             "forms": [{"form": "swops", "tags": ["plural"]}]},
            {"word": "swop", "pos": "verb",
             "senses": [{"glosses": ["Verb sense."]}],
             "forms": [{"form": "swopped", "tags": ["past"]}]},
            {"word": "swop", "pos": "noun",
             "senses": [{"glosses": ["Second noun sense."]}]},
        ]
        text = TOOL.render_card(records, self._Audio(), self.EN, set())
        self.assertEqual(text.count("[p]noun[/p]"), 1)
        self.assertEqual(text.count("[p]verb[/p]"), 1)
        # the interleaved noun's senses sit under the single noun heading
        noun = text.index("[p]noun[/p]")
        verb = text.index("[p]verb[/p]")
        self.assertLess(noun, text.index("First noun sense."))
        self.assertLess(text.index("First noun sense."), verb)
        self.assertLess(text.index("Second noun sense."), verb)
        self.assertIn("swops (pl.)", text)

    def test_shared_audio_is_printed_once_card_wide(self):
        records = [
            {"word": "ermine", "pos": "noun", "senses": [{"glosses": ["A mustelid."]}],
             "sounds": [{"ipa": "/e/", "audio": "En-ermine.ogg"}]},
            {"word": "ermine", "pos": "verb", "senses": [{"glosses": ["To clothe."]}],
             "sounds": [{"ipa": "/e/", "audio": "En-ermine.ogg"}]},
        ]
        text = TOOL.render_card(records, self._Audio(), self.EN, set())
        self.assertEqual(text.count("[s]En-ermine.ogg[/s]"), 1)
        # the single shared transcription is hoisted above the first POS, with
        # the audio on the same line as the transcription
        self.assertIn("[com]/e/  [s]En-ermine.ogg[/s][/com]", text)
        self.assertLess(text.index("/e/"), text.index("[p]noun[/p]"))

    def test_differing_pronunciations_stay_under_their_pos(self):
        records = [
            {"word": "x", "pos": "noun", "senses": [{"glosses": ["n."]}],
             "sounds": [{"ipa": "/a/", "audio": "En-x.ogg"}]},
            {"word": "x", "pos": "verb", "senses": [{"glosses": ["v."]}],
             "sounds": [{"ipa": "/b/", "audio": "En-x.ogg"}]},
        ]
        text = TOOL.render_card(records, self._Audio(), self.EN, set())
        noun = text.index("[p]noun[/p]")
        verb = text.index("[p]verb[/p]")
        self.assertLess(noun, text.index("/a/"))
        self.assertLess(text.index("/a/"), verb)
        self.assertLess(verb, text.index("/b/"))
        # the one audio file is still shown only once, on the first pronunciation
        # line that references it, beside that transcription
        self.assertEqual(text.count("[s]En-x.ogg[/s]"), 1)
        self.assertIn("[com]/a/  [s]En-x.ogg[/s][/com]", text)

    def test_a_new_pos_is_separated_by_a_blank_line(self):
        records = [
            {"word": "w", "pos": "noun", "senses": [{"glosses": ["n."]}]},
            {"word": "w", "pos": "verb", "senses": [{"glosses": ["v."]}]},
        ]
        text = TOOL.render_card(records, self._Audio(), self.EN, set())
        self.assertIn("\n\n\t[p]verb[/p]", text)
        # exactly one blank line, and only between the two sections
        self.assertEqual(
            sum(1 for ln in text.split("\n") if ln.strip() == ""), 1
        )
        # the first section is not preceded by a blank line
        self.assertFalse(text.startswith("\n"))
        self.assertTrue(text.startswith("\t[p]noun[/p]"))

    def test_a_hoisted_transcription_is_not_followed_by_a_blank_line(self):
        # a hoisted transcription sits above the first POS; the separator goes
        # strictly between parts of speech, so no blank follows the transcription
        records = [
            {"word": "w", "pos": "noun", "senses": [{"glosses": ["n."]}],
             "sounds": [{"ipa": "/w/"}]},
            {"word": "w", "pos": "verb", "senses": [{"glosses": ["v."]}],
             "sounds": [{"ipa": "/w/"}]},
        ]
        text = TOOL.render_card(records, self._Audio(), self.EN, set())
        self.assertIn("[com]/w/[/com]\n\t[p]noun[/p]", text)
        self.assertNotIn("[com]/w/[/com]\n\n", text)
        self.assertEqual(
            sum(1 for ln in text.split("\n") if ln.strip() == ""), 1
        )

    def test_audio_without_a_transcription_still_gets_a_line(self):
        record = {
            "word": "w", "pos": "noun", "senses": [{"glosses": ["A thing."]}],
            "sounds": [{"audio": "En-w.ogg"}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertIn("\t[com][s]En-w.ogg[/s][/com]", text)

    def test_long_example_is_truncated_at_a_word_boundary(self):
        shortened = TOOL._truncate_example("word " * 80, limit=50)
        self.assertTrue(shortened.endswith(" …"))
        # cut on a space, so no partial word is left behind
        self.assertEqual(shortened[:-2], shortened[:-2].rstrip())
        self.assertTrue(shortened[:-2].endswith("word"))
        self.assertLess(len(shortened), 80 * len("word "))

    def test_short_example_is_untouched(self):
        self.assertEqual(TOOL._truncate_example("I run every morning."), "I run every morning.")

    def test_example_must_contain_the_headword(self):
        # an example that never uses the word is dropped
        self.assertTrue(TOOL._example_shows_word("I run every morning.", "run"))
        self.assertTrue(TOOL._example_shows_word("He runs fast.", "run"))   # regular inflection
        self.assertTrue(TOOL._example_shows_word("They ran home.", "run", ["ran (past)"]))
        self.assertFalse(TOOL._example_shows_word("An unrelated clause.", "run"))
        self.assertFalse(TOOL._example_shows_word("They ran home.", "run"))  # no forms given

    def test_examples_without_the_word_are_left_out(self):
        record = {
            "word": "run", "pos": "verb",
            "senses": [{"glosses": ["To move swiftly."], "examples": [
                {"text": "I run every morning."},
                {"text": "A wholly unrelated sentence."},
            ]}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertEqual(text.count("[ex]"), 1)
        self.assertIn("[ex]I run every morning.[/ex]", text)
        self.assertNotIn("unrelated", text)

    def test_sense_tag_policy_is_profile_driven(self):
        text = TOOL.render_card(
            [{"word": "w", "pos": "noun", "senses": [
                {"glosses": ["A thing."], "tags": ["countable"]},
                {"glosses": ["A notion."], "tags": ["figuratively"]},
            ]}],
            self._Audio(), self.EN, set(),
        )
        self.assertNotIn("(countable)", text)
        self.assertIn("(fig.) A notion.", text)

    def test_sub_senses_are_indented_definitions_not_comments(self):
        text = TOOL.render_card(
            [{"word": "w", "pos": "noun", "senses": [
                {"glosses": ["Employment.", "Labour."]},
                {"glosses": ["Employment.", "The place one works."]},
            ]}],
            self._Audio(), self.EN, set(),
        )
        self.assertIn("[m1]1. Employment.[/m]", text)
        self.assertIn("[m2]\u2022 Labour.[/m]", text)
        self.assertIn("[m2]\u2022 The place one works.[/m]", text)
        self.assertNotIn("[com]Labour.", text)
        # the parent heading is a category, not a sense: it carries no bullet
        self.assertNotIn("\u2022 Employment.", text)

    def test_group_headings_are_numbered_per_pos(self):
        records = [
            {"word": "w", "pos": "noun", "senses": [
                {"glosses": ["First.", "a."]},
                {"glosses": ["Second.", "b."]},
            ]},
            {"word": "w", "pos": "verb", "senses": [
                {"glosses": ["Third.", "c."]},
            ]},
        ]
        text = TOOL.render_card(records, self._Audio(), self.EN, set())
        self.assertIn("[m1]1. First.[/m]", text)
        self.assertIn("[m1]2. Second.[/m]", text)
        # the counter restarts for the next part of speech
        self.assertIn("[m1]1. Third.[/m]", text)
        self.assertNotIn("2. Third.", text)

    def test_a_heading_without_children_is_not_numbered(self):
        # a single-fragment sense is an ordinary sense, not an outline entry
        record = {
            "word": "w", "pos": "noun",
            "senses": [{"glosses": ["A thing."]}, {"glosses": ["Another."]}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertIn("[m1]\u2022 A thing.[/m]", text)
        self.assertNotIn("1. A thing.", text)

    def test_leaf_senses_are_bulleted(self):
        record = {
            "word": "w", "pos": "noun",
            "senses": [{"glosses": ["A thing."]}, {"glosses": ["Another."]}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertIn("[m1]\u2022 A thing.[/m]", text)
        self.assertIn("[m1]\u2022 Another.[/m]", text)

    def test_a_tagged_sense_renders_its_icon_after_the_bullet(self):
        record = {
            "word": "w", "pos": "noun",
            "senses": [{"glosses": ["A thing."], "tags": ["uncountable"]}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertIn("[m1]\u2022 [s]gd_tag_uncountable.svg[/s] A thing.[/m]", text)

    def test_a_word_tagged_both_ways_shows_no_countability_icon(self):
        # the common Wiktionary "can be either" case is the unmarked one
        record = {
            "word": "w", "pos": "noun",
            "senses": [{"glosses": ["A thing."], "tags": ["countable", "uncountable"]}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertNotIn("gd_tag_countable.svg", text)
        self.assertNotIn("gd_tag_uncountable.svg", text)

    def test_an_alternative_form_links_its_base_headword(self):
        record = {
            "word": "swop", "pos": "noun",
            "senses": [{"glosses": ["Alternative spelling of swap."],
                        "tags": ["alt-of", "alternative"],
                        "alt_of": [{"word": "swap"}]}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, {"swap"})
        self.assertIn("\u2022 Alternative spelling of [ref]swap[/ref].", text)

    def test_an_alternative_form_absent_from_the_dictionary_is_plain(self):
        record = {
            "word": "swop", "pos": "noun",
            "senses": [{"glosses": ["Alternative spelling of swap."],
                        "alt_of": [{"word": "swap"}]}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, {"unrelated"})
        self.assertIn("\u2022 Alternative spelling of swap.", text)
        self.assertNotIn("[ref]swap[/ref]", text)

    def test_initialism_prefix_is_dropped_leaving_the_linked_headword(self):
        record = {
            "word": "ROs", "pos": "noun",
            "senses": [{"glosses": ["Initialism of reverse osmosis."],
                        "tags": ["initialism", "alt-of"],
                        "alt_of": [{"word": "reverse osmosis"}]}],
        }
        text = TOOL.render_card(
            [record], self._Audio(), self.EN, {"reverse osmosis"}
        )
        self.assertIn(
            "[s]gd_tag_initialism.svg[/s] [ref]reverse osmosis[/ref].", text
        )
        self.assertNotIn("Initialism of", text)

    def test_relation_words_are_kept_for_a_tag_without_an_icon(self):
        # a clipping has no icon, so its words stay as the gloss
        groups = TOOL._group_senses(
            [{"glosses": ["Clipping of refrigerator."], "tags": ["clipping"]}],
            self.EN,
        )
        self.assertEqual(groups[0][1][0][0], "Clipping of refrigerator.")

    def test_transcription_is_not_labelled(self):
        record = {
            "word": "w", "pos": "noun", "senses": [{"glosses": ["A thing."]}],
            "sounds": [{"ipa": "/w/"}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertIn("[com]/w/[/com]", text)
        self.assertNotIn("IPA:", text)

    def test_a_single_record_hoists_its_transcription(self):
        # one record is trivially one transcription, so it goes above the part of
        # speech like a multi-record card, not under it
        record = {
            "word": "w", "pos": "noun", "senses": [{"glosses": ["A thing."]}],
            "sounds": [{"ipa": "/w/"}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertLess(text.index("[com]/w/[/com]"), text.index("[p]noun[/p]"))

    def test_a_second_notation_keeps_its_label(self):
        # enPR is not IPA; it keeps its name so the two are distinguishable
        record = {
            "word": "w", "pos": "noun", "senses": [{"glosses": ["A thing."]}],
            "sounds": [{"enpr": "wit"}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertIn("[com]enPR: wit[/com]", text)

    def test_repeated_examples_are_capped_per_sense(self):
        senses = [
            {"glosses": ["A task."], "examples": [{"text": f"work item {i}"} for i in range(10)]},
        ]
        record = {"word": "work", "pos": "noun", "senses": senses}
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertEqual(text.count("[ex]"), TOOL._EXAMPLE_MAX_PER_SENSE)

    def test_each_sense_gets_its_own_optional_zone(self):
        # an example illustrates one use, so it sits under that sense rather
        # than pooling in a single card-level zone
        record = {
            "word": "work", "pos": "verb",
            "senses": [
                {"glosses": ["To toil."], "examples": [{"text": "I work hard."}]},
                {"glosses": ["To function."], "examples": [{"text": "It does not work."}]},
            ],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        # one zone per sense with an example, each opened right after its gloss
        self.assertEqual(text.count("[*]"), 2)
        self.assertEqual(text.count("[/*]"), 2)
        self.assertIn(
            "\t[m1]\u2022 To toil.[/m]\n\t[*]\n\t[ex]I work hard.[/ex]\n\t[/*]",
            text,
        )
        self.assertIn(
            "\t[m1]\u2022 To function.[/m]\n\t[*]\n\t[ex]It does not work.[/ex]\n\t[/*]",
            text,
        )

    def test_a_sense_without_examples_gets_no_zone(self):
        # no empty [*]…[/*] is emitted for a gloss that has nothing to hide
        record = {
            "word": "work", "pos": "verb",
            "senses": [{"glosses": ["To toil."]}],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertNotIn("[*]", text)

    def test_archaic_and_citation_examples_are_dropped(self):
        self.assertFalse(TOOL._example_is_usable("I haue worke in hand."))
        self.assertFalse(TOOL._example_is_usable("Come on Neriſſa, I haue worke."))
        self.assertFalse(TOOL._example_is_usable("Citations:work."))
        self.assertFalse(TOOL._example_is_usable(
            "For quotations using this term, see Citations:work."))
        self.assertFalse(TOOL._example_is_usable(
            "‘I wolde hit were so,’ seyde the Kynge, ‘but I may nat stonde"
            ", my hede worchys so—’"))
        self.assertTrue(TOOL._example_is_usable("My work involves travel."))
        self.assertTrue(TOOL._example_is_usable(
            "Whether we work or rest, the deadline holds."))

    def test_see_also_is_one_line_per_card(self):
        records = [
            {"word": "run", "pos": "verb",
             "senses": [{"glosses": ["To move."]}],
             "synonyms": [{"word": "sprint"}, {"word": "trot"}]},
            {"word": "run", "pos": "noun",
             "senses": [{"glosses": ["A flow."]}],
             "synonyms": [{"word": "flow"}]},
        ]
        text = TOOL.render_card(records, self._Audio(), self.EN, {"sprint", "trot", "flow"})
        self.assertEqual(text.count("See also:"), 1)
        self.assertIn("[ref]sprint[/ref]", text)
        self.assertIn("[ref]flow[/ref]", text)

    def test_a_later_sense_is_not_inside_an_earlier_zone(self):
        # the engine nests by tag name; [/*] must actually close [*], or every
        # following sense ends up inside the hidden span and collapses with it
        record = {
            "word": "swop", "pos": "noun",
            "senses": [
                {"glosses": ["Alternative spelling of swap."],
                 "examples": [{"text": "A straight swop."}]},
                {"glosses": ["A fusion of dance styles."]},
            ],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        lines = [ln.strip() for ln in text.split("\n")]
        depth = 0
        for ln in lines:
            if ln == "[*]":
                depth += 1
            elif ln == "[/*]":
                depth -= 1
                self.assertGreaterEqual(depth, 0)
            elif ln.startswith("[m1]"):
                self.assertEqual(depth, 0, f"sense inside an optional zone: {ln}")
        self.assertEqual(depth, 0)

    def test_every_optional_zone_is_closed_with_a_known_tag(self):
        # engine-supported closers are the tag set in dsl.cc's strip regex;
        # [/opt] is not one and the parser silently ignores it
        record = {
            "word": "work", "pos": "verb",
            "senses": [
                {"glosses": ["To toil."], "examples": [{"text": "I work hard."}]},
                {"glosses": ["To function."], "examples": [{"text": "It works."}]},
            ],
        }
        text = TOOL.render_card([record], self._Audio(), self.EN, set())
        self.assertNotIn("[/opt]", text)
        self.assertEqual(text.count("[*]"), text.count("[/*]"))


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
    """Examples, refs and per-POS pronunciation live in the optional zone."""

    def test_extras_are_hidden_and_senses_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._build(tmp)
            opt = text.index("[*]")
            self.assertIn("[*]", text)
            self.assertIn("[/*]", text)
            # the sense text is outside the optional zone
            self.assertLess(text.index("To move swiftly on foot."), opt)
            # examples and cross-references stay in the optional zone; "run" has
            # no audio, so the only IPA belongs to the verb and is shown inline
            for extra in ("See also:", "[ex]"):
                self.assertGreater(text.index(extra, opt), opt, extra)

    def test_forms_are_visible_beneath_their_pos(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._build(tmp)
            opt = text.index("[*]")
            self.assertIn("[i]runs (3rd sg.)", text)
            # forms are part of the article, not tucked into the optional zone
            self.assertLess(text.index("[i]runs (3rd sg.)"), opt)
            self.assertNotIn("Forms:", text)

    def test_pronunciation_is_hoisted_when_every_pos_agrees(self):
        # "pub" carries one record, so its IPA stays at the top of the card,
        # above the part of speech and outside the optional zone
        with tempfile.TemporaryDirectory() as tmp:
            args = TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--jsonl", EDGE_FIXTURE, "--out-dir", tmp,
                    "--no-audio",
                ]
            )
            TOOL.build(args)
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            ipa = text.index("/p")
            self.assertLess(ipa, text.index("\t[p]noun[/p]", ipa))
            self.assertNotIn("[*]", text[ipa:ipa + 40])

    def test_run_hoists_its_single_pronunciation(self):
        # "run" has an IPA on its verb record only; one distinct transcription
        # across the card is hoisted above the first POS
        with tempfile.TemporaryDirectory() as tmp:
            text = self._build(tmp)
            ipa = text.index("/ɹʌn/")
            self.assertLess(ipa, text.index("\t[p]verb[/p]", ipa))

    def test_pronunciation_stays_per_pos_when_records_differ(self):
        # two records with different IPAs cannot be hoisted, so each stays
        # under its own part of speech
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "two.jsonl")
            recs = [
                {"word": "wind", "lang": "English", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["Moving air."]}],
                 "sounds": [{"ipa": "/wɪnd/"}]},
                {"word": "wind", "lang": "English", "lang_code": "en", "pos": "verb",
                 "senses": [{"glosses": ["To turn."]}],
                 "sounds": [{"ipa": "/waɪnd/"}]},
            ]
            with open(path, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(json.dumps(r) + "\n")
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "en", "--jsonl", path, "--out-dir", tmp, "--no-audio"]
            )
            TOOL.build(args)
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            self.assertIn("/wɪnd/", text)
            self.assertIn("/waɪnd/", text)
            # each IPA sits below its own POS, not above the first one
            noun = text.index("\t[p]noun[/p]")
            verb = text.index("\t[p]verb[/p]")
            self.assertLess(noun, text.index("/wɪnd/"))
            self.assertLess(text.index("/wɪnd/"), verb)
            self.assertLess(verb, text.index("/waɪnd/"))

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

    def test_sample_excludes_other_languages_despite_a_nested_marker(self):
        # a record of another language can carry a nested "lang_code": "en"; the
        # raw-text prefilter lets it through, so the parsed record must be
        # checked again (compact JSON also exercises the prefilter tolerance)
        compact = {"separators": (",", ":")}
        other = {
            "word": "seam", "lang": "Old English", "lang_code": "ang", "pos": "noun",
            "senses": [{"glosses": ["seam"],
                        "related": [{"word": "sima", "lang_code": "en"}]}],
        }
        english = {
            "word": "seam", "lang": "English", "lang_code": "en", "pos": "noun",
            "senses": [{"glosses": ["A stitched joint."]}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mixed.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(other, **compact) + "\n")
                f.write(json.dumps(english, **compact) + "\n")
            args = TOOL.build_parser().parse_args(
                ["--source-lang", "en", "--jsonl", path, "--sample", "5",
                 "--out-dir", tmp, "--no-audio"]
            )
            TOOL.build(args)
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            self.assertIn("A stitched joint.", text)
            self.assertNotIn("Old English", text)
            self.assertNotIn("\u2022 seam", text)

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

    def test_non_ascii_url_is_percent_encoded(self):
        # wiktextract audio URLs may carry a raw Unicode title (zh-xiàn.ogg);
        # urllib sends the request line as ASCII, so it must be escaped first
        ascii_url = TOOL._ascii_url(
            "https://commons.wikimedia.org/wiki/Special:FilePath/zh-xiàn.ogg"
        )
        ascii_url.encode("ascii")
        self.assertEqual(
            ascii_url,
            "https://commons.wikimedia.org/wiki/Special:FilePath/zh-xi%C3%A0n.ogg",
        )

    def test_ascii_url_leaves_existing_escapes_and_hosts_alone(self):
        url = (
            "https://upload.wikimedia.org/wikipedia/commons/transcoded/a/ab/"
            "LL-Q1860_%28eng%29-Yangolin-bulk_carrier.wav/"
            "LL-Q1860_%28eng%29-Yangolin-bulk_carrier.wav.ogg"
        )
        self.assertEqual(TOOL._ascii_url(url), url)
        plain = "https://upload.wikimedia.org/wikipedia/commons/a/a1/En-au-x.ogg"
        self.assertEqual(TOOL._ascii_url(plain), plain)

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
