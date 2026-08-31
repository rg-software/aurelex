## Why

Real-device testing (Xiaomi Android 16, Motorola ThinkPhone Android 15) disproved a
key design assumption from the archived mobile-port change: that the carve's Qt
libraries could be loaded in-process into an ordinary Compose Android app. Doing so
froze HWUI frame production (blank UI), and a separate JNI marshalling bug was
silently aborting the engine process. The working solution — the engine in its own
Android process, talking to the UI over Binder (Messenger) — is a structural change
worth recording as its own change, so the design docs and future work start from the
verified truth.

## What Changes

- **Engine runs in a dedicated `:engine` process** (a foreground `dataSync`
  `EngineService`, `android:process=":engine"`). The Compose UI process never
  dlopens the Qt-linked `libaurelex.so`, so Compose/HWUI rendering is unaffected.
- **IPC via Binder (Messenger)**: new `EngineClient` (UI process) ↔ `EngineService`
  (engine process), mirroring the old `NativeEngine` Future-returning API. Abstract
  local sockets proved unreliable on-device; Binder is the reliable same-app
  multi-process transport.
- **SAF dictionaries are always staged into app-private storage** before scanning
  (the engine process can't read `/storage/emulated/0` via QDir under scoped
  storage, and doesn't hold the content-URI grant). The staged path is persisted and
  `resumeScan()` restores dictionaries after an engine-process restart.
- **JNI robustness fix**: `nativeDictInfo`'s `ArrayStoreException` (created a
  `String[]` outer array but stored `String[]` pairs) aborted the engine process at
  startup and after each scan. Fixed to use `'[Ljava/lang/String;'` element class
  plus `ExceptionCheck` guards.
- **Compose fix**: the `viewModel()` default parameter silently aborted composition
  (blank app). Switched to an Activity-delegated `viewModels()` passed into the
  composable.

## Capabilities

### New Capabilities

None — this is an internal/architecture change; user-visible behavior (scan,
lookup, article rendering) is unchanged.

### Modified Capabilities

None — no spec-level behavior change, so `skip_specs: true` is set (the same
behavior is now delivered via a split-process engine).

## Impact

- `app/src/main/java/aurelex/android/` — new `EngineService.kt`, `EngineClient.kt`;
  `MainViewModel` swaps `NativeEngine` → `EngineClient`; `NativeEngine` now only
  used inside the `:engine` process; `AurelexApp` binds + starts the foreground
  service; `SafResolver` logs staged paths.
- `app/src/main/AndroidManifest.xml` — `EngineService` with `:engine` process and
  foreground-service permissions/types.
- `app/src/main/cpp/jni/jni_bridge.cc` — `nativeDictInfo` array-class + exception
  guards.
- Design docs: archived `design.md` gains an "On-device revision" section.
