## Why

Qt 6 is the single largest thing keeping the carve and the Android app awkwardly
separate: the engine has to run in a separate `:engine` process (a foreground
service with a confusing persistent notification) because loading Qt into the
Compose/WebView UI process broke HWUI rendering (commit `2b106f2`). We now have
hard evidence of exactly which Qt is actually used by the carve, so the old
blanket fear ("any Qt shim makes upstream merges expensive") can be tested cheaply
instead of assumed. This change is a **pragmatic, success-gated experiment**:
audit the real Qt surface, build a confined source-compatible shim, and see whether
the carve compiles and passes smoke tests without Qt. If it turns into a large
rewrite or would impede upstream interoperability, we drop it and keep Qt.

## What Changes

- **Audit** the carve's real Qt usage across the ~40 carved upstream sources
  (preliminary count: ~45 distinct Qt headers — dominated by Core/Xml/Concurrent,
  with a small but real GUI slice from `article_maker`/`tiff`: `QTextDocumentFragment`,
  `QPainter`, `QPixmap`, `QImage`, `QStyleHints`, `QScreen`/`QApplication`).
- **Experiment**: build a confined, header-only, source-compatible shim over
  `std::` for the audited surface and compile the carve against it (host smoke
  build only, first) — **not** yet touching the Android pipeline, `patches/`, or
  the engine submodule.
- **Gate**: success = carve compiles against the shim AND the host smoke test
  produces byte-identical output to the Qt build. Any deviation in semantics
  (`QXmlStreamReader`, `QRegularExpression`, `QUrl`, codecs, hashing) fails the gate.
- **Decision output**: a written recommendation. If the shim holds, the follow-up
  change (separate) can consolidate to one process (remove `:engine` / Messenger /
  FGS notification). If not, we keep Qt and the rule stays.
- **No behavior ships in this change.** This is an experiment with a decision as
  its deliverable; its outcome is a green/red recommendation, not a product change.

## Capabilities

### New Capabilities

None — `skip_specs` (experiment only). If adopted, the implementation change
carries the specs.

### Modified Capabilities

None.

## Impact

- **New, self-contained**: `shims/` (or `app/src/main/cpp/shim/`) holding the
  confined Qt-compatible surface — compiled only by the experiment build, never
  shipped to Android yet.
- **Touchpoints (read-only in this change)**: `app/src/main/cpp/engine/CMakeLists.txt`
  (the carve file list + Qt search — to enumerate the surface, not modify), the
  upstream `engine/` sources as inputs to the audit.
- **No changes** to `patches/`, `app/` Kotlin, `jni_bridge.cc`, or the engine
  submodule during the experiment.
- **If implemented later** (out of scope here): `EngineService`/`EngineClient`,
  `MainActivity` bind points, the `:engine` manifest entry, and AGENTS.md's
  "Do not shim Qt types" rule all get revisited — as a separate change with specs.