# Proposal

## Why

Looking up a word that pulls in embedded dictionary resources (e.g. DSL images/sounds) can crash the app or freeze the whole UI. Two defects in the loopback article server (`app/ArticleServer.cpp`) surface on the same flow:

1. **Use-after-free on a resource 404.** Serving `bres://`/`gdau://` calls into the engine, whose resource fetch spins a nested event loop. During that loop a WebView socket that already disconnected processes its pending `deleteLater()`, so the socket is freed; the server then writes the 404 to the dangling pointer and aborts (SIGSEGV in `QIODevice::write`).
2. **Self-deadlock on parallel resources.** The engine fetch holds the non-recursive `g_engineMutex` across that nested loop. When the WebView issues its resource requests in parallel, the nested loop delivers the next request on the same thread, and the re-entrant engine call locks the mutex forever — the Qt thread wedges and navigation stops responding.

Both happen on ordinary lookups (e.g. the `hello` article references a missing DSL `.bmp`), so article browsing is unreliable whenever a dictionary references resources.

## What Changes

- **Resource responses never write to a destroyed socket.** A resource/audio whose requesting connection closes during the engine fetch is dropped instead of crashing.
- **Concurrent resource fetches no longer deadlock the UI.** The engine boundary's serialization is made re-entrancy-safe, so parallel per-article resource requests complete and the UI stays responsive.
- **Missing/empty resources answer 404 without side effects.** The existing "missing resource does not break rendering" behavior is preserved and now also holds under concurrent loading and mid-flight disconnects.
- No user-visible UI additions; no new `gd_*` functions; no upstream `engine/` edits.

## Capabilities

### New Capabilities

- none — this restores required behavior of the existing article/resource surfaces.

### Modified Capabilities

- `lookup`: The "Embedded dictionary resources" requirement gains robustness guarantees — loading the article's embedded resources MUST NOT crash the app or freeze UI/navigation, including when several resources load concurrently and when a requesting client disconnects mid-load. The "Article rendering" requirement's no-crash/no-hang clause extends to the bound that resource loading happens within the same render.

## Impact

- `app/ArticleServer.cpp` / `.hpp` — hold each request socket via `QPointer` across the engine call and skip the response if it was destroyed; guard the writers. (`handle`/`writeReply`/`writeNotFound`/`writeBadRequest`/`writeServerError`.)
- `carve/gd_boundary.cc` — `g_engineMutex` becomes a `std::recursive_mutex` (with all its lock guards) so the nested-event-loop boundary functions tolerate same-thread re-entry (the ArticleServer serves parallel sockets on the Qt thread) while still serializing across threads. This is boundary/carve code, not upstream `engine/` (AGENTS.md rule 1); no new C API surface (rule 3).
- CI host smoke (`carve/smoke/main.cpp` path) exercised unchanged to confirm no boundary regression.
- No data migration; no settings/prefs changes.
