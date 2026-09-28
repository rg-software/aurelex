#!/usr/bin/env python3
"""Generate small example DSL dictionaries for Aurelex (and their .dsl.dz
dictzip-compressed variants).

Produces into a target directory (default: examples/dictionaries):
  aurelex-basic.dsl        - small EN dictionary exercising DSL markup
  aurelex-lingvo.dsl       - EN <-> RU mini dictionary (second language)
  aurelex-phrasebook.dsl   - common phrases
  <name>.dsl.dz            - dictzip-compressed variant of each (real
                             "RA" random-access extra field, so the engine's
                             dictzip reader can seek; plain gzip would not load)
  aurelex-basic.dsl.files/ - sibling resource dir for aurelex-basic, holding
                             aurelex-resource.svg

The "sun" headword in aurelex-basic carries a `[*]...[/*]` hidden zone, so
the generated fixtures always cover the optional-parts expander (see the
`sample-dictionaries` spec) without hand-editing a dictionary.

The "badge" headword carries a `[s]...[/s]` resource reference, so the
fixtures also cover the embedded-resource path (bres:// resolution) that
fix-article-server-gui-reentrancy exercises. The .dsl.files/ name is the one
the engine derives for BOTH variants: for aurelex-basic.dsl it is
resourceDir1/resourceDir2 directly, and for aurelex-basic.dsl.dz the engine
strips the trailing ".dz" to find it (engine/src/dict/dsl.cc:279-284).

Usage: make-example-dicts.py [output-dir]
"""
import os
import re
import struct
import sys
import zlib

BASIC = """\
#NAME "Aurelex Basic"
#INDEX_LANG "en"
#CONTENTS_LANG "en"
apple
\t[m1]a round fruit with red or green skin[/m]
\t[m2][i]She ate an apple.[/i][/m]
\t[trn]fructus[/trn]
\t[alt]fruit[/alt]
book
\t[m1]a set of printed pages bound together for reading[/m]
\t[ex]I am reading a [b]good[/b] book.[/ex]
\t[ref]read[/ref]
run
\t[m1]to move quickly on foot[/m]
\t[m2]present: [b]run[/b]; past: [b]ran[/b][/m]
\t[url]https://example.com/run[/url]
water
\t[m1]the clear liquid that falls as rain and fills rivers[/m]
\t[!trn]aqua[/!trn]
\t[note]Drink more water.[/note]
sun
\t[m1]the star that gives Earth light and warmth[/m]
\t[m2]the Sun is a star[/m]
\t[*]Extra: its light takes about 8 minutes to reach Earth.[/*]
\t[ref]light[/ref]
badge
\t[m1]embeds a bundled image so the embedded-resource path has a fixture[/m]
\t[s]aurelex-resource.svg[/s]
"""

LINGVO = """\
#NAME "Aurelex Lingvo EN-RU"
#INDEX_LANG "en"
#CONTENTS_LANG "ru"
hello
\t[m1]привет, здравствуйте[/m]
\t[trn]greeting[/trn]
goodbye
\t[m1]до свидания, прощай[/m]
friend
\t[m1]друг[/m]
\t[m2][i]a friend[/i] - друг[/m]
house
\t[m1]дом, здание[/m]
\t[m2][b]house[/b] - дом[/m]
"""

PHRASEBOOK = """\
#NAME "Aurelex Phrasebook"
#INDEX_LANG "en"
#CONTENTS_LANG "en"
good morning
\t[m1]a greeting used in the morning[/m]
\t[trn]Good morning![/trn]
how are you
\t[m1]a friendly inquiry about someone's state[/m]
\t[ex]How are you today?[/ex]
thank you
\t[m1]a polite expression of gratitude[/m]
\t[note]Also: thanks, thanks a lot.[/note]
where is the bathroom
\t[m1]asking for the location of a restroom[/m]
"""


def _encode_dsl(text: str) -> bytes:
    # UTF-8 with BOM; goldendict's DSL reader detects the encoding from it.
    return b"\xef\xbb\xbf" + text.encode("utf-8")


# The resource the "badge" headword references. Deliberately tiny and a valid
# standalone SVG: the smoke test asserts on "<svg" being present, so a corrupt
# or empty file fails the check rather than passing a size test.
RESOURCE_NAME = "aurelex-resource.svg"
RESOURCE_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" \
viewBox="0 0 16 16"><rect width="16" height="16" fill="#c2185b"/></svg>\n"""


def _dz_named(content: str) -> str:
    # The .dsl.dz variant is a second, separately-loaded dictionary; give it a
    # distinct display name so it doesn't collide with the plain .dsl in a scan
    # of a folder that contains both (e.g. "Aurelex Basic" -> "Aurelex Basic (DZ)").
    return re.sub(r'(#NAME\s+"[^"]*)"', r'\1 (DZ)"', content, count=1)


def make_dictzip(data: bytes, chunk_length: int = 16384) -> bytes:
    """Build a real dictzip (.dz) file from raw DSL bytes.

    Structure (RFC 1952 gzip + dictd 'RA' extra field):
      - gzip header with FEXTRA set
      - 'RA' subfield: version=1, chunkLength, chunkCount, then the compressed
        size of each chunk (the engine's dictzip reader uses these to seek)
      - one continuous deflate stream; each chunk is terminated with a FULL
        flush. A full flush resets the deflate history, so any chunk can be
        inflated in isolation - which is what random access does. A *sync* flush
        only flushes pending output and keeps the history, so a later chunk's
        back-references reach into an earlier chunk and a reader that inflates one
        chunk alone fails with "invalid distance too far back" (the engine does
        exactly that, so >1-chunk files were unreadable past the first chunk).
      - gzip trailer: crc32 + ISIZE of the uncompressed data
    """
    chunks = []
    co = zlib.compressobj(level=9, wbits=-zlib.MAX_WBITS)  # raw deflate
    off = 0
    while off < len(data):
        block = data[off:off + chunk_length]
        compressed = co.compress(block)
        compressed += co.flush(zlib.Z_FULL_FLUSH)
        chunks.append(compressed)
        off += chunk_length
    # The final chunk: pad to full block? No - the reader's count is derived
    # from avail_out, so a short final chunk is fine. Finish the stream.
    compressed = co.flush()  # Z_FINISH, typically empty after full flushes
    if compressed:
        chunks.append(compressed)

    chunk_count = len(chunks)
    extra_data = struct.pack("<HHH", 1, chunk_length, chunk_count)
    for c in chunks:
        extra_data += struct.pack("<H", len(c))
    # RA subfield: SI1 SI2 LEN(len bytes of data)
    subfield = b"RA" + struct.pack("<H", len(extra_data)) + extra_data
    xlen = len(subfield)

    header = struct.pack("<BBBBIBB", 0x1F, 0x8B, 8, 0x04, 0, 0, 3)  # FEXTRA
    header += struct.pack("<H", xlen)
    header += subfield

    body = b"".join(chunks)
    trailer = struct.pack("<II", zlib.crc32(data) & 0xFFFFFFFF, len(data) & 0xFFFFFFFF)
    return header + body + trailer


def write_dictionaries(out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name, content in (
        ("aurelex-basic", BASIC),
        ("aurelex-lingvo", LINGVO),
        ("aurelex-phrasebook", PHRASEBOOK),
    ):
        raw = _encode_dsl(content)
        dsl_path = os.path.join(out_dir, name + ".dsl")
        with open(dsl_path, "wb") as f:
            f.write(raw)
        written.append(dsl_path)

        dz_path = os.path.join(out_dir, name + ".dsl.dz")
        with open(dz_path, "wb") as f:
            f.write(make_dictzip(_encode_dsl(_dz_named(content))))
        written.append(dz_path)

    # Sibling resource dir for aurelex-basic. Only aurelex-basic references a
    # resource, so this is the only .files/ tree emitted. CI copies the whole
    # directory next to the dictionary it copies (see engine-smoke.yml).
    res_dir = os.path.join(out_dir, "aurelex-basic.dsl.files")
    os.makedirs(res_dir, exist_ok=True)
    res_path = os.path.join(res_dir, RESOURCE_NAME)
    with open(res_path, "wb") as f:
        f.write(RESOURCE_SVG)
    written.append(res_path)
    return written


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "dictionaries"
    )
    for p in write_dictionaries(out):
        print("wrote", p)
