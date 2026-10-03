#!/usr/bin/env python3
"""Tests for scripts/build-catalog.py (the catalogtool package).

Run with:  python -m unittest discover -s scripts/tests
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import catalogtool  # noqa: E402
from catalogtool import cli  # noqa: E402

BASE = "https://github.com/rg-software/aurelex/releases/download"
TAG = "catalog-data"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_with(files, entry_id="kaikki-en", names=None):
    """A minimal one-entry source document."""
    return {
        "releaseTag": TAG,
        "baseUrl": BASE,
        "entries": [
            {
                "id": entry_id,
                "name": "Aurelex Kaikki English",
                "names": names or {"ru": "Aurelex Kaikki английский"},
                "langFrom": "en",
                "langTo": "en",
                "attribution": "Wiktionary contributors, CC BY-SA 4.0 (via kaikki.org)",
                "license": "CC-BY-SA-4.0",
                "files": files,
            }
        ],
    }


def dict_file(name, required=True):
    return {"role": "dictionary", "required": required, "name": name}


def res_file(name, required=False):
    return {"role": "resources", "required": required, "name": name}


class BuildTest(unittest.TestCase):
    def test_file_url(self):
        self.assertEqual(
            catalogtool.file_url(BASE, TAG, "a.dsl.dz"),
            f"{BASE}/{TAG}/a.dsl.dz",
        )
        self.assertEqual(
            catalogtool.file_url(BASE + "/", "/" + TAG + "/", "a.dsl.dz"),
            f"{BASE}/{TAG}/a.dsl.dz",
        )

    def test_sha256_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x")
            data = b"the quick brown fox" * 1000
            with open(p, "wb") as f:
                f.write(data)
            self.assertEqual(catalogtool.sha256_file(p, chunk=7), sha256(data))

    def test_build_computes_size_digest_and_url(self):
        with tempfile.TemporaryDirectory() as d:
            data = b"dictionary bytes"
            with open(os.path.join(d, "au_kaikki_en-en.dsl.dz"), "wb") as f:
                f.write(data)
            files = [dict_file("au_kaikki_en-en.dsl.dz")]
            catalog = catalogtool.build_catalog(source_with(files), d, updated="2026-10-03")

            self.assertEqual(catalog["schemaVersion"], 1)
            self.assertEqual(catalog["updated"], "2026-10-03")
            f0 = catalog["entries"][0]["files"][0]
            self.assertEqual(f0["name"], "au_kaikki_en-en.dsl.dz")
            self.assertEqual(f0["sizeBytes"], len(data))
            self.assertEqual(f0["sha256"], sha256(data))
            self.assertEqual(f0["url"], f"{BASE}/{TAG}/au_kaikki_en-en.dsl.dz")
            self.assertEqual(catalog["entries"][0]["names"]["ru"],
                             "Aurelex Kaikki английский")

    def test_build_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as d:
            files = [dict_file("nope.dsl.dz")]
            with self.assertRaises(catalogtool.CatalogError):
                catalogtool.build_catalog(source_with(files), d)

    def test_build_empty_file_raises(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "empty.dsl.dz"), "wb").close()
            with self.assertRaises(catalogtool.CatalogError):
                catalogtool.build_catalog(source_with([dict_file("empty.dsl.dz")]), d)

    def test_build_over_asset_cap_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "big.dsl.dz"), "wb") as f:
                f.write(b"0123456789")
            with self.assertRaises(catalogtool.CatalogError):
                catalogtool.build_catalog(
                    source_with([dict_file("big.dsl.dz")]), d, max_asset_bytes=5
                )


class ValidateTest(unittest.TestCase):
    def _err(self, source):
        with self.assertRaises(catalogtool.CatalogError):
            catalogtool.validate_source(source)

    def test_duplicate_id(self):
        s = source_with([dict_file("a.dsl.dz")])
        s["entries"].append(dict(s["entries"][0]))
        self._err(s)

    def test_bad_role(self):
        s = source_with([{"role": "audio", "required": True, "name": "a.dsl.dz"}])
        self._err(s)

    def test_needs_required_dictionary(self):
        s = source_with([res_file("a.files.zip")])
        self._err(s)
        # optional dictionary alone is not enough either
        s = source_with([dict_file("a.dsl.dz", required=False)])
        self._err(s)

    def test_bad_basename(self):
        s = source_with([dict_file("../evil.dsl.dz")])
        self._err(s)

    def test_duplicate_file_name(self):
        s = source_with([dict_file("a.dsl.dz"), dict_file("a.dsl.dz")])
        self._err(s)

    def test_non_https_base(self):
        s = source_with([dict_file("a.dsl.dz")])
        s["baseUrl"] = "http://example.com"
        self._err(s)

    def test_duplicate_entry_name(self):
        s = source_with([dict_file("a.dsl.dz")])
        second = dict(s["entries"][0])
        second["id"] = "kaikki-en-2"
        second["files"] = [dict_file("b.dsl.dz")]
        s["entries"].append(second)
        self._err(s)


class ImportRoundTripTest(unittest.TestCase):
    def test_import_drops_derived_and_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            data = b"payload"
            with open(os.path.join(d, "au_kaikki_en-en.dsl.dz"), "wb") as f:
                f.write(data)
            src = source_with([dict_file("au_kaikki_en-en.dsl.dz")])
            built = catalogtool.build_catalog(src, d, updated="2026-10-03")

            imported = catalogtool.import_catalog(built, release_tag=TAG, base_url=BASE)
            self.assertEqual(imported["releaseTag"], TAG)
            self.assertEqual(imported["baseUrl"], BASE)
            for f in imported["entries"][0]["files"]:
                self.assertNotIn("url", f)
                self.assertNotIn("sizeBytes", f)
                self.assertNotIn("sha256", f)
            self.assertEqual(imported["entries"], src["entries"])

            # Rebuilding from the imported source reproduces the same document.
            again = catalogtool.build_catalog(imported, d, updated="2026-10-03")
            self.assertEqual(again, built)


class DiffTest(unittest.TestCase):
    def _catalog(self, entry_id, files):
        return {
            "schemaVersion": 1,
            "updated": "2026-10-03",
            "entries": [{"id": entry_id, "name": "N", "langFrom": "en", "langTo": "en",
                         "files": files}],
        }

    def _f(self, name, sha, size=10):
        return {"role": "dictionary", "required": True, "name": name,
                "url": f"{BASE}/{TAG}/{name}", "sizeBytes": size, "sha256": sha}

    def test_classifies_new_changed_unchanged(self):
        published = self._catalog("kaikki-en", [self._f("a.dsl.dz", "1" * 64),
                                                self._f("b.dsl.dz", "2" * 64)])
        built = self._catalog("kaikki-en", [self._f("a.dsl.dz", "1" * 64),
                                            self._f("b.dsl.dz", "9" * 64),
                                            self._f("c.dsl.dz", "3" * 64)])
        r = catalogtool.diff_catalogs(built, published)
        self.assertEqual(r["unchanged_files"], ["a.dsl.dz"])
        self.assertEqual(r["changed_files"], ["b.dsl.dz"])
        self.assertEqual(r["new_files"], ["c.dsl.dz"])
        self.assertEqual(r["removed_files"], [])
        self.assertEqual(r["identity_violations"], [])

    def test_rename_on_existing_entry_is_a_violation(self):
        published = self._catalog("kaikki-en", [self._f("old.dsl.dz", "1" * 64)])
        built = self._catalog("kaikki-en", [self._f("new.dsl.dz", "1" * 64)])
        r = catalogtool.diff_catalogs(built, published)
        self.assertEqual(len(r["identity_violations"]), 1)
        self.assertIn("old.dsl.dz", r["identity_violations"][0])

    def test_moved_file_is_a_violation(self):
        published = self._catalog("kaikki-en", [self._f("a.dsl.dz", "1" * 64)])
        built = self._catalog("kaikki-en", [])
        built["entries"][0]["files"] = []
        built["entries"].append({
            "id": "other", "name": "N", "langFrom": "en", "langTo": "en",
            "files": [self._f("a.dsl.dz", "1" * 64)],
        })
        r = catalogtool.diff_catalogs(built, published)
        self.assertTrue(any("moved" in v for v in r["identity_violations"]))


class ValidateCatalogTest(unittest.TestCase):
    def _valid(self):
        return {
            "schemaVersion": 1,
            "entries": [{
                "id": "kaikki-en", "name": "N", "langFrom": "en", "langTo": "en",
                "files": [{
                    "role": "dictionary", "required": True, "name": "a.dsl.dz",
                    "url": f"{BASE}/{TAG}/a.dsl.dz", "sizeBytes": 5,
                    "sha256": "a" * 64,
                }],
            }],
        }

    def test_valid_catalog_passes(self):
        catalogtool.validate_catalog(self._valid())

    def test_missing_sha_fails(self):
        c = self._valid()
        del c["entries"][0]["files"][0]["sha256"]
        with self.assertRaises(catalogtool.CatalogError):
            catalogtool.validate_catalog(c)

    def test_bad_url_fails(self):
        c = self._valid()
        c["entries"][0]["files"][0]["url"] = "http://x/a"
        with self.assertRaises(catalogtool.CatalogError):
            catalogtool.validate_catalog(c)

    def test_bad_size_fails(self):
        c = self._valid()
        c["entries"][0]["files"][0]["sizeBytes"] = 0
        with self.assertRaises(catalogtool.CatalogError):
            catalogtool.validate_catalog(c)


class CliTest(unittest.TestCase):
    def test_build_then_diff_returns_two_on_violation(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "au_kaikki_en-en.dsl.dz"), "wb") as f:
                f.write(b"x")
            src_path = os.path.join(d, "source.json")
            cat_path = os.path.join(d, "catalog.json")
            with open(src_path, "w", encoding="utf-8") as f:
                json.dump(source_with([dict_file("au_kaikki_en-en.dsl.dz")]), f)

            rc = cli.main(["build", "--source", src_path, "--files-dir", d,
                           "--out", cat_path, "--updated", "2026-10-03"])
            self.assertEqual(rc, 0)
            with open(cat_path, encoding="utf-8") as f:
                built = json.load(f)
            self.assertTrue(built["entries"][0]["files"][0]["sha256"])

            # A published catalog whose entry has a differently named file is a
            # rename violation.
            published = {
                "schemaVersion": 1,
                "entries": [{"id": "kaikki-en", "name": "N", "langFrom": "en", "langTo": "en",
                             "files": [{"role": "dictionary", "required": True,
                                        "name": "gone.dsl.dz", "url": "https://e/x",
                                        "sizeBytes": 1, "sha256": "0" * 64}]}],
            }
            pub_path = os.path.join(d, "published.json")
            with open(pub_path, "w", encoding="utf-8") as f:
                json.dump(published, f)
            rc = cli.main(["diff", pub_path, "--catalog", cat_path])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
