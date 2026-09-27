## 1. Settle the blocking risk first

- [x] 1.1 Extend the CI smoke tool to drive a `bres://` resource load from a thread that is neither the constructing thread nor the caller of `gd_scan_dicts`, proving the engine tolerates a third thread identity (design.md D1 risk). Treat any thread-affinity assertion as a blocking failure and stop here if one appears — D1 is invalid until this passes
- [x] 1.2 Record the smoke command and its output in this change so the result is reproducible

## 2. Boundary: take the lock out of the wait

- [x] 2.1 Restructure `fetchResource` in `carve/gd_boundary.cc` into lock → issue request → unlock → bounded wait → lock → copy bytes → unlock, so `g_engineMutex` is not held across `loop.exec()` (design.md D2)
- [x] 2.2 Replace the inline `QTimer::singleShot( 15000, ... )` with a named deadline constant and a comment stating it is a worker-occupancy budget, not a responsiveness budget (design.md D3)
- [x] 2.3 Verified the isolation property with a host test (`app/tests/ArticleServerTest.cpp`): with request A stuck inside the engine, request B on a second connection is still answered, and a request that is abandoned mid-flight leaves no residue — a later request still resolves. D3 records that requests are *not* force-cancelled and why (`cancel()` only sets a flag the runnable reads once at start, and the destructor blocks on `waitForFinished()` regardless), which is why the `gd_*` API stays unchanged. The test has teeth: dropping `kResourceSlotCount` to 1 makes it fail with "second request did not complete while the first was stuck"
- [x] 2.4 Confirm the recursive `g_engineMutex` and every `gd_*` signature are unchanged (design.md D5, proposal Non-Goals)

## 3. ArticleServer: per-connection state

- [x] 3.1 Introduce a `Connection` type holding the header buffer, the parsed flag, and a cancelled flag, owned by its socket (design.md D4)
- [x] 3.2 Replace the `new QByteArray` / `new bool` pair and its `disconnected`-only cleanup with the `Connection` object, so per-request state cannot leak when a socket dies without emitting `disconnected` (design.md D4)
- [x] 3.3 Reduce the `QPointer` liveness checks in `writeReply` / `writeNotFound` / `writeBadRequest` / `writeServerError` to the single `Connection` liveness check, keeping the "never answer on a dead socket" behaviour (design.md D5)
- [x] 3.4 Leave the asset and `qrc://`-mirroring routes reading files inline on the GUI thread (design.md Open Questions)

## 4. ArticleServer: move resolution off the GUI thread

- [x] 4.1 Add a `ResourceSlot` type — a real `QThread` — and start exactly 2 of them; do not use `QThreadPool`, whose workers have no event dispatcher for the boundary's nested `QEventLoop` (design.md D1)
- [x] 4.2 Add the app-side job queue the slots pull from, so a request that finds both slots busy waits in the app and never enters the engine (design.md D1)
- [x] 4.3 Dispatch each `bres://` / `gdau://` request to a slot and return the finished bytes or a failure to the GUI thread via a queued invoke whose context is the `Connection`, so the reply is dropped if the connection died. The post must happen *after* the slot writes the result — posting at submit time races, since the GUI loop could run the delivery first
- [x] 4.4 Confirm `handle()` no longer calls `gd_get_resource` / `gd_get_audio` on the GUI thread, and that no nested event loop remains on it
- [x] 4.5 Stop and join both slot threads in `ArticleServer`'s teardown, and assert the join actually drained all queued work (an in-flight counter, checked after the join). The design's original "assert the engine is still alive" has no probe to use: the app never calls `gd_cleanup()` (only the smoke tool does), so there is no in-process teardown to order against today — see the note on `s_liveInstances` in the header, which is what a future `gd_cleanup()` call site must assert against (design.md Risks)

## 5. Verify

There is no app-level test harness in this repo (only `carve/smoke` and a Python script), so the app-side pool is covered by a new host test that links `app/ArticleServer.cpp` against stubbed `gd_get_resource` / `gd_get_audio`. Build and run it with:

```
cmake -S app/tests -B build-article-server-test -DCMAKE_PREFIX_PATH=C:/Qt/6.6.3/msvc2019_64 -G "Visual Studio 17 2022" -A x64
cmake --build build-article-server-test --config Release
build-article-server-test/Release/article_server_test.exe   # exit 0 = pass
```

- [x] 5.1 Covered by the host test: while one resource request is stuck in the engine, the main thread still accepts a second connection and delivers its reply, which is the observable form of "no nested GUI event loop and no GUI block". The structural half (handle() only enqueues; no gd_* / nested loop on the main thread) is confirmed by inspection of `app/ArticleServer.cpp`
- [ ] 5.2 A boundary-level test that a request which never completes is abandoned within the deadline, reporting the resource missing. NOT covered: it needs a fixture that hangs inside the real engine, and the deadline is 15 s. The code path is unchanged other than the constant's name and the surrounding lock scope, so this is low risk but genuinely untested
- [x] 5.3 Covered by the host test: concurrent requests are independent (isolation check), and abandoning a request leaves no residue — a later request for the same server still resolves. "Keeps the GUI thread accepting input" is represented by the second connection being served while the first is stuck
- [x] 5.4 Re-ran the full CI smoke suite locally after the boundary change: exit 0, all scenarios pass, including `RESOURCE_ON_MAIN_THREAD=OK` and `RESOURCE_ON_WORKER_THREAD=OK` (the task-1.1 third-thread gate), groups, FTS, and dictionary removal. Note: the "228ebf2 scenarios (concurrent requests, abandoned request)" named in the earlier version of this task do not exist as smoke tests; the concurrent/abandoned scenarios are covered by the host test in 5.1/5.3 instead
- [ ] 5.5 On device (ThinkPhone, arm64, debug APK with the recompiled native code). Done: cold start binds the article server and reports init rc=1; a search renders an article that issues three concurrent `bres://` requests (kaikki tag SVGs 292/499/470 bytes), all resolved with no crash; 20 rapid Search<->Groups tab switches — destroying and rebuilding the article pane with resources in flight — leave the same app pid running and still serving resources. NOT done: the pathological case the bug came from (a dictionary whose resources do *not* resolve and time out at 15 s) is not reproducible on this healthy import, and isolated renderer termination could not be forced — the device is not rooted, and force-stopping the WebView provider makes Android kill the client app by design (`ActivityManager: Killing ... stop com.google.android.webview`), which is not a crash. Those two sub-cases remain unverified on-device; the hang/isolation case is covered by the host test in 5.3

## 6. Housekeeping

- [x] 6.1 No `AGENTS.md` change needed — the accessible-element IDs and the storage rules are untouched; this change is internal threading only, with no QML and no on-disk layout change
- [x] 6.2 Confirmed no out-of-patch edit under `engine/`: `git -C engine` shows 5 modified files, and all three patches in `patches/` reverse-apply cleanly against the working tree, so the submodule delta is exactly the documented patch set (dsl.svg-drop, android-no-gui-home, fts-wildcard-cap) and nothing else (AGENTS.md golden rule 1)
