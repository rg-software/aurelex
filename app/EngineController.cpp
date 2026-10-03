#include "EngineController.hpp"
#include "ArticleServer.hpp"
#include "DictionaryIndex.hpp"
#include "IndexCleanup.hpp"
#include "StagedCleanup.hpp"
#include "IndexMigration.hpp"

#include <QtConcurrent>
#include <QStandardPaths>
#include <QDir>
#include <QDebug>
#include <QElapsedTimer>
#include <QtMessageHandler>
#include <QVariantMap>
#include <QPair>
#include <QFile>
#include <QClipboard>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonValue>
#include <QRegularExpression>
#include <QStorageInfo>
#include <QTimer>
#include <QUrl>
#include <QXmlStreamReader>
#include <QColor>
#include <QGuiApplication>
#include <QLocale>
#include <QThread>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QPointer>
#include <QNetworkRequest>
#include <cmath>
#include <algorithm>
#include <climits>
#if defined(Q_OS_ANDROID)
#include <QJniObject>
#endif

// --- diagnostic log (aurelex.log) ---
// qInfo/qWarning normally go to stderr, which on Android is not retrieveable.
// Redirect everything to <appDir>/aurelex.log (app-private storage) with a
// monotonic-millisecond timestamp and the emitting thread id, so the delay in
// any gd_* call (mutex wait vs. event-loop pump) can be reconstructed after a
// slow-search reproduction. The default handler is still invoked, so console
// output (Linux dev loop, smoke tool) is preserved.
static QMutex s_diagLogMutex;
static QString s_diagLogPath;
static QElapsedTimer s_diagLogClock;
static bool s_diagLogStarted = false;
static qint64 s_diagLogBytesSinceRotate = 0;
static QtMessageHandler s_diagLogPrevHandler = nullptr;
static QFile s_diagLogFile;
static const qint64 kDiagLogMaxBytes = 512 * 1024;

static void diagLogMessage(QtMsgType type, const QMessageLogContext &context,
                           const QString &message)
{
    if (s_diagLogPrevHandler)
        s_diagLogPrevHandler(type, context, message);
    else
        qt_message_output(type, context, message);

    if (s_diagLogPath.isEmpty())
        return;
    QMutexLocker lock(&s_diagLogMutex);
    if (s_diagLogPath.isEmpty())
        return;
    if (!s_diagLogStarted) {
        s_diagLogStarted = true;
        s_diagLogClock.start();
    }
    const char sev = type == QtDebugMsg ? 'D'
                   : type == QtInfoMsg ? 'I'
                   : type == QtWarningMsg ? 'W' : 'E';
    const QByteArray line = QByteArray::number(s_diagLogClock.elapsed()) + "ms ["
        + QByteArray::number(qlonglong(QThread::currentThreadId())) + "] " + sev + ": "
        + message.toUtf8() + "\n";
    // Keep the handle open across writes (flush after each line so the tail is
    // always readable); opening/closing per log line is flash I/O churn on the
    // UI thread, which is exactly what we are trying to measure.
    if (!s_diagLogFile.isOpen() && !s_diagLogFile.open(QIODevice::Append | QIODevice::WriteOnly))
        return;
    const qint64 written = s_diagLogFile.write(line);
    s_diagLogFile.flush();
    s_diagLogBytesSinceRotate += written;
    if (s_diagLogBytesSinceRotate > kDiagLogMaxBytes) {
        // Rotate: keep one small .prev so the timestamps around the moment of
        // the last reproduction are not destroyed.
        s_diagLogFile.close();
        QFile::remove(s_diagLogPath + ".prev");
        QFile::rename(s_diagLogPath, s_diagLogPath + ".prev");
        s_diagLogBytesSinceRotate = 0;
    }
}

static void installDiagLog(const QString &appDir)
{
    s_diagLogPath = appDir + "/aurelex.log";
    if (!s_diagLogPrevHandler) {
        s_diagLogPrevHandler = qInstallMessageHandler(diagLogMessage);
    }
}
EngineController::EngineController(QObject *parent)
    : QObject(parent)
{
    // Resolve the theme before any QML binding evaluates. main.cpp constructs this
    // controller (line 89) before the QML engine (line 92), and the QML palette
    // binds straight to m_darkMode -- but applyEffectiveDark() first runs from the
    // gd_init watcher, long after the first frame. Sampling the system night state
    // here (the tick does the same read 500 ms later) means a dark-mode user does
    // not see the correct dark launch starting window followed by a LIGHT app
    // (system-splash-theme, design D4).
    //
    // Only the two fields are touched. applyEffectiveDark() is deliberately not
    // called: it pushes gd_set_dark_mode off-thread, which must not happen before
    // gd_init has run. A user who has FORCED a theme still gets the system theme
    // here -- that is the most available before settings.json has been read, and
    // loadSettings() re-resolves it once the engine is up.
    m_systemDark = readSystemDark();
    m_darkMode = m_systemDark; // m_themeMode is follow-the-system at construction

    // Serial engine dispatch: at most one interactive gd_* call in flight (see
    // m_enginePool in the header). The single thread is kept alive so rapid
    // typing/lookups never pay a thread-spawn cost.
    m_enginePool.setMaxThreadCount(1);
    m_enginePool.setExpiryTimeout(-1);

    // Incoming-lookup poller: AurelexActivity writes shared_prefs/intent.xml
    // for every share/deep-link/PROCESS_TEXT/tile intent (cold or warm). Consume
    // it here as soon as the engine is ready; words arriving before gd_init
    // completes stay in the file and are picked up on a later tick.
    connect(&m_pollTimer, &QTimer::timeout, this, &EngineController::pollPendingLookup);
    m_pollTimer.start(500);

    // Clipboard changes: the Search pane's clipboard control stays in sync with
    // whether the clipboard holds usable text (control-state-and-fts-whole-words).
    // The signal carries no payload; QML re-queries clipboardHasText().
    if (QClipboard *cb = QGuiApplication::clipboard())
        connect(cb, &QClipboard::dataChanged, this, &EngineController::clipboardChanged);

    // Scan failsafe (see runScan): if a scan is still 'active' long past any
    // plausible duration, the engine mutex is parked by a wedged worker. Clear
    // the banner and tell the user to relaunch (which frees the mutex and
    // re-scans the staged root). This keeps the UI from showing "Reading
    // dictionary files…" forever.
    connect(&m_scanWatchdog, &QTimer::timeout, this, [this]{
        m_scanWatchdog.stop();
        if (m_scanningActive) {
            qWarning("[aurelex] scan watchdog fired: dictionary scan did not "
                     "complete in %d ms (engine mutex likely parked). "
                     "Closing the banner; restart the app to rescan.",
                     kScanWatchdogMs);
            // The scan never completes, so autoIndexMissing will never run to end
            // the processing chain; clear both flags or the banner would hang.
            setScanningActive(false);
            setProcessingActive(false);
        }
    });

    // FTS batch completion arrives from the index-build worker thread; deliver
    // it into the UI-thread properties via a queued connection (same-object
    // connect resolves to queued when the emitter thread differs from this
    // object's affinity thread).
    connect(this, &EngineController::ftsIndexBatchProgress,
            this, [this](int completed, int total, const QString &name){
        setFtsIndexProgress(completed, total, name);
    });

    // Smooth in-flight progress: while a batch builds, sample the engine's own
    // per-dictionary percent so the bar fills even for a single huge dict.
    // 1s, VeryCoarse: each tick takes g_engineMutex (pollFtsProgress ->
    // gd_fts_progress). The build used to hold that lock for the whole
    // dictionary, which made a fast (400ms) cadence stutter the UI; since
    // patches/0004-fts-sliced-build the build yields the lock in bounded slices,
    // so a tick now waits at most about one slice. The slower cadence is kept as
    // deliberate headroom rather than re-tuned.
    m_ftsProgressTimer.setInterval(1000);
    m_ftsProgressTimer.setTimerType(Qt::VeryCoarseTimer);
    connect(&m_ftsProgressTimer, &QTimer::timeout, this, &EngineController::pollFtsProgress);

    // Article bridge: start the loopback HTTP server as soon as the controller
    // exists so the WebView (and its URL rewriter) can rely on the base URL
    // being available by the time the first article renders. The server binds
    // a random free port and emits articleBaseUrlChanged when ready.
    m_articleServer = new ArticleServer(this);
    connect(m_articleServer, &ArticleServer::baseUrlChanged,
            this, &EngineController::articleBaseUrlChanged);
    m_articleServer->listen();
}

EngineController::~EngineController()
{
    // Engine jobs capture this to read the generation counters; drop queued
    // ones and wait out the in-flight request so no worker outlives the
    // controller. (They only ever call gd_* + build a QString, no signals.)
    m_enginePool.clear();
    m_enginePool.waitForDone();
}

void EngineController::setDictCount(int n) {
    if (m_dictCount == n) return;
    m_dictCount = n;
    emit dictCountChanged();
}

void EngineController::setReady(bool r) {
    if (m_ready == r) return;
    m_ready = r;
    emit readyChanged();
}

void EngineController::setLastError(const QString &e) {
    // Never store a blank message: a whitespace-only value used to paint an
    // empty "engine error:" banner (control-state-and-fts-whole-words). A blank
    // report clears the error, which is what callers mean by it.
    m_lastError = e.trimmed().isEmpty() ? QString() : e;
    emit lastErrorChanged();
}

void EngineController::setDictionaries(const QVariantList &list) {
    m_dictionaries = list;
    qInfo() << "[aurelex] setDictionaries count=" << list.size();
    // The catalog's "installed" badges are derived from the loaded dictionary
    // paths, so they must be recomputed on every change — otherwise a freshly
    // scanned download would keep showing as not installed until the next
    // catalog fetch.
    refreshCatalogEntries();
    emit dictionariesChanged();
}

void EngineController::setGroups(const QVariantList &list) {
    m_groups = list;
    // Group membership edits change which dictionaries a lookup sees.
    clearArticleCache();
    qInfo() << "[aurelex] setGroups count=" << list.size();
    // m_groups is known-good here, so this is the first point at which a
    // dangling history/favorites entry can be recognised as dangling.
    repointStaleGroupEntries();
    emit groupsChanged();
}

void EngineController::setActiveGroupId(int id) {
    if (m_activeGroupId == id) return;
    m_activeGroupId = id;
    // Lookup results are scoped to the active group: drop cached articles.
    clearArticleCache();
    emit activeGroupChanged();
}

void EngineController::setFtsStarting(bool b) {
    if (m_ftsStarting == b) return;
    m_ftsStarting = b;
    emit ftsStartingChanged();
}

void EngineController::setBuildingFts(bool b) {
    if (m_buildingFts == b) return;
    m_buildingFts = b;
    if (b) {
        m_ftsProgressTimer.start();
    } else {
        m_ftsProgressTimer.stop();
        setFtsFraction(0.0, 0.0);
        setFtsIndexProgress(0, 0, QString());
    }
    emit buildingFtsChanged();
}

void EngineController::setFtsFraction(qreal allFraction, qreal dictFraction) {
    bool changed = false;
    if (!qFuzzyCompare(m_ftsIndexFraction, allFraction)) {
        m_ftsIndexFraction = allFraction;
        changed = true;
    }
    if (!qFuzzyCompare(m_ftsDictFraction, dictFraction)) {
        m_ftsDictFraction = dictFraction;
        changed = true;
    }
    if (changed)
        emit ftsIndexProgressChanged();
}

void EngineController::pollFtsProgress() {
    if (!m_buildingFts) return;
    // Per-dictionary progress (the engine's getIndexingFtsProgress; on a
    // resumed build it continues from where it left off, never from 0).
    int pct = 0;
    const int st = gd_fts_progress(&pct);
    qreal dictFrac = 0.0;
    if (st > 0)
        dictFrac = qBound<qreal>(0.0, qreal(pct) / 100.0, 1.0);
    // Overall = completed dicts + the in-flight dict's share of the batch, so
    // the bottom bar advances proportionally while a single dictionary builds
    // (e.g. 1 dict at 40% -> bottom = 40%, not a 0->100 jump at the end).
    qreal overall = 0.0;
    if (m_ftsIndexTotal > 0) {
        overall = qBound<qreal>(0.0,
                                (qreal(m_ftsIndexDone) + dictFrac) / qreal(m_ftsIndexTotal),
                                1.0);
    }
    setFtsFraction(overall, dictFrac);
    // Push live progress into the foreground-service notification so the user
    // sees "Indexing (2 of 5): <name>" + a determinate bar in the status bar
    // too. The notification bar shows the OVERALL batch fraction (monotonic,
    // includes the in-flight dictionary), while the in-app top bar keeps the
    // per-dictionary progress.
#if defined(Q_OS_ANDROID)
    if (m_ftsIndexTotal > 0) {
        const int overallPercent = qRound(overall * 100.0);
        QJniObject::callStaticMethod<void>(
            "org/aurelex/pocket/dictionary/AurelexActivity",
            "updateIndexingProgress",
            "(IILjava/lang/String;I)V",
            m_ftsIndexDone + 1, m_ftsIndexTotal,
            QJniObject::fromString(m_ftsCurrentDictName).object<jstring>(),
            overallPercent);
    }
#endif
}

void EngineController::setFtsIndexProgress(int done, int total, const QString &name) {
    m_ftsIndexDone = done;
    m_ftsIndexTotal = total;
    if (!name.isEmpty())
        m_ftsCurrentDictName = name;
    if (total > 0)
        setFtsFraction(qMin<qreal>(1.0, qreal(done) / qreal(total)), m_ftsDictFraction);
    else
        setFtsFraction(0.0, 0.0);
    qInfo() << "[aurelex] fts progress" << done << "/" << total << name;
    emit ftsIndexProgressChanged();
}

void EngineController::setStagingActive(bool b) {
    if (m_stagingActive == b) return;
    m_stagingActive = b;
    emit stagingActiveChanged();
}

void EngineController::setScanningActive(bool b) {
    if (m_scanningActive == b) return;
    m_scanningActive = b;
    emit scanningActiveChanged();
}

void EngineController::setProcessingActive(bool b) {
    if (m_processingActive == b) return;
    m_processingActive = b;
    emit processingActiveChanged();
}

void EngineController::setScanFailures(const QVariantList &list) {
    if (m_scanFailures == list) return;
    m_scanFailures = list;
    emit scanFailuresChanged();
}

void EngineController::setResultClashes(const QVariantList &list) {
    if (m_resultClashes == list) return;
    m_resultClashes = list;
    emit scanFailuresChanged();
}

void EngineController::collectScanFailures() {
    // gd_scan_failures takes g_engineMutex, held by the FTS worker for the whole
    // duration of a large dictionary's index build. Never call it on the UI
    // thread (would freeze the app); enumerate, delete and build the model
    // off-thread, then publish on a watcher (report-import-results).
    //
    // The failure list is consume-on-read, so this is also where an unloadable
    // source's own files are deleted: by the time the banner shows a row, the
    // files it names are already gone (design D1), and the row says so. The delete
    // is scoped to the failing source's stem, so a folder shared with dictionaries
    // that DID load keeps every file they need.
    const QString stagedRoot = m_stagedDir;
    QFuture<QVariantList> f = QtConcurrent::run([stagedRoot]{
        char buf[16384];
        const int n = gd_scan_failures(buf, static_cast<int>(sizeof(buf)));
        QVariantList list;
        if (n <= 0) return list;
        const QString joined = QString::fromLocal8Bit(buf);
        const QStringList lines = joined.split('\n', Qt::SkipEmptyParts);
        for (const QString &path : lines) {
            const int removed = StagedCleanup::removeSourceFileSet(path, stagedRoot);
            qInfo() << "[aurelex] deleted unloadable source files:" << path
                    << "removed" << removed;
            QVariantMap m;
            m.insert("file", path);
            m.insert("reason", QStringLiteral("couldNotLoad"));
            // A source that could not be loaded has no engine display name, so the
            // row falls back to the file's basename (design D4).
            m.insert("name", QFileInfo(path).fileName());
            list.append(m);
        }
        return list;
    });
    auto *w = new QFutureWatcher<QVariantList>(this);
    connect(w, &QFutureWatcher<QVariantList>::finished, this, [this, w]{
        const QVariantList result = w->result();
        // Publish only a non-empty report: an empty read (already consumed, or a
        // clean scan) must not wipe a banner the user has not dismissed. A new
        // pick clears the model at the start of runScan instead.
        if (!result.isEmpty())
            setScanFailures(result);
        w->deleteLater();
    });
    w->setFuture(f);
}

// The single place the boundary's dictionary-info call is made, so the source
// path cannot drift between the two places that need it: the scan's in-use set
// (which decides what the staged sweep may delete) and the QML model. They were
// separate gd_dict_info loops, and the sweep's in-use guard ended up vacuous on a
// cold start because it read the wrong one
// (fix-stale-sweep-deletes-live-dictionaries).
//
// Buffers are sized from kDictInfoBufferSize, one constant shared by every
// gd_dict_info call site. gd_dict_info refuses a name or path that does not fit
// rather than truncating it (carve/gd_boundary.cc): a truncated path is *wrong*
// data, not merely incomplete, and the sweep's prefix comparison
// (StagedCleanup::isUsedByLoadedDictionary) could then match a different staged
// directory - protecting the wrong one, or none. A dictionary whose path did not
// fit was therefore loaded but unlisted: absent from the model *and* from the
// in-use set, so it could never be removed
// (fix-long-path-dictionaries-invisible). Sizing to PATH_MAX makes any path a
// filesystem can produce fit instead.
#ifndef PATH_MAX
#define PATH_MAX 4096 // POSIX; bionic defines it, the fallback keeps host tools building
#endif
constexpr int kDictInfoBufferSize = 4096;
static_assert(kDictInfoBufferSize >= PATH_MAX,
              "the dictionary-info buffers must fit any path a filesystem can produce");
namespace {

struct DictInfoAtIndex {
    bool ok = false; // gd_dict_info returned 0
    QString name;
    QString source;
};

// What one scan produced: how many dictionaries loaded, and where each reads from.
// Replaces the QPair<int,int> the scan used to return, whose first element was
// hardcoded to 0 - so `result.first > 0` never fired and the guard downstream was
// really only ever about the count.
struct ScanOutcome {
    int count = 0;
    QStringList sources;
};

DictInfoAtIndex readDictInfoAt(int i) {
    // Fixed stack buffers, sized by kDictInfoBufferSize: the sizes are pinned
    // HERE so every caller gets the same answer, and stack storage keeps this
    // allocation-free on the path that walks every loaded dictionary.
    // gd_dict_info copies the trailing NUL, but the zero-init is kept so a
    // buffer it chose not to fill is still a valid C string -
    // QString::fromLocal8Bit would otherwise read past it.
    char name[kDictInfoBufferSize] = {};
    char file[kDictInfoBufferSize] = {};
    if (gd_dict_info(i, name, static_cast<int>(sizeof(name)),
                     file, static_cast<int>(sizeof(file))) != 0)
        return {};
    return DictInfoAtIndex{true, QString::fromLocal8Bit(name),
                           QString::fromLocal8Bit(file)};
}

} // namespace

void EngineController::runScan() {
    // One-off import model: the app-private staged root is the single source of
    // dictionaries. gd_scan_dicts recurses, so scanning the root picks up every
    // staged/<sourceId>/... import.
    const QString stagedBase = m_stagedDir;
    // Diagnostics: log the staged import folders present on disk so it's clear
    // what the scan is about to look at.
    qInfo() << "[aurelex] scan start; staged root =" << stagedBase;
    {
        QDir sr(stagedBase);
        const QStringList dirs = sr.entryList(QDir::Dirs | QDir::NoDotAndDotDot);
        qInfo() << "[aurelex] staged import folders:" << dirs.size();
        for (const QString &d : dirs) qInfo() << "  staged/" << d;
    }
    // Show "Scanning dictionaries…" while the carve loads dicts so the Dicts
    // processing banner stays visible continuously from folder pick -> staging
    // -> scan -> indexing. Raise the continuous processing indicator here too so
    // a startup scan (no staging phase) also shows the banner; it is cleared
    // only once the whole scan + index chain finishes.
    setScanningActive(true);
    setProcessingActive(true);
    // Failsafe: gd_scan must always eventually return; if the engine mutex is
    // parked (a wedged worker holds it) the QtConcurrent call below never
    // returns and the banner would show forever. Kick a watchdog so the UI
    // recovers with a clear message instead of an endless spinner.
    m_scanWatchdog.start(kScanWatchdogMs);
    // The count AND the source of every loaded dictionary come back together,
    // read on this thread while gd_scan_dicts' result is still the live one.
    //
    // The source list is not redundant with refreshDictionaries() below: that one
    // runs after the staged sweep, and on the first scan after a launch
    // m_dictionaries is still empty - which left the sweep's in-use guard
    // vacuous and every nested import classified as an orphan
    // (fix-stale-sweep-deletes-live-dictionaries). Same read, taken while it is
    // authoritative rather than after.
    QFuture<ScanOutcome> f = QtConcurrent::run([stagedBase]{
        ScanOutcome out;
        if (QDir(stagedBase).exists())
            gd_scan_dicts(stagedBase.toLocal8Bit().constData());
        const int n = gd_dict_count();
        out.count = n;
        out.sources.reserve(n);
        for (int i = 0; i < n; ++i) {
            const QString src = readDictInfoAt(i).source;
            if (!src.isEmpty())
                out.sources.append(src);
        }
        return out;
    });
    auto *w = new QFutureWatcher<ScanOutcome>(this);
    connect(w, &QFutureWatcher<ScanOutcome>::finished, this, [this, w]{
        m_scanWatchdog.stop();
        const ScanOutcome result = w->result();
        qInfo() << "[aurelex] scan done; gd_dict_count =" << result.count;
        setDictCount(result.count);
        setScanningActive(false);
        w->deleteLater();
        // Surface ANY dictionary files that failed to load (corrupt/truncated)
        // so the user knows a dictionary is missing and can re-import the folder.
        collectScanFailures();
        // Resolve duplicates ALREADY on disk before anything else reads the
        // dictionary list, so a cold start repairs an installation that holds two
        // copies instead of loading both and reporting them on every restart
        // (design.md D5). This runs on every scan, not just after an import:
        // at startup there is no "candidate" — the scan simply loads the staged
        // tree, and both copies come back.
        resolveDuplicateDictionaries([this, result]{
        // A staged directory that produced no loaded dictionary is a failed
        // import. If the user has since re-imported the folder successfully, the
        // stale copy is still on disk and would be retried — and re-reported —
        // forever, which is what made the banner's own advice ("pick the same
        // folder again") untrue. Sweep those now that the scan has settled, and
        // re-collect so the banner reflects the result.
        if (sweepStaleStagedDirs(result.sources))
            collectScanFailures();
        if (result.count > 0) {
            refreshDictionaries();
            refreshGroups();
        }
        // Auto-build full-text indexes for any dictionary that lacks one, so
        // search + FTS work without a manual per-dict "Index" button. Runs
        // sequentially off-thread; the UI's buildingFts progress bar covers it.
        autoIndexMissing();
        });
    });
    w->setFuture(f);
}

// ---------------------------------------------------------------------------
// Dictionary identity + duplicate resolution
// (openspec/changes/resolve-duplicate-dictionaries; logic in DictIdentity.hpp)
// ---------------------------------------------------------------------------

void EngineController::fetchIdentityInventory(
    const std::function<void(const QVector<DictIdentity::Identity> &)> &done) {
    // Off the UI thread on purpose: gd_dict_identity takes g_engineMutex, which a
    // running FTS build holds for its whole duration, so calling it inline would
    // freeze the app behind a long index build for a bookkeeping read.
    QFuture<QVector<DictIdentity::Identity>> f = QtConcurrent::run([]{
        QVector<DictIdentity::Identity> out;
        const int count = gd_dict_count();
        char buf[16384];
        for (int i = 0; i < count; ++i) {
            const int rc = gd_dict_identity(i, buf, static_cast<int>(sizeof(buf)));
            if (rc == -2)
                break; // count was stale: a concurrent removal shortened the vector
            if (rc != 0) {
                qWarning() << "[aurelex] gd_dict_identity failed for index" << i
                           << "rc =" << rc << "- skipping it rather than deduping blind";
                continue;
            }
            DictIdentity::Identity id = DictIdentity::parseRecord(QString::fromUtf8(buf));
            if (id.name.isEmpty())
                continue;
            id.engineIndex = i;
            out.append(id);
        }
        return out;
    });
    auto *w = new QFutureWatcher<QVector<DictIdentity::Identity>>(this);
    connect(w, &QFutureWatcher<QVector<DictIdentity::Identity>>::finished, this,
            [this, done, w] {
                done(w->result());
                w->deleteLater();
            });
    w->setFuture(f);
}

QVector<QVector<DictIdentity::Identity>> EngineController::duplicateGroups(
    const QVector<DictIdentity::Identity> &inventory) const {
    QVector<QVector<DictIdentity::Identity>> out;
    const QMap<QString, QVector<DictIdentity::Identity>> groups =
        DictIdentity::groupByName(inventory);
    for (auto it = groups.constBegin(); it != groups.constEnd(); ++it) {
        // A group of one is not a duplicate. Nor is a group whose members all hold
        // different content: that is a name clash, reported rather than resolved
        // (design.md D5) - the scan cannot know which build the user wants.
        if (it.value().size() < 2)
            continue;
        out.append(it.value());
    }
    return out;
}

void EngineController::autoIndexMissing()
{
    if (!m_ready) {
        // Nothing can be indexed; end the processing chain so the banner clears.
        setProcessingActive(false);
        return;
    }
    // Flag the pending enumeration so the Dicts banner shows a "preparing"
    // placeholder between a finished scan and the first FTS progress sample.
    setFtsStarting(true);
    // Keep the continuous processing indicator raised across the hand-off; the
    // worker's watcher clears it when the batch is truly empty (see
    // ensureFtsWorker). Re-raised here so an entry that skipped runScan's raise
    // (non-scan callers) still shows the banner.
    setProcessingActive(true);
    // Enumerate missing dictionary IDs OFF the UI thread: gd_dict_count/
    // gd_fts_index_state/gd_dict_id/gd_dict_meta take g_engineMutex, which a
    // running FTS worker can hold across a build slice. Doing this on the UI
    // thread would freeze the app. Deliver the list via a watcher (runs on the
    // UI thread) which then only touches m_ftsQueue (no engine calls). IDs are
    // stored, not engine indices, so removal mid-run can't shift/desync the
    // queue (see ensureFtsWorker). Dictionaries over kAutoFtsMaxBytes are
    // deferred (built on first full-text search, D5), not enqueued here.
    QSet<QString> failedSnapshot;
    {
        QMutexLocker lock(&m_ftsQueueMutex);
        failedSnapshot = m_ftsBuildFailed;
    }
    QFuture<QPair<QStringList, QStringList>> f =
        QtConcurrent::run([failedSnapshot]{
        QStringList toIndex;
        QStringList deferred;
        const int n = gd_dict_count();
        for (int i = 0; i < n; ++i) {
            int state = -1;
            if (!(gd_fts_index_state(i, &state) == 0 && state == 1))
                continue;
            char idb[128] = {0};
            if (gd_dict_id(i, idb, static_cast<int>(sizeof(idb))) != 0)
                continue;
            const QString id = QString::fromLocal8Bit(idb);
            if (failedSnapshot.contains(id))
                continue; // a previous build failed; never auto-retry it
            char lf[64] = {0}, lt[64] = {0};
            long long sizeBytes = 0;
            if (gd_dict_meta(i, lf, static_cast<int>(sizeof(lf)),
                             lt, static_cast<int>(sizeof(lt)), &sizeBytes) == 0
                && sizeBytes > kAutoFtsMaxBytes) {
                deferred.append(id);
                continue;
            }
            toIndex.append(id);
        }
        return QPair<QStringList, QStringList>(toIndex, deferred);
    });
    auto *w = new QFutureWatcher<QPair<QStringList, QStringList>>(this);
    connect(w, &QFutureWatcher<QPair<QStringList, QStringList>>::finished, this, [this, w]{
        const QStringList missing = w->result().first;
        const QStringList deferred = w->result().second;
        w->deleteLater();
        m_ftsDeferred = QSet<QString>(deferred.begin(), deferred.end());
        if (!deferred.isEmpty())
            qInfo() << "[aurelex] autoIndexMissing: deferred (over size bound; built on demand) ="
                    << deferred;
        qInfo() << "[aurelex] autoIndexMissing: dictionaries lacking an FTS index ="
                << missing;
        // Enumeration done: drop the placeholder. If there is work, the worker
        // below flips buildingFts true in this same event-loop turn so the
        // banner never blinks off between the two states. If there is NOTHING to
        // index, no worker will ever run, so this is where the continuous
        // processing chain ends (otherwise the banner would hang).
        setFtsStarting(false);
        // Enqueue IDs not already queued; start the single worker if idle.
        // A re-import mid-build appends and the running worker picks them up
        // (design D1).
        bool anyNew = false;
        {
            QMutexLocker lock(&m_ftsQueueMutex);
            for (const QString &id : missing) {
                if (!m_ftsQueue.contains(id)) {
                    m_ftsQueue.append(id);
                    anyNew = true;
                }
            }
        }
        if (anyNew && !m_ftsWorkerRunning) {
            ensureFtsWorker();
        } else if (!m_ftsWorkerRunning) {
            // Nothing to index and no worker draining: the chain is over.
            setProcessingActive(false);
        }
    });
    w->setFuture(f);
}

void EngineController::ensureFtsWorker()
{
    if (m_ftsWorkerRunning || m_ftsQueue.isEmpty()) return;
    m_ftsWorkerRunning = true;
#if defined(Q_OS_ANDROID)
    // Long builds (large dictionaries) run on a foreground IndexingService so
    // they survive the app being backgrounded; the service shows a notification
    // and keeps the in-process worker alive. Stopped when the batch completes.
    QJniObject::callStaticMethod<void>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "startIndexing",
        "()V");
#endif
    // Snapshot the batch total for THIS run (later appends grow the queue and
    // will be drained by a subsequent run once this one empties; see design D3).
    int runTotal = 0;
    {
        QMutexLocker lock(&m_ftsQueueMutex);
        runTotal = m_ftsQueue.size();
    }
    setFtsIndexProgress(0, runTotal, QString());
    setBuildingFts(true);
    qInfo() << "[aurelex] FTS indexing batch start; total =" << runTotal;

    // The worker drains the shared queue. Each popped ID is re-resolved to the
    // CURRENT engine index (a dictionary removed mid-run simply no longer
    // resolves -> counted and skipped), re-checked at pop time so one already
    // built by an earlier run is skipped (never indexed twice), and ALWAYS
    // counted toward done — so the overall bar reaches runTotal / 100% when the
    // batch finishes. The current dictionary's name is published BEFORE the
    // build so the header shows what's actually being indexed.
    QFuture<void> f = QtConcurrent::run([this, runTotal]{
        int done = 0;
        char idb[128] = {0};
        // nb/fb feed gd_dict_info the same way readDictInfoAt does, so the name
        // this loop reports to the progress UI cannot disagree with the name the
        // list shows. fb is unused, but gd_dict_info rejects a null file buffer
        // whenever file_size > 0 (carve/gd_boundary.cc), so a caller that only
        // wants the name must still supply one - do not drop it.
        char nb[kDictInfoBufferSize] = {0}, fb[kDictInfoBufferSize] = {0};
        for (;;) {
            QString id;
            {
                QMutexLocker lock(&m_ftsQueueMutex);
                if (m_ftsQueue.isEmpty())
                    break;
                id = m_ftsQueue.takeFirst();
            }
            // Resolve id -> current index (removals shift engine indices).
            int idx = -1;
            {
                const int n = gd_dict_count();
                for (int i = 0; i < n; ++i) {
                    if (gd_dict_id(i, idb, static_cast<int>(sizeof(idb))) == 0
                        && id == QLatin1String(idb)) {
                        idx = i;
                        break;
                    }
                }
            }
            if (idx < 0) {
                // Removed while queued; count and move on.
                ++done;
                emit ftsIndexBatchProgress(done, runTotal, QString());
                continue;
            }
            QString name;
            if (gd_dict_info(idx, nb, static_cast<int>(sizeof(nb)),
                             fb, static_cast<int>(sizeof(fb))) == 0)
                name = QString::fromLocal8Bit(nb);
            // Publish the CURRENT dictionary + count before the (long) build so
            // the UI isn't one item behind.
            emit ftsIndexBatchProgress(done, runTotal, name);
            int st = -1;
            if (!(gd_fts_index_state(idx, &st) == 0 && st == 0)) {
                const int rc = gd_fts_index(idx);
                // -2 = cancelled (the dictionary is being removed): count it and
                // move on. Any other failure is remembered (never auto-retried)
                // so an on-demand re-run cannot loop on it.
                if (rc != 0 && rc != -2 && !id.isEmpty()) {
                    QMutexLocker lock(&m_ftsQueueMutex);
                    m_ftsBuildFailed.insert(id);
                }
            }
            ++done;
            emit ftsIndexBatchProgress(done, runTotal, name);
        }
    });
    auto *w = new QFutureWatcher<void>(this);
    connect(w, &QFutureWatcher<void>::finished, this, [this, w]{
        w->deleteLater();
        m_ftsWorkerRunning = false;
        qInfo() << "[aurelex] FTS worker finished a drain";
#if defined(Q_OS_ANDROID)
        QJniObject::callStaticMethod<void>(
            "org/aurelex/pocket/dictionary/AurelexActivity",
            "stopIndexing",
            "()V");
#endif
        // If more indices were enqueued during/just after the drain (a re-import
        // raced the last pop), hand them to a fresh worker so they are not
        // stranded — keep the indicator on. Only when the queue is genuinely
        // empty is the batch truly done.
        bool empty = false;
        {
            QMutexLocker lock(&m_ftsQueueMutex);
            empty = m_ftsQueue.isEmpty();
        }
        if (empty) {
            setFtsIndexProgress(0, 0, QString());
            setBuildingFts(false);
            // A full-text search that triggered on-demand builds is owed one
            // re-run now that the batch drained, so the deferred dictionaries'
            // hits appear (D5).
            reRunPendingFts();
            if (m_stagedRescanPending) {
                // A download landed in files/staged/ while this batch was still
                // indexing, so the tree we just indexed no longer covers it.
                // Re-arm BEFORE the hand-off: consuming the flag here would
                // leave a batch that finished mid-chain with no rescan, and
                // never clearing processingActive is what keeps the Dicts
                // banner from blinking off between the two scans.
                m_stagedRescanPending = false;
                qInfo() << "[aurelex] download landed during indexing; rescanning staged tree";
                runScan();
                return;
            }
            // Batch genuinely done: end the continuous processing chain so the
            // Dicts banner clears. No phase hand-off follows, so this is the
            // single place the whole staging -> scan -> index lifecycle ends.
            setProcessingActive(false);
            // Indexing + scanning finished: at this point the staged tree is
            // consistent, so purge any leftover temporary staging dirs (partial
            // copies from a killed/interrupted stage). See the "clear stale
            // staging leftovers" intent — this is a safe cleanup moment. Scratch
            // dirs a live download still owns are excluded (optional audio
            // downloads run while the dicts are otherwise idle).
            purgeStagingTmp(liveDownloadHashes());
        } else {
            ensureFtsWorker();
        }
    });
    w->setFuture(f);
}

void EngineController::initialize(const QString &appDir, const QString &stagedDir) {
    m_appDir = appDir;
    m_stagedDir = stagedDir;
    installDiagLog(appDir);
    QDir().mkpath(appDir);
    QDir().mkpath(stagedDir);
    // The engine treats the index dir as a prefix (it appends the dictionary id),
    // so it must end in a separator — otherwise indexes land beside the directory
    // as `files/index<md5>` instead of inside it. Build it with QDir so the
    // separator is correct by construction, independent of the boundary's own
    // normalization (fix-index-directory-path-separator, design.md D2).
    const QString indexDir = QDir(appDir).filePath(QStringLiteral("index")) + QDir::separator();
    QDir().mkpath(indexDir);
    // Move any strays left by the pre-fix path into `index/` before the engine
    // looks there, so existing devices do not have to reindex
    // (fix-index-directory-path-separator, design.md Migration Plan Option A).
    const int migrated = IndexMigration::migrateStrayIndexes(appDir);
    if (migrated > 0)
        qInfo() << "[aurelex] migrated" << migrated << "stray index entries into index/";
    QFuture<int> f = QtConcurrent::run([appDir, indexDir]{
        return gd_init(appDir.toLocal8Bit().constData(),
                       indexDir.toLocal8Bit().constData());
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] init rc=" << rc;
        if (rc != 1) {
            setLastError(QStringLiteral("gd_init failed (rc=%1)").arg(rc));
            w->deleteLater();
            return;
        }
        setReady(true);
        w->deleteLater();
        updateSystemDark();
        loadSettings();
        loadHistory();
        loadFavorites();
        runScan();
    });
    w->setFuture(f);
}

void EngineController::refreshDictionaries() {
    if (!m_ready) {
        qInfo() << "[aurelex] refreshDictionaries skipped: not ready";
        return;
    }
    qInfo() << "[aurelex] refreshDictionaries firing";
    // Dictionary set/scopes changed: cached articles may be stale.
    clearArticleCache();
    QFuture<QVariantList> f = QtConcurrent::run([]{
        QVariantList list;
        const int n = gd_dict_count();
        list.reserve(n);
        std::vector<char> lf(128), lt(128);
        for (int i = 0; i < n; ++i) {
            const DictInfoAtIndex info = readDictInfoAt(i);
            if (!info.ok) continue;
            QVariantMap m;
            // The list is sorted by name below, so the displayed position is NOT
            // the engine's index. Carry the engine index (the coordinate every
            // gd_* call that takes an index expects) alongside each entry, and
            // translate display positions back to it before crossing the
            // boundary (fix-dictionary-removal-index-mismatch).
            m.insert("engineIndex", i);
            m.insert("name", info.name);
            m.insert("source", info.source);
            // Language pair + approx size (design D1): human names, empty when
            // unknown (QML renders '?'); size is the summed staged source files.
            long long sizeBytes = 0;
            if (gd_dict_meta(i, lf.data(), static_cast<int>(lf.size()),
                             lt.data(), static_cast<int>(lt.size()),
                             &sizeBytes) == 0) {
                const QString from = QString::fromUtf8(lf.data());
                const QString to = QString::fromUtf8(lt.data());
                m.insert("langFrom", from);
                m.insert("langTo", to);
                m.insert("sizeBytes", sizeBytes);
                // Section key for By-Pair grouping (unknown side -> '?').
                m.insert("pair", (from.isEmpty() ? QStringLiteral("?") : from)
                                 + QLatin1Char('/')
                                 + (to.isEmpty() ? QStringLiteral("?") : to));
            }
            list.append(m);
        }
        // Alphabetical by name (flat view). By-Pair grouping re-groups this on
        // the QML side; within each group the relative name-order is preserved.
        std::sort(list.begin(), list.end(),
                  [](const QVariant &a, const QVariant &b){
            return a.toMap().value("name").toString().toLower()
                   < b.toMap().value("name").toString().toLower();
        });
        return list;
    });
    auto *w = new QFutureWatcher<QVariantList>(this);
    connect(w, &QFutureWatcher<QVariantList>::finished, this, [this, w]{
        const QVariantList list = w->result();
        setDictionaries(list);
        // The list now matches the engine, so the "unloaded but not yet re-read"
        // exclusions are satisfied and must not leak into later decisions - they
        // would keep a staged directory alive that nothing reads from.
        if (!m_unloadedSources.isEmpty()) {
            qInfo() << "[aurelex] clearing" << m_unloadedSources.size()
                    << "stale unloaded-source entries after refresh";
            m_unloadedSources.clear();
        }
        // Keep the catalog's installed badges honest: a download that just got
        // scanned in (or a removal) changes which entries are installed, and the
        // badge is derived from the loaded sources.
        refreshCatalogEntries();
        // Diagnostics: the full set of loaded dictionaries (id/name/source), so
        // the log shows exactly what is available after a scan / import.
        qInfo() << "[aurelex] dictionaries available:" << list.size();
        for (const QVariant &v : list) {
            const QVariantMap m = v.toMap();
            qInfo().noquote() << "  -" << m.value("name").toString()
                              << "[" << m.value("pair").toString() << "]"
                              << m.value("source").toString();
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::removeDictionary(int index) {
    removeDictionaries(QVariantList{index});
}

void EngineController::removeDictionaries(const QVariantList &indices) {
    if (!m_ready || indices.isEmpty()) return;
    // Removal is permitted during staging / scanning / full-text indexing
    // (fts-indexing-performance): the build now interleaves with other gd_*
    // calls, so a removal no longer queues for the whole build. Any in-flight
    // build for a removed dictionary is cancelled and awaited (bounded) in the
    // worker below before its files are reaped.
    // The QML side passes DISPLAY positions (indices into dictionaries(), which
    // is sorted by name). Resolve them to engine indices and capture each
    // source path on the UI thread BEFORE any gd_remove_dict shifts the engine
    // list. removalTargets orders the result highest-engine-index-first, so a
    // SEQUENTIAL removal never shifts a later target (independent
    // gd_remove_dict tasks could acquire g_engineMutex out of order and delete
    // the wrong dictionaries).
    struct Target {
        int engineIndex;
        QString source;
        QString name;
    };
    const QVector<DictionaryIndex::RemovalTarget> resolved =
        DictionaryIndex::removalTargets(m_dictionaries, indices);
    if (resolved.isEmpty()) return;
    std::vector<Target> targets;
    targets.reserve(static_cast<size_t>(resolved.size()));
    for (const DictionaryIndex::RemovalTarget &t : resolved) {
        const QVariantMap d = m_dictionaries.at(t.displayIndex).toMap();
        targets.push_back({t.engineIndex, d.value("source").toString(),
                           d.value("name").toString()});
    }

    qInfo().noquote() << "[aurelex] removeDictionaries requested:" << targets.size();
    for (const Target &t : targets)
        qInfo().noquote() << "  -" << t.name << "engIdx=" << t.engineIndex
                          << "src=" << t.source;

    const QString stagedRoot = m_stagedDir;
    const QString appDir = m_appDir;

    QFuture<QPair<QVariantList, int>> f = QtConcurrent::run([this, targets]{
        QVariantList removed;
        removed.reserve(static_cast<int>(targets.size()));
        for (const Target &t : targets) {
            char idbuf[128] = {0};
            QString id;
            if (gd_dict_id(t.engineIndex, idbuf, static_cast<int>(sizeof(idbuf))) == 0)
                id = QString::fromLocal8Bit(idbuf);
            // Cancel any in-flight full-text build for this dictionary and drop
            // it from the queue BEFORE removing it from the engine (D4): the
            // build stops at its next slice, so it cannot reintroduce the
            // removed dictionary.
            const QByteArray idb = id.toLocal8Bit();
            if (!id.isEmpty()) {
                {
                    QMutexLocker lock(&m_ftsQueueMutex);
                    m_ftsQueue.removeAll(id);
                }
                gd_fts_cancel(idb.constData());
            }
            const int rc = gd_remove_dict(t.engineIndex);
            // Wait (bounded) for the cancelled build to report idle before the
            // caller reaps files, so a build that was mid-publish finishes
            // first and cannot leave an orphan index behind.
            if (rc == 0 && !id.isEmpty()) {
                int st = 1;
                for (int waited = 0; waited < kFtsIdleWaitMs; waited += 25) {
                    if (gd_fts_build_state(idb.constData(), &st) == 0 && st == 0)
                        break;
                    QThread::msleep(25);
                }
                if (st != 0)
                    qInfo() << "[aurelex] removal proceeding with FTS build not idle for" << id;
            }
            QVariantMap m;
            m.insert("source", t.source);
            m.insert("name", t.name);
            m.insert("id", id);
            m.insert("rc", rc);
            removed.append(m);
        }
        return QPair<QVariantList, int>(removed, gd_dict_count());
    });
    auto *w = new QFutureWatcher<QPair<QVariantList, int>>(this);
    connect(w, &QFutureWatcher<QPair<QVariantList, int>>::finished, this,
            [this, w, stagedRoot, appDir]{
        const QPair<QVariantList, int> result = w->result();
        const int remaining = result.second;
        for (const QVariant &v : result.first) {
            const QVariantMap m = v.toMap();
            const QString dictId = m.value("id").toString();
            const int rc = m.value("rc").toInt();
            qInfo().noquote() << "[aurelex] removeDictionary result: rc=" << rc
                              << "name=" << m.value("name").toString()
                              << "id=" << dictId << "remaining=" << remaining;
            if (rc != 0) {
                setLastError(QStringLiteral("remove_dict failed (rc=%1)").arg(rc));
                continue;
            }
            // Permanent delete: remove the app's copy + its index cache.
            //
            // Record the source as unloaded FIRST. The engine object is gone, but
            // m_dictionaries still lists it until refreshDictionaries() runs below,
            // so without this the sharing guard counts the removed dictionary as a
            // remaining user of its own staged directory and keeps it - leaving the
            // dictionary's companion files and resource tree on disk, and blocking
            // its re-import (reclaim-staged-dirs-on-removal). The duplicate path
            // (removeDuplicates) already does this; this user-initiated path did
            // not, which is why the guard misjudged removals made from the UI.
            const QString removedSource = m.value("source").toString();
            if (!removedSource.isEmpty() && !m_unloadedSources.contains(removedSource))
                m_unloadedSources.append(removedSource);

            deleteDictionaryFiles(removedSource, dictId, stagedRoot, appDir);
            // Also drop the id from the still-running FTS queue so a removed
            // dictionary is never indexed by a worker that already popped it.
            if (!dictId.isEmpty()) {
                QMutexLocker lock(&m_ftsQueueMutex);
                m_ftsQueue.removeAll(dictId);
            }
        }
        refreshDictionaries();
        refreshGroups();
        setDictCount(remaining);
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::reloadDictionariesForResources(const QStringList &entryIds) {
    if (entryIds.isEmpty() || !m_ready) return;
    // Map each entry to the basenames its dictionary files have, then find the
    // loaded dictionaries whose source basename matches. A dictionary is
    // identified by its primary source file (m_dictionaries[].source), which is
    // the same value installed-detection matches on, so the two agree.
    QStringList wanted;
    for (const QString &id : entryIds) {
        const RemoteCatalog::Entry *e = findCatalogEntry(id);
        if (!e) continue;
        for (const RemoteCatalog::File &f : e->dictionaryFiles())
            wanted.append(f.name);
    }
    if (wanted.isEmpty()) return;
    QStringList targets;
    for (const QVariant &v : m_dictionaries) {
        const QVariantMap d = v.toMap();
        if (wanted.contains(QFileInfo(d.value("source").toString()).fileName()))
            targets.append(d.value("name").toString());
    }
    if (targets.isEmpty()) {
        // Nothing loaded under those names (the audio arrived before the
        // dictionary itself): a plain rescan is enough.
        return;
    }
    qInfo().noquote() << "[aurelex] reloading for new resources:" << targets;

    // Collect the engine indices to unload on the UI thread, then do the
    // engine work off it: every gd_* call takes g_engineMutex, which a running
    // FTS build holds for its whole duration, and this must never block the UI.
    // High-to-low so each gd_remove_dict's index shift cannot invalidate a
    // later target.
    QVector<int> indices;
    for (int i = m_dictionaries.size() - 1; i >= 0; --i) {
        const QVariantMap d = m_dictionaries.at(i).toMap();
        if (wanted.contains(QFileInfo(d.value("source").toString()).fileName()))
            indices.append(i);
    }
    if (indices.isEmpty()) return;

    // Claim the continuous-processing indicator for the WHOLE unload, not just
    // the rescan that follows. The indices above were collected against the
    // current m_dictionaries ordering; a deletion landing now would shift them
    // and gd_remove_dict would unload the WRONG dictionary. runScan() does not
    // lower processingActive either, so nothing flickers in between.
    m_processingActive = true;
    emit processingActiveChanged();

    QFuture<int> f = QtConcurrent::run([indices]{
        for (int idx : indices) {
            const int rc = gd_remove_dict(idx);
            qInfo() << "[aurelex] resource-reload gd_remove_dict idx=" << idx << "rc=" << rc;
        }
        return gd_dict_count();
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, w]{
        const int count = w->result();
        w->deleteLater();
        qInfo() << "[aurelex] resource-reload unloaded; dictionaries now" << count;
        // Deliberately NOT deleting files or the index: the dictionary itself
        // is still installed and must keep its FTS index (task 8.2), its list
        // position and its group membership (8.3). Only the in-memory handle
        // was dropped, so the rescan re-adds the SAME dictionary (same content
        // hash -> same engine id -> same index files, same order, same groups)
        // and the new resources take effect. autoIndexMissing then finds its
        // index already built and skips it.
        runScan();
    });
    w->setFuture(f);
}

void EngineController::resolveDuplicateDictionaries(const std::function<void()> &done) {
    fetchIdentityInventory([this, done](const QVector<DictIdentity::Identity> &inv) {
        const QVector<QVector<DictIdentity::Identity>> groups = duplicateGroups(inv);

        // Did the scan being resolved follow a pick? If so, a dictionary whose
        // staged root did not exist before the pick is a CANDIDATE: the
        // import-path rule (skip an identical one, reject a differing one) applies
        // to it. Otherwise only the cold-start rule runs: collapse identical
        // copies, but report differing ones and delete none (design.md D3/D5).
        const bool afterPick = m_prePickSnapshotValid;

        auto isCandidate = [&](const DictIdentity::Identity &id) {
            if (!afterPick)
                return false;
            const QString anc = stagedAncestor(id.primaryFile, m_stagedDir);
            return !anc.isEmpty() && !m_prePickStagedDirs.contains(anc);
        };

        QVector<DictIdentity::Identity> toDrop;
        QVariantList clashRows;
        for (const QVector<DictIdentity::Identity> &group : groups) {
            bool allIdentical = true;
            for (int i = 1; i < group.size(); ++i) {
                if (!DictIdentity::sameContent(group.at(0), group.at(i))) {
                    allIdentical = false;
                    break;
                }
            }
            QVector<bool> isCand(group.size(), false);
            bool anyIncumbent = false;
            for (int i = 0; i < group.size(); ++i) {
                isCand[i] = isCandidate(group.at(i));
                if (!isCand[i])
                    anyIncumbent = true;
            }

            if (allIdentical) {
                // Keep an INCUMBENT when there is one, so the dictionary the user
                // already had keeps its object, list position, groups and indexes;
                // otherwise keep the first in engine order. Drop the rest. An
                // identical candidate therefore disappears silently — the skip
                // (design D3), and what repairs an existing installation (D5).
                int keep = 0;
                for (int i = 0; i < group.size(); ++i) {
                    if (!isCand[i]) { keep = i; break; }
                }
                for (int i = 0; i < group.size(); ++i) {
                    if (i != keep)
                        toDrop.append(group.at(i));
                }
                qInfo().noquote() << "[aurelex] collapsing identical duplicates of"
                                  << group.at(keep).name << "x" << group.size();
                continue;
            }

            // Content differs. On the import path the CANDIDATE is the copy to
            // remove; the incumbent is never touched (design D3). With no
            // incumbent — a cold-start clash, or two builds inside one pick —
            // nothing is deleted, because a scan expresses no intent (design D5).
            bool rejected = false;
            if (anyIncumbent) {
                for (int i = 0; i < group.size(); ++i) {
                    if (isCand[i]) {
                        toDrop.append(group.at(i));
                        rejected = true;
                    }
                }
            }
            qWarning().noquote()
                << "[aurelex] name clash:" << group.at(0).name << "is present"
                << group.size() << "times with different content -"
                << (rejected ? "the incoming copy is removed"
                             : "left in place; the user removes one");

            QVariantMap row;
            row.insert("name", group.at(0).name);
            row.insert("file", QString());
            row.insert("reason", rejected ? QStringLiteral("nameClashWithInstalled")
                                          : QStringLiteral("nameClash"));
            clashRows.append(row);
        }

        m_nameClashes = clashRows;
        setResultClashes(clashRows);

        if (!toDrop.isEmpty()) {
            const int removed = unloadAndDelete(toDrop);
            qInfo() << "[aurelex] duplicate resolution removed" << removed
                    << "dictionary copy(ies)";
        }

        // The pick's candidate window is over: later scans use the cold-start rule.
        m_prePickSnapshotValid = false;
        m_prePickStagedDirs.clear();
        done();
    });
}

int EngineController::unloadAndDelete(
    const QVector<DictIdentity::Identity> &drop) {
    if (drop.isEmpty())
        return 0;

    // DESCENDING engine index: each gd_remove_dict renumbers the dictionaries
    // after it, so removing high-to-low leaves every index still to be removed
    // pointing at the dictionary it was read from.
    QVector<DictIdentity::Identity> ordered = drop;
    std::sort(ordered.begin(), ordered.end(),
              [](const DictIdentity::Identity &a, const DictIdentity::Identity &b) {
                  return a.engineIndex > b.engineIndex;
              });

    // Read the ids off-thread with the unload: gd_dict_id and gd_remove_dict take
    // g_engineMutex, the lock a running FTS build holds for its whole duration, so
    // this must not sit on the UI thread. The id must be read BEFORE the unload -
    // it is an MD5 over the source paths, which are gone afterwards.
    //
    // waitForFinished() below blocks the UI thread for the duration. That is a
    // deliberate trade: the file deletions that follow must see the engine's FINAL
    // dictionary set, and keeping the loop on the UI thread is what makes the
    // order (unload -> delete files -> refresh) enforceable at all. The wait is
    // bounded by one dict_remove per collapsed duplicate, on a path that runs once
    // per scan with no user action pending.
    QFuture<QVector<QPair<int, QString>>> f = QtConcurrent::run([ordered] {
        QVector<QPair<int, QString>> results;
        for (const DictIdentity::Identity &id : ordered) {
            char idBuf[64] = {0};
            QString dictId;
            if (gd_dict_id(id.engineIndex, idBuf, static_cast<int>(sizeof(idBuf))) == 0)
                dictId = QString::fromUtf8(idBuf);
            else
                qWarning() << "[aurelex] could not read dict id for index"
                           << id.engineIndex << "- its index cache will be left behind";
            results.append(qMakePair(gd_remove_dict(id.engineIndex), dictId));
        }
        return results;
    });
    f.waitForFinished();

    const QVector<QPair<int, QString>> results = f.result();
    int removed = 0;
    for (int i = 0; i < results.size(); ++i) {
        const int rc = results.at(i).first;
        const DictIdentity::Identity &id = ordered.at(i);
        qInfo().noquote() << "[aurelex] duplicate unloaded: name=" << id.name
                          << "id=" << results.at(i).second << "rc=" << rc;
        if (rc != 0) {
            // The engine kept it. Delete its files anyway and the next scan reads a
            // loaded object from a missing file — strictly worse than a duplicate,
            // so the files stay and the duplicate is reported instead.
            qWarning() << "[aurelex] unload refused for" << id.name
                       << "- its files kept rather than orphaning a live dictionary";
            continue;
        }
        ++removed;
        // The engine object is gone, but m_dictionaries still lists it until the
        // async refresh lands. Record it so the sharing guard does not treat its
        // staged directory as occupied and keep a directory that now holds
        // nothing (nothing else would ever reclaim it).
        if (!id.primaryFile.isEmpty())
            m_unloadedSources.append(id.primaryFile);
        // Only once the engine object is gone is it safe to reclaim the files.
        deleteIdentityFiles(id, results.at(i).second);
    }

    // The list and the group membership both changed. Groups are stored by
    // dictionary id and the survivors' ids are untouched, so their membership
    // survives this wholesale.
    refreshDictionaries();
    refreshGroups();
    return removed;
}

void EngineController::deleteIdentityFiles(const DictIdentity::Identity &id,
                                           const QString &dictId) {
    const QString stagedRoot = m_stagedDir;
    const QString primary = id.primaryFile;
    if (primary.isEmpty())
        return;

    // The index cache first: it is keyed by the engine id and needs no path
    // checks, and leaving it behind would let a later import of the same content
    // adopt a stale index.
    if (!dictId.isEmpty() && !m_appDir.isEmpty()) {
        for (const QString &full : IndexCleanup::removeIndexEntries(m_appDir, dictId))
            qInfo() << "[aurelex] removed index entry" << full;
    }

    const QString stagedDir = stagedAncestor(primary, stagedRoot);
    if (stagedDir.isEmpty()) {
        // Not under the staged root: refuse rather than delete a path the app does
        // not own. Nothing in the app stages a dictionary anywhere else.
        qWarning() << "[aurelex] refusing to delete a dictionary outside the staged"
                      " root:"
                   << primary;
        return;
    }

    // Delete the whole file SET, not just the primary: an .mdx plus its .mdd
    // volumes, a StarDict .ifo plus .idx/.dict, is one dictionary, and leaving the
    // companions behind means a later import of the same folder builds a broken
    // one. Basenames are resolved inside the PRIMARY's own directory, not the
    // top-level import root: an import mirrors the picked folder's layout, so a
    // nested dictionary's files live several levels down (fix-long-path /
    // report-import-results).
    const QDir fileDir(QFileInfo(primary).absolutePath());
    for (const DictIdentity::SourceFile &sf : id.files) {
        const QString victim = fileDir.filePath(sf.baseName);
        if (!StagedCleanup::isUnderRoot(victim, stagedRoot)) {
            qWarning() << "[aurelex] refusing to delete outside the staged root:"
                       << victim;
            continue;
        }
        if (QFileInfo::exists(victim) && !QFile::remove(victim))
            qWarning() << "[aurelex] could not delete" << victim;
    }

    // A DSL keeps its sounds and images in a sibling `<name>.dsl.files/` tree. It
    // is not in the engine's file set (design.md D2), so the loop above never saw
    // it. Remove it by name so no orphaned audio tree survives the dictionary.
    QString tree = primary;
    if (tree.endsWith(QLatin1String(".dz")))
        tree.chop(3); // .dsl.dz -> .dsl
    if (tree.endsWith(QLatin1String(".dsl")))
        tree += QLatin1String(".files");
    if (tree != primary) {
        const QString treeDir = fileDir.filePath(QFileInfo(tree).fileName());
        if (StagedCleanup::isUnderRoot(treeDir, stagedRoot) &&
            QFileInfo::exists(treeDir)) {
            qInfo() << "[aurelex] removing staged resource tree" << treeDir;
            QDir(treeDir).removeRecursively();
        }
    }

    // Reclaim the staged directory ONLY when nothing still reads from it: one
    // import folder holds many dictionaries, so removing one must not delete its
    // siblings. removeStagedDirIfUnused re-checks that against the live list and
    // removes the directory once its last user is gone.
    if (!removeStagedDirIfUnused(stagedDir, liveDictionarySources()))
        qInfo() << "[aurelex] staged dir kept (shared by siblings)" << stagedDir;
}

void EngineController::dismissScanFailures() {
    // Pure UI state: removing the banner changes nothing on disk. An unloadable
    // source's files were already deleted when the scan reported it
    // (report-import-results, design D2/D7), so there is no action left to take.
    setScanFailures({});
    setResultClashes({});
}

void EngineController::deleteDictionaryFiles(const QString &sourceFile,
                                             const QString &dictId,
                                             const QString &stagedRoot,
                                             const QString &appDir) {
    // Delete the engine's index cache for this dictionary. The engine writes it
    // as `<indexDir><id>` and `<indexDir><id>_FTS_x`, and the index dir is
    // `<appDir>/index/` (a prefix - see index_path.hpp), so the entries are
    // files/index/<id> and files/index/<id>_FTS_x. The helper also removes the
    // pre-fix `files/index<id>` strays, so a removal is correct even if the
    // layout migration has not run (fix-dictionary-removal-cleanup).
    if (!dictId.isEmpty() && !appDir.isEmpty()) {
        const QStringList removed = IndexCleanup::removeIndexEntries(appDir, dictId);
        for (const QString &full : removed)
            qInfo() << "[aurelex] removed index entry" << full;
    }
    // Delete the dictionary's OWN staged source file. This must happen even when
    // the import folder is shared with sibling dictionaries (e.g. one GoldenDict
    // import holding many dicts): otherwise the removed dict's file stays on
    // disk and the next startup scan re-adds it (the "deleted dictionaries
    // reappear" bug).
    if (!sourceFile.isEmpty() && QFileInfo::exists(sourceFile)) {
        const bool ok = QFile::remove(sourceFile);
        qInfo() << "[aurelex] removed staged source file" << sourceFile << "ok=" << ok;
    }
    // Delete the staged copy's folder (files/staged/<sourceId>) only if no other
    // loaded dictionary still uses it (a single import folder can hold several
    // dictionaries; removing one must not delete its siblings). When shared, the
    // per-file delete above already removed this dictionary's file.
    if (!sourceFile.isEmpty() && !stagedRoot.isEmpty()) {
        const QString stagedDir = stagedAncestor(sourceFile, stagedRoot);
        // The guard now lives in removeStagedDirIfUnused so the failed-import
        // cleanup cannot drift from it.
        if (!stagedDir.isEmpty()
            && !removeStagedDirIfUnused(stagedDir, liveDictionarySources())) {
            qInfo() << "[aurelex] staged copy dir kept (shared by siblings)"
                    << stagedDir;
        }
    }
}

QStringList EngineController::liveDictionarySources() const {
    QStringList sources;
    sources.reserve(m_dictionaries.size());
    for (const QVariant &v : m_dictionaries) {
        const QString s = v.toMap().value("source").toString();
        // A source unloaded moments ago is still in m_dictionaries until the
        // async refresh lands; counting it would keep its staged directory alive
        // with nothing in it, and sweepStaleStagedDirs only reclaims a directory a
        // scan reported as FAILED, so it would never be cleaned up again.
        if (!s.isEmpty() && !m_unloadedSources.contains(s))
            sources.append(s);
    }
    return sources;
}

// `loadedSources` is a parameter rather than read from m_dictionaries so that
// every caller names the set it is protecting a deletion with: the sweep passes
// the scan's list (the model is empty on a cold start), the removal and
// failed-import paths pass liveDictionarySources() (the model is the right
// authority there - it reflects an edit the user just made, including the
// m_unloadedSources exclusions that stop a just-unloaded dictionary from
// keeping its own directory alive). Containment and sharing are decided in one
// place so no caller can apply one guard and forget the other
// (see app/StagedCleanup.hpp).
bool EngineController::removeStagedDirIfUnused(const QString &stagedDir,
                                               const QStringList &loadedSources) {
    if (stagedDir.isEmpty() || m_stagedDir.isEmpty())
        return false;

    if (!StagedCleanup::isDirectChildOf(stagedDir, m_stagedDir)) {
        qWarning() << "[aurelex] refusing to remove staged dir outside the staged root:"
                   << stagedDir << "(root" << m_stagedDir << ")";
        return false;
    }
    if (StagedCleanup::isUsedByLoadedDictionary(stagedDir, loadedSources)) {
        qInfo() << "[aurelex] staged dir kept, a loaded dictionary uses it" << stagedDir;
        return false;
    }

    const QString dirAbs = QDir(stagedDir).absolutePath();
    if (!QFileInfo::exists(dirAbs))
        return true;
    qInfo() << "[aurelex] removing staged dir" << dirAbs;
    return QDir(dirAbs).removeRecursively();
}

bool EngineController::sweepStaleStagedDirs(const QStringList &loadedSources) {
    if (m_stagedDir.isEmpty())
        return false;
    // Never sweep while an import is being copied: a directory mid-copy can
    // transiently hold companion files before its primary file lands, and would
    // read as an orphan. Staging has finished by the time this normally runs
    // (it is invoked after the scan settles), so this only guards the overlap.
    if (m_stagingActive)
        return false;
    QDir root(m_stagedDir);
    if (!root.exists())
        return false;

    // Directories a loaded dictionary reads from. Anything else under the staged
    // root produced nothing, i.e. it is a failed import.
    //
    // The list is the scan's, handed in by the caller, NOT liveDictionarySources()
    // from m_dictionaries: the model is still empty on the first scan after a
    // launch (this runs before refreshDictionaries), so reading it here made the
    // guard vacuous and every nested import an orphan
    // (fix-stale-sweep-deletes-live-dictionaries). Logged so a cold start is
    // checkable from logcat - a 0 here with dictionaries on disk means the guard
    // is broken again.
    qInfo() << "[aurelex] staged sweep: in-use sources handed to the sweep ="
            << loadedSources.size();

    const QStringList dirs =
        root.entryList(QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name);
    bool removedAny = false;
    for (const QString &name : dirs) {
        const QString dirAbs = root.absoluteFilePath(name);
        // The shared guard, not a local reimplementation of it: the sweep used to
        // carry its own prefix loop, which is the second time this file has had
        // two copies of this test and only one of them was tested.
        if (StagedCleanup::isUsedByLoadedDictionary(dirAbs, loadedSources))
            continue;

        // An orphan: a staged directory that holds no primary dictionary file.
        // The dictionary it belonged to was removed (its primary file deleted)
        // or its import never produced one, so nothing will ever load from it.
        // It must be reclaimed here rather than left forever - nothing else
        // collects it, and while it remains it also blocks re-importing that
        // dictionary (reclaim-staged-dirs-on-removal).
        //
        // Checked BEFORE the failed-import test, because such a directory
        // produces no scan failure to be reported: it yields no dictionary and
        // no error, which is exactly why the old condition never matched it.
        //
        // RECURSIVE. An import mirrors the picked folder's layout, so the normal
        // staged shape is staged/<sourceId>/<topic>/<name>/<dict>.dsl.dz. Reading
        // only the top level found no primary in that shape and deleted the
        // directory while its dictionaries were loaded and searchable. This is
        // also the layer that protects any dictionary the in-use list cannot name,
        // independent of that list's completeness.
        if (!StagedCleanup::holdsPrimaryDictionaryFile(dirAbs)) {
            qInfo() << "[aurelex] sweeping staged dir holding no dictionary" << dirAbs;
            if (removeStagedDirIfUnused(dirAbs, loadedSources))
                removedAny = true;
            continue;
        }

        // Otherwise only sweep a directory the scan actually reported as failed.
        // A populated directory no scan complained about is not ours to delete
        // (it may be a staged import still being walked by another code path).
        bool reported = false;
        for (const QVariant &v : m_scanFailures) {
            const QString f = v.toMap().value("file").toString();
            if (f.startsWith(dirAbs + QLatin1Char('/'))) {
                reported = true;
                break;
            }
        }
        if (!reported)
            continue;
        qInfo() << "[aurelex] sweeping stale failed import" << dirAbs;
        if (removeStagedDirIfUnused(dirAbs, loadedSources))
            removedAny = true;
    }
    return removedAny;
}

void EngineController::purgeStagingTmp(const QStringList &keepHashes) {
    // Remove leftover temporary staging dirs (files/staging-tmp/*). These only
    // ever hold in-progress copies; once scanning + indexing have finished they
    // are stale, so deleting them keeps app storage clean. `keepHashes` are the
    // scratch dirs a live download still owns (a partial copy mid-flight) —
    // deleting one under a running transfer would corrupt it.
    const QString tmpRoot = m_stagedDir + QStringLiteral("/../staging-tmp");
    QDir dir(tmpRoot);
    if (!dir.exists()) return;
    qInfo() << "[aurelex] purging stale staging-tmp, keeping" << keepHashes.size() << "live";
    for (const QString &entry : dir.entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        if (keepHashes.contains(entry)) {
            qInfo() << "[aurelex] staging-tmp kept (live download)" << entry;
            continue;
        }
        QDir(dir.filePath(entry)).removeRecursively();
    }
}

QString EngineController::stagedAncestor(const QString &file, const QString &stagedRoot) {
    const QDir root(stagedRoot);
    const QString rootAbs = root.absolutePath();
    QDir d = QFileInfo(file).dir();
    while (!d.isRoot()) {
        const QString parentAbs = QFileInfo(d.absolutePath()).dir().absolutePath();
        if (parentAbs == rootAbs)
            return d.absolutePath();
        d = QFileInfo(d.absolutePath()).dir();
    }
    return QString();
}

void EngineController::moveDictionary(int from, int to) {
    if (!m_ready) return;
    QFuture<int> f = QtConcurrent::run([from, to]{
        return gd_move_dict(from, to);
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] move dict" << rc;
        if (rc == 0) refreshDictionaries();
        else setLastError(QStringLiteral("move_dict failed (rc=%1)").arg(rc));
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::refreshGroups() {
    if (!m_ready) {
        qInfo() << "[aurelex] refreshGroups skipped: not ready";
        return;
    }
    qInfo() << "[aurelex] refreshGroups firing";
    QFuture<QPair<QVariantList, int>> f = QtConcurrent::run([]{
        QVariantList list;
        const int n = gd_group_count();
        list.reserve(n);
        std::vector<char> name(256);
        for (int i = 0; i < n; ++i) {
            int idOut = 0;
            int dictCountOut = 0;
            const int rn = gd_group_info(i, &idOut, name.data(),
                                         static_cast<int>(name.size()),
                                         &dictCountOut);
            if (rn != 0) continue;
            QVariantMap m;
            m.insert("id", idOut);
            m.insert("name", QString::fromLocal8Bit(name.data()));
            m.insert("dictCount", dictCountOut);
            list.append(m);
        }
        int active = 0;
        gd_group_active(&active);
        return QPair<QVariantList, int>(list, active);
    });
    auto *w = new QFutureWatcher<QPair<QVariantList, int>>(this);
    connect(w, &QFutureWatcher<QPair<QVariantList, int>>::finished, this, [this, w]{
        const QPair<QVariantList, int> result = w->result();
        setGroups(result.first);
        setActiveGroupId(result.second);
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::createGroup(const QString &name) {
    if (!m_ready) return;
    QFuture<QPair<int, int>> f = QtConcurrent::run([name]{
        int idOut = 0;
        const int rc = gd_group_create(name.toLocal8Bit().constData(), &idOut);
        return QPair<int, int>(rc, idOut);
    });
    auto *w = new QFutureWatcher<QPair<int, int>>(this);
    connect(w, &QFutureWatcher<QPair<int, int>>::finished, this, [this, name, w]{
        const QPair<int, int> result = w->result();
        const int rc = result.first;
        const int newId = result.second;
        qInfo() << "[aurelex] createGroup rc=" << rc << " id=" << newId;
        if (rc == -2) {
            emit groupNameTaken(name);
        } else if (rc != 0) {
            setLastError(QStringLiteral("group_create failed (rc=%1)").arg(rc));
        } else {
            refreshGroups();
            emit groupCreated(newId, name);
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::renameGroup(int groupId, const QString &newName) {
    if (!m_ready) return;
    QFuture<int> f = QtConcurrent::run([groupId, newName]{
        return gd_group_rename(groupId, newName.toLocal8Bit().constData());
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, newName, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] renameGroup" << rc;
        if (rc == -2) {
            emit groupNameTaken(newName);
        } else if (rc == 0) {
            refreshGroups();
        } else {
            setLastError(QStringLiteral("group_rename failed (rc=%1)").arg(rc));
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::deleteGroup(int groupId) {
    if (!m_ready) { qInfo() << "[aurelex] deleteGroup skipped: not ready"; return; }
    qInfo() << "[aurelex] deleteGroup requested id=" << groupId;
    QFuture<int> f = QtConcurrent::run([groupId]{
        return gd_group_delete(groupId);
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, w, groupId]{
        const int rc = w->result();
        qInfo() << "[aurelex] deleteGroup done rc=" << rc;
        if (rc == 0) {
            // Repair history/favorites entries that pointed at the group just
            // deleted, so the panel is truthful now rather than after a restart.
            // The id is passed explicitly: m_groups does not lose it until
            // refreshGroups resolves asynchronously.
            repointStaleGroupEntries(groupId);
            refreshGroups();
        } else {
            setLastError(QStringLiteral("group_delete failed (rc=%1)").arg(rc));
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::setActiveGroup(int groupId) {
    if (!m_ready) return;
    QFuture<QPair<int, int>> f = QtConcurrent::run([groupId]{
        const int rc = gd_group_set_active(groupId);
        int active = 0;
        gd_group_active(&active);
        return QPair<int, int>(rc, active);
    });
    auto *w = new QFutureWatcher<QPair<int, int>>(this);
    connect(w, &QFutureWatcher<QPair<int, int>>::finished, this, [this, w]{
        const QPair<int, int> result = w->result();
        qInfo() << "[aurelex] setActiveGroup" << result.first;
        if (result.first == 0) {
            setActiveGroupId(result.second);
        } else {
            setLastError(QStringLiteral("group_set_active failed (rc=%1)").arg(result.first));
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::groupDicts(int groupId) {
    if (!m_ready) return;
    QFuture<QVariantList> f = QtConcurrent::run([groupId]{
        QVariantList list;
        const int n = gd_dict_count();
        if (n < 0) return list;
        std::vector<int> members(static_cast<size_t>(n + 1));
        int memberCount = 0;
        const int rc = gd_group_dicts(groupId, members.data(), n + 1);
        if (rc >= 0) memberCount = rc;
        for (int i = 0; i < n; ++i) {
            const DictInfoAtIndex info = readDictInfoAt(i);
            if (!info.ok) continue;
            QVariantMap m;
            m.insert("index", i);
            m.insert("name", info.name);
            m.insert("source", info.source);
            QVector<int> idx; // position within the group's ordered membership
            for (int k = 0; k < memberCount; ++k) if (members[k] == i) idx << k;
            m.insert("member", !idx.isEmpty());
            m.insert("memberIndex", idx.isEmpty() ? -1 : idx.first());
            list.append(m);
        }
        return list;
    });
    auto *w = new QFutureWatcher<QVariantList>(this);
    connect(w, &QFutureWatcher<QVariantList>::finished, this, [this, groupId, w]{
        emit groupDictsReady(groupId, w->result());
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::groupAddDict(int groupId, int dictIndex) {
    if (!m_ready) return;
    QFuture<int> f = QtConcurrent::run([groupId, dictIndex]{
        return gd_group_add_dict(groupId, dictIndex);
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, groupId, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] groupAddDict group=" << groupId << "rc=" << rc;
        if (rc != 0) {
            setLastError(QStringLiteral("group_add_dict failed (rc=%1)").arg(rc));
        } else {
            emit groupMembersChanged();
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::groupRemoveDict(int groupId, int dictIndex) {
    if (!m_ready) return;
    QFuture<int> f = QtConcurrent::run([groupId, dictIndex]{
        return gd_group_remove_dict(groupId, dictIndex);
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, groupId, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] groupRemoveDict group=" << groupId << "rc=" << rc;
        if (rc != 0) {
            setLastError(QStringLiteral("group_remove_dict failed (rc=%1)").arg(rc));
        } else {
            emit groupMembersChanged();
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::groupMoveDict(int groupId, int from, int to) {
    if (!m_ready) return;
    QFuture<int> f = QtConcurrent::run([groupId, from, to]{
        return gd_group_move_dict(groupId, from, to);
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, groupId, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] groupMoveDict rc=" << rc;
        if (rc != 0) {
            setLastError(QStringLiteral("group_move_dict failed (rc=%1)").arg(rc));
        } else {
            emit groupMembersChanged();
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

QString EngineController::rewriteArticleUrls(const QString &html) const {
    if (!m_articleServer || !m_articleServer->isRunning()) {
        return html;
    }
    const QString base = m_articleServer->baseUrl(); // e.g. http://127.0.0.1:54321
    QString out = html;
    // bres/gdau/gdlookup MUST be replaced before the bare qrc:// (they share
    // no syntax, but keep order logical). Android's WebView cannot navigate to
    // unknown schemes, so gdlookup://localhost/<word> anchors are ALSO
    // rewritten to loopback http — the QML click-probe (main.qml) catches the
    // click on the http URL and dispatches to engine.lookup().
    out.replace(QStringLiteral("gdlookup://localhost/"), base + QStringLiteral("/gdlookup/"));
    // The kaikki converter's fixed sense-marker icons (scripts/kaikki-to-dsl.py,
    // scripts/assets/kaikki-tag-icons) are bundled into the APK as
    // assets/icons/gd_tag_*.svg as well as into each dictionary's resource
    // bundle. Serve them from the static asset route — the same route that
    // makes qrc:///icons/playsound.svg paint instantly — instead of the engine's
    // bres:// resource pipeline, which queues on the two reader slots and unzips
    // the dictionary before answering, so the icons painted noticeably after the
    // rest of the article. Only the four known names are rewritten; any other
    // dictionary's image keeps its bres:// route. Must run before the bare
    // bres:// replacement below.
    out.replace(
        QRegularExpression(QStringLiteral(
            R"(bres://[^/]+/(gd_tag_(?:countable|uncountable|initialism|obsolete)\.svg))")),
        base + QStringLiteral("/icons/\\1"));
    out.replace(QStringLiteral("bres://"), base + QStringLiteral("/bres/"));
    out.replace(QStringLiteral("gdau://"), base + QStringLiteral("/gdau/"));
    out.replace(QStringLiteral("qrc:///"), base + QStringLiteral("/"));
    // Strip desktop-only / dead-weight script ELEMENTS the engine emits but that
    // serve nothing on Android (they used to 404 and stall the page load):
    //   jquery / gd-custom / gd-builtin   -> desktop link/active-article bridge
    //   qtwebchannel + init script         -> Qt WebChannel (not used on mobile)
    //   iframeResizer / mark               -> desktop iframe + in-page search
    // Keep darkreader.js + the stylesheets, which now load from assets and
    // provide dark mode + proper article CSS.
    // gd-builtin.js stays stripped even though it also defines
    // gdExpandOptPart (the DSL optional-parts expander handler): the rest of
    // that file is the desktop bridge, and its article-collapse paths throw on
    // Android. The one function we need is re-implemented in
    // assets/scripts/gd-article-controls.js and injected below.
    const QStringList stripScripts = {
        QStringLiteral("/scripts/jquery-3.6.0.slim.min.js"),
        QStringLiteral("/scripts/gd-custom.js"),
        QStringLiteral("/scripts/gd-builtin.js"),
        QStringLiteral("/scripts/iframe-defer.js"),
        QStringLiteral("/scripts/iframeResizer.min.js"),
        QStringLiteral("/scripts/iframeResizer.contentWindow.min.js"),
        QStringLiteral("/scripts/mark.min.js"),
        QStringLiteral("/scripts/mark.js"),
        QStringLiteral("/qtwebchannel/qwebchannel.js"),
    };
    // Match the whole <script src="..."></script> element (src may be the
    // original qrc:/// URL or the rewritten loopback URL). Removing the whole
    // element avoids leaving `<script src=""></script>`, whose empty src
    // resolves to the article page itself and triggers a reload/parse error.
    for (const QString &p : stripScripts) {
        QRegularExpression scriptTag(
            QStringLiteral(R"(<script[^>]*\bsrc="[^"]*%1"[^>]*>\s*</script>)")
                .arg(QRegularExpression::escape(p)),
            QRegularExpression::DotMatchesEverythingOption);
        out.remove(scriptTag);
    }
    // Strip the jQuery noConflict stub and the Qt WebChannel init script body
    // (emitted as `function gd_init_QtWebChannel(){ ... new QWebChannel(...) }`,
    // which throws `QWebChannel is not defined` on Android).
    out.remove(QRegularExpression(
        QStringLiteral(R"(<script>\s*jQuery\.noConflict\(\);\s*</script>)")));
    out.remove(QRegularExpression(
        QStringLiteral(R"(<script>\s*function\s+gd_init_QtWebChannel.*?</script>)"),
        QRegularExpression::DotMatchesEverythingOption));
    // Some extended article templates ship their own viewport meta; strip it so
    // the mobile fit-width meta injected below is the only one the WebView sees.
    out.remove(QRegularExpression(
        QStringLiteral(R"(<meta\b[^>]*\bname\s*=\s*["']viewport["'][^>]*>)"),
        QRegularExpression::CaseInsensitiveOption));

    // --- unified dark-mode injection ---
    // The engine bakes darkreader.js + a one-shot enable() into the article HTML
    // ONLY when dark mode is on at generation time (and only for the "modern"
    // style). That couples the page's appearance to generation state, so a dark
    // toggle would otherwise need a full re-lookup + reload (slow, resets scroll).
    // Strip the engine's dark block entirely and inject a fixed controller
    // (darkreader.js + fetchShim + gdSetDarkMode) with the mode baked in. QML
    // then flips the OPEN article in place via gdSetDarkMode() — instant.
    out.remove(QRegularExpression(
        QStringLiteral(R"(<script[^>]*\bsrc="[^"]*(?:scripts/)?darkreader\.js"[^>]*>\s*</script>)"),
        QRegularExpression::DotMatchesEverythingOption));
    out.remove(QRegularExpression(
        QStringLiteral(R"(<script[^>]*>[\s\S]*?DarkReader\.[\s\S]*?</script>)"),
        QRegularExpression::DotMatchesEverythingOption));
    out.remove(QRegularExpression(
        QStringLiteral(R"(<style[^>]*>[\s\S]*?\.gdarticlebody\s+img[\s\S]*?</style>)"),
        QRegularExpression::DotMatchesEverythingOption));

    // Always-on controller. darkreader.js is bundled in APK assets/scripts, so
    // the loopback article server serves it; article-style-darkmode.css is a
    // bare .css in assets/stylesheets (the server prefixes "stylesheets/").
    // A plain-background override is injected too: the "modern" style renders
    // each dictionary entry as a bordered white card (.gdarticle), which reads
    // as a light-gray frame on the phone. Neutralize the card so article text
    // sits directly on the pane's plain background. The base canvas uses a CSS
    // variable that gdSetDarkMode() flips, so the whole WebView background
    // matches the app theme on a live dark/light switch (a fully-transparent
    // html would show the native WebView's own white underneath).
    //
    // The article canvas is the app's own background color, so no seam shows
    // where the article meets the chrome around it. These are Qt 6.6's Material
    // `backgroundColorLight` / `backgroundColorDark` — the same pair Qt resolves
    // for Material.background, which main.qml aliases as uiBg and
    // app/android/res/values{,-night}/colors.xml carries for the starting
    // window. They were #ffffff / #242526, which matched neither theme and left
    // the article a shade off the pane in both (pin-article-canvas-against-dark-reader).
    // main.qml keeps the same pair as root.uiBgHex() — change both together.
    const QString canvasBgLight = QStringLiteral("#fffbfe");
    const QString canvasBgDark = QStringLiteral("#1c1b1f");
    // Baked into the var() fallback rather than left to the injected controller:
    // the document's first paint happens before any script runs, and the
    // controller's own initial call is a no-op (the mode is already baked in),
    // so the fallback is what paints the first frame in BOTH themes. Baking the
    // light value unconditionally would flash white on a dark cold load.
    const QString canvasBg = m_darkMode ? canvasBgDark : canvasBgLight;
    const QString plainCss = QStringLiteral(
        R"(<style>
/* Paints the article's first frame before any script runs. A stylesheet rule
   cannot hold the canvas once Dark Reader is on (its override is a layered
   !important, which outranks an unlayered one), so this is superseded on the
   live document by an inline !important declaration set from the controller
   below. Baked per render so a dark cold load never flashes the light value. */
html, body { background: %1 !important; }
/* Clear the inline nav toolbar: the WebView surface starts right under it, and
   without this the first line of the article (the dictionary-name heading) can
   tuck under the toolbar's buttons. */
body { padding-top: 8px !important; }
/* Reserve a right-hand gutter for the floating scrollbar. Android's WebView
   uses overlay scrollbars, which are drawn OVER the content (and which
   scrollbar-gutter cannot reserve space in — upstream's `scrollbar-gutter:
   stable` on html is a no-op here), so without this the article's text runs
   under the thumb while scrolling. This is also what the stylesheet's own
   2em padding on .gdarticle used to provide before the card frame was
   neutralized below. */
body { padding-right: 12px !important; }
.gdarticle { border: none !important; border-radius: 0 !important;
             background: transparent !important; box-shadow: none !important;
             padding: 0 !important;
             margin-bottom: 0.6em !important; }
/* Touch target for the DSL optional-parts expander. The bundled stylesheet sizes
   .hidden_expand_opt at 16px (desktop-pointer sized); leave the glyph that size
   and only grow the tappable box with padding, pulled back by an equal negative
   margin so the layout does not shift. Injected rather than editing the
   verbatim upstream stylesheet. */
img.hidden_expand_opt { padding: 12px; margin: -12px !important; }
/* Inline sense-marker icons emitted by kaikki-to-dsl dictionaries (see
   scripts/assets/kaikki-tag-icons). Scoped to the gd_tag_ filename so no other
   dictionary's images are affected: text-height, aligned to the text, and with
   no background box. Both width and height are pinned to 1.1em so the box is
   reserved before the SVG has loaded — an image with only a height takes no
   horizontal space until its intrinsic size is known, which reflows the gloss
   when it arrives late. The transparent background must out-specify the
   dark-mode .gdarticlebody img{background:white} rule, which ties with a bare
   img[src*=...] and is injected later, hence the .gdarticlebody prefix plus
   !important. */
.gdarticlebody img[src*="gd_tag_"] { width: 1.1em; height: 1.1em;
                                    vertical-align: -0.15em;
                                    background: transparent !important; }
/* In-article find highlights (article-find.js). Distinct, high-contrast colors
   in both themes. font/line-height are forced to inherit and padding/border are
   zero so a marked run has exactly the surrounding text's metrics and wrapping a
   match never reflows the line. Verify the current-versus-other distinction
   survives Dark Reader on device. */
mark.gd-find-mark { background: #ffe082 !important; color: #202124 !important;
                    font: inherit !important; line-height: inherit !important;
                    padding: 0 !important; border: 0 !important;
                    border-radius: 2px; }
mark.gd-find-mark[data-gd-find-current] { background: #e65100 !important;
                    color: #ffffff !important; }
</style>
)").arg(canvasBg);
    const QString darkInit = m_darkMode ? QStringLiteral("1") : QStringLiteral("0");
    // gd-article-controls.js defines gdExpandOptPart, the handler the engine's
    // DSL optional-parts expander binds to. It replaces the stripped
    // gd-builtin.js for that one function (see the stripScripts list above);
    // the handler is defined at load time, so this tag must come before any
    // article body that can be clicked.
    const QString optCtrl = QStringLiteral(
        R"(<script src="%1/scripts/gd-article-controls.js"></script>
)").arg(base);
    // In-article find: mark.min.js (vendored in APK assets/scripts; the engine's
    // own qrc mark tag stays in the strip-list above as dead desktop weight) plus
    // the article-find.js controller. QML drives them via runJavaScript —
    // gdFindSet/gdFindNext/gdFindPrev/gdFindClear. See
    // app/android/assets/scripts/README.md.
    const QString findCtrl = QStringLiteral(
        R"(<script src="%1/scripts/mark.min.js"></script>
<script src="%1/scripts/article-find.js"></script>
)").arg(base);
    const QString darkCtrl = QStringLiteral(
        R"(
<script src="%1/scripts/darkreader.js"></script>
<script>
window.__gdDarkMode=%2;
(function(){
  function fetchShim(src){
    if(src.indexOf('gdlookup://')===0){console.error('Dark Reader discovered unexpected URL',src);return Promise.resolve({blob:function(){return new Blob();}});}
    if(src.indexOf('qrcx://')===0||src.indexOf('qrc://')===0||src.indexOf('bres://')===0||src.indexOf('gico://')===0){
      return new Promise(function(resolve){
        var img=document.createElement('img');
        img.addEventListener('load',function(){
          var canvas=document.createElement('canvas');canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
          var ctx=canvas.getContext('2d');ctx.drawImage(img,0,0);
          canvas.toBlob(function(blob){resolve({blob:function(){return blob;}});});
        },false);
        img.src=src;
      });
    }
    return fetch(src);
  }
  DarkReader.setFetchMethod(fetchShim);
  var cssId='gd-darkmode-css', imgStyleId='gd-dark-img-style';
  /* The canvas is asserted as an inline !important declaration, not by the
     stylesheet rule above. Dark Reader overrides html/body's background from
     inside a cascade @layer, and a layered !important outranks an unlayered
     one, so the sheet rule loses and the article came out a grey shade
     (#242525) rather than the app's #1c1b1f. An inline !important declaration
     sits outside the layer system and wins. Both elements are set: once html
     has a background, body's no longer propagates to the canvas. */
  function gdSetCanvasBg(bg){
    if(document.documentElement)document.documentElement.style.setProperty('background-color',bg,'important');
    if(document.body)document.body.style.setProperty('background-color',bg,'important');
  }
  window.gdSetDarkMode=function(v){
    v=!!v;
    gdSetCanvasBg(v?'%3':'%4');
    if(v===window.__gdDarkMode)return;
    window.__gdDarkMode=v;
    var head=document.head||document.documentElement;
    if(v){
      var l=document.getElementById(cssId);
      if(!l){l=document.createElement('link');l.id=cssId;l.rel='stylesheet';l.href='%1/article-style-darkmode.css';head.appendChild(l);}
      var st=document.getElementById(imgStyleId);
      if(!st){st=document.createElement('style');st.id=imgStyleId;st.textContent='.gdarticlebody img{background:white !important;}';head.appendChild(st);}
      DarkReader.enable({brightness:100,contrast:90,sepia:10});
    }else{
      var l=document.getElementById(cssId);if(l&&l.parentNode)l.parentNode.removeChild(l);
      var st=document.getElementById(imgStyleId);if(st&&st.parentNode)st.parentNode.removeChild(st);
      DarkReader.disable();
    }
    /* Open find highlights are inline-styled; re-color them for the new mode. */
    try{if(window.gdFindRestyle)window.gdFindRestyle();}catch(e){}
  };
  if(window.__gdDarkMode)window.gdSetDarkMode(1);
  /* This controller runs from <head>, before document.body exists, so the call
     above could only reach <html>. Re-assert once the document is parsed, which
     also lets Dark Reader's late style injection settle first. */
  function gdAssertCanvas(){ gdSetCanvasBg(window.__gdDarkMode?'%3':'%4'); }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',gdAssertCanvas);
  else gdAssertCanvas();
})();
</script>
)").arg(base).arg(darkInit).arg(canvasBgDark).arg(canvasBgLight);

    // --- mobile reflow + article zoom ---
    // Fit the article to the device-width viewport and kill native pinch page
    // scaling (pinch on the fixed-width article is what produced the wide page /
    // horizontal slider). Zoom is a CSS root font-size multiplied by a baked
    // default here; the live gdSetZoom(percent) controller reflows the OPEN
    // article in place (mirror of gdSetDarkMode above).
    const QString zoomCtrl = QStringLiteral(
        R"(
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
html { font-size: %1%; max-width: 100%; overflow-x: hidden !important; }
body { max-width: 100%; overflow-x: hidden !important; }
.gdarticlebody, .gdarticle, .gdarticles { max-width: 100% !important; overflow-wrap: break-word !important; }
img, table { max-width: 100% !important; height: auto; }
.gdarticlebody pre, .gdarticlebody code { white-space: pre-wrap; overflow-wrap: break-word; }
.gdarticlebody a { overflow-wrap: break-word; }
</style>
<script>
window.__gdZoom=%1;
window.gdSetZoom=function(p){
  p=+p||100;
  if(window.__gdZoom===p)return;
  window.__gdZoom=p;
  if(document.documentElement)document.documentElement.style.fontSize=p+'%';
};
if(window.__gdZoom!==100)window.gdSetZoom(window.__gdZoom);
</script>
)").arg(m_articleZoom, 0, 'f', 0);

    const int headEnd = out.indexOf(QStringLiteral("</head>"));
    if (headEnd >= 0)
        out.insert(headEnd, zoomCtrl + plainCss + optCtrl + findCtrl + darkCtrl);
    else
        out.append(zoomCtrl + plainCss + optCtrl + darkCtrl);
    return out;
}

QString EngineController::articleBaseUrl() const {
    return (m_articleServer && m_articleServer->isRunning()) ? m_articleServer->baseUrl() : QString();
}

int EngineController::systemInsetTop() const
{
#if defined(Q_OS_ANDROID)
    return QJniObject::callStaticMethod<jint>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "getSystemInsetTop",
        "()I");
#else
    return 0;
#endif
}

int EngineController::systemInsetBottom() const
{
#if defined(Q_OS_ANDROID)
    return QJniObject::callStaticMethod<jint>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "getSystemInsetBottom",
        "()I");
#else
    return 0;
#endif
}

int EngineController::systemInsetLeft() const
{
#if defined(Q_OS_ANDROID)
    return QJniObject::callStaticMethod<jint>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "getSystemInsetLeft",
        "()I");
#else
    return 0;
#endif
}

int EngineController::systemInsetRight() const
{
#if defined(Q_OS_ANDROID)
    return QJniObject::callStaticMethod<jint>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "getSystemInsetRight",
        "()I");
#else
    return 0;
#endif
}

void EngineController::playAudio(const QString &url) {
#if defined(Q_OS_ANDROID)
    // JNI passthrough to AurelexActivity.playAudio(String) — Android's
    // MediaPlayer plays the loopback URL so the WebView keeps the article.
    const QJniObject javaUrl = QJniObject::fromString(url);
    QJniObject::callStaticMethod<void>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "playAudio",
        "(Ljava/lang/String;)V",
        javaUrl.object<jstring>());
#else
    Q_UNUSED(url);
#endif
}

void EngineController::stopAudio() {
#if defined(Q_OS_ANDROID)
    QJniObject::callStaticMethod<void>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "stopAudio",
        "()V");
#endif
}

QString EngineController::articleCacheKey(const QString &word) const {
    // Article HTML is dark-mode agnostic (rewriteArticleUrls always injects the
    // dark controller), so the key needs word + active group only.
    return word + QLatin1Char('\x1f') + QString::number(m_activeGroupId);
}

void EngineController::cacheArticle(const QString &key, const QString &html) {
    if (key.isEmpty() || html.isEmpty()) return;
    if (!m_articleCache.contains(key)) {
        m_articleCacheOrder.append(key);
        if (m_articleCacheOrder.size() > kArticleCacheMax) {
            const QString oldest = m_articleCacheOrder.takeFirst();
            m_articleCache.remove(oldest);
        }
    }
    m_articleCache.insert(key, html);
}

void EngineController::clearArticleCache() {
    m_articleCache.clear();
    m_articleCacheOrder.clear();
}

// Subordinate background warm-up: prefetch `word`'s article into the cache so
// the next lookup of it (suggestion tap / Enter) hits the cache and renders
// without a gd_lookup wait. Never delays user work: the job bails out (before
// touching the engine) if a newer suggest superseded it or the user already
// issued a lookup — so a tap's lookup is served at most one in-flight call
// behind, and queued prefetches can't pile up in front of interactive work.
void EngineController::prefetchArticle(const QString &word) {
    if (word.trimmed().isEmpty()) return;
    const QString key = articleCacheKey(word);
    if (m_articleCache.contains(key)) return;
    const QByteArray utf = word.toUtf8();
    const int sgen = m_suggestGeneration.load();
    const int lgen = m_lookupGeneration.load();
    QFuture<QString> f = QtConcurrent::run(&m_enginePool, [this, utf, sgen, lgen]{
        if (sgen != m_suggestGeneration.load()) return QString(); // a newer suggest superseded this
        if (lgen != m_lookupGeneration.load()) return QString();  // the user already asked for something
        std::vector<char> buf(1 << 20);
        const int sz = gd_lookup(utf.constData(), buf.data(), static_cast<int>(buf.size()));
        if (sz <= 0) return QString();
        return QString::fromUtf8(buf.data(), sz);
    });
    auto *w = new QFutureWatcher<QString>(this);
    connect(w, &QFutureWatcher<QString>::finished, this, [this, key, sgen, lgen, w]{
        w->deleteLater();
        if (m_articleCache.contains(key)) return;
        if (sgen != m_suggestGeneration.load() || lgen != m_lookupGeneration.load()) return;
        const QString html = w->result();
        if (!html.isEmpty()) cacheArticle(key, html);
    });
    w->setFuture(f);
}

void EngineController::lookup(const QString &word) {
    // Last request wins: a newer lookup supersedes any queued/older one.
    const int gen = ++m_lookupGeneration;
    const QString key = articleCacheKey(word);
    const auto it = m_articleCache.constFind(key);
    if (it != m_articleCache.constEnd()) {
        // Cache hit: render immediately without a gd_lookup worker round-trip.
        m_articleCacheOrder.removeAll(key);
        m_articleCacheOrder.append(key);
        recordHistory(word);
        emit articleLoaded(word, it.value());
        return;
    }
    QElapsedTimer wall; wall.start();
    QFuture<QString> f = QtConcurrent::run(&m_enginePool, [this, word, key, gen]{
        if (gen != m_lookupGeneration.load()) return QString(); // superseded; don't touch the engine
        std::vector<char> buf(1 << 20);
        const int sz = gd_lookup(word.toLocal8Bit().constData(),
                                 buf.data(), static_cast<int>(buf.size()));
        if (sz <= 0) return QString();
        return QString::fromUtf8(buf.data(), sz);
    });
    auto *w = new QFutureWatcher<QString>(this);
    connect(w, &QFutureWatcher<QString>::finished, this, [this, word, key, gen, wall, w]{
        const bool stale = gen != m_lookupGeneration.load();
        const QString html = w->result();
        // Fast lookups log nothing (the diag logger does file I/O); only slow
        // or stale ones are worth a line when hunting a latency bug.
        if (stale || wall.elapsed() >= 20)
            qInfo() << "[aurelex] lookup done:" << word
                    << (stale ? "(stale)" : (html.isEmpty() ? "not-found" : "loaded"))
                    << "enqueue->ready:" << wall.elapsed() << "ms";
        if (!stale) {
            if (html.isEmpty()) {
                emit articleNotFound(word);
            } else {
                cacheArticle(key, html);
                recordHistory(word);
                emit articleLoaded(word, html);
            }
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::lookupInGroup(const QString &word, int groupId) {
    const int gen = ++m_lookupGeneration;
    QFuture<QString> f = QtConcurrent::run(&m_enginePool, [this, word, groupId, gen]{
        if (gen != m_lookupGeneration.load()) return QString(); // superseded; don't touch the engine
        std::vector<char> buf(1 << 20);
        const int sz = gd_lookup_in_group(word.toLocal8Bit().constData(), groupId,
                                          buf.data(), static_cast<int>(buf.size()));
        if (sz <= 0) return QString();
        return QString::fromUtf8(buf.data(), sz);
    });
    auto *w = new QFutureWatcher<QString>(this);
    connect(w, &QFutureWatcher<QString>::finished, this, [this, word, gen, w]{
        const bool stale = gen != m_lookupGeneration.load();
        const QString html = w->result();
        if (!stale) {
            if (html.isEmpty()) {
                emit articleNotFound(word);
            } else {
                recordHistory(word);
                emit articleLoaded(word, html);
            }
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

// Group-restoring lookup used by history/favorites taps and Back/Forward. If
// `groupId` still exists, make it the active group and look up in it (so the
// Search scope + history recording agree); otherwise fall back to "All" (0).
void EngineController::lookupInGroupWithSwitch(const QString &word, int groupId)
{
    const int gen = ++m_lookupGeneration;
    const int target = groupExists(groupId) ? groupId : 0;
    QFuture<QPair<int, QString>> f = QtConcurrent::run(&m_enginePool, [this, word, target, gen]{
        if (gen != m_lookupGeneration.load()) return QPair<int, QString>(0, QString()); // superseded
        int rc = gd_group_set_active(target);
        int active = 0;
        if (rc == 0) gd_group_active(&active);
        std::vector<char> buf(1 << 20);
        const int sz = gd_lookup_in_group(word.toLocal8Bit().constData(), target,
                                          buf.data(), static_cast<int>(buf.size()));
        QString html;
        if (sz > 0) html = QString::fromUtf8(buf.data(), sz);
        return QPair<int, QString>(active, html);
    });
    auto *w = new QFutureWatcher<QPair<int, QString>>(this);
    connect(w, &QFutureWatcher<QPair<int, QString>>::finished, this, [this, word, gen, w]{
        if (gen != m_lookupGeneration.load()) {
            w->deleteLater();
            return;
        }
        const QPair<int, QString> result = w->result();
        setActiveGroupId(result.first);
        const QString html = result.second;
        if (html.isEmpty()) {
            emit articleNotFound(word);
        } else {
            recordHistory(word);
            emit articleLoaded(word, html);
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::suggest(const QString &prefix) {
    qInfo() << "[aurelex] suggest firing:" << prefix;
    // Only the latest request may reach the engine (and emit): while the user
    // keeps typing (or the IME rewrites composing text), older requests are
    // dropped before they even start, and any older result that still lands
    // late is ignored below. Last request wins.
    const int gen = ++m_suggestGeneration;
    QElapsedTimer wall; wall.start();
    QFuture<QStringList> f = QtConcurrent::run(&m_enginePool, [this, prefix, gen]{
        if (gen != m_suggestGeneration.load()) return QStringList(); // superseded; don't touch the engine
        std::vector<char> buf(1 << 16);
        const int n = gd_suggest(prefix.toLocal8Bit().constData(),
                                  buf.data(), static_cast<int>(buf.size()));
        if (n < 0) return QStringList();
        return QString::fromLocal8Bit(buf.data(), strlen(buf.data())).split('\n', Qt::SkipEmptyParts);
    });
    auto *w = new QFutureWatcher<QStringList>(this);
    connect(w, &QFutureWatcher<QStringList>::finished, this, [this, prefix, gen, wall, w]{
        if (gen != m_suggestGeneration) {
            qInfo() << "[aurelex] suggest stale, dropped:" << prefix;
            w->deleteLater();
            return;
        }
        // Fast suggests log nothing (diag logger does file I/O); only slow ones
        // matter when hunting the delay.
        if (wall.elapsed() >= 20)
            qInfo() << "[aurelex] suggest ready:" << prefix
                    << "count:" << w->result().size()
                    << "enqueue->ready:" << wall.elapsed() << "ms";
        emit suggestionsReady(prefix, w->result());
        // Prefetch the top candidate — the likely tap target — so the first
        // suggestion tap / Enter is near-instant (cache hit instead of a fresh
        // gd_lookup). Prefetching the raw prefix would be a useless not-found
        // lookup; this warms the headword the dropdown is about to show.
        if (!w->result().isEmpty()) prefetchArticle(w->result().first());
        w->deleteLater();
    });
    w->setFuture(f);
}
int EngineController::ftsIndexState(int dictIndex) const
{
    if (!m_ready) return -1;
    int out = 0;
    return gd_fts_index_state(dictIndex, &out) == 0 ? out : -1;
}

QVariantList EngineController::ftsIndexStates() const
{
    QVariantList out;
    if (!m_ready) return out;
    const int n = m_dictCount;
    for (int i = 0; i < n; ++i) {
        int state = 1;
        const int rc = gd_fts_index_state(i, &state);
        if (rc != 0) state = -1;
        QVariantMap m;
        m.insert("index", i);
        QString name;
        for (const QVariant &v : m_dictionaries) {
            const QVariantMap mm = v.toMap();
            if (mm.value("index", -1).toInt() == i) { name = mm.value("name").toString(); break; }
        }
        if (name.isEmpty()) {
            std::vector<char> buf(kDictInfoBufferSize);
            if (gd_dict_info(i, buf.data(), static_cast<int>(buf.size()), nullptr, 0) == 0) {
                name = QString::fromLocal8Bit(buf.data());
            }
        }
        m.insert("name", name);
        m.insert("state", state);
        out.append(m);
    }
    return out;
}

void EngineController::ftsIndex(int dictIndex)
{
    if (!m_ready) return;
    if (m_buildingFts) return;
    setBuildingFts(true);
    QFuture<int> f = QtConcurrent::run([dictIndex]{
        return gd_fts_index(dictIndex);
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, dictIndex, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] ftsIndex dict=" << dictIndex << " rc=" << rc;
        setBuildingFts(false);
        emit ftsIndexChanged(dictIndex);
        w->deleteLater();
    });
    w->setFuture(f);
}

QVariantList EngineController::ftsSearch(const QString &query, int mode, int groupId)
{
    if (!m_ready) return QVariantList();
    if (query.isEmpty()) return QVariantList();
    // The caller selects the mode (control-state-and-fts-whole-words): whole
    // words submits SearchMode::WholeWords (0), which parses a folded term as an
    // exact term; prefix search submits Wildcards (2). In Xapian's wildcard mode
    // a term without a trailing `*` would otherwise match exactly, so for the
    // prefix mode we append `*` to terms lacking one. Whole words deliberately
    // does NOT get that suffix: it must not expand to similar terms (the old
    // `vire` -> `vaudeville` bug, where a bare term in wildcard mode parsed as
    // `WILDCARD SYNONYM`).
    QString norm = query;
    if (mode == 2) {
        QStringList parts;
        const QStringList toks = query.split(QLatin1Char(' '), Qt::SkipEmptyParts);
        for (const QString &t : toks) {
            QString term = t;
            if (!term.endsWith(QLatin1Char('*')) && !term.endsWith(QLatin1Char('?')))
                term += QLatin1Char('*');
            parts.append(term);
        }
        norm = parts.join(QLatin1Char(' '));
    }
    qInfo() << "[aurelex] ftsSearch query='" << query << "' norm='" << norm
            << "' mode=" << mode << " group=" << groupId;
    runFtsSearch(norm, mode, groupId, query);
    return QVariantList();
}

void EngineController::runFtsSearch(const QString &norm, int mode, int groupId,
                                    const QString &displayQuery)
{
    if (!m_ready) return;
    QFuture<QVariantList> f = QtConcurrent::run([norm, mode, groupId]{
        std::vector<char> buf(1 << 20);
        const int n = gd_fts_search(norm.toLocal8Bit().constData(), mode, groupId,
                                    buf.data(), static_cast<int>(buf.size()));
        qInfo() << "[aurelex]   gd_fts_search rc=" << n;
        if (n < 0) return QVariantList();
        const QString raw = QString::fromUtf8(buf.data());
        qInfo() << "[aurelex]   raw bytes=" << raw.size();
        QVariantList list;
        const QStringList lines = raw.split('\n', Qt::SkipEmptyParts);
        for (const QString &line : lines) {
            const int tab = line.indexOf('\t');
            QVariantMap row;
            if (tab < 0) {
                row.insert("headword", line);
                row.insert("dictName", QString());
            } else {
                row.insert("headword", line.left(tab));
                row.insert("dictName", line.mid(tab + 1));
            }
            list.append(row);
        }
        return list;
    });
    auto *w = new QFutureWatcher<QVariantList>(this);
    connect(w, &QFutureWatcher<QVariantList>::finished, this, [this, displayQuery, w]{
        emit ftsSearchReady(displayQuery, w->result());
        w->deleteLater();
    });
    w->setFuture(f);

    // On-demand builds (D5): if the scoped group has dictionaries that lack an
    // index, build them through the same single worker and re-run this query
    // once they land. Results from already-indexed dictionaries are emitted
    // above immediately, so the user sees partial results at once.
    QSet<QString> failedSnapshot;
    {
        QMutexLocker lock(&m_ftsQueueMutex);
        failedSnapshot = m_ftsBuildFailed;
    }
    QFuture<QStringList> g = QtConcurrent::run([groupId, failedSnapshot]{
        QStringList ids;
        const int cap = gd_dict_count();
        if (cap <= 0) return ids;
        std::vector<int> dictIdx(cap);
        const int cnt = gd_group_dicts(groupId, dictIdx.data(), static_cast<int>(dictIdx.size()));
        for (int k = 0; k < cnt; ++k) {
            const int i = dictIdx[k];
            int state = -1;
            if (!(gd_fts_index_state(i, &state) == 0 && state == 1))
                continue;
            char idb[128] = {0};
            if (gd_dict_id(i, idb, static_cast<int>(sizeof(idb))) != 0)
                continue;
            const QString id = QString::fromLocal8Bit(idb);
            if (failedSnapshot.contains(id))
                continue;
            ids.append(id);
        }
        return ids;
    });
    auto *gwt = new QFutureWatcher<QStringList>(this);
    connect(gwt, &QFutureWatcher<QStringList>::finished, this,
            [this, norm, mode, groupId, displayQuery, gwt]{
        const QStringList ids = gwt->result();
        gwt->deleteLater();
        if (ids.isEmpty()) return;
        bool anyNew = false;
        {
            QMutexLocker lock(&m_ftsQueueMutex);
            for (const QString &id : ids) {
                if (!m_ftsQueue.contains(id)) {
                    m_ftsQueue.append(id);
                    anyNew = true;
                }
            }
        }
        if (!anyNew) return;
        // Arm a one-shot re-run so the deferred dictionaries' hits appear.
        m_pendingFtsNorm = norm;
        m_pendingFtsMode = mode;
        m_pendingFtsGroup = groupId;
        m_pendingFtsQuery = displayQuery;
        m_pendingFtsValid = true;
        qInfo() << "[aurelex] on-demand FTS builds enqueued for" << ids;
        if (!m_ftsWorkerRunning)
            ensureFtsWorker();
    });
    gwt->setFuture(g);
}

void EngineController::reRunPendingFts()
{
    if (!m_pendingFtsValid) return;
    m_pendingFtsValid = false;
    runFtsSearch(m_pendingFtsNorm, m_pendingFtsMode, m_pendingFtsGroup,
                 m_pendingFtsQuery);
}

// ---------- Milestone 5: history + favorites ----------

void EngineController::loadHistory()
{
    const QString path = m_appDir + "/history.json";
    QVariantList list;
    QFile f(path);
    if (f.open(QIODevice::ReadOnly)) {
        const QJsonDocument doc = QJsonDocument::fromJson(f.readAll());
        for (const QJsonValue &v : doc.array()) {
            QVariantMap m;
            if (v.isString()) {
                // Legacy plain-string entry → group 0 ("All").
                m.insert("word", v.toString());
                m.insert("group", 0);
            } else {
                m = v.toObject().toVariantMap();
                if (!m.contains("group")) m.insert("group", 0);
            }
            if (m.value("word").toString().isEmpty()) continue;
            list.append(m);
        }
    }
    setHistory(list);
}

void EngineController::saveHistory()
{
    const QString path = m_appDir + "/history.json";
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return;
    QJsonArray arr;
    for (const QVariant &entry : m_history) {
        const QVariantMap m = entry.toMap();
        QJsonObject o;
        o.insert("word", m.value("word").toString());
        o.insert("group", m.value("group").toInt());
        arr.append(o);
    }
    f.write(QJsonDocument(arr).toJson(QJsonDocument::Compact));
}

void EngineController::loadFavorites()
{
    const QString path = m_appDir + "/favorites.json";
    QVariantList list;
    QFile f(path);
    if (f.open(QIODevice::ReadOnly)) {
        const QJsonDocument doc = QJsonDocument::fromJson(f.readAll());
        for (const QJsonValue &v : doc.array()) {
            QVariantMap m;
            if (v.isString()) {
                // Legacy plain-string entry → group 0 ("All").
                m.insert("word", v.toString());
                m.insert("group", 0);
            } else {
                m = v.toObject().toVariantMap();
                if (!m.contains("group")) m.insert("group", 0);
            }
            if (m.value("word").toString().isEmpty()) continue;
            list.append(m);
        }
    }
    setFavorites(list);
}

void EngineController::saveFavorites()
{
    const QString path = m_appDir + "/favorites.json";
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return;
    QJsonArray arr;
    for (const QVariant &entry : m_favorites) {
        const QVariantMap m = entry.toMap();
        QJsonObject o;
        o.insert("word", m.value("word").toString());
        o.insert("group", m.value("group").toInt());
        arr.append(o);
    }
    f.write(QJsonDocument(arr).toJson(QJsonDocument::Compact));
}

// Re-point a history/favorites entry whose group no longer exists to the
// built-in group. Nothing else prunes these lists, so an entry recorded in a
// group that was later deleted keeps a dangling id forever: its row claims a
// scope that is not there, and a tap silently looks up in group 0. The word is
// always kept — group 0 is a superset of the group that was deleted, so a
// re-pointed tap returns at least what the original tap would have.
//
// Only runs where m_groups is known-good (setGroups, deleteGroup's success
// path). m_groups is populated asynchronously by the scan, and history loads
// before it, so an empty list here means "not loaded yet", not "no groups
// exist" — re-pointing then would re-point every entry.
//
// `deletedGroupId` lets deleteGroup repair without waiting for refreshGroups:
// m_groups still lists the group it just deleted, so the m_groups check alone
// would not see it as gone.
int EngineController::repointStaleGroupEntries(int deletedGroupId)
{
    if (m_groups.isEmpty()) return 0;

    const auto isStale = [this, deletedGroupId](int g) {
        if (g == 0) return false;  // the built-in group always exists
        if (g == deletedGroupId) return true;
        return !groupExists(g);
    };

    int rewritten = 0;
    QVariantList history, favorites;
    history.reserve(m_history.size());
    favorites.reserve(m_favorites.size());

    for (const QVariant &entry : m_history) {
        QVariantMap m = entry.toMap();
        if (isStale(m.value("group").toInt())) {
            m.insert("group", 0);
            ++rewritten;
        }
        history.append(m);
    }
    for (const QVariant &entry : m_favorites) {
        QVariantMap m = entry.toMap();
        if (isStale(m.value("group").toInt())) {
            m.insert("group", 0);
            ++rewritten;
        }
        favorites.append(m);
    }

    if (rewritten == 0) return 0;  // idempotent: no writes on a second run

    setHistory(history);
    setFavorites(favorites);
    saveHistory();
    saveFavorites();
    qInfo() << "[aurelex] repointStaleGroupEntries rewrote" << rewritten
            << "history/favorites entries to the built-in group";
    return rewritten;
}

void EngineController::setHistory(const QVariantList &list)
{
    if (m_history == list) return;
    m_history = list;
    emit historyChanged();
}

void EngineController::setFavorites(const QVariantList &list)
{
    if (m_favorites == list) return;
    m_favorites = list;
    emit favoritesChanged();
}

QStringList EngineController::historyWords() const
{
    QStringList out;
    for (const QVariant &e : m_history)
        out << e.toMap().value("word").toString();
    return out;
}

QStringList EngineController::favoritesWords() const
{
    QStringList out;
    for (const QVariant &e : m_favorites)
        out << e.toMap().value("word").toString();
    return out;
}

bool EngineController::groupExists(int groupId) const
{
    for (const QVariant &g : m_groups) {
        if (g.toMap().value("id").toInt() == groupId) return true;
    }
    return false;
}

QString EngineController::groupName(int groupId) const
{
    for (const QVariant &g : m_groups) {
        const QVariantMap m = g.toMap();
        if (m.value("id").toInt() == groupId)
            return m.value("name").toString();
    }
    // Unknown/deleted group id → treat as "All". Deliberately the invariant
    // literal, not tr("All"): every visible group name resolves by id on the QML
    // side (_groupLabel), so this fallback is not a label source and must not
    // become a second, divergent naming path.
    return QStringLiteral("All");
}

void EngineController::setThemeMode(int mode)
{
    // An out-of-range write is ignored rather than clamped to a neighbour: the
    // only sources are our own cycle and the settings loader (which already
    // normalizes), so anything else is a programming error, and silently
    // snapping to the nearest mode would hide it. Same guard shape as
    // setArticleZoom's no-op-on-unchanged write: no signal, no save, no churn.
    if (mode != kThemeFollowSystem && mode != kThemeLight && mode != kThemeDark)
        return;
    if (m_themeMode == mode) return;
    m_themeMode = mode;
    saveSettings();
    applyEffectiveDark();
    emit themeModeChanged();
}

void EngineController::toggleThemeMode()
{
    const int next = m_themeMode == kThemeLight    ? kThemeDark
                   : m_themeMode == kThemeDark     ? kThemeFollowSystem
                                                   : kThemeLight;
    qInfo("toggleThemeMode: %d -> %d", m_themeMode, next);
    setThemeMode(next);
}

void EngineController::setArticleZoom(qreal zoom)
{
    // Snap to step then clamp to [75, 250]; the header buttons step by exactly
    // one kArticleZoomStep so snap keeps their values stable. Out-of-range or
    // unchanged writes are a no-op (no signal) so QML isn't churned.
    qreal snapped = std::round(zoom / kArticleZoomStep) * kArticleZoomStep;
    snapped = std::max(kArticleZoomMin, std::min(kArticleZoomMax, snapped));
    if (qFuzzyCompare(m_articleZoom, snapped)) return;
    m_articleZoom = snapped;
    saveSettings();
    emit articleZoomChanged();
}

bool EngineController::readSystemDark() const
{
#if defined(Q_OS_ANDROID)
    return QJniObject::callStaticMethod<jboolean>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "isNightModeActive",
        "()Z");
#else
    return false;
#endif
}

void EngineController::updateSystemDark()
{
    const bool current = m_systemDark;
    m_systemDark = readSystemDark();
    if (m_systemDark != current) {
        emit systemDarkChanged();
        applyEffectiveDark();
    }
}

// Resolve the theme SETTING into the theme in EFFECT: an explicit light/dark
// mode wins outright, follow-system defers to the sampled Android night state.
// Every consumer of m_darkMode — the Material.theme palette (QML), the engine
// preference, the system bar icons — reads this one resolved value, so they
// can't disagree about what "dark mode" currently means. The OPEN article flips
// in place via gdSetDarkMode() (rewriteArticleUrls always injects the dark
// controller), so no re-lookup/reload is needed here — only the engine
// preference is kept in sync off-thread for any future HTML generation.
void EngineController::applyEffectiveDark()
{
    m_darkMode = m_themeMode == kThemeLight  ? false
               : m_themeMode == kThemeDark   ? true
                                             : m_systemDark;
    // Our self-painted status/nav strips must invert the system bar icons to
    // the opposite contrast (dark icons on a light strip, light icons on dark).
    applySystemBarAppearance();
    QtConcurrent::run([dark = m_darkMode]{ gd_set_dark_mode(dark ? 1 : 0); });
    emit darkModeChanged();
}

void EngineController::applySystemBarAppearance()
{
#if defined(Q_OS_ANDROID)
    QJniObject::callStaticMethod<void>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "setSystemBarAppearance",
        "(Z)V",
        m_darkMode ? JNI_TRUE : JNI_FALSE);
#else
    Q_UNUSED(m_darkMode);
#endif
}

// Detect movement of the four safe-area insets.
//
// Why a poll rather than a window-resize hook: rotation 1 and rotation 3 are both
// 2400x1080, so flipping between the two landscape orientations — the natural
// way to turn a phone sideways — produces NO onWidthChanged/onHeightChanged,
// while the display cutout moves from the left edge to the right. Measured on a
// ThinkPhone: the platform reported the cutout correctly (sideHint=RIGHT,
// frame=[2290,0][2400,1080]) but the layout kept the stale left margin and put
// the article back under the camera. Comparing the VALUES also covers the IME,
// split screen and a foldable unfolding, none of which are guaranteed to resize
// the window either.
//
// The compare-and-emit shape matches updateSystemDark on the same tick: read, diff,
// notify. Costs four JNI int reads per 500ms tick, and the emit only fires on an
// actual change.
void EngineController::pollInsets()
{
    const int now[4] = { systemInsetTop(), systemInsetBottom(),
                         systemInsetLeft(), systemInsetRight() };
    if (now[0] == m_insets[0] && now[1] == m_insets[1] &&
        now[2] == m_insets[2] && now[3] == m_insets[3]) {
        return;
    }
    m_insets[0] = now[0];
    m_insets[1] = now[1];
    m_insets[2] = now[2];
    m_insets[3] = now[3];
    emit insetsChanged();
}

void EngineController::syncSystemBarAppearance()
{
#if defined(Q_OS_ANDROID)
    QJniObject::callStaticMethod<void>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "syncSystemBarAppearance",
        "()V");
#endif
}

bool EngineController::peekPendingIndexingDone() const
{
    if (m_appDir.isEmpty()) return false;
    const QString path = m_appDir + QStringLiteral("/../shared_prefs/indexing.xml");
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) return false;
    const QString xml = QString::fromUtf8(f.readAll());
    f.close();
    QXmlStreamReader xr(xml);
    while (!xr.atEnd()) {
        const auto tok = xr.readNext();
        if (tok == QXmlStreamReader::StartElement
            && xr.name() == QStringLiteral("boolean")
            && xr.attributes().value(QStringLiteral("name")) == QStringLiteral("indexingDone")) {
            return xr.attributes().value(QStringLiteral("value")) == QStringLiteral("true");
        }
    }
    return false;
}

void EngineController::removePendingIndexingFile()
{
    if (m_appDir.isEmpty()) return;
    QFile f(m_appDir + QStringLiteral("/../shared_prefs/indexing.xml"));
    f.remove();
}

bool EngineController::peekStagingActive() const
{
    if (m_appDir.isEmpty()) return false;
    const QString path = m_appDir + QStringLiteral("/../shared_prefs/staging.xml");
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) return false;
    const QString xml = QString::fromUtf8(f.readAll());
    f.close();
    QXmlStreamReader xr(xml);
    while (!xr.atEnd()) {
        const auto tok = xr.readNext();
        if (tok == QXmlStreamReader::StartElement
            && xr.name() == QStringLiteral("boolean")
            && xr.attributes().value(QStringLiteral("name")) == QStringLiteral("stagingActive")) {
            return xr.attributes().value(QStringLiteral("value")) == QStringLiteral("true");
        }
    }
    return false;
}

void EngineController::removeStagingFile()
{
    if (m_appDir.isEmpty()) return;
    QFile f(m_appDir + QStringLiteral("/../shared_prefs/staging.xml"));
    f.remove();
}

// ---------- Remote catalog fetch (QNetworkAccessManager) ----------

void EngineController::fetchCatalog()
{
    if (m_remoteCatalogUrl.isEmpty()) return;
    if (!m_manifestValid) {
        // Nothing cached yet: there is no catalog to show, so say so instead of
        // rendering an empty list the user cannot tell from "no entries".
        m_catalogEntries.clear();
    } else if (m_manifestFetched.isValid()
               && m_manifestFetched.msecsTo(QDateTime::currentDateTime()) < kCatalogRereprobeMs) {
        // Recently fetched: hand back the cache without spending a request on a
        // CDN-cached document. An INVALID timestamp (age unknown, e.g. right
        // after refreshCatalog()) must NOT take this branch -- that is exactly
        // when a real re-probe is wanted, and treating "unknown" as "fresh"
        // made refreshCatalog() a no-op that never issued a request.
        refreshCatalogEntries();
        emit catalogChanged();
        return;
    }
    // A cached copy we can already show: keep the entries visible and mark the
    // catalog as "stale" rather than blanking the list mid-refresh.
    m_catalogReachable = false;
    m_catalogLoading = true;
    m_catalogError.clear();
    emit catalogChanged();
    if (m_catalogFetchInFlight) return;
    m_catalogFetchInFlight = true;

    if (!m_net) {
        m_net = new QNetworkAccessManager(this);
    }
    QNetworkRequest req{QUrl(m_remoteCatalogUrl)};
    // The catalog is a static document, so a conditional request is the polite
    // thing and keeps the transfer to a 304 when nothing changed.
    req.setAttribute(QNetworkRequest::RedirectPolicyAttribute,
                     QNetworkRequest::NoLessSafeRedirectPolicy);
    req.setHeader(QNetworkRequest::UserAgentHeader, QByteArrayLiteral("Aurelex"));
    if (m_manifestValid && m_manifestFetched.isValid()) {
        // A raw header, not a QVariant attribute: If-Modified-Since is an HTTP
        // date, and the parser's own timestamp is local time, so format it.
        req.setRawHeader("If-Modified-Since",
                         m_manifestFetched.toUTC().toString(Qt::RFC2822Date).toLatin1());
    }

    qInfo() << "[aurelex] fetching remote catalog:" << m_remoteCatalogUrl;
    QNetworkReply *reply = m_net->get(req);
    connect(reply, &QNetworkReply::finished, this, [this, reply]{
        reply->deleteLater();
        m_catalogFetchInFlight = false;
        m_catalogLoading = false;
        // A 304 is a SUCCESS: our cached copy is still current.
        const int status = reply->attribute(
            QNetworkRequest::HttpStatusCodeAttribute).toInt();
        if (status == 304 && m_manifestValid) {
            m_catalogReachable = true;
            m_catalogError.clear();
            m_manifestFetched = QDateTime::currentDateTime();
            cacheManifest();
            refreshCatalogEntries();
            emit catalogChanged();
            return;
        }
        if (reply->error() != QNetworkReply::NoError || status < 200 || status >= 300) {
            // Unreachable. Report it and LEAVE THE LAST GOOD MANIFEST IN PLACE:
            // a previously-read catalog still renders (read-only) and only
            // download attempts fail.
            m_catalogReachable = false;
            m_catalogError = reply->error() != QNetworkReply::NoError
                    ? reply->errorString()
                    : QStringLiteral("HTTP %1").arg(status);
            qWarning() << "[aurelex] remote catalog unreachable:" << m_catalogError;
            refreshCatalogEntries();
            emit catalogChanged();
            return;
        }
        const QByteArray body = reply->readAll();
        // A small catalog is a maintenance mistake, not a data set.
        if (body.size() > kCatalogMaxBytes) {
            m_catalogReachable = false;
            m_catalogError = QStringLiteral("catalog document is unexpectedly large");
            qWarning() << "[aurelex] remote catalog too large:" << body.size() << "bytes";
            emit catalogChanged();
            return;
        }
        RemoteCatalog::Manifest m;
        QString err;
        if (!RemoteCatalog::parseManifest(body, &m, &err)) {
            // Reject the document rather than showing part of it; the previous
            // good manifest stays as the fallback.
            m_catalogReachable = false;
            m_catalogError = err;
            qWarning() << "[aurelex] remote catalog rejected:" << err;
            emit catalogChanged();
            return;
        }
        m_manifest = m;
        m_manifestRaw = QString::fromUtf8(body);
        m_manifestValid = true;
        m_manifestFetched = QDateTime::currentDateTime();
        m_catalogReachable = true;
        m_catalogError.clear();
        cacheManifest();
        refreshCatalogEntries();
        emit catalogChanged();
        qInfo() << "[aurelex] remote catalog ok:" << m.entries.size() << "entries";
    });
    // A dead link must not leave the catalog spinner up forever. The reply is
    // captured through a QPointer: the finished handler above deleteLater()s it,
    // so a raw capture would dereference freed memory when this fires 15s later
    // (SIGSEGV on the UI thread) on every fetch whose reply finished first.
    QPointer<QNetworkReply> replyGuard(reply);
    QTimer::singleShot(kCatalogFetchTimeoutMs, this, [replyGuard]{
        if (replyGuard && replyGuard->isRunning()) replyGuard->abort();
    });
}

void EngineController::refreshCatalog()
{
    // An explicit refresh always re-probes, and drops the "fresh enough" gate.
    m_manifestFetched = QDateTime();
    fetchCatalog();
}

QStringList EngineController::dictionarySources() const
{
    QStringList sources;
    for (const QVariant &v : m_dictionaries)
        sources.append(v.toMap().value(QStringLiteral("source")).toString());
    return sources;
}

void EngineController::refreshCatalogEntries()
{
    QVariantList out;
    if (m_manifestValid) {
        // Installed-detection is derived from the CURRENT dictionary list, so
        // recompute it whenever the list changes rather than caching a badge
        // that a later scan would make a lie.
        const QStringList sources = dictionarySources();

        // Only the PRIMARY UI language may select a localized entry name: on
        // Android uiLanguages() also lists the APK's resource locales, so passing
        // the whole list would let a device whose top language the manifest has
        // no name for fall through to a ru/ja name.
        const QStringList uiLanguages = QLocale().uiLanguages();
        const QStringList primaryUiLanguage = uiLanguages.isEmpty()
            ? QStringList{} : QStringList{ uiLanguages.first() };

        for (const RemoteCatalog::Entry &e : m_manifest.entries) {
            QVariantMap m;
            m.insert(QStringLiteral("id"), e.id);
            m.insert(QStringLiteral("name"), e.name);
            // The name for the app's active language, or `name` when the entry
            // provides none; QML shows this one and keeps `name` as the stable
            // (English) identifier for accessibility/test IDs.
            m.insert(QStringLiteral("displayName"), e.nameFor(primaryUiLanguage));
            m.insert(QStringLiteral("langFrom"), e.langFrom);
            m.insert(QStringLiteral("langTo"), e.langTo);
            m.insert(QStringLiteral("pair"), e.langFrom + QLatin1Char('/') + e.langTo);
            m.insert(QStringLiteral("attribution"), e.attribution);
            m.insert(QStringLiteral("license"), e.license);
            m.insert(QStringLiteral("totalBytes"), e.totalBytes);
            m.insert(QStringLiteral("requiredBytes"), e.requiredBytes);
            const QVector<RemoteCatalog::File> optional = e.optionalFiles();
            qint64 optionalBytes = 0;
            QVariantList files;
            for (const RemoteCatalog::File &f : e.files) {
                if (!f.required) optionalBytes += f.sizeBytes;
                QVariantMap fm;
                fm.insert(QStringLiteral("name"), f.name);
                fm.insert(QStringLiteral("sizeBytes"), f.sizeBytes);
                fm.insert(QStringLiteral("required"), f.required);
                fm.insert(QStringLiteral("role"), f.role);
                files.append(fm);
            }
            m.insert(QStringLiteral("optionalBytes"), optionalBytes);
            m.insert(QStringLiteral("hasOptional"), !optional.isEmpty());
            // Names of the optional files, so the optional-audio request can
            // name them without QML re-deriving the manifest's structure.
            QStringList optionalNames;
            for (const RemoteCatalog::File &f : optional)
                optionalNames.append(f.name);
            m.insert(QStringLiteral("optionalFileNames"), optionalNames);
            m.insert(QStringLiteral("installed"), RemoteCatalog::isInstalled(e, sources));
            // Whether every optional file is already staged next to the
            // dictionary, so the UI can show audio as present instead of
            // offering the same bundle again. Optional files land in the same
            // content-hash directory as the dictionary.
            bool resourcesPresent = !optional.isEmpty();
            if (resourcesPresent && !m_stagedDir.isEmpty()) {
                const QString dir = m_stagedDir + QLatin1Char('/')
                                    + RemoteCatalog::contentHash(e);
                for (const RemoteCatalog::File &f : optional) {
                    if (!QFileInfo::exists(dir + QLatin1Char('/') + f.name)) {
                        resourcesPresent = false;
                        break;
                    }
                }
            }
            m.insert(QStringLiteral("resourcesPresent"), resourcesPresent);
            m.insert(QStringLiteral("files"), files);
            m.insert(QStringLiteral("installable"), e.installable);
            m.insert(QStringLiteral("unsupportedReason"), e.unsupportedReason);
            out.append(m);
        }
    }
    m_catalogEntries = out;
    m_catalogUpdated = m_manifestValid ? m_manifest.updated : QString();
    m_catalogLastFetched = m_manifestFetched.isValid()
            ? QLocale::system().toString(m_manifestFetched, QLocale::ShortFormat)
            : QString();
    // Emit HERE, rather than only from the fetch reply handlers: the scan /
    // index path (refreshDictionaries) also calls this to re-derive the
    // installed badges, and without the notify the open pane kept stale rows
    // (and a stale selection) until it was reopened.
    emit catalogChanged();
}

// ---------- Downloads ----------

// One SharedPreferences XML read. Mirrors peekStagingActive /
// peekPendingIndexingDone: the service writes the file, this poller consumes
// it, and the marker is cleared on a terminal outcome.
void EngineController::syncDownloadState()
{
    if (m_appDir.isEmpty()) return;
    const QString path = m_appDir + QStringLiteral("/../shared_prefs/download.xml");
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) {
        // No marker: nothing running. Only a change is worth signalling.
        if (m_downloadActive || !m_downloadOutcome.isEmpty()) {
            m_downloadActive = false;
            m_downloadEntryName.clear();
            m_downloadSpeed.clear();
            m_downloadScratchHashes.clear();
            emit downloadChanged();
        }
        return;
    }
    const QString xml = QString::fromUtf8(f.readAll());
    f.close();

    bool active = false, canceled = false;
    int filesDone = 0, filesTotal = 0;
    qint64 bytesDone = 0, bytesTotal = 0;
    QString entry, speed, outcome, message, hashes;
    QStringList succeeded, failed;
    QXmlStreamReader xr(xml);
    while (!xr.atEnd()) {
        if (xr.readNext() != QXmlStreamReader::StartElement) continue;
        const QString name = xr.name().toString();
        const auto attr = [&xr](const char *key) {
            return xr.attributes().value(QLatin1String(key)).toString();
        };
        if (name == QLatin1String("boolean")) {
            const QString k = xr.attributes().value(QStringLiteral("name")).toString();
            const bool v = xr.attributes().value(QStringLiteral("value")) == QLatin1String("true");
            if (k == QLatin1String("downloadActive")) active = v;
            else if (k == QLatin1String("downloadCanceled")) canceled = v;
        } else if (name == QLatin1String("int")) {
            const QString k = xr.attributes().value(QStringLiteral("name")).toString();
            const int v = xr.attributes().value(QStringLiteral("value")).toInt();
            if (k == QLatin1String("filesDone")) filesDone = v;
            else if (k == QLatin1String("filesTotal")) filesTotal = v;
        } else if (name == QLatin1String("long")) {
            const QString k = xr.attributes().value(QStringLiteral("name")).toString();
            const qint64 v = xr.attributes().value(QStringLiteral("value")).toLongLong();
            if (k == QLatin1String("bytesDone")) bytesDone = v;
            else if (k == QLatin1String("bytesTotal")) bytesTotal = v;
        } else if (name == QLatin1String("string")) {
            const QString k = xr.attributes().value(QStringLiteral("name")).toString();
            // SharedPreferences writes a <string> value as the element's TEXT
            // content, NOT a `value` attribute (only boolean/int/long/float use
            // attributes). Reading `value` here silently produced empty strings,
            // so entryName/succeeded/failed/scratchHashes were always blank and a
            // finished batch never produced an outcome or a rescan.
            const QString v = xr.readElementText();
            if (k == QLatin1String("entryName")) entry = v;
            else if (k == QLatin1String("speed")) speed = v;
            else if (k == QLatin1String("message")) message = v;
            else if (k == QLatin1String("scratchHashes")) hashes = v;
            // Pipe-separated so one key carries a whole batch's leftovers.
            else if (k == QLatin1String("succeeded")) succeeded = v.split(QLatin1Char('|'), Qt::SkipEmptyParts);
            else if (k == QLatin1String("failed")) failed = v.split(QLatin1Char('|'), Qt::SkipEmptyParts);
        }
    }

    // The service writes the terminal outcome and drops `active` in the same
    // commit, so derive it rather than trusting a separate flag.
    QString newOutcome;
    if (!active) {
        if (canceled) newOutcome = QStringLiteral("cancelled");
        else if (!failed.isEmpty()) newOutcome = QStringLiteral("failed");
        else if (!succeeded.isEmpty()) newOutcome = QStringLiteral("succeeded");
    }

    const bool changed =
            active != m_downloadActive
            || entry != m_downloadEntryName
            || filesDone != m_downloadFilesDone
            || filesTotal != m_downloadFilesTotal
            || bytesDone != m_downloadBytesDone
            || bytesTotal != m_downloadBytesTotal
            || speed != m_downloadSpeed
            || newOutcome != m_downloadOutcome
            || message != m_downloadMessage
            || hashes != m_downloadScratchHashes
            || succeeded != m_downloadSucceeded
            || failed != m_downloadFailed;
    if (!changed) return;

    m_downloadActive = active;
    m_downloadEntryName = entry;
    m_downloadFilesDone = filesDone;
    m_downloadFilesTotal = filesTotal;
    m_downloadBytesDone = bytesDone;
    m_downloadBytesTotal = bytesTotal;
    m_downloadSpeed = speed;
    m_downloadMessage = message;
    m_downloadScratchHashes = hashes;
    m_downloadSucceeded = succeeded;
    m_downloadFailed = failed;
    m_downloadOutcome = newOutcome;
    // sizeBytes is hand-maintained, so a slightly wrong total must not push the
    // bar past full: clamp, and hold at 0 when there is nothing to measure.
    m_downloadFraction = (bytesTotal > 0)
            ? qBound(0.0, qreal(bytesDone) / qreal(bytesTotal), 1.0)
            : 0.0;

    // "Something landed in files/staged" is the trigger for engine work, NOT the
    // outcome string: a batch where one entry failed and another succeeded is
    // reported as "failed", yet the successful entry is on disk and invisible to
    // the engine until a scan runs. Gating on the outcome string would strand it.
    const bool published = !m_downloadSucceeded.isEmpty();
    const bool terminal = !newOutcome.isEmpty();
    const bool idle = m_ready && !m_processingActive;

    bool plainRescan = false;
    if (terminal) {
        // Terminal outcome: consume the marker (the service's cue is its
        // absence, and a leftover would re-show this result forever).
        removeDownloadFile();
        if (published) {
            // m_audioReloadIds non-empty means this batch was "add audio" for a
            // dictionary the engine already holds: a plain rescan cannot make
            // the new resources take effect, so that path unloads + re-adds.
            if (m_audioReloadIds.isEmpty() && idle) {
                plainRescan = true;
            } else {
                // Everything else waits for a moment when the engine is ready and
                // no tail is live. Arming the flags (instead of starting a second
                // scan alongside a running one) keeps a single chain, and the
                // tail never lowers processingActive between the two scans
                // (no-blink). The poller below re-checks every tick, so a batch
                // landing mid-chain is not lost.
                m_stagedRescanPending = true;
            }
        } else {
            // Cancelled, or nothing succeeded: the optional-resource ids belong to
            // a batch that never published. Dropping them stops a later, unrelated
            // success from unloading dictionaries "for" a batch that changed
            // nothing.
            m_audioReloadIds.clear();
        }
    }
    // A published batch means the named entries are now installed from the
    // catalog: remember their digests (inert; see recordInstalledDigests).
    if (terminal && published)
        recordInstalledDigests(m_downloadSucceeded);
    emit downloadChanged();
    // Terminal + published + idle, and the engine must actually RE-LOAD, not
    // rescan. Both conditions are required: firing this while the transfer is
    // still running would reload the dictionary a few seconds before its new
    // resources arrive.
    if (terminal && published && !m_audioReloadIds.isEmpty() && idle) {
        // Consume the ids BEFORE the call: reloadDictionariesForResources ends in
        // runScan(), and a second marker-driven scan landing in between must not
        // schedule a duplicate reload.
        const QStringList ids = m_audioReloadIds;
        m_audioReloadIds.clear();
        m_stagedRescanPending = false;
        reloadDictionariesForResources(ids);
    } else if (plainRescan) {
        runScan();
    }
}

void EngineController::removeDownloadFile()
{
    if (m_appDir.isEmpty()) return;
    QFile f(m_appDir + QStringLiteral("/../shared_prefs/download.xml"));
    f.remove();
}

QStringList EngineController::liveDownloadHashes() const
{
    return m_downloadScratchHashes.split(QLatin1Char('|'), Qt::SkipEmptyParts);
}

QVariantMap EngineController::downloadPreflight(const QVariantList &requests) const
{
    qint64 need = 0;
    QStringList names;
    for (const QVariant &v : requests) {
        const QVariantMap r = v.toMap();
        const QString id = r.value(QStringLiteral("id")).toString();
        const RemoteCatalog::Entry *e = findCatalogEntry(id);
        if (!e) continue;
        need += sumRequestedBytes(*e, r);
        names.append(e->name);
    }
    const qint64 free = freeBytesForDownloads();
    QVariantMap out;
    out.insert(QStringLiteral("names"), names);
    out.insert(QStringLiteral("needBytes"), need);
    // Always present, so the caller's message never renders an empty %2.
    out.insert(QStringLiteral("freeBytes"), free);
    out.insert(QStringLiteral("nothing"), need <= 0);
    if (need <= 0) {
        // Nothing resolvable (an installed entry with audio off, or an unknown
        // id): this is "nothing to download", NOT a free-space problem.
        out.insert(QStringLiteral("ok"), false);
        out.insert(QStringLiteral("warn"), false);
        return out;
    }
    out.insert(QStringLiteral("ok"), free >= need + RemoteCatalog::kMinHeadroomBytes);
    out.insert(QStringLiteral("warn"),
               free < need + RemoteCatalog::kWarnHeadroomBytes);
    if (free < need + RemoteCatalog::kMinHeadroomBytes)
        out.insert(QStringLiteral("missingBytes"), need + RemoteCatalog::kMinHeadroomBytes - free);
    return out;
}

qint64 EngineController::sumRequestedBytes(const RemoteCatalog::Entry &e,
                                           const QVariantMap &request) const
{
    // An explicit file list wins (legacy callers); otherwise the `audio` flag
    // decides: a fresh install gets required (+ optional when audio is on), an
    // already-installed entry gets only the optional bundle.
    const QVariantList wanted = request.value(QStringLiteral("files")).toList();
    if (!wanted.isEmpty()) {
        qint64 sum = 0;
        for (const QVariant &w : wanted) {
            const QString name = w.toString();
            for (const RemoteCatalog::File &f : e.files)
                if (f.name == name)
                    sum += f.sizeBytes;
        }
        return sum;
    }
    const bool audio = request.value(QStringLiteral("audio")).toBool();
    if (RemoteCatalog::isInstalled(e, dictionarySources())) {
        qint64 sum = 0;
        if (audio)
            for (const RemoteCatalog::File &f : e.optionalFiles())
                sum += f.sizeBytes;
        return sum;
    }
    qint64 sum = 0;
    for (const RemoteCatalog::File &f : e.files)
        if (f.required || (audio && !f.required))
            sum += f.sizeBytes;
    return sum;
}

qint64 EngineController::freeBytesForDownloads() const
{
    // Downloads land in getFilesDir(), so the preflight must measure THAT
    // volume, not the first QStorageInfo root (which may be the SD card).
    const QStorageInfo storage(QDir(m_appDir).absolutePath());
    if (!storage.isValid()) return 0;
    return storage.bytesAvailable();
}

const RemoteCatalog::Entry *EngineController::findCatalogEntry(const QString &id) const
{
    for (const RemoteCatalog::Entry &e : m_manifest.entries)
        if (e.id == id)
            return &e;
    return nullptr;
}

void EngineController::startCatalogDownload(const QVariantList &requests)
{
    if (requests.isEmpty()) return;
    if (!m_catalogReachable) {
        // The catalog is the authority on what exists and where it comes from;
        // a download started from a stale read-only list is refused rather than
        // attempted against a manifest we cannot vouch for.
        m_downloadOutcome = QStringLiteral("failed");
        m_downloadMessage = tr("The dictionary catalog is unavailable.");
        emit downloadChanged();
        return;
    }
    // Build the transfer request from the CURRENTLY PARSED manifest, so the
    // service never sees a URL or size the parser did not approve.
    QJsonArray requestsOut;
    QStringList pendingAudioIds;
    qint64 need = 0;
    for (const QVariant &v : requests) {
        const QVariantMap r = v.toMap();
        const RemoteCatalog::Entry *e = findCatalogEntry(r.value(QStringLiteral("id")).toString());
        // Skip an entry this build cannot install: the UI already disables it,
        // but a download of its unsupported required files would land a
        // dictionary the engine can never load.
        if (!e || !e->installable) continue;
        const bool wantAudio = r.value(QStringLiteral("audio")).toBool();
        const bool installed = RemoteCatalog::isInstalled(*e, dictionarySources());
        const QVariantList wanted = r.value(QStringLiteral("files")).toList();
        QJsonArray filesOut;
        QVector<RemoteCatalog::File> chosen;
        if (!wanted.isEmpty()) {
            // Legacy explicit selector.
            for (const RemoteCatalog::File &f : e->files)
                if (wanted.contains(f.name))
                    chosen.append(f);
        } else if (installed) {
            // Already loaded: only a missing optional bundle can be added, and
            // only when the user asked for audio. Nothing to re-download.
            if (wantAudio)
                chosen = e->optionalFiles();
        } else {
            // Fresh install: required always, resources only when audio is on.
            for (const RemoteCatalog::File &f : e->files)
                if (f.required || (wantAudio && !f.required))
                    chosen.append(f);
        }
        if (chosen.isEmpty()) continue;
        for (const RemoteCatalog::File &f : chosen) {
            QJsonObject fo;
            fo.insert(QStringLiteral("name"), f.name);
            fo.insert(QStringLiteral("url"), f.url);
            fo.insert(QStringLiteral("sizeBytes"), f.sizeBytes);
            fo.insert(QStringLiteral("sha256"), f.sha256);
            fo.insert(QStringLiteral("required"), f.required);
            filesOut.append(fo);
        }
        if (filesOut.isEmpty()) continue;
        QJsonObject ro;
        ro.insert(QStringLiteral("id"), e->id);
        ro.insert(QStringLiteral("name"), e->name);
        ro.insert(QStringLiteral("contentHash"), RemoteCatalog::contentHash(*e));
        ro.insert(QStringLiteral("files"), filesOut);
        requestsOut.append(ro);
        for (const RemoteCatalog::File &f : chosen) need += f.sizeBytes;
        // "Add audio" on an ALREADY-INSTALLED entry: nothing new to load, only
        // new resources next to the existing dictionary. A plain rescan cannot
        // do that -- the engine already holds the dictionary open, so the
        // resources never take effect. Remember the id so the success path
        // unloads the dictionary and rescans it (see audioReloadIds).
        //
        // The ids are collected here but only COMMITTED once the batch is known
        // to be startable: a refusal below must not leave a pending reload for a
        // transfer that never ran.
        bool allOptional = !chosen.isEmpty();
        for (const RemoteCatalog::File &f : chosen)
            if (f.required) allOptional = false;
        if (allOptional && installed) {
            if (!pendingAudioIds.contains(e->id))
                pendingAudioIds.append(e->id);
        }
    }
    if (requestsOut.isEmpty()) return;
    if (need > 0) {
        // The service re-checks before the first byte; this only stops an
        // obviously-doomed batch from starting (the dialog already asked).
        const qint64 free = freeBytesForDownloads();
        if (free < need + RemoteCatalog::kMinHeadroomBytes) {
            m_downloadOutcome = QStringLiteral("failed");
            m_downloadMessage = tr("Not enough free space.");
            emit downloadChanged();
            return;
        }
    }
    m_audioReloadIds = pendingAudioIds;
    QJsonObject payload;
    payload.insert(QStringLiteral("requests"), requestsOut);
    // The whole catalog's id→contentHash index, so the service can tell an
    // orphaned scratch dir whose entry is STILL in the catalog (resume it) from
    // one for a dictionary that has been withdrawn (purge it) — including
    // entries that are not part of this batch.
    QJsonObject index;
    for (const RemoteCatalog::Entry &e : m_manifest.entries)
        index.insert(e.id, RemoteCatalog::contentHash(e));
    payload.insert(QStringLiteral("catalogIndex"), index);
    const QByteArray json = QJsonDocument(payload).toJson(QJsonDocument::Compact);
    // Starting a batch clears the previous terminal outcome so a new run does
    // not read as the old one finishing.
    m_downloadOutcome.clear();
    m_downloadMessage.clear();
    m_downloadSucceeded.clear();
    m_downloadFailed.clear();
    emit downloadChanged();
#if defined(Q_OS_ANDROID)
    // The Java side resolves its own Context through QtNative.activity(), the
    // same way startIndexing()/stopIndexing() do, so there is no Context to
    // marshal across the boundary here.
    //
    // The payload MUST go as a real jstring: the variadic callStaticMethod does
    // not convert a const char* to a jobject, and passing one aborts the process
    // with "jobject is an invalid JNI transition frame reference". Same
    // fromString(...).object<jstring>() pattern as openUrl() below.
    const QJniObject javaPayload = QJniObject::fromString(QString::fromUtf8(json));
    const bool started = QJniObject::callStaticMethod<jboolean>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "startDictionaryDownload",
        "(Ljava/lang/String;)Z",
        javaPayload.object<jstring>());
    if (!started) {
        // A refused start (no service, bad payload, a batch already running)
        // writes no marker, so nothing would ever end the download. Say so
        // instead of leaving a bar that spins forever.
        m_audioReloadIds.clear();
        m_downloadOutcome = QStringLiteral("failed");
        m_downloadMessage = tr("The download could not be started.");
        emit downloadChanged();
    }
#else
    qInfo() << "[aurelex] startCatalogDownload: the download service is Android-only";
#endif
}

void EngineController::cancelCatalogDownload()
{
#if defined(Q_OS_ANDROID)
    QJniObject::callStaticMethod<void>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "cancelDictionaryDownload",
        "()V");
    // No local flag is set here: the service is the authority on whether a
    // transfer is in flight, and it reports the outcome through the marker.
    // Crucially we do NOT touch processingActive — a cancel of the download
    // queue must never clear the scanning/indexing chain's indication.
#else
    qInfo() << "[aurelex] cancelCatalogDownload: the download service is Android-only";
#endif
}

void EngineController::clearDownloadOutcome()
{
    if (m_downloadOutcome.isEmpty()) return;
    m_downloadOutcome.clear();
    m_downloadMessage.clear();
    m_downloadSucceeded.clear();
    m_downloadFailed.clear();
    emit downloadChanged();
}

void EngineController::setOnboarded(bool v)
{
    if (m_onboarded == v) return;
    m_onboarded = v;
    saveSettings();
    emit onboardedChanged();
}

void EngineController::loadSettings()
{
    QFile f(m_appDir + "/settings.json");
    if (!f.open(QIODevice::ReadOnly)) return;
    const QJsonDocument doc = QJsonDocument::fromJson(f.readAll());
    const QJsonObject obj = doc.object();
    m_onboarded = obj.value("onboarded").toBool(false);
    // Theme mode, newest key first. The legacy keys are read-time fallbacks
    // only — they are never rewritten — so an older build still reads this file
    // unchanged if the user downgrades.
    //   'themeMode'          present: the stored tri-state, taken as-is below.
    //   'userDarkOverride'   true  -> the pre-tri-state app had forced dark.
    //   'darkMode'           true  -> even older forced-dark key.
    // Anything absent or out of range falls back to follow-system, matching the
    // article-zoom clamp below: a hand-edited settings.json must not be able to
    // push the app into a state it has no representation for.
    int mode = kThemeFollowSystem;
    if (obj.contains(QStringLiteral("themeMode"))) {
        const int stored = obj.value(QStringLiteral("themeMode")).toInt(kThemeFollowSystem);
        if (stored == kThemeFollowSystem || stored == kThemeLight || stored == kThemeDark)
            mode = stored;
    } else if (obj.value(QStringLiteral("userDarkOverride")).toBool(false)
               || obj.value(QStringLiteral("darkMode")).toBool(false)) {
        mode = kThemeDark;
    }
    m_themeMode = mode;
    // loadSettings() runs from the gd_init watcher, i.e. AFTER the QML bindings
    // are live, so a direct assignment above never reaches them. Without this
    // notify the dock's theme cell keeps advertising the default target until
    // the first tap snaps it back into sync. Same idiom as onboardedChanged()
    // at the end of this function. applyEffectiveDark() below is what actually
    // repaints; this only re-syncs the control.
    emit themeModeChanged();
    // Article reflow zoom: default 100 when absent; snap/clamp the persisted
    // value so a hand-edited settings.json can't push it out of range.
    setArticleZoom(obj.value("articleZoom").toDouble(100.0));
    // Remote catalog URL: compiled-in default when the key is absent. There is
    // deliberately no migration — an app built before this key existed simply
    // takes the default, and the saveSettings() below writes it back on the
    // first run after the upgrade. HTTPS only: a persisted non-HTTPS value is
    // ignored, because the app has no cleartext exception for the catalog
    // (network_security_config.xml is deliberately unchanged).
    m_remoteCatalogUrl = obj.value(QStringLiteral("remoteCatalogUrl")).toString();
    if (!m_remoteCatalogUrl.startsWith(QLatin1String("https://"), Qt::CaseInsensitive))
        m_remoteCatalogUrl = QLatin1String(kDefaultRemoteCatalogUrl);
    // Last-good catalog manifest, so a previously-read catalog still renders
    // (read-only) while offline. A cached copy that no longer parses is
    // dropped rather than shown half-populated.
    const QJsonValue cached = obj.value(QStringLiteral("remoteCatalogManifest"));
    if (cached.isString()) {
        const QByteArray raw = cached.toString().toUtf8();
        RemoteCatalog::Manifest m;
        QString err;
        if (RemoteCatalog::parseManifest(raw, &m, &err)) {
            m_manifest = m;
            m_manifestRaw = QString::fromUtf8(raw);
            m_manifestValid = true;
        } else {
            qWarning() << "[aurelex] cached remote catalog no longer parses; dropping it:" << err;
        }
        m_manifestFetched = QDateTime::fromString(
            obj.value(QStringLiteral("remoteCatalogFetchedAt")).toString(), Qt::ISODate);
    }
    // Reachability is part of the cached catalog (design D11): a manifest we
    // fetched successfully must stay usable across a restart. Without this, a
    // restart resets reachability to false, so the cached list renders
    // read-only and every download is refused until an explicit re-probe even
    // though nothing has changed. A real outage still clears it on the next
    // failed probe, and individual download attempts fail with their own
    // reason regardless.
    m_catalogReachable = m_manifestValid
            && obj.value(QStringLiteral("remoteCatalogReachable")).toBool(false);
    // Installed catalog content identity (inert): entryId -> { fileName: sha256 },
    // written when a catalog download succeeds. Nothing reads it yet; it is the
    // baseline a future update check compares the manifest against. See
    // public-catalog-hosting.
    const QJsonValue installedDigests =
            obj.value(QStringLiteral("catalogInstalledDigests"));
    if (installedDigests.isObject())
        m_installedDigests = installedDigests.toObject();
    // One-off import model: a persisted "sources" array (from older builds) is
    // intentionally ignored — the app-private staged copies remain on disk and
    // are the single source of dictionaries; they re-scan on startup.
    saveSettings();
    applyEffectiveDark();
    emit onboardedChanged();
    refreshCatalogEntries();
}

void EngineController::saveSettings()
{
    QFile f(m_appDir + "/settings.json");
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return;
    QJsonObject obj;
    obj.insert("themeMode", m_themeMode);
    obj.insert("onboarded", m_onboarded);
    obj.insert("articleZoom", m_articleZoom);
    obj.insert("remoteCatalogUrl", m_remoteCatalogUrl);
    // Only ever a manifest that PARSED: a rejected document must not become the
    // cache, or a bad fetch would poison every later offline read. The exact
    // bytes are stored (not a re-serialization), so the offline copy is the
    // same document the parser approved.
    if (m_manifestValid) {
        obj.insert("remoteCatalogManifest", m_manifestRaw);
        obj.insert("remoteCatalogFetchedAt", m_manifestFetched.toString(Qt::ISODate));
        obj.insert("remoteCatalogReachable", m_catalogReachable);
    }
    // Installed catalog content identity (inert): entryId -> { fileName: sha256 }.
    if (!m_installedDigests.isEmpty())
        obj.insert("catalogInstalledDigests", m_installedDigests);
    f.write(QJsonDocument(obj).toJson(QJsonDocument::Compact));
}

void EngineController::cacheManifest()
{
    // Called only after a successful parse; saveSettings() re-emits the parsed
    // manifest (and its fetch time) into settings.json.
    saveSettings();
}

void EngineController::recordInstalledDigests(const QStringList &entryNames)
{
    // Inert bookkeeping (public-catalog-hosting): remember, per catalog entry, the
    // SHA-256 of the required dictionary files we just installed, so a future
    // update check can compare manifest vs installed content without re-reading
    // multi-GB files. The download service reports success by entry NAME, and the
    // generator guarantees names are unique, so the entry is found by name.
    if (!m_manifestValid || entryNames.isEmpty())
        return;
    bool changed = false;
    for (const QString &name : entryNames) {
        const RemoteCatalog::Entry *entry = nullptr;
        for (const RemoteCatalog::Entry &e : m_manifest.entries) {
            if (e.name == name) { entry = &e; break; }
        }
        if (!entry)
            continue;
        QJsonObject files;
        for (const RemoteCatalog::File &f : entry->files) {
            if (!f.required || f.role != QLatin1String("dictionary"))
                continue;
            // No digest in the manifest means nothing to record; the entry is
            // simply not identifiable for a future update.
            if (f.sha256.isEmpty())
                continue;
            files.insert(f.name, f.sha256);
        }
        if (files.isEmpty())
            continue;
        if (m_installedDigests.value(entry->id).toObject() == files)
            continue;
        m_installedDigests.insert(entry->id, files);
        changed = true;
    }
    if (changed)
        saveSettings();
}

void EngineController::recordHistory(const QString &word)
{
    if (word.isEmpty()) return;
    // Dedupe + move-to-front (same word+group is a single entry; the older one
    // is dropped), cap at 500.
    const int group = m_activeGroupId;
    QVariantList updated;
    QVariantMap head;
    head.insert("word", word);
    head.insert("group", group);
    updated.append(head);
    for (const QVariant &entry : m_history) {
        const QVariantMap m = entry.toMap();
        if (m.value("word").toString() == word && m.value("group").toInt() == group)
            continue;
        updated.append(entry);
    }
    while (updated.size() > 500) updated.removeLast();
    setHistory(updated);
    saveHistory();
}

void EngineController::toggleFavorite(const QString &word)
{
    if (word.isEmpty()) return;
    const int group = m_activeGroupId;
    // Remove an existing favorite with the same word+group, else add it.
    QVariantList updated;
    bool present = false;
    for (const QVariant &entry : m_favorites) {
        const QVariantMap m = entry.toMap();
        if (m.value("word").toString() == word && m.value("group").toInt() == group) {
            present = true;
            continue;
        }
        updated.append(entry);
    }
    if (!present) {
        QVariantMap m;
        m.insert("word", word);
        m.insert("group", group);
        updated.append(m);
    }
    setFavorites(updated);
    saveFavorites();
}

void EngineController::removeHistory(const QString &word)
{
    QVariantList updated;
    for (const QVariant &entry : m_history) {
        if (entry.toMap().value("word").toString() == word) continue;
        updated.append(entry);
    }
    setHistory(updated);
    saveHistory();
}

void EngineController::removeHistoryEntry(const QString &word, int group)
{
    QVariantList updated;
    for (const QVariant &entry : m_history) {
        const QVariantMap m = entry.toMap();
        if (m.value("word").toString() == word && m.value("group").toInt() == group)
            continue;
        updated.append(entry);
    }
    setHistory(updated);
    saveHistory();
}

void EngineController::toggleFavoriteEntry(const QString &word, int group)
{
    QVariantList updated;
    bool present = false;
    for (const QVariant &entry : m_favorites) {
        const QVariantMap m = entry.toMap();
        if (m.value("word").toString() == word && m.value("group").toInt() == group) {
            present = true;
            continue;
        }
        updated.append(entry);
    }
    if (!present) {
        QVariantMap m;
        m.insert("word", word);
        m.insert("group", group);
        updated.append(m);
    }
    setFavorites(updated);
    saveFavorites();
}

void EngineController::clearHistory()
{
    setHistory(QVariantList());
    saveHistory();
}

QString EngineController::readPendingLookup()
{
    // Consume-and-return variant (kept for the QML invokable API). The poller
    // (pollPendingLookup) is the primary consumer now.
    const QString word = peekPendingLookup();
    if (!word.isEmpty()) {
        const QString path = m_appDir + QStringLiteral("/../shared_prefs/intent.xml");
        QFile f(path);
        f.remove();
    }
    return word;
}

QString EngineController::peekPendingLookup() const
{
    // The Java shell writes the captured lookup word into
    // shared_prefs/intent.xml as a standard SharedPreferences XML file.
    if (m_appDir.isEmpty()) return QString();
    const QString path = m_appDir + QStringLiteral("/../shared_prefs/intent.xml");
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) return QString();
    const QString xml = QString::fromUtf8(f.readAll());
    f.close();

    QXmlStreamReader xr(xml);
    QString word;
    bool inLookup = false;
    while (!xr.atEnd()) {
        const auto tok = xr.readNext();
        if (tok == QXmlStreamReader::StartElement
            && xr.name() == QStringLiteral("string")
            && xr.attributes().value(QStringLiteral("name")) == QStringLiteral("lookupText")) {
            inLookup = true;
        } else if (tok == QXmlStreamReader::Characters && inLookup) {
            word = xr.text().toString();
        } else if (tok == QXmlStreamReader::EndElement && inLookup) {
            break;
        }
    }
    return word;
}

bool EngineController::peekPendingClipboardFlag() const
{
    if (m_appDir.isEmpty()) return false;
    const QString path = m_appDir + QStringLiteral("/../shared_prefs/intent.xml");
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) return false;
    const QString xml = QString::fromUtf8(f.readAll());
    f.close();

    QXmlStreamReader xr(xml);
    while (!xr.atEnd()) {
        const auto tok = xr.readNext();
        if (tok == QXmlStreamReader::StartElement
            && xr.name() == QStringLiteral("boolean")
            && xr.attributes().value(QStringLiteral("name")) == QStringLiteral("lookupClipboard")) {
            return xr.attributes().value(QStringLiteral("value")) == QStringLiteral("true");
        }
    }
    return false;
}

void EngineController::pollPendingLookup()
{
    if (m_appDir.isEmpty()) return;
    const QString path = m_appDir + QStringLiteral("/../shared_prefs/intent.xml");

    // Heal the system bar icon contrast if the WM/Qt reset it (cheap: only
    // rewrites when the read-back appearance drifted from our desired state).
    syncSystemBarAppearance();

    // Sample the Android system dark/light state (Qt 6.6 QPA can't detect it
    // natively); the activity's onConfigurationChanged fires on a live switch,
    // and this poll (500ms) picks it up for a near-immediate re-palette.
    updateSystemDark();

    // Re-read the safe-area insets and notify QML when any moved (rotation, the
    // IME, split screen, a foldable unfolding). Must stay a poll and not a resize
    // hook: the two landscape orientations have identical window dimensions, so
    // the cutout can move sides with no resize signal at all.
    pollInsets();

    // Staging-progress + one-off-import trigger: the StagingService copies a
    // picked folder into app-private storage and holds its start marker while
    // doing so (the Dicts tab shows "Preparing dictionaries…"). When the copy
    // finishes the marker clears; that transition triggers a scan of the staged
    // root so the imported dictionaries load + are indexed.
    {
        const bool active = peekStagingActive();
        if (active && !m_stagingActive) {
            setStagingActive(true);
            // A new pick supersedes the last batch's report: clear the results
            // before the new ones are collected, so the banner never describes an
            // older import (report-import-results, design D3).
            setScanFailures({});
            // Remember the staged roots that already exist. The scan that follows
            // can then tell which dictionaries this pick brought in and apply the
            // skip/reject rule to them; a dictionary whose staged ancestor is not
            // in this set is a candidate (resolve-duplicate-dictionaries D3).
            m_prePickStagedDirs.clear();
            {
                const QDir sr(m_stagedDir);
                const QStringList dirs = sr.entryList(QDir::Dirs | QDir::NoDotAndDotDot);
                for (const QString &d : dirs)
                    m_prePickStagedDirs.insert(sr.filePath(d));
            }
            m_prePickSnapshotValid = true;
            // Start the continuous processing indicator; runScan/autoIndexMissing
            // keep it raised across the phase hand-offs and it is lowered only
            // when the whole staging -> scan -> index chain is done.
            setProcessingActive(true);
        } else if (!active && m_stagingActive) {
            setStagingActive(false);
            removeStagingFile();
            if (m_ready) {
                runScan();
            } else {
                // No scan will follow to carry the chain; clear it explicitly.
                setProcessingActive(false);
            }
        }
    }

    // The IndexingService finished its stop (marker written when the bulk build
    // completed). Consume it so a stale marker never re-triggers later. The
    // worker's watcher owns buildingFts/reset, so this doesn't touch them.
    if (peekPendingIndexingDone()) {
        removePendingIndexingFile();
    }

    // Remote-catalog download progress: the Android DictionaryDownloadService
    // writes shared_prefs/download.xml as it copies. Read it here so progress /
    // cancel / outcomes render without the service reaching into QML, and so a
    // finished batch arms the rescan the tail owes (see syncDownloadState).
    syncDownloadState();

    // A batch that finished while the engine was still initializing (or while a
    // tail was live) owes its reload; run it now that the engine is ready and
    // idle. Kept in the poller, not in syncDownloadState, because "ready and
    // idle" can become true many ticks after the outcome was reported.
    if (m_stagedRescanPending && m_ready && !m_processingActive) {
        m_stagedRescanPending = false;
        if (!m_audioReloadIds.isEmpty()) {
            const QStringList ids = m_audioReloadIds;
            m_audioReloadIds.clear();
            qInfo().noquote() << "[aurelex] reloading for new resources (deferred):" << ids;
            reloadDictionariesForResources(ids);
        } else {
            qInfo() << "[aurelex] running the rescan a finished download owed";
            runScan();
        }
    }

    // A concrete word (share / PROCESS_TEXT / deep link) takes priority over
    // the clipboard marker; each Java capture clears the prefs file, so at most
    // one request is ever pending.
    const QString word = peekPendingLookup();
    if (!word.isEmpty()) {
        if (!m_ready) return; // engine still initializing; retry on a later tick
        QFile f(path);
        f.remove();
        qInfo() << "[aurelex] pending lookup:" << word;
        lookup(word);
        return;
    }

    // Clipboard-lookup marker (QS tile): the tile can't read the clipboard
    // (no window focus), so it just signals us; read it here once the app has
    // window focus. Retry briefly when focus/clipboard aren't ready yet.
    if (peekPendingClipboardFlag()) {
        if (!m_ready) return; // engine still initializing; retry on a later tick
        const QString clip = clipboardText().trimmed();
        if (clip.isEmpty() && m_clipboardRetries < 10) {
            ++m_clipboardRetries;
            return;
        }
        m_clipboardRetries = 0;
        QFile f(path);
        f.remove();
        if (!clip.isEmpty()) {
            qInfo() << "[aurelex] clipboard lookup:" << clip;
            lookup(clip);
        }
    }
}

QString EngineController::clipboardText()
{
    QClipboard *cb = QGuiApplication::clipboard();
    if (!cb) return QString();
    return cb->text();
}

bool EngineController::clipboardHasText()
{
    return !clipboardText().trimmed().isEmpty();
}


// ---------- Folder-scoped storage (SAF) ----------

void EngineController::addDictionaryFolder()
{
#if defined(Q_OS_ANDROID)
    QJniObject::callStaticMethod<void>(
        "org/aurelex/pocket/dictionary/AurelexActivity",
        "pickDictionaryFolder",
        "()V");
#else
    qInfo() << "[aurelex] addDictionaryFolder: SAF picker is Android-only";
#endif
}
