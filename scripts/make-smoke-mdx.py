#!/usr/bin/env python3
"""Generate a tiny MDict (.mdx) dictionary for the CI smoke test.

Writes smoke.mdx into the given directory: a spec-correct MDict v2.0 file with
a handful of UTF-16LE headwords and zlib-compressed record blocks.

Why this exists
---------------
The smoke tool had no MDX input at all, so the whole MDict import path -- and
in particular the engine's index build for it -- was never exercised by CI.
That gap let a defect ship in which the index build hangs forever on Android
(see openspec/changes/fix-iconv-nonprogress-loop): the charset wrapper retried
without consuming input and never terminated. A real dictionary that reproduces
it (collinslaw.zip) is copyrighted and cannot be committed, so this generator
produces an equivalent synthetic one: small, redistributable, and deterministic.

Format notes (v2.0, the shape the engine's MdictParser reads)
------------------------------------------------------------
    <4 bytes BE> header text size in bytes
    <header text> UTF-16LE, "<Key>Key</Key><Key>...</Key>" attribute blob
    <4 bytes LE> Adler-32 of the header text bytes
    <8 bytes BE> number of headword blocks            (qint64)
    <8 bytes BE> number of entries                    (qint64)
    <8 bytes BE> decompressed size of headword blocks (qint64)
    <8 bytes BE> headword-block-info size, compressed  (qint64)
    <8 bytes BE> headword-block size, compressed       (qint64)
    <4 bytes BE> Adler-32 over those five numbers
    <headword block info> zlib: per block, qint64 compressed + qint64
                          decompressed size
    <headword blocks>     zlib: per entry, qint64 article offset (into the
                          decompressed record stream) + NUL-terminated
                          UTF-16LE headword
    <record block info>   per block, qint64 compressed + qint64 decompressed
    <record blocks>       zlib: concatenated articles, each NUL-terminated
                          UTF-16LE

All multi-byte fields are big-endian except the first header checksum, which
MDict stores little-endian.

Usage: make-smoke-mdx.py <output-dir> [--encoding UTF-16LE]
"""

import os
import struct
import sys
import zlib

# Headwords used by the smoke tool. "smoke" is the word the CI assertions look
# up; the others give the index more than one entry so a partial walk is
# detectable, and exercise a non-ASCII path in one of them.
WORDS = {
    "smoke": "smoke - an MDX test entry for the smoke word.",
    "blood": "blood - another headword for the CI smoke test.",
    "cafe": "non-ASCII-free extra headword, so the block holds several entries.",
}

# MDict stores the offset in the *decompressed* record stream, so articles are
# laid out first and the headword index refers into the result.
def build_records(words):
    """Lay out article bodies and return (blob, offsets).

    Articles are written in SORTED headword order, because the headword index
    is ordered by headword and each entry's offset must point at that
    headword's own article. Writing them in declaration order while sorting the
    index produces a dictionary that loads but resolves nothing: every entry
    points at the wrong article.
    """
    blob = bytearray()
    offsets = {}
    for word in sorted(words):
        offsets[word] = len(blob)
        blob += words[word].encode("utf-16-le") + b"\x00\x00"
    return bytes(blob), offsets


def build_headword_block(words, offsets):
    """One block: qint64 record offset + NUL-terminated UTF-16LE headword."""
    block = bytearray()
    # Keys must be sorted; MDict's index is ordered.
    for word in sorted(words):
        block += struct.pack(">q", offsets[word])
        block += word.encode("utf-16-le") + b"\x00\x00"
    return bytes(block)


def build_block_info_records(words, headword_block: bytes, headword_z: bytes) -> bytes:
    """The per-block records inside the (compressed) headword-block info.

    v2.0 layout per block, as decodeHeadWordBlockInfo reads it:
        qint64  number of keywords in the block
        u16     byte size of the first headword
        ...     first headword, NUL-terminated
        u16     byte size of the last headword
        ...     last headword, NUL-terminated
        qint64  compressed size of the headword block
        qint64  decompressed size of the headword block
    Headword sizes count bytes (UTF-16LE, so 2 per character); the terminator
    is included in the skipped length, hence +2 below.
    """
    ordered = sorted(words)
    first_b = ordered[0].encode("utf-16-le")
    last_b = ordered[-1].encode("utf-16-le")

    # The size fields are CHARACTER counts, not byte counts: the reader skips
    # (size + 1) * 2 bytes for UTF-16LE, i.e. it adds the terminator itself and
    # doubles. Declaring byte lengths makes it skip twice as far as intended and
    # read the block sizes from the wrong offset (they come out 0, and the
    # dictionary then loads with no entries at all).
    rec = bytearray()
    rec += struct.pack(">q", len(ordered))
    rec += struct.pack(">H", len(ordered[0]))          # characters, not bytes
    rec += first_b + b"\x00\x00"
    rec += struct.pack(">H", len(ordered[-1]))         # characters, not bytes
    rec += last_b + b"\x00\x00"
    rec += struct.pack(">q", len(headword_z))
    rec += struct.pack(">q", len(headword_block))
    return bytes(rec)


def compress_block(payload: bytes) -> bytes:
    """Wrap a payload as an MDict compressed block.

    Every block begins with a 4-byte compression type and a 4-byte Adler-32 of
    the *decompressed* payload, then the compressed data. Type 0x02000000 is
    zlib. Writing the compressed bytes alone makes the reader treat the first
    payload bytes as the type/checksum header and fail the checksum test.
    """
    return (
        struct.pack(">I", 0x02000000)
        + struct.pack(">I", zlib.adler32(payload) & 0xFFFFFFFF)
        + zlib.compress(payload)
    )


def write_mdx(out_dir: str, encoding: str = "UTF-16LE") -> str:
    os.makedirs(out_dir, exist_ok=True)

    words = dict(WORDS)
    record_blob, offsets = build_records(words)

    headword_block = build_headword_block(words, offsets)
    headword_z = compress_block(headword_block)

    # The headword-block INFO is itself a compressed block, and the engine
    # decompresses it before decoding the per-block records (visible in the
    # device trace as "HWI about to decompress -> pCB enter type=0x02000000").
    # Writing the records uncompressed makes the parser consume the wrong
    # number of bytes and start the headword block mid-header.
    block_info_records = build_block_info_records(words, headword_block, headword_z)
    block_info_z = compress_block(block_info_records)

    # One record block holding every article.
    record_z = compress_block(record_blob)

    # Header text. The engine parses this as an XML attribute list on a
    # <Dictionary> element and reads RequiredEngineVersion to decide the file
    # layout: with it at 2.0 the parser uses 64-bit numbers and u16 headword
    # sizes; without it the file is read as v1.x (32-bit) and every field
    # after the header is misparsed.
    attrs = [
        ('GeneratedByEngineVersion', '2.0'),
        ('RequiredEngineVersion', '2.0'),
        ('Format', 'Html'),
        ('KeyCaseSensitive', 'No'),
        ('StripKey', 'Yes'),
        ('Encoding', encoding),
        ('Description', 'Synthetic MDict dictionary for the Aurelex smoke test.'),
        ('StyleSheet', 'p { margin: 0; }'),
    ]
    attr_text = " ".join('%s="%s"' % (k, v) for k, v in attrs)
    header_text = "<Dictionary %s/>" % attr_text
    header_bytes = header_text.encode("utf-16-le")

    out = bytearray()
    out += struct.pack(">i", len(header_bytes))
    out += header_bytes
    # Header checksum is little-endian, unlike every other field.
    out += struct.pack("<I", zlib.adler32(header_bytes) & 0xFFFFFFFF)

    # Five qint64 count/size fields, checksummed as a group. The third is the
    # DECOMPRESSED size of the headword-block info, the fourth its compressed
    # size, the fifth the compressed headword-block size.
    five = struct.pack(
        ">q", 1
    ) + struct.pack(
        ">q", len(words)
    ) + struct.pack(
        ">q", len(block_info_records)
    ) + struct.pack(
        ">q", len(block_info_z)
    ) + struct.pack(
        ">q", len(headword_z)
    )
    out += five
    out += struct.pack(">I", zlib.adler32(five) & 0xFFFFFFFF)

    out += block_info_z
    out += headword_z

    # Record block info. The engine seeks past the headword block and reads:
    #   qint64 numRecordBlocks
    #   qint64 totalRecords          (skipped)
    #   qint64 recordInfoSize        (bytes of the per-block array that follows)
    #   qint64 totalRecordsSize_     (sum of decompressed sizes)
    # then numRecordBlocks pairs of (compressedSize, decompressedSize), and
    # finally the block data. It computes the data position as
    # "position after the preamble + recordInfoSize", so recordInfoSize must be
    # exactly the size of the pair array or the blocks are read from the wrong
    # offset (and the reader sees a bogus compression type).
    number_type_size = 8
    record_info_size = 1 * (2 * number_type_size)
    preamble = (
        struct.pack(">q", 1)  # numRecordBlocks
        + struct.pack(">q", len(words))  # totalRecords
        + struct.pack(">q", record_info_size)
        + struct.pack(">q", len(record_blob))  # totalRecordsSize_
    )
    pairs = struct.pack(">q", len(record_z)) + struct.pack(">q", len(record_blob))
    assert len(pairs) == record_info_size

    out += preamble
    out += pairs
    out += record_z

    path = os.path.join(out_dir, "smoke.mdx")
    with open(path, "wb") as f:
        f.write(out)
    return path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: make-smoke-mdx.py <output-dir> [--encoding NAME]")
    enc = "UTF-16LE"
    if "--encoding" in sys.argv:
        enc = sys.argv[sys.argv.index("--encoding") + 1]
    print("wrote " + write_mdx(sys.argv[1], enc))
