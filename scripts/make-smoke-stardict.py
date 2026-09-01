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
    "smoke": "An MDX test entry for the smoke word.",
    "blood": "Another headword for the CI smoke test.",
}


def write_stardict(out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)

    idx = bytearray()
    dict_blob = bytearray()

    for word in sorted(WORDS):
        body = WORDS[word].encode("utf-8")
        entry = body + b"\x00"
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
        # sametypesequence=m marks every article body as a plain UTF-8, zero-
        # terminated entry — without it the parser misreads the leading ASCII
        # byte of each raw body as an entry-size marker and drops the article.
        f.write(
            "StarDict's dict ifo file\n"
            "version=3.0.0\n"
            "bookname=Smoke\n"
            "sametypesequence=m\n"
            "wordcount=%d\n"
            "idxfilesize=%d\n"
            "samplingfrequency=0\n" % (len(WORDS), len(idx))
        )
    return os.path.join(out_dir, "smoke.ifo")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make-smoke-stardict.py <output-dir>")
    print("wrote " + write_stardict(sys.argv[1]))