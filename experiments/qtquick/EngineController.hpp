#pragma once

#include <QObject>
#include <QString>
#include <QStringList>
#include <QVariantList>
#include <QVariantMap>
#include <QFuture>
#include <QFutureWatcher>

extern "C" {
#include "goldendict.h"
}

// EngineController: QML-facing wrapper around the in-process goldendict engine.
// Owns the engine lifetime; calls are off-thread (QtConcurrent) so the UI
// thread never blocks on the (potentially slow) gd_* C API.
class EngineController : public QObject
{
    Q_OBJECT
    Q_PROPERTY(int dictCount READ dictCount NOTIFY dictCountChanged)
    Q_PROPERTY(bool ready READ ready NOTIFY readyChanged)
    Q_PROPERTY(QString lastError READ lastError NOTIFY lastErrorChanged)
    Q_PROPERTY(QVariantList dictionaries READ dictionaries NOTIFY dictionariesChanged)
    Q_PROPERTY(QVariantList groups READ groups NOTIFY groupsChanged)
    Q_PROPERTY(int activeGroupId READ activeGroupId NOTIFY activeGroupChanged)
public:
    explicit EngineController(QObject *parent = nullptr);
    ~EngineController() override;

    int dictCount() const { return m_dictCount; }
    bool ready() const { return m_ready; }
    QString lastError() const { return m_lastError; }
    QVariantList dictionaries() const { return m_dictionaries; }
    QVariantList groups() const { return m_groups; }
    int activeGroupId() const { return m_activeGroupId; }

    // Initialise the engine. `configDir`/`indexDir` are usually the same
    // AppLocalDataLocation; `stagedDir` is the dict folder the app stages to.
    Q_INVOKABLE void initialize(const QString &appDir, const QString &stagedDir);
    Q_INVOKABLE void rescan();

    // Refresh the dictionaries list (off-thread; result delivered via
    // dictionariesChanged signal). No-op if the engine isn't ready.
    Q_INVOKABLE void refreshDictionaries();

    // Remove / reorder. Indices match dictionaries()'s list. Both are
    // synchronous wrappers around the engine C API (fast in practice); we
    // route them through QtConcurrent anyway so they never block the UI thread.
    Q_INVOKABLE void removeDictionary(int index);
    Q_INVOKABLE void moveDictionary(int from, int to);

    // Refresh the groups list + the active group id.
    Q_INVOKABLE void refreshGroups();

    // Group CRUD. `name` is required for create; rename/replace take a new
    // string; delete and setActive act on the integer group id returned by
    // gd_group_create (and listed in groups()). Membership / reordering is
    // deferred to a follow-up: for the experiment gate, the groups list + active
    // toggle prove the UI/controller pattern; dict-in-group wiring (Q_INVOKABLE
    // wrappers around gd_group_add/remove/move_dict) is the next slice.
    Q_INVOKABLE void createGroup(const QString &name);
    Q_INVOKABLE void renameGroup(int groupId, const QString &newName);
    Q_INVOKABLE void deleteGroup(int groupId);
    Q_INVOKABLE void setActiveGroup(int groupId);

    // Full-text search. Index build (`gd_fts_index`) is heavy and runs on the
    // worker thread; the controller's `buildingFts` Q_PROPERTY flips while it's
    // in flight and `ftsIndexChanged(dictIndex)` fires on completion. State queries
    // are fast; `ftsIndexState` returns 0 (built) or 1 (missing/stale) for a
    // dictionary, and `ftsIndexStates` returns the same for all loaded dicts.
    // Search returns QVariantList of {headword, dictName} pairs (newline-separated
    // upstream format, split here). `mode` maps to FTS::SearchMode: 0=xapian
    // syntax, 1=plain, 2=wildcards, 3=regexp.
    Q_INVOKABLE void ftsIndex(int dictIndex);
    Q_INVOKABLE int ftsIndexState(int dictIndex) const;
    Q_INVOKABLE QVariantList ftsIndexStates() const;
    Q_INVOKABLE QVariantList ftsSearch(const QString &query, int mode, int groupId = 0);

    bool buildingFts() const { return m_buildingFts; }

    // Lookup a word. `articleLoaded(word, html)` on success, or
    // `articleNotFound(word)` when the engine returned a "no match" article.
    Q_INVOKABLE void lookup(const QString &word);
    Q_INVOKABLE void suggest(const QString &prefix);

    // Rewrite upstream article asset URLs (qrc:///, :/<module>/) to
    // file:///android_asset/ so the platform WebView can load them.
    // Engine image / audio resources (bres://, gdau://) get a local loopback
    // HTTP server in a later milestone (article bridge D3 in the all-qt-ui-port
    // design); for milestone 1 the test dict has no images/audio, so this
    // rewrite is enough.
    Q_INVOKABLE QString rewriteArticleUrls(const QString &html) const;

signals:
    void dictCountChanged();
    void readyChanged();
    void lastErrorChanged();
    void dictionariesChanged();
    void groupsChanged();
    void activeGroupChanged();
    void articleLoaded(const QString &word, const QString &html);
    void articleNotFound(const QString &word);
    void suggestionsReady(const QString &prefix, const QStringList &suggestions);
    void ftsIndexChanged(int dictIndex);
    void ftsSearchReady(const QString &query, const QVariantList &results);
    void buildingFtsChanged();

private:
    void runScan();
    void setDictCount(int n);
    void setReady(bool r);
    void setLastError(const QString &e);
    void setDictionaries(const QVariantList &list);
    void setGroups(const QVariantList &list);
    void setActiveGroupId(int id);
    void setBuildingFts(bool b);

    int m_dictCount = 0;
    bool m_ready = false;
    QString m_lastError;
    QVariantList m_dictionaries;
    QVariantList m_groups;
    int m_activeGroupId = 0;
    bool m_buildingFts = false;
    QString m_appDir;
    QString m_stagedDir;
};