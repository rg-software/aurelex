"""Shared constants for the bilingual dictionary builder."""

from __future__ import annotations

import os

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DSL tags this builder emits. Subset of the reader's tag set; anything else is
# a bug, not a fallback.
READER_TAGS = {"p", "m", "trn", "ex", "com", "t"}

# Per-sense equivalent cap and per-sense example count (spec: at most one
# example pair per sense; length ranks, never filters).
EQUIVALENTS_PER_SENSE = 8
EXAMPLES_PER_SENSE = 1
SYNONYMS_PER_SENSE = 3

# Preferred example length; longer pairs still ship when they are all a sense
# has (length is a ranking signal, not a filter).
PREFERRED_EXAMPLE_LENGTH = 140

# Tatoeba headword cap used by the Dict B funnel probe.
EXAMPLES_PER_HEADWORD = 3
