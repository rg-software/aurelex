#include "EngineController.hpp"
#include "ArticleServer.hpp"

#include <QtConcurrent>
#include <QStandardPaths>
#include <QDir>
#include <QDebug>
#include <QVariantMap>
#include <QPair>
#include <QFile>
#include <QClipboard>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonValue>
#include <QXmlStreamReader>
#include <QGuiApplication>
#if defined(Q_OS_ANDROID)
#include <QJniObject>
#endif
EngineController::EngineController(QObject *parent)
    : QObject(parent)
{
    // Incoming-lookup poller: AurelexActivity writes shared_prefs/intent.xml
    // for every share/deep-link/PROCESS_TEXT/tile intent (cold or warm). Consume
    // it here as soon as the engine is ready; words arriving before gd_init
    // completes stay in the file and are picked up on a later tick.
    connect(&m_pollTimer, &QTimer::timeout, this, &EngineController::pollPendingLookup);
    m_pollTimer.start(500);

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
    m_ftsProgressTimer.setInterval(400);
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

EngineController::~EngineController() = default;

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
    qInfo() << "[aurelex] setDictionaries count=" << list.size()
            << " names=" << (list.isEmpty() ? QString() : list.first().toMap().value("name").toString());
    emit dictionariesChanged();
}

void EngineController::setGroups(const QVariantList &list) {
    m_groups = list;
    qInfo() << "[aurelex] setGroups count=" << list.size();
    emit groupsChanged();
}

void EngineController::setActiveGroupId(int id) {
    if (m_activeGroupId == id) return;
    m_activeGroupId = id;
    emit activeGroupChanged();
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
            "aurelex/android/AurelexActivity",
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
    // Show "Scanning dictionaries…" while the carve loads dicts so the Dicts
    // processing banner stays visible continuously from folder pick -> staging
    // -> scan -> indexing.
    setScanningActive(true);
    QFuture<QPair<int, int>> f = QtConcurrent::run([stagedBase]{
        int total = 0;
        if (QDir(stagedBase).exists())
            gd_scan_dicts(stagedBase.toLocal8Bit().constData());
        total = gd_dict_count();
        return QPair<int, int>(0, total);
    });
    auto *w = new QFutureWatcher<QPair<int, int>>(this);
    connect(w, &QFutureWatcher<QPair<int, int>>::finished, this, [this, w]{
        const QPair<int, int> result = w->result();
        qInfo() << "[aurelex] scan ->" << result.first;
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
    if (!m_ready) return;
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
        if (anyNew && !m_ftsWorkerRunning)
            ensureFtsWorker();
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
        "aurelex/android/AurelexActivity",
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
            "aurelex/android/AurelexActivity",
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
        } else {
            ensureFtsWorker();
        }
    });
    w->setFuture(f);
}

void EngineController::initialize(const QString &appDir, const QString &stagedDir) {
    m_appDir = appDir;
    m_stagedDir = stagedDir;
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
    QFuture<QVariantList> f = QtConcurrent::run([]{
        QVariantList list;
        const int n = gd_dict_count();
        list.reserve(n);
        std::vector<char> name(256);
        std::vector<char> file(512);
        for (int i = 0; i < n; ++i) {
            const int rn = gd_dict_info(i, name.data(), static_cast<int>(name.size()),
                                        file.data(), static_cast<int>(file.size()));
            if (rn != 0) continue;
            QVariantMap m;
            m.insert("name", QString::fromLocal8Bit(name.data()));
            m.insert("source", QString::fromLocal8Bit(file.data()));
            list.append(m);
        }
        return list;
    });
    auto *w = new QFutureWatcher<QVariantList>(this);
    connect(w, &QFutureWatcher<QVariantList>::finished, this, [this, w]{
        setDictionaries(w->result());
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::removeDictionary(int index) {
    if (!m_ready || index < 0 || index >= m_dictionaries.size()) return;
    // Capture the dictionary id (engine mutex) + its primary source file path
    // BEFORE gd_remove_dict shifts indices. The id capture runs off-thread so
    // the UI never blocks behind a long FTS build holding the engine mutex.
    const QString sourceFile = m_dictionaries.at(index).toMap().value("source").toString();
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
            [this, w, sourceFile, stagedRoot, appDir]{
        const QPair<QString, QPair<int, int>> result = w->result();
        const QString dictId = result.first;
        const int rc = result.second.first;
        const int count = result.second.second;
        qInfo() << "[aurelex] remove dict" << rc;
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
    // lines/index<id>_FTS_x (and any _temp) live directly in the app dir.
    if (!dictId.isEmpty() && !appDir.isEmpty()) {
        QDir dir(appDir);
        const QStringList matches = dir.entryList(
            QStringList() << (QStringLiteral("index") + dictId + QLatin1Char('*')));
        for (const QString &entry : matches) {
            const QString full = dir.filePath(entry);
            QFileInfo fi(full);
            if (fi.isDir()) QDir(full).removeRecursively();
            else QFile::remove(full);
        }
    }
    // Delete the staged copy's folder (files/staged/<sourceId>) only if no other
    // loaded dictionary still uses it (a single import folder can hold several
    // dictionaries; removing one must not delete its siblings).
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
                qInfo() << "[aurelex] removing staged copy" << stagedDir;
                QDir(stagedDir).removeRecursively();
            }
        }
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
    connect(w, &QFutureWatcher<QPair<int, int>>::finished, this, [this, w]{
        const QPair<int, int> result = w->result();
        const int rc = result.first;
        const int newId = result.second;
        qInfo() << "[aurelex] createGroup rc=" << rc << " id=" << newId;
        if (rc != 0) {
            setLastError(QStringLiteral("group_create failed (rc=%1)").arg(rc));
        } else {
            refreshGroups();
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
    connect(w, &QFutureWatcher<int>::finished, this, [this, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] renameGroup" << rc;
        if (rc == 0) refreshGroups();
        else setLastError(QStringLiteral("group_rename failed (rc=%1)").arg(rc));
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::deleteGroup(int groupId) {
    if (!m_ready) return;
    QFuture<int> f = QtConcurrent::run([groupId]{
        return gd_group_delete(groupId);
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] deleteGroup" << rc;
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
        if (rc != 0) setLastError(QStringLiteral("group_add_dict failed (rc=%1)").arg(rc));
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
        if (rc != 0) setLastError(QStringLiteral("group_remove_dict failed (rc=%1)").arg(rc));
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
        if (rc != 0) setLastError(QStringLiteral("group_move_dict failed (rc=%1)").arg(rc));
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
    return out;
}

QString EngineController::articleBaseUrl() const {
    return (m_articleServer && m_articleServer->isRunning()) ? m_articleServer->baseUrl() : QString();
}

void EngineController::playAudio(const QString &url) {
#if defined(Q_OS_ANDROID)
    // JNI passthrough to AurelexActivity.playAudio(String) — Android's
    // MediaPlayer plays the loopback URL so the WebView keeps the article.
    const QJniObject javaUrl = QJniObject::fromString(url);
    QJniObject::callStaticMethod<void>(
        "aurelex/android/AurelexActivity",
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
        "aurelex/android/AurelexActivity",
        "stopAudio",
        "()V");
#endif
}

void EngineController::lookup(const QString &word) {
    QFuture<QString> f = QtConcurrent::run([word]{
        std::vector<char> buf(1 << 20);
        const int sz = gd_lookup(word.toLocal8Bit().constData(),
                                 buf.data(), static_cast<int>(buf.size()));
        if (sz <= 0) return QString();
        return QString::fromUtf8(buf.data(), sz);
    });
    auto *w = new QFutureWatcher<QString>(this);
    connect(w, &QFutureWatcher<QString>::finished, this, [this, word, w]{
        const QString html = w->result();
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

void EngineController::lookupInGroup(const QString &word, int groupId) {
    QFuture<QString> f = QtConcurrent::run([word, groupId]{
        std::vector<char> buf(1 << 20);
        const int sz = gd_lookup_in_group(word.toLocal8Bit().constData(), groupId,
                                          buf.data(), static_cast<int>(buf.size()));
        if (sz <= 0) return QString();
        return QString::fromUtf8(buf.data(), sz);
    });
    auto *w = new QFutureWatcher<QString>(this);
    connect(w, &QFutureWatcher<QString>::finished, this, [this, word, w]{
        const QString html = w->result();
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
    // Only the latest request may emit: while the user keeps typing (or the
    // IME rewrites composing text), older results would otherwise land late
    // and repopulate the list with stale content.
    const int gen = ++m_suggestGeneration;
    QFuture<QStringList> f = QtConcurrent::run([prefix]{
        std::vector<char> buf(1 << 16);
        const int n = gd_suggest(prefix.toLocal8Bit().constData(),
                                  buf.data(), static_cast<int>(buf.size()));
        if (n < 0) return QStringList();
        return QString::fromLocal8Bit(buf.data(), strlen(buf.data())).split('\n', Qt::SkipEmptyParts);
    });
    auto *w = new QFutureWatcher<QStringList>(this);
    connect(w, &QFutureWatcher<QStringList>::finished, this, [this, prefix, gen, w]{
        if (gen != m_suggestGeneration) {
            qInfo() << "[aurelex] suggest stale, dropped:" << prefix;
            w->deleteLater();
            return;
        }
        qInfo() << "[aurelex] suggest ready:" << prefix << "count:" << w->result().size();
        emit suggestionsReady(prefix, w->result());
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
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) { setHistory(QStringList()); return; }
    const QJsonDocument doc = QJsonDocument::fromJson(f.readAll());
    QStringList list;
    for (const QJsonValue &v : doc.array()) list.append(v.toString());
    setHistory(list);
}

void EngineController::saveHistory()
{
    const QString path = m_appDir + "/history.json";
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return;
    QJsonArray arr;
    for (const QString &w : m_history) arr.append(w);
    f.write(QJsonDocument(arr).toJson(QJsonDocument::Compact));
}

void EngineController::loadFavorites()
{
    const QString path = m_appDir + "/favorites.json";
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) { setFavorites(QStringList()); return; }
    const QJsonDocument doc = QJsonDocument::fromJson(f.readAll());
    QStringList list;
    for (const QJsonValue &v : doc.array()) list.append(v.toString());
    setFavorites(list);
}

void EngineController::saveFavorites()
{
    const QString path = m_appDir + "/favorites.json";
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return;
    QJsonArray arr;
    for (const QString &w : m_favorites) arr.append(w);
    f.write(QJsonDocument(arr).toJson(QJsonDocument::Compact));
}

void EngineController::setHistory(const QStringList &list)
{
    if (m_history == list) return;
    m_history = list;
    emit historyChanged();
}

void EngineController::setFavorites(const QStringList &list)
{
    if (m_favorites == list) return;
    m_favorites = list;
    emit favoritesChanged();
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

bool EngineController::readSystemDark() const
{
#if defined(Q_OS_ANDROID)
    return QJniObject::callStaticMethod<jboolean>(
        "aurelex/android/AurelexActivity",
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
// palette (QML) and the article CSS (gd_set_dark_mode).
void EngineController::applyEffectiveDark()
{
    m_darkMode = m_userDarkOverride || m_systemDark;
    // Off-thread: gd_set_dark_mode takes the engine mutex, which a concurrent
    // FTS index build may hold for a long time. Never block the UI thread.
    QtConcurrent::run([dark = m_darkMode]{ gd_set_dark_mode(dark ? 1 : 0); });
    emit darkModeChanged();
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
    f.write(QJsonDocument(obj).toJson(QJsonDocument::Compact));
}

void EngineController::recordHistory(const QString &word)
{
    if (word.isEmpty()) return;
    // Dedupe + move-to-front, cap at 100.
    QStringList updated;
    updated.append(word);
    for (const QString &w : m_history) {
        if (w == word) continue;
        updated.append(w);
    }
    while (updated.size() > 100) updated.removeLast();
    setHistory(updated);
    saveHistory();
}

void EngineController::toggleFavorite(const QString &word)
{
    QStringList updated = m_favorites;
    if (updated.contains(word)) updated.removeAll(word);
    else updated.append(word);
    setFavorites(updated);
    saveFavorites();
}

void EngineController::removeHistory(const QString &word)
{
    QStringList updated = m_history;
    updated.removeAll(word);
    setHistory(updated);
    saveHistory();
}

void EngineController::clearHistory()
{
    setHistory(QStringList());
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
        if (active && !m_stagingActive) setStagingActive(true);
        else if (!active && m_stagingActive) {
            setStagingActive(false);
            removeStagingFile();
            if (m_ready) runScan();
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
        "aurelex/android/AurelexActivity",
        "pickDictionaryFolder",
        "()V");
#else
    qInfo() << "[aurelex] addDictionaryFolder: SAF picker is Android-only";
#endif
}
