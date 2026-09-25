import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtWebView

// All-Qt UI: search / dictionaries / groups / FTS / history / favorites /
// article panes switched by `state`, plus onboarding + theme.
// Material Design 3 via QtQuick.Controls2 (Material style). See the
// qt-material-ui change; the Material palette drives light/dark.
// NOTE: legacy component behavior (no `pragma ComponentBehavior: Bound`) —
// several delegates rely on the implicit `modelData`/`index` injection, which
// Bound would remove. The article WebView still resolves `engine` (context
// property) and outer ids across the Loader boundary as-is.
ApplicationWindow {
    id: root
    width: 480
    height: 800
    visible: true
    title: "Aurelex"

    // Material accent drives highlights; theme follows system dark with the
    // manual D-toggle override (see EngineController userDarkOverride/systemDark).
    // Task 3.1: Material.theme bound at the root so light/dark is driven by the
    // effective dark mode (JNI systemDark + userDarkOverride), not by Qt's own
    // (unreliable on Android 6.6) system detection.
    Material.accent: Material.Purple
    Material.theme: (engine.userDarkOverride || engine.systemDark)
                    ? Material.Dark : Material.Light

    // 0 = search, 1 = dictionaries, 2 = article, 3 = groups, 4 = fts,
    // 5 = history, 6 = favorites.
    property int state: 0
    property string currentWord: ""
    property string currentHtml: ""
    property var ftsResults: []
    // Whole-words FTS toggle state. Driven by a plain Button (like the "By Pair"
    // switch) rather than Button.checked so it renders exactly the same accent
    // fill as the other magenta buttons.
    property bool ftsWholeWordsOn: false
    // The article WebView is the Search tab's inline pane (articleLoader aliases
    // it); there is no separate full-pane article view — every article opens in
    // the inline Search surface.
    // Back-stack for in-article navigation. Each entry is a {word, html, group}
    // triple so the Back button can pop to the previous article without losing
    // scroll position (we re-render the prior article's HTML) and restore the
    // dictionary group it was produced in.
    property var navStack: []
    // Browser-like redo stack: words the user backed out of, re-opened by the
    // Forward control. Cleared whenever a fresh lookup happens (any new lookup
    // invalidates the forward path, like a browser).
    property var fwdStack: []
    // True while the foreground StagingService is copy-staging a picked folder.
    // Drives the Dicts-tab "Preparing dictionaries…" banner.
    property bool _stagingActive: engine.stagingActive

    // Material icon font family (registered from fonts.qrc in main.cpp) + the
    // icon-name -> codepoint helper (qt-material-ui task 7.2).
    property string iconFontFamily: "Material Icons"
    // Secondary icon font: a Material Symbols Outlined subset holding glyphs the
    // classic Material Icons set lacks. The registered family is the subset's
    // name (log: "Material Symbols Outlined"); symbolIcon emits the codepoints.
    property string symbolFontFamily: "Material Symbols Outlined"
    // Android system-window insets (logical px): the Qt window is edge-to-edge,
    // so our own chrome must sit below the status bar / above the navigation
    // bar. Converted from physical px returned by the activity via JNI. They are
    // recomputed on every window resize (e.g. portrait->landscape, where the
    // bottom inscription on gesture-nav devices moves to a side and the bottom
    // inset becomes 0) rather than captured once.
    property int _insetTop: 0
    property int _insetBottom: 0
    property real _insetDpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    // Briefly true after an orientation change: tears down both native WebViews
    // so they recreate at the new window geometry (a stale-size native surface
    // would otherwise cover sibling chrome — e.g. the bottom dock in landscape).
    property bool _geometryInvalid: false
    // Last observed window size, used to detect real orientation flips.
    // A pure resize (the Android IME showing/hiding resizes the window on
    // adjustResize) must NOT tear the WebView down — doing so killed the
    // suggestion overlay mid-typing (typed word, no candidates rendered).
    property int _lastGeoW: -1
    property int _lastGeoH: -1
    function _refreshInsets() {
        root._insetDpr = Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
        root._insetTop = Math.round(engine.systemInsetTop() / root._insetDpr)
        root._insetBottom = Math.round(engine.systemInsetBottom() / root._insetDpr)
        var w = root.width, h = root.height
        if (root._lastGeoW < 0) {
            root._lastGeoW = w; root._lastGeoH = h
            return
        }
        var prevLandscape = root._lastGeoW > root._lastGeoH
        var nowLandscape = w > h
        root._lastGeoW = w; root._lastGeoH = h
        // Only a true portrait<->landscape flip needs the WebView teardown:
        // both loaders' `active` bindings re-evaluate to false (destroying the
        // native surfaces) then true again next tick (recreating them at the new
        // window size). The inline currentHtml/overlay survive and re-render via
        // onLoaded/onLoadingChanged.
        if (prevLandscape !== nowLandscape) {
            root._geometryInvalid = true
            Qt.callLater(function(){ root._geometryInvalid = false })
        }
    }
    onWidthChanged: root._refreshInsets()
    onHeightChanged: root._refreshInsets()
    Component.onCompleted: root._refreshInsets()
    // First-launch tab routing happens on onBoardedChanged (not here):
    // engine.onboarded is only final after EngineController's ASYNC gd_init +
    // loadSettings() completes, so at Component.onCompleted it is still the
    // default false and the onboarding decision cannot be trusted yet.
    // Routing from the async signal is guarded by _bootRouted so the "Get
    // started" toggle (which also emits onboardedChanged) can never hijack the
    // user away from a tab they already navigated to.
    property bool _bootRouted: false

    Connections {
        target: engine
        function onBoardedChanged() {
            if (!root._bootRouted) {
                // The async init reported the real onboarding state: first run
                // lands on the Dicts tab (the welcome card overlays the Dicts
                // pane, which has no inline WebView); once onboarded, every
                // fresh launch must start on Search.
                root._bootRouted = true
                root.state = engine.onboarded ? 0 : 1
            }
        }
    }
    function icon( name ) {
        var map = {
            "search": 0xe8b6,
            "menu_book": 0xea19,
            "book": 0xea19,
            "library_books": 0xe02f,
            "manage_search": 0xf02f,
            "content_paste_search": 0xea9b,
            "star": 0xe838,
            "star_border": 0xe83a,
            "arrow_back": 0xe5c4,
            "arrow_forward": 0xe5c8,
            "close": 0xe5cd,
            "add": 0xe145,
            "check": 0xe5ca,
            "edit": 0xe150,
            "drag_handle": 0xe25d,
            "translate": 0xe8e2,
            "delete": 0xe872,
            "bookmark": 0xe866,
            "dark_mode": 0xe51c,
            "zoom_in": 0xe8ff,
            "zoom_out": 0xe900
        }
        return map[name] !== undefined ? String.fromCharCode(map[name]) : "\uFFFD"
    }
    // Material Symbols icons (rendered with symbolFontFamily): glyphs that only
    // exist in the Material Symbols Outlined subset (folder_open, match_word).
    function symbolIcon( name ) {
        var map = {
            "folder_open": 0xe2c8,
            "match_word": 0xf6f0
        }
        return map[name] !== undefined ? String.fromCharCode(map[name]) : "\uFFFD"
    }
    // Convenient Material palette aliases (replaces the old darkMode ternaries).
    property color uiBg: Material.background
    property color uiCard: Material.dialogColor
    property color uiBorder: Material.dividerColor
    property color uiFg: Material.foreground
    property color uiSubFg: Material.secondaryTextColor

    // Human-readable byte size: 145 MB, 1.2 GB, 500 KB, 42 B.
    function fmtSize(bytes) {
        if (!bytes || bytes <= 0) return ""
        const gb = 1024 * 1024 * 1024
        const mb = 1024 * 1024
        const kb = 1024
        if (bytes >= gb) return (Math.round(bytes * 10 / gb) / 10) + " " + qsTr("GB")
        if (bytes >= mb) return Math.round(bytes / mb) + " " + qsTr("MB")
        if (bytes >= kb) return Math.round(bytes / kb) + " " + qsTr("KB")
        return bytes + " " + qsTr("B")
    }
    // "English/Russian" with unknown side shown as '?'.
    function fmtPair(d) {
        const f = (d.langFrom && d.langFrom.length > 0) ? d.langFrom : "?"
        const t = (d.langTo && d.langTo.length > 0) ? d.langTo : "?"
        return f + "/" + t
    }
    function fmtSubLine(d) {
        const pair = root.fmtPair(d)
        const sz = root.fmtSize(d.sizeBytes)
        return sz.length > 0 ? pair + " · " + sz : pair
    }

    // All pane switches blur the focused input BEFORE hiding its pane:
    // an IME query arriving at a focused-but-hidden item can spin the
    // Qt tab-focus-chain walker forever (ANR deadlock with the IME's
    // blocking finishComposingText on the Android main thread).
    property bool inlineArticle: false
    // The lazily-created inline WebView (null when no inline article is showing).
    property var inlineWv: null
    // Set by a short timer once the Search tab is on-screen and measured, so the
    // inline WebView is created with a correct (band-sized) native surface rather
    // than a full-window one.
    property bool inlineWebReady: false
    Timer {
        id: inlineWebTimer
        interval: 420
        repeat: false
        running: root.state === 0
        onTriggered: root.inlineWebReady = true
    }
    onStateChanged: {
        if (root.state !== 0) {
            // Leaving the Search tab: mark that a return should restore the
            // field's focus and re-trigger suggestions (the inline WebView and
            // its suggestion overlay are destroyed on leaving). An inline
            // article is PRESERVED (currentHtml); returning re-renders it.
            root._returningToSearch = true
            root.inlineWebReady = false
            root.inlineWebTimer.stop()
        } else if (root._returningToSearch) {
            root._returningToSearch = false
            if (root.inlineArticle) {
                // An article was showing when we left; the loader re-creates
                // the WebView and re-renders currentHtml on its own (onLoaded
                // restarts articleLoadTimer). Don't force-suggest or refocus so
                // the article (and its field text) survives the round trip.
                return
            }
            // No article: refocus the field (so Enter works again) and
            // re-populate candidates for the text that's still typed. The
            // fresh inline WebView is (re)created by inlineWebTimer shortly
            // after; the pending suggestions are flushed once it's ready.
            input.forceActiveFocus()
            if (input.displayText.trim().length > 0) searchPane._doSuggest()
        }
    }
    // Guards the onStateChanged re-focus/re-suggest so it only runs on an
    // actual return to Search, not on first show.
    property bool _returningToSearch: false
    function _clearInlineArticle() {
        root.inlineArticle = false
        root.currentWord = ""
        root.currentHtml = ""
        root.navStack = []
        root.fwdStack = []
        root._hideSuggestOverlay()
        root._blankInline()
    }
    // Conceal the inline article (back to the candidate surface) WITHOUT
    // destroying the article nav history: currentWord/currentHtml and the
    // back/forward stacks are retained, so a subsequent lookup still pushes the
    // previous article and Back/Forward can re-open it. Used when the user types
    // over a shown article. _clearInlineArticle() remains the full reset
    // (leaving the tab / exiting to search).
    function _hideInlineArticle() {
        root.inlineArticle = false
        root._hideSuggestOverlay()
        root._blankInline()
    }
    function _blankInline() {
        if (root.inlineWv && engine.articleBaseUrl.length > 0) {
            // A suggestion injected before this blank load finishes gets wiped;
            // flag it so _renderSuggestOverlay defers (see _blankPending).
            root._blankPending = true
            root.inlineWv.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
        }
    }

    // --- search-suggestion overlay (rendered inside the inline article
    // WebView) --- QML items cannot stack above Android's native WebView
    // surface, so the candidate dropdown is an HTML <a> panel in the same
    // document (id `gd-sugg`, pinned to the top of the article pane). Each
    // entry carries data-w; the articleLinkPoller's click listener reads it and
    // dispatches engine.lookup() directly — no navigation, so the panel simply
    // collapses when the article loads. The candidate list is held in
    // _suggWords (authoritative, NOT consumed on render) and _applySuggestOverlay()
    // (re)renders it: it whenever safe; _flushPendingSugg() re-applies after any
    // load-settle, and _ensureInlineBlank() guarantees the WebView has a
    // document to inject into.
    property var _suggWords: []
    property bool _suggVisible: false
    // What the candidate overlay currently shows: "sugg" (headword suggestions
    // while typing) or "history" (recent lookups when the field is empty or a
    // query has no matches). Drives how _applySuggestOverlay builds the rows.
    property string _suggMode: "sugg"
    // Set while programmatically assigning input.text (article open via Back/
    // Forward/selection) so the onDisplayTextChanged -> _doSuggest path does
    // not race the article render with a suggestion re-query.
    property bool _suppressSuggest: false
    // True while `inlineWv` is loading a base document (fresh WebView or a
    // cleared article). An overlay injected before that load finishes is wiped
    // by the load completion, so re-apply is deferred while this is set;
    // onLoadingChanged clears it and flushes.
    property bool _blankPending: false
    function _escHtml(s) {
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    }
    function _renderSuggestOverlay(words) {
        root._suggMode = "sugg"
        root._suggWords = words
        articleLinkPoller._lastSugg = ""
        root._applySuggestOverlay()
    }
    // Show recent lookups in the candidate surface (empty field / no matches).
    function _showHistoryOverlay() {
        root._suggMode = "history"
        articleLinkPoller._lastSugg = ""
        root._suggWords = engine.history
        root._applySuggestOverlay()
    }
    function _applySuggestOverlay() {
        const wv = root.inlineWv
        // Need a live WebView that actually has a loaded document (URL present).
        // runJavaScript on a doc-less WebView silently does nothing.
        if (!wv || root._blankPending) return
        const words = root._suggWords
        const url = wv.url.toString()
        if (url.length < 6) return
        const base = engine.articleBaseUrl
        if (base.length < 5) return
        // History must NEVER sit under a typed query: if the box has text but the
        // surface is in history mode (stale from an earlier empty/fallback state),
        // drop the overlay entirely and let the pending suggestion render.
        if (root._suggMode === "history" && input.displayText.trim().length > 0) {
            root._clearOverlayDom()
            root._suggVisible = false
            return
        }
        // In suggestions mode, zero words means a query is still in flight (or
        // just started): render nothing (clear any stale overlay) until results
        // arrive. A history overlay with no entries still gets drawn (empty state).
        if (words.length === 0 && root._suggMode !== "history") {
            root._clearOverlayDom()
            root._suggVisible = false
            return
        }
        const dark = engine.darkMode
        const bg = dark ? "#242526" : "#ffffff"
        const fg = dark ? "#e0e0e0" : "#202124"
        const sep = dark ? "#3a3b3c" : "#eeeeee"
        const accent = dark ? "#b388ff" : "#6200ee"
        var html = '<div id="gd-sugg" style="position:fixed;top:0;left:0;right:0;'
            + 'z-index:9999;background:' + bg + ';color:' + fg + ';'
            + 'box-shadow:0 2px 10px rgba(0,0,0,0.4);overflow-y:auto;max-height:72%;'
            + 'font-family:Roboto,sans-serif;font-size:16px;text-align:left;">'
        if (root._suggMode === "history") {
            if (words.length === 0) {
                html += '<div style="padding:20px 16px;color:#999;text-align:center;">' + root._escHtml(qsTr("No lookups yet")) + '</div>'
            } else {
                // Recent lookups, most recent first, each tap-to-lookup with a
                // per-row remove; plus a Clear all row. The word is the entry's
                // `.word`; removal targets the exact (word, group) pair via
                // data-w + data-group. The articleLinkPoller dispatches both.
                for (var h = 0; h < words.length; ++h) {
                    const hwObj = words[h]
                    const hw = typeof hwObj === "string" ? hwObj : hwObj.word
                    const hg = (typeof hwObj === "string") ? 0 : (hwObj.group || 0)
                    const hgName = root._escHtml(engine.groupName(hg))
                    html += '<div style="display:flex;align-items:center;border-bottom:1px solid ' + sep + ';">'
                        + '<a id="gd-sugg-link" href="javascript:;" data-action="open-history" data-w="' + root._escHtml(hw)
                        + '" data-group="' + hg
                        + '" style="flex:1;padding:12px 16px;text-decoration:none;color:inherit;overflow:hidden;'
                        + 'text-overflow:ellipsis;white-space:nowrap;">'
                        + '<span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + root._escHtml(hw) + '</span>'
                        + '<span style="display:block;font-size:11px;color:#888;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + hgName + '</span>'
                        + '</a>'
                        + '<button data-action="remove-history" data-w="' + root._escHtml(hw)
                        + '" data-group="' + hg
                        + '" style="border:0;background:none;color:#999;font-size:18px;padding:4px 16px;">✕</button>'
                        + '</div>'
                }
                html += '<div style="padding:6px;text-align:center;border-top:1px solid ' + sep + ';">'
                    + '<a href="javascript:;" data-action="clear-history" style="display:inline-block;'
                    + 'padding:8px 16px;color:' + accent + ';text-decoration:none;font-size:14px;">' + root._escHtml(qsTr("Clear all")) + '</a>'
                    + '</div>'
            }
        } else {
            for (var i = 0; i < words.length; ++i) {
                const w = words[i]
                if (w.indexOf("(no results") === 0) {
                    html += '<div style="padding:12px 16px;color:#999;">' + root._escHtml(w) + '</div>'
                } else {
                    // Entries are plain anchors carrying data-w. The articleLinkPoller
                    // installs a click listener on #gd-sugg that reads data-w and calls
                    // engine.lookup() directly — no navigation, no article-server 404,
                    // no load race with the ensuing article render.
                    html += '<a id="gd-sugg-link" href="javascript:;" data-w="'
                        + root._escHtml(w) + '" style="display:block;padding:12px 16px;'
                        + 'border-bottom:1px solid ' + sep + ';text-decoration:none;color:inherit;">'
                        + root._escHtml(w) + '</a>'
                }
            }
        }
        html += '</div>'
        const script = '(function(){'
            + 'var e=document.getElementById("gd-sugg");if(e)e.remove();'
            + 'var st="' + bg + '";'
            + 'if(document.body){document.body.style.background=st;'
            + 'document.body.style.margin="0";}'
            + 'if(document.documentElement)document.documentElement.style.background=st;'
            + 'var d=document.createElement("div");d.id="gd-sugg";d.innerHTML='
            + JSON.stringify(html) + ';document.body.appendChild(d);})()'
        wv.runJavaScript(script)
        root._suggVisible = true
    }
    // Remove the overlay element from the live document if it exists.
    function _clearOverlayDom() {
        if (root.inlineWv) {
            root.inlineWv.runJavaScript(
                '(function(){var e=document.getElementById("gd-sugg");if(e)e.remove();})()')
        }
    }
    function _hideSuggestOverlay() {
        root._suggMode = "sugg"
        root._suggWords = []
        articleLinkPoller._lastSugg = ""
        if (root.inlineWv && root._suggVisible) root._clearOverlayDom()
        root._suggVisible = false
    }
    // Called on every load-settle (and after WebView recreation): re-render the
    // stored candidate list if it's safe to do so.
    function _flushPendingSugg() {
        root._blankPending = false
        root._applySuggestOverlay()
    }
    // Give the freshly-created inline WebView a real (blank) base document so
    // runJavaScript works — until a page is loaded the WebView has an empty URL
    // and no JS context, which silently swallows the suggestion-overlay
    // injection and the link poller.
    function _ensureInlineBlank() {
        // When NOT showing an article and there is no article to show, load a
        // blank base document so runJavaScript works for the candidate overlay.
        if (root.inlineWv && !root.inlineArticle && root.currentHtml.length === 0
            && engine.articleBaseUrl.length > 5) {
            root._blankPending = true
            root.inlineWv.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
        }
    }
    function _showArticle(word, html) {
        // A picked word replaces the candidate list — collapse the dropdown.
        root._hideSuggestOverlay()
        if (currentWord !== "" && currentWord !== word) {
            // Reassign a NEW array: push()/pop() on a `property var` don't
            // notify QML, so a binding on navStack.length would go stale.
            // Capture the producing group (engine.activeGroupId) so Back/Forward
            // can restore the scope the article was rendered in.
            root.navStack = root.navStack.concat([{ word: currentWord,
                                                    html: currentHtml,
                                                    group: engine.activeGroupId }])
            // A fresh lookup invalidates any forward (redo) path. Reassign too
            // so the Forward buttons' `enabled` binding re-evaluates to false.
            root.fwdStack = []
        }
        // Route any lookup to the Search tab's inline surface.
        if (root.state !== 0) state = 0
        currentWord = word
        currentHtml = html
        // Show the looked-up term in the search box (users see the article +
        // its word in the field, like a browser address bar).
        root._suppressSuggest = true
        input.text = word
        root._suppressSuggest = false
        _blurActive()
        inlineArticle = true
        articleLoadTimer.restart()
    }
    function _backFromArticle() {
        // Back/Forward only navigate between SEARCH RESULTS (previous/next
        // looked-up articles). At the oldest result there is nothing to go back
        // to — do nothing (the button is disabled), and never fall back to
        // popping the suggestion/history dropdown, which was confusing.
        if (navStack.length === 0) {
            root.fwdStack = []
            return
        }
        const prev = root.navStack[root.navStack.length - 1]
        root.navStack = root.navStack.slice(0, root.navStack.length - 1)
        // Push the article we're leaving onto the forward stack (new array so
        // the Forward buttons' enabled binding sees the change).
        if (root.currentWord.length > 0) {
            root.fwdStack = root.fwdStack.concat([{ word: currentWord,
                                                    html: currentHtml,
                                                    group: engine.activeGroupId }])
        }
        // Restore the group the previous article was produced in (fallback All)
        // before rendering it, and render inline.
        root._applyGroupForNav(prev.group)
        currentWord = prev.word
        currentHtml = prev.html
        // Reflect the previous article's word in the search box.
        root._suppressSuggest = true
        input.text = prev.word
        root._suppressSuggest = false
        inlineArticle = true
        articleLoadTimer.restart()
    }
    function _forwardFromArticle() {
        if (root.fwdStack.length === 0) return
        const next = root.fwdStack[root.fwdStack.length - 1]
        root.fwdStack = root.fwdStack.slice(0, root.fwdStack.length - 1)
        // Moving forward returns us to where we'd be on the back path.
        if (root.currentWord.length > 0) {
            root.navStack = root.navStack.concat([{ word: currentWord,
                                                    html: currentHtml,
                                                    group: engine.activeGroupId }])
        }
        // Restore the group then render inline.
        root._applyGroupForNav(next.group)
        currentWord = next.word
        currentHtml = next.html
        // Reflect the next article's word in the search box.
        root._suppressSuggest = true
        input.text = next.word
        root._suppressSuggest = false
        inlineArticle = true
        articleLoadTimer.restart()
    }
    // Restore a stored group (fallback to "All"=0 if the group no longer exists)
    // and keep the Search group picker's selection in sync.
    function _applyGroupForNav(groupId) {
        if (engine.groupExists(groupId)) {
            engine.setActiveGroup(groupId)
            searchGroupCombo.currentIndex = root._groupIndexForId(groupId)
        } else {
            engine.setActiveGroup(0)
            searchGroupCombo.currentIndex = root._groupIndexForId(0)
        }
    }
    function _groupIndexForId(groupId) {
        for (var i = 0; i < engine.groups.length; ++i) {
            if (engine.groups[i].id === groupId) return i
        }
        return 0
    }
    // Is `word` a favorite in the given group (favorites are {word, group})?
    function _isFavorite(word, group) {
        const favs = engine.favorites
        for (var i = 0; i < favs.length; ++i) {
            const e = favs[i]
            const w = (typeof e === "string") ? e : e.word
            const g = (typeof e === "string") ? 0 : (e.group || 0)
            if (w === word && g === group) return true
        }
        return false
    }
    function _blurActive() {
        if (root.activeFocusItem && root.activeFocusItem.forceActiveFocus === undefined) return
        if (input.activeFocus) input.focus = false
        if (renameGroupInput.activeFocus) renameGroupInput.focus = false
        if (createGroupNameInput.activeFocus) createGroupNameInput.focus = false
        if (ftsInput.activeFocus) ftsInput.focus = false
    }
    function _openDicts() {
        _blurActive()
        engine.refreshDictionaries()
        state = 1
    }
    function _openGroups() {
        _blurActive()
        engine.refreshGroups()
        state = 3
    }
    function _openFts() {
        _blurActive()
        // Don't clear ftsResults here: switching tabs must be idempotent, so
        // the last search results survive a round trip (the field keeps its
        // query and the results stay valid). A new search replaces them.
        state = 4
    }
    function _openFavorites() {
        _blurActive()
        state = 6
    }
    function _runFts() {
        // Single v1 mode: Wildcards (FTS::SearchMode=2). By default each term is
        // treated as a prefix (boo -> boo*); the "Match whole words" checkbox
        // switches to exact-term matching. The scope is the group selected in
        // the FTS tab's dropdown (All by default).
        let gid = 0
        if (ftsGroupCombo.currentIndex >= 0 && engine.groups.length > 0)
            gid = engine.groups[ftsGroupCombo.currentIndex].id
        engine.ftsSearch(ftsInput.text, 2, gid, root.ftsWholeWordsOn)
    }
    // Navigation labels/icons for the bottom TabBar. The visible `label` is
    // translated; `a11y` stays the literal English accessibility name so the
    // UIAutomator/Appium content-desc contract (AGENTS.md) is unaffected.
    property var navItems: [
        { idx: 0, label: qsTr("Search"), a11y: "Search", icon: "search" },
        { idx: 1, label: qsTr("Dicts"),  a11y: "Dicts",  icon: "book" },
        { idx: 3, label: qsTr("Groups"), a11y: "Groups", icon: "library_books" },
        { idx: 4, label: qsTr("FTS"),    a11y: "FTS",    icon: "manage_search" },
        { idx: 6, label: qsTr("Favs"),   a11y: "Favs",   icon: "star" }
    ]
    // Position of the nav-tab whose `idx` matches the current state (articles
    // always live in the Search tab, so state 0 is always a match). Drives
    // TabBar.currentIndex and the highlight; keeps the mapping in one place.
    function _tabIndexForState() {
        if (root.state === 2) return -1 // safety: no such state anymore
        for (var i = 0; i < root.navItems.length; ++i) {
            if (root.navItems[i].idx === root.state) return i
        }
        return -1
    }
    function _navTo(idx) {
        if (idx === 0) {
            _blurActive()
            // An article left over from another pane (full-pane article opened
            // from Favs/FTS) must not carry into a fresh Search — a stale
            // article would steal the WebView and the typed query's suggestions
            // would never show. Inline articles (opened IN Search) are kept:
            // leaving the tab only hides the WebView (the loader tears it down),
            // and returning re-renders currentHtml, so the article reappears.
            if (root.currentHtml.length > 0 && !root.inlineArticle) {
                root.currentWord = ""
                root.currentHtml = ""
            }
            state = 0
            return
        }
        // Leaving the search tab: keep any inline article state (currentWord /
        // currentHtml / navStack) so a return restores the shown article. The
        // inline WebView itself is destroyed by the loader, not here — no
        // need to wipe anything; returning re-renders from currentHtml.
        if (idx === 1) { _openDicts(); return }
        if (idx === 3) { _openGroups(); return }
        if (idx === 4) { _openFts(); return }
        if (idx === 6) { _openFavorites(); return }
    }

    Connections {
        target: engine
        function onFtsSearchReady(query, results) {
            if (query !== ftsInput.text) return
            ftsResults = results
        }
    }

    // --- shared top chrome (system-status-bar strip) ---
    // The window is edge-to-edge, so this strip sits behind the status icons
    // and paints them onto our background. It holds no interactive content
    // (per design: nothing goes in the unsafe top area).
    Rectangle {
        id: topBar
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: root._insetTop
        color: root.uiBg
        z: 5
    }

// --- bottom chrome (navigation dock + dark toggle + system-nav strip) ---
    // The Qt window is edge-to-edge; the dock sits above the system navigation
    // bar (insetBottom) and its tab cells stay within the safe area, while a
    // strip below repaints the nav-bar region in our background color.
    Rectangle {
        id: navDock
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 56 + root._insetBottom
        z: 5
        color: root.uiBg

        Row {
            id: navRow
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 56
            spacing: 0

            TabBar {
                id: navBar
                // Five nav tabs take 5/6 of the dock; the theme cell (a sibling
                // below) takes the last 1/6. As a sibling — not a TabBar child —
                // it can never become the "active tab".
                width: navRow.width - Math.round(navRow.width / 6)
                height: navRow.height
                // TabBar tabs tile the bar exactly (spacing 0 + exact-fill
                // widths) so the row is never horizontally scrollable.
                spacing: 0
                clip: true
                Accessible.name: "Main navigation"
                Accessible.role: Accessible.TabBar
                // 5.2: highlight the active tab by driving the TabBar's own
                // selection (TabButton has no `highlighted` in Qt 6.6). State ->
                // tab position via _tabIndexForState(); article pane has no tab.
                // The Theme tab is last and never matches a state.
                currentIndex: root._tabIndexForState()

                Repeater {
                    model: root.navItems
                    delegate: TabButton {
                        id: tabBtn
                        // Five equal nav cells across the TabBar.
                        width: navBar.width / 5
                        height: parent.height
                        // icon glyph + label in the theme font (a single-font
                        // `text` would render the icon glyphs as broken Latin).
                        contentItem: Column {
                            anchors.centerIn: parent
                            spacing: 0
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: root.icon(modelData.icon)
                                font.family: root.iconFontFamily
                                font.pixelSize: 18
                                color: tabBtn.down || tabBtn.checked ? tabBtn.Material.accentColor
                                                                     : tabBtn.Material.foreground
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: modelData.label
                                font.pixelSize: 10
                                color: tabBtn.down || tabBtn.checked ? tabBtn.Material.accentColor
                                                                      : tabBtn.Material.foreground
                            }
                        }
                        Accessible.name: modelData.a11y
                        Accessible.role: Accessible.TabButton
                        onClicked: root._navTo(modelData.idx)
                    }
                }
            }

            // Theme toggle: the 6th cell, a SIBLING of the TabBar so it can
            // never become the selected tab. Forces dark (or follows the system
            // theme); does not navigate.
            Button {
                id: themeBtn
                width: navRow.width - navBar.width
                height: navRow.height
                flat: true
                contentItem: Column {
                    // The theme cell is sibling to the TabBar (no active-tab
                    // underline), and the Material Button's content area sits a
                    // touch lower than the TabButtons' — nudge it up so the
                    // icon+label line up with the tabs.
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.verticalCenterOffset: -2
                    spacing: 0
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: root.icon("dark_mode")
                        font.family: root.iconFontFamily
                        font.pixelSize: 18
                        color: themeBtn.down ? themeBtn.Material.accentColor
                                            : themeBtn.Material.foreground
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: qsTr("Theme")
                        font.pixelSize: 10
                        color: themeBtn.down ? themeBtn.Material.accentColor
                                            : themeBtn.Material.foreground
                    }
                }
                Accessible.name: engine.userDarkOverride || engine.systemDark ? "Light mode" : "Dark mode"
                Accessible.role: Accessible.Button
                onClicked: {
                    engine.toggleDarkOverride()
                    root._blurActive()
                }
            }
        }

        // Repaint the system-navigation-bar strip in our background color.
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: root._insetBottom
            color: root.uiBg
        }
    }

    // --- search view ---
    Rectangle {
        id: searchPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navDock.top }
        color: root.uiBg
        visible: root.state === 0

        function _doSuggest() {
            // Programmatic box updates (article open via Back/Forward) must not
            // re-trigger a suggestion query that would race the article render.
            if (root._suppressSuggest) return
            const t = input.displayText
            if (t.trim().length === 0) {
                // Empty field: concealing any open article and showing history.
                // History is retained (not wiped) so Back/Forward can still
                // re-open the concealed article after a later lookup.
                if (root.inlineArticle) root._hideInlineArticle()
                root._showHistoryOverlay()
                return
            }
            // When the user types a new query, conceal any open article but keep
            // the article nav history so Back still reaches the previous article.
            if (root.inlineArticle) {
                root._hideInlineArticle()
            }
            // Immediately switch the surface to suggestions-pending: clear any
            // stale history/suggestion overlay so nothing lingers under a typed
            // query while the engine is still working.
            root._suggMode = "sugg"
            root._suggWords = []
            articleLinkPoller._lastSugg = ""
            root._applySuggestOverlay()
            engine.suggest(t)
        }

        property var pendingSuggestions: []

        Connections {
            target: engine
            function onSuggestionsReady(prefix, suggestions) {
                // Only apply results for the query still in the box. A result
                // for an earlier query (e.g. the user cleared the field and no
                // new suggest fired, so the engine's stale-guard didn't drop it)
                // must not overwrite what the empty field now shows (history).
                // NB: compare against displayText, not text — during IME
                // composition text lags behind what the user sees/typed.
                if (prefix.trim() !== input.displayText.trim()) return
                searchPane.pendingSuggestions = suggestions
                // A typed query that matches nothing falls back to history.
                if (suggestions.length === 0) {
                    root._showHistoryOverlay()
                } else {
                    root._renderSuggestOverlay(suggestions)
                }
            }
            function onArticleNotFound(word) {
                // A failed lookup returns the surface to history (only while the
                // field is empty or matches the failed word; a new typed query
                // must keep showing its own suggestions instead).
                const cur = input.displayText.trim()
                if (cur.length === 0 || word.trim() === cur)
                    root._showHistoryOverlay()
            }
        }

ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            // Search + group scope + clipboard on one line. Search takes ~70% of
            // the row, the group dropdown ~30%; the clipboard is a small icon
            // button. With a single group the scope can't change, so the dropdown
            // is disabled (still visible, showing the current scope).
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                TextField {
                    id: input
                    Layout.fillWidth: true
                    Layout.preferredWidth: 7
                    placeholderText: qsTr("Search dictionaries")
                    Accessible.name: "Search dictionaries"
                    Accessible.role: Accessible.EditableText
                    font.pixelSize: 18
                    onDisplayTextChanged: searchPane._doSuggest()
                    onAccepted: { input.focus = false; root._requestedWord = text.trim(); engine.lookup(text.trim()) }
                    Component.onCompleted: {
                        // Focus the field + show the keyboard only AFTER
                        // onboarding — on first run the keyboard must not pop
                        // up behind the welcome overlay.
                        if (engine.onboarded) forceActiveFocus()
                    }
                }

                ComboBox {
                    id: searchGroupCombo
                    Layout.fillWidth: true
                    Layout.preferredWidth: 3
                    enabled: engine.groups.length > 1
                    model: engine.groups
                    textRole: "name"
                    Accessible.name: "Search group scope"
                    Accessible.role: Accessible.ComboBox
                    // The article WebView sits ABOVE Qt's own popup surface, so a
                    // normal ComboBox dropdown would be hidden behind it. Instead
                    // tapping the control opens a modal group picker (a Dialog that
                    // first hides the WebView). Selecting there applies the group.
                    // Keep the widget from opening its own popup by never letting
                    // it get pressed-under: a transparent MouseArea on top
                    // intercepts taps and routes them to the picker.
                    MouseArea {
                        anchors.fill: parent
                        enabled: searchGroupCombo.enabled
                        z: parent.z + 1
                        onClicked: {
                            if (engine.groups.length > 1) {
                                input.focus = false
                                groupPicker.openAt(searchGroupCombo.currentIndex)
                            }
                        }
                    }
                    // Floating "Group" caption, mirroring the search field's
                    // floating placeholder: a tiny label sits on the combo's top
                    // border (left) so the field reads as a labelled control even
                    // though a ComboBox always has a selected value. It doesn't
                    // grab pointer events, so taps fall through to the dropdown.
                    Label {
                        text: qsTr("Group")
                        // Match the floated placeholder of the search field
                        // (Qt floats TextField placeholders at 0.75x its font).
                        font.pixelSize: Math.round(input.font.pixelSize * 0.75)
                        color: root.uiSubFg
                        z: 3
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.leftMargin: 10
                        anchors.topMargin: -6
                        background: Rectangle {
                            color: root.uiBg
                            anchors.fill: parent
                            anchors.leftMargin: -3
                            anchors.rightMargin: -3
                            anchors.topMargin: 2
                            anchors.bottomMargin: 3
                        }
                    }
                }

                ToolButton {
                    id: clipboardBtn
                    text: root.icon("content_paste_search")
                    font.family: root.iconFontFamily
                    font.pixelSize: 20
                    Accessible.name: "Clipboard"
                    Accessible.role: Accessible.Button
                    // Paste clipboard text into the search field (so the looked-up
                    // word is visible in the box) and run the lookup.
                    onClicked: {
                        const t = engine.clipboardText()
                        if (t.length > 0) {
                            input.text = t
                            input.forceActiveFocus()
                            root._requestedWord = t
                            engine.lookup(t)
                        }
                    }
                }
            }



            Label {
                Layout.fillWidth: true
                visible: engine.lastError.length > 0
                text: qsTr("engine error: %1").arg(engine.lastError)
                color: Material.color(Material.Red)
                wrapMode: Text.Wrap
            }

            // Inline article area: a permanent browser pane filling the Search
            // tab below the search row. It is always present while on this tab
            // (never hidden while a WebView is alive — a hidden-but-alive native
            // WebView overlays the whole screen on Android), and is destroyed on
            // leaving the tab so it never covers the other panes. The warm
            // WebView gives near-instant re-renders. Search suggestions render as
            // an <a> dropdown INSIDE this WebView (main.qml _renderSuggestOverlay):
            // QML controls cannot draw over Android's native WebView surface, so
            // the dropdown lives in the same HTML document as the article.
            Rectangle {
                id: searchArticleArea
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 300
                color: root.uiBg

                Rectangle {
                    id: inlineArticleToolbar
                    // Nav/star controls only exist while a real article is shown;
                    // with nothing open (suggestions/history) the header collapses
                    // and the WebView fills the pane.
                    visible: root.inlineArticle
                    width: parent.width
                    height: root.inlineArticle ? 40 : 0
                    // Frameless header: the icons sit directly on the pane. The
                    // background MUST be themed (a Rectangle defaults to white,
                    // which broke dark mode for this stripe).
                    color: root.uiBg

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 4
                        anchors.rightMargin: 4
                        spacing: 4

                        // Spacer right-justifies the controls.
                        Item { Layout.fillWidth: true }

                        ToolButton {
                            text: root.icon("arrow_back")
                            font.family: root.iconFontFamily
                            font.pixelSize: 22
                            enabled: root.navStack.length > 0
                            Accessible.name: "Back"
                            Accessible.role: Accessible.Button
                            onClicked: root._backFromArticle()
                        }
                        ToolButton {
                            text: root.icon("arrow_forward")
                            font.family: root.iconFontFamily
                            font.pixelSize: 22
                            enabled: root.fwdStack.length > 0
                            Accessible.name: "Forward"
                            Accessible.role: Accessible.Button
                            onClicked: root._forwardFromArticle()
                        }
                        ToolButton {
                            property bool active: root._isFavorite(root.currentWord, engine.activeGroupId)
                            text: root.icon(active ? "star" : "star_border")
                            font.family: root.iconFontFamily
                            font.pixelSize: 22
                            Material.foreground: active ? Material.primary : root.uiSubFg
                            Accessible.name: active ? "Remove from favorites" : "Add to favorites"
                            Accessible.role: Accessible.Button
                            onClicked: engine.toggleFavorite(root.currentWord)
                        }

                        // Article reflow zoom: icon-only controls (no visible text),
                        // disabled at the range bounds so the header never offers a
                        // no-op tap. engine.setArticleZoom clamps/snaps anyway.
                        ToolButton {
                            text: root.icon("zoom_out")
                            font.family: root.iconFontFamily
                            font.pixelSize: 20
                            enabled: engine.articleZoom > engine.articleZoomMin
                            Accessible.name: "Zoom out"
                            Accessible.role: Accessible.Button
                            onClicked: engine.setArticleZoom(engine.articleZoom - engine.articleZoomStep)
                        }
                        ToolButton {
                            text: root.icon("zoom_in")
                            font.family: root.iconFontFamily
                            font.pixelSize: 20
                            enabled: engine.articleZoom < engine.articleZoomMax
                            Accessible.name: "Zoom in"
                            Accessible.role: Accessible.Button
                            onClicked: engine.setArticleZoom(engine.articleZoom + engine.articleZoomStep)
                        }
                    }
                }

                Loader {
                    id: searchArticleLoader
                    anchors { top: parent.top; topMargin: inlineArticleToolbar.height; left: parent.left; right: parent.right; bottom: parent.bottom }
                    // Defer WebView creation until the scene is measured.
                    // On Android, a WebView created before layout runs locks its
                    // native surface to a wrong (full-window) size that then
                    // overtakes the whole screen. inlineWebReady is set by a
                    // short timer once the Search tab is actually visible.
                    active: root.state === 0 && root.inlineWebReady && !root._pickerOpen && !root._geometryInvalid
                    onLoaded: {
                        root.inlineWv = item
                        // Give the fresh WebView a document to run JS against.
                        root._ensureInlineBlank()
                        // Re-render an already-loaded article when returning to
                        // the tab (the WebView was just recreated).
                        if (root.currentHtml.length > 0) articleLoadTimer.restart()
                    }
                    onActiveChanged: { root._blankPending = false; if (!active) root.inlineWv = null }
                    sourceComponent: Component {
                        WebView {
                            id: searchArticleView
                            anchors.fill: parent
                            Accessible.name: "Dictionary article"
                            Accessible.role: Accessible.WebView
                            onUrlChanged: {
                                const u = url.toString()
                                const base = engine.articleBaseUrl
                                if (base.length > 0 && u.indexOf(base + "/gdlookup/") === 0) {
                                    const word = _parseGdlookupHttpUrl(u, base)
                                    if (word.length > 0) {
                                        _gdlookupInFlight = word
                                        root._requestedWord = word
                                        engine.lookup(word)
                                    }
                                    searchArticleView.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
                                    return
                                }
                                if (u.indexOf("gdlookup://") === 0) {
                                    const word = _parseGdlookupUrl(u)
                                    if (word.length > 0) {
                                        _gdlookupInFlight = word
                                        root._requestedWord = word
                                        engine.lookup(word)
                                    }
                                    searchArticleView.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
                                    return
                                }
                                if (base.length > 0 && u.indexOf(base + "/gdau/") === 0) {
                                    engine.playAudio(u)
                                    searchArticleView.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
                                    return
                                }
                            }
                            onLoadingChanged: {
                                if (!loading) {
                                    // Blank base document settled: safe to inject
                                    // any suggestions that arrived meanwhile.
                                    root._blankPending = false
                                    root._flushPendingSugg()
                                    // With nothing typed and no article open, the
                                    // empty Search surface falls back to history.
                                    if (root.state === 0 && !root.inlineArticle
                                        && input.displayText.trim().length === 0)
                                        root._showHistoryOverlay()
                                    // A suggestion can land a tick AFTER this flush
                                    // (e.g. a lookup raced a WebView recreation after
                                    // returning from another pane). Re-apply on the
                                    // next event-loop turn so it still renders.
                                    Qt.callLater(function(){
                                        root._blankPending = false
                                        root._applySuggestOverlay()
                                    })
                                }
                            }
                            onHeightChanged: {
                                if (root.state === 0 && root.inlineArticle
                                    && searchArticleView.height !== root.loadedAtHeight
                                    && root.currentHtml.length > 0)
                                    articleReloader.restart()
                            }
                        }
                    }
                }
            }
        }
    }

    // --- dictionaries view ---
    Rectangle {
        id: dictsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navDock.top }
        color: root.uiBg
        visible: root.state === 1

        Component.onCompleted: engine.refreshDictionaries()
        property bool byPair: false
        // Indices of selected dictionary rows (for Delete selection).
        property var selectedDicts: []
        // Flattened model for By-Pair view: entries are either
        // {type:"header", pair:...} or {type:"dict", ...dict}. Rebuilt whenever
        // dictionaries or the toggle change.
        property var groupedModel: []
        function _rebuildGrouped() {
            const rows = []
            const d = engine.dictionaries
            // group by pair, keep alphabetical-by-name order within each.
            const byPair = {}
            for (let i = 0; i < d.length; i++) {
                const p = root.fmtPair(d[i])
                if (!byPair[p]) byPair[p] = []
                byPair[p].push({ index: i, item: d[i] })
            }
            const pairs = Object.keys(byPair).sort()
            for (const p of pairs) {
                rows.push({ type: "header", pair: p })
                for (const it of byPair[p]) rows.push({ type: "dict", dictIndex: it.index, item: it.item })
            }
            dictsPane.groupedModel = rows
        }
        function _toggleSelect(idx) {
            const sel = dictsPane.selectedDicts
            const i = sel.indexOf(idx)
            if (i >= 0) sel.splice(i, 1)
            else sel.push(idx)
            dictsPane.selectedDicts = sel
        }
        // True when every dictionary in `pair` is selected (header check mark).
        function _pairSelected(pair) {
            const sel = dictsPane.selectedDicts
            for (let i = 0; i < engine.dictionaries.length; i++) {
                if (root.fmtPair(engine.dictionaries[i]) === pair
                    && sel.indexOf(i) < 0)
                    return false
            }
            return true
        }
        // Tap a pair (section) header to select or clear every dictionary in
        // that pair. Mixed state: selects the unselected ones (full select);
        // fully selected pair: clears the whole section.
        function _toggleSelectPair(pair) {
            const idxs = []
            for (let i = 0; i < engine.dictionaries.length; i++) {
                if (root.fmtPair(engine.dictionaries[i]) === pair) idxs.push(i)
            }
            const allSelected = idxs.every(i => dictsPane.selectedDicts.indexOf(i) >= 0)
            const sel = dictsPane.selectedDicts.slice()
            if (allSelected) {
                // Clear only this pair's indices, keep other selections.
                dictsPane.selectedDicts = sel.filter(i => idxs.indexOf(i) < 0)
            } else {
                for (const i of idxs) {
                    if (sel.indexOf(i) < 0) sel.push(i)
                }
                dictsPane.selectedDicts = sel
            }
        }
        function _removeSelected() {
            // Copy indices high-to-low so removal doesn't shift later ones; then
            // clear the selection and refresh.
            const sel = dictsPane.selectedDicts.slice().sort((a,b)=>b-a)
            for (const idx of sel) engine.removeDictionary(idx)
            dictsPane.selectedDicts = []
        }
        Connections {
            target: engine
            function onDictionariesChanged() { dictsList.model = engine.dictionaries; dictsPane.selectedDicts = []; dictsPane._rebuildGrouped() }
            function onReadyChanged() { if (engine.ready) engine.refreshDictionaries() }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            // Processing banner: surfaces BOTH long-running phases after you
            // add a folder — the stage copy (foreground StagingService) and the
            // automatic full-text index build (foreground IndexingService). Both
            // run in the background, so without this the Dicts tab looks frozen
            // for tens of seconds while dictionaries "quietly" load.
            Rectangle {
                Layout.fillWidth: true
                visible: root._stagingActive || engine.scanningActive || engine.buildingFts
                color: Material.color(Material.Purple, Material.Shade50)
                radius: 4
                height: processingCol.implicitHeight + 20

                ColumnLayout {
                    id: processingCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6

                    // Header carries the currently-indexing dictionary (1-based).
                    Label {
                        Layout.fillWidth: true
                        text: root._stagingActive ? qsTr("Preparing dictionaries…")
                            : engine.scanningActive ? qsTr("Scanning dictionaries…")
                            : qsTr("Indexing (%1 of %2): %3")
                              .arg(engine.ftsIndexDone + 1)
                              .arg(engine.ftsIndexTotal)
                              .arg(engine.ftsCurrentDictName)
                        font.pixelSize: 13
                        font.bold: true
                        color: Material.color(Material.Purple)
                        elide: Text.ElideMiddle
                        wrapMode: Text.Wrap
                    }

                    // Top bar: this dictionary's own progress (resumes where it
                    // left off after an interrupted build).
                    ProgressBar {
                        Layout.fillWidth: true
                        visible: engine.buildingFts
                        indeterminate: false
                        from: 0
                        to: 1
                        value: engine.ftsDictFraction
                        Accessible.role: Accessible.ProgressBar
                    }

                    // Bottom bar: all-dictionaries progress (no caption).
                    ProgressBar {
                        Layout.fillWidth: true
                        visible: engine.buildingFts
                        indeterminate: false
                        from: 0
                        to: 1
                        value: engine.ftsIndexFraction
                        Accessible.role: Accessible.ProgressBar
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: !engine.buildingFts
text: root._stagingActive
                          ? qsTr("Copying dictionary files into app storage. Your dictionaries will appear here when it's done.")
                          : qsTr("Reading dictionary files…")
                        color: root.uiSubFg
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // "Add" (folder-scoped SAF picker). Qt 6.6 RoundButton stands in
                // for the Material 3 FloatingActionButton; the folder-open icon
                // signals importing from local storage.
                RoundButton {
                    highlighted: true
                    Accessible.name: "Add"
                    Accessible.role: Accessible.Button
                    onClicked: engine.addDictionaryFolder()
                    contentItem: RowLayout {
                        spacing: 6
                        Label {
                            text: root.symbolIcon("folder_open")
                            font.family: root.symbolFontFamily
                            font.pixelSize: 18
                            color: Material.primaryHighlightedTextColor
                            Layout.alignment: Qt.AlignVCenter
                        }
                        Label {
                            text: qsTr("Add")
                            font.pixelSize: 14
                            font.bold: true
                            color: Material.primaryHighlightedTextColor
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }
                }
                // Delete selection: sits right next to Add, styled like the
                // By Pair toggle — gray while nothing is selected, magenta
                // (highlighted) once a selection exists.
                Button {
                    text: qsTr("Remove")
                    highlighted: dictsPane.selectedDicts.length > 0
                    enabled: dictsPane.selectedDicts.length > 0
                    Accessible.name: "Remove"
                    Accessible.role: Accessible.Button
                    onClicked: dictsPane._removeSelected()
                }
                // By Pair toggle: group the dictionary list by Source/Target.
                Button {
                    text: root.icon("translate")
                    font.family: root.iconFontFamily
                    font.pixelSize: 18
                    highlighted: dictsPane.byPair
                    Accessible.name: "By Pair"
                    Accessible.role: Accessible.Button
                    onClicked: dictsPane.byPair = !dictsPane.byPair
                }
            }

            Label {
                Layout.fillWidth: true
                color: root.uiSubFg
                font.pixelSize: 12
                wrapMode: Text.Wrap
                text: qsTr("Tap Add dictionaries to import a folder containing dictionary files (.mdx, .dsl, .dsl.dz, .ifo). The folder is copied into the app once; no system-wide storage access is needed.")
            }

            // Dictionaries that failed to load in the last scan (corrupt or
            // truncated source files). Surface them so the user knows a
            // dictionary is missing; the fix is to re-add the folder, which
            // wipes the old copy and re-stages it.
            Rectangle {
                Layout.fillWidth: true
                visible: engine.scanFailures.length > 0
                color: Material.color(Material.Red, Material.Shade50)
                radius: 4
                height: failuresCol.implicitHeight + 16

                ColumnLayout {
                    id: failuresCol
                    anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 8 }
                    anchors.leftMargin: 10; anchors.rightMargin: 10
                    spacing: 4

                    Label {
                        Layout.fillWidth: true
                        text: qsTr("%1 dictionary file(s) failed to load").arg(engine.scanFailures.length)
                        font.pixelSize: 13
                        font.bold: true
                        color: Material.color(Material.Red)
                        wrapMode: Text.Wrap
                    }
                    Repeater {
                        model: engine.scanFailures
                        delegate: Label {
                            Layout.fillWidth: true
                            text: modelData.file
                            font.pixelSize: 11
                            elide: Text.ElideMiddle
                            color: root.uiSubFg
                            wrapMode: Text.Wrap
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        text: qsTr("The file may be incomplete or corrupt. Tap Add dictionaries and pick the same folder again to re-copy it.")
                        font.pixelSize: 11
                        color: root.uiSubFg
                        wrapMode: Text.Wrap
                    }
                }
            }

            // Flat list (By Pair off): alphabetical by name.
            ListView {
                id: dictsList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: engine.dictionaries
                spacing: 2
                visible: !dictsPane.byPair
                Accessible.name: "Dictionaries list"
                Accessible.role: Accessible.List
                delegate: ItemDelegate {
                    id: dictRow
                    property int dictIndex: index
                    property var dictData: modelData
                    width: ListView.view.width
                    height: 76
                    padding: 8
                    // Selected (for RemoveSelected) highlight.
                    highlighted: dictsPane.selectedDicts.indexOf(dictRow.dictIndex) >= 0
                    // Tap toggles multi-select selection.
                    onClicked: dictsPane._toggleSelect(dictRow.dictIndex)

                    Accessible.name: dictRow.dictData.name
                    Accessible.role: Accessible.ListItem

                    contentItem: RowLayout {
                        spacing: 8
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Label {
                                text: dictRow.dictData.name
                                font.pixelSize: 16
                                font.bold: true
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }
                            Label {
                                // Source/Target · size; size hidden while indexing.
                                text: engine.buildingFts
                                    ? root.fmtPair(dictRow.dictData)
                                    : root.fmtSubLine(dictRow.dictData)
                                color: root.uiSubFg
                                font.pixelSize: 12
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }

            // Grouped list (By Pair on): header rows + dict rows from a flattened model.
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: dictsPane.groupedModel
                spacing: 2
                visible: dictsPane.byPair
                Accessible.name: "Dictionaries list by pair"
                Accessible.role: Accessible.List
                delegate: ItemDelegate {
                    id: bpRow
                    width: ListView.view.width
                    height: modelData.type === "header" ? 34 : 76
                    padding: 8
                    // Selected (for batch removal) highlight on dict rows.
                    highlighted: modelData.type !== "header"
                        && dictsPane.selectedDicts.indexOf(modelData.dictIndex) >= 0
                    Accessible.name: modelData.type === "header" ? modelData.pair : modelData.item.name
                    Accessible.role: Accessible.ListItem
                    contentItem: Loader {
                        anchors.fill: parent
                        sourceComponent: modelData.type === "header" ? headerComp : dictComp
                    }

                    Component {
                        id: headerComp
                        RowLayout {
                            anchors.fill: parent
                            spacing: 8
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                color: Material.color(Material.Purple, Material.Shade50)
                                z: -1
                            }
                            Label {
                                Layout.fillWidth: true
                                text: modelData.pair
                                font.pixelSize: 12
                                font.bold: true
                                color: root.uiSubFg
                                verticalAlignment: Text.AlignVCenter
                            }
                            // Check indicator: reflects whether every dictionary
                            // in this pair is selected.
                            Label {
                                text: root.icon("check")
                                font.family: root.iconFontFamily
                                font.pixelSize: 16
                                color: root.uiSubFg
                                visible: dictsPane._pairSelected(modelData.pair)
                            }
                        }
                    }

                    // The pair header tap toggles the whole section's selection.
                    onClicked: {
                        if (modelData.type === "header")
                            dictsPane._toggleSelectPair(modelData.pair)
                        else
                            dictsPane._toggleSelect(modelData.dictIndex)
                    }

                    Component {
                        id: dictComp
                        RowLayout {
                            anchors.fill: parent
                            spacing: 8
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Label {
                                    text: modelData.item.name
                                    font.pixelSize: 16
                                    font.bold: true
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                Label {
                                    text: engine.buildingFts
                                        ? root.fmtPair(modelData.item)
                                        : root.fmtSubLine(modelData.item)
                                    color: root.uiSubFg
                                    font.pixelSize: 12
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }
        }

        // --- onboarding overlay (first run) ---
        // Rendered as a full-pane Rectangle inside the Dicts tab (not a Dialog):
        // on Android, normal scene items receive taps reliably while popup
        // overlays can miss them. First run routes to the Dicts tab, and this
        // tab has no inline WebView, so the dim + card can't be punctured by a
        // native surface. Fills the safe content-pane area exactly.
        Rectangle {
            id: onboardingOverlay
            anchors.fill: parent
            visible: !engine.onboarded
            color: Qt.rgba(0, 0, 0, 0.5)

            Rectangle {
                anchors.centerIn: parent
                width: parent.width - 80
                implicitHeight: onbCol.implicitHeight + 48
                color: root.uiCard
                radius: 12
                border.color: root.uiBorder

                ColumnLayout {
                    id: onbCol
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 16

                    Label {
                        Layout.fillWidth: true
                        text: qsTr("Welcome to Aurelex")
                        font.pixelSize: 22
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                    }
                    Label {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: qsTr("Add dictionaries by tapping Add dictionaries below and picking a folder with dictionary files (.mdx, .dsl, .dsl.dz, .ifo) — the folder is copied into the app once (no system-wide storage access needed). Use the bottom bar to switch between Search, Dictionaries, Groups, FTS and Favorites.")
                        font.pixelSize: 15
                        wrapMode: Text.Wrap
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: root.uiFg
                    }
                    Button {
                        id: onboardingGetStarted
                        Layout.alignment: Qt.AlignHCenter
                        text: qsTr("Get started")
                        highlighted: true
                        Accessible.name: "Get started"
                        Accessible.role: Accessible.Button
                        onClicked: {
                            engine.onboarded = true
                            // Onboarding is over (the Dicts tab was only chosen
                            // to host the welcome overlay) — land on Search.
                            root.state = 0
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        id: groupsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navDock.top }
        color: root.uiBg
        visible: root.state === 3

        property int editingGroup: -1
        property string editingGroupName: ""
        property var groupMembers: []
        property var groupNonMembers: []
        property int renameGroupId: -1
        property string renameGroupName: ""
        property string renameGroupNameError: ""
        property int deleteGroupId: -1
        property string deleteGroupName: ""
        // "Add group" dialog state: the pending name and any inline error.
        property string createGroupNameError: ""
        // Drag-to-reorder state for the member list. _dragFrom is the member
        // index the gesture started on; _dragStartY the finger's Y at
        // press-and-hold; _dragLastTo the last index we moved to (so crossing a
        // row boundary fires exactly one engine move). Cleared on release.
        property int _dragFrom: -1
        property real _dragStartY: 0
        property int _dragLastTo: -1
        property bool _dragArmed: false
        // Mark the row that's being dragged/reordered so the active
        // line is visible while the finger moves it.
        property int _dragIndex: -1
        // Single-shot watchdog for the reorder gesture. The member MouseArea's
        // `released` can be lost (the ListView recycles its delegate mid-drag),
        // so ending the drag must not depend on it: every press/move restarts
        // this timer, and when it fires (~300 ms of no motion = finger up) the
        // drag is finalized and the highlight clears.

        function _dragBegin(index, mouseY) {
            // Any row can be dragged up or down; _dragMove clamps to the list
            // bounds and no-ops within the same slot.
            groupsPane._dragFrom = index
            groupsPane._dragStartY = mouseY
            groupsPane._dragLastTo = index
            groupsPane._dragIndex = index
            groupsPane._dragArmed = true
            dragWatchdog.restart()
        }
        function _dragMove(mouseY) {
            if (!groupsPane._dragArmed) return
            dragWatchdog.restart()
            const dy = mouseY - groupsPane._dragStartY
            // 44 = member row height. Round to the nearest row boundary; each
            // crossed boundary moves the row one slot (delta-based, so it works
            // regardless of the list's scroll offset).
            const to = groupsPane._dragFrom + Math.round(dy / 44)
            const n = groupsPane.groupMembers.length
            if (to < 0 || to >= n || to === groupsPane._dragLastTo) return
            groupsPane._dragLastTo = to
            engine.groupMoveDict(groupsPane.editingGroup, groupsPane._dragFrom, to)
            groupsPane._dragFrom = to
            groupsPane._dragIndex = to
        }
        function _dragEnd() {
            groupsPane._dragArmed = false
            groupsPane._dragFrom = -1
            groupsPane._dragLastTo = -1
            groupsPane._dragIndex = -1
            dragWatchdog.stop()
        }
        Timer {
            id: dragWatchdog
            interval: 400
            repeat: false
            onTriggered: groupsPane._dragEnd()
        }

        function _openMembership(id, name) {
            editingGroup = id
            editingGroupName = name
            // Reset the child lists so opening always starts blank: stale
            // members from a previous open can linger otherwise, and the
            // membership ColumnLayout shows stale rows until the async
            // onGroupDictsReady replaces them.
            groupsPane.groupMembers = []
            groupsPane.groupNonMembers = []
            engine.groupDicts(id)
        }
        function _openRename(id, name) {
            if (id <= 0) return // "All" cannot be renamed
            renameGroupId = id
            renameGroupName = name
            renameGroupNameError = ""     // fresh open: no stale "already exists"
            renameGroupDialog.open()
        }
        function _requestDeleteGroup(id, name) {
            if (id <= 0) return // "All" cannot be deleted
            deleteGroupId = id
            deleteGroupName = name
        }
        function _confirmDeleteGroup() {
            const id = deleteGroupId
            deleteGroupId = -1
            deleteGroupName = ""
            if (id > 0) engine.deleteGroup(id)
        }
        function _cancelDeleteGroup() {
            deleteGroupId = -1
            deleteGroupName = ""
        }
        function _refreshMembership() {
            if (editingGroup !== -1) {
                engine.groupDicts(editingGroup)
                engine.refreshGroups()
            }
        }
        function _openCreateGroup(initial) {
            groupsPane.createGroupNameError = ""
            createGroupNameInput.text = initial !== undefined ? initial : ""
            createGroupNameInput.forceActiveFocus()
            createGroupDialog.open()
        }
        function _confirmCreateGroup() {
            const name = createGroupNameInput.text.trim()
            if (name.length === 0) return
            // Immediate duplicate check on the in-memory group list (the engine
            // is the backstop but emits asynchronously). Case-insensitive, same
            // rule as gd_group_create. On a duplicate the dialog stays open and
            // shows the inline error — no reopen dance needed.
            for (let i = 0; i < engine.groups.length; ++i) {
                if (String(engine.groups[i].name).toLowerCase() === name.toLowerCase()) {
                    groupsPane.createGroupNameError = qsTr("A group named \"%1\" already exists").arg(name)
                    createGroupNameInput.forceActiveFocus()
                    return
                }
            }
            engine.createGroup(name)
            createGroupDialog.close()
        }
        function _confirmRenameGroup() {
            const name = renameGroupInput.text.trim()
            const id = groupsPane.renameGroupId
            if (name.length === 0 || id <= 0) return
            // Immediate duplicate check (in-memory list) — on a duplicate the
            // dialog stays open showing the inline error.
            for (let i = 0; i < engine.groups.length; ++i) {
                const g = engine.groups[i]
                if (g.id === id) continue
                if (String(g.name).toLowerCase() === name.toLowerCase()) {
                    groupsPane.renameGroupNameError = qsTr("A group named \"%1\" already exists").arg(name)
                    renameGroupInput.forceActiveFocus()
                    return
                }
            }
            engine.renameGroup(id, name)
            // The editor header keeps its own copy of the group name; refresh
            // it so the title stops showing a stale name until the list
            // re-renders (renameGroup is async, but the editor stays open).
            if (groupsPane.editingGroup === id)
                groupsPane.editingGroupName = name
            renameGroupDialog.close()
        }

        Component.onCompleted: engine.refreshGroups()
        Connections {
            target: engine
            function onGroupsChanged() { groupsList.model = engine.groups }
            function onReadyChanged() { if (engine.ready) engine.refreshGroups() }
            // The engine committed a group-membership mutation (add/remove/move).
            // _refreshMembership() re-queries AFTER the async commit, so the
            // member list and the row dict-count always reflect the new state.
            function onGroupMembersChanged() { groupsPane._refreshMembership() }
            // A group was created: land straight in its membership editor.
            function onGroupCreated(groupId, name) {
                if (groupId > 0)
                    groupsPane._openMembership(groupId, name)
            }
            // The name is taken (create or rename): surface it inline.
            function onGroupNameTaken(name) {
                // Rename or create: the standard OK button already closed the
                // dialog, so re-open it with the error and the typed name.
                // Set the error AFTER (re)opening — _openCreateGroup clears it
                // for a fresh open, so the message must land after the dialog
                // is back up.
                if (groupsPane.renameGroupId > 0 || renameGroupName !== "") {
                    groupsPane.renameGroupName = name
                    renameGroupDialog.open()
                    groupsPane.renameGroupNameError = qsTr("A group named \"%1\" already exists").arg(name)
                    return
                }
                _openCreateGroup(name)
                groupsPane.createGroupNameError = qsTr("A group named \"%1\" already exists").arg(name)
            }
            function onGroupDictsReady(groupId, dicts) {
                if (groupId !== groupsPane.editingGroup) return
                const m = []
                const nm = []
                for (let i = 0; i < dicts.length; i++) {
                    if (dicts[i].member) m.push(dicts[i])
                    else nm.push(dicts[i])
                }
                // Members must display in the GROUP's order (memberIndex = the
                // position inside the group's membership list), not in the
                // global dictionary order the query happens to return them in.
                // Without this, "Move up"/"Move down" changes were invisible.
                for (let i = 1; i < m.length; ++i) {
                    const row = m[i]
                    let j = i - 1
                    while (j >= 0 && m[j].memberIndex > row.memberIndex) {
                        m[j + 1] = m[j]
                        --j
                    }
                    m[j + 1] = row
                }
                groupsPane.groupMembers = m
                groupsPane.groupNonMembers = nm
                // The membership editor may be freshly shown (or the same group
                // reopened): force the two lists to re-layout so dict names are
                // always drawn, not left blank from a stale frame.
                Qt.callLater(function() {
                    if (groupsPane.editingGroup !== groupId) return
                    memberList.forceLayout()
                    if (nonMemberList) nonMemberList.forceLayout()
                })
            }
        }

        // --- group list mode ---
        ColumnLayout {
            visible: groupsPane.editingGroup === -1
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // "Add" button opens the name dialog; a new group is created and
                // the membership editor opens immediately on OK.
                Button {
                    text: qsTr("Add group")
                    highlighted: true
                    Accessible.name: "Add group"
                    Accessible.role: Accessible.Button
                    onClicked: groupsPane._openCreateGroup()
                }
            }

            ListView {
                id: groupsList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: engine.groups
                spacing: 2
                Accessible.name: "Groups list"
                Accessible.role: Accessible.List
                delegate: ItemDelegate {
                    id: groupRow
                    property var groupData: modelData
                    width: ListView.view.width
                    height: 56
                    padding: 4
                    Accessible.name: groupRow.groupData.name
                    Accessible.role: Accessible.ListItem

                    // Tapping the group name opens the membership editor; the
                    // trash asks for confirmation before deleting. Rename lives
                    // inside the editor (no pencil on the row).
                    contentItem: Label {
                        text: qsTr("%1 (%2)").arg(groupRow.groupData.name).arg(groupRow.groupData.dictCount)
                        font.pixelSize: 16
                        font.bold: true
                        elide: Text.ElideMiddle
                        verticalAlignment: Text.AlignVCenter
                        rightPadding: 56
                    }

                    RowLayout {
                        anchors {
                            right: parent.right
                            rightMargin: 4
                            verticalCenter: parent.verticalCenter
                        }
                        spacing: 2

                        // Trash asks for confirmation first.
                        ToolButton {
                            text: root.icon("delete")
                            font.family: root.iconFontFamily
                            font.pixelSize: 20
                            visible: groupRow.groupData.id !== 0
                            Accessible.name: "Delete"
                            Accessible.role: Accessible.Button
                            onClicked: groupsPane._requestDeleteGroup(groupRow.groupData.id, groupRow.groupData.name)
                        }
                    }

                    onClicked: {
                        // Only editable groups open the membership editor;
                        // "All" is a fixed, always-present group.
                        if (groupRow.groupData.id !== 0)
                            groupsPane._openMembership(groupRow.groupData.id, groupRow.groupData.name)
                    }
                }
            }
        }

        // --- create-group dialog ---
        // Add a group by typing a name then OK: the group is created and the
        // membership editor opens immediately. Duplicate names show an inline
        // error (the engine also rejects them).
        Dialog {
            id: createGroupDialog
            anchors.centerIn: parent
            width: Math.min(parent.width - 80, 360)
            modal: true
            title: qsTr("Add group")
            Accessible.name: "Add group"
            Accessible.role: Accessible.Dialog
            standardButtons: Dialog.NoButton

            contentItem: ColumnLayout {
                width: parent.width
                spacing: 8
                TextField {
                    id: createGroupNameInput
                    Layout.fillWidth: true
                    placeholderText: qsTr("New group name")
                    font.pixelSize: 16
                    Accessible.name: "New group name"
                    Accessible.role: Accessible.EditableText
                    onAccepted: groupsPane._confirmCreateGroup()
                }
                Label {
                    Layout.fillWidth: true
                    visible: groupsPane.createGroupNameError.length > 0
                    text: groupsPane.createGroupNameError
                    color: Material.color(Material.Red)
                    wrapMode: Text.Wrap
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    Button {
                        text: qsTr("Cancel")
                        Accessible.name: "Cancel"
                        Accessible.role: Accessible.Button
                        onClicked: createGroupDialog.close()
                    }
                    Button {
                        text: qsTr("Create")
                        highlighted: true
                        Accessible.name: "Create"
                        Accessible.role: Accessible.Button
                        onClicked: groupsPane._confirmCreateGroup()
                    }
                }
            }
        }

        // --- rename-group dialog ---
        // A working rename (the old menu item just appended "_r" to the name).
        // Prefills the current name and puts the cursor in the field (NO full
        // selection — the user can edit in place). Empty names are rejected
        // (gd_group_rename refuses empty names anyway).
        Dialog {
            id: renameGroupDialog
            anchors.centerIn: parent
            width: Math.min(parent.width - 80, 360)
            modal: true
            title: qsTr("Rename group")
            Accessible.name: "Rename group"
            Accessible.role: Accessible.Dialog
            standardButtons: Dialog.NoButton

            contentItem: ColumnLayout {
                width: parent.width
                spacing: 8
                TextField {
                    id: renameGroupInput
                    Layout.fillWidth: true
                    font.pixelSize: 16
                    Accessible.name: "New group name"
                    Accessible.role: Accessible.EditableText
                    onAccepted: groupsPane._confirmRenameGroup()
                }
                Label {
                    Layout.fillWidth: true
                    visible: groupsPane.renameGroupNameError.length > 0
                    text: groupsPane.renameGroupNameError
                    color: Material.color(Material.Red)
                    wrapMode: Text.Wrap
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    Button {
                        text: qsTr("Cancel")
                        Accessible.name: "Cancel"
                        Accessible.role: Accessible.Button
                        onClicked: renameGroupDialog.close()
                    }
                    Button {
                        text: qsTr("Rename")
                        highlighted: true
                        Accessible.name: "Rename group"
                        Accessible.role: Accessible.Button
                        onClicked: groupsPane._confirmRenameGroup()
                    }
                }
            }

            onOpened: {
                renameGroupInput.text = groupsPane.renameGroupName
                // Place the caret at the end instead of selecting the whole
                // name: the user may want to append, and the field is never
                // left with an accidental full overwrite.
                renameGroupInput.cursorPosition = renameGroupInput.text.length
                renameGroupInput.forceActiveFocus()
            }
        }

        // --- delete-group confirm dialog ---
        // Deleting a group is destructive (membership is gone for good), so ask
        // before acting. Mirrors the remove-dictionary confirmation style.
        Dialog {
            id: deleteGroupDialog
            anchors.centerIn: parent
            width: Math.min(parent.width - 80, 360)
            modal: true
            title: qsTr("Delete group")
            visible: groupsPane.deleteGroupId > 0
            Accessible.name: "Delete group confirmation"
            Accessible.role: Accessible.Dialog

            ColumnLayout {
                width: parent.width
                spacing: 8
                Label {
                    Layout.fillWidth: true
                    text: qsTr('Delete group "%1"?').arg(groupsPane.deleteGroupName)
                    wrapMode: Text.Wrap
                }
                Label {
                    Layout.fillWidth: true
                    color: root.uiSubFg
                    text: qsTr("The group and its dictionary order are removed. The dictionaries themselves are not deleted.")
                    wrapMode: Text.Wrap
                }
            }

            standardButtons: Dialog.Cancel | Dialog.Ok

            onAccepted: groupsPane._confirmDeleteGroup()
            onRejected: groupsPane._cancelDeleteGroup()
        }

        // --- membership editor mode ---
        ColumnLayout {
            visible: groupsPane.editingGroup !== -1
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                ToolButton {
                    text: root.icon("arrow_back")
                    font.family: root.iconFontFamily
                    font.pixelSize: 22
                    Accessible.name: "Back"
                    Accessible.role: Accessible.Button
                    onClicked: groupsPane.editingGroup = -1
                }
                Label {
                    Layout.fillWidth: true
                    // Just the group name — it's inside the group's editor, so
                    // a "Group: " prefix would be redundant.
                    text: groupsPane.editingGroupName
                    font.pixelSize: 16
                    font.bold: true
                    elide: Text.ElideMiddle
                }
                ToolButton {
                    text: root.icon("edit")
                    font.family: root.iconFontFamily
                    font.pixelSize: 22
                    Accessible.name: "Rename group"
                    Accessible.role: Accessible.Button
                    onClicked: groupsPane._openRename(groupsPane.editingGroup, groupsPane.editingGroupName)
                }
            }

            Label { text: qsTr("In this group (%1)").arg(groupsPane.groupMembers.length); color: root.uiSubFg; font.pixelSize: 13 }

            ListView {
                id: memberList
                Layout.fillWidth: true
                Layout.preferredHeight: 190
                clip: true
                model: groupsPane.groupMembers
                spacing: 2
                Accessible.name: "Group members"
                Accessible.role: Accessible.List
                delegate: ItemDelegate {
                    id: memberRow
                    property var rowData: modelData
                    width: ListView.view.width
                    height: 44
                    padding: 4
                    // Mark the row that's being dragged/reordered so the active
                    // line is visible while the finger moves it.
                    highlighted: memberRow.rowData.memberIndex === groupsPane._dragIndex
                    Accessible.name: memberRow.rowData.name
                    Accessible.role: Accessible.ListItem

                    contentItem: RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        // The whole row is the drag surface: grab anywhere on
                        // the member and drag up/down to reorder. The row's
                        // delegate has no tap action, so there's nothing for an
                        // accidental tap to break; the right-hand Remove button
                        // sits above this bag and still receives its taps.
                        MouseArea {
                            anchors { top: parent.top; bottom: parent.bottom; left: parent.left; right: parent.right }
                            // Leave the right-most sliver clear so the Remove
                            // button (a sibling overlapping this bag) still gets
                            // its taps; the whole NAME area stays draggable.
                            anchors.rightMargin: 90
                            // Keep the ListView's flick-scroll from stealing the
                            // gesture once a reorder drag starts.
                            preventStealing: true
                            Accessible.name: "Reorder"
                            Accessible.role: Accessible.Button
                            onPressed: (mouse) => {
                                groupsPane._dragBegin(memberRow.rowData.memberIndex, mouse.y)
                            }
                            onPositionChanged: (mouse) => {
                                groupsPane._dragMove(mouse.y)
                            }
                            onReleased: groupsPane._dragEnd()
                        }
                        Label {
                            text: root.icon("drag_handle")
                            font.family: root.iconFontFamily
                            font.pixelSize: 20
                            color: root.uiSubFg
                        }
                        Label {
                            Layout.fillWidth: true
                            text: memberRow.rowData.name
                            elide: Text.ElideMiddle
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    RowLayout {
                        anchors {
                            right: parent.right
                            rightMargin: 4
                            verticalCenter: parent.verticalCenter
                        }
                        spacing: 2
                        ToolButton {
                            text: root.icon("close")
                            font.family: root.iconFontFamily
                            font.pixelSize: 20
                            Accessible.name: "Remove from group"
                            Accessible.role: Accessible.Button
                            onClicked: engine.groupRemoveDict(groupsPane.editingGroup, memberRow.rowData.index)
                        }
                    }
                }
            }

            Label { text: qsTr("Add dictionaries"); color: root.uiSubFg; font.pixelSize: 13 }

            ListView {
                id: nonMemberList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: groupsPane.groupNonMembers
                spacing: 2
                Accessible.name: "Available dictionaries to add"
                Accessible.role: Accessible.List
                delegate: ItemDelegate {
                    id: nonMemberRow
                    property var rowData: modelData
                    width: ListView.view.width
                    height: 44
                    padding: 4
                    Accessible.name: nonMemberRow.rowData.name
                    Accessible.role: Accessible.ListItem

                    contentItem: Label {
                        text: nonMemberRow.rowData.name
                        elide: Text.ElideMiddle
                        verticalAlignment: Text.AlignVCenter
                    }

                    ToolButton {
                        anchors {
                            right: parent.right
                            rightMargin: 4
                            verticalCenter: parent.verticalCenter
                        }
                        text: root.icon("add")
                        font.family: root.iconFontFamily
                        font.pixelSize: 20
                        Accessible.name: "Add to group"
                        Accessible.role: Accessible.Button
                        onClicked: engine.groupAddDict(groupsPane.editingGroup, nonMemberRow.rowData.index)
                    }
                }
            }
        }
    }

    function _parseGdlookupUrl(u) {
        const q = u.indexOf("?")
        if (q >= 0) {
            const params = u.substring(q + 1).split("&")
            for (let i = 0; i < params.length; ++i) {
                const kv = params[i].split("=")
                if (kv.length === 2 && kv[0] === "word") {
                    return decodeURIComponent(kv[1].replace(/\+/g, " "))
                }
            }
            return ""
        }
        const slash = u.indexOf("/", "gdlookup://".length)
        if (slash < 0) return ""
        return decodeURIComponent(u.substring(slash + 1))
    }
    property string _gdlookupInFlight: ""
    // The most recent word requested via a lookup. engine.lookup is async; a
    // slow (mutex-contended) lookup for an OLD word can complete after the user
    // already navigated elsewhere — _showArticle guards against that so a stale
    // article can't replace the current search/suggestions.
    property string _requestedWord: ""

    function _parseGdlookupHttpUrl(u, base) {
        const rest = u.substring((base + "/gdlookup/").length)
        const q = rest.indexOf("?")
        if (q >= 0) {
            const params = rest.substring(q + 1).split("&")
            for (let i = 0; i < params.length; ++i) {
                const kv = params[i].split("=")
                if (kv.length === 2 && kv[0] === "word") {
                    return decodeURIComponent(kv[1].replace(/\+/g, " "))
                }
            }
            return ""
        }
        return decodeURIComponent(rest)
    }

    // --- favorites view ---
    Rectangle {
        id: favoritesPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navDock.top }
        color: root.uiBg
        visible: root.state === 6

        ListView {
            anchors.fill: parent
            anchors.margins: 12
            clip: true
            model: engine.favorites
            spacing: 2
            Accessible.name: "Favorites"
            Accessible.role: Accessible.List
            delegate: ItemDelegate {
                id: favRow
                property string word: typeof modelData === "string" ? modelData : modelData.word
                property int group: (typeof modelData === "string") ? 0 : (modelData.group || 0)
                width: ListView.view.width
                height: 48
                Accessible.name: favRow.word
                Accessible.role: Accessible.ListItem
                contentItem: RowLayout {
                    spacing: 0
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Label {
                            Layout.fillWidth: true
                            text: favRow.word
                            elide: Text.ElideMiddle
                            leftPadding: 16
                            font.pixelSize: 16
                        }
                        Label {
                            Layout.fillWidth: true
                            text: engine.groupName(favRow.group)
                            elide: Text.ElideMiddle
                            leftPadding: 16
                            font.pixelSize: 11
                            color: root.uiSubFg
                        }
                    }
                    // "X to remove" matches the history overlay (no swipe gesture).
                    ToolButton {
                        text: root.icon("close")
                        font.family: root.iconFontFamily
                        font.pixelSize: 18
                        flat: true
                        Accessible.name: "Remove"
                        Accessible.role: Accessible.Button
                        onClicked: engine.toggleFavoriteEntry(favRow.word, favRow.group)
                    }
                }
                onClicked: {
                    root._requestedWord = favRow.word
                    engine.lookupInGroupWithSwitch(favRow.word, favRow.group)
                }
            }
        }
    }

    Connections {
        target: engine
        function onArticleLoaded(word, html) {
            // Drop stale lookups: a slow engine reply for a word the user no
            // longer asked for must not replace the current pane.
            if (root._requestedWord.length > 0 && word !== root._requestedWord) return
            root._requestedWord = ""
            root._showArticle(word, html)
        }
    }

    Connections {
        target: engine
        // History changed (a new lookup was recorded, an item removed, or the
        // list cleared): if the candidate surface is showing history, refresh
        // the overlay so removals/clears reflect immediately.
        function onHistoryChanged() {
            if (root._suggMode === "history") root._showHistoryOverlay()
        }
    }

    Connections {
        target: engine
        // The active group changed (a history/favorite item was opened, a group
        // picked, or Back/Forward restored one). Keep the Search group combo in
        // sync so both boxes reflect the item's data. The combo may not contain
        // the group if it was deleted → _groupIndexForId falls back to All (0).
        function onActiveGroupChanged() {
            searchGroupCombo.currentIndex = root._groupIndexForId(engine.activeGroupId)
        }
    }

    Connections {
        target: engine
        // Dark mode flips the OPEN article in place: rewriteArticleUrls always
        // injects darkreader + a gdSetDarkMode controller, so on the toggle we
        // just call it on the live document — no re-lookup/reload, no scroll
        // reset. The candidate overlay (suggestions/history) re-renders with the
        // new palette too. Runs synchronously on darkModeChanged.
        function onDarkModeChanged() {
            root._applyArticleDarkMode()
            root._applySuggestOverlay()
        }
    }

    Connections {
        target: engine
        // Article zoom reflows the OPEN article in place via the injected
        // gdSetZoom controller — no reload, scroll preserved (same contract as
        // onDarkModeChanged). A not-loaded WebView is a no-op; freshly rendered
        // articles get the level baked in by rewriteArticleUrls anyway.
        function onArticleZoomChanged() {
            root._applyArticleZoom()
        }
    }

    Connections {
        target: engine
        function onArticleBaseUrlChanged() {
            if (root.inlineArticle && currentHtml.length > 0)
                _loadArticleNow()
            else if (state === 0) root._ensureInlineBlank()
        }
    }

    Timer {
        id: articleLoadTimer
        // Coalesce rapid navigation; short enough that the render starts almost
        // immediately (the engine pre-parses the article, and with the cache
        // _showArticle often already has the full HTML in hand).
        interval: 60
        onTriggered: root._loadArticleNow()
    }
    Timer {
        id: articleReloader
        interval: 200
        onTriggered: root._loadArticleNow()
    }
    property real loadedAtHeight: 0
    function _loadArticleNow() {
        const html = engine.rewriteArticleUrls(currentHtml)
        const base = engine.articleBaseUrl.length > 0 ? engine.articleBaseUrl + "/" : ""
        if (root.inlineWv) {
            loadedAtHeight = root.inlineWv.height
            root.inlineWv.loadHtml(html, base)
        }
    }
    // Flip the OPEN article's dark mode in place via the injected gdSetDarkMode
    // controller — instant, no reload, scroll position preserved. No article
    // open? The next rendered document gets the baked-in mode from
    // rewriteArticleUrls, so nothing to do here.
    function _applyArticleDarkMode() {
        if (root.inlineWv && root.inlineWv.url.toString().length > 5) {
            root.inlineWv.runJavaScript("try{if(window.gdSetDarkMode)gdSetDarkMode("
                + (engine.darkMode ? 1 : 0) + ");}catch(e){}")
        }
    }
    // Reflow the OPEN article to the current zoom via the injected gdSetZoom
    // controller — instant, no reload. No live document? rewriteArticleUrls bakes
    // the saved level into the next render, so nothing to do here.
    function _applyArticleZoom() {
        if (root.inlineWv && root.inlineWv.url.toString().length > 5) {
            root.inlineWv.runJavaScript("try{if(window.gdSetZoom)gdSetZoom("
                + engine.articleZoom + ");}catch(e){}")
        }
    }
    Timer {
        id: articleLinkPoller
        // 120 ms: fast enough that suggestion-dropdown taps feel instant, slow
        // enough to not hammer the WebView with runJavaScript calls.
        interval: 120
        repeat: true
        running: root.state === 0
        onTriggered: {
            // Only the inline Search article exists now.
            const wv = root.inlineWv
            if (!wv || wv.url.toString().length < 5) return
            wv.runJavaScript(
                "if(!window.__probeInstalled){"
                + "window.__tapped='';window.__suggWord='';window.__gdAction='';"
                + "document.addEventListener('click',function(e){"
                + "var n=e.target.closest?e.target.closest('[data-action],[data-w]'):null;"
                + "if(n){"
                + "if(n.getAttribute('data-action')){window.__gdAction=n.getAttribute('data-action')+'|'+(n.getAttribute('data-w')||'')+'|'+(n.getAttribute('data-group')||'');}"
                + "else if(n.tagName==='A'){window.__suggWord=n.getAttribute('data-w');}"
                + "e.preventDefault();return;}"
                + "var a=e.target.closest?e.target.closest('a'):null;"
                + "window.__tapped=(a?a.href:'');},true);"
                + "window.__probeInstalled=true;}"
                + "var act=window.__gdAction||'';window.__gdAction='';"
                + "var s=window.__suggWord||'';window.__suggWord='';"
                + "(act ? 'ACT:'+act : (s ? 'SUGG:'+s : (window.__tapped || '')))",
                function(v){
                    if (!v) return
                    if (v.indexOf("ACT:") === 0) {
                        // History overlay actions: remove-history|word|group or
                        // clear-history|. Per-entry removal uses (word, group).
                        const rest = v.substring(4)
                        const parts = rest.split("|")
                        const action = parts[0] || ""
                        const arg = parts[1] || ""
                        const grp = parseInt(parts[2] || "0", 10)
                        if (action === "remove-history" && arg.length > 0) {
                            engine.removeHistoryEntry(arg, isNaN(grp) ? 0 : grp)
                            // The tap happened inside the WebView, so Qt focus is
                            // not on the search field even though it looks focused
                            // (keyboard may still show). Put focus back so the
                            // next keystroke actually types.
                            input.forceActiveFocus()
                        }
                        else if (action === "open-history" && arg.length > 0) {
                            root._requestedWord = arg
                            engine.lookupInGroupWithSwitch(arg, isNaN(grp) ? 0 : grp)
                        }
                        else if (action === "clear-history") {
                            engine.clearHistory()
                            input.forceActiveFocus()
                        }
                        return
                    }
                    if (v.indexOf("SUGG:") === 0) {
                        const word = v.substring(5)
                        if (word.length > 0 && word !== articleLinkPoller._lastSugg) {
                            articleLinkPoller._lastSugg = word
                            root._hideSuggestOverlay()
                            root._requestedWord = word
                            engine.lookup(word)
                        }
                        return
                    }
                    if (v !== articleLinkPoller._prev) {
                        articleLinkPoller._prev = v
                        _handleArticleLink(v)
                    }
                })
        }
        property string _prev: ""
        property string _lastSugg: ""
    }

    function _handleArticleLink(link) {
        const base = engine.articleBaseUrl
        if (base.length < 5) return
        if (link.indexOf(base + "/gdau/") === 0) {
            engine.playAudio(link)
            return
        }
        if (link.indexOf(base + "/gdlookup/") === 0) {
            const word = _parseGdlookupHttpUrl(link, base)
            if (word.length > 0) { root._requestedWord = word; engine.lookup(word) }
            return
        }
    }

    // --- FTS view ---
    Rectangle {
        id: ftsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navDock.top }
        color: root.uiBg
        visible: root.state === 4

        Connections {
            target: engine
            function onBuildingFtsChanged() { ftsInput.enabled = !engine.buildingFts; ftsSearchBtn.enabled = !engine.buildingFts }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                TextField {
                    id: ftsInput
                    Layout.fillWidth: true
                    Layout.preferredWidth: 7
                    placeholderText: qsTr("Full-text search")
                    font.pixelSize: 18
                    enabled: !engine.buildingFts
                    Accessible.name: "Full-text search"
                    Accessible.role: Accessible.EditableText
                    onAccepted: { ftsInput.focus = false; root._runFts() }
                }

                // Group scope for full-text search (mirrors the Search tab's
                // scope). "All" (index 0) is first and selected by
                // default; choosing a group searches only that group's dicts.
                // A transparent MouseArea routes taps to the same modal group
                // picker the Search tab uses (its native popup would render
                // oddly here; the dialog is the established pattern).
                ComboBox {
                    id: ftsGroupCombo
                    Layout.fillWidth: true
                    Layout.preferredWidth: 3
                    enabled: engine.groups.length > 1
                    model: engine.groups
                    textRole: "name"
                    Accessible.name: "Full-text search group scope"
                    Accessible.role: Accessible.ComboBox
                    MouseArea {
                        anchors.fill: parent
                        enabled: ftsGroupCombo.enabled
                        z: parent.z + 1
                        onClicked: {
                            if (engine.groups.length > 1) {
                                ftsInput.focus = false
                                groupPicker.openAt(ftsGroupCombo.currentIndex, "fts")
                            }
                        }
                    }
                    // Floating "Group" caption (mirrors the Search tab's combo).
                    Label {
                        text: qsTr("Group")
                        font.pixelSize: Math.round(input.font.pixelSize * 0.75)
                        color: root.uiSubFg
                        z: 3
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.leftMargin: 10
                        anchors.topMargin: -6
                        background: Rectangle {
                            color: root.uiBg
                            anchors.fill: parent
                            anchors.leftMargin: -3
                            anchors.rightMargin: -3
                            anchors.topMargin: 2
                            anchors.bottomMargin: 3
                        }
                    }
                }

                // Whole-words toggle as an icon button, styled exactly like the Dicts
                // "By Pair" switch: NOT checkable (an external bool drives
                // `highlighted`), so it uses the same accent fill as the other
                // magenta buttons. Filled + white glyph when ON, flat gray glyph
                // when OFF. Reads in light and dark mode.
                Button {
                    id: ftsWholeWords
                    highlighted: root.ftsWholeWordsOn
                    Layout.preferredWidth: 48
                    // The Material Button's default padding is icon-aware and
                    // asymmetric; equalize it so the centered glyph really sits
                    // in the middle of the button.
                    leftPadding: 12
                    rightPadding: 12
                    enabled: !engine.buildingFts
                    Accessible.name: "Whole words"
                    Accessible.role: Accessible.CheckBox
                    onClicked: {
                        root.ftsWholeWordsOn = !root.ftsWholeWordsOn
                        if (ftsInput.text.trim().length > 0) root._runFts()
                    }
                    contentItem: Text {
                        text: root.symbolIcon("match_word")
                        font.family: root.symbolFontFamily
                        font.pixelSize: 20
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: root.ftsWholeWordsOn
                            ? ftsWholeWords.Material.primaryHighlightedTextColor
                            : ftsWholeWords.Material.foreground
                    }
                }
            }

            // 8.1: index-build progress is shown in the Dicts tab banner; the
            // FTS pane only disables its controls while building (no duplicate
            // bars).

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    id: ftsSearchBtn
                    text: qsTr("Search")
                    highlighted: true
                    enabled: !engine.buildingFts
                    Accessible.name: "Search"
                    Accessible.role: Accessible.Button
                    onClicked: root._runFts()
                }
            }

            Label {
                Layout.fillWidth: true
                visible: engine.lastError.length > 0
                text: qsTr("engine error: %1").arg(engine.lastError)
                color: Material.color(Material.Red)
                wrapMode: Text.Wrap
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: root.ftsResults
                spacing: 2
                Accessible.name: "Full-text search results"
                Accessible.role: Accessible.List
                delegate: ItemDelegate {
                    width: ListView.view.width
                    height: 52
                    padding: 8
                    Accessible.name: modelData.headword
                    Accessible.role: Accessible.ListItem
                    contentItem: ColumnLayout {
                        spacing: 0
                        Label { text: modelData.headword; font.pixelSize: 16; font.bold: true }
                        Label { text: modelData.dictName; color: root.uiSubFg; font.pixelSize: 11 }
                    }
                    onClicked: {
                        let gid = 0
                        if (ftsGroupCombo.currentIndex >= 0 && engine.groups.length > 0)
                            gid = engine.groups[ftsGroupCombo.currentIndex].id
                        root._requestedWord = modelData.headword
                        engine.lookupInGroupWithSwitch(modelData.headword, gid)
                    }
                }
            }
        }
    }

    // --- group picker dialog ---
    // True while the modal group picker is open: the inline WebView is torn
    // down (its native surface sits above ANY Qt item, so it would cover the
    // dialog). When this flips back to false, the loader re-creates the WebView
    // and the suggestion/history overlay is re-applied via onLoadingChanged.
    property bool _pickerOpen: false
    // Which scope the modal picker was opened for: "search" or "fts". Decides
    // which combo to update on selection and whether the Search WebView needs
    // the teardown/restore dance (only the Search tab has an inline WebView).
    property string _pickerTarget: "search"
    Dialog {
        id: groupPicker
        anchors.centerIn: parent
        // A tall modal, like the dictionary/groups list: most of the screen
        // height, with the group rows filling it and scrolling naturally.
        width: parent.width - 48
        height: parent.height * 0.8
        modal: true
        title: qsTr("Select group")
        Accessible.name: "Select group"
        Accessible.role: Accessible.Dialog
        // No Cancel button — tapping outside (or Back) dismisses.
        closePolicy: Popup.CloseOnPressOutside | Popup.CloseOnEscape
        function openAt(index, target) {
            root._pickerTarget = target !== undefined ? target : "search"
            if (root._pickerTarget === "search") {
                // Tear down the inline WebView so its native surface can't sit
                // above the modal dialog. Its document/history survive in
                // currentHtml; the loader recreates it when _pickerOpen goes
                // back to false. The FTS tab has no WebView, so skip.
                root._pickerOpen = true
                root.inlineWv = null
                input.focus = false
            }
            groupPicker.open()
        }
        onClosed: {
            const wasSearch = root._pickerTarget === "search"
            root._pickerTarget = "search"
            if (!wasSearch) return // FTS: no WebView teardown happened
            root._pickerOpen = false
            // Loader binding re-evaluates to create the WebView (state 0 &&
            // inlineWebReady && !_pickerOpen). If inlineWebReady was toggled off
            // while away, the inlineWebTimer re-arms on the Search state.
            root.inlineWebReady = true
            // Re-populate the candidate surface for whatever is in the box now
            // (suggestions for a typed query, or history when empty). The
            // _suggWords/_suggMode state survives, but re-querying ensures the
            // results are fresh after the WebView destruction + group change.
            if (input.displayText.trim().length > 0) searchPane._doSuggest()
            else root._showHistoryOverlay()
        }
        onOpened: {
            // Scroll to the currently-active group.
            let activeIndex = 0
            if (root._pickerTarget === "fts")
                activeIndex = ftsGroupCombo.currentIndex
            else
                activeIndex = searchGroupCombo.currentIndex
            if (activeIndex >= 0 && activeIndex < engine.groups.length)
                groupPickerList.positionViewAtIndex(activeIndex, ListView.Center)
        }

        contentItem: ColumnLayout {
            spacing: 8

            ListView {
                id: groupPickerList
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: engine.groups
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Accessible.name: "Select group"
                Accessible.role: Accessible.List
                delegate: ItemDelegate {
                    width: groupPickerList.width
                    height: 56
                    text: modelData.name
                    highlighted: groupPickerList.currentIndex === index
                    font.pixelSize: 16
                    Accessible.name: modelData.name
                    Accessible.role: Accessible.ListItem
                    onClicked: {
                        const g = engine.groups[index]
                        if (g) {
                            groupPickerList.currentIndex = index
                            if (root._pickerTarget === "fts") {
                                ftsGroupCombo.currentIndex = index
                                // Re-run the FTS for the new scope if a query is present.
                                if (ftsInput.text.trim().length > 0) root._runFts()
                            } else {
                                searchGroupCombo.currentIndex = index
                                const q = input.displayText.trim()
                                if (q.length > 0) {
                                    // Switching the group actually triggers a lookup
                                    // of the typed query in the new group. This also
                                    // sets the active group and records the entry
                                    // (a fresh search → new history item).
                                    root._requestedWord = q
                                    engine.lookupInGroupWithSwitch(q, g.id)
                                } else {
                                    engine.setActiveGroup(g.id)
                                    root._showHistoryOverlay()
                                }
                            }
                        }
                        groupPicker.close()
                    }
}
            }
        }
    }
}
