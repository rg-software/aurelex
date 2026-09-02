#include "EngineController.hpp"

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
    emit buildingFtsChanged();
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
        if (n > 0) {
            refreshDictionaries();
            refreshGroups();
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
        loadSettings();
        loadHistory();
        loadFavorites();
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

void EngineController::refreshGroups() {
    if (!m_ready) {
        qInfo() << "[aurelex] refreshGroups skipped: not ready";
        return;
    }
    qInfo() << "[aurelex] refreshGroups firing";
    QFuture<QVariantList> f = QtConcurrent::run([]{
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
        return list;
    });
    auto *w = new QFutureWatcher<QVariantList>(this);
    connect(w, &QFutureWatcher<QVariantList>::finished, this, [this, w]{
        setGroups(w->result());
        w->deleteLater();
        int active = 0;
        gd_group_active(&active);
        setActiveGroupId(active);
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
    QFuture<int> f = QtConcurrent::run([groupId]{
        return gd_group_set_active(groupId);
    });
    auto *w = new QFutureWatcher<int>(this);
    connect(w, &QFutureWatcher<int>::finished, this, [this, w]{
        const int rc = w->result();
        qInfo() << "[aurelex] setActiveGroup" << rc;
        if (rc == 0) {
            int active = 0;
            gd_group_active(&active);
            setActiveGroupId(active);
        } else {
            setLastError(QStringLiteral("group_set_active failed (rc=%1)").arg(rc));
        }
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

QVariantList EngineController::ftsSearch(const QString &query, int mode, int groupId)
{
    if (!m_ready) return QVariantList();
    if (query.isEmpty()) return QVariantList();
    qInfo() << "[aurelex] ftsSearch query='" << query << "' mode=" << mode << " group=" << groupId;
    QFuture<QVariantList> f = QtConcurrent::run([query, mode, groupId]{
        std::vector<char> buf(1 << 20);
        const int n = gd_fts_search(query.toLocal8Bit().constData(), mode, groupId,
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

void EngineController::setDarkMode(bool on)
{
    if (m_darkMode == on) return;
    m_darkMode = on;
    gd_set_dark_mode(on ? 1 : 0);
    QFile f(m_appDir + "/settings.json");
    if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        QJsonObject obj;
        obj.insert("darkMode", on);
        obj.insert("onboarded", m_onboarded);
        f.write(QJsonDocument(obj).toJson(QJsonDocument::Compact));
    }
    emit darkModeChanged();
}

void EngineController::setOnboarded(bool v)
{
    if (m_onboarded == v) return;
    m_onboarded = v;
    QFile f(m_appDir + "/settings.json");
    if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        QJsonObject obj;
        obj.insert("darkMode", m_darkMode);
        obj.insert("onboarded", v);
        f.write(QJsonDocument(obj).toJson(QJsonDocument::Compact));
    }
    emit onboardedChanged();
}

void EngineController::loadSettings()
{
    QFile f(m_appDir + "/settings.json");
    if (!f.open(QIODevice::ReadOnly)) return;
    const QJsonDocument doc = QJsonDocument::fromJson(f.readAll());
    m_darkMode = doc.object().value("darkMode").toBool(false);
    m_onboarded = doc.object().value("onboarded").toBool(false);
    gd_set_dark_mode(m_darkMode ? 1 : 0);
    emit darkModeChanged();
    emit onboardedChanged();
}

void EngineController::saveSettings()
{
    QFile f(m_appDir + "/settings.json");
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return;
    QJsonObject obj;
    obj.insert("darkMode", m_darkMode);
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
    // The Java shell writes the captured lookup word into
    // shared_prefs/intent.xml as a standard SharedPreferences XML file.
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

    if (!word.isEmpty()) {
        // Consume: delete the file so the lookup isn't re-triggered.
        f.remove();
    }
    return word;
}

QString EngineController::clipboardText()
{
    QClipboard *cb = QGuiApplication::clipboard();
    if (!cb) return QString();
    return cb->text();
}

