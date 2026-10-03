#pragma once

#include <QObject>
#include <QString>
#include <QStringList>
#include <QDateTime>
#include <QVariantList>
#include <QVariantMap>
#include <QJsonObject>
#include <QFuture>
#include <QFutureWatcher>
#include <QPointer>
#include <QTimer>
#include <QMutex>
#include <QThreadPool>
#include <QList>
#include <QHash>
#include <QSet>

#include <atomic>
#include <functional>

#include "RemoteCatalog.hpp"
#include "DictIdentity.hpp"

class ArticleServer;
class QNetworkAccessManager;

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
    Q_PROPERTY(int themeMode READ themeMode WRITE setThemeMode NOTIFY themeModeChanged)
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

    // ---------- Remote dictionary catalog (remote-dictionary-catalog) ----------
    // The catalog is ONE hand-maintained JSON document fetched over HTTPS from
    // remoteCatalogUrl (see loadSettings). It is never fetched at startup: the
    // probe runs when the user asks for it, so a surface most sessions never
    // open adds no network latency to launch.
    Q_PROPERTY(bool catalogLoading READ catalogLoading NOTIFY catalogChanged)
    // True when the last fetch SUCCEEDED. False means "we could not reach the
    // catalog right now" — which may still have a readable last-known copy
    // (catalogEntries stays populated; catalogLastFetched says how old).
    Q_PROPERTY(bool catalogReachable READ catalogReachable NOTIFY catalogChanged)
    // The last-good manifest's entries, decorated for QML: {id, name,
    // langFrom, langTo, pair, attribution, license, totalBytes, requiredBytes,
    // optionalBytes, hasOptional, installed, installable, unsupportedReason,
    // files:[{name, sizeBytes, required, role}]}. Rendered read-only when
    // unreachable; installed/download flags are recomputed on every
    // dictionariesChanged so a fresh scan is reflected immediately.
    Q_PROPERTY(QVariantList catalogEntries READ catalogEntries NOTIFY catalogChanged)
    Q_PROPERTY(QString catalogError READ catalogError NOTIFY catalogChanged)
    // The manifest's own "updated" field, and when WE last fetched it.
    Q_PROPERTY(QString catalogUpdated READ catalogUpdated NOTIFY catalogChanged)
    Q_PROPERTY(QString catalogLastFetched READ catalogLastFetched NOTIFY catalogChanged)
    Q_PROPERTY(QString remoteCatalogUrl READ remoteCatalogUrl CONSTANT)

    // ---------- Download progress (read from shared_prefs/download.xml) ----------
    // Deliberately SEPARATE from the staging/scanning/indexing properties
    // above: a download is a second, independent queue (design D1), so its
    // progress never raises processingActive and its cancel never lowers it.
    // The UI keeps the two surfaces visually distinct so they cannot read as
    // one chain.
    Q_PROPERTY(bool downloadActive READ downloadActive NOTIFY downloadChanged)
    // Display name of the entry currently transferring.
    Q_PROPERTY(QString downloadEntryName READ downloadEntryName NOTIFY downloadChanged)
    Q_PROPERTY(int downloadFilesDone READ downloadFilesDone NOTIFY downloadChanged)
    Q_PROPERTY(int downloadFilesTotal READ downloadFilesTotal NOTIFY downloadChanged)
    Q_PROPERTY(qint64 downloadBytesDone READ downloadBytesDone NOTIFY downloadChanged)
    Q_PROPERTY(qint64 downloadBytesTotal READ downloadBytesTotal NOTIFY downloadChanged)
    // Whole-batch byte fraction (0..1). Kept non-negative and capped at 1 so a
    // hand-maintained sizeBytes that is slightly wrong cannot overshoot the bar.
    Q_PROPERTY(qreal downloadFraction READ downloadFraction NOTIFY downloadChanged)
    // Human-readable transfer rate, formatted by the service.
    Q_PROPERTY(QString downloadSpeed READ downloadSpeed NOTIFY downloadChanged)
    // "" while running or before the first batch; otherwise "succeeded",
    // "cancelled" or "failed". Cancelled is NOT a failure: the user asked for
    // it, and the UI must not present it as an error.
    Q_PROPERTY(QString downloadOutcome READ downloadOutcome NOTIFY downloadChanged)
    Q_PROPERTY(QStringList downloadSucceeded READ downloadSucceeded NOTIFY downloadChanged)
    Q_PROPERTY(QStringList downloadFailed READ downloadFailed NOTIFY downloadChanged)
    // One-line reason for the terminal outcome (e.g. the entry that failed
    // verification, or "the catalog is unreachable"). Empty when succeeded.
    Q_PROPERTY(QString downloadMessage READ downloadMessage NOTIFY downloadChanged)
    // Staging scratch dirs (files/staging-tmp/<contentHash>) a live download
    // owns, '|'-separated. purgeStagingTmp skips these so the tail's cleanup
    // can never delete a transfer in flight.
    Q_PROPERTY(QString downloadScratchHashes READ downloadScratchHashes NOTIFY downloadChanged)
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
    // The theme the user asked for (kThemeFollowSystem / kThemeLight / kThemeDark).
    // This is the SETTING; darkMode() is the theme it resolves to. Most consumers
    // want darkMode() — the resolution already accounts for the system theme.
    int themeMode() const { return m_themeMode; }
    void setThemeMode(int mode);
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
    // The banner's results: unloadable sources (m_scanFailures) followed by
    // name clashes resolved by the last scan (m_resultClashes). Combined here so
    // the two producers never race to overwrite each other's rows.
    QVariantList scanFailures() const { return m_scanFailures + m_resultClashes; }

    // Dismiss the import-results banner. Pure UI state: it clears the reported
    // results and touches no file and no dictionary. Failed sources have already
    // been deleted automatically by the scan (report-import-results), so there is
    // nothing left for a control here to act on.
    Q_INVOKABLE void dismissScanFailures();

    // Cycle the theme mode Light -> Dark -> Follow-system -> Light. The order is
    // deliberate: leaving Follow-system always lands on an explicit theme, which
    // is by construction different from whatever the system is showing, so no tap
    // is ever a visual no-op. (The reverse order reproduces the dead-button bug
    // this replaced: under a dark system, the step out of follow-system selects
    // dark — which is already showing.)
    Q_INVOKABLE void toggleThemeMode();

    // Initialise the engine. `configDir`/`indexDir` are usually the same
    // AppLocalDataLocation; `stagedDir` is the dict folder the app stages to.
    Q_INVOKABLE void initialize(const QString &appDir, const QString &stagedDir);

    // Refresh the dictionaries list (off-thread; result delivered via
    // dictionariesChanged signal). No-op if the engine isn't ready.
    Q_INVOKABLE void refreshDictionaries();

    // Remove / reorder. `removeDictionary`/`removeDictionaries` take DISPLAY
    // positions into dictionaries() (which is sorted by name); the controller
    // translates them to the engine's indices internally, so callers never need
    // the engine numbering. Removal is permanent (staged file + index deleted)
    // and refuses while processing. Both are wrappers around the engine C API,
    // routed through QtConcurrent so they never block the UI thread.
    Q_INVOKABLE void removeDictionary(int index);
    Q_INVOKABLE void removeDictionaries(const QVariantList &indices);
    // `moveDictionary` uses ENGINE indices (it predates the display/engine split
    // and is currently unused from QML; groups own reordering).
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
    // Run a full-text search. `mode` is the FTS::SearchMode to use: 0 (whole
    // words) parses the query as exact terms, 2 (wildcards) as prefixes
    // (control-state-and-fts-whole-words). `groupId` selects the scope, 0 = All.
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

    // Whether the clipboard currently holds usable (non-whitespace) text. The
    // Search pane's clipboard control is enabled only when this is true; QML
    // re-queries it on clipboardChanged (control-state-and-fts-whole-words).
    Q_INVOKABLE bool clipboardHasText();

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

    // Remote catalog accessors.
    bool catalogLoading() const { return m_catalogLoading; }
    bool catalogReachable() const { return m_catalogReachable; }
    QVariantList catalogEntries() const { return m_catalogEntries; }
    QString catalogError() const { return m_catalogError; }
    QString catalogUpdated() const { return m_catalogUpdated; }
    QString catalogLastFetched() const { return m_catalogLastFetched; }
    QString remoteCatalogUrl() const { return m_remoteCatalogUrl; }

    bool downloadActive() const { return m_downloadActive; }
    QString downloadEntryName() const { return m_downloadEntryName; }
    int downloadFilesDone() const { return m_downloadFilesDone; }
    int downloadFilesTotal() const { return m_downloadFilesTotal; }
    qint64 downloadBytesDone() const { return m_downloadBytesDone; }
    qint64 downloadBytesTotal() const { return m_downloadBytesTotal; }
    qreal downloadFraction() const { return m_downloadFraction; }
    QString downloadSpeed() const { return m_downloadSpeed; }
    QString downloadOutcome() const { return m_downloadOutcome; }
    QStringList downloadSucceeded() const { return m_downloadSucceeded; }
    QStringList downloadFailed() const { return m_downloadFailed; }
    QString downloadMessage() const { return m_downloadMessage; }
    QString downloadScratchHashes() const { return m_downloadScratchHashes; }

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

    // ---------- Remote catalog API (QML-facing) ----------
    // Fetch the manifest now. Never called automatically at startup; the
    // Dictionaries pane calls it when the user asks for the catalog and on an
    // explicit refresh. On failure catalogReachable goes false, the last-good
    // manifest (if any) is left in place, and catalogError explains why.
    Q_INVOKABLE void fetchCatalog();
    // Drop the cached manifest + its timestamp and fetch again. Offered as the
    // user-visible "refresh" so re-probing is deliberate, not on every visit.
    Q_INVOKABLE void refreshCatalog();

    // Free-space preflight for a batch, run BEFORE the service starts so the
    // user gets a dialog rather than a silent refusal. Returns
    // {ok, warn, needBytes, freeBytes, missingBytes}: ok=false means refuse
    // (below bundle + kMinHeadroomBytes), warn=true means ask (below bundle +
    // kWarnHeadroomBytes). The service re-checks authoritatively before the
    // first byte; this is the UX, not the guarantee.
    Q_INVOKABLE QVariantMap downloadPreflight(const QVariantList &requests) const;

    // Start a batch. `requests` is a list of {id, files?}: `files` names the
    // files to fetch for that entry, defaulting to all of its REQUIRED files.
    // A normal install passes the entry ids alone; "Add audio" passes an
    // already-installed entry's id plus the optional file names. Files land in
    // files/staged/<contentHash> exactly like a folder import, so the existing
    // scan -> auto-index -> refresh chain picks them up unchanged.
    Q_INVOKABLE void startCatalogDownload(const QVariantList &requests);
    // Abort the WHOLE batch: stop the transfer, delete the partial files, and
    // report "cancelled". It never touches processingActive, so a scan or index
    // build already running keeps its indication and finishes on its own.
    Q_INVOKABLE void cancelCatalogDownload();
    // Clear a terminal outcome once the UI has shown it.
    Q_INVOKABLE void clearDownloadOutcome();

    // Safe-area insets (physical px) read from the Android activity: the Qt
    // window runs edge-to-edge, so QML offsets its own content inside these
    // values. Each is the union — the larger of — the system-window inset and
    // the display cutout's safe inset for that edge, because the platform
    // already folds the cutout into the status bar on some versions and not on
    // others. The horizontal pair is what keeps content clear of a side-mounted
    // camera in landscape, where nothing else reserves space. 0 off-Android.
    Q_INVOKABLE int systemInsetTop() const;
    Q_INVOKABLE int systemInsetBottom() const;
    Q_INVOKABLE int systemInsetLeft() const;
    Q_INVOKABLE int systemInsetRight() const;

signals:
    void dictCountChanged();
    void readyChanged();
    void lastErrorChanged();
    // The system clipboard's contents changed. QML re-queries clipboardHasText()
    // on this to keep the Search pane's clipboard control in sync.
    void clipboardChanged();
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
    // Emitted when any safe-area inset moved since the last poll (rotation, the
    // IME, split screen, a foldable unfolding). Rotation between the two
    // LANDSCAPE orientations keeps the window at identical dimensions, so no
    // resize signal fires even though the display cutout has moved from one side
    // edge to the other — polling the values is what catches that, and QML
    // re-reads all four insets on this.
    void insetsChanged();
    void themeModeChanged();
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
    // Emitted whenever any remote-catalog or download property changes. One
    // signal for the whole surface: the UI re-reads the handful of properties
    // together, and a download updates them several times a second.
    void catalogChanged();
    void downloadChanged();

private:
    void runScan();    void autoIndexMissing();
    // Start the single FTS worker if it isn't already draining the queue.
    void ensureFtsWorker();
    // Run one full-text search: emit ftsSearchReady(displayQuery, results), and
    // (unless the engine is mid-batch) enqueue on-demand index builds for the
    // group's dictionaries that lack an index, arming a one-shot re-run of this
    // query when those builds finish.
    void runFtsSearch(const QString &norm, int mode, int groupId,
                      const QString &displayQuery);
    // Re-run the query a deferred/on-demand build was owed, once, when the batch
    // drains. No-op when none is pending.
    void reRunPendingFts();
    // Permanently delete an imported dictionary's staged copy (when not shared)
    // and its engine index cache. Called after gd_remove_dict; indices may have
    // shifted, so operate on captured paths/ids.
    void deleteDictionaryFiles(const QString &sourceFile, const QString &dictId,
                               const QString &stagedRoot, const QString &appDir);
    // Remove `stagedDir` (a files/staged/<sourceId> directory) and anything it
    // left behind, but ONLY when it is inside the staged root and no loaded
    // dictionary still reads a file from it. This is the single place that guard
    // lives: deleteDictionaryFiles and the failed-import cleanup both go through
    // it, so a shared import folder (one pick holding several dictionaries) keeps
    // the members that still work. Returns true when the directory is gone (or
    // was already absent).
    //
    // `loadedSources` is supplied by the caller rather than read from
    // m_dictionaries: see sweepStaleStagedDirs. Removal and failed-import paths
    // pass liveDictionarySources(); the sweep passes the scan's list.
    bool removeStagedDirIfUnused(const QString &stagedDir,
                                 const QStringList &loadedSources);
    // Remove staged directories that yielded no loaded dictionary (a failed
    // import) so they are not retried and re-reported on every later scan.
    // Returns true when it removed anything. Never touches a directory a loaded
    // dictionary uses, and never runs on its own initiative outside a scan.
    //
    // `loadedSources` MUST come from the scan that just ran, not from
    // m_dictionaries: this runs BEFORE refreshDictionaries(), so on the first scan
    // after a launch the model is still empty and a guard read from it protects
    // nothing (fix-stale-sweep-deletes-live-dictionaries).
    bool sweepStaleStagedDirs(const QStringList &loadedSources);
    // Remove leftover temporary staging dirs (files/staging-tmp/*) once a
    // scan+index batch has finished and the staged tree is consistent.
    // `keepHashes` are content-hash scratch dirs a live download owns; they are
    // never purged (see downloadScratchHashes).
    void purgeStagingTmp(const QStringList &keepHashes = QStringList());
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
    // Publish the name-clash rows (reason "nameClashWithInstalled") found by the
    // last scan, replacing any from the previous one. Kept separate from
    // m_scanFailures because the two are produced by independent passes.
    void setResultClashes(const QVariantList &list);
    void collectScanFailures();

    // ---- dictionary identity + duplicate resolution ----
    // (openspec/changes/resolve-duplicate-dictionaries)
    //
    // Read every loaded dictionary's name + source-file set off the UI thread
    // (gd_dict_identity takes g_engineMutex, which a running FTS build holds for
    // its whole duration) and hand the inventory to `done` on the UI thread. The
    // returned vector is in engine order, so "keep the first of a group" is a
    // stable rule.
    void fetchIdentityInventory(
        const std::function<void(const QVector<DictIdentity::Identity> &)> &done);
    // Fold the inventory by match key, drop identities we cannot attribute
    // (unnamed, or a name that lost a race with a concurrent removal), and hand
    // on only the groups with more than one member - a group of one cannot be a
    // duplicate, and there is no need to build those.
    QVector<QVector<DictIdentity::Identity>>
    duplicateGroups(const QVector<DictIdentity::Identity> &inventory) const;
    // Fold the inventory by match key and resolve every group of two or more
    // (design.md D5). A group whose members are all identical is collapsed
    // silently, which is the one automatic deletion in the app and the step that
    // repairs an installation that already holds duplicates. A group whose members
    // DIFFER is left completely alone and recorded as a name clash: a scan expresses
    // no intent, and the comparison cannot tell a newer build from an unrelated
    // dictionary, so the user removes one. `done` runs on the UI thread after the
    // collapse, so the caller's scan chain keeps its order.
    void resolveDuplicateDictionaries(const std::function<void()> &done);
    // Remove every engine dictionary in `drop`, deleting each one's staged files.
    // Each id is read BEFORE its unload, because the engine id is an MD5 over the
    // absolute source paths and cannot be recovered afterwards. Returns the number
    // actually removed; a dictionary the engine refuses to unload keeps its files,
    // because deleting them would leave a live engine object unreadable.
    // The survivors are never touched, so they keep their object, list position,
    // group membership and built indexes.
    int unloadAndDelete(const QVector<DictIdentity::Identity> &drop);
    // Delete one already-unloaded dictionary's staged file set: every file of the
    // set (not just the primary — an .mdx plus its .mdd volumes is one
    // dictionary), its DSL `<name>.dsl.files` resource tree, and its engine index
    // cache; then the staged directory ONLY if no surviving dictionary still reads
    // from it. Refuses any path outside the staged root.
    void deleteIdentityFiles(const DictIdentity::Identity &id, const QString &dictId);
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

    // ---- remote catalog internals ----
    // Rebuild m_catalogEntries from the cached manifest + the CURRENT dictionary
    // list, so installed badges are always consistent with what is loaded. Called
    // on dictionariesChanged and after a fetch.
    void refreshCatalogEntries();
    // Persist the last-good manifest + its fetch timestamp so a previously-read
    // catalog still renders (read-only) while offline. Called only after a
    // successful parse: a failed fetch must leave both untouched.
    void cacheManifest();
    // Record the manifest's required-file digests for the catalog entries named
    // by a successful download batch (matched by entry name, which the download
    // service reports). Inert bookkeeping for a future update check.
    void recordInstalledDigests(const QStringList &entryNames);
    // Consume shared_prefs/download.xml into the download properties, and on a
    // terminal outcome clear the marker + arm the tail's rescan. Called from the
    // same 500 ms poller as the staging/indexing markers.
    void syncDownloadState();
    void removeDownloadFile();
    // Basenames of the currently loaded dictionaries' source paths — the input
    // installed-detection matches against.
    QStringList dictionarySources() const;
    // Catalog entry ids whose optional bundle (audio/resources) this session
    // downloaded for an ALREADY-loaded dictionary. On success those need
    // unload + rescan rather than a plain rescan, so it is remembered across the
    // download -> tail hand-off. Cleared once the reload has run.
    QStringList m_audioReloadIds;
    // Unload every loaded dictionary whose source matches one of the named
    // catalog entries, then rescan so the new resources are picked up. Off the
    // UI thread: gd_remove_dict/gd_scan_dicts serialize on g_engineMutex, which
    // a running FTS build holds for its whole duration.
    void reloadDictionariesForResources(const QStringList &entryIds);
    // The sources of every dictionary the engine currently has loaded, MINUS any
    // this session has unloaded but whose list entry has not been re-read yet
    // (m_unloadedSources). This is the input to every "is this staged directory
    // still in use?" decision, so a stale entry cannot make a directory that now
    // holds nothing look occupied.
    QStringList liveDictionarySources() const;
    // Source files of dictionaries this session has unloaded but whose
    // m_dictionaries entry is still stale. Valid only until the next
    // refreshDictionaries applies a fresh list, which is where it is cleared.
    QStringList m_unloadedSources;

    // Name clashes found by the last resolveDuplicateDictionaries pass, as
    // {name, count}, kept for logging. The banner rows derived from them live in
    // m_resultClashes.
    QVariantList m_nameClashes;
    // Banner rows for a same-name conflict, as {name, file, reason}. Set by
    // resolveDuplicateDictionaries; cleared when the conflict is gone.
    QVariantList m_resultClashes;
    // The top-level staged directories that existed when the last pick's staging
    // began. A dictionary whose staged ancestor is NOT in this set came from that
    // pick, so the import-path rule (skip/reject) applies to it. Emptied after the
    // first scan that follows the pick, so later scans use the cold-start rule
    // (collapse only, never reject) — design.md D3/D5.
    QSet<QString> m_prePickStagedDirs;
    // True between a pick's staging start and the first scan that resolves it.
    // Distinguishes "a pick happened and the snapshot was empty" (first-ever
    // import) from a cold start, where m_prePickStagedDirs is also empty.
    bool m_prePickSnapshotValid = false;

    // The staging scratch dirs (files/staging-tmp/<contentHash>) a live download
    // owns, so purgeStagingTmp never deletes a transfer in flight.
    QStringList liveDownloadHashes() const;
    // Bytes a request will write: the files it names, or the entry's whole
    // required set for a plain install.
    qint64 sumRequestedBytes(const RemoteCatalog::Entry &e, const QVariantMap &request) const;
    // Free space on the volume the downloads actually land on (the app's files
    // dir), not the first QStorageInfo root, which may be a different volume.
    qint64 freeBytesForDownloads() const;
    const RemoteCatalog::Entry *findCatalogEntry(const QString &id) const;
    // A rescan the tail owes because a download landed new files. Re-armed
    // across the hand-off so a batch that finishes mid-chain is not missed, and
    // the no-blink rule holds (processingActive never dips between them).
    bool m_stagedRescanPending = false;

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
    // Re-reads the four safe-area insets and emits insetsChanged() when any of
    // them moved. Driven from the same ~2Hz poll as the dark-mode sample rather
    // than from a window-resize hook: a landscape flip between the two landscape
    // orientations (rotation 1 <-> 3) keeps the window at identical dimensions,
    // so NO resize signal fires, yet the display cutout moves from one side edge
    // to the other. Polling the values themselves notices that case, and every
    // other one, without depending on which Qt signal the platform happens to
    // emit for a given rotation.
    void pollInsets();

    QTimer m_pollTimer;
    // Failsafe for the "Scanning/Reading dictionary files..." banner: gd_scan
    // can wedge behind a parked engine-mutex holder, and the QtConcurrent scan
    // never returns (the UI then shows the banner forever). If a scan hasn't
    // completed within kScanWatchdogMs, clear the flag so the UI recovers and
    // logs what to do. A relaunch re-scans the staged root and frees the mutex.
    QTimer m_scanWatchdog;
    static constexpr int kScanWatchdogMs = 90000;
    // FTS auto-index size bound: a dictionary whose source is larger than this
    // is not built during the import chain (it would dominate it); it is built
    // on demand at the user's first full-text search over it
    // (fts-indexing-performance D5). The value is a tunable; behavior does not
    // depend on it.
    static constexpr qint64 kAutoFtsMaxBytes = 200LL * 1024 * 1024;
    // How long a removal waits for a cancelled in-flight build to report idle
    // before it reaps the removed dictionary's files anyway (D4).
    static constexpr int kFtsIdleWaitMs = 3000;
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
    // Last physical-px safe-area insets seen by pollInsets(), so a change can be
    // detected by comparing against the previous tick. {-1, -1, -1, -1} forces
    // the first tick to emit, which is what makes the initial layout land on the
    // correct values rather than the QML defaults of 0.
    int m_insets[4] = {-1, -1, -1, -1};
    // Persisted theme setting. Stored as the int itself so settings.json carries
    // no serialize step; the values are the on-disk representation.
    int m_themeMode = kThemeFollowSystem;
    qreal m_articleZoom = 100.0;
    // Theme modes. Follow-system is the default (and the migration target for
    // any previously-unset or out-of-range stored value).
    static constexpr int kThemeFollowSystem = -1;
    static constexpr int kThemeLight = 1;
    static constexpr int kThemeDark = 2;
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
    // Dictionary ids skipped by auto-index because their source exceeds
    // kAutoFtsMaxBytes (built on demand instead), and ids whose build failed
    // (never auto-retried, so an on-demand re-run cannot loop). UI-thread only.
    QSet<QString> m_ftsDeferred;
    QSet<QString> m_ftsBuildFailed;
    // A full-text search owed a re-run once the on-demand builds it triggered
    // finish (D5). One-shot: cleared before re-running.
    QString m_pendingFtsNorm;
    QString m_pendingFtsQuery;
    int m_pendingFtsMode = 0;
    int m_pendingFtsGroup = 0;
    bool m_pendingFtsValid = false;
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

    // ---------- Remote catalog state ----------
    // The compiled-in default: the published catalog on GitHub Pages, chosen so
    // the URL is decoupled from a branch/tag name and served from a CDN. Not
    // user-editable; the persisted `remoteCatalogUrl` overrides it for installs
    // that already stored one (see loadSettings()).
    static constexpr char kDefaultRemoteCatalogUrl[] =
        "https://rg-software.github.io/aurelex/catalog/catalog.json";
    // Fetch budget. The document is a few hundred KB at most; a slow link must
    // not leave the catalog spinner up indefinitely.
    static constexpr int kCatalogFetchTimeoutMs = 15000;
    // A catalog bigger than this is a maintenance mistake, not a data set.
    static constexpr int kCatalogMaxBytes = 4 * 1024 * 1024;
    // Re-probing on every Dictionaries-pane visit would be wasteful against a
    // CDN-cached document, so the cached copy is reused until it is this old and
    // the user asks for the catalog.
    static constexpr int kCatalogRereprobeMs = 6 * 60 * 60 * 1000;

    // Initialized to the compiled-in default, deliberately NOT left empty:
    // loadSettings() returns early when settings.json does not exist (a fresh
    // install), so without this a first-run app would never probe the catalog
    // (fetchCatalog() bails on an empty URL) and the pane would sit on "Not
    // checked yet" until a restart wrote the file. Found on-device while
    // verifying public-catalog-hosting.
    QString m_remoteCatalogUrl = QLatin1String(kDefaultRemoteCatalogUrl);
    // Last-good manifest, cached in settings.json so it survives a restart and
    // renders while offline. m_manifestValid guards against a missing/!parsed
    // cache (there is no manifest to speak of until the first successful fetch).
    RemoteCatalog::Manifest m_manifest;
    bool m_manifestValid = false;
    // The exact bytes of the last-good manifest, so the offline cache is the
    // document the parser approved rather than a re-serialization of it.
    QString m_manifestRaw;
    QDateTime m_manifestFetched;
    bool m_catalogLoading = false;
    bool m_catalogReachable = false;
    QString m_catalogError;
    QString m_catalogUpdated;
    QString m_catalogLastFetched;
    QVariantList m_catalogEntries;
    // Installed catalog content identity: entryId -> { requiredFileName: sha256 },
    // recorded when a catalog download succeeds. Inert today (nothing reads it);
    // it lets a future update capability compare installed content against the
    // manifest without re-hashing the files. See public-catalog-hosting.
    QJsonObject m_installedDigests;
    QNetworkAccessManager *m_net = nullptr;
    // A fetch already in flight, so a refresh tap does not stack replies.
    bool m_catalogFetchInFlight = false;

    // ---------- Download state (mirrors shared_prefs/download.xml) ----------
    bool m_downloadActive = false;
    QString m_downloadEntryName;
    int m_downloadFilesDone = 0;
    int m_downloadFilesTotal = 0;
    qint64 m_downloadBytesDone = 0;
    qint64 m_downloadBytesTotal = 0;
    qreal m_downloadFraction = 0.0;
    QString m_downloadSpeed;
    QString m_downloadOutcome;
    QStringList m_downloadSucceeded;
    QStringList m_downloadFailed;
    QString m_downloadMessage;
    QString m_downloadScratchHashes;
};