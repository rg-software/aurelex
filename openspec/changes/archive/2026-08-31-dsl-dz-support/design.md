## Context

The archived v1 change declared `DSL .dsl/.dsl.dz` as supported, and the carve
already links the dictzip reader (`dict/utils/dictzip.c`) plus the `.dsl.dz`
scan filter in `gd_scan_dicts`. What was missing: a **real** compressed fixture
and a verification run — plain gzip would silently fail to load because the
engine's `dictzip.c` requires the dictd "RA" random-access extra field.

## Decisions

### D1. Example set: three shapes, each with a compressed variant
`examples/dictionaries/` ships three small packs so device testing exercises
distinct DSL features:
- `aurelex-basic` — plain EN; DSL markup (`[m1]`, `[b]`, `[i]`, `[url]`,
  `[ref]`, `[trn]`, `[alt]`, `[ex]`, `[note]`, `[!trn]`).
- `aurelex-lingvo` — bilingual EN↔RU (`#CONTENTS_LANG "ru"`), non-ASCII
  content/encoding.
- `aurelex-phrasebook` — multi-word headwords ("how are you").

Each also exists as `<name>.dsl.dz`. Files are UTF-8 with BOM (the DSL reader's
encoding detection uses the BOM).

### D2. Real dictzip generator
`scripts/make-example-dicts.py` produces genuine `.dsl.dz` files — not plain
gzip. The writer:
- builds an RFC 1952 gzip header with `FEXTRA` and the dictd `RA` subfield
  (version=1, chunkLength, chunkCount, per-chunk compressed sizes),
- emits one continuous raw-deflate stream where each ~16 KiB chunk ends with a
  `Z_SYNC_FLUSH` (matching the reader's per-chunk `inflate(Z_PARTIAL_FLUSH)`),
- appends the gzip trailer (crc32 + ISIZE).

Regenerating is `python scripts/make-example-dicts.py` (writes into
`examples/dictionaries/`).

### D3. Verification gate
Host: scan a folder containing the six files → `gd_scan_dicts` returns 6; look
up headwords from each pack (single word, non-ASCII, multi-word) → non-empty
`gdarticlebody` HTML. On-device: pick the `examples/dictionaries/` folder in the
app and confirm all 6 list + look up (task-gated, requires the phone test pass).

## Risks

| Risk | Mitigation |
| --- | --- |
| My generator emits a format the engine reader rejects | Verified on host: `.dsl.dz` loads and returns identical HTML to `.dsl` (2892 B for "apple"); the reader is the ground truth |
| `.dsl.dz` fails only on-device (filesystem/SAF staging) | On-device verification is an explicit open task; `.dz` is already in the SAF staging extension list |
| Example dictionaries drift from the generator | Files are regenerable in one command; smoke CI can assert they load |
