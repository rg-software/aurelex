#!/usr/bin/env python3
"""Build an importable ABBYY Lingvo DSL dictionary from a pinned kaikki.org
Wiktionary (wiktextract) snapshot for one language.

The output is a deterministic dictzip-compressed ``<name>.dsl.dz`` plus a
sibling ``<name>.dsl.files.zip`` (or ``.files/`` directory) holding the
referenced pronunciation audio, so it imports through Aurelex's existing
folder import without any app or engine changes.

This builds **monolingual explanatory dictionaries**: the indexed headwords and
their definitions are in the same language. Wiktionary's cross-language data is
not used, because it is too sparse and too loosely aligned to make a reliable
translation dictionary (see ``docs/KAIKKI-CONVERSION.md``).

Highlights:
  * reproducible: a pinned dump date, cached downloads (with sha256 sidecars),
    no plain ``.dsl`` in the output, byte-identical rebuilds
  * the source language selects the indexed headwords and the article language
  * base forms are the only indexed headwords by default; ``--include-inflections``
    adds a base word's inflected forms as extra headword lines (they then also
    appear in the suggestion list - there is no hidden-alias concept in DSL)
  * grammatical forms are filtered to the standard paradigm and compactly
    labelled, driven by a per-language profile
  * bounded audio (``--audio-per-word``, default 3; ``--no-audio`` disables)
  * ``--sample N`` and ``--preview`` for reviewing article shape and formatting
  * provenance (Wiktionary, CC BY-SA 4.0, wiktextract citation, dump date) is
    embedded in the ``#NAME`` metadata and in an about card

Usage:
  kaikki-to-dsl.py --source-lang en --dump-date 2026-09-02 \\
      --out-dir dist --sample 200 --preview
"""

from __future__ import annotations

import argparse
import base64
from collections import deque
import gzip
import hashlib
import heapq
import html
import importlib.util
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from typing import (
    Deque, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple,
)
from urllib.parse import quote, unquote, urlsplit, urlunsplit

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_JSONL_URL = "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"
AUDIO_TAR_URL = "https://kaikki.org/dictionary/wiktionary-audios.tar"
RAWDATA_PAGE_URL = "https://kaikki.org/dictionary/rawdata.html"

WIKTIONARY_LICENSE = "CC BY-SA 4.0"
WIKTEXTRACT_CITATION = (
    "Tatu Ylonen: Wiktextract: Wiktionary as Machine-Readable Structured Data, "
    "LREC 2022 (https://kaikki.org)"
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


# ---------------------------------------------------------------------------
# Per-language profiles
# ---------------------------------------------------------------------------
# Anything specific to one language (its form-tag vocabulary, transcription
# fields, compact labels) lives in a profile rather than in the renderer, so
# adding a language is a data change. Tests assert the renderer stays generic.

class LangProfile:
    """How to read one language's records into an article.

    ``form_tags``       - the grammatical tag vocabulary of this language. A
                          form is labelled from these and, when ``strict_tags``
                          is set, must consist only of them.
    ``form_noise_tags`` - tags that mean "raw inflection table" or a low-value
                          register/dialect variant; such forms are never shown.
    ``pron_fields``     - ``sounds[]`` keys that carry a transcription, shown in
                          this order and each at most once.
    ``short_tags``      - compact labels for the common grammatical tags.
    ``has_audio``       - whether the language has pronunciation recordings.
    ``strip_forms``     - whether article "Forms:" lines are meaningful.
    """

    def __init__(
        self,
        code: str,
        form_tags: Set[str],
        form_noise_tags: Set[str],
        pron_fields: Sequence[str],
        short_tags: Dict[str, str],
        has_audio: bool = True,
        strip_forms: bool = False,
        strict_tags: bool = False,
        sense_noise_tags: Optional[Set[str]] = None,
        sense_short_tags: Optional[Dict[str, str]] = None,
    ) -> None:
        self.code = code
        self.form_tags = form_tags
        self.form_noise_tags = form_noise_tags
        self.pron_fields = tuple(pron_fields)
        self.short_tags = short_tags
        self.has_audio = has_audio
        self.strip_forms = strip_forms
        self.strict_tags = strict_tags
        # Sense tags that mark the unremarkable case (a noun is countable, a
        # verb transitive) add no information and are dropped; the rest are
        # abbreviated through ``sense_short_tags``.
        self.sense_noise_tags = set(sense_noise_tags or ())
        self.sense_short_tags = dict(sense_short_tags or {})

    def form_qualifies(self, tags: Sequence[str]) -> bool:
        """Whether a form belongs in the article's forms line.

        The default is a blocklist: keep a tagged form unless it carries a
        register/dialect or table-machinery tag. That keeps ordinary paradigms
        (``children (plural)``, ``ran (past)``) whose tag sets include
        bookkeeping tags the profile does not enumerate. ``strict_tags`` flips
        it to a whitelist for languages whose tag space is noisy enough to
        need one.
        """
        tags = [str(t) for t in tags]
        if not tags:
            return False
        if any(t in self.form_noise_tags for t in tags):
            return False
        if self.strict_tags:
            return all(t in self.form_tags for t in tags)
        return True

    def label_tags(self, tags: Sequence[str]) -> str:
        """Compact human label for a tag set.

        A person tag already implies its number (``third-person`` + ``singular``
        is just "3rd sg."), so the number is dropped when a person is present,
        and tags outside the language's vocabulary are dropped as noise.
        """
        tags = [str(t) for t in tags]
        if "third-person" in tags or "first-person" in tags or "second-person" in tags:
            tags = [t for t in tags if t not in ("singular", "plural")]
        if self.form_tags:
            tags = [t for t in tags if t in self.form_tags]
        parts = [self.short_tags.get(t, t.replace("-", " ")) for t in tags]
        return ", ".join(parts)


# Register and dialect tags: a learner wants the standard paradigm, not every
# archaic, dialectal or eye-dialect variant Wiktionary records beside it.
_REGISTER_TAGS = {
    "archaic", "obsolete", "dialectal", "nonstandard", "rare", "humorous",
    "slang", "informal", "colloquial", "vulgar", "offensive", "derogatory",
    "pronunciation-spelling", "alternative", "misspelling", "Internet",
    "proscribed", "dated", "poetic", "literary", "regional",
}
_TABLE_TAGS = {"table-tags", "inflection-template", "no-table-tags"}
_FORM_NOISE = _TABLE_TAGS | _REGISTER_TAGS

# English grammatical vocabulary, used to label forms and to strip bookkeeping
# tags (canonical, etc.) from a label.
_EN_FORM_TAGS = {
    "plural", "singular", "past", "present", "participle",
    "third-person", "first-person", "second-person",
    "comparative", "superlative", "imperative", "infinitive",
    "positive", "attributive", "predicative", "not-comparable",
    "definite", "indefinite",
}
_EN_NOISE = _FORM_NOISE
_EN_SHORT_TAGS = {
    "third-person": "3rd sg.", "first-person": "1st", "second-person": "2nd",
    "singular": "sg.", "plural": "pl.",
    "present": "pres.", "past": "past", "participle": "part.",
    "comparative": "comp.", "superlative": "sup.",
    "imperative": "imper.", "infinitive": "inf.",
}

# Sense tags on English glosses that describe the unremarkable case: a verb is
# transitive unless said otherwise, so printing "(transitive)" on every other
# sense is pure noise. (Countability is *not* noise — it is shown as an icon, see
# ``_SENSE_TAG_ICONS``.) The rest are abbreviated to the forms a printed
# dictionary uses.
_EN_SENSE_NOISE = {"transitive", "intransitive", "not-comparable"}
_EN_SENSE_SHORT = {
    "figuratively": "fig.", "derogatory": "derog.", "informal": "inform.",
    "colloquial": "colloq.", "slang": "slang", "archaic": "arch.",
    "obsolete": "obs.", "dialectal": "dial.", "humorous": "hum.",
    "vulgar": "vulg.", "offensive": "offens.", "rare": "rare",
    "literary": "lit.", "poetic": "poet.", "dated": "dated",
    "metonymically": "meton.", "transferred sense": "fig.",
    "historical": "hist.", "law": "law", "medicine": "med.",
    "computing": "comput.", "biology": "biol.", "chemistry": "chem.",
    "mathematics": "math.", "physics": "phys.", "sports": "sports",
    "informal or colloquial": "inform.",
}

# German forms are dominated by case/number/gender; a global whitelist would
# discard the most useful information, hence a dedicated row.
_DE_FORM_TAGS = {
    "singular", "plural", "nominative", "genitive", "dative", "accusative",
    "strong", "weak", "mixed", "definite", "indefinite", "without-article",
    "with-article", "comparative", "superlative", "positive",
    "present", "past", "participle", "first-person", "second-person",
    "third-person", "imperative",
}
_DE_NOISE = _FORM_NOISE
_DE_SHORT_TAGS = {
    "singular": "sg.", "plural": "pl.", "nominative": "nom.",
    "genitive": "gen.", "dative": "dat.", "accusative": "acc.",
    "strong": "strong", "weak": "weak", "mixed": "mixed",
    "present": "pres.", "past": "past", "participle": "part.",
    "comparative": "comp.", "superlative": "sup.",
}

# Japanese has no IPA in this source; readings arrive as forms (`romanization`,
# `hiragana`, ...) so the pronunciation slot is filled from those instead. Its
# tag space is broad, so it stays on the permissive default policy.
_JA_FORM_TAGS: Set[str] = set()
_JA_NOISE = _FORM_NOISE
_JA_SHORT_TAGS = {
    "romanization": "romaji", "hiragana": "hiragana", "katakana": "katakana",
    "kanji": "kanji", "kyūjitai": "kyūjitai", "stem": "stem",
    "imperfective": "imperf.", "continuative": "cont.", "past": "past",
}

LANG_PROFILES: Dict[str, LangProfile] = {
    "en": LangProfile(
        "en", _EN_FORM_TAGS, _EN_NOISE, ("ipa", "enpr"), _EN_SHORT_TAGS,
        sense_noise_tags=_EN_SENSE_NOISE, sense_short_tags=_EN_SENSE_SHORT,
    ),
    "de": LangProfile(
        "de", _DE_FORM_TAGS, _DE_NOISE, ("ipa", "enpr"), _DE_SHORT_TAGS,
    ),
    "ja": LangProfile(
        "ja", _JA_FORM_TAGS, _JA_NOISE, (), _JA_SHORT_TAGS, has_audio=False,
    ),
}


def get_lang_profile(code: str) -> LangProfile:
    """The source-language profile, or a permissive fallback.

    The fallback keeps any tagged form and shows any transcription the source
    happens to provide, so an unknown source language still produces a sane
    article (and a warning) instead of an empty one.
    """
    profile = LANG_PROFILES.get(code)
    if profile is not None:
        return profile
    print(
        f"warning: no language profile for {code!r}; using a permissive default",
        file=sys.stderr,
    )
    return LangProfile(code, set(), _EN_NOISE, ("ipa", "enpr"), {})


def collect_profile_forms(record: dict, profile: LangProfile, limit: int = 8) -> List[str]:
    """Standard paradigm forms, compactly labelled and de-duplicated.

    Register/dialect variants and raw inflection tables are dropped, so an
    article shows ``ran (past)`` and ``children (pl.)`` but not
    ``runnest (archaic, 2nd sg.)`` or ``childer (dialectal, pl.)``.
    """
    forms: List[str] = []
    seen: Set[Tuple[str, Tuple[str, ...]]] = set()
    for form in record.get("forms") or []:
        if not isinstance(form, dict):
            continue
        text = form.get("form")
        if not text:
            continue
        tags = tuple(str(t) for t in (form.get("tags") or []))
        if not profile.form_qualifies(tags):
            continue
        key = (str(text), tags)
        if key in seen:
            continue
        seen.add(key)
        label = profile.label_tags(tags)
        forms.append(f"{text} ({label})" if label else str(text))
        if len(forms) >= limit:
            break
    return forms


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# dictzip: reuse the writer from make-example-dicts.py (single source of truth)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# DSL text tooling
# ---------------------------------------------------------------------------

def escape_dsl(text: Optional[str]) -> str:
    """Escape free text so it cannot form DSL markup.

    Backslash, square brackets, and the ``<<``/``>>`` media delimiters are
    escaped; tabs/newlines collapse to spaces and runs of spaces collapse.
    """
    if not text:
        return ""
    s = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    s = s.replace("\t", " ")
    s = s.replace("\\", "\\\\")
    s = s.replace("[", "\\[")
    s = s.replace("]", "\\]")
    s = s.replace("<<", "\\<\\<").replace(">>", "\\>\\>")
    s = re.sub(r" {2,}", " ", s)
    return s.strip()


def clean_headword(word: Optional[str]) -> str:
    """Sanitise a headword line (column 0, no indentation)."""
    hw = escape_dsl(word)
    hw = hw.lstrip("\t ")
    if hw.startswith("#"):
        hw = "\\" + hw
    return hw


def header_arg(value: Optional[str]) -> str:
    """Sanitise a quoted DSL header argument (no embedded quotes)."""
    return escape_dsl(value).replace('"', "'")


def _flatten(value) -> str:
    """Render an arbitrary wiktextract value as readable text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values() if v is not None)
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v) for v in value if v is not None)
    return ""


# Wiktionary sense tags that describe how the gloss relates to another entry
# ("alternative/other form of", "synonym of", an ellipsis, a clipping) rather than
# how the word is used: the gloss itself states the relation, so no marker is
# added. The related headword is linked instead (see ``_link_form_targets``).
_STRUCTURAL_SENSE_TAGS = {
    "alt-of", "alternative", "form-of",
    "synonym", "synonyms", "ellipsis", "clipping",
}


# Sense tags shown as a small inline icon instead of a parenthetical word. The
# same icon may stand for several source tags: a drink for countable, a water
# drop for uncountable, a tag glyph for the initialism family, and a landmark for
# obsolete/dated/archaic usage. The filenames resolve against the dictionary's
# own resource bundle (see ``scripts/assets/kaikki-tag-icons/``).
_SENSE_TAG_ICONS = {
    "countable": "gd_tag_countable.svg",
    "uncountable": "gd_tag_uncountable.svg",
    "initialism": "gd_tag_initialism.svg",
    "abbreviation": "gd_tag_initialism.svg",
    "acronym": "gd_tag_initialism.svg",
    "obsolete": "gd_tag_obsolete.svg",
    "dated": "gd_tag_obsolete.svg",
    "archaic": "gd_tag_obsolete.svg",
}


def _icon_ref(name: str) -> str:
    """A DSL picture reference for one bundled sense-marker icon."""
    return f"[s]{escape_dsl(name)}[/s]"


# The relation a gloss states in words ("Initialism of …", "Abbreviation of …")
# when that same relation is already shown as an icon.
_RELATION_PREFIX_RE = re.compile(
    r"^(?:Initialism|Abbreviation|Acronym) of\s+", re.IGNORECASE
)
_ICONISED_RELATION_TAGS = {"initialism", "abbreviation", "acronym"}


def _strip_relation_prefix(text: str, tags: Sequence[str]) -> str:
    """Drop a leading "Initialism of"/"Abbreviation of"/"Acronym of" phrase.

    Those relations are shown as the initialism icon, so the words would say the
    same thing twice; what remains is the headword the gloss names, which is then
    linked. A tag outside the icon set (a clipping, an ellipsis) is left as text.
    """
    if not _ICONISED_RELATION_TAGS & {str(t) for t in (tags or [])}:
        return text
    return _RELATION_PREFIX_RE.sub("", text, count=1)


def _link_form_targets(
    escaped: str, sense: dict, known: Optional[Set[str]], word: str
) -> str:
    """Turn the headword a form-of/alt-of sense points at into a ``[ref]`` link.

    A sense such as ``Alternative spelling of swap.`` already names the headword
    it relates to in its gloss, and ``alt_of``/``form_of`` states it explicitly.
    That word is linked when the dictionary actually contains it — the same
    known-headword guard the cross-references use — so ``swop`` reads
    ``Alternative spelling of [ref]swap[/ref].`` and tapping opens ``swap``.

    ``escaped`` is the gloss already run through :func:`escape_dsl`; the target is
    a plain word, so escaping leaves it unchanged and it can be wrapped in place.
    """
    for entry in list(sense.get("alt_of") or []) + list(sense.get("form_of") or []):
        if not isinstance(entry, dict):
            continue
        target = str(entry.get("word") or "").strip()
        if not target or target == word:
            continue
        if not known or target not in known:
            continue
        pattern = re.compile(
            r"(?<!\w)" + re.escape(escape_dsl(target)) + r"(?!\w)",
            re.IGNORECASE | re.UNICODE,
        )
        escaped = pattern.sub(lambda m: f"[ref]{m.group(0)}[/ref]", escaped, count=1)
    return escaped


# The vendored sense-marker icons, bundled into every produced dictionary and
# advertised in its about card. See scripts/assets/kaikki-tag-icons/README.md for
# provenance and license. The list is fixed, so the resource bundle is a
# deterministic set of files.
_ICON_ASSET_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "kaikki-tag-icons"
)
_ICON_FILES = (
    "gd_tag_countable.svg",
    "gd_tag_uncountable.svg",
    "gd_tag_initialism.svg",
    "gd_tag_obsolete.svg",
)

# The about-card legend: each bundled icon and the tags it stands for.
_ICON_LEGEND = (
    ("gd_tag_countable.svg", "countable"),
    ("gd_tag_uncountable.svg", "uncountable (a word that is both shows neither)"),
    ("gd_tag_initialism.svg", "initialism, abbreviation or acronym"),
    ("gd_tag_obsolete.svg", "obsolete, dated or archaic"),
)


def _icon_data_uri(name: str) -> str:
    """A data URI for one bundled icon, so the standalone preview shows it."""
    with open(os.path.join(_ICON_ASSET_DIR, name), "rb") as f:
        data = f.read()
    return "data:image/svg+xml;base64," + base64.b64encode(data).decode("ascii")


def _audio_ref(name: str) -> str:
    """A DSL sound reference for one bundled audio filename."""
    return f"[s]{escape_dsl(name)}[/s]"


def _sense_markers(tags: Sequence[str], profile: "LangProfile") -> str:
    """The inline markers that precede a sense's gloss: icons, then a text tag.

    Common tags are shown as small icons (``_SENSE_TAG_ICONS``), in tag order and
    de-duplicated by icon; at most one remaining register/context tag follows as
    abbreviated text. Tags describing the unremarkable case or a relation the
    gloss already states are dropped. Returns "" when a sense carries none.

    Countability is the one special case: Wiktionary tags most nouns both
    ``countable`` and ``uncountable`` ("can be either"), so when both are present
    neither icon is shown — only a lone countability tag is informative.
    """
    tags = [str(t) for t in (tags or [])]
    both_counter = {"countable", "uncountable"} <= set(tags)
    icons: List[str] = []
    for tag in tags:
        if both_counter and tag in ("countable", "uncountable"):
            continue
        icon = _SENSE_TAG_ICONS.get(tag)
        if icon and icon not in icons:
            icons.append(icon)
    text = ""
    for tag in tags:
        if (
            tag in _SENSE_TAG_ICONS
            or tag in _STRUCTURAL_SENSE_TAGS
            or tag in profile.sense_noise_tags
        ):
            continue
        text = "(" + profile.sense_short_tags.get(tag, tag.replace("-", " ")) + ") "
        break
    return "".join(_icon_ref(name) + " " for name in icons) + text


# ---------------------------------------------------------------------------
# Snapshot model and cached download
# ---------------------------------------------------------------------------

class Snapshot:
    """A pinned kaikki.org snapshot and its local cache locations."""

    def __init__(
        self,
        dump_date: Optional[str],
        cache_dir: str,
        jsonl_url: str = RAW_JSONL_URL,
        audio_url: str = AUDIO_TAR_URL,
    ) -> None:
        self.dump_date = dump_date
        self.cache_dir = cache_dir
        self.jsonl_url = jsonl_url
        self.audio_url = audio_url
        key = dump_date or "local"
        self.dir = os.path.join(cache_dir, key)

    @property
    def jsonl_path(self) -> str:
        return os.path.join(self.dir, os.path.basename(self.jsonl_url.split("?")[0]))

    @property
    def audio_path(self) -> str:
        return os.path.join(self.dir, os.path.basename(self.audio_url.split("?")[0]))


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_sidecar(path: str) -> bool:
    """Verify a downloaded file against its ``.sha256`` sidecar if present."""
    sidecar = path + ".sha256"
    if not os.path.isfile(path):
        return False
    if os.path.getsize(path) == 0:
        return False
    if not os.path.isfile(sidecar):
        return True
    with open(sidecar, "r", encoding="ascii") as f:
        expected = f.read().strip()
    return expected == _sha256_file(path)


_last_request_time = 0.0


def _throttle(gap: Optional[float] = None) -> None:
    """Sleep so consecutive requests to the same host stay polite."""
    global _last_request_time
    spacing = _DOWNLOAD_SPACING_SECONDS if gap is None else gap
    elapsed = time.time() - _last_request_time
    if elapsed < spacing:
        time.sleep(spacing - elapsed)
    _last_request_time = time.time()


def _ascii_url(url: str) -> str:
    """Percent-encode a URL's non-ASCII parts so urllib can send it.

    A wiktextract audio URL may carry a raw Unicode title (``zh-xiàn.ogg``),
    and ``urllib`` writes the request line as ASCII, so sending it unescaped
    fails with ``'ascii' codec can't encode character``. Quote the path and
    query while leaving the scheme, host and existing escapes untouched.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    path = quote(parts.path, safe="/%:@!$&'()*+,;=~")
    query = quote(parts.query, safe="=&%:@!$'()*+,;/?~")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def _retry_after_seconds(exc: urllib.error.HTTPError) -> Optional[float]:
    """The server's own requested wait, in seconds, if it sent one.

    Wikimedia sets ``Retry-After`` on a 429 with its robot-policy cooldown, and
    that is the number it will actually hold us to; guessing a shorter backoff
    just earns another 429. Returns ``None`` when the header is absent or
    unparseable, leaving the caller on its own exponential schedule.
    """
    headers = getattr(exc, "headers", None)
    if headers is None:
        return None
    try:
        raw = headers.get("Retry-After")
    except AttributeError:
        return None
    if not raw:
        return None
    try:
        seconds = float(str(raw).strip())
    except ValueError:
        # the header may also be an HTTP-date; we cannot parse one without a
        # full date library, and the exponential fallback is the safe answer
        return None
    return max(0.0, seconds)


def _open_with_retries(
    url: str,
    timeout: int,
    retries: Optional[int] = None,
    spacing: Optional[float] = None,
    max_backoff: Optional[float] = None,
):
    """Open ``url``, retrying rate limits and transient server errors.

    Wikimedia answers an over-eager client with 429 (sometimes with a robot-policy
    message); backing off and retrying turns that into a slow success rather than
    a missing file. A ``Retry-After`` on the response overrides the computed
    backoff, capped by ``max_backoff`` so a hostile or mistaken header cannot
    park the run for hours.

    ``retries``/``spacing``/``max_backoff`` default to the module-level policy;
    the audio prefetcher passes its own, because filling a large cache back is a
    different job from fetching a handful of files during a build.
    """
    last: Optional[Exception] = None
    url = _ascii_url(url)
    attempts = _DOWNLOAD_RETRIES if retries is None else max(1, retries)
    gap = _DOWNLOAD_SPACING_SECONDS if spacing is None else max(0.0, spacing)
    ceiling = _DOWNLOAD_MAX_BACKOFF_SECONDS if max_backoff is None else max_backoff
    for attempt in range(attempts):
        _throttle(gap)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            delay = min(ceiling, gap * (2 ** attempt))
            asked = _retry_after_seconds(exc)
            if asked is not None:
                delay = min(ceiling, max(delay, asked))
            print(f"  rate limited ({exc.code}), retrying in {delay:.0f}s ...",
                  file=sys.stderr)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(min(ceiling, gap * (2 ** attempt)))
    assert last is not None
    raise last


# Statuses a retry cannot fix: the file is gone, or never was there. Anything
# else -- 429, 5xx, 403 from a bot filter, a timeout, a dropped connection -- is
# worth trying again, because the next run might be the one that gets through.
# The split is what lets the prefetcher say "stop" instead of "keep going": a
# dead URL retried on every run never succeeds, so without recording it the run
# could never report itself finished.
PERMANENT_HTTP_STATUS = frozenset({400, 404, 410, 451})


def failure_is_permanent(exc: BaseException) -> bool:
    """Whether retrying ``exc`` could ever succeed.

    Only a definitive HTTP answer counts. A 404 or 410 is a statement about the
    file rather than the moment; everything else -- including statuses that are
    usually temporary -- is treated as worth another try, because the cost of a
    wrong "permanent" is a pronunciation the article silently never gets.
    """
    return isinstance(exc, urllib.error.HTTPError) and exc.code in PERMANENT_HTTP_STATUS


def describe_failure(exc: BaseException) -> str:
    """A short human reason for a failed fetch, for the dead-file record."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return str(exc.reason)
    return type(exc).__name__


def download_cached(
    url: str,
    dest: str,
    force: bool = False,
    timeout: int = 60,
    retries: Optional[int] = None,
    spacing: Optional[float] = None,
    max_backoff: Optional[float] = None,
) -> str:
    """Download ``url`` to ``dest`` once, writing a sha256 sidecar.

    Reuses an existing, verified file unless ``force`` is set. The write is
    atomic (a ``.part`` file is renamed into place), and rate limits are retried
    with backoff.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not force and verify_sidecar(dest):
        return dest
    part = dest + ".part"
    print(f"downloading {url} ...", file=sys.stderr)
    with _open_with_retries(url, timeout, retries, spacing, max_backoff) as response, \
            open(part, "wb") as out:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            out.write(block)
    os.replace(part, dest)
    with open(dest + ".sha256", "w", encoding="ascii") as f:
        f.write(_sha256_file(dest))
    return dest


def _fetch_dump_date(timeout: int = 60) -> Optional[str]:
    with _open_with_retries(RAWDATA_PAGE_URL, timeout) as response:
        page = response.read().decode("utf-8", "replace")
    match = re.search(r"dump dated (\d{4}-\d{2}-\d{2})", page)
    return match.group(1) if match else None


class Progress:
    """A coarse, cheap stderr progress indicator.

    ``tick`` is called once per item and only formats and writes on a batch
    boundary (or the first item), so the cost per item is a single comparison.
    ``done`` always reports the final count, so a short run still shows that the
    stage ran rather than staying silent.
    """

    def __init__(self, label: str, every: int = 200000, total: Optional[int] = None) -> None:
        self.label = label
        self.every = max(1, every)
        self.total = total
        self.count = 0
        self.t0 = time.time()
        self._shown = False

    def tick(self, increment: int = 1) -> None:
        self.count += increment
        if self.count == increment or self.count % self.every == 0:
            self._write()

    def _write(self, final: bool = False) -> None:
        if self.total:
            text = f"{self.label}: {self.count:,}/{self.total:,}"
        else:
            text = f"{self.label}: {self.count:,}"
        text += f"  ({time.time() - self.t0:.0f}s)"
        stream = sys.stderr
        stream.write("\r" + text.ljust(72))
        if final:
            stream.write("\n")
        stream.flush()
        self._shown = True

    def done(self) -> None:
        self._write(final=True)


# ---------------------------------------------------------------------------
# Reading / filtering records
# ---------------------------------------------------------------------------

def open_text_maybe_gzip(path: str):
    with open(path, "rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "rt", encoding="utf-8", errors="replace")


def iter_records(
    path: str,
    progress: Optional["Progress"] = None,
    lang_code: Optional[str] = None,
) -> Iterator[Tuple[int, Optional[dict]]]:
    """Yield ``(line_number, record_or_None)``; ``None`` marks a malformed line.

    With ``lang_code`` set, a line whose raw text does not contain that
    language's marker is skipped before JSON parsing, which is most of a full
    snapshot and the dominant cost of a scan. The prefilter is a substring test,
    so the parsed record is checked again: a record of another language can carry
    a nested ``"lang_code": "<x>"`` and slip past the raw-text test.
    """
    needle = f'"lang_code": "{lang_code}"' if lang_code else None
    compact_needle = f'"lang_code":"{lang_code}"' if lang_code else None
    with open_text_maybe_gzip(path) as stream:
        for line_no, line in enumerate(stream, 1):
            if progress is not None:
                progress.tick()
            line = line.strip()
            if not line:
                continue
            # the prefilter must not reject a real record, so accept either JSON
            # spacing; the parsed check below is what actually decides
            if (
                needle is not None
                and needle not in line
                and compact_needle not in line
            ):
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("not an object")
            except (json.JSONDecodeError, ValueError):
                yield line_no, None
                continue
            if lang_code is not None and record.get("lang_code") != lang_code:
                continue
            yield line_no, record


def is_lexical(record: dict) -> bool:
    if record.get("pos") in NON_LEXICAL_POS:
        return False
    if not record.get("word"):
        return False
    senses = record.get("senses")
    if not isinstance(senses, list) or not senses:
        return False
    return True


def is_inflected(record: dict) -> bool:
    senses = record.get("senses") or []
    return any(isinstance(s, dict) and s.get("form_of") for s in senses)


def iter_candidate_records(
    path: str, source_code: str, progress: Optional["Progress"] = None
) -> Iterator[dict]:
    """Yield the records that become indexed headwords, in file order.

    This is the single definition of what a build indexes: the source language,
    lexical, and not an inflected form. Everything that walks the snapshot for
    those records goes through here -- the build, the headword selection, and the
    audio prefetcher -- so a change to the rules cannot leave one of them
    planning against a different set of articles than the others.
    """
    for _, record in iter_records(path, progress):
        if record is None or record.get("lang_code") != source_code:
            continue
        if not is_lexical(record) or is_inflected(record):
            continue
        yield record


def iter_candidate_headwords(
    path: str, source_code: str, progress: Optional["Progress"] = None
) -> Iterator[str]:
    """Yield headword candidates (source language, lexical, not inflected)."""
    for record in iter_candidate_records(path, source_code, progress):
        word = record.get("word")
        if word:
            yield str(word)


def select_headwords(
    path: str,
    source_code: str,
    sample: Optional[int],
    sample_mode: str,
    progress: Optional["Progress"] = None,
) -> Set[str]:
    """The set of headwords that will be indexed (drives cross-reference safety).

    This is the *full-build* selection: every candidate headword. It reads the
    whole snapshot, so it is only used when no sample is requested.
    """
    return set(iter_candidate_headwords(path, source_code, progress))


def sample_headwords(
    path: str,
    source_code: str,
    sample: int,
    sample_mode: str,
    progress: Optional["Progress"] = None,
    report: Optional["Report"] = None,
) -> List[dict]:
    """Pick a small sample of records in a single bounded pass.

    Returns the source-language records of up to ``sample`` *distinct* lexical,
    non-inflected headwords, with all the records of each, in file order.
    Unlike the full build this never reads the whole snapshot, so a sample of a
    few hundred words finishes in seconds.

    ``first`` takes the first candidates encountered. ``random`` reads a bounded
    window of ``sample * _SAMPLE_STRIDE_TARGET`` distinct candidates and keeps
    the ``sample`` with the smallest sha256 keys, which spreads the sample over
    thousands of headwords without scanning the file. A file smaller than the
    window simply contributes all the candidates it has. Both modes are
    deterministic for a given snapshot and options.
    """
    window = sample * _SAMPLE_STRIDE_TARGET if sample_mode == "random" else sample
    heap: List[Tuple[int, str]] = []  # max-heap of (-hash, word), size <= sample
    chosen: Set[str] = set()
    records_by_word: Dict[str, List[dict]] = {}
    order: List[str] = []               # words in first-seen order
    take_all = sample_mode != "random"
    distinct_seen = 0

    for _, record in iter_records(path, progress, source_code):
        if record is None:
            if report is not None:
                report.skipped_malformed += 1
            continue
        if not is_lexical(record) or is_inflected(record):
            if report is not None:
                if is_inflected(record):
                    report.skipped_inflected += 1
                else:
                    report.skipped_nonlexical += 1
            continue
        word = str(record.get("word"))
        if word in records_by_word:
            if word in chosen:
                records_by_word[word].append(record)
            continue

        if take_all:
            if len(chosen) >= sample:
                break
            chosen.add(word)
            order.append(word)
            records_by_word[word] = [record]
            continue

        records_by_word[word] = [record]
        order.append(word)
        key = int.from_bytes(hashlib.sha256(word.encode("utf-8")).digest()[:8], "big")
        if len(heap) < sample:
            heapq.heappush(heap, (-key, word))
            chosen.add(word)
        else:
            evicted = heapq.heapreplace(heap, (-key, word))[1]
            chosen.discard(evicted)
            chosen.add(word)
        distinct_seen += 1
        if distinct_seen >= window:
            break

    return [r for word in order if word in chosen for r in records_by_word[word]]


# How the transcription fields of a profile are labelled in an article. The
# line a transcription lands on is always a transcription, so the common IPA
# value is emitted bare; a second notation (enPR) keeps its name.
_PRON_LABEL = {"ipa": "IPA", "enpr": "enPR"}
_UNLABELLED_PRON_FIELDS = {"ipa"}


# ---------------------------------------------------------------------------
# Audio planning and extraction
# ---------------------------------------------------------------------------

def _basename(name: str) -> str:
    return os.path.basename(name.split("?")[0].split("/")[-1])


def _url_basename(name: str) -> str:
    """The canonical file name behind a media reference.

    A reference may be a bare name, a URL, or a percent-encoded MediaWiki path
    (``LL-Q1860_%28eng%29-Vealhurl-pub.wav/...wav.ogg``), and it may carry HTML
    entities (``&#45;`` for a hyphen). Decoding it yields the name the audio
    archive stores.
    """
    return html.unescape(unquote(_basename(name)))


def _audio_match_key(name: str) -> str:
    """Normalisation that pairs a reference with an archive member.

    The archive stores MediaWiki names (underscores, percent-encoded), while a
    reference may use spaces and any casing, so both sides are folded before
    comparison.
    """
    return _url_basename(name).replace(" ", "_").casefold()


def _audio_name_variants(name: str) -> List[str]:
    """Ordered archive keys a reference may be stored under.

    The archive keeps a compressed original plus an mp3 transcode; a large
    original (``.wav``/``.flac``) is present only as ``<name>.ogg`` or
    ``<name>.mp3``. The exact key comes first so the best-quality match wins.
    """
    key = _audio_match_key(name)
    if not key:
        return []
    stem, ext = os.path.splitext(key)
    if ext in OGG_EXTENSIONS:
        return [key, key + ".mp3"]
    return [key, key + ".ogg", key + ".mp3", stem + ".ogg", stem + ".mp3"]


def _canonical_audio_name(sound: dict) -> Optional[str]:
    """The name to bundle and reference for one ``sounds`` entry.

    ``audio`` is the raw wiki argument and is unreliable (wrong case, spaces
    instead of underscores, HTML entities); the URL fields carry the canonical
    MediaWiki title, so they are preferred.
    """
    for field in ("ogg_url", "mp3_url", "audio"):
        value = sound.get(field)
        if value:
            return _url_basename(str(value))
    return None


def _audio_sounds(record: dict) -> List[dict]:
    return [
        s
        for s in (record.get("sounds") or [])
        if isinstance(s, dict)
        and any(s.get(f) for f in ("audio", "ogg_url", "mp3_url"))
    ]


class AudioPlan:
    """Assign collision-free final filenames and remember what is referenced.

    When ``available`` is given it is the set of normalised names present in
    the audio archive; only references found in it (or fetched directly from
    Wikimedia, when a URL is known) are planned, so the output never carries a
    link to a file that was not bundled, and a reference that is absent does
    not consume one of the per-word slots.
    """

    def __init__(
        self,
        per_word: int,
        preferred_lang: Optional[str],
        enabled: bool,
        available: Optional[Set[str]] = None,
        downloader=None,
    ) -> None:
        self.per_word = per_word
        self.preferred_lang = preferred_lang
        self.enabled = enabled
        self.available = available
        # ``downloader(url, dest)`` fetches a recording the archive lacks; the
        # default reuses the cached downloader. Tests inject a stub.
        self.downloader = downloader or (
            lambda url, dest: download_cached(url, dest)
        )
        self._owner: Dict[str, str] = {}   # final_name -> source url
        self.referenced: Set[str] = set()
        self.aliases: Dict[str, List[str]] = {}  # final_name -> archive match keys
        self.local: Dict[str, str] = {}    # final_name -> fetched file on disk
        self.missing: Set[str] = set()     # referenced sources not bundled
        self._fetched: Dict[str, Optional[str]] = {}  # source -> local path or None

    def _final_name(self, source: str) -> str:
        base = _basename(source)
        if base not in self._owner or self._owner[base] == source:
            self._owner[base] = source
            return base
        stem, ext = os.path.splitext(base)
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:8]
        candidate = f"{stem}-{digest}{ext}"
        self._owner[candidate] = source
        return candidate

    def _archive_keys(self, source: str, sound: dict) -> List[str]:
        keys: List[str] = []
        for field in ("ogg_url", "mp3_url", "audio"):
            value = sound.get(field)
            if not value:
                continue
            for key in _audio_name_variants(str(value)):
                if key not in keys:
                    keys.append(key)
        if not keys:
            keys = _audio_name_variants(source)
        return keys

    def _is_available(self, keys: List[str]) -> bool:
        if self.available is None:
            return True
        return any(key in self.available for key in keys)

    def _fetch(self, source: str, sound: dict) -> Optional[str]:
        """Download a recording the archive lacks from its Wikimedia URL.

        The result lands in ``download_dir`` through the cached downloader, so
        a later run reuses it instead of fetching it again. Returns the local
        path, or ``None`` when there is no URL or the fetch failed.
        """
        if source in self._fetched:
            return self._fetched[source]
        path: Optional[str] = None
        url = sound.get("ogg_url") or sound.get("mp3_url")
        if self.download_dir and url:
            name = self._final_name(source)
            dest = os.path.join(self.download_dir, name)
            try:
                os.makedirs(self.download_dir, exist_ok=True)
                cached = verify_sidecar(dest)
                self.downloader(str(url), dest)
                if os.path.isfile(dest):
                    path = dest
                    self.local[name] = dest
                    if cached:
                        print(f"audio cached: {source}", file=sys.stderr)
                    else:
                        print(f"audio downloaded: {source} (from {url})", file=sys.stderr)
            except Exception as exc:  # network errors must not abort the run
                print(f"audio download failed for {source}: {exc}", file=sys.stderr)
        self._fetched[source] = path
        return path

    def plan(self, record: dict) -> List[str]:
        """Return the final audio filenames chosen for this record (bounded)."""
        if not self.enabled or self.per_word <= 0:
            return []
        candidates: List[Tuple[int, str, dict]] = []
        for sound in _audio_sounds(record):
            source = _canonical_audio_name(sound)
            if not source:
                continue
            ext = os.path.splitext(source)[1].lower()
            if ext not in AUDIO_EXTENSIONS:
                continue
            score = 0
            if ext in OGG_EXTENSIONS:
                score -= 1
            if self.preferred_lang:
                tags = " ".join(str(t).lower() for t in (sound.get("tags") or []))
                if self.preferred_lang.lower() in tags:
                    score -= 2
            candidates.append((score, source, sound))
        candidates.sort(key=lambda item: (item[0], item[1]))
        chosen: List[str] = []
        seen: Set[str] = set()
        for _, source, sound in candidates:
            if source in seen:
                continue
            seen.add(source)
            keys = self._archive_keys(source, sound)
            if not self._is_available(keys) and self._fetch(source, sound) is None:
                # Unresolvable: note it and let the next recording fill the
                # slot instead of emitting a link to a file we do not have.
                if source not in self.missing:
                    self.missing.add(source)
                    print(f"audio missing: {source}", file=sys.stderr)
                continue
            name = self._final_name(source)
            aliases = self.aliases.setdefault(name, [])
            for key in keys:
                if key not in aliases:
                    aliases.append(key)
            chosen.append(name)
            if len(chosen) >= self.per_word:
                break
        for name in chosen:
            self.referenced.add(name)
        return chosen


def _archive_identity(audio_path: str) -> str:
    """A cheap fingerprint of the archive, for validating a cached index.

    Records the absolute path plus size, mtime and (when present) the sha256
    sidecar. Any of these changing means the archive was replaced or
    re-downloaded, so a cached name index is stale and must be rebuilt. The path
    is included so two different archives can never share a cache entry.
    """
    st = os.stat(audio_path)
    parts = [
        "path=" + os.path.abspath(audio_path),
        f"size={st.st_size}",
        f"mtime={int(st.st_mtime)}",
    ]
    sidecar = audio_path + ".sha256"
    if os.path.isfile(sidecar):
        with open(sidecar, "r", encoding="ascii") as f:
            parts.append("sha256=" + f.read().strip())
    return "|".join(parts)


def available_audio_keys(
    audio_path: str,
    progress: Optional[Progress] = None,
    cache_dir: Optional[str] = None,
    force: bool = False,
) -> Set[str]:
    """The set of normalised member names held in the audio archive.

    Streaming the archive once up front lets planning know which recordings can
    actually be bundled, so a missing file never becomes a link in the output.
    Because the archive is large and never changes for a given dump date, the
    resulting name set is cached beside it and keyed to the archive's identity
    (size, mtime and sha256 sidecar), so it is rebuilt only when the archive
    actually changes.
    """
    keys: Set[str] = set()
    if not os.path.isfile(audio_path):
        return keys

    # The index lives beside the archive it describes, so two archives can never
    # share an entry even when a caller points at a different one.
    cache_path = (audio_path + ".keys.txt") if cache_dir else None
    identity = _archive_identity(audio_path)
    if cache_path and not force and os.path.isfile(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                header = f.readline().rstrip("\n")
                if header == identity:
                    for line in f:
                        name = line.rstrip("\n")
                        if name:
                            keys.add(name)
                    print(
                        f"audio index: {len(keys):,} names (cached)",
                        file=sys.stderr,
                    )
                    return keys
        except OSError:
            keys = set()

    keys = set()
    mode = "r|gz" if audio_path.endswith(".gz") else "r|"
    with tarfile.open(audio_path, mode) as tar:
        for member in tar:
            if progress is not None:
                progress.tick()
            if member.isfile():
                keys.add(_audio_match_key(member.name))

    if cache_path:
        try:
            part = cache_path + ".part"
            with open(part, "w", encoding="utf-8") as f:
                f.write(identity + "\n")
                for name in sorted(keys):
                    f.write(name + "\n")
            os.replace(part, cache_path)
        except OSError as exc:
            print(f"warning: could not cache the audio index: {exc}", file=sys.stderr)
    return keys


def extract_audio(
    audio_path: str,
    wanted: Dict[str, List[str]],
    dest_dir: str,
    progress: Optional[Progress] = None,
) -> Tuple[int, List[str]]:
    """Stream the bulk tar and extract the wanted names into ``dest_dir``.

    ``wanted`` maps each final filename to its ordered candidate archive keys;
    members are matched by the normalised basename. Returns
    ``(found_count, missing_names)``.
    """
    os.makedirs(dest_dir, exist_ok=True)
    remaining = set(wanted)
    found = 0
    key_index: Dict[str, List[str]] = {}
    for name, keys in wanted.items():
        for key in keys:
            key_index.setdefault(key, []).append(name)
    if not wanted or not os.path.isfile(audio_path):
        return 0, sorted(remaining)
    mode = "r|gz" if audio_path.endswith(".gz") else "r|"
    with tarfile.open(audio_path, mode) as tar:
        for member in tar:
            if not member.isfile():
                continue
            owners = key_index.get(_audio_match_key(member.name))
            if not owners:
                continue
            target = next((n for n in owners if n in remaining), None)
            if target is None:
                continue
            data = tar.extractfile(member)
            if data is None:
                continue
            try:
                with open(os.path.join(dest_dir, target), "wb") as out:
                    while True:
                        block = data.read(1024 * 1024)
                        if not block:
                            break
                        out.write(block)
            finally:
                data.close()
            remaining.discard(target)
            found += 1
            if progress is not None:
                progress.tick()
            if not remaining:
                break
    return found, sorted(remaining)


def write_audio_zip(src_dir: str, dest_zip: str) -> None:
    """Write a deterministic zip of ``src_dir``'s files (sorted, fixed times)."""
    names = sorted(
        n for n in os.listdir(src_dir) if os.path.isfile(os.path.join(src_dir, n))
    )
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(os.path.join(src_dir, name), "rb") as f:
                zf.writestr(info, f.read())


# ---------------------------------------------------------------------------
# Rendering records into DSL cards
# ---------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.kept_records = 0
        self.cards = 0
        self.skipped_malformed = 0
        self.skipped_nonlexical = 0
        self.skipped_inflected = 0
        self.out_of_pair = 0
        self.missing_audio = 0
        self.audio_found = 0

    def summary(self) -> str:
        return (
            f"headword cards: {self.cards}\n"
            f"source records kept: {self.kept_records}\n"
            f"malformed records skipped: {self.skipped_malformed}\n"
            f"non-lexical records skipped: {self.skipped_nonlexical}\n"
            f"inflected records not indexed: {self.skipped_inflected}\n"
            f"audio files bundled: {self.audio_found}\n"
            f"audio files referenced but missing: {self.missing_audio}"
        )


_LEADING_ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+")


def _cross_refs(record: dict, known: Set[str], limit: int = 12) -> List[str]:
    """Cross-reference words that are themselves indexed headwords (no dead links)."""
    word = str(record.get("word") or "")
    refs: List[str] = []
    for field in ("synonyms", "related"):
        for item in record.get(field) or []:
            target = item.get("word") if isinstance(item, dict) else item
            if not target:
                continue
            target = str(target)
            if target != word and target in known and target not in refs:
                refs.append(target)
            if len(refs) >= limit:
                return refs
    return refs


# A rendered sense and the raw examples that illustrate it. ``text`` is the
# gloss line; ``examples`` are the source lines, still unfiltered.
SenseEntry = Tuple[str, List[str]]


def _extract_examples(sense: dict) -> List[str]:
    """The raw example sentences recorded on one sense."""
    out: List[str] = []
    for example in sense.get("examples") or []:
        if isinstance(example, dict):
            text = example.get("text") or example.get("english") or ""
        else:
            text = str(example)
        text = str(text).strip()
        if text:
            out.append(text)
    return out


def _group_senses(
    senses: Sequence[dict],
    profile: LangProfile,
    known: Optional[Set[str]] = None,
    word: str = "",
) -> List[Tuple[str, List[SenseEntry]]]:
    """Group rendered senses by a shared leading gloss fragment.

    wiktextract splits a Wiktionary definition on ``:`` into a parent phrase
    plus the specific part. Senses that share a parent become one group: the
    parent is rendered once as the heading and each specific part beneath it as
    a child, so ``monkey``'s seven figurative uses do not reprint the parent
    seven times. A sense whose gloss is a single fragment is its own group with
    heading "".

    Groups merge by parent in first-seen order, and a heading or child already
    emitted is dropped — Wiktionary repeats definitions verbatim across
    sub-senses, and printing a repeat says nothing new.

    Each entry carries the examples recorded on the sense it came from, so the
    renderer can keep an example beside the use it illustrates.

    Returns ``(heading, entries)`` pairs.
    """
    groups: Dict[str, List[SenseEntry]] = {}    # heading -> child entries
    # (kind, text, group key, examples). A group's key is the *raw* parent
    # gloss, which render() may alter (it trims and collapses whitespace,
    # escapes markup, drops a relation prefix, wraps a form-of target in
    # [ref]); the key travels beside the rendered heading so the children can
    # be looked up by the string they were stored under.
    items: List[Tuple[str, str, str, List[str]]] = []
    seen: Set[str] = set()

    def fresh(text: str) -> bool:
        key = text.casefold().strip()
        if not key or key in seen:
            return False
        seen.add(key)
        return True

    for sense in senses:
        if not isinstance(sense, dict):
            continue
        parts = [str(g) for g in (sense.get("glosses") or []) if g]
        if not parts:
            continue
        markers = _sense_markers(sense.get("tags"), profile)
        examples = _extract_examples(sense)

        def render(part: str) -> str:
            # drop the relation phrase the icon already conveys, escape the free
            # text, then link the headword a form-of or alt-of sense names
            part = _strip_relation_prefix(part, sense.get("tags"))
            return _link_form_targets(escape_dsl(part), sense, known, word)

        if len(parts) == 1:
            if fresh(parts[0]):
                items.append(("plain", markers + render(parts[0]), "", examples))
            continue
        parent, children = parts[0], parts[1:]
        if parent not in groups:
            if not fresh(parent):
                continue
            groups[parent] = []
            items.append(("group", render(parent), parent, []))
        if children and fresh(children[0]):
            groups[parent].append((markers + render(children[0]), examples))
        for child in children[1:]:
            if fresh(child):
                groups[parent].append((render(child), []))

    return [
        (text, groups[key]) if kind == "group" else ("", [(text, ex)])
        for kind, text, key, ex in items
    ]


_EXAMPLE_MAX_CHARS = 200

# Two tokens are considered the same word when their first this-many characters
# match, which pairs a headword with a regular inflection (swop/swopping,
# run/running) without a stemmer. Kept short so it does not over-match.
_MIN_STEM = 3

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# At most this many examples survive on one sense; the shortest are kept, which
# favours a crisp illustrative phrase over a paragraph-long quotation.
_EXAMPLE_MAX_PER_SENSE = 1

# Wiktionary cross-reference bookkeeping, not usage: the bare "Citations:work."
# placeholder and the "For quotations using this term, see Citations:work."
# sentence that wraps it.
_CITATION_RE = re.compile(r"Citations?:|^see\s+citations?:", re.IGNORECASE)

# Pre-modern spelling and grammar: a long s, the Early Modern -e endings and
# pronouns of Shakespeare-era quotations, and the Middle English inflections that
# survive in Chaucer. Modern usage contains none of them, so matching any marks
# a quote as archaic.
_ARCHAIC_MARKERS = (
    "ſ", "haue", "hath", "thou", "thee", "thy", "doth", "sayde", "vnto",
    "worke", "euery", "wee ", "knowe", "theſe",
    "wolde", "sholde", "seyde", "kyng", "hyre", "yow ", "dooth",
    "my hede", "nat ", "wher ",
)


def _example_is_usable(text: str) -> bool:
    """Whether an example is worth showing a modern learner.

    Archaic quotations (Early Modern and Middle English) and ``Citations:``
    pointers are unreadable or say nothing, and the source records far more of
    them than modern usage; they are dropped so the few current examples are not
    drowned out.
    """
    if "ſ" in text:                     # long s: an archaic quote
        return False
    if _CITATION_RE.search(text):
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in _ARCHAIC_MARKERS):
        return False
    return True


def _truncate_example(text: str, limit: int = _EXAMPLE_MAX_CHARS) -> str:
    """Shorten an over-long example at a word boundary.

    Wiktionary quotes can run to a whole paragraph; a learner wants the phrase
    that shows the word in use, not the surrounding essay, so an example longer
    than ``limit`` is cut at the last space that fits and an ellipsis appended.
    """
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cut + " …"


def _example_shows_word(text: str, word: str, forms: Sequence[str] = ()) -> bool:
    """Whether an example actually uses the headword (or a form of it).

    An example that does not contain the word proves nothing about it, so it is
    dropped rather than shown. Two matches count:

    * an exact token match against the headword or any listed ``forms[]`` — this
      catches irregular forms (``ran``, ``children``) that share no stem with
      the headword, and
    * a shared stem of at least ``_MIN_STEM`` characters against the headword
      alone, which pairs it with a regular inflection the ``forms[]`` may not
      list (``swop``/``swopping``, ``run``/``running``).
    """
    tokens = [t.lower() for t in _WORD_RE.findall(text)]
    if not tokens:
        return False
    token_set = set(tokens)

    def strip_label(form: str) -> str:
        return re.split(r"\s+\(", form, maxsplit=1)[0].strip().lower()

    exact = {strip_label(str(word or ""))}
    exact.discard("")
    exact.update(
        f for f in (strip_label(v) for v in forms) if f
    )
    if exact & token_set:
        return True

    head = str(word or "").strip().lower()
    if len(head) < _MIN_STEM:
        return False
    for candidate in {head, *head.split()}:
        if len(candidate) < _MIN_STEM:
            continue
        n = _MIN_STEM
        if any(candidate[:n] == token[:n] for token in tokens):
            return True
    return False


def _sense_examples(
    raw: Sequence[str], word: str, forms: Sequence[str] = ()
) -> List[str]:
    """Optional-zone lines for one sense's examples.

    Only examples that actually contain the headword (or one of the record's
    forms) are kept, and archaic quotations or "Citations:" placeholders are
    dropped — neither says anything about how the word is used today. The
    survivors are ordered shortest-first and capped, because a sense needs one
    crisp illustration, not every quotation the source happens to record.
    """
    usable = [
        text
        for text in (str(t).strip() for t in raw)
        if text and _example_is_usable(text) and _example_shows_word(text, word, forms)
    ]
    usable.sort(key=len)
    return [
        f"\t[ex]{escape_dsl(_truncate_example(text))}[/ex]"
        for text in usable[:_EXAMPLE_MAX_PER_SENSE]
    ]


def _record_transcription(record: dict, profile: LangProfile) -> str:
    """The IPA/enPR transcription of one record, as inline DSL (or "").

    The common IPA value is emitted without a name — the line it lands on is
    always a transcription — while a less common notation (enPR) keeps its label
    so the two are distinguishable.
    """
    for field in profile.pron_fields:
        for sound in record.get("sounds") or []:
            if isinstance(sound, dict) and sound.get(field):
                value = escape_dsl(str(sound[field]))
                if field in _UNLABELLED_PRON_FIELDS:
                    return value
                return f"{_PRON_LABEL.get(field, field.upper())}: {value}"
    return ""


def _group_by_pos(records: Sequence[dict]) -> List[Tuple[str, List[int]]]:
    """Group record indices by part of speech, preserving first-seen order.

    A headword's records can arrive interleaved (``noun``, ``verb``, ``noun``),
    but an article should read one part of speech at a time, so records that
    share a POS are merged into a single block under one heading.
    """
    order: List[str] = []
    groups: Dict[str, List[int]] = {}
    for i, record in enumerate(records):
        pos = str(record.get("pos") or "")
        if pos not in groups:
            groups[pos] = []
            order.append(pos)
        groups[pos].append(i)
    return [(pos, groups[pos]) for pos in order]


def render_card(
    records: Sequence[dict],
    audio: AudioPlan,
    profile: LangProfile,
    known: Optional[Set[str]] = None,
) -> str:
    """Render a headword's records as one DSL card.

    A card is one headword whose records are its parts of speech (``run`` is a
    verb and a noun). Records that share a part of speech are merged into one
    block, so an interleaved ``noun, verb, noun`` reads ``noun, verb``. The
    visible article is part of speech → forms → senses; examples and
    cross-references go into the DSL optional zone (``[*]…[/*]``), which the
    reader expands on demand.

    A single transcription shared across the card is hoisted above the first
    part of speech; differing ones stay under their own part of speech. Audio is
    never hoisted and never repeated: each file prints once, under the first
    part of speech that references it.
    """
    records = [r for r in records if r]
    if not records:
        return ""

    # Audio must be planned exactly once per record (planning mutates the
    # plan's referenced set), so plan for all of them before laying anything
    # out and share the result between the hoisted and per-POS layouts.
    transcriptions = [_record_transcription(record, profile) for record in records]
    record_audio = [list(audio.plan(record)) for record in records]

    blocks = _group_by_pos(records)

    # The transcription is hoisted above the first POS whenever the whole card
    # has a single one — including a card that is a single record, so the common
    # word does not place its transcription inconsistently below the part of
    # speech; audio is never hoisted but is de-duplicated card-wide, so a word
    # whose parts of speech share one recording prints it once.
    distinct_tr = {t for t in transcriptions if t}
    hoist = len(distinct_tr) == 1

    form_lines: List[List[str]] = []
    words: List[str] = []
    forms_by_record: List[List[str]] = []
    for record in records:
        forms = collect_profile_forms(record, profile)
        words.append(str(record.get("word") or ""))
        forms_by_record.append(forms)
        form_lines.append(
            []
            if (not forms or profile.strip_forms)
            else ["\t[i]" + escape_dsl(", ".join(forms)) + "[/i]"]
        )

    # Cross-references: one card-level line, de-duplicated and capped, rather
    # than one "See also" per record.
    refs_seen: List[str] = []
    for record in records:
        if not known:
            break
        for ref in _cross_refs(record, known):
            if ref not in refs_seen:
                refs_seen.append(ref)
            if len(refs_seen) >= 8:
                break

    # Each audio file is emitted once, under the first block that references it.
    # Audio rides on the pronunciation line — the transcription and its playback
    # controls together — so "IPA next to the audio" holds whether the
    # transcription is hoisted or sits under a part of speech.
    shown_audio: Set[str] = set()

    def audio_bits(idxs: Sequence[int]) -> List[str]:
        bits: List[str] = []
        for i in idxs:
            for name in record_audio[i]:
                if name not in shown_audio:
                    shown_audio.add(name)
                    bits.append(_audio_ref(name))
        return bits

    lines: List[str] = []
    if hoist:
        hoisted_audio = audio_bits(range(len(records)))
        pron = next(iter(distinct_tr))
        if hoisted_audio:
            pron += "  " + "  ".join(hoisted_audio)
        lines.append("\t[com]" + pron + "[/com]")

    # A blank line separates consecutive parts of speech, so their sections read
    # as blocks rather than one list. It goes strictly between them: no blank
    # before the first part of speech, even when a hoisted transcription sits
    # above it.
    first_pos_seen = False
    for pos, idxs in blocks:
        if pos:
            if first_pos_seen:
                lines.append("")
            first_pos_seen = True
            lines.append(f"\t[p]{escape_dsl(pos)}[/p]")
        # forms: first record of the block that carries any
        for i in idxs:
            if form_lines[i]:
                lines.extend(form_lines[i])
                break

        # pronunciation: the transcription of the block's records (one per
        # distinct value) with any not-yet-shown audio; hoisted when the whole
        # card shares one transcription. Each distinct transcription takes the
        # audio of the first record that carries it, so a multi-record block
        # without a hoist still keeps its audio beside the pronunciation.
        if not hoist:
            seen_tr: Set[str] = set()
            for i in idxs:
                tr = transcriptions[i]
                if tr and tr not in seen_tr:
                    seen_tr.add(tr)
                    bits = audio_bits([i])
                    pron = tr + ("  " + "  ".join(bits) if bits else "")
                    lines.append("\t[com]" + pron + "[/com]")
            block_audio = audio_bits([i for i in idxs if not transcriptions[i]])
            if block_audio:
                lines.append("\t[com]" + "  ".join(block_audio) + "[/com]")

        # senses: merged across the block's records. Every sense sits at [m1]
        # (one indentation level under its part of speech); a grouped parent
        # gloss is [m1] with its sub-senses at [m2], one level deeper. The
        # engine renders [mN] by indentation, so this nests the children under
        # the parent without a global sense counter. Each leaf sense is prefixed
        # with a bullet; the sense text is already escaped and may carry inline
        # icon markup, so it is not escaped again here.
        #
        # A parent heading (a sense that carries sub-senses) is numbered "1. ",
        # "2. "…, counted per part of speech, so the top-level sections of a long
        # article read as an outline. A heading with no children is an ordinary
        # sense and is left bulleted but unnumbered, so a card that has no groups
        # (most cards) is unchanged.
        group_nom = 0
        for i in idxs:
            for heading, entries in _group_senses(
                records[i].get("senses") or [], profile, known, words[i]
            ):
                if heading:
                    if entries:
                        group_nom += 1
                        heading = f"{group_nom}. {heading}"
                    lines.append(f"\t[m1]{heading}[/m]")
                level = 2 if heading else 1
                for text, raw_examples in entries:
                    lines.append(f"\t[m{level}]\u2022 {text}[/m]")
                    examples = _sense_examples(raw_examples, words[i], forms_by_record[i])
                    if examples:
                        lines.append("\t[*]")
                        lines.extend(examples)
                        lines.append("\t[/*]")

    if refs_seen:
        links = ", ".join("[ref]" + escape_dsl(r) + "[/ref]" for r in refs_seen)
        lines.append("\t[*]")
        lines.append("\t[com]See also: " + links + "[/com]")
        lines.append("\t[/*]")

    return "\n".join(lines)


def render_record(
    record: dict,
    audio: AudioPlan,
    profile: LangProfile,
    known: Optional[Set[str]] = None,
) -> str:
    """Render one record as a card (a thin wrapper over :func:`render_card`)."""
    return render_card([record], audio, profile, known)


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

_PREVIEW_TAGS = {
    "p": ("span", {"class": "pos"}),
    "m": ("div", {"class": "sense"}),
    "ex": ("div", {"class": "example"}),
    "com": ("div", {"class": "note"}),
    "b": ("b", {}),
    "i": ("i", {}),
    "u": ("u", {}),
    "ref": ("a", {"href": "#"}),
}

def dsl_to_html(text: str) -> str:
    """Render the DSL subset this tool emits as HTML (for preview only).

    Opening and closing tags are tracked together: a closing tag closes the
    element its opening counterpart produced, so the preview nests exactly as
    the DSL does instead of leaving every block element open.
    """
    from html import escape as _h

    out: List[str] = []
    stack: List[str] = []   # HTML element names, outermost first
    i = 0

    def closing_element(name: str) -> str:
        base = re.match(r"m\d*", name)
        if base and base.group(0):
            return "span"
        if name == "*" or name == "opt":
            return "div"
        if name in _PREVIEW_TAGS:
            return _PREVIEW_TAGS[name][0]
        return ""

    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            out.append(_h(text[i + 1]))
            i += 2
            continue
        if ch == "[":
            close = text.find("]", i)
            if close == -1:
                out.append(_h(ch))
                i += 1
                continue
            inner = text[i + 1:close]
            if inner.startswith("/"):
                # closing tag: close its element if it is the innermost open one
                name = inner[1:].strip()
                element = closing_element(name)
                if element and stack and stack[-1] == element:
                    stack.pop()
                    out.append(f"</{element}>")
                elif element and element in stack:
                    # unbalanced input: close everything above it too
                    while stack:
                        top = stack.pop()
                        out.append(f"</{top}>")
                        if top == element:
                            break
                i = close + 1
                continue
            # opening tag
            base = re.match(r"m\d*", inner)
            key = base.group(0) if base else inner
            if key.startswith("m"):
                out.append('<span class="sense">')
                stack.append("span")
            elif key == "*":
                out.append('<div class="optional"><span class="optlabel">[optional]</span> ')
                stack.append("div")
            elif key == "s":
                # the filename is the tag's own text; a bundled sense-marker
                # icon is inlined as a data URI so the standalone preview file
                # shows it, any other file stays the audio note glyph
                end = text.find("[/s]", close + 1)
                if end != -1:
                    name = text[close + 1:end]
                    if name in _ICON_FILES:
                        out.append(
                            f'<img class="senseicon" alt="{_h(name)}" '
                            f'src="{_icon_data_uri(name)}">'
                        )
                    else:
                        out.append(
                            '<span class="audio">&#9835; ' + _h(name) + "</span>"
                        )
                    i = end + 4
                    continue
            elif key in _PREVIEW_TAGS:
                tag, attrs = _PREVIEW_TAGS[key]
                attr = "".join(f' {k}="{_h(v)}"' for k, v in attrs.items())
                out.append(f"<{tag}{attr}>")
                stack.append(tag)
            i = close + 1
            continue
        out.append(_h(ch))
        i += 1

    # close anything the input left open, so no article can swallow the next
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)


def render_preview(name: str, dsl_text: str, dest_html: str) -> None:
    """Write a human-readable HTML preview of the generated cards."""
    lines = dsl_text.splitlines()
    cards: List[Tuple[str, List[str]]] = []
    headword: Optional[str] = None
    body: List[str] = []
    for line in lines:
        if line.startswith("#"):
            continue
        if line and not line[0].isspace():
            if headword is not None:
                cards.append((headword, body))
            headword, body = line, []
        elif headword is not None:
            body.append(line)
    if headword is not None:
        cards.append((headword, body))

    parts = [
        "<!doctype html><meta charset='utf-8'>",
        f"<title>{name} preview</title>",
        "<style>body{font-family:sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}"
        "h2{border-bottom:1px solid #ccc;margin-top:2rem}.pos{font-weight:bold;color:#0a6}"
        ".sense{margin:.2em 0 .2em 1em}.example{color:#555;margin-left:2em;font-style:italic}"
        ".note{color:#777;font-size:.9em}.audio{color:#a0a}"
        ".senseicon{height:1em;vertical-align:-.15em}"
        ".optional{border-left:3px solid #cc0;background:#ffd;padding:.4em .6em;margin:.6em 0}"
        ".optlabel{color:#880;font-size:.8em;text-transform:uppercase}</style>",
        f"<h1>{name} — preview</h1>",
    ]
    for headword, body in cards:
        parts.append(f"<h2>{dsl_to_html(headword)}</h2>")
        parts.append("<div>" + "<br>".join(dsl_to_html(b) for b in body) + "</div>")
    with open(dest_html, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")


# ---------------------------------------------------------------------------
# Build pipeline
# ---------------------------------------------------------------------------

def _language_name(record: Optional[dict], code: str) -> str:
    if record and record.get("lang"):
        return str(record["lang"])
    return code.upper()


def _resolve_inputs(
    args, want_audio: bool
) -> Tuple[Snapshot, str, Optional[str], Optional[Set[str]], Optional[str]]:
    """Resolve the snapshot both the build and the audio prefetcher read.

    Checks the pinned dump date against kaikki.org (unless a local ``--jsonl`` is
    given), downloads the JSONL and the audio archive into the cache if they are
    not there yet, and indexes the archive's member names (itself cached beside
    the archive). Returns
    ``(snapshot, jsonl_path, audio_path, available_names, download_dir)``.

    Every stage is a cached, sidecar-verified download, so a second run over the
    same snapshot does no network I/O at all.
    """
    if not args.jsonl:
        if not args.dump_date:
            raise SystemExit("--dump-date is required when downloading (or pass --jsonl)")
        if not args.skip_date_check:
            try:
                current = _fetch_dump_date(args.timeout)
            except (urllib.error.URLError, TimeoutError) as exc:
                raise SystemExit(f"could not verify snapshot date: {exc}")
            if current and current != args.dump_date:
                raise SystemExit(
                    f"pinned dump date {args.dump_date} does not match the current "
                    f"kaikki.org snapshot ({current}); re-run with --dump-date {current} "
                    f"or pass --skip-date-check"
                )

    snapshot = Snapshot(args.dump_date, args.cache_dir, args.jsonl_url, args.audio_url)
    jsonl_path = args.jsonl
    if not jsonl_path:
        jsonl_path = download_cached(
            snapshot.jsonl_url, snapshot.jsonl_path, args.force_download, args.timeout
        )

    audio_path: Optional[str] = None
    available: Optional[Set[str]] = None
    if want_audio:
        # Resolve the archive up front so planning only references recordings
        # it actually holds; a missing file is logged and left out instead of
        # becoming a dead link, and does not use up a per-word slot.
        audio_path = args.audio_tar
        if not audio_path:
            audio_path = download_cached(
                snapshot.audio_url, snapshot.audio_path, args.force_download, args.timeout
            )
        scan = Progress("scanning audio archive")
        available = available_audio_keys(
            audio_path, scan, snapshot.dir, args.force_audio_index
        )
        scan.done()
        if not available:
            print(
                f"warning: no audio found in {audio_path}; audio will not be bundled",
                file=sys.stderr,
            )
    download_dir = None
    if want_audio and not args.no_audio_download:
        download_dir = os.path.join(snapshot.dir, "audio-cache")
    return snapshot, jsonl_path, audio_path, available, download_dir


def build(args) -> Report:
    report = Report()

    want_audio = (not args.no_audio) and args.audio_per_word > 0
    snapshot, jsonl_path, audio_path, available, download_dir = _resolve_inputs(
        args, want_audio
    )

    downloader = args.audio_downloader
    if downloader is None and download_dir is not None:
        timeout = args.timeout

        def downloader(url: str, dest: str) -> str:  # type: ignore[misc]
            return download_cached(url, dest, timeout=timeout)

    audio = AudioPlan(
        args.audio_per_word, args.audio_lang, want_audio, available, downloader
    )
    audio.download_dir = download_dir

    header_name = args.name or f"kaikki-{args.source_lang}"

    out_lines: List[str] = []
    header_lines: List[str] = []

    profile = get_lang_profile(args.source_lang)

    current_word: Optional[str] = None
    current_records: List[dict] = []
    source_lang_name = args.source_lang.upper()
    # Words already emitted. In sample mode this is the only set cross-references
    # may point at, so a sample never links to a headword it does not contain.
    known: Set[str] = set()

    def emit(word: str, records: List[dict]) -> None:
        nonlocal source_lang_name
        if not records:
            return
        record = records[0]
        source_lang_name = _language_name(record, args.source_lang)
        headwords = [clean_headword(word)]
        if args.include_inflections:
            for form in collect_profile_forms(record, profile):
                form_word = re.split(r"\s+\(", form, maxsplit=1)[0].strip()
                if form_word and form_word != word:
                    headwords.append(clean_headword(form_word))
        body = render_card(records, audio, profile, known)
        if not body:
            return
        out_lines.append("\n".join(headwords))
        out_lines.append(body)
        report.cards += 1
        report.kept_records += len(records)
        known.add(word)

    def flush() -> None:
        nonlocal current_word, current_records
        if not current_records:
            return
        emit(str(current_word), current_records)
        current_word, current_records = None, []

    if args.sample:
        # Single bounded pass over the snapshot: the whole-file selection the
        # full build needs would make a sample take minutes, and a sample only
        # has to show article shape.
        sampling = Progress("sampling headwords")
        sampled = sample_headwords(
            jsonl_path, args.source_lang, args.sample, args.sample_mode, sampling, report
        )
        sampling.done()
        for record in sampled:
            word = str(record.get("word"))
            if word != current_word:
                flush()
                current_word = word
            current_records.append(record)
        flush()
    else:
        # Full build: the indexed-headword set drives cross-reference safety, so
        # every reference points at a word the dictionary actually contains.
        selecting = Progress("selecting headwords")
        known = select_headwords(jsonl_path, args.source_lang, None, args.sample_mode, selecting)
        selecting.done()

        rendering = Progress("rendering")
        for _, record in iter_records(jsonl_path, rendering):
            if record is None:
                report.skipped_malformed += 1
                continue
            if record.get("lang_code") != args.source_lang:
                report.out_of_pair += 1
                continue
            if not is_lexical(record) or is_inflected(record):
                if is_inflected(record):
                    report.skipped_inflected += 1
                else:
                    report.skipped_nonlexical += 1
                continue
            word = str(record.get("word"))
            if word != current_word:
                flush()
                current_word = word
            current_records.append(record)
        flush()
        rendering.done()

    if report.cards == 0:
        raise SystemExit(
            f"no {args.source_lang!r} headwords were found in this snapshot"
        )

    header_lines.append(f'#NAME "{header_arg(header_name)}"')
    header_lines.append(f'#INDEX_LANGUAGE "{header_arg(source_lang_name)}"')
    header_lines.append(f'#CONTENTS_LANGUAGE "{header_arg(source_lang_name)}"')

    about = [
        clean_headword("About this dictionary"),
        "\t[com]Source: Wiktionary (via kaikki.org / wiktextract)[/com]",
        f"\t[com]License: {WIKTIONARY_LICENSE} (attribution required, share-alike)[/com]",
        f"\t[com]Citation: {escape_dsl(WIKTEXTRACT_CITATION)}[/com]",
        f"\t[com]Snapshot dump date: {escape_dsl(args.dump_date or 'unknown')}[/com]",
        f"\t[com]Language: {escape_dsl(source_lang_name)} ({escape_dsl(args.source_lang)})[/com]",
        "\t[com]Generated by scripts/kaikki-to-dsl.py; this is a derivative work.[/com]",
        "\t[com]Sense icons (Material Symbols, Google; Apache-2.0):[/com]",
    ]
    for icon_name, meaning in _ICON_LEGEND:
        about.append(f"\t[com]{_icon_ref(icon_name)} {escape_dsl(meaning)}[/com]")


    dsl_text = "\n".join(header_lines) + "\n\n" + "\n".join(about) + "\n" + "\n".join(out_lines) + "\n"

    os.makedirs(args.out_dir, exist_ok=True)
    dz_path = os.path.join(args.out_dir, header_name + ".dsl.dz")
    # The resource bundle is named after the dictionary file *without* the
    # dictzip suffix: the reader looks for "<base>.dsl.files.zip" first
    # (dsl.cc:1743, where baseName drops ".dsl.dz"), so that is the canonical
    # name; "<base>.dsl.dz.files.zip" is only its fallback.
    res_base = os.path.join(args.out_dir, header_name + ".dsl")
    with open(dz_path, "wb") as f:
        f.write(make_dictzip(encode_dsl(dsl_text)))

    if args.preview:
        preview_path = os.path.join(args.out_dir, header_name + ".preview.html")
        render_preview(header_name, dsl_text, preview_path)
        print(f"wrote {preview_path}", file=sys.stderr)

    # Resource bundle: the sense-marker icons (always) plus pronunciation audio
    # (when enabled), written as one archive by default or a directory on request.
    # Bundling is unconditional because the about card always references the icon
    # set, so the icons must resolve even when audio is disabled.
    with tempfile.TemporaryDirectory(prefix="kaikki-res-") as tmp:
        for name in _ICON_FILES:
            shutil.copyfile(os.path.join(_ICON_ASSET_DIR, name), os.path.join(tmp, name))
        if want_audio and audio.referenced:
            fetched = {
                name: path
                for name, path in audio.local.items()
                if name in audio.referenced and os.path.isfile(path)
            }
            for name, path in fetched.items():
                shutil.copyfile(path, os.path.join(tmp, name))
            wanted = {
                name: list(audio.aliases.get(name, []))
                for name in sorted(audio.referenced)
                if name not in fetched
            }
            batching = Progress("bundling audio", every=1, total=len(audio.referenced))
            found, missing = extract_audio(audio_path, wanted, tmp, batching)
            batching.done()
            report.audio_found = len(fetched) + found
            if missing:
                print(
                    f"warning: {len(missing)} planned audio file(s) were not found in "
                    f"the archive while bundling",
                    file=sys.stderr,
                )
        if args.audio_layout == "zip":
            write_audio_zip(tmp, res_base + ".files.zip")
        else:
            dest_dir = res_base + ".files"
            os.makedirs(dest_dir, exist_ok=True)
            for name in sorted(os.listdir(tmp)):
                src = os.path.join(tmp, name)
                if os.path.isfile(src):
                    with open(src, "rb") as fsrc, open(os.path.join(dest_dir, name), "wb") as fdst:
                        fdst.write(fsrc.read())

    report.missing_audio = len(audio.missing)
    print(f"wrote {dz_path}", file=sys.stderr)
    return report


# ---------------------------------------------------------------------------
# Audio prefetch
# ---------------------------------------------------------------------------

class AudioWishlist:
    """Decides, one headword at a time, which recordings a build would fetch.

    Handed to :class:`AudioPlan` in place of the cached downloader, so planning
    runs the real selection logic and simply records what it *would* have asked
    for instead of asking. Nothing reaches the network from here; the caller
    fetches what :meth:`scan` yields, as it yields it.

    ``probed`` is the raw record of everything planning asked for, which is a
    superset of what any article ends up referencing -- an unresolved candidate
    does not use up a per-word slot, so planning keeps looking past it.
    :meth:`consider` narrows that to the referenced subset.
    """

    def __init__(
        self,
        download_dir: str,
        per_word: int,
        preferred_lang: Optional[str],
        available: Optional[Set[str]] = None,
        dead: Optional[Set[str]] = None,
    ) -> None:
        self.download_dir = download_dir
        self.per_word = per_word
        self.preferred_lang = preferred_lang
        # A private copy of the archive's names: a wanted-but-absent recording is
        # added to it so it counts against the per-word cap (see ``consider``).
        self.reachable: Set[str] = set(available or ())
        # recordings a previous run found permanently gone, by match key
        self.dead: Set[str] = set(dead or ())
        self.probed: Dict[str, str] = {}  # destination path -> url, in file order
        self.satisfied: Set[str] = set()  # already in the cache before this run
        # A destination is offered once per run. A failure is left for the next
        # run rather than retried here: a rate-limited URL should be left alone.
        self.offered: Set[str] = set()
        self.failed: Set[str] = set()
        # the headword currently being offered, its full candidate set, and the
        # fallback offers a failure has produced for it; the caller drains the
        # latter (see mark_failed)
        self._batch: Sequence[dict] = ()
        self._batch_probed: Set[str] = set()
        self.replacements: List[Tuple[str, str]] = []

    def __call__(self, url: str, dest: str) -> None:
        if os.path.isfile(dest):
            self.satisfied.add(dest)
            return
        self.probed.setdefault(dest, url)
        # ``AudioPlan._final_name`` disambiguates two different recordings that
        # share a basename by suffixing a digest of the source. Enumeration and
        # the build agree on that order only while they see the same records, so
        # a suffixed name also gets recorded under the plain one: whichever name
        # the build settles on, the file is there and no refetch is needed.
        final = os.path.basename(dest)
        plain = _url_basename(url)
        stem, ext = os.path.splitext(final)
        if plain and plain != final and plain.endswith(ext):
            if stem.startswith(plain[: -len(ext)] if ext else plain):
                alias = os.path.join(self.download_dir, plain)
                if not os.path.isfile(alias):
                    self.probed.setdefault(alias, url)

    def _plan(self, records: Sequence[dict]) -> Set[str]:
        audio = AudioPlan(
            self.per_word, self.preferred_lang, True, self.reachable, self
        )
        audio.download_dir = self.download_dir
        for record in records:
            audio.plan(record)
        return audio.referenced

    def consider(self, records: Sequence[dict]) -> List[Tuple[str, str]]:
        """What one headword's records need fetched, as (destination, url).

        The batch is planned twice. The first pass records every candidate the
        archive lacks. The second treats those as obtainable and replans, which
        is precisely what the build will see once the cache holds them: an
        unresolved candidate does not consume a per-word slot, so the first pass
        alone would keep looking past a file that will in fact be there, and
        would fetch every later candidate too. Replanning through the same
        :meth:`AudioPlan.plan` rather than re-deriving the choice keeps the two
        in step by construction.

        Only the headword's own records are needed, and they are contiguous in
        the snapshot, so this decides each headword as it is read rather than
        waiting for a whole-dictionary pass.
        """
        before = len(self.probed)
        self._plan(records)
        for dest in list(self.probed)[before:]:
            self._batch_probed.add(dest)
            key = _audio_match_key(os.path.basename(dest))
            if key in self.dead:
                # recorded as gone in an earlier run. Deliberately not added to
                # ``reachable``: it will not be there when the build runs either,
                # so the build slot-fills past it, and the replacement it settles
                # on has to be fetched here for the article to come out whole.
                continue
            self.reachable.add(key)
        referenced = self._plan(records)
        offers: List[Tuple[str, str]] = []
        # Over the headword's *whole* candidate set, not just what this pass
        # probed: on a replan after a failure, what needs offering is a candidate
        # the first pass already knew about but had no reason to want yet.
        for dest in self._batch_probed:
            if os.path.basename(dest) not in referenced:
                continue
            # a recording another headword already asked for, or one that has
            # already failed this run, is not offered twice: a rate-limited URL
            # should be retried in the next run, not hammered within this one
            if dest in self.offered or dest in self.failed or os.path.isfile(dest):
                continue
            if _audio_match_key(os.path.basename(dest)) in self.dead:
                continue
            self.offered.add(dest)
            offers.append((dest, self.probed[dest]))
        return offers

    def mark_failed(self, dest: str) -> None:
        """Record a fetch that did not land, and take it out of ``reachable``.

        ``reachable`` stands in for what the build will find, so a name that
        stayed in it after a failure would keep a later headword from slot-
        filling around the gap: that headword would be planned as if the file
        were there, and the recording it actually falls back to would never be
        offered. Withdrawing it lets the next headword consider the same
        candidate list the build will.

        The headword that asked for the file is replanned as well. Both planning
        passes assume every probed candidate lands, so the plan it holds is the
        one for a *successful* fetch; now that this one is known to have failed,
        the build will slot-fill past it, and the recording it falls back to has
        to be fetched here or the article keeps the gap. Its replacement offers
        land in :attr:`replacements` for the caller to drain.
        """
        self.failed.add(dest)
        self.reachable.discard(_audio_match_key(os.path.basename(dest)))
        self._replan_current()

    def mark_dead(self, dest: str) -> None:
        """Record a file that is permanently gone, so no run ever requests it again.

        The headword is replanned exactly as for a transient failure -- the build
        will slot-fill past the gap either way -- but the file leaves the dead
        list, which is what lets a later run report the cache finished instead of
        retrying a 404 forever.

        The withdrawal from ``reachable`` matters here as much as it does for a
        transient failure: a file that only just turned out to be dead was added
        to the set when this headword was first planned, and a replan that still
        believed in it would re-select the dead file and fetch no replacement.
        """
        self.dead.add(_audio_match_key(os.path.basename(dest)))
        self.failed.add(dest)
        self.reachable.discard(_audio_match_key(os.path.basename(dest)))
        self._replan_current()

    def _replan_current(self) -> None:
        if self._batch:
            self.replacements.extend(self.consider(self._batch))

    def take_replacements(self) -> List[Tuple[str, str]]:
        """Drain the offers :meth:`mark_failed` queued, leaving the queue empty."""
        queued, self.replacements = self.replacements, []
        return queued

    def scan(
        self, jsonl_path: str, source_lang: str, sample: Optional[int],
        sample_mode: str,
    ) -> Iterator[Tuple[str, str]]:
        """Yield (destination, url) as each headword's recordings are decided.

        Batches the records by headword the way a build does, so the per-word cap
        is applied over exactly the same set of candidates. Headwords are
        contiguous in the snapshot, so nothing has to be buffered beyond the
        batch in hand.
        """
        if sample:
            sampling = Progress("sampling headwords")
            records: Iterable[dict] = sample_headwords(
                jsonl_path, source_lang, sample, sample_mode, sampling
            )
            sampling.done()
        else:
            records = iter_candidate_records(jsonl_path, source_lang)

        batch: List[dict] = []
        current: Optional[str] = None
        for record in records:
            word = str(record.get("word"))
            if word != current:
                # kept so a failure can be replanned against this headword
                self._batch = batch
                self._batch_probed = set()
                yield from self.consider(batch)
                batch = []
                current = word
            batch.append(record)
        self._batch = batch
        self._batch_probed = set()
        yield from self.consider(batch)


def _collect_wishlist(
    args,
    jsonl_path: str,
    available: Optional[Set[str]],
    download_dir: str,
    dead: Optional[Set[str]] = None,
) -> AudioWishlist:
    """A wishlist over one snapshot, driven with the build's own audio options.

    Which files are wanted follows from the same
    :meth:`AudioPlan.plan` the build uses, over the same records batched the
    same way, so the file *names* here are the names the build references. That
    is why the audio-affecting options (``--audio-per-word``, ``--audio-lang``)
    have to match the build's: a different per-word cap or preference changes
    which candidates are considered and therefore which files are wanted.

    ``dead`` carries the match keys an earlier run found permanently gone, so
    they are neither requested again nor counted as obtainable.

    Nothing is decided here; :meth:`AudioWishlist.scan` yields each headword's
    files as it reads them, so the caller can fetch them immediately.
    """
    return AudioWishlist(
        download_dir, args.audio_per_word, args.audio_lang, available, dead
    )


class TabularLog:
    """A ``name<TAB>url[\\TAB reason]`` record of what a run found.

    Written and flushed per line, so a run that is interrupted still leaves a
    valid record -- which is the point when the run is being cut short by a rate
    limit rather than by finishing.

    ``truncate`` suits the manifest, which describes one run and must not
    accumulate. The dead-file record is cache *state* that carries across runs,
    so it is opened for append and skips names it already holds; that is what
    keeps a file that is gone on Wikimedia from being requested on every future
    run.

    ``header`` lines are written ahead of the first entry, and only when the
    file is created rather than appended to. They exist for the shard files
    (see :class:`ShardSet`), which are handed to another machine and have to
    say how to fetch themselves; the manifest is only ever read by this tool and
    is left in the plain format the tests and the docs describe.
    """

    def __init__(
        self,
        path: str,
        download_dir: str,
        truncate: bool = True,
        header: Sequence[str] = (),
    ) -> None:
        self.path = path
        self.download_dir = download_dir
        self.count = 0  # entries written by this run
        self.names: Set[str] = set()  # every name the file holds
        self._truncate = truncate
        self._header = list(header)
        # read eagerly even though the write is lazy: the caller consults the
        # names already held before offering anything
        if not truncate and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.names = {
                    line.split("\t", 1)[0]
                    for line in f
                    if line.strip() and not line.startswith("#")
                }
        # opened on the first entry, so a run with nothing to record does not
        # leave an empty file behind, and truncating still happens before any
        # line is written
        self._stream = None

    def add(self, dest: str, url: str, reason: Optional[str] = None) -> bool:
        """Record one file. False if the name is already held."""
        name = os.path.relpath(dest, self.download_dir).replace(os.sep, "/")
        if name in self.names:
            return False
        if self._stream is None:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            self._stream = open(
                self.path, "w" if self._truncate else "a", encoding="utf-8"
            )
            if self._truncate:
                for line in self._header:
                    self._stream.write(line + "\n")
                self._stream.flush()

        fields = [name, url] + ([reason] if reason else [])
        self._stream.write("\t".join(fields) + "\n")
        self._stream.flush()
        self.names.add(name)
        self.count += 1
        return True

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def describe(self) -> List[str]:
        """How much work this record turned out to hold, for the run's summary."""
        return [f"  to download:    {self.count:,}"]


def shard_paths(manifest_path: str, count: int) -> List[str]:
    """Where the shards of ``manifest_path`` go.

    Derived from the manifest so that one option still names the whole job and
    the names of its parts follow from it: ``missing.tsv`` becomes
    ``missing.shard-01-of-04.tsv``.
    """
    base, ext = os.path.splitext(manifest_path)
    width = len(str(count))
    return [
        f"{base}.shard-{i:0{width}d}-of-{count}{ext or '.tsv'}"
        for i in range(1, count + 1)
    ]


class ShardSet:
    """The outstanding audio work divided into N disjoint shard files.

    Stands in for the manifest where the prefetcher records what it found, so
    the run itself is unchanged: the work is offered one file at a time and this
    decides which file each one goes to.

    Each name goes to the shard that the count of names *accepted so far* names
    as it is offered. That is what makes the shards disjoint and evenly sized:
    the de-duplication :meth:`TabularLog.add` already does is applied first, so
    a name two headwords both asked for is recorded once, and two machines are
    never sent to fetch the same file. Routing on the accepted count rather
    than on the running total is also what balances them: a repeated name does
    not consume a turn, and the counts can differ by at most one.

    Nothing is buffered and the snapshot is still read exactly once, because the
    decision needs nothing but the running count.
    """

    def __init__(
        self,
        manifest_path: str,
        download_dir: str,
        count: int,
        args,
        snapshot: "Snapshot",
    ) -> None:
        self.count = 0
        self.paths = shard_paths(manifest_path, count)
        self._shards = [
            TabularLog(path, download_dir, header=_shard_header(args, snapshot))
            for path in self.paths
        ]

    def add(self, dest: str, url: str) -> bool:
        shard = self._shards[self.count % len(self._shards)]
        if not shard.add(dest, url):
            return False
        self.count += 1
        return True

    def describe(self) -> List[str]:
        lines = [f"  to download:    {self.count:,}, in {len(self._shards)} shard(s):"]
        for path, shard in zip(self.paths, self._shards):
            lines.append(f"    {path}  ({shard.count:,})")
        return lines

    def close(self) -> None:
        for shard in self._shards:
            shard.close()


def _shard_header(args, snapshot: "Snapshot") -> List[str]:
    """The lines that make a shard file explain itself to whoever is handed it.

    A shard leaves this machine and is fetched by a command that knows nothing
    about the snapshot that produced it, so it has to carry the command line
    that fetches it, the options it was planned with -- a different
    ``--audio-per-word`` wants a different set of files, so shards from two
    plans of the same snapshot may overlap -- and what to do with the result.
    """
    plan = [f"--source-lang {args.source_lang}", f"--audio-per-word {args.audio_per_word}"]
    if args.audio_lang:
        plan.append(f"--audio-lang {args.audio_lang}")
    if args.jsonl:
        plan.append(f"--jsonl {args.jsonl}")
    elif args.dump_date:
        plan.append(f"--dump-date {args.dump_date}")
    return [
        "# a shard of the audio a kaikki-to-dsl.py build could not take from the",
        "# Wiktionary archive. Fetch it with:",
        "#   python scripts/kaikki-to-dsl.py fetch-list <this file> --into <dir>",
        f"# planned with: {' '.join(plan)}",
        "# combine the results by copying the filled <dir> into the building",
        "# machine's <cache-dir>/<dump-date>/audio-cache/, then re-run",
        "# 'prefetch-audio' there: it skips every file the cache now holds.",
    ]


class FetchTally:
    """What one run attempted, and the verdict those attempts imply.

    Shared by the two fetch modes -- the prefetcher walking the snapshot and a
    worker walking a shard file (see design D6) -- so that the summary wording
    and the exit status are the same whichever one ran. The user learns to read
    this output, and the docs quote it; a second phrasing would be a second
    thing to learn.

    ``--limit`` bounds *attempts*, not successes: a run in which files are
    failing is the run most at risk of earning a harder rate limit, so it must
    not sail on through the rest of the work.
    """

    def __init__(
        self,
        limit: Optional[int] = None,
        dead_label: str = "audio-dead.tsv",
        done_text: str = "every recording that exists is now cached -- run the build",
    ) -> None:
        self.limit = limit
        self.attempted = 0
        self.fetched = 0
        self.already = 0  # skipped: present and verified before this run
        self.gone: Dict[str, int] = {}  # reason -> how many are permanently gone
        self.transient = 0
        self.complete = True
        self._dead_label = dead_label
        self._done_text = done_text

    def spent(self) -> bool:
        """True once the run's attempt budget is used up."""
        return self.limit is not None and self.attempted >= self.limit

    def report(self) -> List[str]:
        """The run's summary lines, in the order the docs show them."""
        lines = [
            f"fetched {self.fetched:,} of {self.attempted:,} "
            f"attempted file(s) this run"
        ]
        # The two kinds of failure are reported apart because they call for
        # opposite action: one is finished business, the other is worth coming
        # back to.
        if self.gone:
            breakdown = ", ".join(
                f"{n} {reason}" for reason, n in sorted(self.gone.items())
            )
            lines.append(
                f"  {sum(self.gone.values()):,} permanently gone ({breakdown}) -- "
                f"recorded in {self._dead_label}, never requested again"
            )
        if self.transient:
            lines.append(
                f"  {self.transient:,} rate-limited, blocked or interrupted "
                f"-- re-run later"
            )
        if not self.complete:
            lines.append(
                f"  stopped at --limit {self.limit}; more files remain "
                f"-- re-run to continue"
            )
        elif self.transient:
            lines.append(
                "  not finished: re-run when the rate limit clears, and the files "
                "that did land are skipped"
            )
        else:
            # Every recording that was asked for is on disk. The ones that do
            # not exist cannot be fetched, and the build slot-fills past them, so
            # re-running would only re-read the work to reach the same verdict.
            lines.append(f"  done: {self._done_text}")
        return lines

    def exit_code(self) -> int:
        return 1 if (self.transient or not self.complete) else 0


def fetch_one(
    url: str,
    dest: str,
    args,
    tally: FetchTally,
    dead_log: "TabularLog",
    on_failure=None,
) -> bool:
    """Put one file in the cache, and account for it.

    Returns False *only* when the run's attempt budget is spent, so the caller
    can stop without having touched the network. A file already present and
    verified is not an attempt and is not re-requested, so a re-run over a full
    cache spends nothing.

    One bad file must not end the pass, so every failure is caught and filed
    rather than raised: a file that is *gone* is recorded so no future run asks
    for it again, and one that was merely refused or timed out is left for the
    next run. ``on_failure(dest, permanent)`` is how the prefetcher re-plans the
    headword that wanted the file; a worker has no records to re-plan against
    and passes nothing.
    """
    if not args.force_download and verify_sidecar(dest):
        tally.already += 1
        return True
    if tally.spent():
        return False
    tally.attempted += 1
    try:
        download_cached(
            url, dest, args.force_download, args.timeout,
            args.retries, args.spacing, args.max_backoff,
        )
    except Exception as exc:  # one bad file must not end the pass
        permanent = failure_is_permanent(exc)
        if permanent:
            reason = describe_failure(exc)
            dead_log.add(dest, url, reason)
            tally.gone[reason] = tally.gone.get(reason, 0) + 1
            print(
                f"  gone ({reason}): {os.path.basename(dest)}", file=sys.stderr
            )
        else:
            tally.transient += 1
            print(
                f"  failed, will retry: {os.path.basename(dest)}: {exc}",
                file=sys.stderr,
            )
        if on_failure is not None:
            on_failure(dest, permanent)
        return True
    tally.fetched += 1
    return True


def prefetch_audio(args) -> int:
    """Fetch, politely and resumably, the audio a build cannot take from the tar.

    The build itself has to render the articles that reference a recording, so
    the dictionary is re-rendered after this -- but that pass is pure CPU and
    local archive I/O: every file this command leaves in the cache is found by
    its sha256 sidecar and never requested again. Running it in chunks over
    several rate-limit windows is therefore just a matter of repeating the
    command; each run skips what it already has.

    Fetching is interleaved with the scan rather than deferred until it ends. A
    headword's decision needs only its own records, which are contiguous in the
    snapshot, so there is nothing to wait for: the first files are on disk within
    seconds of starting, and a run stopped by ``--limit`` never reads the rest of
    the snapshot at all.

    ``--split N`` records the same work as N disjoint shard files instead of one
    manifest, for machines other than this one to fetch: see
    :class:`ShardSet` for how they are divided and ``fetch-list`` for the other
    end. Splitting also lists, because a shard is a plan to hand out rather than
    a job to finish here.
    """
    want_audio = args.audio_per_word > 0
    if not want_audio:
        raise SystemExit("--audio-per-word 0 disables audio; nothing to prefetch")
    if args.split is not None:
        if args.split < 1:
            raise SystemExit("--split needs a shard count of at least 1")
        if args.limit is not None:
            raise SystemExit(
                "--split plans the whole job so the shards can be handed out; "
                "--limit would silently drop the rest of it, and belongs on a "
                "fetching run instead"
            )
        # A shard is a plan to give away, so splitting is listing.
        args.list_only = True
    snapshot, jsonl_path, _audio_path, available, download_dir = _resolve_inputs(
        args, True
    )
    if download_dir is None:
        raise SystemExit("--no-audio-download leaves nowhere to cache prefetched audio")
    if not available:
        print(
            "warning: the audio archive holds no known recordings; every audio "
            "file in this dictionary will be fetched one by one",
            file=sys.stderr,
        )

    # The dead-file record is cache *state*, not a report, so it always lives
    # beside the cache rather than following --manifest around.
    dead_path = os.path.join(snapshot.dir, "audio-dead.tsv")
    dead_log = TabularLog(dead_path, download_dir, truncate=False)
    wishlist = _collect_wishlist(
        args, jsonl_path, available, download_dir, dead_log.names
    )
    manifest_path = args.manifest or os.path.join(snapshot.dir, "audio-missing.tsv")
    if args.split:
        work = ShardSet(manifest_path, download_dir, args.split, args, snapshot)
    else:
        work = TabularLog(manifest_path, download_dir)
    print(
        f"audio cache: {download_dir}\n"
        f"  manifest:   {manifest_path}\n"
        f"  gone:       {dead_path} ({len(dead_log.names):,} recorded)",
        file=sys.stderr,
    )
    os.makedirs(download_dir, exist_ok=True)

    tally = FetchTally(args.limit, os.path.basename(dead_path))
    fetching = Progress("fetching audio", every=25)

    def replan(dest: str, permanent: bool) -> None:
        """A file did not land, so the build will slot-fill past it.

        Both classes are replanned the same way -- the build moves on either
        way -- but a gone file also leaves the dead list, which is what lets a
        later run report the cache finished instead of retrying a 404 forever.
        The headword that asked for the file is replanned as well, and the
        replacements it yields are queued, so the article keeps the same
        recording count it would have had if the fetch had worked.
        """
        if permanent:
            wishlist.mark_dead(dest)
        else:
            wishlist.mark_failed(dest)
        queue.extend(wishlist.take_replacements())

    # Offers are pulled one at a time: draining the scan into the queue up front
    # would read the whole snapshot before fetching anything, which is the very
    # thing this avoids. A failed file can queue a replacement for its own
    # headword, so the queue outlives any single headword's offers.
    scan = wishlist.scan(jsonl_path, args.source_lang, args.sample, args.sample_mode)
    queue: Deque[Tuple[str, str]] = deque()
    exhausted = False
    try:
        while True:
            while not queue and not exhausted:
                try:
                    queue.append(next(scan))
                except StopIteration:
                    exhausted = True
            if not queue:
                break
            dest, url = queue.popleft()
            work.add(dest, url)
            if args.list_only:
                continue
            if not fetch_one(url, dest, args, tally, dead_log, replan):
                # stop consuming the scan: the rest of the snapshot does not
                # need reading to know there is more to come
                tally.complete = False
                break
            fetching.tick()
    finally:
        if not args.list_only:
            fetching.done()
        work.close()
        dead_log.close()

    if args.list_only:
        print(f"  already cached: {len(wishlist.satisfied):,}", file=sys.stderr)
        for line in work.describe():
            print(line, file=sys.stderr)
        print("listing only; nothing was downloaded", file=sys.stderr)
        return 0

    for line in tally.report():
        print(line, file=sys.stderr)
    return tally.exit_code()


def iter_list_entries(path: str) -> Iterator[Tuple[str, str]]:
    """Yield ``(name, url)`` for each entry of a manifest or shard file.

    Read as a generator: a full dictionary's outstanding work runs to hundreds
    of thousands of lines, and neither a worker nor ``--limit`` has any use for
    the ones past the end.

    Blank lines and ``#`` comments are skipped, and a third column -- which the
    dead list carries as its reason -- is ignored, so the three file kinds share
    one format. A line with no tab is refused with its number rather than
    skipped: a silently dropped line is a silently missing recording, which is
    the one failure this whole feature exists to avoid. Names are held to being
    relative and inside their directory, so a list file from somewhere else
    cannot write outside ``--into``.
    """
    with open(path, "r", encoding="utf-8") as stream:
        for number, raw in enumerate(stream, 1):
            line = raw.rstrip("\n").rstrip("\r")
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 2 or not fields[1].strip():
                raise SystemExit(
                    f"{path}:{number}: expected 'name<TAB>url', got {line!r}"
                )
            name = fields[0].strip()
            parts = name.replace("\\", "/").split("/")
            if (
                not name
                or name.startswith("/")
                or (len(parts) > 1 and os.path.isabs(name))
                or ".." in parts
            ):
                raise SystemExit(
                    f"{path}:{number}: {name!r} is not a plain relative name"
                )
            yield name, fields[1].strip()


def fetch_list(args) -> int:
    """Fetch one shard of the outstanding audio into a cache directory.

    The other end of ``prefetch-audio --split``, and deliberately much smaller:
    this command needs no snapshot, no audio archive, and no contact with
    kaikki.org, only the shard file, so any machine with Python can take one.

    A recording is written under the name the shard gives it, with the same
    checksum sidecar the prefetcher writes, which is what makes the filled
    directory indistinguishable from one this machine filled itself. The
    directory is therefore combined with the others by copying: the building
    machine's audio cache is a flat set of named, verified files, and a file
    already there is left alone.

    There is no re-planning here. A file that is permanently gone is recorded
    and skipped, where the prefetcher would fetch the headword's next candidate
    instead -- a worker has no records to choose one with. The build slot-fills
    past the gap, and the closing ``prefetch-audio`` run on the building machine
    is the pass that finishes whatever no worker could.
    """
    into = args.into
    if not os.path.isdir(into):
        os.makedirs(into, exist_ok=True)
    dead_path = args.dead or (args.list + ".dead.tsv")
    dead_log = TabularLog(dead_path, into, truncate=False)
    tally = FetchTally(
        args.limit,
        os.path.basename(dead_path),
        done_text=(
            "every recording this shard lists is now cached -- copy the "
            "directory into the building machine's audio cache"
        ),
    )
    print(
        f"audio cache: {into}\n"
        f"  shard:      {args.list}\n"
        f"  gone:       {dead_path} ({len(dead_log.names):,} recorded)",
        file=sys.stderr,
    )
    fetching = Progress("fetching audio", every=25)
    try:
        for name, url in iter_list_entries(args.list):
            dest = os.path.join(into, *name.split("/"))
            if not fetch_one(url, dest, args, tally, dead_log):
                # --limit bounds attempts, so the rest of the list is left for
                # another run -- which costs nothing, because every file already
                # in the directory is skipped
                tally.complete = False
                break
            fetching.tick()
    finally:
        fetching.done()
        dead_log.close()

    print(f"  already cached: {tally.already:,}", file=sys.stderr)
    for line in tally.report():
        print(line, file=sys.stderr)
    return tally.exit_code()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaikki-to-dsl.py",
        description="Build an importable DSL dictionary from a pinned kaikki.org "
        "Wiktionary snapshot for one language.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Notes:\n"
            "  This builds a monolingual explanatory dictionary: headwords and\n"
            "  definitions are both in --source-lang.\n\n"
            "  Base forms are the only indexed headwords by default. With\n"
            "  --include-inflections a base word's inflected forms are added as\n"
            "  extra headword lines on its card; in DSL every indexed word also\n"
            "  appears in the suggestion list (there is no hidden-alias concept),\n"
            "  so enable it only when direct lookup of inflected forms is wanted.\n\n"
            "  Audio is bundled at most --audio-per-word times per headword,\n"
            "  de-duplicated. A recording the archive lacks is fetched from its\n"
            "  Wikimedia URL and cached (--no-audio-download disables that); one\n"
            "  that cannot be resolved is logged and left out rather than emitted\n"
            "  as a broken link, and it does not use up a per-word slot.\n"
            "  --no-audio (or --audio-per-word 0) disables audio entirely and\n"
            "  skips downloading the audio archive.\n\n"
            "  The output is <name>.dsl.dz plus <name>.dsl.files.zip (or the\n"
            "  .files/ directory with --audio-layout dir). The archive holds the\n"
            "  sense-marker icons in addition to any bundled audio, so it is\n"
            "  written even with --no-audio.\n\n"
            "  A recording Wikimedia rate-limits is left out of the article rather\n"
            "  than emitted as a broken link, so a long build can end with gaps.\n"
            "  The 'prefetch-audio' subcommand fills those gaps on its own,\n"
            "  politely and in resumable chunks, so the rate-limited fetching does\n"
            "  not have to share a run with rendering:\n\n"
            "    kaikki-to-dsl.py prefetch-audio --source-lang en \\\n"
            "        --dump-date 2026-09-02 --list      # see what is missing\n"
            "    kaikki-to-dsl.py prefetch-audio --source-lang en \\\n"
            "        --dump-date 2026-09-02 --limit 500  # fetch a chunk\n"
            "    kaikki-to-dsl.py --source-lang en --dump-date 2026-09-02\n"
            "\n"
            "  Several machines can share the back-fill: 'prefetch-audio --split N'\n"
            "  writes N disjoint shard files, each fetched by any machine with\n"
            "  'kaikki-to-dsl.py fetch-list <shard> --into <dir>', and the filled\n"
            "  directories are copied into <cache-dir>/<dump-date>/audio-cache/.\n"
            "\n"
            "  The prefetcher must be given the same --source-lang,\n"
            "  --audio-per-word and --audio-lang as the build, because both decide\n"
            "  which recordings an article gets.\n"
        ),
    )
    parser.add_argument("--source-lang", required=True, help="ISO code of the dictionary's language (e.g. en)")
    parser.add_argument("--dump-date", help="pinned kaikki.org dump date (YYYY-MM-DD); required unless --jsonl")
    parser.add_argument("--jsonl", help="use a local wiktextract JSONL(.gz) instead of downloading")
    parser.add_argument("--audio-tar", help="use a local Wiktionary audio tar instead of downloading")
    parser.add_argument("--jsonl-url", default=RAW_JSONL_URL, help="override the JSONL source URL")
    parser.add_argument("--audio-url", default=AUDIO_TAR_URL, help="override the audio archive URL")
    parser.add_argument("--cache-dir", default=os.path.join(os.path.expanduser("~"), ".cache", "aurelex-kaikki"))
    parser.add_argument("--out-dir", default="dist")
    parser.add_argument("--name", help="dictionary/output base name (default kaikki-<source>)")
    parser.add_argument("--include-inflections", action="store_true", help="also index inflected forms (adds them to suggestions)")
    parser.add_argument("--audio-per-word", type=int, default=3, help="max audio files per headword (default 3)")
    parser.add_argument("--no-audio", action="store_true", help="do not bundle audio (and do not download the archive)")
    parser.add_argument("--audio-lang", help="prefer audio whose tags match this language/accent (e.g. US)")
    parser.add_argument(
        "--no-audio-download",
        action="store_true",
        help="do not fetch audio missing from the archive from Wikimedia (tar only)",
    )
    parser.add_argument(
        "--force-audio-index",
        action="store_true",
        help="rebuild the cached audio-archive name index even if it looks current",
    )
    parser.add_argument(
        "--audio-layout", choices=["zip", "dir"], default="zip",
        help="how to bundle audio (default zip)",
    )
    parser.set_defaults(audio_downloader=None, force_audio_index=False)
    parser.add_argument("--sample", type=int, help="emit only N headwords")
    parser.add_argument(
        "--sample-mode", choices=["first", "random"], default="first",
        help="how --sample picks headwords: first N in file order, or a "
        "deterministic spread over thousands of headwords (default first). "
        "Both read only a bounded part of the snapshot, so a sample is quick",
    )
    parser.add_argument("--preview", action="store_true", help="also write a human-readable HTML preview")
    parser.add_argument("--force-download", action="store_true", help="re-download cached files")
    parser.add_argument("--skip-date-check", action="store_true", help="skip verifying the dump date against kaikki.org")
    parser.add_argument("--timeout", type=int, default=60, help="network timeout in seconds (default 60)")
    return parser


def _add_snapshot_args(parser: argparse.ArgumentParser) -> None:
    """The options that decide *which* articles, and so which audio, are wanted.

    Shared by the build and the prefetcher: enumerating a different set of
    articles than the build renders is the one way the prefetched cache could end
    up holding files nothing references, or missing files the build asks for.
    """
    parser.add_argument("--source-lang", required=True,
                        help="ISO code of the dictionary's language (e.g. en)")
    parser.add_argument("--dump-date", help="pinned kaikki.org dump date (YYYY-MM-DD); required unless --jsonl")
    parser.add_argument("--jsonl", help="use a local wiktextract JSONL(.gz) instead of downloading")
    parser.add_argument("--audio-tar", help="use a local Wiktionary audio tar instead of downloading")
    parser.add_argument("--jsonl-url", default=RAW_JSONL_URL, help="override the JSONL source URL")
    parser.add_argument("--audio-url", default=AUDIO_TAR_URL, help="override the audio archive URL")
    parser.add_argument("--cache-dir", default=os.path.join(os.path.expanduser("~"), ".cache", "aurelex-kaikki"))
    parser.add_argument("--audio-per-word", type=int, default=3, help="max audio files per headword (default 3)")
    parser.add_argument("--audio-lang", help="prefer audio whose tags match this language/accent (e.g. US)")
    parser.add_argument("--sample", type=int, help="emit only N headwords")
    parser.add_argument(
        "--sample-mode", choices=["first", "random"], default="first",
        help="how --sample picks headwords: first N in file order, or a "
        "deterministic spread over thousands of headwords (default first). "
        "Both read only a bounded part of the snapshot, so a sample is quick",
    )
    parser.add_argument("--no-audio-download", action="store_true",
                        help="do not fetch audio missing from the archive from Wikimedia (tar only)")
    parser.add_argument("--force-audio-index", action="store_true",
                        help="rebuild the cached audio-archive name index even if it looks current")
    parser.add_argument("--force-download", action="store_true", help="re-download cached files")
    parser.add_argument("--skip-date-check", action="store_true",
                        help="skip verifying the dump date against kaikki.org")
    parser.add_argument("--timeout", type=int, default=60, help="network timeout in seconds (default 60)")


def prefetch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaikki-to-dsl.py prefetch-audio",
        description="Fetch the pronunciation recordings a build cannot take from the "
        "audio archive, into the same cache the build reads. Walks the snapshot and, "
        "as each headword's recordings are decided, downloads them at a polite rate. "
        "Nothing is fetched twice, so the command is safe to repeat until the cache "
        "is complete; the build then bundles the whole set with no network I/O.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Notes:\n"
            "  Pass the same --source-lang, --audio-per-word, --audio-lang and\n"
            "  snapshot as the build you are preparing for; those decide which\n"
            "  recordings each article gets, and therefore which files are wanted.\n\n"
            "  Fetching is interleaved with the scan, so the first files land within\n"
            "  seconds and --limit stops before the rest of the snapshot is read.\n"
            "  --list is the exception: it downloads nothing, so it reads everything in\n"
            "  order to write a complete manifest -- the way to size the job before\n"
            "  spending any of your rate limit on it.\n\n"
            "  --split N is how several machines share the job. It records the same work as\n"
            "  N disjoint shard files, each carrying a header saying how to fetch it, and\n"
            "  implies --list. Then, on each machine:\n"
            "    python scripts/kaikki-to-dsl.py fetch-list \\\n"
            "        <cache>/<dump-date>/audio-missing.shard-01-of-04.tsv --into ./cache01\n"
            "  Copy the filled directories into <cache-dir>/<dump-date>/audio-cache/ and\n"
            "  re-run prefetch-audio here to check nothing was missed. See 'fetch-list --help'.\n\n"
            "  Each run ends by saying whether there is anything left to do, and the\n"
            "  exit status agrees: 0 means every recording that exists is cached, 1\n"
            "  means a rate limit or --limit cut the run short. Failures are reported\n"
            "  in two classes, because they want opposite things from you:\n"
            "    * gone (HTTP 404 and similar) -- recorded in <cache>/<dump-date>/\n"
            "      audio-dead.tsv and never requested again. Retrying cannot help, so\n"
            "      these do not count as outstanding work; the build uses the next\n"
            "      candidate instead, and the article keeps a pronunciation.\n"
            "    * rate-limited, blocked or interrupted -- left for the next run.\n"
        ),
    )
    _add_snapshot_args(parser)
    parser.add_argument("--list", dest="list_only", action="store_true",
                        help="write the manifest of missing files and exit without downloading; "
                             "reads the whole snapshot, so it overrides --limit")
    parser.add_argument("--manifest", help="where to write the manifest (default <cache>/<dump-date>/audio-missing.tsv)")
    parser.add_argument("--split", type=int, metavar="N",
                        help="record the outstanding work as N disjoint shard files "
                             "instead of one manifest (missing.tsv becomes "
                             "missing.shard-01-of-04.tsv), for other machines to fetch "
                             "with 'fetch-list'; the shards differ in size by at most "
                             "one file and no two hold the same one, so no machine is "
                             "sent to fetch another's work. Implies --list, since a "
                             "shard is a plan to hand out, and cannot be combined with "
                             "--limit")
    _add_fetch_args(parser)
    return parser


def _add_fetch_args(parser: argparse.ArgumentParser) -> None:
    """The options that shape a fetching run, whichever mode is fetching.

    Shared by the prefetcher and the worker, so a file is fetched the same way
    whichever list it came from. Deliberately *not* the snapshot options: none
    of these change which files are wanted, only how they are asked for.
    """
    parser.add_argument("--limit", type=int,
                        help="attempt at most N files this run, then stop; anything "
                             "left is picked up by the next run. Counts attempts, so "
                             "a run where files are failing cannot outrun its window")
    parser.add_argument("--spacing", type=float, default=_PREFETCH_SPACING_SECONDS,
                        help=f"minimum seconds between requests (default {_PREFETCH_SPACING_SECONDS}; "
                             "Wikimedia asks bulk clients to stay well above 1)")
    parser.add_argument("--retries", type=int, default=_PREFETCH_RETRIES,
                        help=f"attempts per file (default {_PREFETCH_RETRIES})")
    parser.add_argument("--max-backoff", type=float, default=600.0,
                        help="ceiling on a single backoff sleep, honouring Retry-After up to it (default 600)")


def fetch_list_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaikki-to-dsl.py fetch-list",
        description="Fetch the recordings one shard of the outstanding audio lists, into "
        "a cache directory. Needs nothing but the shard file: no dictionary snapshot, no "
        "audio archive, no contact with kaikki.org, so any machine with Python can take "
        "one -- which is the point, since Wikimedia's rate limit is per client and "
        "several machines fetching disjoint parts of a job finish it sooner. Copy the "
        "filled directory into the building machine's audio cache afterwards.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Notes:\n"
            "  A shard is written by 'prefetch-audio --split N', which must be run with\n"
            "  the same --source-lang, --audio-per-word, --audio-lang and snapshot as the\n"
            "  build; those decide which recordings each article gets. Each shard says so\n"
            "  in its own header lines.\n\n"
            "  --into is an ordinary directory: give each shard its own, and copy them all\n"
            "  into <cache-dir>/<dump-date>/audio-cache/ on the machine that builds. Every\n"
            "  file is written with a .sha256 sidecar and an existing verified file is\n"
            "  never re-requested, so copying a directory over another -- or over itself --\n"
            "  is all the combining there is. Re-running 'prefetch-audio' on the building\n"
            "  machine afterwards is the check: it asks for nothing the cache now holds.\n\n"
            "  A file that is permanently gone is recorded and skipped rather than replaced.\n"
            "  The prefetcher can substitute the headword's next candidate because it has\n"
            "  the records; a worker cannot, and the build slot-fills past the gap instead.\n\n"
            "  The summary and exit status are the prefetcher's: 0 means the shard is done,\n"
            "  1 means a rate limit or --limit cut the run short. The dead list is written\n"
            "  beside the shard (<shard>.dead.tsv), never into the cache directory.\n"
        ),
    )
    parser.add_argument("list", help="the shard file to fetch ('prefetch-audio --split N')")
    parser.add_argument("--into", required=True,
                        help="the directory to fill; copy it into <cache-dir>/<dump-date>/"
                             "audio-cache/ on the machine that builds the dictionary")
    parser.add_argument("--dead",
                        help="where to record permanently-gone files (default <shard>.dead.tsv)")
    parser.add_argument("--force-download", action="store_true",
                        help="re-download files already present in the directory")
    parser.add_argument("--timeout", type=int, default=60,
                        help="network timeout in seconds (default 60)")
    _add_fetch_args(parser)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Dispatched by hand rather than through argparse subparsers: the build's
    # options have stayed flat and heavily used since the tool's first release,
    # and a subparser would put them behind a mode word. The two modes that need
    # the snapshot instead share the options that decide which articles -- and so
    # which audio -- are wanted, through _add_snapshot_args. The worker takes
    # neither: it is handed a finished list, so it needs nothing that decides what
    # is wanted, only _add_fetch_args.
    if argv and argv[0] == "prefetch-audio":
        return prefetch_audio(prefetch_parser().parse_args(argv[1:]))
    if argv and argv[0] == "fetch-list":
        return fetch_list(fetch_list_parser().parse_args(argv[1:]))
    args = build_parser().parse_args(argv)
    report = build(args)
    print(report.summary(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
