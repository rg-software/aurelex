## Why

The loopback article server resolves `bres://`/`gdau://` engine resources by calling the `gd_*` boundary **on the Qt GUI thread**, and several `gd_*` entry points drive an async engine request to completion by pumping a nested `QEventLoop` (`carve/gd_boundary.cc`). That nested loop re-enters the whole GUI thread: input events, timers, other sockets, and the QML engine all keep running while an engine call is in flight and the engine lock is held.

Two user-visible failures follow, both observed on a ThinkPhone (Android 15, `org.aurelex.pocket.dictionary`):

1. **UI freeze.** `fetchResource` returns `-3` only when its 15-second `QTimer` fires, because the sole other exit is the request's own `finished` signal. Every `-3` in logcat is therefore a 15-second block of the GUI thread. Two occurred in the fatal session (`21:59:39.165`, `22:00:34.209`), each for a resource the engine could not load.
2. **Native crash.** At `22:00:34.966` the GUI thread took `SIGSEGV` in `QQmlData::isSignalConnected`, dispatched from `QIODevice::channelReadyRead` — i.e. a socket `readyRead` signal was being delivered to the QML engine 46 ms after the QtWebEngine render process died, while a `gd_get_resource` nested loop was running and QML was concurrently mutating the object graph. `am_crash` was logged; there was no `am_anr`.

`228ebf2` ("stop resource crash and UI deadlock") already patched two symptoms of this root cause: a `QPointer` guard around the request socket, and a recursive `g_engineMutex`. Both are correct and stay. Neither removes the nested event loop from the GUI thread, and the recursive mutex actively permits the unbounded same-thread re-entry that crashed. The root cause has to go.

## What Changes

- **Resolve engine resources off the GUI thread.** `ArticleServer` hands each `bres://`/`gdau://` request to a worker thread, then delivers the finished bytes (or a failure) back to the GUI thread with a queued signal. The GUI thread never blocks on the engine and never runs a nested event loop for a resource.
- **Stop holding `g_engineMutex` across a nested event loop.** Resource resolution must not pin every other thread's `gd_*` call for the duration of a wait.
- **Bound resource resolution with a short deadline.** A resource that cannot be produced fails fast and is reported to the article as a normal 404/5xx, instead of stalling the GUI thread for 15 seconds.
- **Give the request socket explicit ownership.** Replace the raw `QPointer` + heap-allocated parse state (`buf`, `headersParsed`) with a per-connection context object whose lifetime is tied to the socket, so a request cannot be answered on a dead socket and per-connection state cannot leak when a socket dies without emitting `disconnected`.
- **Keep the existing guarantees.** Concurrent resource requests stay independent; an abandoned request is still dropped silently; assets and the `qrc://`-mirroring routes are unaffected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lookup`: the "Embedded dictionary resources" requirement gains an explicit guarantee that resolving a resource MUST NOT run a nested event loop on the GUI thread and MUST NOT block the GUI thread for a fixed timeout. Existing scenarios ("Concurrent resource requests do not freeze the article", "Navigation stays responsive while an article with resources is shown") are strengthened rather than replaced.

## Impact

- `app/ArticleServer.hpp` / `app/ArticleServer.cpp` — per-connection context object; worker dispatch instead of inline engine calls; `handle()` no longer calls `gd_get_resource`/`gd_get_audio` directly.
- `carve/gd_boundary.cc` — resource resolution split so the wait happens off the GUI thread; `g_engineMutex` is no longer held across the wait; the 15 s timeout is replaced with a short deadline.
- `app/EngineController.cpp` — no API change expected; `articleBaseUrl` and the existing `baseUrlChanged` wiring stay as-is.
- `patches/` — unchanged. This is boundary-layer and app work; no upstream engine source is edited, per AGENTS.md golden rule 1.
- Tests: a boundary-level test that a resource request completes without a nested GUI event loop, and that a never-completing request is abandoned within the short deadline.

### Adjacent defect found while diagnosing (not in scope here)

`EngineController` passes `appDir + "/index"` as the engine's `indicesDir`, and the engine concatenates `indicesDir + dictId` with no separator (`engine/src/dict/dsl.cc:1752`). Index files therefore land as siblings named `files/index<md5>` while the created `files/index/` directory stays empty. Harmless today, but it makes on-device index inspection misleading. Filed separately.
