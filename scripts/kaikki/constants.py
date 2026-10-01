"""Constants"""

from __future__ import annotations

import os


RAW_JSONL_URL = "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"
AUDIO_TAR_URL = "https://kaikki.org/dictionary/wiktionary-audios.tar"
RAWDATA_PAGE_URL = "https://kaikki.org/dictionary/rawdata.html"

WIKTIONARY_LICENSE = "CC BY-SA 4.0"
WIKTEXTRACT_CITATION = (
    "Tatu Ylonen. Wiktextract: Wiktionary as Machine-Readable Structured Data, "
    "LREC 2022"
)

# Wikimedia rejects generic user agents under its robot policy
# (https://meta.wikimedia.org/wiki/User-Agent_policy), so identify the tool and
# provide a contact URL.
USER_AGENT = (
    "Aurelex-Kaikki-DSL/1.0 "
    "(https://github.com/anomalyco/aurelex; dictionary build tool) "
    "python-urllib"
)
# Minimum gap between requests to a single host, to stay clear of rate limits.
_DOWNLOAD_SPACING_SECONDS = 1.0
_DOWNLOAD_RETRIES = 4
# Ceiling on any single backoff sleep, so a hostile or mistaken Retry-After
# cannot park a run for hours.
_DOWNLOAD_MAX_BACKOFF_SECONDS = 60.0

# Filling the audio cache is a bulk back-fill against Wikimedia, not the
# incidental fetch a build does, so it runs slower and retries longer: their
# robot policy expects bulk clients to stay well clear of one request per second
# and to give up rather than hammer a 429.
_PREFETCH_SPACING_SECONDS = 2.0
_PREFETCH_RETRIES = 6

# Parts of speech that are not lexical headwords in this converter's sense.
NON_LEXICAL_POS = {"soft-redirect", "romanization"}

AUDIO_EXTENSIONS = (
    ".ogg", ".oga", ".mp3", ".wav", ".flac", ".opus", ".m4a", ".spx",
    ".au", ".aac", ".wma", ".mp2", ".mpa",
)

OGG_EXTENSIONS = {".ogg", ".oga", ".opus"}

# How far a random sample spreads: keep one headword per this many distinct
# candidates, so a sample of N covers N * this many words without reading the
# whole snapshot.
_SAMPLE_STRIDE_TARGET = 200

# The scripts directory is the package's parent: this package sits at
# ``scripts/kaikki/`` and the sibling ``make-example-dicts.py`` module and the
# ``assets/`` icon tree live in ``scripts/``.
_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
