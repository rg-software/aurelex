#!/usr/bin/env python3
"""Tests for scripts/kaikki-to-dsl.py.

Run with:  python -m unittest discover -s scripts/tests
"""

import gzip
import contextlib
import io
import json
import os
import re
import shutil
import struct
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.error
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
TOOL_PATH = os.path.join(SCRIPTS, "kaikki-to-dsl.py")
FIXTURE = os.path.join(HERE, "fixtures", "sample-en.jsonl")
EDGE_FIXTURE = os.path.join(HERE, "fixtures", "kaikki-edge.jsonl")
AUDIO_LIMIT_FIXTURE = os.path.join(HERE, "fixtures", "kaikki-audio-limit.jsonl")


def load_tool():
    """The ``kaikki`` package the single-file tool became.

    The suite addresses it exactly as before: ``kaikki.<name>`` is the flat
    facade over the modules, and writing an attribute on it reaches the modules
    that bound that name, so the download stubs below still take effect.
    """
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import kaikki

    return kaikki


TOOL = load_tool()


def read_dz(path):
    with open(path, "rb") as f:
        raw = gzip.decompress(f.read())
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8")


def headword_lines(text, name="kaikki-en"):
    """Headword lines, excluding the about article ``About <name>``."""
    return [
        ln for ln in text.splitlines()
        if ln and not ln[0].isspace() and not ln.startswith("#")
        and ln != f"About {name}"
    ]


def sense_texts(entries):
    """Just the glosses of a ``_group_senses`` entry list.

    Each entry is a ``(gloss, examples, allow_archaic)`` triple; grouping tests
    that only care about the glosses compare through this so they do not have to
    spell out the example list every time.
    """
    return [text for text, _examples, _archaic in entries]


def sense_examples(entries):
    """The raw example strings carried by a ``_group_senses`` entry list."""
    return [examples for _text, examples, _archaic in entries]


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

    def test_audio_filename_is_made_filesystem_safe(self):
        # A MediaWiki name is not a filename: a quote aborted the whole build
        # when a recording used one, because the tar extract wrote it verbatim.
        self.assertEqual(
            TOOL._safe_audio_filename('En-US_pronunciation_of_"lute".ogg'),
            "En-US_pronunciation_of__lute_.ogg",
        )
        # the characters Windows refuses, and control characters, fold to "_"
        self.assertEqual(TOOL._safe_audio_filename("a<b>c:d*e?f.ogg"), "a_b_c_d_e_f.ogg")
        self.assertEqual(TOOL._safe_audio_filename("line\nbreak.ogg"), "line_break.ogg")
        # a trailing space or dot is dropped, as Windows would drop it silently
        self.assertEqual(TOOL._safe_audio_filename("name .ogg"), "name .ogg")
        self.assertEqual(TOOL._safe_audio_filename("trailing.ogg."), "trailing.ogg")
        self.assertEqual(TOOL._safe_audio_filename("trailing.ogg "), "trailing.ogg")
        # a device name gets a prefix so it names a file, not a device
        self.assertEqual(TOOL._safe_audio_filename("CON.ogg"), "_CON.ogg")
        self.assertEqual(TOOL._safe_audio_filename("com1"), "_com1")
        # an empty result still has to be a name
        self.assertEqual(TOOL._safe_audio_filename(' . '), "audio")

    def test_audio_with_a_quote_in_its_name_still_builds(self):
        # Build a dictionary whose only recording is named like the one that
        # aborted the real run, and check the file lands and is referenced
        # under its sanitised name.
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = os.path.join(tmp, "quote.jsonl")
            with open(jsonl, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "word": "lute", "lang_code": "en", "pos": "noun",
                    "senses": [{"glosses": ["A stringed instrument."]}],
                    "sounds": [{
                        "audio": "En-US_pronunciation_of_\u0022lute\u0022.ogg",
                        "ogg_url": "https://upload.wikimedia.org/wikipedia/commons/4/4f/"
                                   'En-US_pronunciation_of_%22lute%22.ogg',
                        "tags": ["US"],
                    }],
                }) + "\n")
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-US_pronunciation_of_%22lute%22.ogg"])
            args = TOOL.build_parser().parse_args([
                "--source-lang", "en", "--jsonl", jsonl, "--out-dir", tmp,
                "--audio-tar", tar_path, "--no-audio-download", "--audio-per-word", "1",
            ])
            report = TOOL.build(args)
            self.assertEqual(report.audio_found, 1)
            zip_path = os.path.join(tmp, "kaikki-en.dsl.files.zip")
            with zipfile.ZipFile(zip_path) as zf:
                bundled = only_audio(set(zf.namelist()))
            self.assertEqual(bundled, {"En-US_pronunciation_of__lute_.ogg"})
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            self.assertIn("[s]En-US_pronunciation_of__lute_.ogg[/s]", text)


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

    def test_cached_recordings_are_counted_not_logged_one_by_one(self):
        # A large dictionary serves tens of thousands of recordings from the
        # cache; one log line each would dominate the run, so hits become a
        # running count and a summary total, with no filename per file.
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])

            def first_downloader(url, dest):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(b"FAKE-" + os.path.basename(dest).encode())

            args = TOOL.build_parser().parse_args([
                "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                "--out-dir", os.path.join(tmp, "out1"), "--audio-tar", tar_path,
                "--audio-per-word", "3",
            ])
            args.audio_downloader = first_downloader
            args.cache_dir = os.path.join(tmp, "cache")
            stream = io.StringIO()
            original = sys.stderr
            sys.stderr = stream
            try:
                TOOL.build(args)  # fills the cache with the two archive-missing files
            finally:
                sys.stderr = original
            # a real download is still named
            self.assertRegex(stream.getvalue(), r"audio downloaded: \S+\.ogg")

            # second run: both recordings are already cached, and download_cached
            # would leave a verified file alone, so the stub writes nothing
            written = []

            def skip_if_cached(url, dest):
                if not os.path.isfile(dest):
                    written.append(dest)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "wb") as f:
                        f.write(b"FAKE")

            args2 = TOOL.build_parser().parse_args([
                "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                "--out-dir", os.path.join(tmp, "out2"), "--audio-tar", tar_path,
                "--audio-per-word", "3",
            ])
            args2.audio_downloader = skip_if_cached
            args2.cache_dir = os.path.join(tmp, "cache")
            stream = io.StringIO()
            sys.stderr = stream
            try:
                report = TOOL.build(args2)
            finally:
                sys.stderr = original

            self.assertEqual(written, [])
            self.assertEqual(report.audio_cached, 2)
            self.assertIn("audio files from cache: 2", report.summary())
            out = stream.getvalue()
            self.assertIn("audio cached: 1", out)
            # the filename is gone: no per-file cached line remains
            self.assertNotRegex(out, r"audio cached: \S+\.ogg")

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


class AudioPrefetchTests(unittest.TestCase):
    """The prefetcher's contract: fill the cache, and the build just works.

    The point of splitting the two is that a rate-limited fetch should not have
    to share a run with rendering, so the tests here drive the real sequence a
    user does -- build (gaps), prefetch, build again -- and assert the second
    build asks the network for nothing.
    """

    def build_args(self, tmp, tar_path, *extra):
        args = TOOL.build_parser().parse_args(
            [
                "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                "--out-dir", os.path.join(tmp, "out"), "--audio-tar", tar_path,
                "--audio-per-word", "3",
            ]
            + list(extra)
        )
        args.cache_dir = os.path.join(tmp, "cache")
        return args

    def prefetch_args(self, tmp, tar_path, *extra):
        args = TOOL.prefetch_parser().parse_args(
            [
                "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                "--audio-tar", tar_path, "--audio-per-word", "3",
            ]
            + list(extra)
        )
        args.cache_dir = os.path.join(tmp, "cache")
        return args

    def with_stubbed_downloads(self, stub):
        """Run a block with ``download_cached`` replaced, restoring it after."""
        original = TOOL.download_cached
        TOOL.download_cached = stub

        def restore():
            TOOL.download_cached = original

        self.addCleanup(restore)

    @contextlib.contextmanager
    def no_network(self, exc):
        """Fail every fetch attempt, to prove a run needs none."""
        original = TOOL._open_with_retries

        def blocked(*args, **kwargs):
            raise exc("the network was used")

        TOOL._open_with_retries = blocked
        try:
            yield
        finally:
            TOOL._open_with_retries = original

    @staticmethod
    def stub_writer(calls):
        def stub(url, dest, *args, **kwargs):
            calls.append((url, dest))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(b"OGGDATA-" + os.path.basename(dest).encode())
            with open(dest + ".sha256", "w", encoding="ascii") as f:
                f.write(TOOL._sha256_file(dest))
            return dest

        return stub

    def manifest_names(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return [line.split("\t")[0] for line in f if line.strip()]

    def test_list_names_the_recordings_the_archive_lacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])
            manifest = os.path.join(tmp, "missing.tsv")
            calls = []
            self.with_stubbed_downloads(self.stub_writer(calls))
            TOOL.prefetch_audio(
                self.prefetch_args(tmp, tar_path, "--list", "--manifest", manifest)
            )
            # nothing was fetched, and the recording the tar holds is not wanted
            self.assertEqual(calls, [])
            # exactly the recordings the article will reference, and no more:
            # the fifth candidate is past the per-word cap of three, so fetching
            # it would spend rate limit on a file nothing points at. The order is
            # the order the scan found them in, which for a streaming run is the
            # only order it can write them.
            self.assertEqual(sorted(self.manifest_names(manifest)), [
                "En-uk-limitword.ogg",
                "En-us-limitword-gone1.ogg",
            ])

    def test_prefetched_files_let_the_next_build_run_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])

            # 1. a build that cannot reach the network leaves gaps
            with self.no_network(OSError):
                report = TOOL.build(self.build_args(tmp, tar_path))
            self.assertEqual(report.audio_found, 1)
            self.assertEqual(report.missing_audio, 4)

            # 2. the prefetcher fills the cache with exactly what was missing
            calls = []
            self.with_stubbed_downloads(self.stub_writer(calls))
            TOOL.prefetch_audio(self.prefetch_args(tmp, tar_path))
            self.assertEqual(
                sorted(os.path.basename(d) for _u, d in calls),
                ["En-uk-limitword.ogg", "En-us-limitword-gone1.ogg"],
            )

            # 3. a build that may not touch the network still gets whole
            #    articles, because the cache answers before any request is made
            with self.no_network(AssertionError):
                report = TOOL.build(
                    self.build_args(tmp, tar_path, "--out-dir", os.path.join(tmp, "out2"))
                )
            self.assertEqual(report.missing_audio, 0)
            self.assertEqual(report.audio_found, 3)
            import zipfile
            with zipfile.ZipFile(
                os.path.join(tmp, "out2", "kaikki-en.dsl.files.zip")
            ) as zf:
                bundled = only_audio(set(zf.namelist()))
            self.assertEqual(bundled, {
                "En-au-limitword.ogg",
                "En-uk-limitword.ogg",
                "En-us-limitword-gone1.ogg",
            })

    def test_a_second_prefetch_fetches_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])
            calls = []
            self.with_stubbed_downloads(self.stub_writer(calls))
            TOOL.prefetch_audio(self.prefetch_args(tmp, tar_path))
            self.assertEqual(len(calls), 2)
            calls.clear()
            TOOL.prefetch_audio(self.prefetch_args(tmp, tar_path))
            self.assertEqual(calls, [])

    def test_limit_leaves_the_rest_for_the_next_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])
            manifest = os.path.join(tmp, "missing.tsv")
            calls = []
            self.with_stubbed_downloads(self.stub_writer(calls))
            TOOL.prefetch_audio(
                self.prefetch_args(tmp, tar_path, "--limit", "1", "--manifest", manifest)
            )
            self.assertEqual(len(calls), 1)
            # the whole wishlist is still on record, and the next run continues
            self.assertEqual(len(self.manifest_names(manifest)), 2)
            TOOL.prefetch_audio(
                self.prefetch_args(tmp, tar_path, "--limit", "1", "--manifest", manifest)
            )
            self.assertEqual(len(calls), 2)

    def test_a_file_is_fetched_before_the_snapshot_is_fully_read(self):
        # the whole point of interleaving: the first file lands while the scan is
        # still early in the file, and a run stopped by --limit never reads the
        # rest of the snapshot at all
        with tempfile.TemporaryDirectory() as tmp:
            words = [f"streamword{i}" for i in range(20)]
            jsonl = os.path.join(tmp, "many.jsonl")
            with open(jsonl, "w", encoding="utf-8") as f:
                for word in words:
                    f.write(json.dumps({
                        "word": word, "lang_code": "en", "pos": "noun",
                        "senses": [{"glosses": ["Something."]}],
                        "sounds": [{
                            "audio": f"{word}.ogg",
                            "ogg_url": f"https://upload.wikimedia.org/w/commons/a/a1/{word}.ogg",
                        }],
                    }) + "\n")
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])

            calls = []
            read = []
            original = TOOL.iter_candidate_records

            def counting(path, source_code, progress=None):
                for record in original(path, source_code, progress):
                    read.append(record.get("word"))
                    yield record

            TOOL.iter_candidate_records = counting
            self.addCleanup(setattr, TOOL, "iter_candidate_records", original)
            self.with_stubbed_downloads(self.stub_writer(calls))
            TOOL.prefetch_audio(
                self.prefetch_args(tmp, tar_path, "--limit", "3", "--jsonl", jsonl)
            )
            self.assertEqual(len(calls), 3)
            # Five of twenty records, not the whole snapshot: three headwords are
            # fetched, and deciding the third takes reading two records past it
            # (one to see the batch end, one to reach the fourth headword's
            # first offer, which is where --limit stops the scan).
            self.assertEqual(read, words[:5])
            self.assertLess(len(read), len(words))

    def test_a_full_run_reads_the_whole_snapshot_and_stops_repeating(self):
        with tempfile.TemporaryDirectory() as tmp:
            words = [f"offered{i}" for i in range(5)]
            jsonl = os.path.join(tmp, "many.jsonl")
            with open(jsonl, "w", encoding="utf-8") as f:
                for word in words:
                    f.write(json.dumps({
                        "word": word, "lang_code": "en", "pos": "noun",
                        "senses": [{"glosses": ["Something."]}],
                        "sounds": [{
                            "audio": f"{word}.ogg",
                            "ogg_url": f"https://upload.wikimedia.org/w/commons/a/a1/{word}.ogg",
                        }],
                    }) + "\n")
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])
            args = self.prefetch_args(tmp, tar_path, "--jsonl", jsonl)

            calls = []
            self.with_stubbed_downloads(self.stub_writer(calls))
            TOOL.prefetch_audio(args)
            self.assertEqual(len(calls), 5)
            # the second headword asking for a file the first already fetched
            # must not produce a second request
            calls.clear()
            TOOL.prefetch_audio(args)
            self.assertEqual(calls, [])

    def test_one_bad_file_does_not_end_the_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])
            calls = []

            def flaky(url, dest, *args, **kwargs):
                if "gone1" in url:
                    calls.append((url, dest))
                    raise OSError("gateway timeout")
                return self.stub_writer(calls)(url, dest)

            self.with_stubbed_downloads(flaky)
            self.assertEqual(
                TOOL.prefetch_audio(self.prefetch_args(tmp, tar_path)), 1
            )
            # the other one still made it into the cache, and the article is left
            # whole anyway: the failed recording is replaced by the next candidate
            # rather than costing the headword a pronunciation
            cache = os.path.join(tmp, "cache", "local", "audio-cache")
            self.assertEqual(
                sorted(n for n in os.listdir(cache) if not n.endswith(".sha256")),
                ["En-uk-limitword.ogg", "En-us-limitword-gone2.ogg"],
            )

    def test_limit_counts_attempts_so_failing_files_cannot_sail_past_it(self):
        # the failure mode this guards: --limit bounded *successes*, so a run in
        # which every file failed tried the entire dictionary -- the one run that
        # most deserves to stop is the one that would have refused to
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])
            calls = []

            def always_fails(url, dest, *args, **kwargs):
                calls.append(url)
                raise OSError("gateway timeout")

            self.with_stubbed_downloads(always_fails)
            self.assertEqual(
                TOOL.prefetch_audio(self.prefetch_args(tmp, tar_path, "--limit", "1")),
                1,
            )
            # one attempt, then it stopped -- and the manifest still records what
            # it had found, so the next run knows where to pick up
            self.assertEqual(len(calls), 1)
            self.assertEqual(
                len(self.manifest_names(
                    os.path.join(tmp, "cache", "local", "audio-missing.tsv")
                )),
                2,
            )

    def test_a_failed_recording_is_replaced_so_the_build_stays_offline(self):
        # Every planning pass assumes the files it probed will land, so a failure
        # invalidates the plan that was built on top of it: the build slot-fills
        # past the gap, and the recording it falls back to was never fetched.
        # The prefetcher has to notice the failure and fetch the replacement,
        # which is the whole promise -- afterwards the build asks for nothing.
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = os.path.join(tmp, "gap.jsonl")
            dead = "https://upload.wikimedia.org/w/commons/a/a1/dead.ogg"
            with open(jsonl, "w", encoding="utf-8") as f:
                for word in ("alpha", "beta"):
                    f.write(json.dumps({
                        "word": word, "lang_code": "en", "pos": "noun",
                        "senses": [{"glosses": ["Something."]}],
                        "sounds": [
                            # tags matching --audio-lang win the ranking, so this
                            # is the recording the article takes
                            {"audio": f"{word}.ogg", "ogg_url": dead,
                             "tags": ["British English"]},
                            {"audio": f"{word}.ogg",
                             "ogg_url": f"https://upload.wikimedia.org/w/commons/a/a1/{word}-alt.ogg"},
                        ],
                    }) + "\n")
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])

            calls = []

            def dead_fails(url, dest, *args, **kwargs):
                if url == dead:
                    calls.append(url)
                    raise OSError("gateway timeout")
                return self.stub_writer(calls)(url, dest)

            self.with_stubbed_downloads(dead_fails)
            args = TOOL.prefetch_parser().parse_args([
                "--source-lang", "en", "--jsonl", jsonl, "--audio-tar", tar_path,
                "--audio-per-word", "1", "--audio-lang", "en",
            ])
            args.cache_dir = os.path.join(tmp, "cache")
            self.assertEqual(TOOL.prefetch_audio(args), 1)  # the dead one failed

            # the dead file was asked for once -- not once per headword, since a
            # URL that just failed gets no second request this run -- and each
            # headword got the recording the build will fall back to
            self.assertEqual(calls.count(dead), 1)
            cache = os.path.join(tmp, "cache", "local", "audio-cache")
            self.assertEqual(
                sorted(n for n in os.listdir(cache) if not n.endswith(".sha256")),
                ["alpha-alt.ogg", "beta-alt.ogg"],
            )

            # and the build that follows reaches the network for nothing, with
            # every headword still holding the recording it was promised. The
            # dead candidate is still counted as missing -- it is, and the build
            # had to try it before slot-filling -- but no article lost anything.
            build = TOOL.build_parser().parse_args([
                "--source-lang", "en", "--jsonl", jsonl, "--out-dir",
                os.path.join(tmp, "out"), "--audio-tar", tar_path,
                "--audio-per-word", "1", "--audio-lang", "en",
            ])
            build.cache_dir = os.path.join(tmp, "cache")
            with self.no_network(AssertionError):
                report = TOOL.build(build)
            self.assertEqual(report.audio_found, 2)
            self.assertEqual(report.missing_audio, 1)

    def test_the_build_records_a_gone_recording_and_the_next_build_skips_it(self):
        # A 404 is a verdict about the file, not about the moment, so a rebuild
        # must not re-discover it. The build keeps the same dead record the
        # prefetcher does: it appends what it finds gone and, on the next run,
        # skips it without touching the network. Wikimedia names are capitalised,
        # which is exactly the case the match has to fold.
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = os.path.join(tmp, "gone.jsonl")
            with open(jsonl, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "word": "alpha", "lang_code": "en", "pos": "noun",
                    "senses": [{"glosses": ["Something."]}],
                    "sounds": [{
                        "audio": "alpha.ogg",
                        "ogg_url": "https://upload.wikimedia.org/w/commons/a/a1/En-us-gone.ogg",
                    }],
                }) + "\n")
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])

            calls = []

            def gone_404(url, dest, *args, **kwargs):
                calls.append(os.path.basename(dest))
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

            self.with_stubbed_downloads(gone_404)

            def build_args():
                parsed = TOOL.build_parser().parse_args([
                    "--source-lang", "en", "--jsonl", jsonl, "--out-dir",
                    os.path.join(tmp, "out"), "--audio-tar", tar_path,
                    "--audio-per-word", "1",
                ])
                parsed.cache_dir = os.path.join(tmp, "cache")
                return parsed

            with self.captured() as out:
                report = TOOL.build(build_args())
            self.assertEqual(report.missing_audio, 1)
            self.assertIn("audio gone (HTTP 404)", out.getvalue())
            self.assertEqual(calls, ["En-us-gone.ogg"])
            self.assertEqual(self.dead_names(tmp), ["En-us-gone.ogg"])

            # the rebuild asks for nothing, and reports the same shortfall
            calls.clear()
            with self.captured() as out:
                report = TOOL.build(build_args())
            self.assertEqual(calls, [])
            self.assertEqual(report.missing_audio, 1)
            self.assertNotIn("audio gone", out.getvalue())


    @contextlib.contextmanager
    def captured(self):
        """Capture stderr, which is where the run reports what happened."""
        stream = io.StringIO()
        original = sys.stderr
        sys.stderr = stream
        try:
            yield stream
        finally:
            sys.stderr = original

    def dead_names(self, tmp):
        path = os.path.join(tmp, "cache", "local", "audio-dead.tsv")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return [line.split("\t")[0] for line in f if line.strip()]

    def test_a_deleted_file_is_never_asked_for_again_and_the_run_reports_done(self):
        # The question a run has to answer is "am I finished?", and a URL that is
        # gone cannot ever succeed. Retrying it on every run would make a finished
        # cache look like permanent outstanding work, so the refusal is recorded
        # and the run is allowed to call itself done.
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = os.path.join(tmp, "gone.jsonl")
            gone = "https://upload.wikimedia.org/w/commons/a/a1/En-us-gone.ogg"
            with open(jsonl, "w", encoding="utf-8") as f:
                for word in ("alpha", "beta"):
                    f.write(json.dumps({
                        "word": word, "lang_code": "en", "pos": "noun",
                        "senses": [{"glosses": ["Something."]}],
                        "sounds": [
                            # the tags make this the recording an article takes
                            {"audio": f"{word}.ogg", "ogg_url": gone,
                             "tags": ["British English"]},
                            {"audio": f"{word}.ogg",
                             "ogg_url": f"https://upload.wikimedia.org/w/commons/a/a1/{word}-alt.ogg"},
                        ],
                    }) + "\n")
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])

            calls = []

            def deleted(url, dest, *args, **kwargs):
                calls.append(os.path.basename(dest))
                if url == gone:
                    raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
                return self.stub_writer([])(url, dest)

            self.with_stubbed_downloads(deleted)
            args = TOOL.prefetch_parser().parse_args([
                "--source-lang", "en", "--jsonl", jsonl, "--audio-tar", tar_path,
                "--audio-per-word", "1", "--audio-lang", "en", "--spacing", "0",
            ])
            args.cache_dir = os.path.join(tmp, "cache")

            with self.captured() as out:
                self.assertEqual(TOOL.prefetch_audio(args), 0)
            self.assertIn("permanently gone", out.getvalue())
            self.assertIn("HTTP 404", out.getvalue())
            self.assertIn("done:", out.getvalue())
            # the replacement for each headword was fetched in the same run, so
            # no article is left short, and the dead file is on the record
            self.assertEqual(sorted(calls), ["En-us-gone.ogg", "alpha-alt.ogg", "beta-alt.ogg"])
            self.assertEqual(self.dead_names(tmp), ["En-us-gone.ogg"])

            # the next run asks for nothing at all, and is still finished
            calls.clear()
            with self.captured() as out:
                self.assertEqual(TOOL.prefetch_audio(args), 0)
            self.assertEqual(calls, [])
            self.assertIn("done:", out.getvalue())
            self.assertEqual(self.dead_names(tmp), ["En-us-gone.ogg"])

    def test_a_capitalised_dead_name_is_matched_case_insensitively(self):
        # The dead file holds the name as written ('En-us-...'), while the lookup
        # is a folded match key ('en-us-...'). Loading the set without folding it
        # would make the skip never fire for any real Wikimedia name, so a run
        # would re-request every 404 it had already classified.
        wishlist = TOOL.AudioWishlist("/tmp/cache", 1, None, set(), {"En-us-gone.ogg"})
        self.assertIn(TOOL._audio_match_key("En-us-gone.ogg"), wishlist.dead)

    def test_a_rate_limited_file_is_left_for_later_and_the_run_says_not_finished(self):
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = os.path.join(tmp, "blocked.jsonl")
            blocked = "https://upload.wikimedia.org/w/commons/a/a1/blocked.ogg"
            with open(jsonl, "w", encoding="utf-8") as f:
                for word in ("alpha", "beta"):
                    f.write(json.dumps({
                        "word": word, "lang_code": "en", "pos": "noun",
                        "senses": [{"glosses": ["Something."]}],
                        "sounds": [
                            {"audio": f"{word}.ogg", "ogg_url": blocked,
                             "tags": ["British English"]},
                            {"audio": f"{word}.ogg",
                             "ogg_url": f"https://upload.wikimedia.org/w/commons/a/a1/{word}-alt.ogg"},
                        ],
                    }) + "\n")
            tar_path = os.path.join(tmp, "audios.tar")
            make_tar(tar_path, ["audios/En-au-limitword.ogg"])

            calls = []
            limited = [True]

            def throttled(url, dest, *args, **kwargs):
                calls.append(os.path.basename(dest))
                if url == blocked and limited[0]:
                    raise urllib.error.HTTPError(
                        url, 429, "Too Many Requests", None, None
                    )
                return self.stub_writer([])(url, dest)

            self.with_stubbed_downloads(throttled)
            args = TOOL.prefetch_parser().parse_args([
                "--source-lang", "en", "--jsonl", jsonl, "--audio-tar", tar_path,
                "--audio-per-word", "1", "--audio-lang", "en", "--spacing", "0",
            ])
            args.cache_dir = os.path.join(tmp, "cache")

            with self.captured() as out:
                # still work to do, so still work to come back to
                self.assertEqual(TOOL.prefetch_audio(args), 1)
            self.assertIn("rate-limited, blocked or interrupted", out.getvalue())
            self.assertIn("not finished", out.getvalue())
            # a refusal is not a verdict about the file, so it is not recorded as
            # permanently gone -- that would throw the file away for good
            self.assertEqual(self.dead_names(tmp), [])

            # once the limit clears, the same run picks it up and finishes
            limited[0] = False
            calls.clear()
            with self.captured() as out:
                self.assertEqual(TOOL.prefetch_audio(args), 0)
            self.assertEqual(calls, ["blocked.ogg"])
            self.assertIn("done:", out.getvalue())

    def test_only_a_definitive_status_counts_as_permanent(self):
        def http_error(code):
            return urllib.error.HTTPError("u", code, "m", None, None)

        for code in sorted(TOOL.PERMANENT_HTTP_STATUS):
            self.assertTrue(TOOL.failure_is_permanent(http_error(code)), code)
        # a refusal or a hiccup is not a statement about the file: calling these
        # permanent would silently drop a recording the article could have had
        for code in (403, 429, 500, 502, 503, 504):
            self.assertFalse(TOOL.failure_is_permanent(http_error(code)), code)
        self.assertFalse(TOOL.failure_is_permanent(OSError("timed out")))
        self.assertFalse(TOOL.failure_is_permanent(
            urllib.error.URLError("connection reset")
        ))


class AudioShardTests(unittest.TestCase):
    """The split-and-fetch workflow: several machines can share one gap.

    One machine plans, many machines fetch disjoint lists, and the building
    machine combines the results by copying -- no merge command, because a file
    already in the cache is skipped anyway. The re-run of the prefetcher over the
    combined cache is both the check and the backstop.
    """

    def make_tar_with_limit(self, tmp):
        path = os.path.join(tmp, "audios.tar")
        make_tar(path, ["audios/En-au-limitword.ogg"])
        return path

    def prefetch_args(self, tmp, tar_path, *extra):
        args = TOOL.prefetch_parser().parse_args(
            [
                "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                "--audio-tar", tar_path, "--audio-per-word", "3",
            ]
            + list(extra)
        )
        args.cache_dir = os.path.join(tmp, "cache")
        return args

    def build_args(self, tmp, tar_path, *extra):
        args = TOOL.build_parser().parse_args(
            [
                "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                "--out-dir", os.path.join(tmp, "out"), "--audio-tar", tar_path,
                "--audio-per-word", "3",
            ]
            + list(extra)
        )
        args.cache_dir = os.path.join(tmp, "cache")
        return args

    @contextlib.contextmanager
    def no_network(self, exc):
        """Fail every fetch attempt, to prove a run needs none."""
        original = TOOL._open_with_retries

        def blocked(*args, **kwargs):
            raise exc("the network was used")

        TOOL._open_with_retries = blocked
        try:
            yield
        finally:
            TOOL._open_with_retries = original

    def stub_writer(self, calls):
        def stub(url, dest, *args, **kwargs):
            calls.append((url, dest))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(b"OGGDATA-" + os.path.basename(dest).encode())
            with open(dest + ".sha256", "w", encoding="ascii") as f:
                f.write(TOOL._sha256_file(dest))
            return dest

        return stub

    def shard_names(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return [
                line.split("\t")[0]
                for line in f
                if line.strip() and not line.startswith("#")
            ]

    @contextlib.contextmanager
    def captured(self):
        stream = io.StringIO()
        original = sys.stderr
        sys.stderr = stream
        try:
            yield stream
        finally:
            sys.stderr = original

    def test_split_writes_disjoint_balanced_shards_that_explain_themselves(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = self.make_tar_with_limit(tmp)
            manifest = os.path.join(tmp, "missing.tsv")
            calls = []
            original = TOOL.download_cached
            TOOL.download_cached = self.stub_writer(calls)
            self.addCleanup(setattr, TOOL, "download_cached", original)

            # what an unsharded --list would have written, for comparison
            with self.captured():
                TOOL.prefetch_audio(
                    self.prefetch_args(tmp, tar_path, "--list", "--manifest", manifest)
                )
            expected = self.shard_names(manifest)

            for count in (1, 2, 5):  # N at, below and above the file count
                split_manifest = os.path.join(tmp, f"missing-{count}.tsv")
                calls.clear()
                with self.captured() as out:
                    self.assertEqual(
                        TOOL.prefetch_audio(
                            self.prefetch_args(
                                tmp, tar_path, "--split", str(count),
                                "--manifest", split_manifest,
                            )
                        ),
                        0,
                    )
                # splitting is listing: nothing was fetched
                self.assertEqual(calls, [])
                self.assertIn("listing only", out.getvalue())

                shards = TOOL.shard_paths(split_manifest, count)
                self.assertIn(".shard-1-of-%d." % count, shards[0])
                found = []
                for path in shards:
                    if os.path.exists(path):
                        found.extend(self.shard_names(path))
                        with open(path, encoding="utf-8") as header_file:
                            header = header_file.read()
                        self.assertTrue(header.startswith("#"), path)
                        self.assertIn("fetch-list", header, path)
                        self.assertIn("planned with", header, path)
                # complete against the manifest and disjoint: every name once
                self.assertEqual(sorted(found), sorted(expected))
                self.assertEqual(len(found), len(set(found)))
                # balanced to within one file, from "one shard" down to "more
                # shards than files" (where the surplus shards are not written)
                sizes = [
                    len(self.shard_names(p))
                    for p in shards
                    if os.path.exists(p)
                ]
                self.assertLessEqual(max(sizes) - min(sizes), 1)

    def test_local_cache_is_absent_and_an_empty_plan_writes_no_shards(self):
        # 4.9 / 2.4: a file the local cache already holds is not work, and a run
        # with nothing outstanding leaves no shard file behind at all -- the
        # wishlist is exactly what a would-be build would still fetch.
        expected = ["En-uk-limitword.ogg", "En-us-limitword-gone1.ogg"]
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = self.make_tar_with_limit(tmp)
            cache = os.path.join(tmp, "cache", "local", "audio-cache")
            os.makedirs(cache, exist_ok=True)
            with open(os.path.join(cache, expected[0]), "wb") as f:
                f.write(b"OGGDATA")
            with open(os.path.join(cache, expected[0] + ".sha256"), "w",
                      encoding="ascii") as f:
                f.write(TOOL._sha256_file(os.path.join(cache, expected[0])))

            manifest = os.path.join(tmp, "missing.tsv")
            original = TOOL.download_cached
            TOOL.download_cached = self.stub_writer([])
            self.addCleanup(setattr, TOOL, "download_cached", original)
            with self.captured() as out:
                TOOL.prefetch_audio(
                    self.prefetch_args(tmp, tar_path, "--split", "2",
                                       "--manifest", manifest)
                )
            self.assertIn("already cached: 1", out.getvalue())
            remaining = []
            for path in TOOL.shard_paths(manifest, 2):
                if os.path.exists(path):
                    remaining.extend(self.shard_names(path))
            self.assertEqual(remaining, [expected[1]])

            # fill the last gap: the next split has no shards to write. Remove
            # the previous run's shards first, so a fresh run is what is judged.
            for path in TOOL.shard_paths(manifest, 2):
                if os.path.exists(path):
                    os.remove(path)
            with open(os.path.join(cache, expected[1]), "wb") as f:
                f.write(b"OGGDATA")
            with open(os.path.join(cache, expected[1] + ".sha256"), "w",
                      encoding="ascii") as f:
                f.write(TOOL._sha256_file(os.path.join(cache, expected[1])))
            with self.captured() as out:
                TOOL.prefetch_audio(
                    self.prefetch_args(tmp, tar_path, "--split", "2",
                                       "--manifest", manifest)
                )
            self.assertIn("already cached: 2", out.getvalue())
            self.assertEqual(
                [p for p in TOOL.shard_paths(manifest, 2) if os.path.exists(p)],
                [],
            )

    def test_split_rejects_contradictory_and_broken_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = self.make_tar_with_limit(tmp)
            for bad, message in (
                ("--limit", "--split"),
            ):
                with self.assertRaises(SystemExit):
                    TOOL.prefetch_audio(
                        self.prefetch_args(tmp, tar_path, "--split", "2", bad, "1")
                    )
            with self.assertRaises(SystemExit):
                TOOL.prefetch_audio(
                    self.prefetch_args(tmp, tar_path, "--split", "0")
                )

    def test_workers_fill_directories_the_building_machine_just_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = self.make_tar_with_limit(tmp)

            # 1. a build that cannot reach the network leaves gaps to fill
            with self.no_network(OSError):
                report = TOOL.build(self.build_args(tmp, tar_path))
            self.assertEqual(report.audio_found, 1)
            self.assertEqual(report.missing_audio, 4)

            # 2. the owner plans with --split
            manifest = os.path.join(tmp, "missing.tsv")
            with self.captured():
                TOOL.prefetch_audio(
                    self.prefetch_args(tmp, tar_path, "--split", "2",
                                       "--manifest", manifest)
                )

            # 3. each worker fetches its shard into its own directory
            calls = []
            original = TOOL.download_cached
            TOOL.download_cached = self.stub_writer(calls)
            self.addCleanup(setattr, TOOL, "download_cached", original)
            worker_dirs = []
            for shard in TOOL.shard_paths(manifest, 2):
                worker_dir = os.path.join(tmp, "worker" + os.path.basename(shard))
                worker_dirs.append(worker_dir)
                args = TOOL.fetch_list_parser().parse_args(
                    [shard, "--into", worker_dir, "--spacing", "0"]
                )
                with self.captured():
                    self.assertEqual(TOOL.fetch_list(args), 0)

            # every recording landed exactly once, each with a .sha256 sidecar
            self.assertEqual(len(calls), 2)
            self.assertEqual(len({calls[0][1], calls[1][1]}), 2)
            landed = []
            for worker_dir in worker_dirs:
                for name in os.listdir(worker_dir):
                    landed.append(worker_dir + os.sep + name)
            self.assertEqual(
                sorted(os.path.basename(n) for n in landed),
                ["En-uk-limitword.ogg", "En-uk-limitword.ogg.sha256",
                 "En-us-limitword-gone1.ogg",
                 "En-us-limitword-gone1.ogg.sha256"],
            )

            # 4. combining is copying: a flat set of named, verified files
            cache = os.path.join(tmp, "cache", "local", "audio-cache")
            os.makedirs(cache, exist_ok=True)
            for worker_dir in worker_dirs:
                for name in os.listdir(worker_dir):
                    shutil.copy2(
                        os.path.join(worker_dir, name), os.path.join(cache, name)
                    )

            # 5. the closing prefetch run has nothing to ask for
            calls.clear()
            with self.captured() as out:
                self.assertEqual(TOOL.prefetch_audio(
                    self.prefetch_args(tmp, tar_path)
                ), 0)
            self.assertEqual(calls, [])
            self.assertIn("done:", out.getvalue())

            # 6. a build that may not touch the network gets whole articles
            with self.no_network(AssertionError):
                report = TOOL.build(
                    self.build_args(tmp, tar_path, "--audio-per-word", "1")
                )
            self.assertEqual(report.missing_audio, 0)

    def test_a_partial_worker_run_is_finished_by_the_closing_local_pass(self):
        # 4.8: a worker that stops early leaves a gap, and the re-run that checks
        # the copy is also what closes it -- it requests only what is missing.
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = self.make_tar_with_limit(tmp)
            shard = os.path.join(tmp, "one.tsv")
            base = "https://upload.wikimedia.org/wikipedia/commons/"
            with open(shard, "w", encoding="utf-8") as f:
                f.write("En-uk-limitword.ogg\t" + base + "a/a1/En-uk-limitword.ogg\n")
                f.write("En-us-limitword-gone1.ogg\t" + base + "a/a3/En-us-limitword-gone1.ogg\n")

            calls = []
            original = TOOL.download_cached
            TOOL.download_cached = self.stub_writer(calls)
            self.addCleanup(setattr, TOOL, "download_cached", original)

            # the worker fetches one of the two, then stops at its attempt cap
            worker_dir = os.path.join(tmp, "partial")
            args = TOOL.fetch_list_parser().parse_args(
                [shard, "--into", worker_dir, "--limit", "1", "--spacing", "0"]
            )
            with self.captured():
                self.assertEqual(TOOL.fetch_list(args), 1)
            cache = os.path.join(tmp, "cache", "local", "audio-cache")
            os.makedirs(cache, exist_ok=True)
            for name in os.listdir(worker_dir):
                shutil.copy2(os.path.join(worker_dir, name), os.path.join(cache, name))

            # the closing local run requests exactly the recording no worker took
            calls.clear()
            with self.captured() as out:
                self.assertEqual(TOOL.prefetch_audio(
                    self.prefetch_args(tmp, tar_path)
                ), 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(
                os.path.basename(calls[0][1]), "En-us-limitword-gone1.ogg"
            )
            self.assertIn("done:", out.getvalue())

    def test_worker_records_a_deleted_file_beside_the_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            shard = os.path.join(tmp, "one.tsv")
            gone = "https://upload.wikimedia.org/w/commons/a/a1/gone.ogg"
            with open(shard, "w", encoding="utf-8") as f:
                f.write("# a hand-written shard for this test\n")
                f.write("sub/gone.ogg\t" + gone + "\n")

            calls = []

            def still_writes_if_gone_not_asked(url, dest, *args, **kwargs):
                self.assertNotEqual(url, gone)
                calls.append((url, dest))
                return self.stub_writer([])(url, dest)

            original = TOOL.download_cached
            TOOL.download_cached = lambda url, dest, *a, **kw: (
                self.stub_writer(calls)(url, dest)
                if url != gone
                else (_ for _ in ()).throw(
                    urllib.error.HTTPError(url, 404, "Not Found", None, None)
                )
            )
            self.addCleanup(setattr, TOOL, "download_cached", original)

            args = TOOL.fetch_list_parser().parse_args(
                [shard, "--into", os.path.join(tmp, "fill")]
            )
            with self.captured() as out:
                self.assertEqual(TOOL.fetch_list(args), 0)
            # gone is recorded next to the shard, and the directory stays clean
            self.assertEqual(os.listdir(os.path.join(tmp, "fill")), [])
            self.assertEqual(
                self.shard_names(shard + ".dead.tsv"), ["sub/gone.ogg"]
            )
            self.assertIn("permanently gone", out.getvalue())
            self.assertIn("done:", out.getvalue())

    def test_worker_does_not_re_request_a_name_its_dead_file_holds(self):
        # A re-run over the same shard must not re-attempt the 404s the first run
        # already classified: the dead file beside the shard is the record, and
        # honouring it is what makes the second pass cheap rather than a repeat
        # of every file that can never be fetched.
        with tempfile.TemporaryDirectory() as tmp:
            shard = os.path.join(tmp, "one.tsv")
            base = "https://upload.wikimedia.org/w/commons/a/a1/"
            with open(shard, "w", encoding="utf-8") as f:
                f.write(f"En-us-gone.ogg\t{base}En-us-gone.ogg\n")
            with open(shard + ".dead.tsv", "w", encoding="utf-8") as f:
                f.write(f"En-us-gone.ogg\t{base}En-us-gone.ogg\tHTTP 404\n")
            fill = os.path.join(tmp, "fill")
            os.makedirs(fill, exist_ok=True)

            calls = []
            original = TOOL.download_cached
            TOOL.download_cached = self.stub_writer(calls)
            self.addCleanup(setattr, TOOL, "download_cached", original)

            args = TOOL.fetch_list_parser().parse_args(
                [shard, "--into", fill, "--spacing", "0"]
            )
            with self.captured() as out:
                self.assertEqual(TOOL.fetch_list(args), 0)
            self.assertEqual(calls, [])
            self.assertIn("already known gone", out.getvalue())
            self.assertIn("done:", out.getvalue())

    def test_worker_limits_attempts_and_a_repeat_finishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            shard = os.path.join(tmp, "two.tsv")
            base = "https://upload.wikimedia.org/w/commons/a/a1/"
            with open(shard, "w", encoding="utf-8") as f:
                for i in range(4):
                    f.write(f"a{i}.ogg\t{base}a{i}.ogg\n")

            calls = []
            original = TOOL.download_cached
            TOOL.download_cached = self.stub_writer(calls)
            self.addCleanup(setattr, TOOL, "download_cached", original)

            fill = os.path.join(tmp, "fill")
            args = TOOL.fetch_list_parser().parse_args(
                [shard, "--into", fill, "--limit", "1", "--spacing", "0"]
            )
            with self.captured() as out:
                self.assertEqual(TOOL.fetch_list(args), 1)
            self.assertIn("stopped at --limit 1", out.getvalue())
            self.assertEqual([os.path.basename(d) for _u, d in calls], ["a0.ogg"])

            # a continuation run skips what landed and fetches only the rest
            calls.clear()
            args = TOOL.fetch_list_parser().parse_args(
                [shard, "--into", fill, "--spacing", "0"]
            )
            with self.captured() as out:
                self.assertEqual(TOOL.fetch_list(args), 0)
            self.assertEqual(
                sorted(os.path.basename(d) for _u, d in calls),
                ["a1.ogg", "a2.ogg", "a3.ogg"],
            )
            self.assertIn("done:", out.getvalue())
            self.assertIn("already cached: 1", out.getvalue())

    def test_worker_refuses_malformed_and_escaping_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            shard = os.path.join(tmp, "bad.tsv")
            fill = os.path.join(tmp, "fill")
            # no entry may reach a real network: the good line only documents the
            # format, and it would be stubbed anyway once we get past it
            original = TOOL.download_cached
            TOOL.download_cached = lambda url, dest, *a, **kw: dest
            self.addCleanup(setattr, TOOL, "download_cached", original)
            with open(shard, "w", encoding="utf-8") as f:
                f.write("# comment lines are fine\n")
                f.write("good.ogg\thttps://example/good.ogg\n")
                f.write("this-line-has-no-tab\n")
            args = TOOL.fetch_list_parser().parse_args([shard, "--into", fill])
            with self.assertRaises(SystemExit) as ctx:
                TOOL.fetch_list(args)
            self.assertIn("bad.tsv:3", str(ctx.exception))

            with open(shard, "w", encoding="utf-8") as f:
                f.write("../escape.ogg\thttps://example/escape.ogg\n")
            with self.assertRaises(SystemExit) as ctx:
                TOOL.fetch_list(args)
            self.assertIn("..", str(ctx.exception))

    def test_copying_a_cache_over_itself_changes_nothing(self):
        # 4.10: the combine step is a plain copy, and a copy that lands on an
        # existing cache still leaves every file verified and unchanged.
        with tempfile.TemporaryDirectory() as tmp:
            shard = os.path.join(tmp, "two.tsv")
            base = "https://upload.wikimedia.org/w/commons/a/a1/"
            with open(shard, "w", encoding="utf-8") as f:
                for i in range(2):
                    f.write(f"b{i}.ogg\t{base}b{i}.ogg\n")

            calls = []
            original = TOOL.download_cached
            TOOL.download_cached = self.stub_writer(calls)
            self.addCleanup(setattr, TOOL, "download_cached", original)

            cache = os.path.join(tmp, "cache")
            args = TOOL.fetch_list_parser().parse_args(
                [shard, "--into", cache, "--spacing", "0"]
            )
            with self.captured():
                self.assertEqual(TOOL.fetch_list(args), 0)
            with open(os.path.join(cache, "b0.ogg"), "rb") as f:
                contents = f.read()

            # the combine step is literally a copy; copying a cache back over
            # itself (via a duplicate of it) must not disturb the files
            mirror = os.path.join(tmp, "mirror")
            shutil.copytree(cache, mirror)
            for name in os.listdir(mirror):
                shutil.copy2(os.path.join(mirror, name), os.path.join(cache, name))

            calls.clear()
            args = TOOL.fetch_list_parser().parse_args(
                [shard, "--into", cache, "--spacing", "0"]
            )
            with self.captured() as out:
                self.assertEqual(TOOL.fetch_list(args), 0)
            self.assertEqual(calls, [])
            self.assertIn("already cached: 2", out.getvalue())
            with open(os.path.join(cache, "b0.ogg"), "rb") as f:
                self.assertEqual(f.read(), contents)


class BundleRebuildTests(unittest.TestCase):
    """Rebuild a rendered dictionary's resource bundle without re-rendering."""

    def bundle_args(self, tmp, dict_path, *extra):
        return TOOL.bundle_audio_parser().parse_args(
            [dict_path, "--jsonl", AUDIO_LIMIT_FIXTURE, "--cache-dir",
             os.path.join(tmp, "cache")] + list(extra)
        )

    @contextlib.contextmanager
    def captured(self):
        stream = io.StringIO()
        original = sys.stderr
        sys.stderr = stream
        try:
            yield stream
        finally:
            sys.stderr = original

    def write_dz(self, path, text):
        with open(path, "wb") as f:
            f.write(TOOL.make_dictzip(TOOL.encode_dsl(text)))

    def cache_dir(self, tmp):
        path = os.path.join(tmp, "cache", "local", "audio-cache")
        os.makedirs(path, exist_ok=True)
        return path

    def zip_names(self, path):
        with zipfile.ZipFile(path) as z:
            return set(z.namelist())

    def test_the_bundle_stores_entries_rather_than_recompressing(self):
        # The bundle is almost all already-compressed audio, so deflating it
        # spends minutes of CPU for no size gain; entries must be stored.
        with tempfile.TemporaryDirectory() as tmp:
            sources = {}
            for name in ("a.ogg", "b.mp3"):
                path = os.path.join(tmp, name)
                with open(path, "wb") as f:
                    f.write(b"\0" * 4096)
                sources[name] = path
            out = os.path.join(tmp, "x.dsl.files.zip")
            TOOL.write_bundle(sources, out, "zip")
            with zipfile.ZipFile(out) as z:
                self.assertEqual(z.testzip(), None)
                self.assertTrue(
                    all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist())
                )
                self.assertEqual(sorted(z.namelist()), ["a.ogg", "b.mp3"])

    def test_the_bundle_directory_layout_copies_each_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = {}
            for name in ("a.ogg", "b.mp3"):
                path = os.path.join(tmp, "src-" + name)
                with open(path, "wb") as f:
                    f.write(b"DATA-" + name.encode())
                sources[name] = path
            out = os.path.join(tmp, "x.dsl.files")
            TOOL.write_bundle(sources, out, "dir")
            self.assertEqual(sorted(os.listdir(out)), ["a.ogg", "b.mp3"])
            with open(os.path.join(out, "a.ogg"), "rb") as f:
                self.assertEqual(f.read(), b"DATA-a.ogg")

    def test_references_are_collected_in_order_and_unescaped(self):
        text = (
            "[s]a.ogg[/s] [s]b.ogg[/s] [s]a.ogg[/s] "
            "[s]gd_tag_x.svg[/s] [s]we\\[ird\\].ogg[/s]"
        )
        self.assertEqual(
            TOOL.collect_audio_refs(text),
            ["a.ogg", "b.ogg", "gd_tag_x.svg", "we[ird].ogg"],
        )

    def test_rebuild_restores_the_bundle_a_build_wrote(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar = os.path.join(tmp, "audios.tar")
            make_tar(tar, ["audios/En-au-limitword.ogg", "audios/En-uk-limitword.ogg",
                           "audios/En-us-limitword-gone1.ogg"])
            out = os.path.join(tmp, "out")
            TOOL.build(TOOL.build_parser().parse_args([
                "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
                "--out-dir", out, "--audio-tar", tar, "--audio-per-word", "3",
                "--cache-dir", os.path.join(tmp, "cache"), "--no-audio-download",
            ]))
            dz = os.path.join(out, "kaikki-en.dsl.dz")
            zip_path = os.path.join(out, "kaikki-en.dsl.files.zip")
            with open(zip_path, "rb") as f:
                zip_before = f.read()
            with open(dz, "rb") as f:
                dz_before = f.read()
            os.remove(zip_path)

            with self.captured():
                self.assertEqual(
                    TOOL.bundle_audio(self.bundle_args(tmp, dz, "--audio-tar", tar)), 0)
            # byte-for-byte what a build wrote, not merely the same names
            with open(zip_path, "rb") as f:
                self.assertEqual(f.read(), zip_before)
            # the references were already safe, so the dictionary is untouched
            with open(dz, "rb") as f:
                self.assertEqual(f.read(), dz_before)

            # repeating is safe and changes nothing
            with self.captured():
                self.assertEqual(
                    TOOL.bundle_audio(self.bundle_args(tmp, dz, "--audio-tar", tar)), 0)
            with open(zip_path, "rb") as f:
                self.assertEqual(f.read(), zip_before)

    def test_an_unsafe_reference_is_rewritten_and_bundled(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = 'En-US_pronunciation_of_"lute".ogg'
            dz = os.path.join(tmp, "x.dsl.dz")
            self.write_dz(dz, f"[s]{raw}[/s]\n")
            tar = os.path.join(tmp, "audios.tar")
            make_tar(tar, ["audios/" + raw])

            with self.captured() as out:
                self.assertEqual(
                    TOOL.bundle_audio(self.bundle_args(tmp, dz, "--audio-tar", tar)), 0)
            safe = "En-US_pronunciation_of__lute_.ogg"
            # the link and the bundled file both moved to the safe name
            self.assertEqual(TOOL.collect_audio_refs(read_dz(dz)), [safe])
            self.assertIn(safe, self.zip_names(os.path.join(tmp, "x.dsl.files.zip")))
            self.assertIn("rewrote", out.getvalue())

    def test_a_recording_only_in_the_cache_is_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            dz = os.path.join(tmp, "x.dsl.dz")
            self.write_dz(dz, "[s]only-cached.ogg[/s]\n")
            with open(os.path.join(self.cache_dir(tmp), "only-cached.ogg"), "wb") as f:
                f.write(b"OGGDATA")

            with self.captured():
                self.assertEqual(TOOL.bundle_audio(self.bundle_args(
                    tmp, dz, "--audio-tar", os.path.join(tmp, "absent.tar"))), 0)
            self.assertIn(
                "only-cached.ogg", self.zip_names(os.path.join(tmp, "x.dsl.files.zip"))
            )

    def test_a_recording_found_nowhere_is_warned_about(self):
        with tempfile.TemporaryDirectory() as tmp:
            dz = os.path.join(tmp, "x.dsl.dz")
            self.write_dz(dz, "[s]nowhere.ogg[/s]\n")
            tar = os.path.join(tmp, "audios.tar")
            make_tar(tar, ["audios/something-else.ogg"])

            with self.captured() as out:
                self.assertEqual(
                    TOOL.bundle_audio(self.bundle_args(tmp, dz, "--audio-tar", tar)), 0)
            self.assertIn("were not found", out.getvalue())
            names = self.zip_names(os.path.join(tmp, "x.dsl.files.zip"))
            self.assertNotIn("nowhere.ogg", names)
            self.assertTrue(set(TOOL._ICON_FILES) <= names)

    def test_directory_layout_writes_the_files_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            dz = os.path.join(tmp, "x.dsl.dz")
            self.write_dz(dz, "[s]cached.ogg[/s]\n")
            with open(os.path.join(self.cache_dir(tmp), "cached.ogg"), "wb") as f:
                f.write(b"OGGDATA")

            with self.captured():
                self.assertEqual(TOOL.bundle_audio(self.bundle_args(
                    tmp, dz, "--audio-tar", os.path.join(tmp, "absent.tar"),
                    "--audio-layout", "dir")), 0)
            self.assertTrue(
                os.path.isfile(os.path.join(tmp, "x.dsl.files", "cached.ogg"))
            )
            self.assertFalse(os.path.exists(os.path.join(tmp, "x.dsl.files.zip")))

    def test_rebuild_with_a_local_archive_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            dz = os.path.join(tmp, "x.dsl.dz")
            self.write_dz(dz, "[s]offline.ogg[/s]\n")
            tar = os.path.join(tmp, "audios.tar")
            make_tar(tar, ["audios/offline.ogg"])

            original = TOOL._open_with_retries

            def blocked(*args, **kwargs):
                raise AssertionError("the network was used")

            TOOL._open_with_retries = blocked
            self.addCleanup(setattr, TOOL, "_open_with_retries", original)
            with self.captured():
                self.assertEqual(
                    TOOL.bundle_audio(self.bundle_args(tmp, dz, "--audio-tar", tar)), 0)

    def test_rebuild_needs_a_snapshot_marker_for_the_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            dz = os.path.join(tmp, "x.dsl.dz")
            self.write_dz(dz, "[s]a.ogg[/s]\n")
            args = TOOL.bundle_audio_parser().parse_args([dz])
            with self.assertRaises(SystemExit):
                TOOL.bundle_audio(args)


class CardQualityTests(unittest.TestCase):
    """One card per headword, and no definition-less or dangling cards."""

    def build(self, tmp, records, *extra):
        path = os.path.join(tmp, "in.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")
        args = TOOL.build_parser().parse_args([
            "--source-lang", "en", "--jsonl", path, "--out-dir", tmp,
            "--no-audio", "--cache-dir", os.path.join(tmp, "cache"), *extra,
        ])
        return TOOL.build(args)

    def text(self, tmp):
        return read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))

    def test_non_adjacent_records_merge_into_one_card(self):
        # The snapshot is not word-sorted, so a headword's records can be split;
        # they must still become a single card.
        with tempfile.TemporaryDirectory() as tmp:
            report = self.build(tmp, [
                {"word": "zebra", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["Striped animal."]}]},
                {"word": "apple", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["A fruit."]}]},
                {"word": "zebra", "lang_code": "en", "pos": "adj",
                 "senses": [{"glosses": ["Striped."]}]},
            ])
            text = self.text(tmp)
            self.assertEqual(headword_lines(text).count("zebra"), 1)
            self.assertIn("Striped animal.", text)
            self.assertIn("Striped.", text)
            self.assertEqual(report.merged_headwords, 1)

    def test_a_definition_less_card_with_no_link_is_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.build(tmp, [
                {"word": "solid", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["Firm."]}]},
                {"word": "hollowish", "lang_code": "en", "pos": "adj",
                 "senses": [{"tags": ["obsolete"]}]},
            ])
            heads = headword_lines(self.text(tmp))
            self.assertIn("solid", heads)
            self.assertNotIn("hollowish", heads)
            self.assertEqual(report.dropped_cards, 1)

    def test_a_linked_definition_less_card_is_kept(self):
        # Dropping the stub would leave the link to it dangling, so it stays.
        with tempfile.TemporaryDirectory() as tmp:
            report = self.build(tmp, [
                {"word": "alpha", "lang_code": "en", "pos": "noun",
                 "senses": [{"glosses": ["First."]}],
                 "related": [{"word": "beta"}]},
                {"word": "beta", "lang_code": "en", "pos": "adj",
                 "senses": [{"tags": ["obsolete"]}]},
            ])
            text = self.text(tmp)
            self.assertIn("beta", headword_lines(text))
            self.assertIn("[ref]beta[/ref]", text)
            self.assertEqual(report.dropped_cards, 0)

    def test_a_link_to_an_absent_headword_is_left_as_text(self):
        body, unlinked = TOOL.unlink_absent_refs(
            "See [ref]ghost[/ref] and [ref]real[/ref].", {"real"}
        )
        self.assertEqual(body, "See ghost and [ref]real[/ref].")
        self.assertEqual(unlinked, 1)

    def test_unlinking_a_nested_link_leaves_plain_text(self):
        body, unlinked = TOOL.unlink_absent_refs("[ref][ref]ghost[/ref][/ref]", set())
        self.assertEqual(body, "ghost")
        self.assertGreaterEqual(unlinked, 1)

    def test_a_target_named_by_two_relations_is_linked_once(self):
        # alt_of and form_of both name "ho": the second wrap used to land inside
        # the first, producing [ref][ref]ho[/ref][/ref].
        escaped = TOOL.escape_dsl("Alternative form of [[ho]], ho, ho.")
        sense = {"alt_of": [{"word": "ho"}], "form_of": [{"word": "ho"}]}
        out = TOOL._link_form_targets(escaped, sense, {"ho"}, "ho ho")
        self.assertIn("[ref]ho[/ref]", out)
        self.assertEqual(out.count("[ref]"), 1)
        self.assertEqual(out.count("[/ref]"), 1)


class ArchaicExampleTests(unittest.TestCase):
    """An archaic sense may fall back to an archaic example; a modern one may not."""

    def examples(self, raw, word, allow_archaic):
        return TOOL._sense_examples(raw, word, (), allow_archaic)

    def test_a_modern_sense_drops_an_archaic_example(self):
        self.assertEqual(self.examples(["I haue worke in hand."], "work", False), [])

    def test_an_archaic_sense_falls_back_to_an_archaic_example(self):
        out = self.examples(["I haue worke in hand."], "work", True)
        self.assertEqual(len(out), 1)
        self.assertIn("haue", out[0])

    def test_an_archaic_sense_prefers_a_readable_example(self):
        out = self.examples(
            ["I haue worke in hand.", "My work involves travel."], "work", True
        )
        self.assertEqual(len(out), 1)
        self.assertIn("travel", out[0])

    def test_a_bookkeeping_example_is_dropped_even_when_archaic(self):
        self.assertEqual(self.examples(["Citations:work."], "work", True), [])

    def test_the_fallback_reaches_the_rendered_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "in.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for record in (
                    {"word": "oldword", "lang_code": "en", "pos": "adj",
                     "senses": [{"glosses": ["Old use."], "tags": ["obsolete"],
                                 "examples": [{"text": "I haue oldword in hand."}]}]},
                    {"word": "modword", "lang_code": "en", "pos": "noun",
                     "senses": [{"glosses": ["Modern."],
                                 "examples": [{"text": "I haue modword in hand."}]}]},
                ):
                    f.write(json.dumps(record) + "\n")
            TOOL.build(TOOL.build_parser().parse_args([
                "--source-lang", "en", "--jsonl", path, "--out-dir", tmp,
                "--no-audio", "--cache-dir", os.path.join(tmp, "cache"),
            ]))
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            old = text.split("oldword", 1)[1].split("modword", 1)[0]
            mod = text.split("modword", 1)[1]
            # the obsolete sense fell back to its archaic quotation
            self.assertIn("[ex]", old)
            # the modern sense did not: it may not show an archaic example
            self.assertNotIn("[ex]", mod)


class AnnotationTests(unittest.TestCase):
    """The about headword names the dictionary; a sibling .ann carries it."""

    def args(self, tmp, *extra):
        path = os.path.join(tmp, "in.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "word": "solid", "lang_code": "en", "pos": "noun",
                "senses": [{"glosses": ["Firm."]}],
            }) + "\n")
        return TOOL.build_parser().parse_args([
            "--source-lang", "en", "--jsonl", path, "--out-dir", tmp,
            "--no-audio", "--cache-dir", os.path.join(tmp, "cache"), *extra,
        ])

    def test_about_headword_names_the_dictionary(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(tmp))
            text = read_dz(os.path.join(tmp, "kaikki-en.dsl.dz"))
            self.assertIn("About kaikki-en", text.splitlines())
            self.assertIn("\t[com]Entries: 1[/com]", text)

    def test_about_headword_uses_the_chosen_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(tmp, "--name", "webster"))
            text = read_dz(os.path.join(tmp, "webster.dsl.dz"))
            self.assertIn("About webster", text.splitlines())

    def test_annotation_sits_beside_the_dictionary(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(tmp))
            with open(os.path.join(tmp, "kaikki-en.ann"), encoding="utf-8") as f:
                content = f.read()
            self.assertIn("kaikki-en", content)
            self.assertIn("CC BY-SA 4.0", content)
            self.assertIn("Wiktionary", content)
            self.assertIn("derivative work", content)
            self.assertIn("Entries: 1", content)

    def test_title_is_separate_from_the_file_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(
                tmp, "--name", "au_kaikki_en-en", "--title", "Aurelex Kaikki En"
            ))
            # files use the output name
            self.assertTrue(os.path.isfile(
                os.path.join(tmp, "au_kaikki_en-en.dsl.dz")))
            # the metadata, the about headword and the description use the title
            text = read_dz(os.path.join(tmp, "au_kaikki_en-en.dsl.dz"))
            self.assertIn('#NAME "Aurelex Kaikki En"', text)
            self.assertIn("About Aurelex Kaikki En", text.splitlines())
            with open(os.path.join(tmp, "au_kaikki_en-en.ann"), encoding="utf-8") as f:
                self.assertIn("Aurelex Kaikki En: a Wiktionary-based", f.read())

    def test_annotation_is_written_even_when_the_bundle_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            TOOL.build(self.args(tmp))
            ann = os.path.join(tmp, "kaikki-en.ann")
            os.remove(ann)
            with contextlib.redirect_stderr(io.StringIO()):
                TOOL.build(self.args(tmp, "--reuse-bundle"))
            self.assertTrue(os.path.isfile(ann))

    def test_metadata_names_the_language_in_english(self):
        # a non-English edition names the language in its own language ("Русский")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "in.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "word": "собака", "lang_code": "ru", "lang": "Русский",
                    "pos": "noun", "senses": [{"glosses": ["dog"]}],
                }) + "\n")
            TOOL.build(TOOL.build_parser().parse_args([
                "--source-lang", "ru", "--jsonl", path, "--out-dir", tmp,
                "--no-audio", "--cache-dir", os.path.join(tmp, "cache"),
            ]))
            text = read_dz(os.path.join(tmp, "kaikki-ru.dsl.dz"))
            self.assertIn('#INDEX_LANGUAGE "Russian"', text)
            self.assertIn('#CONTENTS_LANGUAGE "Russian"', text)
            self.assertIn("a Wiktionary-based dictionary", text)
            with open(os.path.join(tmp, "kaikki-ru.ann"), encoding="utf-8") as f:
                self.assertIn("Language: Russian (ru)", f.read())

    def test_an_unlisted_language_falls_back_to_its_source_name(self):
        self.assertEqual(TOOL._language_name({"lang": "Klingon"}, "tlh"), "Klingon")
        self.assertEqual(TOOL._language_name(None, "tlh"), "TLH")


class ReuseBundleTests(unittest.TestCase):
    """--reuse-bundle renders the dictionary and reuses the existing bundle."""

    def args(self, tmp, out, *extra):
        tar = os.path.join(tmp, "audios.tar")
        if not os.path.exists(tar):
            make_tar(tar, [
                "audios/En-au-limitword.ogg",
                "audios/En-uk-limitword.ogg",
                "audios/En-us-limitword-gone1.ogg",
            ])
        return TOOL.build_parser().parse_args([
            "--source-lang", "en", "--jsonl", AUDIO_LIMIT_FIXTURE,
            "--out-dir", out, "--audio-tar", tar, "--audio-per-word", "3",
            "--cache-dir", os.path.join(tmp, "cache"), "--no-audio-download",
            *extra,
        ])

    @contextlib.contextmanager
    def captured(self):
        stream = io.StringIO()
        original = sys.stderr
        sys.stderr = stream
        try:
            yield stream
        finally:
            sys.stderr = original

    def test_reusing_a_complete_bundle_leaves_it_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            TOOL.build(self.args(tmp, out))
            zip_path = os.path.join(out, "kaikki-en.dsl.files.zip")
            with open(zip_path, "rb") as f:
                before = f.read()

            with self.captured() as out_err:
                TOOL.build(self.args(tmp, out, "--reuse-bundle"))
            with open(zip_path, "rb") as f:
                self.assertEqual(f.read(), before)
            self.assertIn("reused resource bundle", out_err.getvalue())

    def test_a_reused_bundle_missing_a_resource_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            # A first build with audio disabled leaves a bundle of icons only.
            TOOL.build(self.args(tmp, out, "--no-audio"))
            # The next build references audio the reused bundle does not hold.
            with self.captured() as out_err:
                TOOL.build(self.args(tmp, out, "--reuse-bundle"))
            message = out_err.getvalue()
            self.assertIn("lacks", message)
            self.assertIn("referenced resource(s)", message)

    def test_reuse_without_a_bundle_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            with self.captured() as out_err:
                TOOL.build(self.args(tmp, out, "--reuse-bundle"))
            self.assertIn("no resource bundle", out_err.getvalue())


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

    def test_japanese_labels_are_in_japanese(self):
        ja = TOOL.get_lang_profile("ja")
        self.assertEqual(ja.pos_labels.get("noun"), "名詞")
        self.assertEqual(ja.pos_labels.get("adj_noun"), "形容動詞")
        # a reading is labelled as a reading, and the conjugation-class row tag
        # that every inflected form carries does not clutter the label
        self.assertEqual(
            ja.label_tags(("transliteration", "kan-on", "joyo")), "読み, 漢音, 常用"
        )
        self.assertEqual(ja.label_tags(("sa-row", "imperfective")), "未然形")
        self.assertEqual(ja.sense_short_tags.get("figuratively"), "比喩")

    def test_a_japanese_reading_survives_as_a_form(self):
        record = {
            "word": "青", "pos": "noun",
            "forms": [{"form": "セイ", "tags": ["transliteration", "kan-on", "joyo"]}],
        }
        self.assertEqual(
            TOOL.collect_profile_forms(record, TOOL.get_lang_profile("ja")),
            ["セイ (読み, 漢音, 常用)"],
        )

    def test_japanese_has_no_audio_so_no_archive_is_fetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            jsonl = os.path.join(tmp, "ja.jsonl")
            with open(jsonl, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "word": "青", "lang_code": "ja", "pos": "noun",
                    "senses": [{"glosses": ["色の一つ。"]}],
                }) + "\n")
            args = TOOL.build_parser().parse_args([
                "--source-lang", "ja", "--jsonl", jsonl,
                "--out-dir", os.path.join(tmp, "out"),
            ])
            args.cache_dir = os.path.join(tmp, "cache")
            original = TOOL._open_with_retries

            def blocked(*_a, **_k):
                raise AssertionError("the network was used")

            TOOL._open_with_retries = blocked
            self.addCleanup(setattr, TOOL, "_open_with_retries", original)
            # the profile declares no recordings, so no audio archive is opened
            report = TOOL.build(args)
            self.assertEqual(report.audio_found, 0)
            self.assertEqual(report.missing_audio, 0)

    def test_russian_profile_keeps_case_and_aspect(self):
        ru = TOOL.get_lang_profile("ru")
        # the profile is registered, so no fallback is used
        self.assertIs(ru, TOOL.LANG_PROFILES["ru"])
        self.assertTrue(ru.form_qualifies(("genitive", "singular")))
        self.assertTrue(ru.form_qualifies(("imperfective", "past", "feminine")))
        # table machinery, the canonical lemma entry and transliterations are not
        # inflected forms
        self.assertFalse(ru.form_qualifies(("table-tags",)))
        self.assertFalse(ru.form_qualifies(("canonical", "singular")))
        self.assertFalse(ru.form_qualifies(("romanization",)))
        # a derived lemma (a relational adjective, a diminutive) is not a form
        self.assertFalse(ru.form_qualifies(("relational",)))
        self.assertFalse(ru.form_qualifies(("diminutive",)))

    def test_russian_labels_use_the_conventional_abbreviations(self):
        ru = TOOL.get_lang_profile("ru")
        self.assertEqual(ru.label_tags(("genitive", "singular")), "род., ед.")
        self.assertEqual(
            ru.label_tags(("third-person", "singular", "present")), "3-е л., наст."
        )
        self.assertEqual(ru.label_tags(("imperfective",)), "несов.")

    def test_russian_sense_noise_drops_indicative_but_keeps_aspect(self):
        ru = TOOL.get_lang_profile("ru")
        self.assertIn("indicative", ru.sense_noise_tags)
        self.assertNotIn("imperfective", ru.sense_noise_tags)

    def test_a_form_with_no_recognised_label_is_dropped(self):
        record = {
            "word": "w", "pos": "noun",
            "forms": [
                {"form": "bare", "tags": ["adverb"]},
                {"form": "wfs", "tags": ["genitive", "singular"]},
            ],
        }
        self.assertEqual(
            TOOL.collect_profile_forms(record, TOOL.get_lang_profile("ru")),
            ["wfs (род., ед.)"],
        )

    def test_english_part_of_speech_is_unchanged(self):
        self.assertEqual(TOOL.get_lang_profile("en").pos_labels, {})

    def test_russian_pos_and_sense_labels_render_in_russian(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "in.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "word": "собака", "lang_code": "ru", "lang": "Russian",
                    "pos": "noun",
                    "senses": [{"glosses": ["собака."], "tags": ["colloquial"]}],
                }) + "\n")
            TOOL.build(TOOL.build_parser().parse_args([
                "--source-lang", "ru", "--jsonl", path, "--out-dir", tmp,
                "--no-audio", "--cache-dir", os.path.join(tmp, "cache"),
            ]))
            text = read_dz(os.path.join(tmp, "kaikki-ru.dsl.dz"))
            self.assertIn("[p]сущ.[/p]", text)
            self.assertIn("(разг.)", text)

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
        # the renderer follows the profile object, not the language code: the
        # same tag reads differently in English and Japanese
        self.assertEqual(
            TOOL.collect_profile_forms(record, TOOL.get_lang_profile("ja")),
            ["f (過去)"],
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
        self.assertEqual(groups, [("", [("A penis.", [], False)])])

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

    def test_group_children_survive_a_heading_rendered_differently(self):
        # the children are stored under the raw parent gloss but printed under
        # the rendered heading; when rendering changes the text (whitespace is
        # trimmed here, and it is escaped, stripped of a relation prefix or
        # linked elsewhere) the two must still be joined up
        senses = [
            {"glosses": ["The fourth digestive compartment of a cow:  ",
                         "The lining of said compartment, as a foodstuff."]},
        ]
        groups = TOOL._group_senses(senses, self.EN)
        self.assertEqual(len(groups), 1)
        heading, children = groups[0]
        self.assertEqual(heading, "The fourth digestive compartment of a cow:")
        self.assertEqual(sense_texts(children), [
            "The lining of said compartment, as a foodstuff.",
        ])

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

    def test_over_long_example_keeps_the_sentence_with_the_headword(self):
        # The word's own sentence sits past the bound; keeping the head of the
        # quote would show the lead-in and drop the words that prove the sense.
        text = ("Женя Баринов часто говаривал: «Сильным характером отважный мой "
                "дядя обязан своему деду, В. В. Баринову, который в бытность "
                "свою личным денщиком барона Маннергейма на коне перевалил "
                "Шишалдинский хребет и вышел к озеру Хан».")
        shortened = TOOL._truncate_example(text, "Хан")
        self.assertIn("к озеру Хан", shortened)
        self.assertNotIn("говаривал", shortened)

    def test_over_long_example_without_a_break_windows_around_the_headword(self):
        text = "aaa " * 40 + "target " + "bbb " * 40
        shortened = TOOL._truncate_example(text, "target", limit=40)
        self.assertIn("target", shortened)
        self.assertTrue(shortened.startswith("…"))
        self.assertTrue(shortened.endswith("…"))

    def test_over_long_example_without_a_headword_falls_back_to_a_head_cut(self):
        shortened = TOOL._truncate_example("word " * 80, word="absent", limit=50)
        self.assertTrue(shortened.endswith(" …"))
        self.assertTrue(shortened[:-2].endswith("word"))

    def test_a_cjk_full_stop_bounds_an_example(self):
        # Japanese ends a sentence with 。, not '.', so without it the whole
        # quotation counts as one sentence and the window fallback is used.
        text = "これは前置きの長い文章です。" * 25 + "この文には羊頭狗肉が入っています。"
        self.assertEqual(
            TOOL._truncate_example(text, "羊頭狗肉"),
            "… この文には羊頭狗肉が入っています。",
        )

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

    def fake_rate_limited(self, sleeps, retry_after=None):
        """A 429 on the first attempt, then success; records the backoff waits."""
        attempts = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                return b""

        def fake_urlopen(request, timeout):
            attempts.append(request.full_url)
            if len(attempts) == 1:
                headers = {"Retry-After": retry_after} if retry_after else {}
                raise urllib.error.HTTPError(
                    request.full_url, 429, "Too many requests", headers, None
                )
            return FakeResponse()

        original = TOOL.urllib.request.urlopen
        original_sleep = TOOL.time.sleep
        TOOL.urllib.request.urlopen = fake_urlopen

        def record(seconds):
            sleeps.append(seconds)
            # _throttle measures against a real clock, which the mocked sleep
            # does not advance; without this the next attempt would throttle too
            TOOL._last_request_time = 0.0

        TOOL.time.sleep = record

        def restore():
            TOOL.urllib.request.urlopen = original
            TOOL.time.sleep = original_sleep

        # a throttle gap left by an earlier test would show up as a first sleep
        TOOL._last_request_time = 0.0
        return attempts, restore

    def test_retry_after_is_honoured_over_the_computed_backoff(self):
        # Wikimedia's cooldown is the number it will actually hold us to, so a
        # short guess only earns another 429
        sleeps = []
        attempts, restore = self.fake_rate_limited(sleeps, retry_after="45")
        try:
            with TOOL._open_with_retries("https://example.invalid/x", 5, spacing=1.0):
                pass
        finally:
            restore()
        self.assertEqual(len(attempts), 2)
        self.assertEqual(sleeps, [45.0])

    def test_retry_after_cannot_exceed_the_backoff_ceiling(self):
        sleeps = []
        attempts, restore = self.fake_rate_limited(sleeps, retry_after="86400")
        try:
            with TOOL._open_with_retries(
                "https://example.invalid/x", 5, spacing=1.0, max_backoff=30.0
            ):
                pass
        finally:
            restore()
        self.assertEqual(len(attempts), 2)
        self.assertEqual(sleeps, [30.0])

    def test_an_unparseable_retry_after_falls_back_to_exponential_backoff(self):
        sleeps = []
        attempts, restore = self.fake_rate_limited(sleeps, retry_after="Wed, 21 Oct")
        try:
            with TOOL._open_with_retries("https://example.invalid/x", 5, spacing=1.0):
                pass
        finally:
            restore()
        self.assertEqual(len(attempts), 2)
        self.assertEqual(sleeps, [1.0])

    def test_spacing_is_the_floor_even_when_retry_after_is_shorter(self):
        sleeps = []
        attempts, restore = self.fake_rate_limited(sleeps, retry_after="0")
        try:
            with TOOL._open_with_retries("https://example.invalid/x", 5, spacing=2.0):
                pass
        finally:
            restore()
        self.assertEqual(len(attempts), 2)
        self.assertEqual(sleeps, [2.0])


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


def dictzip_chunks(blob):
    """(chunk_length, chunk_count, [compressed chunk bytes]) from a dictzip .dz."""
    if blob[:2] != b"\x1f\x8b":
        raise ValueError("not gzip")
    if not blob[3] & 0x04:
        raise ValueError("FEXTRA not set")
    xlen = struct.unpack("<H", blob[10:12])[0]
    extra = blob[12:12 + xlen]
    if extra[:2] != b"RA":
        raise ValueError("no RA subfield")
    _ver, chlen, chcnt = struct.unpack("<HHH", extra[4:10])
    sizes = struct.unpack("<%dH" % chcnt, extra[10:10 + 2 * chcnt])
    off = 12 + xlen
    chunks = []
    for size in sizes:
        chunks.append(blob[off:off + size])
        off += size
    return chlen, chcnt, chunks


class DictzipTests(unittest.TestCase):
    """The dictzip writer must emit independently inflatable chunks.

    The engine random-accesses a .dsl.dz: it seeks to a chunk and inflates just
    that chunk. That works only when every chunk was terminated with a FULL flush,
    which resets the deflate history. A sync flush keeps the history, so a later
    chunk's back-references reach into an earlier chunk and inflating it alone
    fails with "invalid distance too far back" - exactly what a reported
    multi-chunk dictionary did on device.
    """

    def test_every_chunk_inflates_independently(self):
        payload = (b"the quick brown fox jumps over the lazy dog. " * 2000) + bytes(range(256)) * 300
        chlen, chcnt, chunks = dictzip_chunks(TOOL.make_dictzip(payload))
        self.assertEqual(chlen, 16384)
        self.assertGreater(chcnt, 2)
        total = 0
        for i, chunk in enumerate(chunks):
            # Cold-start inflate. With a sync flush this raises for i > 0.
            raw = zlib.decompressobj(-zlib.MAX_WBITS).decompress(chunk)
            if i < chcnt - 1:
                self.assertGreater(len(raw), 0, f"chunk {i} inflated to nothing")
            total += len(raw)
        self.assertEqual(total, len(payload))

    def test_stream_round_trips(self):
        payload = (b"abcdefgh" * 9000) + b"tail"
        self.assertEqual(gzip.decompress(TOOL.make_dictzip(payload)), payload)


if __name__ == "__main__":
    unittest.main()
