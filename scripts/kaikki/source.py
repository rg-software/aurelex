"""Reading / filtering records"""

from __future__ import annotations

import gzip
import hashlib
import heapq
import json
from typing import Dict, Iterator, List, Optional, Set, Tuple

from .constants import NON_LEXICAL_POS, _SAMPLE_STRIDE_TARGET


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

def select_headwords_and_splits(
    path: str,
    source_code: str,
    progress: Optional["Progress"] = None,
) -> Tuple[Set[str], Set[str]]:
    """The indexed headwords, and those whose records are not contiguous.

    The snapshot is not sorted by headword, so a headword's records can appear in
    several runs separated by other words. Returning the split set lets the
    render pass merge such a headword into one card instead of emitting it twice.
    One pass; the run test is a set lookup per candidate.
    """
    known: Set[str] = set()
    split: Set[str] = set()
    run_started: Set[str] = set()
    previous: Optional[str] = None
    for word in iter_candidate_headwords(path, source_code, progress):
        known.add(word)
        if word != previous:
            if word in run_started:
                split.add(word)
            run_started.add(word)
            previous = word
    return known, split

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
