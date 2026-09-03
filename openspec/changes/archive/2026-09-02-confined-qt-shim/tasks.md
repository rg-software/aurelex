## 1. Surface audit

- [ ] 1.1 Enumerate fresh from disk (not ad-hoc) every Qt `#include` across the 39 carved upstream sources + `gd_boundary.cc`; write `docs/qt-surface.md` with per-file counts (expect ~45 distinct headers; Core/Xml/Concurrent dominated, a smaller Gui slice).
- [ ] 1.2 Balloon the include list to the symbol set the carve actually calls (`rg -oN \bQ[A-Za-z]+` per carve file), grouped Core / Xml / Concurrent / Gui / other, so we know which types are load-bearing vs merely listed.
- [ ] 1.3 Determine whether the carve only type-checks Qt through its own internal headers (the realistic case for a confined shim) or whether any upstream header must also stay source-compatible with external consumers. Record in `docs/qt-surface.md`.
- [ ] 1.4 Flag the **GUI risk set** specifically: find where `article_maker`/`tiff` use `QTextDocumentFragment`, `QPainter`, `QPixmap`, `QImage`, `QStyleHints`, `QScreen`/`QApplication`/`QGuiApplication`, and decide for each: genuinely needed for article output, or stubbable intermediate.

## 2. Confined shim experiment (host-only)

- [ ] 2.1 Create `app/src/main/cpp/shim/` with header-only Qt-compatible types over `std::`, covering the audited Core/string containers first (`QString`, `QStringList`, `QByteArray`, `QList`, `QMap`/`QHash`, `QStringBuilder`). No full Qt; no shadowing of upstream headers in place.
- [ ] 2.2 Stand up a host-only build variant of the carve that compiles against `-I shim/` instead of `Qt6::*` (a separate CMake target / flag, not touching the Android config), and get the carve + boundary to compile — excluding `tiff.cc` only if 1.4 shows it is Gui-only and unused.
- [ ] 2.3 Add progressively the hard Core/Xml symbols actually referenced: `QRegularExpression`, `QXmlStreamReader`, `QUrl`, `QLocale`, codecs (`.dsl.dz`/`.mdx`), `QDataStream`/`QBuffer`/`QTextStream`, `QDir`/`QFileInfo`/`QFile` (std::filesystem), concurrency (`QMutex`, `QAtomicInt`, `QtConcurrent`→std::thread, `QScopeGuard`), `QSettings`, `QJsonDocument`/`QJsonArray`, `QCryptographicHash`/`QDateTime`/`QStandardPaths` — only what 1.2 proves is referenced.
- [ ] 2.4 Byte-identical smoke gate: run host smoke `main.cpp` (StarDict `smoke`, `.dsl`, `.dsl.dz`, `.mdx`, FTS smoke) against **both** the Qt build and the shim build; diff outputs. Any byte delta → experiment fails the gate.
- [ ] 2.5 Explicitly test the two highest-drift risks with targeted fixtures: `QRegularExpression` capture/anchors and `QXmlStreamReader` tokenization (the DSL parse path). A delta here fails the gate even if the broad smoke passes.

## 3. Decision

- [ ] 3.1 Write the recommendation into `design.md` (Decision section): **Adopt** (single-process follow-up change to be proposed separately) or **Drop** (keep Qt, keep the rule), with the evidence summary.
- [ ] 3.2 If **Drop**: ensure no `shim/` or CMake changes leak into the shipped tree (`git status` clean of experiment artifacts); close the change.
- [ ] 3.3 If **Adopt**: capture the concrete deltas for implementing the real thing (which headers were hard, which were trivial, what the Android-specific work would be) for the follow-up change's proposal.

## 4. Guardrails (apply throughout)

- [ ] 4.1 No changes to `engine/`, `patches/`, `jni_bridge.cc`, or the Android `app/` pipeline during the experiment.
- [ ] 4.2 Commit discipline: the experiment may be committed as `docs/` + `shim/` behind an opt-in CMake flag so it is reviewable, but must not affect the shipped Android build.
- [ ] 4.3 Any outcome that starts mirroring upstream headers so closely that bumps stop being "recompile against pinned Qt" counts as an automatic rejection criterion (per design).