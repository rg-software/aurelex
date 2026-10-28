# Design

## Root cause

`Iconv::convert` (`engine/src/common/iconv.cc`) ends every successful conversion with a
shift-sequence flush:

```cpp
result = iconv( state, NULL, NULL, (char **)&outBufPtr, &outBufLeft );
```

POSIX blesses `NULL` here as "reset the shift state". Bionic on the reporting device
(Huawei Android 10, `iconv+40`) dereferences it instead: all six tombstones show
`SIGSEGV fault addr 0x0` with `x1=0, x2=0` (the `inbuf`/`inbytesleft` args) on a pooled
scan thread, ~1s after `scan start`. That call site is the *only* `iconv()` call in the
whole engine passing NULL (the other two pass stack addresses), so the register state
identifies it uniquely — no symbolication needed.

The flush is dead code for this class: `Iconv::Iconv(from)` opens
`iconv_open(Text::utf8, from)` — the target is always UTF-8, which is stateless and has
no shift sequences to flush. glibc and newer Bionic tolerate the NULL reset, which is why
host CI and the Android 15 test devices never saw it.

## Fix

New patch `0007-iconv-no-null-flush`: delete the flush block. Keep 0005's loop guards
untouched (they handle the orthogonal non-progress hang).

Alternatives rejected:

- `#ifdef Q_OS_ANDROID` guard — keeps a crash-shaped call on other platforms for no
  benefit; the flush writes nothing for a UTF-8 target anywhere.
- Dummy non-NULL pointers with `*inbytesleft == 0` — relies on undocumented backend
  behavior instead of removing the unneeded call.

## Verification

1. Host suites: `app/tests` (ctest set) + `scripts/tests` + `carve/smoke` on both
   fixture layouts (MDX-only and combined).
2. Device (VOG-L29, Android 10, debug build): stage `au_kaikki_ru-ru.dsl.dz`, cold
   start — scan completes, dictionary listed, a headword resolves, no tombstone.
3. `docs/TESTING.md`: record the row.
