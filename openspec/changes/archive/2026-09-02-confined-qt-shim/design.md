## Design

### Goal

Determine, cheaply and conclusively, whether the carved engine can compile and
behave identically against a **confined, source-compatible Qt shim** built on
`std::`, instead of linking real Qt. This is an experiment; the deliverable is a
Go/No‑Go recommendation. Nothing ships.

### Method

The experiment is **host-only** (Windows smoke build), never the Android
pipeline. This isolates the question of "does the Qt surface hold?" from the
separate (already-solvable) problem of Android linkage, and it lets us iterate in
seconds. A green host result does **not** imply Android is free of work — it
gates whether the idea is worth pursuing at all.

### Step 1 — Definitive surface audit

Enumerate *every* Qt symbol the carve actually references, not just `#include`s.
Create `docs/qt-surface.md` from:

- Per-file `#include`s across the 39 carved upstream sources + `gd_boundary.cc`
  (confirmed: ~45 distinct Qt headers).
- The symbol set each file touches (`rg -oN \bQ[A-Za-z]+` per carve file),
  grouped into Core / Xml / Concurrent / Gui / Widgets / other.
- Open question to resolve: whether the carve *type-checks* against Qt only
  through **internal headers** (all consumers inside the carve — the shim only
  needs to be source-compatible for our own headers to compile, not a public
  ABI) or whether any upstream header is also pulled in externally.

Buckets:

| Bucket | Headers (preliminary) | Shim difficulty |
| --- | --- | --- |
| Core containers/string | `QString`, `QStringList`, `QByteArray`, `QList`, `QMap`, `QHash`, `QStringBuilder`, `QStringList` | Low — wrap `std::string`/`std::vector`/`std::map`. Semantics to verify: `QString::arg`/`arg` formatting, `mid`/`left`/`right` (invalid-index behavior), `QString::toLatin1`/`fromLocal8Bit`, `QList::removeAll/contains`, iteration order of `QMap`/`QHash`. |
| Core regex | `QRegularExpression` (9 files) | High — real regex engine with `QRegularExpressionMatch` capture semantics + `globalMatch`. Cannot be a fake. Vendoring a small regex lib (e.g. `re2`/custom) is likely needed; drift risk on capture groups/anchors is the top gate-risker. |
| Core concurrency | `QAtomicInt`, `QMutexLocker`, `QMutex`, `QtConcurrentRun`, `QThreadPool`, `QScopeGuard`, `QtEndian` | Medium — `std::atomic`/`std::mutex`/`std::thread` wraps. `QtConcurrentRun`/`QThreadPool` need mapping to `std::thread`/`std::parallel` or plain loops; must preserve ordering guarantees used by ingest. |
| Core filesystem | `QDir`, `QFileInfo`, `QFile` (8 + 5 + 2 files) | Medium — `std::filesystem` + a `QDir::entryList`-style directory walk. Locale/case-folding in `entryList` ordering is a subtle-risk. |
| Core url/io/codec | `QUrl`, `QDataStream`, `QBuffer`, `QIODevice`, `QTextStream`, `QCryptographicHash`, `QDateTime`, `QLocale`, `QStandardPaths`, `QOperatingSystemVersion` | Medium-High — `QXmlStreamReader` (DSL parsing path) and `QUrl` normalization are actual logic, not wrappers. Codecs for `dsl.dz`/`mdx` are the real risk. |
| Core misc | `QMimeDatabase`, `QSettings`, `QDebug`, `QGlobalStatic`, `QJsonDocument`/`QJsonArray` | Low-Medium — `QSettings` (used by `config.cc`) is meaningful; JSON can be a small std::-based parser. |
| Xml | `QDomDocument`, `QXmlStreamReader`, `QtXml` (via mdx/btreeidx) | High — `QXmlStreamReader` tokenizer semantics must match; `QDomDocument` tree building for mdx needs care. |
| Gui | `QPainter`, `QTextDocumentFragment`, `QPixmap`, `QImage`, `QStyleHints`, `QScreen`, `QApplication`, `QGuiApplication`, `QMessageBox` (from `article_maker`/`tiff`) | **Highest risk** — these are real GUI model APIs, likely *not* shimmable without reimplementing a chunk of article rendering and the tiff path. The experiment must determine **where the carve actually uses these** and whether they can be stubbed to compile (article_maker returns an HTML *string*, so the GUI types may be intermediate-only; `tiff.cc` pulls `QApplication`/`QScreen` — possibly removable from the carve if unused). |

### Step 2 — Confined shim build

Create `app/src/main/cpp/shim/` with header-only Qt-compatible types over `std::`,
targeting only the audited surface. Do **not** attempt full Qt; do not shadow
upstream headers in place (they live in `engine/`). Build `gd_boundary` + carve
against `-I shim/` **instead of** Qt, host-only.

Two sub-gates:
1. **Compiles** — carve + boundary link with no Qt (`Qt6::*` removed, shim in
   its place), excluding `tiff.cc` if the audit shows it is Gui-only and unused.
2. **Byte-identical smoke** — host smoke `main.cpp` run against **both** builds
   (Qt and shim) on the same fixtures (StarDict `smoke`, the `.dsl`/`.mdx`/
   `.dsl.dz` fixtures + FTS smoke) must produce identical bytes. Any delta = fail.

### Step 3 — Decision

Written recommendation in `design.md` (Decision section): **Adopt** (build a
follow-up change to go single-process) or **Drop** (keep Qt, keep the rule).

### Rejection criteria (explicit — any of these = Drop)

- The shim must reimplement more than the audited Core/Xml/Concurrent surface
  (e.g. a genuine `QTextDocumentFragment`/rendering model).
- Smoke output differs from the Qt build in **any** fixture (semantic drift).
- Upstream merge friction would increase: if a shim header has to mirror an
  upstream header so closely that bumps stop being "recompile against pinned Qt",
  the cost lands where the rule warned, and we stop.
- The experiment consumes disproportionate effort (tunneling on `QRegularExpression`
  or `QXmlStreamReader` parity for days) without a clear path.

### Risks

- **Semantic drift** is silent: hashing/case-folding/encoding/parse differences
  won't fail to build. Mitigated by the byte-identical smoke gate.
- **Underestimation of Gui usage**: if `article_maker`'s `QTextDocumentFragment`
  flow turns out to be load-bearing, the shim balloons. The audit gates this.
- **False green on host**: host build ≠ Android. The design explicitly treats a
  green host result as "worth investigating", not "done".

### Decision

*Pending experiment.* Not adopted. This section is updated by the final task.