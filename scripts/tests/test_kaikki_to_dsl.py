#!/usr/bin/env python3
"""Tests for scripts/kaikki-to-dsl.py.

Run with:  python -m unittest discover -s scripts/tests
"""

import gzip
import importlib.util
import io
import os
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
TOOL_PATH = os.path.join(SCRIPTS, "kaikki-to-dsl.py")
FIXTURE = os.path.join(HERE, "fixtures", "sample-en.jsonl")


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


if __name__ == "__main__":
    unittest.main()
