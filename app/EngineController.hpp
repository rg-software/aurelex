#pragma once

#include <QObject>
#include <QString>
#include <QStringList>
#include <QVariantList>
#include <QVariantMap>
#include <QFuture>
#include <QFutureWatcher>
#include <QPointer>
#include <QTimer>
#include <QMutex>
#include <QList>

class ArticleServer;

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
    Q_PROPERTY(bool darkMode READ darkMode NOTIFY darkModeChanged)
    Q_PROPERTY(bool systemDark READ systemDark NOTIFY systemDarkChanged)
    Q_PROPERTY(bool userDarkOverride READ userDarkOverride WRITE setUserDarkOverride NOTIFY userDarkOverrideChanged)
    Q_PROPERTY(bool onboarded READ onboarded WRITE setOnboarded NOTIFY onboardedChanged)
    Q_PROPERTY(bool buildingFts READ buildingFts NOTIFY buildingFtsChanged)
    // Full-text index batch progress: while buildingFts is true, ftsIndexDone /
    // ftsIndexTotal report "N of M" dictionaries COMPLETED (0/0 when idle).
    // ftsCurrentDictIndex is the currently-indexing dictionary number (1-based).
    Q_PROPERTY(int ftsIndexDone READ ftsIndexDone NOTIFY ftsIndexProgressChanged)
    Q_PROPERTY(int ftsIndexTotal READ ftsIndexTotal NOTIFY ftsIndexProgressChanged)
    // All-dictionaries progress as a 0..1 fraction (ftsIndexDone/ftsIndexTotal).
    Q_PROPERTY(qreal ftsIndexFraction READ ftsIndexFraction NOTIFY ftsIndexProgressChanged)
    // The currently-indexing dictionary's own progress (0..1) sampled from
    // gd_fts_progress; on a resumed build it continues from where we left off
    // (never restarts at 0).
    Q_PROPERTY(qreal ftsDictFraction READ ftsDictFraction NOTIFY ftsIndexProgressChanged)
    // Display name of the dictionary currently being indexed.
    Q_PROPERTY(QString ftsCurrentDictName READ ftsCurrentDictName NOTIFY ftsIndexProgressChanged)
    // True while the foreground StagingService is copy-staging a picked folder
    // into app storage. Written by the service via shared_prefs/staging.xml
    // (start) / <absent> (done); the poller tracks it so the Dicts tab can show
    // "Preparing dictionaries..." instead of looking frozen.
    Q_PROPERTY(bool stagingActive READ stagingActive NOTIFY stagingActiveChanged)
    // True while the carve is scanning (gd_scan_dicts) a newly-staged folder.
    // Bridges the gap so the processing banner stays visible continuously from
    // folder pick -> staging -> scan -> indexing.
    Q_PROPERTY(bool scanningActive READ scanningActive NOTIFY scanningActiveChanged)
    // List of {file, reason} maps for dictionary files that failed to load in
    // the last scan (corrupt/truncated source). Filled after each runScan; the
    // Dicts tab surfaces it so the user knows a dictionary is missing and that
    // re-adding the folder re-copies it. Empty when everything loaded.
    Q_PROPERTY(QVariantList scanFailures READ scanFailures NOTIFY scanFailuresChanged)
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
    bool systemDark() const { return m_systemDark; }
    bool userDarkOverride() const { return m_userDarkOverride; }
    void setUserDarkOverride(bool on);
    bool onboarded() const { return m_onboarded; }
    void setOnboarded(bool v);
    QVariantList scanFailures() const { return m_scanFailures; }

    // Cycle the manual dark override: when following system, force dark; when
    // forcing dark, return to following system. Drives Material.theme + the
    // effective dark mode (article CSS).
    Q_INVOKABLE void toggleDarkOverride();

    // Initialise the engine. `configDir`/`indexDir` are usually the same
    // AppLocalDataLocation; `stagedDir` is the dict folder the app stages to.
    Q_INVOKABLE void initialize(const QString &appDir, const QString &stagedDir);

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
    // deferred to a follow-up: for the v1 gate, the groups list + active
    // toggle prove the UI/controller pattern; dict-in-group wiring (Q_INVOKABLE
    // wrappers around gd_group_add/remove/move_dict) is the next slice.
    Q_INVOKABLE void createGroup(const QString &name);
    Q_INVOKABLE void renameGroup(int groupId, const QString &newName);
    Q_INVOKABLE void deleteGroup(int groupId);
    Q_INVOKABLE void setActiveGroup(int groupId);

    // Group membership editing. `dictIndex` is the GLOBAL dictionary index as
    // listed in dictionaries(); the engine maps it into group membership.
    // groupDicts(groupId) emits groupDictsReady(groupId, list) where each item
    // is {index, memberIndex, name, source, member}. Group 0 ("All") owns every
    // dict in global order and is not editable (the engine rejects id 0).
    Q_INVOKABLE void groupDicts(int groupId);
    Q_INVOKABLE void groupAddDict(int groupId, int dictIndex);
    Q_INVOKABLE void groupRemoveDict(int groupId, int dictIndex);
    Q_INVOKABLE void groupMoveDict(int groupId, int from, int to);

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
    // Whole-words: when true (exact), the query matches exact terms; when false
    // (default), each term is treated as a prefix (a trailing * is appended).
    Q_INVOKABLE QVariantList ftsSearch(const QString &query, int mode, int groupId = 0,
                                       bool wholeWords = false);

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

    // Milestone 6: incoming lookup intents. The Java shell (AurelexActivity)
    // writes the captured word into shared_prefs/intent.xml on every
    // onCreate/onNewIntent (share sheet, aurelex://, PROCESS_TEXT, QS tile).
    // A poller (m_pollTimer) consumes the file as soon as the engine is ready
    // and runs the lookup — this covers cold start AND warm onNewIntent, where
    // the old Component.onCompleted read missed words entirely.
    Q_INVOKABLE QString readPendingLookup();

    // Clipboard lookup: reads the system clipboard text (via the JNI clipboard
    // bridge) and returns it. Empty when the clipboard has no text.
    Q_INVOKABLE QString clipboardText();

    bool buildingFts() const { return m_buildingFts; }
    int ftsIndexDone() const { return m_ftsIndexDone; }
    int ftsIndexTotal() const { return m_ftsIndexTotal; }
    qreal ftsIndexFraction() const { return m_ftsIndexFraction; }
    qreal ftsDictFraction() const { return m_ftsDictFraction; }
    QString ftsCurrentDictName() const { return m_ftsCurrentDictName; }
    bool stagingActive() const { return m_stagingActive; }
    bool scanningActive() const { return m_scanningActive; }

    // Lookup a word. `articleLoaded(word, html)` on success, or
    // `articleNotFound(word)` when the engine returned a "no match" article.
    Q_INVOKABLE void lookup(const QString &word);
    // Lookup `word` scoped to a specific group (id, 0 = All). Used when a
    // result from a scoped context (e.g. FTS tab) must open in that group,
    // independent of the Search tab's active-group selection.
    Q_INVOKABLE void lookupInGroup(const QString &word, int groupId);
    Q_INVOKABLE void suggest(const QString &prefix);

    // Rewrite upstream article asset URLs (qrc:///, bres://, gdau://) to the
    // loopback HTTP server's origin (baseUrl()). gdlookup:// links in the
    // article are intercepted separately by the WebView's onUrlChanged handler
    // (in-article navigation, see main.qml). Engine resource routes are served
    // by the loopback server; engine qrc:/// assets are bundled into the APK's
    // assets/ directory by build.ps1.
    Q_INVOKABLE QString rewriteArticleUrls(const QString &html) const;

    // Loopback article server's base URL (e.g. "http://127.0.0.1:54321") once
    // it has bound a port. Empty before startup. Useful for tests and for
    // constructing manual resource URLs from QML.
    Q_PROPERTY(QString articleBaseUrl READ articleBaseUrl NOTIFY articleBaseUrlChanged)
    QString articleBaseUrl() const;

    // In-app audio playback. `url` is a loopback gdau URL the ArticleServer
    // serves (http://127.0.0.1:PORT/gdau/<dictId>/<file>.wav). The QML WebView
    // intercepts the anchor before navigation and hands it here; the bytes are
    // played via the Android MediaPlayer in AurelexActivity.playAudio, so
    // the article stays on screen. Mirrors the shipped app's AudioPlayer.
    Q_INVOKABLE void playAudio(const QString &url);
    Q_INVOKABLE void stopAudio();

    // Folder-scoped storage (SAF). addDictionaryFolder() launches the Android
    // folder picker via the Java shell; the picked folder is stage-copied into
    // app-private storage and then scanned + indexed (a one-off import).
    Q_INVOKABLE void addDictionaryFolder();

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
    void stagingActiveChanged();
    void groupDictsReady(int groupId, const QVariantList &dicts);
    void historyChanged();
    void favoritesChanged();
    void darkModeChanged();
    void onboardedChanged();
    void articleBaseUrlChanged();
    void systemDarkChanged();
    void userDarkOverrideChanged();
    void scanFailuresChanged();
    void ftsIndexProgressChanged();
    // Emitted from the index-build worker thread after each dictionary finishes
    // indexing (queued delivery to the UI thread). currentCount = number of
    // dictionaries COMPLETED so far; total = batch size; name = the dictionary
    // that was just finished (so the "currently indexing" label can use the
    // NEXT one). Note the app reads live per-dict progress separately via
    // gd_fts_progress.
    void ftsIndexBatchProgress(int currentCount, int total, const QString &name);
    void scanningActiveChanged();

private:
    void runScan();
    void autoIndexMissing();
    // Start the single FTS worker if it isn't already draining the queue.
    void ensureFtsWorker();
    // Permanently delete an imported dictionary's staged copy (when not shared)
    // and its engine index cache. Called after gd_remove_dict; indices may have
    // shifted, so operate on captured paths/ids.
    void deleteDictionaryFiles(const QString &sourceFile, const QString &dictId,
                               const QString &stagedRoot, const QString &appDir);
    // Remove leftover temporary staging dirs (files/staging-tmp/*) once a
    // scan+index batch has finished and the staged tree is consistent.
    void purgeStagingTmp();
    // The staged/<sourceId> directory that owns `file` (a direct child of the
    // staged root), or empty.
    static QString stagedAncestor(const QString &file, const QString &stagedRoot);
    void setDictCount(int n);
    void setReady(bool r);
    void setLastError(const QString &e);
    void setDictionaries(const QVariantList &list);
    void setGroups(const QVariantList &list);
    void setActiveGroupId(int id);
    void setBuildingFts(bool b);
    void setStagingActive(bool b);
    void setScanningActive(bool b);
    void setFtsIndexProgress(int done, int total, const QString &name);
    void setFtsFraction(qreal allFraction, qreal dictFraction);
    void pollFtsProgress();
    void setScanFailures(const QVariantList &list);
    void collectScanFailures();
    void setHistory(const QStringList &list);
    void setFavorites(const QStringList &list);
    void loadHistory();
    void saveHistory();
    void loadFavorites();
    void saveFavorites();
    void loadSettings();
    void saveSettings();
    void pollPendingLookup();
    QString peekPendingLookup() const;
    bool peekPendingClipboardFlag() const;
    // Bulk FTS indexing: the Android IndexingService writes a completion marker
    // (shared_prefs/indexing.xml) when it stops; consume it here so a leftover
    // marker never re-triggers stale indexing state on a later tick.
    bool peekPendingIndexingDone() const;
    void removePendingIndexingFile();
    // Dictionary staging: the Android StagingService writes a start marker
    // (shared_prefs/staging.xml) to show "Preparing dictionaries..." and
    // clears it when the copy completes (or fails).
    bool peekStagingActive() const;
    void removeStagingFile();

    // Android system dark-mode (Qt 6.6 QPA doesn't expose it); sampled via JNI
    // on the poller tick. Recomputes and applies the effective dark mode.
    bool readSystemDark() const;
    void updateSystemDark();
    void applyEffectiveDark();

    QTimer m_pollTimer;
    int m_clipboardRetries = 0;
    int m_suggestGeneration = 0;

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
    bool m_systemDark = false;
    bool m_userDarkOverride = false;
    bool m_onboarded = false;
    QString m_appDir;
    QString m_stagedDir;
    QVariantList m_scanFailures;
    bool m_stagingActive = false;
    bool m_scanningActive = false;
    int m_ftsIndexDone = 0;
    int m_ftsIndexTotal = 0;
    qreal m_ftsIndexFraction = 0.0;
    qreal m_ftsDictFraction = 0.0;
    QString m_ftsCurrentDictName;
    // Samples gd_fts_progress while a batch is building so ftsDictFraction
    // reflects the in-flight dictionary's own progress (not just whole dicts).
    QTimer m_ftsProgressTimer;
    // Single-index-worker queue (design D1/D2): dictionary IDs still needing a
    // full-text index. Stored as IDs (not engine indices) so a dictionary
    // removed mid-build doesn't shift/desync the queue; the worker re-resolves
    // id -> index at pop time and skips ids that no longer exist. buildingFts
    // clears only when the queue empties.
    QList<QString> m_ftsQueue;
    // Guards m_ftsQueue (written by the UI thread in autoIndexMissing/remove,
    // read/popped by the worker thread).
    QMutex m_ftsQueueMutex;
    // True while the single FTS worker task is draining m_ftsQueue. Controls
    // whether autoIndexMissing starts a new run; a re-import mid-build appends
    // to the queue the running worker picks up.
    bool m_ftsWorkerRunning = false;
    QPointer<ArticleServer> m_articleServer;
};