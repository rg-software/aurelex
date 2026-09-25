#include "EngineController.hpp"
#include "ArticleServer.hpp"

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
#include <QXmlStreamReader>
#include <QGuiApplication>
#include <QThread>
#include <cmath>
#include <algorithm>
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
    // gd_fts_progress), which the FTS build holds for the whole dictionary. On
    // the UI thread that means every tick can block behind the build, so a fast
    // (400ms) cadence was stuttering the UI for no visible benefit. TODO: this
    // contention is the main "search unusable while indexing" cause — the real
    // fix is to stop holding g_engineMutex across makeFTSIndex (or move this
    // poll off the UI thread); see docs/ROADMAP.md.
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
    m_lastError = e;
    emit lastErrorChanged();
}

void EngineController::setDictionaries(const QVariantList &list) {
    m_dictionaries = list;
    qInfo() << "[aurelex] setDictionaries count=" << list.size();
    emit dictionariesChanged();
}

void EngineController::setGroups(const QVariantList &list) {
    m_groups = list;
    // Group membership edits change which dictionaries a lookup sees.
    clearArticleCache();
    qInfo() << "[aurelex] setGroups count=" << list.size();
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

void EngineController::collectScanFailures() {
    // gd_scan_failures takes g_engineMutex, held by the FTS worker for the whole
    // duration of a large dictionary's index build. Never call it on the UI
    // thread (would freeze the app); enumerate off-thread and set on a watcher.
    QFuture<QVariantList> f = QtConcurrent::run([]{
        char buf[16384];
        const int n = gd_scan_failures(buf, static_cast<int>(sizeof(buf)));
        QVariantList list;
        if (n <= 0) return list;
        const QString joined = QString::fromLocal8Bit(buf);
        const QStringList lines = joined.split('\n', Qt::SkipEmptyParts);
        for (const QString &path : lines) {
            QVariantMap m;
            m.insert("file", path);
            list.append(m);
        }
        return list;
    });
    auto *w = new QFutureWatcher<QVariantList>(this);
    connect(w, &QFutureWatcher<QVariantList>::finished, this, [this, w]{
        setScanFailures(w->result());
        w->deleteLater();
    });
    w->setFuture(f);
}

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
    QFuture<QPair<int, int>> f = QtConcurrent::run([stagedBase]{
        int total = 0;
        if (QDir(stagedBase).exists())
            gd_scan_dicts(stagedBase.toLocal8Bit().constData());
        total = gd_dict_count();
        return QPair<int, int>(0, total);
    });
    auto *w = new QFutureWatcher<QPair<int, int>>(this);
    connect(w, &QFutureWatcher<QPair<int, int>>::finished, this, [this, w]{
        m_scanWatchdog.stop();
        const QPair<int, int> result = w->result();
        qInfo() << "[aurelex] scan done; gd_dict_count =" << result.second;
        setDictCount(result.second);
        setScanningActive(false);
        w->deleteLater();
        // Surface ANY dictionary files that failed to load (corrupt/truncated)
        // so the user knows a dictionary is missing and can re-import the folder.
        collectScanFailures();
        if (result.first > 0 || result.second > 0) {
            refreshDictionaries();
            refreshGroups();
        }
        // Auto-build full-text indexes for any dictionary that lacks one, so
        // search + FTS work without a manual per-dict "Index" button. Runs
        // sequentially off-thread; the UI's buildingFts progress bar covers it.
        autoIndexMissing();
    });
    w->setFuture(f);
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
    // gd_fts_index_state/gd_dict_id take g_engineMutex, which the running FTS
    // worker holds for the whole duration of a large dictionary build. Doing
    // this on the UI thread would freeze the app. Deliver the list via a watcher
    // (runs on the UI thread) which then only touches m_ftsQueue (no engine
    // calls). IDs are stored, not engine indices, so removal mid-run can't
    // shift/desync the queue (see ensureFtsWorker).
    QFuture<QStringList> f = QtConcurrent::run([]{
        QStringList ids;
        const int n = gd_dict_count();
        for (int i = 0; i < n; ++i) {
            int state = -1;
            if (gd_fts_index_state(i, &state) == 0 && state == 1) {
                char idb[128] = {0};
                if (gd_dict_id(i, idb, static_cast<int>(sizeof(idb))) == 0)
                    ids.append(QString::fromLocal8Bit(idb));
            }
        }
        return ids;
    });
    auto *w = new QFutureWatcher<QStringList>(this);
    connect(w, &QFutureWatcher<QStringList>::finished, this, [this, w]{
        const QStringList missing = w->result();
        w->deleteLater();
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
        char idb[128] = {0}, nb[256] = {0}, fb[512] = {0};
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
                gd_fts_index(idx);
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
            // Batch genuinely done: end the continuous processing chain so the
            // Dicts banner clears. No phase hand-off follows, so this is the
            // single place the whole staging -> scan -> index lifecycle ends.
            setProcessingActive(false);
            // Indexing + scanning finished: at this point the staged tree is
            // consistent, so purge any leftover temporary staging dirs (partial
            // copies from a killed/interrupted stage). See the "clear stale
            // staging leftovers" intent — this is a safe cleanup moment.
            purgeStagingTmp();
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
    const QString indexDir = appDir + "/index";
    QDir().mkpath(indexDir);
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
        std::vector<char> name(256);
        std::vector<char> file(512);
        std::vector<char> lf(128), lt(128);
        for (int i = 0; i < n; ++i) {
            const int rn = gd_dict_info(i, name.data(), static_cast<int>(name.size()),
                                        file.data(), static_cast<int>(file.size()));
            if (rn != 0) continue;
            QVariantMap m;
            m.insert("name", QString::fromLocal8Bit(name.data()));
            m.insert("source", QString::fromLocal8Bit(file.data()));
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
    if (!m_ready || index < 0 || index >= m_dictionaries.size()) return;
    // Capture the dictionary id (engine mutex) + its primary source file path
    // BEFORE gd_remove_dict shifts indices. The id capture runs off-thread so
    // the UI never blocks behind a long FTS build holding the engine mutex.
    const QVariantMap removed = m_dictionaries.at(index).toMap();
    const QString sourceFile = removed.value("source").toString();
    const QString removedName = removed.value("name").toString();
    qInfo().noquote() << "[aurelex] removeDictionary requested:"
                      << removedName << "src=" << sourceFile << "idx=" << index;
    const QString stagedRoot = m_stagedDir;
    const QString appDir = m_appDir;

    QFuture<QPair<QString, QPair<int, int>>> f = QtConcurrent::run([index]{
        char idbuf[128] = {0};
        QString id;
        if (gd_dict_id(index, idbuf, static_cast<int>(sizeof(idbuf))) == 0)
            id = QString::fromLocal8Bit(idbuf);
        const int rc = gd_remove_dict(index);
        return QPair<QString, QPair<int, int>>(id, QPair<int, int>(rc, gd_dict_count()));
    });
    auto *w = new QFutureWatcher<QPair<QString, QPair<int, int>>>(this);
    connect(w, &QFutureWatcher<QPair<QString, QPair<int, int>>>::finished, this,
            [this, w, sourceFile, removedName, stagedRoot, appDir]{
        const QPair<QString, QPair<int, int>> result = w->result();
        const QString dictId = result.first;
        const int rc = result.second.first;
        const int count = result.second.second;
        qInfo().noquote() << "[aurelex] removeDictionary result: rc=" << rc
                          << "name=" << removedName << "id=" << dictId
                          << "remaining=" << count;
        if (rc == 0) {
            // Permanent delete: remove the app's copy + its index cache.
            deleteDictionaryFiles(sourceFile, dictId, stagedRoot, appDir);
            // Also drop the id from the still-running FTS queue so a removed
            // dictionary is never indexed by a worker that already popped it.
            if (!dictId.isEmpty()) {
                QMutexLocker lock(&m_ftsQueueMutex);
                m_ftsQueue.removeAll(dictId);
            }
            refreshDictionaries();
            refreshGroups();
            setDictCount(count);
        } else {
            setLastError(QStringLiteral("remove_dict failed (rc=%1)").arg(rc));
        }
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::deleteDictionaryFiles(const QString &sourceFile,
                                             const QString &dictId,
                                             const QString &stagedRoot,
                                             const QString &appDir) {
    // Delete the engine's index cache for this dictionary: files/index<id> and
    // files/index<id>_FTS_x (and any _temp) live directly in the app dir.
    if (!dictId.isEmpty() && !appDir.isEmpty()) {
        QDir dir(appDir);
        const QStringList matches = dir.entryList(
            QStringList() << (QStringLiteral("index") + dictId + QLatin1Char('*')));
        for (const QString &entry : matches) {
            const QString full = dir.filePath(entry);
            QFileInfo fi(full);
            if (fi.isDir()) QDir(full).removeRecursively();
            else QFile::remove(full);
            qInfo() << "[aurelex] removed index entry" << full;
        }
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
        if (!stagedDir.isEmpty()) {
            bool shared = false;
            for (const QVariant &v : m_dictionaries) {
                const QString s = v.toMap().value("source").toString();
                if (s != sourceFile && (s.startsWith(stagedDir + QLatin1Char('/'))
                                        || s == stagedDir)) {
                    shared = true;
                    break;
                }
            }
            if (!shared) {
                qInfo() << "[aurelex] removing staged copy dir" << stagedDir;
                QDir(stagedDir).removeRecursively();
            } else {
                qInfo() << "[aurelex] staged copy dir kept (shared by siblings)"
                        << stagedDir;
            }
        }
    }
}

void EngineController::purgeStagingTmp() {
    // Remove leftover temporary staging dirs (files/staging-tmp/*). These only
    // ever hold in-progress copies; once scanning + indexing have finished they
    // are guaranteed stale, so deleting them keeps app storage clean.
    const QString tmpRoot = m_stagedDir + QStringLiteral("/../staging-tmp");
    QDir dir(tmpRoot);
    if (!dir.exists()) return;
    qInfo() << "[aurelex] purging stale staging-tmp";
    for (const QString &entry : dir.entryList(QDir::Dirs | QDir::NoDotAndDotDot))
        QDir(dir.filePath(entry)).removeRecursively();
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
    connect(w, &QFutureWatcher<int>::finished, this, [this, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] deleteGroup done rc=" << rc;
        if (rc == 0) refreshGroups();
        else setLastError(QStringLiteral("group_delete failed (rc=%1)").arg(rc));
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
        std::vector<char> name(256);
        std::vector<char> file(512);
        for (int i = 0; i < n; ++i) {
            if (gd_dict_info(i, name.data(), static_cast<int>(name.size()),
                             file.data(), static_cast<int>(file.size())) != 0) continue;
            QVariantMap m;
            m.insert("index", i);
            m.insert("name", QString::fromLocal8Bit(name.data()));
            m.insert("source", QString::fromLocal8Bit(file.data()));
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
    // variable that gdSetDarkMode() flips, so the whole WebView backgrounds
    // match the app theme on a live dark/light switch (a fully-transparent html
    // would show the native WebView's own white underneath).
    const QString plainCss = QStringLiteral(
        R"(<style>
html, body { background: var(--gd-bg, #ffffff) !important; }
/* Clear the inline nav toolbar: the WebView surface starts right under it, and
   without this the first line of the article (the dictionary-name heading) can
   tuck under the toolbar's buttons. */
body { padding-top: 8px !important; }
.gdarticle { border: none !important; border-radius: 0 !important;
             background: transparent !important; box-shadow: none !important;
             padding: 0 !important;
             margin-bottom: 0.6em !important; }
</style>
)");
    const QString darkInit = m_darkMode ? QStringLiteral("1") : QStringLiteral("0");
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
  window.gdSetDarkMode=function(v){
    v=!!v;
    if(v===window.__gdDarkMode)return;
    window.__gdDarkMode=v;
    var head=document.head||document.documentElement;
    if(document.documentElement)document.documentElement.style.setProperty('--gd-bg', v?'#242526':'#ffffff');
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
  };
  if(window.__gdDarkMode)window.gdSetDarkMode(1);
})();
</script>
)").arg(base).arg(darkInit);

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
        out.insert(headEnd, zoomCtrl + plainCss + darkCtrl);
    else
        out.append(zoomCtrl + plainCss + darkCtrl);
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
            std::vector<char> buf(256);
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

QVariantList EngineController::ftsSearch(const QString &query, int mode, int groupId, bool wholeWords)
{
    if (!m_ready) return QVariantList();
    if (query.isEmpty()) return QVariantList();
    // In Xapian's wildcard mode a term without a trailing `*` matches exactly,
    // so `boo` misses `book`. By default (prefix search) we append a `*` to
    // terms lacking one; with wholeWords=true we leave the query exact.
    QString norm = query;
    if (mode == 2 && !wholeWords) {
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
    connect(w, &QFutureWatcher<QVariantList>::finished, this, [this, query, w]{
        emit ftsSearchReady(query, w->result());
        w->deleteLater();
    });
    w->setFuture(f);
    return QVariantList();
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
    // Unknown/deleted group id → treat as "All".
    return tr("All");
}

void EngineController::setUserDarkOverride(bool on)
{
    if (m_userDarkOverride == on) return;
    m_userDarkOverride = on;
    saveSettings();
    applyEffectiveDark();
    emit userDarkOverrideChanged();
}

void EngineController::toggleDarkOverride()
{
    // The manual D toggle: force dark when following system, else return to
    // following the system theme.
    qInfo("toggleDarkOverride: %d -> %d", int(m_userDarkOverride), int(!m_userDarkOverride));
    setUserDarkOverride(!m_userDarkOverride);
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

// Effective dark = manual override OR system dark. Drives the Material.theme
// palette (QML) and the engine preference. The OPEN article flips in place via
// gdSetDarkMode() (rewriteArticleUrls always injects the dark controller), so
// no re-lookup/reload is needed here — only the engine preference is kept in
// sync off-thread for any future HTML generation.
void EngineController::applyEffectiveDark()
{
    m_darkMode = m_userDarkOverride || m_systemDark;
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
    // Migrate the old bumped 'darkMode' key to the explicit userDarkOverride
    // (absent = follow system). A persisted darkMode=true means the user had
    // forced dark; map that onto an override so the old toggle keeps working.
    if (obj.contains("userDarkOverride"))
        m_userDarkOverride = obj.value("userDarkOverride").toBool(false);
    else if (obj.value("darkMode").toBool(false))
        m_userDarkOverride = true;
    // Article reflow zoom: default 100 when absent; snap/clamp the persisted
    // value so a hand-edited settings.json can't push it out of range.
    setArticleZoom(obj.value("articleZoom").toDouble(100.0));
    // One-off import model: a persisted "sources" array (from older builds) is
    // intentionally ignored — the app-private staged copies remain on disk and
    // are the single source of dictionaries; they re-scan on startup.
    saveSettings();
    applyEffectiveDark();
    emit onboardedChanged();
}

void EngineController::saveSettings()
{
    QFile f(m_appDir + "/settings.json");
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return;
    QJsonObject obj;
    obj.insert("userDarkOverride", m_userDarkOverride);
    obj.insert("onboarded", m_onboarded);
    obj.insert("articleZoom", m_articleZoom);
    f.write(QJsonDocument(obj).toJson(QJsonDocument::Compact));
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

    // Staging-progress + one-off-import trigger: the StagingService copies a
    // picked folder into app-private storage and holds its start marker while
    // doing so (the Dicts tab shows "Preparing dictionaries…"). When the copy
    // finishes the marker clears; that transition triggers a scan of the staged
    // root so the imported dictionaries load + are indexed.
    {
        const bool active = peekStagingActive();
        if (active && !m_stagingActive) {
            setStagingActive(true);
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
