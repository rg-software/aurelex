"""Dict A equivalent resolution: PWN synsets bridged to RuWordNet via `ili`.

Each English synset resolves to its linked RU synsets; each linked RU synset
becomes one card sense with its Russian definition (or title fallback) and
member lemmas. Senses with no `ili` link (including all adverb senses in
practice) resolve unlinked: they keep their English synonyms, ship no
equivalents, and count against coverage.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple


def _ru_pos_labels() -> Dict[str, str]:
    scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from kaikki.profiles import _RU_POS_LABELS

    return _RU_POS_LABELS


# PWN synset POS letter (as in WNSynset ids like ``07679356-n``) to card POS.
_EN_POS = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}
POS_ORDER = ["noun", "verb", "adjective", "adverb"]


@dataclass
class RuGroup:
    """One linked RU synset: title, definition (may be empty), member lemmas."""

    title: str = ""
    definition: str = ""
    lemmas: List[str] = field(default_factory=list)


@dataclass
class EnSynset:
    """One English synset: POS, member lemmas, linked RU groups (maybe none)."""

    pos: str = ""
    lemmas: List[str] = field(default_factory=list)
    groups: List[RuGroup] = field(default_factory=list)


@dataclass
class ResolvedSense:
    """One card sense, ready for the DSL emitter."""

    pos: str = ""
    definition: str = ""
    equivalents: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    linked: bool = False


@dataclass
class ResolutionReport:
    words: int = 0
    words_no_en: int = 0
    synsets: int = 0
    synsets_linked: int = 0


def _serialise(senses: Sequence[ResolvedSense]) -> List[dict]:
    return [
        {
            "pos": s.pos,
            "definition": s.definition,
            "equivalents": list(s.equivalents),
            "synonyms": list(s.synonyms),
            "linked": s.linked,
        }
        for s in senses
    ]


def _deserialise(rows: List[dict]) -> List[ResolvedSense]:
    return [
        ResolvedSense(
            pos=r.get("pos", ""),
            definition=r.get("definition", ""),
            equivalents=list(r.get("equivalents", [])),
            synonyms=list(r.get("synonyms", [])),
            linked=bool(r.get("linked", False)),
        )
        for r in rows
    ]


def _cache_key(db_id: str, words: Sequence[str]) -> str:
    import hashlib

    h = hashlib.sha256()
    h.update(db_id.encode("utf-8"))
    h.update(b"\x00")
    for w in sorted(words):
        h.update(w.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _load_cached(
    words: Sequence[str], cache_path: str, cache_id: str,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Optional[Tuple[Dict[str, List[ResolvedSense]], ResolutionReport]]:
    """Return the cached resolution when it matches, else None."""
    import json as _json

    try:
        with open(cache_path, encoding="utf-8") as f:
            payload = _json.load(f)
        if payload.get("key") != _cache_key(cache_id, words):
            return None
        report = ResolutionReport(
            words=payload["report"]["words"],
            words_no_en=payload["report"]["words_no_en"],
            synsets=payload["report"]["synsets"],
            synsets_linked=payload["report"]["synsets_linked"],
        )
        cards = {
            w: _deserialise(senses) for w, senses in payload.get("cards", {}).items()
        }
        if progress is not None:
            progress(report.words, len(words))
        return cards, report
    except (OSError, ValueError, KeyError):
        return None  # missing or corrupt cache: rebuild it


def _save_cached(
    path: str, db_id: str, words: Sequence[str],
    cards: Dict[str, List[ResolvedSense]], report: ResolutionReport,
) -> None:
    import json as _json

    payload = {
        "key": _cache_key(db_id, words),
        "report": {
            "words": report.words,
            "words_no_en": report.words_no_en,
            "synsets": report.synsets,
            "synsets_linked": report.synsets_linked,
        },
        "cards": {w: _serialise(senses) for w, senses in cards.items()},
    }
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, ensure_ascii=False)


def russian_pos(en_pos: str) -> str:
    """Map an English POS name to the Russian card label."""
    labels = _ru_pos_labels()
    short = {"noun": "noun", "verb": "verb", "adjective": "adj", "adverb": "adv"}
    return labels.get(short.get(en_pos, en_pos), en_pos)


def _sense_definition(group: RuGroup) -> str:
    """RU definition with the title fallback, sentence-cased if ALL-CAPS.

    Synset titles are stored uppercase; a lowercased title would destroy
    proper-noun capitals wholesale ("УЛАН-БАТОР" -> "улан-батор"), so the
    fallback is sentence case instead ("Улан-батор") — standard dictionary
    style, and right for single-word proper-noun titles ("АМСТЕРДАМ" ->
    "Амстердам"). Natural-case definitions (which may hold proper nouns
    mid-text) pass through untouched.
    """
    text = (group.definition or "").strip() or group.title
    if text.isupper():
        text = text.capitalize()
    return text


def _gloss_definition(group: RuGroup) -> str:
    """PWN gloss for the reverse direction: verbatim, never re-cased.

    Glosses are natural-case English ("a city of central European Russia"),
    so the sentence-case rule of :func:`_sense_definition` does not apply.
    A gloss-less EN synset falls back to its own lemmas rather than an empty
    line.
    """
    text = (group.definition or "").strip()
    return text or ", ".join(group.lemmas)


def find_case_variant_synsets(db_path: str, word: str) -> List[str]:
    """Synset ids whose stored lemma matches ``word`` ignoring case/underscores.

    The wrapper lowercases every query, so this is the only route to
    capitalized and multiword lemmas (proper nouns, acronyms). Deterministic:
    de-duplicated and sorted. Returns [] when nothing matches.
    """
    import sqlite3

    key = word.strip().lower().replace(" ", "_")
    if not key:
        return []
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT DISTINCT synset_id FROM wn_sense WHERE lower(name) = ?",
            (key,),
        ).fetchall()
    finally:
        con.close()
    return sorted({r[0] for r in rows if r and r[0]})


class RuWordNetBackend:
    """Live backend over the `python-ruwordnet` sqlite database."""

    def __init__(self) -> None:
        try:
            from ruwordnet import RuWordNet
        except ImportError as exc:
            raise RuntimeError(
                "Dict A needs the `ruwordnet` package: "
                "`pip install ruwordnet && ruwordnet download`"
            ) from exc
        self.db_path = _ruwordnet_db_path()
        self._wn = RuWordNet()

    def db_identity(self) -> str:
        """Fingerprint the thesaurus file for the resolve cache."""
        st = os.stat(self.db_path)
        return f"{self.db_path}|{st.st_size}|{int(st.st_mtime)}"

    def _build_synsets(self, synsets) -> List[EnSynset]:
        """Build EnSynset records from WNSynset objects (shared by both paths)."""
        out = []
        for syn in synsets:
            pos_letter = syn.id.rsplit("-", 1)[-1]
            groups = [
                RuGroup(
                    title=rs.title or "",
                    definition=(rs.definition or "").strip(),
                    lemmas=sorted({s.name.lower() for s in rs.senses if s.name}),
                )
                for rs in (syn.ili or [])
            ]
            out.append(
                EnSynset(
                    pos=_EN_POS.get(pos_letter, "?"),
                    lemmas=sorted({s.name.replace("_", " ") for s in syn.senses}),
                    groups=groups,
                )
            )
        return out

    def ru_synsets(self, word: str) -> List[EnSynset]:
        """Mirror of :meth:`en_synsets` for the reverse direction.

        Reuses the same record shapes: the RU synset plays the ``EnSynset``
        role (POS, member lemmas, linked groups) and each linked EN synset
        plays the ``RuGroup`` role (gloss as definition, EN lemmas verbatim).
        No case-variant fallback is needed here — the wrapper uppercases
        every RU query and the stored lemmas are uppercase, so lookups are
        case-insensitive by construction. POS comes from the linked EN
        synsets (bridge pairs always agree); unlinked RU synsets fall back
        to their own id suffix.
        """
        out = []
        for sense in self._wn.get_senses(word):
            syn = sense.synset
            groups = [
                RuGroup(
                    title="",
                    definition=(es.definition or "").strip(),
                    lemmas=sorted({s.name.replace("_", " ") for s in es.senses if s.name}),
                )
                for es in (syn.ili or [])
            ]
            if groups:
                pos = self._pos_from_ili(syn)
            else:
                pos = _EN_POS.get(syn.id.rsplit("-", 1)[-1].lower(), "?")
            out.append(
                EnSynset(
                    pos=pos,
                    lemmas=sorted({s.name.lower() for s in syn.senses if s.name}),
                    groups=groups,
                )
            )
        return out

    @staticmethod
    def _pos_from_ili(syn) -> str:
        """POS from the first linked EN synset id (PWN letters)."""
        for es in syn.ili or []:
            letter = (es.id or "").rsplit("-", 1)[-1]
            if letter in _EN_POS:
                return _EN_POS[letter]
        return "?"

    def en_synsets(self, word: str) -> List[EnSynset]:
        out = []
        for sense in self._wn.get_en_senses(word):
            out.extend(self._build_synsets([sense.synset]))
        if out:
            return out
        # Fallback: the wrapper lowercases every query, so capitalized and
        # multiword lemmas (proper nouns, acronyms) never match through it.
        # Match stored names case-insensitively instead; exact-case words
        # already returned above, so behavior for them is unchanged.
        found = []
        for sid in find_case_variant_synsets(self.db_path, word):
            try:
                found.extend(self._build_synsets([self._wn.get_en_synset_by_id(sid)]))
            except Exception:
                continue  # stale index entry: skip, do not fail the word
        return found


def _ruwordnet_db_path() -> str:
    """Locate the installed RuWordNet sqlite (2021 db preferred)."""
    try:
        import ruwordnet as _pkg
    except ImportError as exc:
        raise RuntimeError(
            "EN lemma universe needs the `ruwordnet` package: "
            "`pip install ruwordnet && ruwordnet download`"
        ) from exc
    static = os.path.join(os.path.dirname(_pkg.__file__), "static")
    for cand in ("ruwordnet-2021.db", "ruwordnet.db"):
        path = os.path.join(static, cand)
        if os.path.isfile(path):
            return path
    raise RuntimeError("no RuWordNet sqlite found; run `ruwordnet download`")


def english_lemma_universe(db_path: Optional[str] = None) -> List[str]:
    """Every English lemma in the bundled EN subset (max-coverage headwords).

    The bundled subset holds only `ili`-linked synsets, so this universe is
    exactly the headwords the translation dictionary can cover. Default locates
    the installed `python-ruwordnet` sqlite (2021 db preferred).
    """
    import sqlite3

    if db_path is None:
        db_path = _ruwordnet_db_path()
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT DISTINCT name FROM wn_sense").fetchall()
    finally:
        con.close()
    return sorted({str(name).replace("_", " ") for (name,) in rows if name})


def kaikki_headwords(snapshot_path: str, lang: str = "en") -> List[str]:
    """Every lexical, non-inflected headword in a kaikki snapshot.

    ``lang`` selects the snapshot language; the pairs mode passes its source
    language, so the ru→en universe comes from the kaikki RU snapshot.
    The pairs dictionary iterates this universe and keeps the headwords that
    have Tatoeba pairs (about 1 in 20); the rest ship no card at all.
    """
    scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from kaikki import source as _ksource

    found: Set[str] = set()
    tick = 0
    for _line_no, record in _ksource.iter_records(snapshot_path, None, lang):
        tick += 1
        if tick % 1000000 == 0:
            print(f"snapshot scan: {tick:,} lines", file=sys.stderr)
        if record is None:
            continue
        word = record.get("word")
        if not word:
            continue
        if not _ksource.is_lexical(record) or _ksource.is_inflected(record):
            continue
        found.add(str(word))
    return sorted(found)


def rank_equivalents(equivalents: Sequence[str], freq: Dict[str, int]) -> List[str]:
    """Order equivalents common-first using Russian corpus frequencies.

    Within one RU synset the members share the meaning, so the ranking only
    decides what the eye hits first: everyday words before rare ones
    (``парламент`` before ``высший законодательный орган государства``).
    Unknown words sink to the end; ties break shorter-first, then
    alphabetically, so the order is deterministic. Pure ranking — nothing is
    dropped; collapsing near-synonyms would need semantic judgment.
    """
    def score(e: str) -> tuple:
        words = [w.lower() for w in re.findall(r"[а-яёa-z]+", e)]
        known = [freq.get(w, 0) for w in words] or [0]
        return (-min(known), len(e), e)

    seen: Set[str] = set()
    unique = [e for e in equivalents if not (e in seen or seen.add(e))]
    return sorted(unique, key=score)


def resolve_word(word: str, backend: Optional[RuWordNetBackend] = None,
                 direction: str = "en-ru") -> List[ResolvedSense]:
    """Resolve one headword to card senses, grouped per target synset.

    ``direction`` picks the walk: ``"en-ru"`` (each linked RU synset is one
    sense with a RU definition) or ``"ru-en"`` (each linked EN synset is one
    sense with the verbatim PWN gloss). POS labels are always the target
    language's (the backend sets them).
    """
    backend = backend or RuWordNetBackend()
    senses: List[ResolvedSense] = []
    synsets = (backend.ru_synsets(word) if direction == "ru-en"
               else backend.en_synsets(word))
    define = _gloss_definition if direction == "ru-en" else _sense_definition
    for syn in synsets:
        if not syn.groups:
            senses.append(
                ResolvedSense(
                    pos=syn.pos,
                    definition="",
                    equivalents=[],
                    synonyms=syn.lemmas,
                    linked=False,
                )
            )
            continue
        for group in syn.groups:
            senses.append(
                ResolvedSense(
                    pos=syn.pos,
                    definition=define(group),
                    equivalents=list(group.lemmas),
                    synonyms=syn.lemmas,
                    linked=True,
                )
            )
    senses.sort(key=lambda s: POS_ORDER.index(s.pos) if s.pos in POS_ORDER else 99)
    return senses


def resolve_words(
    words: Sequence[str], backend: Optional[RuWordNetBackend] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    cache_path: Optional[str] = None,
    cache_id: Optional[str] = None,
    direction: str = "en-ru",
) -> Tuple[Dict[str, List[ResolvedSense]], ResolutionReport]:
    """Resolve headwords, counting coverage (unlinked senses included).

    ``progress(done, total)`` is called every 1,000 headwords so an
    hours-long full build is not silent. With ``cache_path`` + ``cache_id``
    (e.g. the RuWordNet sqlite identity), a completed resolution is stored as
    JSON and reused verbatim on later runs over the same headwords — the
    thesaurus is pinned, so the result is deterministic and never recomputed.
    ``direction`` (``"en-ru"`` or ``"ru-en"``) picks which way the `ili`
    bridge is walked; POS labels are always the target language's.
    """
    if cache_path is not None and cache_id is not None and os.path.isfile(cache_path):
        hit = _load_cached(words, cache_path, cache_id, progress)
        if hit is not None:
            return hit
    backend = backend or RuWordNetBackend()
    report = ResolutionReport()
    cards: Dict[str, List[ResolvedSense]] = {}
    total = len(words)
    define = _gloss_definition if direction == "ru-en" else _sense_definition
    for word in words:
        report.words += 1
        if progress is not None and report.words % 1000 == 0:
            progress(report.words, total)
        synsets = (backend.ru_synsets(word) if direction == "ru-en"
                   else backend.en_synsets(word))
        if not synsets:
            report.words_no_en += 1
            cards[word] = []
            continue
        report.synsets += len(synsets)
        report.synsets_linked += sum(1 for s in synsets if s.groups)
        cards[word] = []
        for syn in synsets:
            if not syn.groups:
                cards[word].append(
                    ResolvedSense(
                        pos=syn.pos, definition="", equivalents=[],
                        synonyms=syn.lemmas, linked=False,
                    )
                )
                continue
            for group in syn.groups:
                cards[word].append(
                    ResolvedSense(
                        pos=syn.pos,
                        definition=define(group),
                        equivalents=list(group.lemmas),
                        synonyms=syn.lemmas,
                        linked=True,
                    )
                )
        cards[word].sort(
            key=lambda s: POS_ORDER.index(s.pos) if s.pos in POS_ORDER else 99
        )
    if cache_path is not None and cache_id is not None:
        _save_cached(cache_path, cache_id, words, cards, report)
    return cards, report
