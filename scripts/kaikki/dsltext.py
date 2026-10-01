"""DSL text tooling"""

from __future__ import annotations

import base64
import os
import re
from typing import Dict, List, Optional, Sequence, Set

from .constants import _SCRIPT_DIR


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

#: Tags that mark a sense as archaic use: exactly those that show the usage icon.
#: Such a sense is allowed to fall back to an archaic example (see
#: ``_sense_examples``).
_USAGE_TAGS = {
    tag for tag, icon in _SENSE_TAG_ICONS.items() if icon == "gd_tag_obsolete.svg"
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
    targets: List[str] = []
    for entry in list(sense.get("alt_of") or []) + list(sense.get("form_of") or []):
        if not isinstance(entry, dict):
            continue
        target = str(entry.get("word") or "").strip()
        # A target named by several relations is linked once: a second wrap would
        # land inside the first link and nest [ref] inside [ref].
        if target and target != word and target not in targets:
            targets.append(target)
    for target in targets:
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
_ICON_ASSET_DIR = os.path.join(_SCRIPT_DIR, "assets", "kaikki-tag-icons")
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

#: A sound link, whose captured group is the DSL-escaped recording name.
_AUDIO_REF_RE = re.compile(r"\[s\](.*?)\[/s\]")

def _unescape_dsl(text: str) -> str:
    """Reverse the escaping :func:`escape_dsl` applies to a sound-link name."""
    out: List[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in "\\[]<>":
            out.append(text[i + 1])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)

def collect_audio_refs(text: str) -> List[str]:
    """The recordings a rendered dictionary references, in first-seen order.

    The dictionary is the source of truth for what to bundle: a sound link
    exists only because the build chose that recording, so reading the links
    recovers the exact set without the records that produced them. Each name is
    un-escaped back to the real filename.
    """
    seen: Set[str] = set()
    names: List[str] = []
    for match in _AUDIO_REF_RE.finditer(text):
        name = _unescape_dsl(match.group(1))
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names

def rewrite_audio_refs(text: str, rename: Dict[str, str]) -> str:
    """Point each sound link at its bundled name, where the two differ."""
    def replace(match: "re.Match[str]") -> str:
        original = _unescape_dsl(match.group(1))
        new = rename.get(original)
        if new is None or new == original:
            return match.group(0)
        return f"[s]{escape_dsl(new)}[/s]"

    return _AUDIO_REF_RE.sub(replace, text)

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
