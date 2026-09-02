#include "EngineController.hpp"

#include <QtConcurrent>
#include <QStandardPaths>
#include <QDir>
#include <QDebug>
#include <QVariantMap>

EngineController::EngineController(QObject *parent) : QObject(parent) {}
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

void EngineController::runScan() {
    QFuture<int> f = QtConcurrent::run([staged = m_stagedDir]{
        return gd_scan_dicts(staged.toLocal8Bit().constData());
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, w]{
        const int n = w->result();
        qInfo() << "[aurelex] scan ->" << n;
        setDictCount(n);
        w->deleteLater();
        // After a successful scan, refresh the dictionaries list so the UI
        // reflects the new state without the user having to call refresh.
        if (n > 0) refreshDictionaries();
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
        runScan();
    });
    w->setFuture(f);
}

void EngineController::rescan() {
    if (!m_ready) return;
    runScan();
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
    if (!m_ready) return;
    QFuture<int> f = QtConcurrent::run([index]{
        return gd_remove_dict(index);
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] remove dict" << rc;
        if (rc == 0) {
            // Successful removal: re-fetch list + count.
            refreshDictionaries();
            setDictCount(gd_dict_count());
        } else {
            setLastError(QStringLiteral("remove_dict failed (rc=%1)").arg(rc));
        }
        w->deleteLater();
    });
    w->setFuture(f);
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

QString EngineController::rewriteArticleUrls(const QString &html) const {
    QString out = html;
    out.replace(QStringLiteral("qrc:///"), QStringLiteral("file:///android_asset/"));
    return out;
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
        if (html.isEmpty()) emit articleNotFound(word);
        else emit articleLoaded(word, html);
        w->deleteLater();
    });
    w->setFuture(f);
}

void EngineController::suggest(const QString &prefix) {
    QFuture<QStringList> f = QtConcurrent::run([prefix]{
        std::vector<char> buf(1 << 16);
        const int n = gd_suggest(prefix.toLocal8Bit().constData(),
                                  buf.data(), static_cast<int>(buf.size()));
        if (n < 0) return QStringList();
        return QString::fromLocal8Bit(buf.data(), strlen(buf.data())).split('\n', Qt::SkipEmptyParts);
    });
    auto *w = new QFutureWatcher<QStringList>(this);
    connect(w, &QFutureWatcher<QStringList>::finished, this, [this, prefix, w]{
        emit suggestionsReady(prefix, w->result());
        w->deleteLater();
    });
    w->setFuture(f);
}