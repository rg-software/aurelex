#!/usr/bin/env python3
"""Generate a tiny StarDict dictionary ("smoke") for the CI smoke test.

Writes smoke.ifo / smoke.idx / smoke.dict into the given directory. The IDX
format is: zero-terminated word, then 32-bit big-endian offset/length triplets
per entry (see upstream stardict.cc / DICTFILE format).

Usage: make-smoke-stardict.py <output-dir>
"""
import os
import struct
import sys

WORDS = {
    "smoke": ("m", "An MDX test entry for the smoke word."),
    "blood": ("m", "Another headword for the CI smoke test."),
    # Cross-reference, in the form StarDict dictionaries use and The World
    # Factbook emits: the bword: scheme with NO slashes. The engine must
    # rewrite it into a scheme the app resolves; before
    # stardict-bword-link-navigation it was passed through untouched and did
    # nothing on tap. Present here so the CI assertion has an input - without
    # it the check would pass vacuously.
    #
    # This entry is HTML ('h'), not plain ('m'), and that is the point: the
    # rewrite lives in the HTML handling path, and a plain-text entry escapes
    # its markup into visible text instead. Both types are therefore exercised.
    "clot": ("h", 'A cross-reference: <a href="bword:blood">blood</a>.'),
}


def write_stardict(out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)

    idx = bytearray()
    dict_blob = bytearray()

    for word in sorted(WORDS):
        kind, text = WORDS[word]
        body = text.encode("utf-8")
        # Per-article type: a type character followed by a zero-terminated
        # body. Using per-entry types (rather than sametypesequence) is what
        # lets one entry be HTML and another plain in the same dictionary.
        entry = kind.encode("ascii") + body + b"\x00"
        offset = len(dict_blob)
        length = len(entry)
        dict_blob += entry
        idx += word.encode("utf-8") + b"\x00"
        idx += struct.pack(">II", offset, length)

    with open(os.path.join(out_dir, "smoke.dict"), "wb") as f:
        f.write(dict_blob)
    with open(os.path.join(out_dir, "smoke.idx"), "wb") as f:
        f.write(idx)
    with open(os.path.join(out_dir, "smoke.ifo"), "w", encoding="utf-8") as f:
        # First two lines must be exactly per upstream's parser (stardict.cc):
        # "StarDict's dict ifo file" then "version=…"; the rest are k=v pairs.
        #
        # No sametypesequence: each article carries its own type character
        # instead (see the entry construction above). A single global type
        # cannot express "one entry is HTML, another is plain", and the
        # cross-reference must be HTML or its markup is escaped into visible
        # text rather than becoming a link.
        f.write(
            "StarDict's dict ifo file\n"
            "version=3.0.0\n"
            "bookname=Smoke\n"
            "wordcount=%d\n"
            "idxfilesize=%d\n"
            "samplingfrequency=0\n" % (len(WORDS), len(idx))
        )
    return os.path.join(out_dir, "smoke.ifo")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make-smoke-stardict.py <output-dir>")
    print("wrote " + write_stardict(sys.argv[1]))