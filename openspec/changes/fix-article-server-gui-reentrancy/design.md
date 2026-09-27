## Context

Three facts about the current shape of the code constrain the approach (motivation is in `proposal.md`).

**The wait is a nested event loop, and it lives on the GUI thread.** `ArticleServer::handle()` calls `gd_get_resource` / `gd_get_audio` inline (`app/ArticleServer.cpp:210`). Those land in `fetchResource`, which locks `g_engineMutex` (`carve/gd_boundary.cc:675`), issues the request, and then calls `loop.exec()` **while still holding the lock** (`carve/gd_boundary.cc:702`). A nested `QEventLoop` runs `QEventDispatcherUNIX::processEvents`, so the GUI thread keeps dispatching input, timers, and other sockets, and the QML engine keeps mutating the object graph, for the whole duration of the engine call.

**Reentrancy is only dangerous because of what the reentered code touches.** The recursive `g_engineMutex` added by `228ebf2` is correct as far as it goes — it is what lets a same-thread re-entry proceed instead of self-deadlocking. But it cannot be made safe while the reentered code reaches GUI-thread-owned objects. A `Loader` whose `active` binding flips destroys the article `WebView` and its QML-bound signals (`app/main.qml:1036`, `app/main.qml:2764`); if that happens inside the nested loop, the next signal dispatch into the QML engine walks freed QML data. The fix is not to make re-entry safe — it is to have no GUI-thread state reachable from the reentered code.

**The engine is already used from several threads.** `gd_init` and `gd_scan_dicts` run on a `QtConcurrent` thread (`app/EngineController.cpp:589`), FTS runs on its own worker, and the boundary serializes all of it behind `g_engineMutex`. Adding one more caller on a dedicated thread introduces no new concurrency — it introduces a new *thread identity*, which is the thing actually worth checking (see Risks).

## Goals / Non-Goals

**Goals:**

- No nested event loop on the GUI thread for any reason.
- `g_engineMutex` is not held across a wait, so one slow resource cannot block every other `gd_*` caller.
- A stuck resource request costs one pool slot, not the whole pool, so it cannot cascade into the other resources of the same or a later article.
- Per-connection request state has a lifetime tied to the socket, with no raw heap members and no reliance on `disconnected` firing.
- Behavior for assets, the `qrc://`-mirroring routes, and audio playback is unchanged.

**Non-Goals:**

- Removing the recursive mutex. It is still required: the boundary's own `gd_lookup` / `gd_suggest` also pump nested loops and can re-enter each other.
- Changing any `gd_*` signature or the C API surface. The boundary is the contract (AGENTS.md golden rule 3).
- The `files/index` separator defect noted in `proposal.md`; separate change.
- Whether any particular resource content is resolvable. The kaikki resource bundle was checked and found sound: 175 entries, exact ASCII names, all deflated, no ZIP64, and all four tag SVGs present, and the SVGs render after a re-import. The misses seen on 2026-09-27 came from a stale index on a bad import, not from the archive. This change fixes the crash the misses triggered, not the misses.

## Decisions

### D1: Resolve resources on a small fixed pool of engine-resource threads

Two long-lived slot threads each serve `bres://` / `gdau://` requests, one request per slot, each in its own nested `QEventLoop`. Requests that find both slots busy wait in an app-side queue and never enter the engine. Results return to the GUI thread as a queued signal carrying the owning connection as context.

The slot's `run()` is a plain pull loop over the queue; it does *not* wrap itself in an outer `exec()`. The event dispatcher the boundary's nested `QEventLoop` needs is supplied by that nested loop itself, which runs on the slot's thread for the duration of each request — the same shape the task-1.1 gate proved from a bare `QThread::create`. An outer `exec()` would add a second loop that has to be woken and quit correctly on shutdown, for no benefit.

Two slots is a fault-isolation choice, not a throughput one. Reads are tiny — the smoke test resolves 135 bytes, kaikki's largest bundle member is under 48 KB, all local — so a single slot drains a typical article's handful of requests in single-digit milliseconds, and Chromium's ~6-per-origin limit caps in-flight demand. One slot would be enough if every request were well behaved; the second exists so that a *stuck* request cannot gate the others, which is precisely the cascade the 2026-09-27 logcat showed (repeated `-3` timeouts, 15 s apart, piling up behind each other). Three or more slots would add thread identities inside the engine for no measured gain, so the count stays at 2 unless saturation is measured.

The decisive property is that a slot thread owns **no** `QObject` that the GUI thread can mutate, so the reentrancy that crashed the app becomes harmless: a slot's nested loop can only redeliver engine events for its own request. The GUI thread never runs a nested loop and never blocks — it only enqueues.

*Alternatives considered.* One dedicated thread (the first draft of this decision): rejected — it makes the slowest in-flight request gate every other one. `QtConcurrent` + `QFutureWatcher`: rejected — the engine's `finished` signal still needs an event loop on the waiting thread, so this only relocates the same problem, and it cannot express "don't start until a slot is free". `QThreadPool`: rejected — a pool worker has no Qt event dispatcher, so `QEventLoop::exec()` inside the boundary cannot run there. The gate in task 1.1 confirms the engine tolerates resource loads from a foreign thread identity, which is the property any pool shape depends on. Running the whole `ArticleServer` on its own thread: viable, but it splits socket ownership across threads for no benefit, since the GUI thread's involvement is limited to accepting connections and writing replies.

**What this does *not* fix.** If a wedge happens inside `getResource()` itself rather than in the wait, D2's scoped lock is still held and every caller blocks regardless of slot count. Slots isolate the *wait*; they cannot isolate a wedged engine call. That is a known limit, not an oversight.

### D2: Scope `g_engineMutex` to state access, not to the wait

Restructure `fetchResource` into: lock → resolve dictionary id and issue the request → unlock → wait for `finished` (bounded) → lock → copy the bytes out → unlock.

Rationale: issuing the request mutates the dictionary, so that part must hold the lock. Waiting mutates nothing, so holding the lock across it only serves to block other callers. Reading `getFullData()` after `finished` is safe under a fresh acquisition because the completed request owns stable data.

*Alternative considered.* Keep the lock across the wait on the new dedicated thread, on the grounds that it is simpler. Rejected: with the GUI thread no longer involved, the lock's only remaining effect would be to serialize *other* `gd_*` callers (FTS builds, lookups from the engine pool) behind an unrelated slow resource — a new, easier-to-hit version of the freeze this change is fixing.

### D3: Deadline becomes an explicit, named bound; no force-cancel

Keep a bounded wait, expressed as a named constant rather than an inline `15000`. The request is **not** force-cancelled when its client disconnects.

Rationale for the bound: removing it would let a wedged request pin a slot forever, which is the same class of bug with a longer fuse. The 15-second value was chosen when it was also the GUI-freeze duration; now that it is off the GUI thread it is a slot-occupancy budget rather than a responsiveness budget, so the exact value should be chosen against real first-touch load times on device rather than inherited. The value is unchanged pending that measurement (see Open Questions).

Rationale for **not** cancelling, which was the original D3: the consumer is the Android WebView in this same process, talking to us over loopback. When the user navigates away the WebView simply drops the fetch — nobody outside the app ever wanted the bytes — so cancellation is a tidiness concern, and it turns out to be an expensive one. `Dictionary::DataRequest::cancel()` only sets a flag that the engine's request runnable reads once, at the top of `run()` (`dsl.cc:1578`, `dsl.cc:1594`), and the request's destructor calls `f.waitForFinished()` (`dsl.cc:1586`). So for a runnable already inside the read — the only case that matters — a cancel call changes nothing that the destructor does not do anyway. Its sole advantage is a request that has not started yet.

Reaching it at all would require growing the C API, since the wait loop lives inside `fetchResource` and has no way to learn that a client disconnected. Paying for a new boundary function to cover a millisecond-wide window is not worth it, and D1's pool already removes the consequence that motivated cancelling: a stuck request now costs one slot instead of all of them. **Consequence, stated plainly:** an abandoned request still occupies its slot until the engine finishes or the deadline fires. The spec does not promise earlier abandonment, so it remains satisfied — the guarantee that matters is that the interface stays responsive while a resource is outstanding.

### D4: One `Connection` object per socket, parented to the socket

Replace the `QPointer<QTcpSocket>` plus `new QByteArray` / `new bool` pair with a small `Connection` type owned by the socket (as a child `QObject`, or held by value in a `QHash` keyed on the socket with the socket as the owner). It holds the header buffer, the parsed flag, and a cancelled flag.

Rationale: today `buf` and `headersParsed` are freed only from the `disconnected` lambda (`app/ArticleServer.cpp:119-123`). A socket destroyed without `disconnected` ever firing leaks both, and the `readyRead` lambda captures them raw. Parenting the state to the socket ties its lifetime to the socket's, so the answer-on-a-dead-socket guard becomes a single `Connection` liveness check rather than a separately maintained `QPointer`. It also gives cancellation (D3) somewhere natural to live.

### D5: Keep the `228ebf2` socket guard and recursive mutex

Both stay. The `QPointer` checks in `writeReply` and friends become redundant once D4 lands and should be simplified rather than left alongside the new mechanism, but the *behaviour* they added (never answer on a dead socket) is a requirement, not an implementation.

### D6: A slot thread never dereferences a `Connection`; the main thread owns liveness

A finished job hands its bytes back through a heap `Delivery` that the slot appends to a mutex-guarded queue and then wakes the main thread (`drainCompleted`, a queued call to the server). `Delivery` carries the `Connection` pointer only as an identity token. The main thread keeps `QSet<Connection*> m_liveConnections` (inserted at accept, removed in the connection's `destroyed`), and `drainCompleted` drops any `Delivery` whose connection is no longer in that set. The set is touched only on the main thread.

Rationale: the obvious implementation — have the slot post its reply to the `Connection` as the queued-call context — is a use-after-free. The client can disconnect while the engine is still running, at which point the main thread deletes the socket and its child `Connection`; the slot then holds a dangling pointer and calling `QMetaObject::invokeMethod` on it reads freed memory. The alternative of checking a `QPointer` on the slot thread only relocates the race, because the write that nulls it happens on another thread. Routing every completion through the main thread and checking membership there removes the cross-thread access entirely: the slot's only job is to call the engine and enqueue bytes. The same rework is why the result no longer lives in the `Connection` at all — a slot-written field would be a data race for exactly the same reason.

## Risks / Trade-offs

**[Risk] The engine may not tolerate being driven from a new thread identity.** Dictionaries are *constructed* on whichever thread calls `makeDictionaries` (the engine pool, via `QtConcurrent`) and would now be *used* from the resource thread. `g_engineMutex` serializes access but does not make a backend that caches thread-affine state safe to move between threads. *Mitigation*: the CI smoke tool already exercises resource loading, so extend it to do so through the new path and treat any thread-affinity assertion as a blocking failure. This is the single risk most likely to invalidate D1, and it must be settled before the rest of the implementation is trusted.

> **RESOLVED — the risk did not materialise (2026-09-27).** Task 1.1 added a `bres://` load to `carve/smoke/main.cpp` driven from a `QThread` that is neither the constructing thread nor the `gd_scan_dicts` caller, with a main-thread control on the same URL. Fixture: `aurelex-basic` now carries a `badge` headword with `[s]aurelex-resource.svg[/s]` and a sibling `aurelex-basic.dsl.files/` (the name the engine derives for both the `.dsl` and `.dsl.dz` variants, `dsl.cc:279-284`). The check asserts on `<svg` being present rather than on a byte count, so a truncated payload fails.
>
> ```
> python scripts/make-smoke-stardict.py  "$RUNNER_TEMP/dic"
> python scripts/make-example-dicts.py   "$RUNNER_TEMP/dsl"
> cp "$RUNNER_TEMP/dsl/aurelex-basic.dsl.dz"        "$RUNNER_TEMP/dic/"
> cp -r "$RUNNER_TEMP/dsl/aurelex-basic.dsl.files"   "$RUNNER_TEMP/dic/"
> mkdir -p "$RUNNER_TEMP/dic/nested" && cp "$RUNNER_TEMP/dsl/aurelex-lingvo.dsl" "$RUNNER_TEMP/dic/nested/"
> aurelex_smoke "$RUNNER_TEMP/cfg" "$RUNNER_TEMP/dic" smoke
> ```
>
> ```
> gd_dict_id(0) -> rc=0 id=c3c3f339a4e0a0875c89212c7eaeb683
> gd_get_resource("bres://c3c3f339.../aurelex-resource.svg") on main thread   -> rc=135 (135 bytes)
> RESOURCE_ON_MAIN_THREAD=OK
> gd_get_resource("bres://c3c3f339.../aurelex-resource.svg") on worker thread -> rc=135 (135 bytes)
> RESOURCE_ON_WORKER_THREAD=OK
> ```
>
> Both threads returned the full 135 bytes, and the whole smoke suite still exits 0. `QThread` rather than `std::thread` is load-bearing: `gd_get_resource` spins a nested `QEventLoop` internally, and a thread with no Qt event dispatcher returns immediately, which would have read as a meaningless result. D1 stands.

**[Risk] A request that never completes still occupies one of the two slots.** With a bounded wait it eventually frees, but for its full budget. *Mitigation*: two slots (D1), so a single stuck request cannot block its peers — this replaces the force-cancel that D3 originally proposed, since that turned out to be ineffective against a runnable already inside the read.

**[Risk] Shutdown ordering.** The slot threads must be stopped and joined before the engine state is torn down, or a late `finished` signal can arrive against a destroyed `g_state`. *Mitigation*: join both threads in `ArticleServer`'s teardown, and assert afterwards that the join actually drained every enqueued job (an in-flight counter checked after the join). Note that D2 makes `fetchResource` safer here than it was — it no longer touches `g_state` after releasing the lock. As it stands the app never calls `gd_cleanup()` (only the smoke tool does), so this ordering has no in-process teardown to race against today; the invariant is recorded so that a future `gd_cleanup()` call site can assert it rather than rediscover it.

**[Risk] `QEventLoop` on a worker requires that thread to have an event loop.** A bare `QThreadPool` thread has none. *Mitigation*: each slot is a real `QThread`; the boundary's nested loop supplies the dispatcher. Do not use `QThreadPool` for this. The task 1.1 gate exercises exactly this shape via `QThread::create`, so a regression here shows up as the nested loop returning early.

**[Risk] The result hand-off could be posted before the result is written.** The reply is delivered by a queued invoke on the GUI thread, so posting it at submit time would let the GUI loop run the delivery before the slot had filled the result in — a spurious "no result" 500 on a perfectly good request. *Mitigation*: the slot posts the invoke only after writing the result, so the event queue's mutex provides the happens-before edge. The result is stored inline in the `Connection` rather than in a separately-owned buffer, so a connection that dies mid-flight drops both the call and the data with nothing to leak.

**[Trade-off] Two slots cap concurrent resource resolution at two.** Article rendering with many embedded resources serializes beyond that. Accepted: the engine is not thread-safe, so a ceiling already existed one level down behind `g_engineMutex`. Moving the wait out of the critical section (D2) is what improves throughput; the slot count is about isolation, not speed.

**[Trade-off] Abandoned requests are not force-cancelled.** Per D3, a request the user navigated away from can hold its slot until the deadline. Accepted deliberately, and recorded there with the reasoning, rather than paid for with a new boundary function that would not have helped.

## Migration Plan

No persisted state, no user-visible migration, no version bump. `ArticleServer` is constructed in `EngineController`'s initializer; the resource thread starts and stops with it. Rollback is a single revert.

## Open Questions

- The concrete deadline value for D3. Default to the existing 15 s until device measurement of a genuine first-touch resource load says otherwise; the point of D3 is that it is now off the GUI thread, so this is no longer a responsiveness number.
- Whether `ArticleServer`'s asset routes should also move to the worker. They are plain file reads and do not touch the engine, so they are expected to stay; revisit only if profiling shows asset serving is measurable.
