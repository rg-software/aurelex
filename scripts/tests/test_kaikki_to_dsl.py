#!/usr/bin/env python3
"""Tests for scripts/kaikki-to-dsl.py.

Run with:  python -m unittest discover -s scripts/tests
"""

import gzip
import importlib.util
import io
import os
import re
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
TOOL_PATH = os.path.join(SCRIPTS, "kaikki-to-dsl.py")
FIXTURE = os.path.join(HERE, "fixtures", "sample-en.jsonl")
EDGE_FIXTURE = os.path.join(HERE, "fixtures", "kaikki-edge.jsonl")
AUDIO_LIMIT_FIXTURE = os.path.join(HERE, "fixtures", "kaikki-audio-limit.jsonl")
TRANSLATION_FIXTURE = os.path.join(HERE, "fixtures", "kaikki-translation.jsonl")


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
                "--target-lang", "ru",
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
            dz = os.path.join(tmp, "kaikki-en-ru.dsl.dz")
            self.assertTrue(os.path.isfile(dz))
            self.assertFalse(os.path.isfile(os.path.join(tmp, "kaikki-en-ru.dsl")))

            text = read_dz(dz)
            self.assertIn('#NAME "kaikki-en-ru"', text)
            self.assertIn('#INDEX_LANGUAGE "English"', text)
            self.assertIn('#CONTENTS_LANGUAGE "Russian"', text)
            self.assertIn("[p]verb[/p]", text)
            self.assertIn("[p]noun[/p]", text)
            self.assertIn("[m1]", text)
            self.assertIn("[ex]I run every morning.[/ex]", text)
            self.assertIn("[trn]бегать; бежать[/trn]", text)
            self.assertIn("Forms: runs", text)
            # cross-references only to indexed headwords (no dead links)
            self.assertIn("[ref]runner[/ref]", text)
            self.assertNotIn("[ref]sprint[/ref]", text)
            # base-form policy: the inflected entry "ran" is not a headword
            self.assertNotIn("ran", headword_lines(text))
            # non-lexical + blank word + German + malformed are not headwords
            self.assertNotIn("foo", headword_lines(text))
            self.assertNotIn("laufen", headword_lines(text))
            self.assertEqual(report.skipped_malformed, 1)
            self.assertGreaterEqual(report.skipped_nonlexical, 1)
            self.assertEqual(report.skipped_inflected, 1)

    def test_include_inflections(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(tmp, "--sample", "20", "--include-inflections"))
            text = read_dz(os.path.join(tmp, "kaikki-en-ru.dsl.dz"))
            self.assertIn("ran", headword_lines(text))

    def test_sample_mode_random_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            def build(out):
                args = TOOL.build_parser().parse_args(
                    [
                        "--source-lang", "en", "--target-lang", "ru",
                        "--jsonl", FIXTURE, "--out-dir", out,
                        "--sample", "3", "--sample-mode", "random", "--no-audio",
                    ]
                )
                return TOOL.build(args)

            out1, out2 = os.path.join(tmp, "a"), os.path.join(tmp, "b")
            build(out1)
            build(out2)
            dz1 = os.path.join(out1, "kaikki-en-ru.dsl.dz")
            dz2 = os.path.join(out2, "kaikki-en-ru.dsl.dz")
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
                        "--source-lang", "en", "--target-lang", "ru",
                        "--jsonl", FIXTURE, "--out-dir", out,
                        "--sample", "20", "--audio-tar", tar_path,
                        "--audio-per-word", "1", "--audio-lang", "US",
                    ]
                )
                return TOOL.build(args)

            out1, out2 = os.path.join(tmp, "a"), os.path.join(tmp, "b")
            report = build(out1)
            build(out2)
            self.assertGreaterEqual(report.audio_found, 1)
            self.assertEqual(report.missing_audio, 0)

            zip1 = os.path.join(out1, "kaikki-en-ru.dsl.dz.files.zip")
            self.assertTrue(os.path.isfile(zip1))
            import zipfile
            with zipfile.ZipFile(zip1) as zf:
                names = sorted(zf.namelist())
            self.assertIn("En-us-run.ogg", names)
            self.assertIn("En-us-multi.ogg", names)
            self.assertNotIn("En-uk-run.ogg", names)

            dz1 = os.path.join(out1, "kaikki-en-ru.dsl.dz")
            dz2 = os.path.join(out2, "kaikki-en-ru.dsl.dz")
            with open(dz1, "rb") as f1, open(dz2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())
            zip2 = os.path.join(out2, "kaikki-en-ru.dsl.dz.files.zip")
            with open(zip1, "rb") as f1, open(zip2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())

    def test_audio_dir_layout_and_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["En-us-run.ogg"])
            args = TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--jsonl", FIXTURE, "--out-dir", tmp,
                    "--sample", "1", "--audio-tar", tar_path,
                    "--audio-per-word", "3", "--audio-layout", "dir", "--preview",
                ]
            )
            TOOL.build(args)
            self.assertTrue(os.path.isdir(os.path.join(tmp, "kaikki-en-en.dsl.dz.files")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, "kaikki-en-en.dsl.dz.files", "En-us-run.ogg")))
            preview = os.path.join(tmp, "kaikki-en-en.preview.html")
            self.assertTrue(os.path.isfile(preview))
            with open(preview, encoding="utf-8") as f:
                self.assertIn("preview", f.read())

    def test_missing_audio_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["something-else.ogg"])
            args = TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--target-lang", "ru", "--jsonl", FIXTURE,
                    "--out-dir", tmp, "--sample", "20", "--audio-tar", tar_path,
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
                "--target-lang", "ru",
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

    def test_translation_sense_key_is_matched_loosely(self):
        # a short key contained in a longer gloss ("A public house where ...")
        self.assertTrue(TOOL._sense_key_matches_gloss(
            "A public house where beverages may be bought.", "public house"))
        # a key that is a superset of the gloss (wiktionary's "— see also")
        self.assertTrue(TOOL._sense_key_matches_gloss(
            "To mention, specify.", "to mention, specify — see also choose, elect"))
        # a wholly unrelated key is rejected
        self.assertFalse(TOOL._sense_key_matches_gloss(
            "A public house where beverages may be bought.", "an unrelated sense key"))
        # a keyless translation applies to any sense
        self.assertTrue(TOOL._sense_key_matches_gloss("Anything at all.", ""))

    def test_bilingual_translations_use_real_sense_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(tmp, "--sample", "20"))
            text = read_dz(os.path.join(tmp, "kaikki-en-ru.dsl.dz"))
            self.assertIn("[trn]паб[/trn]", text)
            self.assertIn("[trn]сло́во[/trn]", text)
            self.assertIn("[trn]выбира́ть[/trn]", text)
            # the German target and the non-matching Russian sense are excluded
            self.assertNotIn("Kneipe", text)
            self.assertNotIn("МИМО", text)

    def test_ipa_comes_from_a_separate_sound_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(tmp, "--sample", "20"))
            text = read_dz(os.path.join(tmp, "kaikki-en-ru.dsl.dz"))
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
            heads = headword_lines(read_dz(os.path.join(tmp, "kaikki-en-ru.dsl.dz")))
            self.assertEqual(len(heads), distinct)
            self.assertEqual(len(set(heads)), distinct)
            self.assertEqual(report.cards, distinct)

    def test_duplicate_records_share_one_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = TOOL.build(self.args(tmp, "--sample", "20"))
            text = read_dz(os.path.join(tmp, "kaikki-en-ru.dsl.dz"))
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
                    "--source-lang", "en", "--target-lang", "ru", "--jsonl", EDGE_FIXTURE,
                    "--out-dir", tmp, "--sample", "20", "--audio-tar", tar_path,
                    "--audio-per-word", "2", "--no-audio-download",
                ]
            )
            report = TOOL.build(args)
            self.assertEqual(report.audio_found, 4)
            self.assertEqual(report.missing_audio, 0)
            import zipfile
            zip_path = os.path.join(tmp, "kaikki-en-ru.dsl.dz.files.zip")
            with zipfile.ZipFile(zip_path) as zf:
                names = set(zf.namelist())
            self.assertEqual(names, {
                "En-us-pub.ogg",
                "En-au-herbed_up.ogg",
                "En-au-sello.ogg",
                "LL-Q1860_(eng)-Yangolin-bulk_carrier.wav.ogg",
            })
            # every bundled file is referenced under exactly its bundled name
            text = read_dz(os.path.join(tmp, "kaikki-en-ru.dsl.dz"))
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
                "--out-dir", os.path.join(tmp, "out"), "--audio-tar", tar_path,
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
            text = read_dz(os.path.join(tmp, "out", "kaikki-en-en.dsl.dz"))
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
            text = read_dz(os.path.join(tmp, "out", "kaikki-en-en.dsl.dz"))
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
            with zipfile.ZipFile(os.path.join(tmp, "out", "kaikki-en-en.dsl.dz.files.zip")) as zf:
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
                    "--out-dir", os.path.join(tmp, "out"), "--audio-tar", tar_path,
                    "--audio-per-word", "3",
                ]
            )
            args.audio_downloader = failing
            report = TOOL.build(args)
            self.assertEqual(report.audio_found, 1)
            self.assertEqual(report.missing_audio, 4)
            text = read_dz(os.path.join(tmp, "out", "kaikki-en-en.dsl.dz"))
            self.assertEqual(re.findall(r"\[s\](.*?)\[/s\]", text), ["En-au-limitword.ogg"])


class TranslationModeTests(unittest.TestCase):
    """The learner-oriented bilingual article (--translation)."""

    def args(self, out_dir, *extra):
        return TOOL.build_parser().parse_args(
            [
                "--source-lang", "en",
                "--target-lang", "ru",
                "--jsonl", TRANSLATION_FIXTURE,
                "--out-dir", out_dir,
                "--no-audio",
                "--translation",
                *extra,
            ]
        )

    def text(self, tmp, *extra):
        TOOL.build(self.args(tmp, *extra))
        return read_dz(os.path.join(tmp, "kaikki-en-ru.dsl.dz"))

    def test_equivalents_are_grouped_by_sense_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.text(tmp)
            self.assertIn("[m1]", text)
            # the two words sharing one sense key sit together
            self.assertIn("бегать  бежать", text)
            # a second key makes a second sense
            self.assertIn("[m2]", text)
            self.assertIn("течь", text)

    def test_target_attributes_are_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.text(tmp)
            # transliterations and target grammar are noise for a native reader
            self.assertNotIn("bégatʹ", text)
            self.assertNotIn("imperfective", text)
            self.assertNotIn("rebjónok", text)
            self.assertNotIn("masculine", text)

    def test_source_pronunciation_and_forms_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.text(tmp)
            self.assertIn("/ɹʌn/", text)          # source transcription kept
            self.assertIn("ran (past)", text)     # source form, compactly labelled
            self.assertIn("runs (pres., 3rd sg.)", text)
            self.assertIn("running (part., pres.)", text)
            # register/dialect variants and table machinery are dropped
            self.assertNotIn("runnest", text)
            self.assertNotIn("no-table-tags", text)
            self.assertNotIn("glossary", text)
            self.assertNotIn("childer", text)
            self.assertNotIn("childs", text)
            self.assertIn("children (pl.)", text)

    def test_extras_are_in_a_collapsible_zone(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.text(tmp)
            self.assertIn("[*]", text)
            self.assertIn("[/opt]", text)
            # the optional zone opens after the senses and closes at the end
            self.assertLess(text.index("[m1]"), text.index("[*]"))
            self.assertLess(text.index("[*]"), text.index("[/opt]"))

    def test_placeholder_sense_key_never_becomes_a_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.text(tmp)
            # the "translations" artifact key must not render as a heading
            self.assertNotIn("Translations\n", text)
            self.assertNotIn(">Translations<", text)

    def test_record_without_target_translations_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.text(tmp)
            self.assertNotIn("untranslated", text)

    def test_translation_needs_a_distinct_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--target-lang", "en",
                    "--jsonl", TRANSLATION_FIXTURE, "--out-dir", tmp,
                    "--no-audio", "--translation",
                ]
            )
            TOOL.build(args)  # must not raise; falls back to monolingual
            text = read_dz(os.path.join(tmp, "kaikki-en-en.dsl.dz"))
            self.assertNotIn("[*]", text)

    def test_monolingual_article_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(TOOL.build_parser().parse_args(
                [
                    "--source-lang", "en", "--target-lang", "en",
                    "--jsonl", TRANSLATION_FIXTURE, "--out-dir", tmp,
                    "--no-audio",
                ]
            ))
            text = read_dz(os.path.join(tmp, "kaikki-en-en.dsl.dz"))
            self.assertIn("To move swiftly on foot.", text)
            self.assertNotIn("бегать", text)
            self.assertNotIn("[*]", text)


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
