## Context

The archived mobile-port change (D1) assumed the Qt-linked carve could be loaded
in-process into an ordinary Compose Android app. On real devices that assumption
failed (Compose/HWUI froze blank when the Qt libs were dlopen'd into the UI
process), and a JNI marshalling bug silently killed the engine process. This
change records the corrected architecture that was implemented and verified on
device (commit 2b106f2).

## Decisions

### D1. Engine in a separate `:engine` process
`libaurelex.so` (which links Qt Core/Gui/Widgets) is loaded only in a dedicated
`:engine` Android process hosting `EngineService` (foreground `dataSync`
service, `android:process=":engine"`). The Compose UI process never dlopens Qt,
so Compose/HWUI rendering is unaffected. This overturns the archived D1's
"load QtGui in-process into an ordinary Android app" model — that blanks the UI.

`QCoreApplication` is constructed on the `:engine` process main thread inside
`gd_init`; `NativeEngine` methods call `awaitInit()` to not touch native before
init completes.

### D2. IPC: Binder (Messenger)
UI ↔ engine over Binder via `Messenger`: `EngineClient` (UI) sends opcode
Messages to `EngineService` (engine), which replies to `msg.replyTo`.
Abstract local sockets were unreliable on-device (connection refused / no such
file despite matching names); Binder is the canonical reliable same-app
multi-process transport. `EngineClient` exposes the same Future-returning API
the old in-process `NativeEngine` had, so the ViewModel is agnostic.

### D3. Resume after engine-process restart
SAF folder grants restart the whole package (including `:engine`), killing the
engine's in-memory dictionary state. Dictionaries are therefore always staged
into app-private storage (`files/staged`) before scanning (the engine can't read
`/storage/emulated/0` via QDir under scoped storage, and the `:engine` process
doesn't hold the content-URI grant anyway). The staged path is persisted in
SharedPreferences; on `onServiceDisconnected` the app calls `resumeScan()` to
reload the staged dictionaries after a restart.

### D4. JNI robustness
`nativeDictInfo` must create the outer array with element class
`'[Ljava/lang/String;'` (array of `String[]`), not `String`. Every JNI call in
the boundary checks `ExceptionCheck()` before use so a bad dictionary header
(odd UTF-8, etc.) degrades gracefully instead of aborting the process.

## Risks

| Risk | Mitigation |
| --- | --- |
| Engine process still killed by the OS under memory pressure | Foreground service (dataSync) + bound with BIND_AUTO_CREATE; resumeScan restores dicts |
| IPC reply timeout if the process is restarting | EngineClient waits for re-bind; ViewModel catches and surfaces "engine not ready" instead of crashing |
| Staging large `.mdd` doubles disk usage + copy time | Staging is the only reliable path under scoped storage; index cache stays in app-private storage |
