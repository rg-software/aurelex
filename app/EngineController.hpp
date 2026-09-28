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
#include <QThreadPool>
#include <QList>
#include <QHash>

#include <atomic>

class ArticleServer;

extern "C" {
#include "goldendict.h"
}

// EngineController: QML-facing wrapper around the in-process goldendict engine.
// Owns the engine lifetime; calls are off-thread so the UI thread never blocks
// on the (potentially slow) gd_* C API. User-facing calls (suggest/lookup/
// prefetch) run serially on a single worker (m_enginePool) with last-wins
// semantics; management calls (scan/groups/FTS) run on QtConcurrent.
class EngineController : public QObject
{
    Q_OBJECT
    Q_PROPERTY(int dictCount READ dictCount NOTIFY dictCountChanged)
    Q_PROPERTY(bool ready READ ready NOTIFY readyChanged)
    Q_PROPERTY(QString lastError READ lastError NOTIFY lastErrorChanged)
    Q_PROPERTY(QVariantList dictionaries READ dictionaries NOTIFY dictionariesChanged)
    Q_PROPERTY(QVariantList groups READ groups NOTIFY groupsChanged)
    Q_PROPERTY(int activeGroupId READ activeGroupId NOTIFY activeGroupChanged)
    Q_PROPERTY(QVariantList history READ history NOTIFY historyChanged)
    Q_PROPERTY(QVariantList favorites READ favorites NOTIFY favoritesChanged)
    Q_PROPERTY(bool darkMode READ darkMode NOTIFY darkModeChanged)
    Q_PROPERTY(bool systemDark READ systemDark NOTIFY systemDarkChanged)
    Q_PROPERTY(bool userDarkOverride READ userDarkOverride WRITE setUserDarkOverride NOTIFY userDarkOverrideChanged)
    Q_PROPERTY(bool onboarded READ onboarded WRITE setOnboarded NOTIFY onboardedChanged)
    // Article reflow zoom (percent, 75-250 in 25 steps; 100 = default). Persisted
    // in settings.json; rewriteArticleUrls bakes it into the article CSS, and
    // QML applies live changes via the injected gdSetZoom(...) controller.
    Q_PROPERTY(qreal articleZoom READ articleZoom NOTIFY articleZoomChanged)
    Q_PROPERTY(qreal articleZoomMin READ articleZoomMin CONSTANT)
    Q_PROPERTY(qreal articleZoomMax READ articleZoomMax CONSTANT)
    Q_PROPERTY(qreal articleZoomStep READ articleZoomStep CONSTANT)
    Q_PROPERTY(bool buildingFts READ buildingFts NOTIFY buildingFtsChanged)
    // True from the moment the controller starts enumerating which dictionaries
    // still need an FTS index until buildingFts flips true (or the batch ends
    // with nothing to do). Only used to pick the banner's label text; the
    // banner's VISIBILITY is driven by processingActive.
    Q_PROPERTY(bool ftsStarting READ ftsStarting NOTIFY ftsStartingChanged)
    // Single continuous "long-running processing" flag driving the Dicts
    // processing banner's VISIBILITY. True for the whole staging -> scan -> FTS
    // enumeration -> FTS build chain and false only when all of it is done, so
    // the banner never blinks off between phases (the old design OR'd four
    // independent phase flags and could paint a phase-boundary frame with none
    // of them set). stagingActive/scanningActive/buildingFts/ftsStarting remain
    // the per-phase flags that choose the banner's label text.
    Q_PROPERTY(bool processingActive READ processingActive NOTIFY processingActiveChanged)
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
    // History / favorites as a list of {word, group} maps. The group is the
    // dictionary group the article was produced in (0 = "All"). QML renders the
    // row label from `.word` and uses `.group` for per-entry restore/removal.
    QVariantList history() const { return m_history; }
    QVariantList favorites() const { return m_favorites; }
    Q_INVOKABLE QStringList historyWords() const;
    Q_INVOKABLE QStringList favoritesWords() const;
    // Does a group with this id exist (used for group-restore fallback to All)?
    Q_INVOKABLE bool groupExists(int groupId) const;
    // Human-readable name of a group id (falls back to the invariant "All").
    // Not a label source: the UI resolves every visible group name by id via the
    // QML _groupLabel helper, so the built-in group is localized there.
    Q_INVOKABLE QString groupName(int groupId) const;
    bool darkMode() const { return m_darkMode; }
    bool systemDark() const { return m_systemDark; }
    bool userDarkOverride() const { return m_userDarkOverride; }
    void setUserDarkOverride(bool on);
    qreal articleZoom() const { return m_articleZoom; }
    qreal articleZoomMin() const { return kArticleZoomMin; }
    qreal articleZoomMax() const { return kArticleZoomMax; }
    qreal articleZoomStep() const { return kArticleZoomStep; }
    // Set the article reflow zoom (percent). Clamped to [kArticleZoomMin,
    // kArticleZoomMax] and snapped to kArticleZoomStep; no-ops (no signal) when
    // the clamped value is unchanged, so QML does not churn JS calls.
    Q_INVOKABLE void setArticleZoom(qreal zoom);
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
    Q_INVOKABLE void removeHistoryEntry(const QString &word, int group);
    Q_INVOKABLE void toggleFavoriteEntry(const QString &word, int group);
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
    bool ftsStarting() const { return m_ftsStarting; }
    int ftsIndexDone() const { return m_ftsIndexDone; }
    int ftsIndexTotal() const { return m_ftsIndexTotal; }
    qreal ftsIndexFraction() const { return m_ftsIndexFraction; }
    qreal ftsDictFraction() const { return m_ftsDictFraction; }
    QString ftsCurrentDictName() const { return m_ftsCurrentDictName; }
    bool stagingActive() const { return m_stagingActive; }
    bool scanningActive() const { return m_scanningActive; }
    bool processingActive() const { return m_processingActive; }

    // Lookup a word. `articleLoaded(word, html)` on success, or
    // `articleNotFound(word)` when the engine returned a "no match" article.
    Q_INVOKABLE void lookup(const QString &word);
    // Lookup `word` scoped to a specific group (id, 0 = All). Used when a
    // result from a scoped context (e.g. FTS tab) must open in that group,
    // independent of the Search tab's active-group selection.
    Q_INVOKABLE void lookupInGroup(const QString &word, int groupId);
    // Group-restoring lookup: switch active group to `groupId` (fallback All) and
    // look up `word` in it. Used for history/favorites taps and Back/Forward.
    Q_INVOKABLE void lookupInGroupWithSwitch(const QString &word, int groupId);
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

    // System-window inset heights (physical px) read from the Android activity:
    // the Qt window runs edge-to-edge, so QML offsets its top/bottom chrome
    // above the status bar / navigation bar itself. 0 off-Android.
    Q_INVOKABLE int systemInsetTop() const;
    Q_INVOKABLE int systemInsetBottom() const;

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
    void ftsStartingChanged();
    void processingActiveChanged();
    void stagingActiveChanged();
    void groupDictsReady(int groupId, const QVariantList &dicts);
    // Emitted after a group's membership or order changed (add/remove/move) and
    // the engine has committed it, so QML can re-query groupDicts(editingGroup)
    // AFTER the async mutation lands (avoids reading stale order).
    void groupMembersChanged();
    // Emitted when a group is created successfully (the create ran on a worker
    // thread). QML uses the id to jump straight into the new group's editor.
    void groupCreated(int groupId, const QString &name);
    // Emitted when group creation/rename is rejected because the name is taken.
    void groupNameTaken(const QString &name);
    void historyChanged();
    void favoritesChanged();
    void darkModeChanged();
    // (darkModeChanged drives the in-place gdSetDarkMode flip on the open
    // article; rewriteArticleUrls always injects the dark controller, so no
    // re-lookup is needed — QML reacts to darkModeChanged directly.)
    void onboardedChanged();
    void articleBaseUrlChanged();
    void systemDarkChanged();
    void userDarkOverrideChanged();
    void articleZoomChanged();
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
    void setFtsStarting(bool b);
    void setStagingActive(bool b);
    void setScanningActive(bool b);
    void setProcessingActive(bool b);
    void setFtsIndexProgress(int done, int total, const QString &name);
    void setFtsFraction(qreal allFraction, qreal dictFraction);
    void pollFtsProgress();
    void setScanFailures(const QVariantList &list);
    void collectScanFailures();
    void setHistory(const QVariantList &list);
    void setFavorites(const QVariantList &list);
    void loadHistory();
    void saveHistory();
    void loadFavorites();
    void saveFavorites();
    // Re-point every history/favorites entry whose group id is absent from
    // m_groups to the built-in group (0), keeping the word, and persist both
    // files. No-op while m_groups is empty, so a transient empty list mid-reload
    // cannot re-point every entry. `deletedGroupId` additionally treats that one
    // id as gone, so deleteGroup can repair synchronously instead of waiting for
    // the async refreshGroups round trip. Returns the number of entries rewritten.
    int repointStaleGroupEntries(int deletedGroupId = -1);
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
    // Flips the Android system status/nav bar icons to the correct contrast for
    // our self-painted light/dark chrome strips (JNI).
    void applySystemBarAppearance();
    // Periodic self-heal: the WM/Qt can reset the bar icons to the device-theme
    // default; this reapplies our desired appearance when it drifted (cheap, ~2Hz).
    void syncSystemBarAppearance();

    QTimer m_pollTimer;
    // Failsafe for the "Scanning/Reading dictionary files..." banner: gd_scan
    // can wedge behind a parked engine-mutex holder, and the QtConcurrent scan
    // never returns (the UI then shows the banner forever). If a scan hasn't
    // completed within kScanWatchdogMs, clear the flag so the UI recovers and
    // logs what to do. A relaunch re-scans the staged root and frees the mutex.
    QTimer m_scanWatchdog;
    static constexpr int kScanWatchdogMs = 90000;
    int m_clipboardRetries = 0;
    // Serial engine dispatcher (last-wins). Every user-facing engine call
    // (suggest/lookup/prefetch) runs one-at-a-time on this single worker
    // instead of the global pool. The blocking gd_* calls already serialize
    // inside the carve on its own engine mutex, and their results must not
    // overwrite each other (that was the "suggestion dropdown takes ~10s"
    // bug: keystroke requests flooded the global pool, the carve's internal
    // index lookups — which ALSO schedule on the global pool — starved, and
    // every request burned its full 10s/15s loop bound). With one in-flight
    // request the global pool always has a thread for the inner lookups, and
    // queued-but-superseded jobs bail out on a stale generation before ever
    // touching the engine.
    QThreadPool m_enginePool;
    // Monotonic "last request wins" generations, bumped on the UI thread;
    // a queued job whose generation is no longer current skips the engine.
    std::atomic<int> m_suggestGeneration{0};
    std::atomic<int> m_lookupGeneration{0};

    int m_dictCount = 0;
    bool m_ready = false;
    QString m_lastError;
    QVariantList m_dictionaries;
    QVariantList m_groups;
    int m_activeGroupId = 0;
    bool m_buildingFts = false;
    bool m_ftsStarting = false;
    QVariantList m_history;
    QVariantList m_favorites;
    bool m_darkMode = false;
    bool m_systemDark = false;
    bool m_userDarkOverride = false;
    qreal m_articleZoom = 100.0;
    static constexpr qreal kArticleZoomMin = 75.0;
    static constexpr qreal kArticleZoomMax = 250.0;
    static constexpr qreal kArticleZoomStep = 25.0;
    bool m_onboarded = false;
    QString m_appDir;
    QString m_stagedDir;
    QVariantList m_scanFailures;
    bool m_stagingActive = false;
    bool m_scanningActive = false;
    bool m_processingActive = false;
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

    // Small per-(word, active group, dark) article cache. Suggested words are
    // prefetched when suggestions arrive and lookups write back on completion,
    // so tapping a candidate (or re-opening a word) usually skips gd_lookup
    // entirely — the QML shows the cached HTML immediately. Keyed by dark mode
    // because the engine embeds darkreader.js into generated HTML.
    static constexpr int kArticleCacheMax = 8;
    QString articleCacheKey(const QString &word) const;
    void cacheArticle(const QString &key, const QString &html);
    void clearArticleCache();
    void prefetchArticle(const QString &word);
    QHash<QString, QString> m_articleCache;
    QStringList m_articleCacheOrder;
};