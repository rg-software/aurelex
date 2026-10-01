"""dictzip: reuse the writer from make-example-dicts.py (single source of truth)"""

from __future__ import annotations

import gzip
import importlib.util
import os

from .constants import _SCRIPT_DIR


def _load_make_example_dicts():
    path = os.path.join(_SCRIPT_DIR, "make-example-dicts.py")
    spec = importlib.util.spec_from_file_location("aurelex_make_example_dicts", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load dictzip writer from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_MED = _load_make_example_dicts()
make_dictzip = _MED.make_dictzip

def encode_dsl(text: str) -> bytes:
    """UTF-8 with BOM; the DSL reader detects the encoding from it."""
    return b"\xef\xbb\xbf" + text.encode("utf-8")

def read_dictzip(path: str) -> str:
    """Read a ``.dsl.dz`` back to text.

    A dictzip is a gzip stream with an extra header, so a full read is just a
    gzip decompress; the inverse of ``make_dictzip(encode_dsl(...))``.
    """
    with open(path, "rb") as f:
        raw = gzip.decompress(f.read())
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8")
