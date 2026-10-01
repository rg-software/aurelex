#!/usr/bin/env python3
"""Build an importable ABBYY Lingvo DSL dictionary from a pinned kaikki.org
Wiktionary (wiktextract) snapshot for one language.

The implementation lives in the ``kaikki`` package beside this file; this script
is the launcher, kept so every documented command
(``python scripts/kaikki-to-dsl.py ...``) keeps working unchanged.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kaikki.cli import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
