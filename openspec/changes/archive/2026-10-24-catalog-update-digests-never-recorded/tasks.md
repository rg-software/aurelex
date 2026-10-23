# Tasks

## 1. Move the clear (app/EngineController.cpp)

- [x] 1.1 `m_downloadRequested.clear()` relocated from the post-loop reset
      block to before the request-building loop in `startCatalogDownload`
- [x] 1.2 Change validates; existing C++ catalog tests unaffected (parser
      fixtures untouched)

## 2. Verification

- [x] 2.1 Diff review: populate → JNI start → terminal record now shares one
      map lifetime; no other writer/reader of `m_downloadRequested` changes
      meaning (readers: `recordInstalledDigests` only; writers: the loop only)
- [x] 2.2 Post-fix behavior on device needs one reinstall per entry to
      establish the baseline (no backfill by design)
