# Tasks

## 1. Article server: never write to a destroyed socket

- [x] 1.1 Hold the request socket by `QPointer` in `onIncomingConnection`'s `readyRead` handler and pass it through `handle()`; guard the handler entry — done: `app/ArticleServer.cpp` (`sockGuard`), `app/ArticleServer.hpp`
- [x] 1.2 Re-check the socket immediately after the engine call in `handle()` and skip the response if it was destroyed by the nested event loop; change `writeReply`/`writeNotFound`/`writeBadRequest`/`writeServerError` to take the guarded socket and no-op when null — done: `app/ArticleServer.cpp`
- [x] 1.3 Verify no raw `QTcpSocket*` dereference remains after the engine call (grep `socket->` in the bres/gdau path) — done: all post-fetch uses are behind the `socket.isNull()` return

## 2. Boundary: make engine serialization re-entrancy-safe

- [x] 2.1 Change `g_engineMutex` to `std::recursive_mutex` and update every `g_engineMutex` lock guard accordingly; leave `g_ftsProgressMutex` a plain `std::mutex` — done: `carve/gd_boundary.cc` (30 guards) 
- [x] 2.2 Document inline why the mutex is recursive (nested `QEventLoop` in `gd_lookup`/`gd_suggest`/`fetchResource`, and the ArticleServer serving parallel sockets on the Qt thread) — done: comment at the declaration

## 3. Regression checks

- [x] 3.1 Rebuild the host smoke tool and run the CI fixture (StarDict + `.dsl.dz` + nested `.dsl`): `gd_scan_dicts→3`, `gd_lookup("smoke")→2894 B`, `FTS_BODY=OK`, `FTS_WILD=OK`, `REMOVE_DICT=OK`, exit 0 — done
- [x] 3.2 Grep-verify no upstream `engine/` or `patches/` files changed — done: diff touches only `app/ArticleServer.*` and `carve/gd_boundary.cc`

## 4. On-device verification

- [x] 4.1 Build + install the Debug APK, look up `hello` (article references a missing DSL `.bmp`): the article renders and the app does not crash — done (crash-buffer empty; PID stable)
- [x] 4.2 With that article displayed, switch tabs (Dicts/Groups/FTS/… ) and back; confirm navigation is responsive and the article re-renders on return — done
- [x] 4.3 Stress: rapidly cycle all tabs while the article is open; confirm no freeze, no deadlock (CPU not pegged / UI reacts), and no crash — done
