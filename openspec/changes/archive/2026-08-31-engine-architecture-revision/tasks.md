## 1. Engine process architecture

- [x] 1.1 Add `EngineService` running in its own `:engine` process (foreground `dataSync` FGS, `android:process=":engine"`), loads `libaurelex.so` + runs `gd_init` on the engine process main thread.
- [x] 1.2 IPC via Binder (Messenger): `EngineService` handles opcode Messages and replies to `msg.replyTo`; `EngineClient` (UI process) mirrors the old `NativeEngine` Future-returning API.

## 2. Compose / rendering fixes

- [x] 2.1 Fix Compose blank (viewModel() default-param silently aborts composition): Activity-delegated `by viewModels()` passed into the composable.
- [x] 2.2 Engine in separate process so the UI process never dlopens Qt (Compose/HWUI no longer blanks).

## 3. Engine-process stability

- [x] 3.1 Fix `nativeDictInfo` JNI `ArrayStoreException` (outer array element class must be `'[Ljava/lang/String;'`); added `ExceptionCheck` guards to all boundary JNI string/array calls.
- [x] 3.2 `NativeEngine` methods `awaitInit()` before touching native (no native call before gd_init completes).
- [x] 3.3 ViewModel wraps IPC calls so a transient engine error surfaces as a message, not a process crash.

## 4. Persistence / resume

- [x] 4.1 Always stage SAF folders into app-private storage before scanning; persist the staged path.
- [x] 4.2 `resumeScan()` on `onServiceDisconnected` (and app start) to restore dictionaries after an engine restart.

## 5. On-device verification

- [x] 5.1 Verify on a real device: search UI renders, 3 dictionaries (6 entries incl. .dsl.dz) load via Dictionaries → Add, and a lookup ("apple") renders the article in the WebView. (Verified on Motorola ThinkPhone Android 15 after a clean install + re-add: search UI (Aurelex/Search field/Look up/Dictionaries), "Dictionaries (6 loaded)", article content present in the WebView screenshot.)
- [x] 5.2 Verify the engine survives a SAF folder-grant package restart and dictionaries are auto-restored (resumeScan) without re-picking the folder. (Verified: the `:engine` PID was unchanged across the grant — foreground service kept it alive; startup `resumeScan(/.../staged) -> 3` restored dictionaries, then the re-scan confirmed 6 loaded.)
