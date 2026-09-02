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
    Q_PROPERTY(QStringList history READ history NOTIFY historyChanged)
    Q_PROPERTY(QStringList favorites READ favorites NOTIFY favoritesChanged)
    Q_PROPERTY(bool darkMode READ darkMode WRITE setDarkMode NOTIFY darkModeChanged)
    Q_PROPERTY(bool onboarded READ onboarded WRITE setOnboarded NOTIFY onboardedChanged)
public:
    explicit EngineController(QObject *parent = nullptr);
    ~EngineController() override;

    int dictCount() const { return m_dictCount; }
    bool ready() const { return m_ready; }
    QString lastError() const { return m_lastError; }
    QVariantList dictionaries() const { return m_dictionaries; }
    QVariantList groups() const { return m_groups; }
    int activeGroupId() const { return m_activeGroupId; }
    QStringList history() const { return m_history; }
    QStringList favorites() const { return m_favorites; }
    bool darkMode() const { return m_darkMode; }
    bool onboarded() const { return m_onboarded; }
    void setDarkMode(bool on);
    void setOnboarded(bool v);

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

    // History + favorites persistence. The carve's engine has no built-in
    // history/favorites; we use a small JSON file in AppLocalDataLocation
    // (files/history.json, files/favorites.json). The controller caps the
    // history at 100 entries (most-recent-first, dedupes), matching the
    // shipped app's behavior. Persistence is transparent: on engine init the
    // controller loads the file, every mutation rewrites the file, and
    // historyChanged()/favoritesChanged() fire so QML stays in sync.
    Q_INVOKABLE void recordHistory(const QString &word);
    Q_INVOKABLE void toggleFavorite(const QString &word);
    Q_INVOKABLE void removeHistory(const QString &word);
    Q_INVOKABLE void clearHistory();

    // Milestone 6: incoming lookup intents. The Java shell (ExperimentActivity)
    // writes the captured word into shared_prefs/intent.xml. QML calls this on
    // startup + resume; the method returns the pending word (or empty) and
    // clears the file so the next lookup isn't re-triggered.
    Q_INVOKABLE QString readPendingLookup();

    // Clipboard lookup: reads the system clipboard text (via the JNI clipboard
    // bridge) and returns it. Empty when the clipboard has no text.
    Q_INVOKABLE QString clipboardText();

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
    void historyChanged();
    void favoritesChanged();
    void darkModeChanged();
    void onboardedChanged();

private:
    void runScan();
    void setDictCount(int n);
    void setReady(bool r);
    void setLastError(const QString &e);
    void setDictionaries(const QVariantList &list);
    void setGroups(const QVariantList &list);
    void setActiveGroupId(int id);
    void setBuildingFts(bool b);
    void setHistory(const QStringList &list);
    void setFavorites(const QStringList &list);
    void loadHistory();
    void saveHistory();
    void loadFavorites();
    void saveFavorites();
    void loadSettings();
    void saveSettings();

    int m_dictCount = 0;
    bool m_ready = false;
    QString m_lastError;
    QVariantList m_dictionaries;
    QVariantList m_groups;
    int m_activeGroupId = 0;
    bool m_buildingFts = false;
    QStringList m_history;
    QStringList m_favorites;
    bool m_darkMode = false;
    bool m_onboarded = false;
    QString m_appDir;
    QString m_stagedDir;
};