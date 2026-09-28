# Design - fix dictzip chunk full flush

## D1 - Full flush, not sync flush, at chunk boundaries

dictzip splits a gzip deflate stream at byte-aligned boundaries and records each
chunk's compressed size in the `RA` extra subfield, so a reader can seek to a
chunk and inflate it on its own. That only works if the deflate history is reset
at each boundary - i.e. each chunk is terminated with `Z_FULL_FLUSH`.

The writer used `Z_SYNC_FLUSH`. A sync flush emits pending output and aligns to a
byte boundary but keeps the 32 KiB sliding window, so the next chunk may still
reference bytes from earlier chunks. A cold-start inflate of that chunk then hits
a back-reference before its own output and errors with "invalid distance too far
back". Confirmed by inflating each chunk of the reported file with a fresh
`decompressobj(-15)`: chunk 0 succeeds, chunks 1-9 all fail.

`Z_FULL_FLUSH` is the documented requirement for independently decodable gzip
members/points, and it is what the original `dictzip` tool uses. The change is one
token; the stream remains a valid continuous deflate stream, so a straight
sequential reader is unaffected.

Rejected: emitting each chunk as its own gzip member. dictzip's `RA` scheme is a
single member with an index; a multi-member file would not be dictzip and the
reader would not find the chunk index.

Rejected: inflating chunks with a retained window from the previous chunk. That
is the reader's business and it is not how the format is specified; the producer
must make chunks independently decodable.

## D2 - A test that reads the way the engine does

`read_dz` in the converter tests does `gzip.decompress`, which reconstructs the
whole window and cannot observe the defect. The new `DictzipTests`:

- parses the gzip `RA` subfield (version, chunk length, chunk count, per-chunk
  compressed sizes),
- inflates each chunk with a fresh `zlib.decompressobj(-zlib.MAX_WBITS)`,
  mirroring the engine's seek-and-inflate,
- sums the chunk outputs and asserts they equal the input,
- keeps a full-stream round-trip so a writer that breaks sequential reading is
  also caught.

Verified both ways: with `Z_SYNC_FLUSH` the test errors with exactly
`invalid distance too far back`; with `Z_FULL_FLUSH` it passes. The payload mixes
repetitive and incompressible data and is large enough to span several chunks, so
the cross-chunk reference occurs.

## D3 - Fixtures were blind to it by construction

Every committed fixture is under one chunk, so the whole stream is chunk 0 and no
chunk ever references another. The fixtures are regenerated with the corrected
writer (their bytes change: a full flush differs from a sync flush), and the
regression is carried by the unit test rather than the fixtures, since a fixture
small enough to be readable is also small enough to be single-chunk.

## Risks

- **Larger output.** A full flush restarts the compressor's match search, so the
  compressed size grows slightly (the reported file went 55248 -> 62180 bytes for
  identical content). Irrelevant next to a dictionary's size, and the alternative
  is an unreadable file.
- **Reader expectations.** Some dictzip readers decompress the whole stream and
  only use chunks for seeking; a full flush is valid in a continuous stream, so
  they keep working. The one reader that matters here (goldendict) seeks and
  inflates per chunk and is fixed by this.
- **Old files.** Files already produced with the sync flush stay broken until
  regenerated. The tool cannot repair files it did not just write; the change
  notes how to repair one (decompress + rewrite).
