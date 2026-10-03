#!/usr/bin/env python3
"""Build and compare the remote dictionary catalog.

The implementation lives in the ``catalogtool`` package beside this file; this
script is the launcher, kept so the documented command
(``python scripts/build-catalog.py ...``) is stable. See
``docs/REMOTE-CATALOG.md`` for the maintainer workflow.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalogtool.cli import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
