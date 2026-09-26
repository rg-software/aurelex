# Design — Article server: crash + UI hang under embedded resources

## Context

Articles are rendered in a QtWebView, and every engine URL scheme the engine
emits (`bres://`, `gdau://`) is rewritten to a loopback HTTP origin served by
`app/ArticleServer.cpp` (see the `all-qt-ui-port` design D3). The WebView then
fetches those resources over local sockets, in parallel, while the user is
already able to interact with the app.

Serving a resource calls into the engine boundary:

- `ArticleServer::handle()` → `gd_get_resource` / `gd_get_audio`
- `carve/gd_boundary.cc` `fetchResource()` looks up the dictionary under
  `g_engineMutex`, starts an async `Dictionary::DataRequest`, and drives it to
  completion with a nested `QEventLoop` (bounded by a 15 s timer).

Two properties collide with this design:

1. `fetchResource` holds `g_engineMutex` for the whole function — including the
   nested `QEventLoop`.
2. The `QEventLoop` processes *all* events on its thread, which is the same Qt
   thread that runs `ArticleServer` (`onIncomingConnection` / `readyRead`).

The observed failure on the `hello` article (references a missing DSL `.bmp`):
render starts, the WebView fires several `bres://` requests in parallel, the
first `fetchResource` enters its nested loop holding the mutex, and the loop
delivers the next socket's `readyRead` → `fetchResource` again on the same
thread → `std::mutex` self-lock → Qt thread wedged forever (0 % CPU, frozen UI).

Before the UI ever gets there, a second defect crashes first: when the WebView
abandons/aborts a request, the socket's `disconnected` handler runs and
`deleteLater()` is processed by that same nested loop, freeing the `QTcpSocket`;
`handle()` then writes the 404 to the dangling pointer → SIGSEGV in
`QIODevice::write`.

## Goals / Non-Goals

**Goals**
- Article rendering with embedded resources (present, missing, empty, or
  concurrent) never crashes and never freezes the UI/navigation.
- Keep the loopback-server model and the `gd_*` C boundary unchanged in shape
  (AGENTS.md rule 3); no upstream `engine/` edits (rule 1).
- Keep cross-thread serialization of the non-thread-safe engine intact.

**Non-Goals**
- Making the engine itself re-entrant or thread-safe.
- Redesigning resource serving to be asynchronous/off the Qt thread.
- Any user-visible UI change; any change to dictionary formats or storage.

## Decisions

### D1: Hold the request socket via `QPointer`, not a raw pointer
`handle()` and the four response writers take `const QPointer<QTcpSocket>&`. The
`readyRead` handler captures a `QPointer` guard. Any write checks
`socket.isNull()` first; `handle()` also re-checks immediately after the engine
call returns. If the WebView dropped the request while the resource was loading,
the response is skipped instead of written to freed memory.

**Why not** only defer `deleteLater` in the `disconnected` handler: the nested
loop can outlive one event turn, and a raw pointer is still used after the
engine call. `QPointer` nulls on destruction regardless of *when* the deferred
delete runs, which is what makes it robust to re-entrancy.

### D2: Make `g_engineMutex` a `std::recursive_mutex`
The deadlock is same-thread re-entry of a boundary function through its own
nested event loop. A recursive mutex lets that re-entrant call proceed while
still serializing calls from *different* threads (the engine pool, the FTS
worker, and the Qt thread). All ~30 guards on `g_engineMutex` are updated; the
separate `g_ftsProgressMutex` stays a plain mutex (it is never entered
re-entrantly and must stay non-blocking behind a long build).

**Alternatives considered:**
- *Release `g_engineMutex` before the nested wait* (scope the lock to the
  dictionary lookup + request start). Fixes the self-lock, but drops the
  protection that a concurrent `gd_remove_dict` currently has against freeing a
  dictionary whose request is still in flight. Rejected as a safety regression.
- *Serialize ArticleServer so it never re-enters* `fetchResource` (a pending
  queue per connection). Larger refactor, and it only fixes this one re-entry
  path while recreating the same hazard for any future nested-loop boundary
  call. Rejected for now.
- *Run `ArticleServer` on its own thread.* Does not by itself prevent the
  re-entry (the server's other sockets run on that thread too) and adds
  thread-affinity plumbing. Rejected as insufficient and heavier.
- *Rewrite the boundary to a callback/poll resource API.* The correct
  long-term shape, but a much larger C-API change than this fix warrants.

### D3: Keep the change in the app + carve boundary only
`ArticleServer` is app code; `gd_boundary.cc` is our carve (not upstream). No
`patches/` entry is needed, and no new `gd_*` function is added. The CI host
smoke test (which links the carve) is re-run to confirm the mutex change does
not alter engine behavior.

## Risks / Trade-offs

- **[Recursive mutex hides a latent lock-order bug]** → Same-thread re-entry is
  the *only* new allowance; cross-thread ordering is unchanged, and the
  documented order (`g_engineMutex` → `g_ftsProgressMutex`) is preserved.
- **[Nested depth under many concurrent resources]** → Bounded by the WebView's
  per-host connection limit (single digits); each nested loop exits when its
  request completes, so the stack unwinds normally.
- **[A dropped (null) socket means the WebView gets no response]** → That is the
  correct outcome when the client already went away; the WebView is no longer
  waiting. Missing/empty resources still answer 404 when the socket is alive.
- **[`QPointer` check is not a substitute for real concurrency control]** →
  ArticleServer remains single-threaded on the Qt thread; `QPointer` only covers
  destruction, which is exactly the observed failure.

## Migration Plan

No data migration. Pure code fix: on rollback, the crash/hang returns but no
persisted state changes. Verify with the host smoke (`gd_lookup`/FTS/group/
remove unchanged) plus an on-device pass: look up a word whose article
references missing resources, then switch tabs and back and confirm the UI stays
responsive and no crash occurs.

## Open Questions

None.
