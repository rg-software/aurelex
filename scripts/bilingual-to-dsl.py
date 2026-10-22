#!/usr/bin/env python3
"""Build offline En→Ru translation DSL dictionaries from WordNet-family
equivalents and Tatoeba example sentences.

The implementation lives in the ``bilingual`` package beside this file; this
script is the launcher, kept so every documented command
(``python scripts/bilingual-to-dsl.py ...``) keeps working unchanged.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bilingual.cli import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
