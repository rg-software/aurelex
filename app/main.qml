import QtQuick
import QtQml.Models
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

    // Material accent drives highlights. Task 3.1: Material.theme bound at the
    // root so light/dark is driven by the EFFECTIVE theme, not by Qt's own
    // (unreliable on Android 6.6) system detection. EngineController already
    // resolves the user's theme setting against the JNI-sampled system state, so
    // the whole app reads the one resolved value.
    Material.accent: Material.Purple
    Material.theme: engine.darkMode ? Material.Dark : Material.Light

    // The window paints the app background edge to edge. Everything that is not
    // a pane (the inset strips beside a side-mounted camera, the area under a
    // dialog) shows this, so an inset never exposes the window's clear colour as
    // a black band. The panes carry `color: root.uiBg` too, so the seam is
    // invisible in either theme.
    color: root.uiBg

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
    // True from the moment a search is submitted until its results land. Drives
    // the search control's enabled state; cleared in onFtsSearchReady.
    property bool ftsSearching: false
    // The inputs the DISPLAYED results were produced from. Compared against the
    // live inputs to invalidate stale results (control-state-and-fts-whole-words).
    property string ftsAppliedQuery: ""
    property int ftsAppliedGroup: -1
    property bool ftsAppliedWhole: false
    // Whether the clipboard holds usable text. Re-queried whenever the system
    // clipboard changes, so the Search pane's clipboard control enables/disables
    // live. Initialized at startup (engine is constructed before QML).
    property bool clipboardHasText: engine.clipboardHasText()
    property int searchGroupId: 0
    property int ftsGroupId: 0
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

    // Material icon font family (registered in main.cpp from the bundled
    // resource declared by qt_add_resources("fonts") in CMakeLists.txt) + the
    // icon-name -> codepoint helper (qt-material-ui task 7.2).
    property string iconFontFamily: "Material Icons"
    // Secondary icon font: a Material Symbols Outlined subset holding glyphs the
    // classic Material Icons set lacks. The registered family is the subset's
    // name (log: "Material Symbols Outlined"); symbolIcon emits the codepoints.
    property string symbolFontFamily: "Material Symbols Outlined"
    // Android safe-area insets (logical px): the Qt window is edge-to-edge, so
    // our own content must sit inside the area the platform reserves. Each value
    // is the union — the LARGER of — the system-window inset and the display
    // cutout's safe inset for that edge (Android 15 folds the cutout into the
    // status bar on the top edge, so summing would double-count it). Converted
    // from physical px returned by the activity via JNI and recomputed on every
    // window resize rather than captured once.
    //
    // Top/bottom cover the status bar and the navigation bar. The horizontal pair
    // exists for the display cutout: on Android 15 the platform enforces
    // layoutInDisplayCutoutMode=always for our target SDK, so a camera in
    // landscape punches a hole in OUR surface and nothing else reserves space
    // there. Both are 0 on a device with no cutout, so the layout is unchanged.
    property int _insetTop: 0
    property int _insetBottom: 0
    property int _insetLeft: 0
    property int _insetRight: 0
    property real _insetDpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    function _refreshInsets() {
        root._insetDpr = Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
        root._insetTop = Math.round(engine.systemInsetTop() / root._insetDpr)
        root._insetBottom = Math.round(engine.systemInsetBottom() / root._insetDpr)
        root._insetLeft = Math.round(engine.systemInsetLeft() / root._insetDpr)
        root._insetRight = Math.round(engine.systemInsetRight() / root._insetDpr)
    }
    // The resize hooks below are a FAST PATH for the common cases (a real
    // portrait<->landscape flip, the IME, split screen). They are not the
    // authoritative trigger: flipping between the two LANDSCAPE orientations
    // (rotation 1 <-> 3) leaves the window at identical dimensions, so no resize
    // signal fires while the display cutout moves from one side edge to the
    // other — measured, that left the article running back under the camera.
    // EngineController::pollInsets watches the four values themselves and emits
    // insetsChanged on actual movement, which covers every case above plus this
    // one. Both paths are kept: the resize hook makes the common case instant
    // rather than waiting up to one poll interval (~500ms).
    onWidthChanged: root._refreshInsets()
    onHeightChanged: root._refreshInsets()
    Connections {
        target: engine
        function onInsetsChanged() { root._refreshInsets() }
    }
    Component.onCompleted: root._refreshInsets()
    // First-launch tab routing happens on onOnboardedChanged (not here):
    // engine.onboarded is only final after EngineController's ASYNC gd_init +
    // loadSettings() completes, so at Component.onCompleted it is still the
    // default false and the onboarding decision cannot be trusted yet.
    // Routing from the async signal is guarded by _bootRouted so the "Get
    // started" toggle (which also emits onboardedChanged) can never hijack the
    // user away from a tab they already navigated to.
    property bool _bootRouted: false

    Connections {
        target: engine
        function onOnboardedChanged() {
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
            // Add-group control (ui-polish): classic Material Icons glyph.
            "create_new_folder": 0xe2cc,
            "check": 0xe5ca,
            "edit": 0xe150,
            "drag_handle": 0xe25d,
            "translate": 0xe8e2,
            "delete": 0xe872,
            "bookmark": 0xe866,
            // light_mode/dark_mode are present in the classic Material Icons font,
            // so they come from icon() and not from symbolIcon(); only
            // light_mode_auto needs the symbol subset.
            "light_mode": 0xe518,
            "dark_mode": 0xe51c,
            "cloud_download": 0xe2c0,
            "refresh": 0xe5d5,
            "sync": 0xe627,
            "music_note": 0xe405,
            "music_off": 0xe440
        }
        if (map[name] === undefined) {
            // A missing key used to fail silently as U+FFFD tofu in the UI. That
            // is how the theme button lost its sun: icon("light_mode") had no
            // entry, so the control rendered a replacement character. Warn
            // instead — the caller asked for an icon that does not exist.
            console.warn("icon(): no such icon name:", name);
            return "\uFFFD";
        }
        return String.fromCharCode(map[name]);
    }
    // Material Symbols icons (rendered with symbolFontFamily): glyphs that only
    // exist in the Material Symbols Outlined subset (folder_open, match_word,
    // light_mode_auto, text_decrease, text_increase).
    // fromCodePoint, not fromCharCode: light_mode_auto is U+FFF00, outside the
    // BMP, so it needs a surrogate pair in UTF-16. fromCharCode truncates its
    // argument to 16 bits, which would yield U+FF00 — a real glyph present in the
    // subset's cmap — and the icon would render as the wrong character rather than
    // failing visibly.
    function symbolIcon( name ) {
        var map = {
            "folder_open": 0xe2c8,
            "match_word": 0xf6f0,
            "light_mode_auto": 0xfff00,
            "text_decrease": 0xeadd,
            "text_increase": 0xeae2
        }
        return map[name] !== undefined ? String.fromCodePoint(map[name]) : "\uFFFD"
    }
    // Convenient Material palette aliases (replaces the old darkMode ternaries).
    property color uiBg: Material.background
    property color uiCard: Material.dialogColor
    property color uiBorder: Material.dividerColor
    property color uiFg: Material.foreground
    property color uiSubFg: Material.secondaryTextColor
    // The article WebView's canvas: the app's own background color, so no seam
    // shows where the article meets the chrome. These are Qt 6.6's Material
    // backgroundColorLight / backgroundColorDark — the same pair Qt resolves for
    // Material.background (root.uiBg) and colors.xml carries for the starting
    // window. They were #ffffff / #242526, which matched neither theme
    // (pin-article-canvas-against-dark-reader). EngineController carries the same two
    // values for the article CSS it injects — change both together.
    function uiBgHex() {
        return engine.darkMode ? "#1c1b1f" : "#fffbfe"
    }
    // Section stripe for the By-Pair dictionary list. A full-width tinted band
    // that reads as a separator between pairs in both themes (the pair headers
    // were previously a pale, half-width rect and were nearly invisible).
    property color uiSectionBg: engine.darkMode
        ? Material.color(Material.Purple, Material.Shade900)
        : Material.color(Material.Purple, Material.Shade100)
    property color uiSectionFg: engine.darkMode
        ? Material.color(Material.Purple, Material.Shade100)
        : Material.color(Material.Purple, Material.Shade900)

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

    // The name shown for a dictionary: a catalog entry's name in the app's
    // active language when the dictionary came from the catalog, else the
    // dictionary's own name (#NAME). See localized-catalog-names.
    function dictDisplayName(d) {
        const src = d.source ? d.source.split("/").pop() : ""
        const entries = engine.catalogEntries
        for (let i = 0; i < entries.length; ++i) {
            const e = entries[i]
            const files = e.files || []
            for (let j = 0; j < files.length; ++j) {
                if (files[j].role === "dictionary" && files[j].name === src)
                    return e.displayName || e.name
            }
        }
        return d.name
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
    // --- in-article find (see openspec change in-article-find) ---
    // QML owns the find bar state; the injected article-find.js owns the DOM
    // highlights. findIndex is 1-based (0 when there are no matches).
    property bool articleFindMode: false
    property string findQuery: ""
    property int findIndex: 0
    property int findTotal: 0
    Timer {
        id: inlineWebTimer
        interval: 420
        repeat: false
        running: root.state === 0
        onTriggered: {
            root.inlineWebReady = true
        }
    }
    onStateChanged: {
        if (root.state !== 0) {
            // Leaving the Search tab: mark that a return should restore the
            // field's focus and re-trigger suggestions (the inline WebView and
            // its suggestion overlay are destroyed on leaving). An inline
            // article is PRESERVED (currentHtml); returning re-renders it.
            root._returningToSearch = true
            root.inlineWebReady = false
            inlineWebTimer.stop()
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
            //
            // Focus is granted on the next turn, once the pane is actually
            // visible: the field's frame repaints on focus and on text, while
            // its floating label settles on its own schedule, so granting focus
            // mid-switch can leave the frame redrawn through the label.
            Qt.callLater(function() {
                if (root.state !== 0) return
                input.forceActiveFocus()
                if (input.displayText.trim().length > 0) searchPane._doSuggest()
            })
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
        root._resetFind()
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
        root._resetFind()
        root._hideSuggestOverlay()
        root._blankInline()
    }
    // The article surface is a NATIVE view painted over the QML panes, so a bare
    // document shows the WebView's own white canvas behind it — a white flash or
    // pane in dark mode. Painting it the app background fixes that; the value is
    // re-stated on <html> by _applyArticleDarkMode on a live theme flip.
    function uiBlankHtml() {
        return "<html style=\"background:" + root.uiBgHex()
            + "\"><body></body></html>"
    }
    function _blankInline() {
        if (root.inlineWv && engine.articleBaseUrl.length > 0) {
            // A suggestion injected before this blank load finishes gets wiped;
            // flag it so _renderSuggestOverlay defers (see _blankPending).
            root._blankPending = true
            root.inlineWv.loadHtml(root.uiBlankHtml(), engine.articleBaseUrl)
        }
    }

    // --- in-article find (openspec change in-article-find) ---
    // QML owns the bar; the injected article-find.js owns the highlights. All
    // controller calls return a "total|index" string (index 1-based, 0 = none).
    function _openFind() {
        if (!root.inlineArticle) return
        root.articleFindMode = true
        findInput.forceActiveFocus()
    }
    function _closeFind() {
        if (root.inlineWv && root.inlineWv.url.toString().length > 5)
            root.inlineWv.runJavaScript(
                "try{if(window.gdFindClear)gdFindClear();}catch(e){}")
        findInput.focus = false
        root._resetFind()
    }
    // Clear the bar and its state. Called when a new article is shown or the
    // article surface is concealed — a new article must not inherit a query.
    function _resetFind() {
        root.articleFindMode = false
        root.findQuery = ""
        root.findIndex = 0
        root.findTotal = 0
        if (findInput.text.length > 0) findInput.text = ""
    }
    // Wrap a controller call so a missing/old document yields "0|0" rather than
    // an undefined result. runJavaScript returns the last expression's value.
    function _findCall(expr) {
        return "(function(){try{return window." + expr + "}catch(e){return '0|0'}})()"
    }
    function _applyFind() {
        const wv = root.inlineWv
        if (!wv || !root.inlineArticle || wv.url.toString().length < 6) return
        wv.runJavaScript(
            root._findCall("gdFindSet(" + JSON.stringify(root.findQuery) + ")"),
            root._setFindResult)
    }
    function _findNext() {
        const wv = root.inlineWv
        if (!wv || !root.findQuery || wv.url.toString().length < 6) return
        wv.runJavaScript(root._findCall("gdFindNext()"), root._setFindResult)
    }
    function _findPrev() {
        const wv = root.inlineWv
        if (!wv || !root.findQuery || wv.url.toString().length < 6) return
        wv.runJavaScript(root._findCall("gdFindPrev()"), root._setFindResult)
    }
    function _setFindResult(v) {
        const parts = String(v === undefined || v === null ? "0|0" : v).split("|")
        root.findTotal = parseInt(parts[0], 10) || 0
        root.findIndex = parseInt(parts[1], 10) || 0
    }
    // Re-apply an open find after the document is (re)loaded — rotation, or the
    // WebView being recreated on returning to the tab — restoring the match.
    function _reapplyFind() {
        if (!root.articleFindMode || root.findQuery.length === 0) return
        const wv = root.inlineWv
        if (!wv || !root.inlineArticle || wv.url.toString().length < 6) return
        const want = root.findIndex > 0 ? root.findIndex - 1 : 0
        wv.runJavaScript(
            root._findCall("gdFindSet(" + JSON.stringify(root.findQuery) + "," + want + ")"),
            root._setFindResult)
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
    // True while the query currently in the box is owned by an article rather
    // than by the candidate dropdown: a lookup for that query is in flight
    // (_requestedWord), or the article for it is already rendered. In either
    // state a late suggestion reply must NOT repaint over the article (the
    // group-switch / Enter dropdown-over-article bug).
    function _articleOwnsSurface() {
        const q = input.displayText.trim()
        if (q.length === 0) return false
        if (root._requestedWord.length > 0 && root._requestedWord === q) return true
        return root.inlineArticle && root.currentWord === q
    }
    function _applySuggestOverlay() {
        const wv = root.inlineWv
        // Need a live WebView that actually has a loaded document (URL present).
        // runJavaScript on a doc-less WebView silently does nothing.
        if (!wv || root._blankPending) return
        // The submitted query owns the surface: never paint candidates over it.
        if (root._articleOwnsSurface()) {
            root._clearOverlayDom()
            root._suggVisible = false
            return
        }
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
        // The overlay is painted on the WebView's canvas, so its background is
        // the app background too — same value the article itself uses, so the
        // candidate pane never reads as a lighter panel inside the Search pane.
        const bg = root.uiBgHex()
        const fg = dark ? "#e0e0e0" : "#202124"
        const sep = dark ? "#3a3b3c" : "#eeeeee"
        const accent = dark ? "#b388ff" : "#6200ee"
        // History (recent lookups) fills the whole inline article pane; the
        // suggestions dropdown stays bounded so the article behind it shows.
        const fillPane = root._suggMode === "history"
        var html = '<div id="gd-sugg" style="position:fixed;top:0;left:0;right:0;'
            + 'z-index:9999;background:' + bg + ';color:' + fg + ';'
            + 'box-shadow:0 2px 10px rgba(0,0,0,0.4);overflow-y:auto;'
            + (fillPane ? 'bottom:0;' : 'max-height:72%;')
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
                    const hgName = root._escHtml(root._groupLabel(hg))
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
        // Only the panel itself is painted here. The DOCUMENT's background is
        // deliberately not touched: the blank base document paints it inline on
        // <html> (uiBlankHtml, restated on a theme flip by
        // _applyArticleDarkMode) and the article paints it from its injected
        // CSS (rewriteArticleUrls). Writing it inline here instead froze the
        // color at the value it had when the overlay was drawn, which left the
        // pane on the previous theme's background after a flip — and unlike the
        // overlay it was never removed again (pin-article-canvas-against-dark-reader).
        const script = '(function(){'
            + 'var e=document.getElementById("gd-sugg");if(e)e.remove();'
            + 'if(document.body)document.body.style.margin="0";'
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
            root.inlineWv.loadHtml(root.uiBlankHtml(), engine.articleBaseUrl)
        }
    }
    function _showArticle(word, html) {
        // A picked word replaces the candidate list — collapse the dropdown.
        root._hideSuggestOverlay()
        // A newly opened article must not inherit the previous find query.
        root._resetFind()
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
        root._resetFind()
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
        root._resetFind()
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
            root.searchGroupId = groupId
        } else {
            engine.setActiveGroup(0)
            root.searchGroupId = 0
        }
    }
    function _groupIndexForId(groupId) {
        for (var i = 0; i < engine.groups.length; ++i) {
            if (engine.groups[i].id === groupId) return i
        }
        return 0
    }
    // Display name of the built-in group, in the active language. The engine
    // boundary returns this group as a hardcoded C literal ("All") because the
    // carve loads no translation catalog, so the app names it from its own
    // catalog instead of passing the engine's string through. This is the only
    // qsTr("All") call site; _groupLabel is the only reader.
    readonly property string _allGroupLabel: qsTr("All")
    // The single source of a group's display label, keyed by its stable id (D1).
    // Every surface that names a group goes through here, so one group reads the
    // same everywhere. A user group keeps the name the user typed (never
    // translated); an id with no matching group is labelled as the built-in
    // group, which is where a tap on such a row actually looks up.
    function _groupLabel(groupId) {
        if (groupId === 0) return root._allGroupLabel
        for (var i = 0; i < engine.groups.length; ++i) {
            if (engine.groups[i].id === groupId) return engine.groups[i].name
        }
        return root._allGroupLabel
    }
    // Language pair ("English/Russian", unknown side '?') for a dictionary's
    // engine index. The membership list's rows (from groupDicts) carry the engine
    // index but not the language pair, so read it from the dictionary list.
    function _pairForDictIndex(idx) {
        const d = engine.dictionaries
        for (var i = 0; i < d.length; ++i) {
            if (d[i].engineIndex === idx) return root.fmtPair(d[i])
        }
        return "?"
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
        if (findInput.activeFocus) findInput.focus = false
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
        // Also clear any busy flag left by a submit whose reply was dropped for
        // a stale query, so the control cannot stay disabled across a re-entry.
        root.ftsSearching = false
        state = 4
    }
    function _openFavorites() {
        _blurActive()
        state = 6
    }
    // Submit a full-text search. This is the ONLY path that runs a search
    // (control-state-and-fts-whole-words): typing, a scope change, and the
    // whole-words toggle change what a later search does, not whether one runs.
    // The mode is chosen here from the toggle — whole words -> FTS::
    // WholeWords (0, exact terms), off -> Wildcards (2, prefix terms). The scope
    // is the group selected in the FTS tab's group button (All by default).
    function _runFts() {
        // displayText: during IME composition `text` lags what the user sees.
        const q = ftsInput.displayText.trim()
        if (q.length === 0) return
        const gid = engine.groupExists(root.ftsGroupId) ? root.ftsGroupId : 0
        // Record the inputs this submit is for: displayed results belong to
        // them, so an input change invalidates the list (see _invalidateFtsResults).
        root.ftsAppliedQuery = ftsInput.displayText
        root.ftsAppliedGroup = gid
        root.ftsAppliedWhole = root.ftsWholeWordsOn
        root.ftsSearching = true
        engine.ftsSearch(ftsInput.displayText, root.ftsWholeWordsOn ? 0 : 2, gid)
    }
    // Clear the result list when an input differs from the one the shown results
    // were produced from, so the list never disagrees with the visible inputs.
    // Called from every non-submit input change (query edit, scope change,
    // whole-words toggle). Leaving/re-entering the pane does not call it, so a
    // round trip keeps the results.
    function _invalidateFtsResults() {
        const gid = engine.groupExists(root.ftsGroupId) ? root.ftsGroupId : 0
        if (ftsInput.displayText === root.ftsAppliedQuery
            && gid === root.ftsAppliedGroup
            && root.ftsWholeWordsOn === root.ftsAppliedWhole)
            return
        if (root.ftsResults.length > 0) root.ftsResults = []
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
            // Results have landed: the busy window for this submit is over, so
            // re-enable the search control even if this reply turns out to be
            // stale (otherwise a dropped reply would strand the button disabled).
            root.ftsSearching = false
            if (query !== ftsInput.displayText) return
            ftsResults = results
        }
        // Keep the Search pane's clipboard control in sync with the clipboard.
        function onClipboardChanged() {
            root.clipboardHasText = engine.clipboardHasText()
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
            // The dock itself keeps its full-bleed background (it is what
            // visually terminates the bottom of the screen), but its cells are
            // interactive, so the row takes the side insets — in landscape the
            // outermost tab must move clear of the camera.
            anchors { left: parent.left; leftMargin: root._insetLeft
                      right: parent.right; rightMargin: root._insetRight; top: parent.top }
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
                Accessible.role: Accessible.PageTabList
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
                        Accessible.role: Accessible.PageTab
                        onClicked: root._navTo(modelData.idx)
                    }
                }
            }

            // Theme toggle: the 6th cell, a SIBLING of the TabBar so it can
            // never become the selected tab. Cycles Light -> Dark -> follow the
            // system; does not navigate.
            Button {
                id: themeBtn
                width: navRow.width - navBar.width
                height: navRow.height
                flat: true
                // The icon and the accessible name both show what the NEXT tap
                // selects, not the current theme: the moon means "tap to go dark",
                // the sun "tap to go light", the auto glyph "tap to hand control
                // back to the system". Current-state icons could not express the
                // third mode — pinned-light and follow-system-under-a-light-system
                // would draw the same sun.
                readonly property int _nextMode: engine.themeMode === 1 ? 2
                                                : engine.themeMode === 2 ? -1
                                                                      : 1
                readonly property bool _nextIsAuto: _nextMode === -1
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
                        text: themeBtn._nextIsAuto
                              ? root.symbolIcon("light_mode_auto")
                              : root.icon(themeBtn._nextMode === 2 ? "dark_mode" : "light_mode")
                        font.family: themeBtn._nextIsAuto ? root.symbolFontFamily : root.iconFontFamily
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
                // Invariant English (house rule): these are the documented
                // UIAutomator test IDs, so they are never wrapped in qsTr.
                Accessible.name: themeBtn._nextIsAuto ? "Follow system theme"
                            : themeBtn._nextMode === 2 ? "Dark mode"
                                                        : "Light mode"
                Accessible.role: Accessible.Button
                onClicked: {
                    engine.toggleThemeMode()
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
        // Every top-level pane shares this anchor line, so the side insets that keep
        // content clear of a display cutout are applied in one place. A new pane
        // must copy this line verbatim, margins included, or it will run under a
        // side-mounted camera.
        anchors { top: topBar.bottom; left: parent.left; leftMargin: root._insetLeft
                  right: parent.right; rightMargin: root._insetRight; bottom: navDock.top }
        color: root.uiBg
        visible: root.state === 0

        // Keyboard submit (IME action). Opens the top suggestion when there is
        // one, otherwise looks up the literal typed text. Either way the article
        // owns the surface: `_requestedWord` + the shown-article check in
        // `_articleOwnsSurface()` keep a late suggestion reply from repainting
        // over it.
        function _submitSearch() {
            input.focus = false
            const typed = input.displayText.trim()
            if (typed.length === 0) return
            let word = typed
            if (root._suggMode === "sugg" && root._suggWords.length > 0) {
                const first = root._suggWords[0]
                if (typeof first === "string" && first.indexOf("(no results") !== 0)
                    word = first
            }
            root._requestedWord = word
            engine.lookup(word)
        }

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
                // A submitted query owns the surface: drop this reply instead of
                // painting suggestions over the article that is loading or has
                // already been rendered for that query.
                if (root._articleOwnsSurface()) return
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
                // Stale replies are dropped like onArticleLoaded's: only the word
                // we are actually waiting for releases the surface guard.
                if (root._requestedWord.length > 0 && word.trim() !== root._requestedWord) return
                root._requestedWord = ""
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
            // the row, the group button ~30%; the clipboard is a small icon
            // button. The group button is always tappable: it shows the current
            // scope in the app's magenta accent scheme and opens the picker.
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
                    // No font.pixelSize override: enlarging it makes the
                    // placeholder's largestHeight exceed what Material's
                    // MaterialTextContainer budgets for, so the floating label is
                    // positioned at the unfloated y and lands ON the box border
                    // (reproduced on desktop Qt 6.6.3 and two Android devices).
                    // Material's default size keeps the label where the style
                    // expects it. Root cause and fix in the archived
                    // 2026-10-01-control-state-and-fts-whole-words change.
                    onDisplayTextChanged: searchPane._doSuggest()
                    onAccepted: searchPane._submitSearch()
                    Component.onCompleted: {
                        // Focus the field + show the keyboard only AFTER
                        // onboarding — on first run the keyboard must not pop
                        // up behind the welcome overlay.
                        if (engine.onboarded) forceActiveFocus()
                    }
                }

                Button {
                    id: searchGroupButton
                    Layout.fillWidth: true
                    Layout.preferredWidth: 3.9
                    Layout.minimumWidth: 0
                    // Permanently `highlighted` so the Material style paints the
                    // app's standard accent fill (magenta) with white label text,
                    // like the FTS "Search" button and the "By Pair" toggle.
                    highlighted: true
                    padding: 4
                    font.pixelSize: 14
                    // Never take keyboard focus: tapping this would move active
                    // focus off the search field and desync its frame from its
                    // floating label (see the clipboard button).
                    focusPolicy: Qt.NoFocus
                    text: {
                        if (engine.groups.length === 0) return ""
                        const i = root._groupIndexForId(root.searchGroupId)
                        const matches = i >= 0 && i < engine.groups.length
                            && engine.groups[i].id === root.searchGroupId
                        return root._groupLabel(matches ? root.searchGroupId : 0)
                    }
                    Accessible.name: "Search group scope"
                    Accessible.role: Accessible.Button
                    onClicked: {
                        input.focus = false
                        groupPicker.openAt(root._groupIndexForId(root.searchGroupId))
                    }
                }

                Button {
                    id: clipboardBtn
                    text: root.icon("content_paste_search")
                    font.family: root.iconFontFamily
                    font.pixelSize: 18
                    // Primary action: accent styling so it never reads as the
                    // disabled grey. Enabled only while the clipboard holds
                    // usable text (control-state-and-fts-whole-words).
                    highlighted: true
                    enabled: root.clipboardHasText
                    // Never take keyboard focus. Qt would otherwise move active
                    // focus off the search field on press, repainting the field's
                    // frame from magenta to grey while the floating label keeps its
                    // old position — and restoring focus repaints only the frame,
                    // leaving it drawn through the label. A tap does not need focus.
                    focusPolicy: Qt.NoFocus
                    Accessible.name: "Clipboard"
                    Accessible.role: Accessible.Button
                    // Paste clipboard text into the search field (so the looked-up
                    // word is visible in the box) and run the lookup.
                    onClicked: {
                        const t = engine.clipboardText()
                        if (t.length > 0) {
                            // Ensure the field is the focused control before the
                            // text changes, so the frame and the label both settle
                            // from the focused state.
                            input.forceActiveFocus()
                            // Assign with suggestion queries suppressed (the
                            // assignment fires onDisplayTextChanged, and an
                            // unsuppressed suggest would race the lookup below).
                            root._suppressSuggest = true
                            input.text = t
                            root._suppressSuggest = false
                            root._requestedWord = t
                            engine.lookup(t)
                        }
                    }
                }
            }



            Label {
                Layout.fillWidth: true
                // Trimmed check: a whitespace-only message must not paint an
                // empty "engine error:" line.
                visible: engine.lastError.trim().length > 0
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
                // A floor for the article surface, but a SMALL one on purpose. This
                // is the last item in a ColumnLayout that cannot shrink the search
                // row, so a floor larger than the window's leftover height makes the
                // whole column overflow its pane — and the overflow spills DOWNWARD
                // over the bottom dock. That is exactly why the dock used to vanish
                // in landscape: on a 387px-tall landscape window the pane is 268, the
                // search row takes 64, and the old floor of 300 pushed this item to
                // y=364 while the dock starts at y=307. The native WebView inside
                // paints over the dock (a native view ignores QML z and clip), so the
                // whole bottom bar disappeared on the Search tab only.
                //
                // 88 keeps a usable band (toolbar 40 + 6 margin leaves 42 of article)
                // and never inverts the toolbar anchors below it, while still fitting
                // a landscape phone with room to spare. Do not raise it without
                // re-measuring the landscape layout.
                // (fix-article-surface-covers-dock)
                Layout.minimumHeight: 88
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
                        // Find mode swaps this row for the find bar (below).
                        visible: !root.articleFindMode

                        // Find toggle, leftmost so it has room; opens the find bar
                        // in place of the navigation controls.
                        ToolButton {
                            text: root.icon("search")
                            font.family: root.iconFontFamily
                            font.pixelSize: 20
                            Accessible.name: "Search in article"
                            Accessible.role: Accessible.Button
                            onClicked: root._openFind()
                        }

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
                        // Icons are the Material Symbols text_decrease/text_increase
                        // glyphs (from the secondary subset font), which read as
                        // "smaller/larger text" rather than a generic magnifier.
                        ToolButton {
                            text: root.symbolIcon("text_decrease")
                            font.family: root.symbolFontFamily
                            font.pixelSize: 20
                            enabled: engine.articleZoom > engine.articleZoomMin
                            Accessible.name: "Zoom out"
                            Accessible.role: Accessible.Button
                            onClicked: engine.setArticleZoom(engine.articleZoom - engine.articleZoomStep)
                        }
                        ToolButton {
                            text: root.symbolIcon("text_increase")
                            font.family: root.symbolFontFamily
                            font.pixelSize: 20
                            enabled: engine.articleZoom < engine.articleZoomMax
                            Accessible.name: "Zoom in"
                            Accessible.role: Accessible.Button
                            onClicked: engine.setArticleZoom(engine.articleZoom + engine.articleZoomStep)
                        }
                    }

                    // Find bar: drawn in place of the navigation row, same 40px
                    // height (so opening/closing find never resizes the WebView).
                    RowLayout {
                        id: findBar
                        anchors.fill: parent
                        anchors.leftMargin: 4
                        anchors.rightMargin: 4
                        spacing: 4
                        visible: root.articleFindMode

                        // The magnifier turns into the close affordance.
                        ToolButton {
                            text: root.icon("close")
                            font.family: root.iconFontFamily
                            font.pixelSize: 20
                            Accessible.name: "Close find"
                            Accessible.role: Accessible.Button
                            onClicked: root._closeFind()
                        }

                        // Compact field: no floating label, so it fits the row.
                        TextField {
                            id: findInput
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            placeholderText: qsTr("Find in article")
                            Accessible.name: "Find in article"
                            Accessible.role: Accessible.EditableText
                            font.pixelSize: 14
                            selectByMouse: true
                            topPadding: 0
                            bottomPadding: 0
                            background: Rectangle {
                                color: "transparent"
                                border.color: root.uiBorder
                                border.width: 1
                                radius: 4
                            }
                            onDisplayTextChanged: {
                                root.findQuery = findInput.displayText
                                findDebounce.restart()
                            }
                            // Enter advances to the next match.
                            onAccepted: root._findNext()
                        }

                        Label {
                            id: findCounter
                            text: root.findTotal > 0
                                  ? (root.findIndex + " / " + root.findTotal)
                                  : (root.findQuery.length > 0 ? qsTr("No matches") : "")
                            color: root.uiSubFg
                            font.pixelSize: 13
                            Layout.alignment: Qt.AlignVCenter
                        }

                        ToolButton {
                            text: root.icon("arrow_back")
                            font.family: root.iconFontFamily
                            font.pixelSize: 20
                            enabled: root.findTotal > 0
                            Accessible.name: "Previous match"
                            Accessible.role: Accessible.Button
                            onClicked: root._findPrev()
                        }
                        ToolButton {
                            text: root.icon("arrow_forward")
                            font.family: root.iconFontFamily
                            font.pixelSize: 20
                            enabled: root.findTotal > 0
                            Accessible.name: "Next match"
                            Accessible.role: Accessible.Button
                            onClicked: root._findNext()
                        }
                    }
                }

                Loader {
                    id: searchArticleLoader
                    anchors { top: parent.top; topMargin: inlineArticleToolbar.height + 6; left: parent.left; right: parent.right; bottom: parent.bottom }
                    // Defer WebView creation until the scene is measured.
                    // On Android, a WebView created before layout runs locks its
                    // native surface to a wrong (full-window) size that then
                    // overtakes the whole screen. inlineWebReady is set by a
                    // short timer once the Search tab is actually visible.
                    active: root.state === 0 && root.inlineWebReady && !root._pickerOpen
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
                            Accessible.role: Accessible.WebDocument
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
                                    searchArticleView.loadHtml(root.uiBlankHtml(), engine.articleBaseUrl)
                                    return
                                }
                                if (u.indexOf("gdlookup://") === 0) {
                                    const word = _parseGdlookupUrl(u)
                                    if (word.length > 0) {
                                        _gdlookupInFlight = word
                                        root._requestedWord = word
                                        engine.lookup(word)
                                    }
                                    searchArticleView.loadHtml(root.uiBlankHtml(), engine.articleBaseUrl)
                                    return
                                }
                                if (base.length > 0 && u.indexOf(base + "/gdau/") === 0) {
                                    engine.playAudio(u)
                                    searchArticleView.loadHtml(root.uiBlankHtml(), engine.articleBaseUrl)
                                    return
                                }
                            }
                            onLoadingChanged: {
                                if (!loading) {
                                    // Blank base document settled: safe to inject
                                    // any suggestions that arrived meanwhile.
                                    root._blankPending = false
                                    root._flushPendingSugg()
                                    // A genuine reload with find open re-applies the
                                    // query and restores the current match.
                                    root._reapplyFind()
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
        // Every top-level pane shares this anchor line, so the side insets that keep
        // content clear of a display cutout are applied in one place. A new pane
        // must copy this line verbatim, margins included, or it will run under a
        // side-mounted camera.
        anchors { top: topBar.bottom; left: parent.left; leftMargin: root._insetLeft
                  right: parent.right; rightMargin: root._insetRight; bottom: navDock.top }
        color: root.uiBg
        visible: root.state === 1

        Component.onCompleted: engine.refreshDictionaries()
        property bool byPair: false
        // Indices of selected dictionary rows (for Delete selection).
        property var selectedDicts: []
        // ---------- remote catalog pane ----------
        property bool catalogOpen: false
        // Entry ids ticked for the next batch, and the subset whose audio the
        // user turned OFF. Audio is opted OUT: selecting an entry selects its
        // bundle too, and the music toggle only ever removes it.
        property var catalogSelected: []
        property var catalogAudioOff: []
        function _openCatalog() {
            dictsPane.catalogSelected = []
            dictsPane.catalogAudioOff = []
            dictsPane.catalogOpen = true
            // Re-probe on every open so the pane shows the latest catalog; the
            // cached copy still renders immediately while the fetch is in flight.
            engine.refreshCatalog()
        }
        function _catalogIsSelected(id) {
            return dictsPane.catalogSelected.indexOf(id) >= 0
        }
        // Name tap: installed entries are not selectable (only their audio
        // toggle is); selecting clears any audio opt-out, deselecting forgets it.
        function _toggleCatalogSelect(id) {
            const e = dictsPane._catalogEntry(id)
            if (!e || e.installed || !e.installable) return
            const sel = dictsPane.catalogSelected
            const i = sel.indexOf(id)
            if (i >= 0) sel.splice(i, 1)
            else sel.push(id)
            dictsPane.catalogSelected = sel
            dictsPane.catalogAudioOff = dictsPane.catalogAudioOff.filter(function(x){ return x !== id })
        }
        // Music tap. Installed entry: add the missing bundle now. Selected
        // entry: toggle the opt-out. Otherwise nothing (select the row first).
        function _toggleCatalogAudio(id) {
            const e = dictsPane._catalogEntry(id)
            if (!e || !e.hasOptional || e.resourcesPresent) return
            if (e.installed) {
                dictsPane._startRequests([{ id: e.id, audio: true }])
                return
            }
            if (!dictsPane._catalogIsSelected(id)) return
            const off = dictsPane.catalogAudioOff
            const i = off.indexOf(id)
            if (i >= 0) off.splice(i, 1)
            else off.push(id)
            dictsPane.catalogAudioOff = off
        }
        function _catalogEntry(id) {
            const all = engine.catalogEntries
            for (let i = 0; i < all.length; i++)
                if (all[i].id === id) return all[i]
            return null
        }
        // Requests for the selected entries. `audio` is on unless the user
        // opted that entry out, so a fresh install carries required (+ optional)
        // and an installed entry carries just its missing bundle.
        function _pickedRequests() {
            const reqs = []
            for (let i = 0; i < dictsPane.catalogSelected.length; i++) {
                const e = dictsPane._catalogEntry(dictsPane.catalogSelected[i])
                if (!e || !e.installable) continue
                const audio = e.hasOptional
                    && dictsPane.catalogAudioOff.indexOf(e.id) < 0
                // An installed entry whose bundle is present (or declined) has
                // nothing to fetch; skip it rather than reporting a space error.
                if (e.installed && (!audio || e.resourcesPresent)) continue
                reqs.push({ id: e.id, audio: audio })
            }
            return reqs
        }
        // Runs the free-space gate, then either starts the batch or asks.
        // `ok` is "above the hard minimum", `warn` is "below the 2 GiB comfort
        // tier"; so refuse is checked FIRST, then the warning, and only a batch
        // with comfortable headroom starts silently.
        function _startRequests(reqs) {
            if (reqs.length === 0) return
            const pf = engine.downloadPreflight(reqs)
            // Nothing resolvable: nothing to fetch, so no dialog at all.
            if (pf.nothing) return
            if (!pf.ok) {
                dictsPane._confirmFree(qsTr("Not enough free space"),
                    qsTr("%1 is needed but only %2 is free. Free up space and try again.")
                        .arg(root.fmtSize(pf.needBytes)).arg(root.fmtSize(pf.freeBytes)),
                    reqs, false)
            } else if (pf.warn) {
                // Enough to proceed, but tight: the service re-checks
                // authoritatively, so a batch that turns out short fails there
                // with a real reason rather than silently truncating.
                dictsPane._confirmFree(qsTr("Not much free space"),
                    qsTr("About %1 is needed but only %2 is free. Downloading may fail if the app also needs room for the index.")
                        .arg(root.fmtSize(pf.needBytes)).arg(root.fmtSize(pf.freeBytes)),
                    reqs, true)
            } else {
                engine.startCatalogDownload(reqs)
            }
        }
        function _startPicked() {
            dictsPane._startRequests(dictsPane._pickedRequests())
        }
        function _confirmFree(title, body, reqs, proceedAnyway) {
            freeSpaceDialog.titleText = title
            freeSpaceDialog.bodyText = body
            freeSpaceDialog.proceedAnyway = proceedAnyway
            freeSpaceDialog.requests = reqs
            freeSpaceDialog.open()
        }
        // A landed batch is deselected once the rescan marks it installed, so
        // the next batch starts clean without the user unticking anything.
        function _pruneSelection() {
            const keep = dictsPane.catalogSelected.filter(function(id){
                const e = dictsPane._catalogEntry(id)
                return e && !e.installed
            })
            if (keep.length !== dictsPane.catalogSelected.length)
                dictsPane.catalogSelected = keep
        }
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
            // Hand the whole selection to the controller in one call: it maps
            // the display positions to engine indices and removes them in one
            // ordered batch, so multi-selection cannot desync. Clear the
            // selection now; the list refreshes when the batch completes.
            const sel = dictsPane.selectedDicts.slice()
            dictsPane.selectedDicts = []
            engine.removeDictionaries(sel)
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
            // Visibility is driven by the single continuous processingActive
            // flag (raised for the whole staging -> scan -> index chain) rather
            // than OR-ing the per-phase flags, which could paint a phase-boundary
            // frame with none of them set and blink the banner off.
            Rectangle {
                Layout.fillWidth: true
                visible: engine.processingActive
                color: Material.color(Material.Purple, Material.Shade50)
                radius: 4
                // Height from the column's implicitHeight; the column's WIDTH is
                // bound explicitly (not anchors.fill) so its wrapped-label height
                // is computed against a known width and does not feed back into
                // the height (a fill/height circular binding undercounted the
                // wrapped header and let the row below overlap the banner).
                implicitHeight: processingCol.implicitHeight + 20
                height: implicitHeight
                // Guarantee a clear seam above the Add/Remove row even if the
                // banner's computed height is momentarily short.
                Layout.bottomMargin: 8

                ColumnLayout {
                    id: processingCol
                    x: 10
                    y: 10
                    width: parent.width - 20
                    spacing: 6

                    // Header carries the currently-indexing dictionary (1-based).
                    Label {
                        Layout.fillWidth: true
                        text: root._stagingActive ? qsTr("Preparing dictionaries…")
                            : engine.scanningActive ? qsTr("Scanning dictionaries…")
                            : engine.buildingFts ? qsTr("Indexing (%1 of %2): %3")
                              .arg(engine.ftsIndexDone + 1)
                              .arg(engine.ftsIndexTotal)
                              .arg(engine.ftsCurrentDictName)
                            : qsTr("Preparing full-text index…")
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
                          : engine.scanningActive
                            ? qsTr("Reading dictionary files…")
                            : qsTr("Checking which dictionaries need indexing…")
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
                Button {
                    text: root.symbolIcon("folder_open")
                    font.family: root.symbolFontFamily
                    font.pixelSize: 18
                    highlighted: true
                    Accessible.name: "Add"
                    Accessible.role: Accessible.Button
                    onClicked: engine.addDictionaryFolder()
                }
                // Remote catalog: the curated download list. Sits next to Add
                // because it is the other way a dictionary gets here, and is
                // disabled while the app is processing so a batch cannot be
                // queued behind an in-flight scan/index. NOT disabled when the
                // catalog is unreachable: opening the pane is how the user sees
                // the reason and retries, and a previously-read catalog still
                // renders read-only there.
                Button {
                    text: root.icon("cloud_download")
                    font.family: root.iconFontFamily
                    font.pixelSize: 18
                    // A primary action, not a toggle: keep it in the accent so it
                    // never reads as a disabled grey button.
                    highlighted: true
                    enabled: !engine.processingActive
                    Accessible.name: "Add from remote"
                    Accessible.role: Accessible.Button
                    onClicked: dictsPane._openCatalog()
                }
                // Delete selection: sits right next to Add, styled like the
                // By Pair toggle — gray while nothing is selected, magenta
                // (highlighted) once a selection exists. Enabled during staging/
                // scanning/indexing too (fts-indexing-performance): the build now
                // interleaves with other engine calls, and a removal cancels any
                // in-flight build for its dictionary, so it no longer queues for
                // minutes.
                Button {
                    text: root.icon("delete")
                    font.family: root.iconFontFamily
                    font.pixelSize: 18
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
                text: qsTr("Tap Add to import a folder containing dictionary files (.mdx, .dsl, .dsl.dz, .ifo), or the cloud button to pick from the remote catalog. Either way the files are copied into the app once; no system-wide storage access is needed.")
            }

            // Import results (report-import-results). Purely informational: by
            // the time it is shown, every unloadable source has already been
            // deleted by the scan, so nothing here acts on files. One dismiss for
            // the whole banner; starting a new import clears it (EngineController).
            // The height is bounded and the rows scroll, so a large result count
            // can never push the dictionary list out of view.
            Rectangle {
                id: importResults
                Layout.fillWidth: true
                Layout.fillHeight: false
                readonly property int maxHeight: Math.round(dictsPane.height * 0.4)
                implicitHeight: Math.min(importResultsCol.implicitHeight + 12, maxHeight)
                visible: engine.scanFailures.length > 0
                color: Material.color(Material.Red, Material.Shade50)
                radius: 4

                ColumnLayout {
                    id: importResultsCol
                    anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 6 }
                    anchors.leftMargin: 10; anchors.rightMargin: 10
                    spacing: 2

                    RowLayout {
                        id: importResultsHeader
                        Layout.fillWidth: true
                        spacing: 4
                        Label {
                            Layout.fillWidth: true
                            // Placeholder-substituted count: the headline stays a
                            // translated template, never concatenated (localization
                            // "Parameterized messages").
                            text: qsTr("%1 import result(s)").arg(engine.scanFailures.length)
                            font.pixelSize: 12
                            font.bold: true
                            color: Material.color(Material.Red)
                            wrapMode: Text.Wrap
                        }
                        // The banner's only control: dismiss the report. It is not
                        // a delete - the failed sources are already gone.
                        Item {
                            implicitWidth: 28
                            implicitHeight: 28
                            Layout.preferredWidth: 28
                            Layout.preferredHeight: 28
                            Layout.fillHeight: false
                            Layout.alignment: Qt.AlignVCenter
                            Text {
                                anchors.centerIn: parent
                                text: root.icon("close")
                                font.family: root.iconFontFamily
                                font.pixelSize: 15
                                color: root.uiSubFg
                            }
                            MouseArea {
                                anchors.fill: parent
                                // Invariant English test ID (AGENTS.md); it says
                                // dismiss, never remove.
                                Accessible.name: "Dismiss import results"
                                Accessible.role: Accessible.Button
                                onClicked: engine.dismissScanFailures()
                            }
                        }
                    }
                    ListView {
                        id: importResultsList
                        Layout.fillWidth: true
                        // Scroll only once the rows would exceed what the pane can
                        // spare; below that the banner is only as tall as its rows.
                        Layout.preferredHeight: Math.min(contentHeight,
                            Math.max(0, importResults.maxHeight - importResultsHeader.height
                                        - importResultsFootnote.height
                                        - importResultsCol.spacing * 2 - 12))
                        clip: true
                        model: engine.scanFailures
                        spacing: 2
                        delegate: Label {
                            width: ListView.view.width
                            // The reason wording is specific to why the row was not
                            // added; a clash must NOT inherit the old corrupt-file
                            // advice, which is untrue for it.
                            text: modelData.reason === "alreadyPresent"
                                  ? qsTr("%1 was already imported and was not added again").arg(modelData.name)
                                  : modelData.reason === "nameClashWithInstalled"
                                    ? qsTr("%1 was not added: a dictionary with this name is already installed. Remove the installed one to use this build.").arg(modelData.name)
                                    : modelData.reason === "nameClash"
                                      ? qsTr("%1 is installed more than once with different content. Remove the one you do not want.").arg(modelData.name)
                                      : qsTr("%1 could not be loaded and was removed").arg(modelData.name)
                            font.pixelSize: 11
                            color: root.uiSubFg
                            wrapMode: Text.Wrap
                        }
                    }
                    Label {
                        id: importResultsFootnote
                        Layout.fillWidth: true
                        text: qsTr("Nothing else is needed from you.")
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
                                text: root.dictDisplayName(dictRow.dictData)
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
                    height: modelData.type === "header" ? 40 : 76
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
                        Item {
                            anchors.fill: parent
                            // Full-width tinted stripe so a pair boundary is an
                            // obvious separator, not a pale half-width block.
                            Rectangle {
                                anchors.fill: parent
                                color: root.uiSectionBg
                            }
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 8
                                Label {
                                    Layout.fillWidth: true
                                    text: modelData.pair
                                    font.pixelSize: 13
                                    font.bold: true
                                    color: root.uiSectionFg
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideMiddle
                                }
                                // Check indicator: reflects whether every
                                // dictionary in this pair is selected.
                                Label {
                                    text: root.icon("check")
                                    font.family: root.iconFontFamily
                                    font.pixelSize: 16
                                    color: root.uiSectionFg
                                    visible: dictsPane._pairSelected(modelData.pair)
                                }
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
                                    text: root.dictDisplayName(modelData.item)
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

        // --- remote catalog pane ---
        // A full-size pane over the Dicts list (not a modal sheet): a back arrow
        // returns to the dictionary list, matching the group membership editor,
        // and the bottom dock stays reachable. The pane's surface is opaque.
        Rectangle {
            id: catalogOverlay
            anchors.fill: parent
            visible: dictsPane.catalogOpen
            color: root.uiBg

            // A landed batch is deselected once the rescan marks it installed.
            Connections {
                target: engine
                function onCatalogChanged() { dictsPane._pruneSelection() }
                // A finished/failed/cancelled batch shows a one-line note; clear
                // it after a few seconds so it cannot linger over the list.
                function onDownloadChanged() {
                    if (engine.downloadActive) return
                    if (engine.downloadOutcome.length > 0) outcomeClearTimer.restart()
                }
            }
            Timer {
                id: outcomeClearTimer
                interval: 4000
                onTriggered: engine.clearDownloadOutcome()
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                // Header: back, title + status, sync, master download/cancel.
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    ToolButton {
                        text: root.icon("arrow_back")
                        font.family: root.iconFontFamily
                        font.pixelSize: 22
                        Accessible.name: "Back"
                        Accessible.role: Accessible.Button
                        onClicked: dictsPane.catalogOpen = false
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Label {
                            text: qsTr("Dictionary catalog")
                            font.pixelSize: 18
                            font.bold: true
                        }
                        Label {
                            Layout.fillWidth: true
                            text: engine.catalogLoading
                                ? qsTr("Checking for updates…")
                                : engine.catalogError.length > 0
                                    ? qsTr("Using the saved catalog — the update check failed.")
                                    : engine.catalogLastFetched.length > 0
                                        ? qsTr("Updated %1").arg(engine.catalogLastFetched)
                                        : qsTr("Not checked yet")
                            font.pixelSize: 11
                            color: root.uiSubFg
                            wrapMode: Text.Wrap
                            elide: Text.ElideRight
                        }
                    }
                    // Master download; becomes cancel while a batch runs. The
                    // catalog re-probes on open, so there is no separate sync
                    // button.
                    Button {
                        text: engine.downloadActive ? root.icon("close") : root.icon("cloud_download")
                        font.family: root.iconFontFamily
                        font.pixelSize: 18
                        highlighted: engine.downloadActive
                            || (dictsPane.catalogSelected.length > 0 && !engine.processingActive)
                        enabled: engine.downloadActive
                            || (dictsPane.catalogSelected.length > 0 && !engine.processingActive)
                        Accessible.name: engine.downloadActive ? "Cancel download" : "Download selected"
                        Accessible.role: Accessible.Button
                        onClicked: engine.downloadActive
                            ? engine.cancelCatalogDownload()
                            : dictsPane._startPicked()
                    }
                }

                    // Unreachable with no cache at all: the only honest thing to
                    // show is the reason, since there is no list to show.
                Label {
                    Layout.fillWidth: true
                    visible: !engine.catalogLoading && engine.catalogEntries.length === 0
                    text: engine.catalogError.length > 0
                        ? qsTr("The catalog could not be loaded.\n%1").arg(engine.catalogError)
                        : qsTr("The catalog has no dictionaries yet.")
                    font.pixelSize: 12
                    color: Material.color(Material.Red)
                    wrapMode: Text.Wrap
                }

                // Offline with a cached copy: the list below still renders, but
                // per-entry download attempts would have to trust a manifest we
                // could not re-validate, so say so rather than let a tap fail
                // with no explanation.
                Label {
                    Layout.fillWidth: true
                    visible: !engine.catalogLoading
                        && engine.catalogEntries.length > 0
                        && !engine.catalogReachable
                    text: qsTr("Showing the last saved catalog. Downloads need a connection to the catalog host.")
                    font.pixelSize: 11
                    color: Material.color(Material.Orange, Material.Shade800)
                    wrapMode: Text.Wrap
                }

                    // Progress only: a bar while a batch runs, plus a plain
                    // one-line note if it failed or was cancelled. No banners
                    // and no dismiss button — a completed entry turns grey in
                    // the list (installed), which IS the success signal.
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        visible: engine.downloadActive
                            || (engine.downloadOutcome.length > 0
                                && engine.downloadOutcome !== "succeeded")

                        ProgressBar {
                            Layout.fillWidth: true
                            visible: engine.downloadActive
                            from: 0
                            to: 1
                            value: engine.downloadFraction
                            Accessible.role: Accessible.ProgressBar
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: engine.downloadActive
                            text: engine.downloadFilesTotal > 0
                                ? qsTr("Downloading %1 (%2 of %3 files)").arg(
                                    engine.downloadEntryName)
                                  .arg(engine.downloadFilesDone)
                                  .arg(engine.downloadFilesTotal)
                                : qsTr("Downloading %1").arg(engine.downloadEntryName)
                            font.pixelSize: 12
                            color: root.uiSubFg
                            elide: Text.ElideMiddle
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: !engine.downloadActive
                            text: engine.downloadOutcome === "cancelled"
                                ? qsTr("Download cancelled.")
                                : engine.downloadMessage.length > 0
                                    ? engine.downloadMessage
                                    : qsTr("Some downloads failed.")
                            font.pixelSize: 12
                            color: Material.color(Material.Red)
                            wrapMode: Text.Wrap
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: !engine.downloadActive
                                && engine.downloadFailed.length > 0
                            text: engine.downloadFailed.join(", ")
                            font.pixelSize: 11
                            color: root.uiSubFg
                            wrapMode: Text.Wrap
                        }
                    }

                    ListView {
                        id: catalogList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 6
                        model: engine.catalogEntries
                        Accessible.name: "Remote catalog list"
                        Accessible.role: Accessible.List
                        // A row is a name block plus a music toggle on the
                        // right. Tapping the name selects the entry (and its
                        // audio); tapping the note opts the audio back out.
                        delegate: ItemDelegate {
                            id: catRow
                            required property var modelData
                            required property int index
                            width: ListView.view.width
                            height: 76
                            padding: 8
                            readonly property bool selectable: !catRow.modelData.installed
                                && catRow.modelData.installable && !engine.downloadActive
                            readonly property bool selected: dictsPane._catalogIsSelected(catRow.modelData.id)
                            readonly property bool audioOn: catRow.selected
                                && dictsPane.catalogAudioOff.indexOf(catRow.modelData.id) < 0
                            highlighted: catRow.selected
                            Accessible.name: catRow.modelData.name
                                + (catRow.modelData.installed ? ", installed" : "")
                            Accessible.role: Accessible.ListItem
                            onClicked: dictsPane._toggleCatalogSelect(catRow.modelData.id)

                            contentItem: RowLayout {
                                spacing: 8

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Label {
                                        Layout.fillWidth: true
                                        text: catRow.modelData.displayName
                                        font.pixelSize: 15
                                        font.bold: true
                                        elide: Text.ElideMiddle
                                        // Installed (downloaded) rows grey out.
                                        opacity: catRow.modelData.installed ? 0.45
                                            : (catRow.selectable ? 1.0 : 0.6)
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        text: catRow.modelData.installed
                                            ? qsTr("Installed")
                                            : qsTr("%1 to download").arg(root.fmtSize(catRow.modelData.requiredBytes))
                                        font.pixelSize: 11
                                        color: root.uiSubFg
                                        wrapMode: Text.Wrap
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        visible: !catRow.modelData.installable
                                        text: qsTr("This dictionary's format is not supported by this app version.")
                                        font.pixelSize: 11
                                        color: Material.color(Material.Red)
                                        wrapMode: Text.Wrap
                                    }
                                }

                                // Music toggle. A note means the entry has an
                                // optional bundle; `music_off` means it has none.
                                // Enabled only when it can do something: the row
                                // is selected (opt the audio out), or the entry
                                // is installed and still missing its bundle (add
                                // it now). Audio is opted OUT, so selecting a row
                                // turns the note on.
                                Button {
                                    id: audioButton
                                    readonly property bool actionable: catRow.modelData.hasOptional
                                        && (catRow.selected
                                            || (catRow.modelData.installed && !catRow.modelData.resourcesPresent))
                                    text: catRow.modelData.hasOptional
                                        ? root.icon("music_note")
                                        : root.icon("music_off")
                                    font.family: root.iconFontFamily
                                    font.pixelSize: 18
                                    enabled: audioButton.actionable && !engine.downloadActive
                                    highlighted: (catRow.selected && catRow.audioOn)
                                        || (catRow.modelData.installed && catRow.modelData.hasOptional
                                            && !catRow.modelData.resourcesPresent)
                                    Accessible.name: catRow.modelData.hasOptional
                                        ? "Audio for " + catRow.modelData.name
                                        : "No audio for " + catRow.modelData.name
                                    Accessible.role: Accessible.Button
                                    onClicked: dictsPane._toggleCatalogAudio(catRow.modelData.id)
                                }
                            }
                        }
                    }

            }
        }

        // Free-space gate for a download batch. A Dialog (not an inline
        // Rectangle) because it is modal over the catalog pane, and unlike the
        // Dicts overlays it does not need to dodge a native surface.
        Dialog {
            id: freeSpaceDialog
            anchors.centerIn: Overlay.overlay
            modal: true
            property string titleText: ""
            property string bodyText: ""
            property bool proceedAnyway: false
            property var requests: []
            standardButtons: proceedAnyway ? Dialog.Ok | Dialog.Cancel : Dialog.Cancel
            onAccepted: {
                // The warning tier lets the user proceed; the refuse tier has no
                // OK, so a batch can never start against a known-short volume.
                if (freeSpaceDialog.proceedAnyway)
                    engine.startCatalogDownload(freeSpaceDialog.requests)
                freeSpaceDialog.requests = []
            }
            onRejected: freeSpaceDialog.requests = []
            contentItem: ColumnLayout {
                spacing: 12
                Label {
                    text: freeSpaceDialog.titleText
                    font.pixelSize: 18
                    font.bold: true
                    wrapMode: Text.Wrap
                }
                Label {
                    text: freeSpaceDialog.bodyText
                    font.pixelSize: 14
                    color: root.uiFg
                    wrapMode: Text.Wrap
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
        // Every top-level pane shares this anchor line, so the side insets that keep
        // content clear of a display cutout are applied in one place. A new pane
        // must copy this line verbatim, margins included, or it will run under a
        // side-mounted camera.
        anchors { top: topBar.bottom; left: parent.left; leftMargin: root._insetLeft
                  right: parent.right; rightMargin: root._insetRight; bottom: navDock.top }
        color: root.uiBg
        visible: root.state === 3

        property int editingGroup: -1
        property string editingGroupName: ""
        property var groupNonMembers: []
        // By Pair (ui-polish): group the available-to-add list under language-pair
        // captions. The member list is deliberately NOT grouped — it is one flat,
        // draggable order (the article order).
        property bool byPair: false
        // Flattened rows for the available list: {type:"header", pair} or
        // {type:"dict", name, index}. Rebuilt from groupNonMembers.
        property var nonMemberRows: []
        property int renameGroupId: -1
        property string renameGroupName: ""
        property string renameGroupNameError: ""
        property int deleteGroupId: -1
        property string deleteGroupName: ""
        // "Add group" dialog state: the pending name and any inline error.
        property string createGroupNameError: ""
        // Drag-to-reorder state for the member list. The member list is a
        // ListModel (not a reassigned JS array) so a move repositions the
        // delegate in place instead of destroying it — the pressed MouseArea
        // therefore keeps its grab for the whole gesture, no matter how many
        // row boundaries it crosses. Reordering is applied to the local model
        // while dragging; the final order is committed to the engine once, on
        // release. _dragOrigin is the row index the gesture started on;
        // _dragIndex the dragged row's current index; _dragStartY the finger's
        // Y in the member list's coordinate space at press (that frame is fixed
        // while the row moves under the finger, so the travel does not reset).
        property int _dragOrigin: -1
        property int _dragIndex: -1
        property real _dragStartY: 0
        property bool _dragArmed: false
        // Row pitch: delegate height (44) + ListView.spacing (2).
        readonly property int memberRowPitch: 46
        // Member rows, in group order (roles: dictName, dictIndex).
        ListModel { id: memberModel }

        function _dragBegin(index, sceneY) {
            groupsPane._dragOrigin = index
            groupsPane._dragIndex = index
            groupsPane._dragStartY = sceneY
            groupsPane._dragArmed = true
        }
        function _dragMove(sceneY) {
            if (!groupsPane._dragArmed) return
            // Round to the nearest row boundary; each crossed boundary moves the
            // row one slot. Clamp to the list bounds.
            const dy = sceneY - groupsPane._dragStartY
            let to = groupsPane._dragOrigin + Math.round(dy / groupsPane.memberRowPitch)
            to = Math.max(0, Math.min(memberModel.count - 1, to))
            if (to === groupsPane._dragIndex) return
            memberModel.move(groupsPane._dragIndex, to, 1)
            groupsPane._dragIndex = to
        }
        // Release or cancel: commit the resulting order to the engine in one
        // move. A single groupMoveDict(origin, finalIndex) reproduces the order
        // built by the local moves (both are erase+insert of the same item).
        function _dragEnd() {
            if (!groupsPane._dragArmed) return
            const from = groupsPane._dragOrigin
            const to = groupsPane._dragIndex
            groupsPane._dragArmed = false
            groupsPane._dragOrigin = -1
            groupsPane._dragIndex = -1
            if (from !== -1 && to !== -1 && from !== to)
                engine.groupMoveDict(groupsPane.editingGroup, from, to)
        }

        function _openMembership(id, name) {
            editingGroup = id
            editingGroupName = name
            // Reset the child lists so opening always starts blank: stale
            // members from a previous open can linger otherwise, and the
            // membership ColumnLayout shows stale rows until the async
            // onGroupDictsReady replaces them.
            memberModel.clear()
            groupsPane.groupNonMembers = []
            groupsPane.nonMemberRows = []
            engine.groupDicts(id)
        }
        // Rebuild the available-to-add rows. Flat when By Pair is off; grouped
        // under pair caption rows (same pairing as the Dicts tab) when on.
        function _rebuildNonMemberRows() {
            const src = groupsPane.groupNonMembers
            const rows = []
            if (!groupsPane.byPair) {
                for (let i = 0; i < src.length; i++)
                    rows.push({ type: "dict", name: src[i].name, index: src[i].index })
            } else {
                const byPair = {}
                for (let i = 0; i < src.length; i++) {
                    const p = root._pairForDictIndex(src[i].index)
                    if (!byPair[p]) byPair[p] = []
                    byPair[p].push(src[i])
                }
                const pairs = Object.keys(byPair).sort()
                for (const p of pairs) {
                    rows.push({ type: "header", pair: p })
                    for (const it of byPair[p])
                        rows.push({ type: "dict", name: it.name, index: it.index })
                }
            }
            groupsPane.nonMemberRows = rows
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
            deleteGroupDialog.open()
        }
        // The standard OK/Cancel buttons close the dialog themselves; we only
        // manage state. Clear deleteGroupId (hides) but NOT deleteGroupName: the
        // dialog animates shut, and blanking the name during the close animation
        // made it flash "Delete group ''?" (which looked like a second dialog).
        // _requestDeleteGroup always re-sets the name before reopening.
        function _confirmDeleteGroup() {
            const id = deleteGroupId
            deleteGroupId = -1
            if (id > 0) engine.deleteGroup(id)
        }
        function _cancelDeleteGroup() {
            deleteGroupId = -1
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
                // If an engine refresh lands while a drag is in flight (e.g. the
                // previous gesture's async commit completes just after the next
                // drag began), ignore it: the local model is authoritative until
                // the active gesture commits.
                if (groupsPane._dragArmed) return
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
                memberModel.clear()
                for (let i = 0; i < m.length; ++i)
                    memberModel.append({ "dictName": m[i].name, "dictIndex": m[i].index })
                groupsPane.groupNonMembers = nm
                groupsPane._rebuildNonMemberRows()
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

                // "Add" is an icon button (standard icon-button styling, like the
                // dictionary toolbar) that opens the name dialog; a new group is
                // created and the membership editor opens immediately on OK.
                Button {
                    text: root.icon("create_new_folder")
                    font.family: root.iconFontFamily
                    font.pixelSize: 18
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
                    // Visible label is localized; Accessible.name above stays the
                    // invariant English name so UIAutomator addressing is unchanged
                    // across locales (design D2).
                    contentItem: Label {
                        text: qsTr("%1 (%2)").arg(root._groupLabel(groupRow.groupData.id)).arg(groupRow.groupData.dictCount)
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
                        // Any group opens the editor. "All" opens in reorder-only
                        // mode (its membership is fixed; only the article order
                        // is editable — see the editor below).
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
                    // a "Group: " prefix would be redundant. Resolved by id, not
                    // read from the stored name, so the built-in group reads in
                    // the active language here too.
                    text: root._groupLabel(groupsPane.editingGroup)
                    font.pixelSize: 16
                    font.bold: true
                    elide: Text.ElideMiddle
                }
                // By Pair: group the available-to-add list under language-pair
                // captions (the member list stays one flat, draggable order).
                // Meaningless for "All" (no available-to-add list), so hidden.
                Button {
                    text: root.icon("translate")
                    font.family: root.iconFontFamily
                    font.pixelSize: 18
                    highlighted: groupsPane.byPair
                    visible: groupsPane.editingGroup !== 0
                    Accessible.name: "By Pair"
                    Accessible.role: Accessible.Button
                    onClicked: {
                        groupsPane.byPair = !groupsPane.byPair
                        groupsPane._rebuildNonMemberRows()
                    }
                }
                Button {
                    text: root.icon("edit")
                    font.family: root.iconFontFamily
                    font.pixelSize: 18
                    // Primary action: accent styling so the pencil does not read
                    // as disabled (control-state-and-fts-whole-words).
                    highlighted: true
                    // "All" is fixed: it cannot be renamed.
                    visible: groupsPane.editingGroup !== 0
                    Accessible.name: "Rename group"
                    Accessible.role: Accessible.Button
                    onClicked: groupsPane._openRename(groupsPane.editingGroup, groupsPane.editingGroupName)
                }
            }

            Label {
                Layout.fillWidth: true
                text: groupsPane.editingGroup === 0
                    // "All" holds every dictionary; only the order is editable.
                    ? qsTr("Article order: drag to set which dictionary's results come first.")
                    : qsTr("In this group (%1)").arg(memberModel.count)
                color: root.uiSubFg
                font.pixelSize: 13
                wrapMode: Text.Wrap
            }

            ListView {
                id: memberList
                Layout.fillWidth: true
                Layout.preferredHeight: 190
                // "All" has no add/remove section below, so let its list fill the
                // pane.
                Layout.fillHeight: groupsPane.editingGroup === 0
                clip: true
                model: memberModel
                spacing: 2
                Accessible.name: "Group members"
                Accessible.role: Accessible.List
                delegate: ItemDelegate {
                    id: memberRow
                    width: ListView.view.width
                    height: 44
                    padding: 4
                    // Mark the row that's being dragged/reordered so the active
                    // line is visible while the finger moves it. `index` follows
                    // the row as ListModel.move() relocates it.
                    highlighted: index === groupsPane._dragIndex
                    Accessible.name: dictName
                    Accessible.role: Accessible.ListItem

                    contentItem: Item {
                        RowLayout {
                            // Reserve the trailing remove button's width so a long
                            // dictionary name elides clear of it (ui-polish).
                            anchors {
                                fill: parent
                                rightMargin: 56
                            }
                            spacing: 6
                            // Only the left-hand handle is the drag surface. A
                            // fixed-width slot whose MouseArea fills it, so a
                            // drag that starts anywhere else on the row falls
                            // through to the ListView and scrolls it instead of
                            // arming a reorder.
                            Item {
                                id: dragHandle
                                Layout.preferredWidth: 48
                                Layout.fillHeight: true

                                Label {
                                    anchors.centerIn: parent
                                    text: root.icon("drag_handle")
                                    font.family: root.iconFontFamily
                                    font.pixelSize: 20
                                    color: root.uiSubFg
                                }

                                MouseArea {
                                    id: dragArea
                                    anchors.fill: parent
                                    // Keep the ListView's flick-scroll from
                                    // stealing the gesture once a reorder drag
                                    // starts on the handle.
                                    preventStealing: true
                                    Accessible.name: "Reorder"
                                    Accessible.role: Accessible.Button
                                    // QQuickMouseEvent (Qt 6.6) has no
                                    // scenePosition, so map the finger into the
                                    // ListView's coordinate space: that frame is
                                    // fixed while the row moves under the finger,
                                    // so the travel does not reset.
                                    function _listY(mouse) {
                                        return dragArea.mapToItem(memberList, mouse.x, mouse.y).y
                                    }
                                    onPressed: (mouse) => {
                                        groupsPane._dragBegin(index, dragArea._listY(mouse))
                                    }
                                    onPositionChanged: (mouse) => {
                                        groupsPane._dragMove(dragArea._listY(mouse))
                                    }
                                    onReleased: groupsPane._dragEnd()
                                    onCanceled: groupsPane._dragEnd()
                                }
                            }
                            Label {
                                Layout.fillWidth: true
                                text: dictName
                                elide: Text.ElideMiddle
                                verticalAlignment: Text.AlignVCenter
                            }
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
                            // "All" membership is fixed: reorder only, no removal.
                            visible: groupsPane.editingGroup !== 0
                            Accessible.name: "Remove from group"
                            Accessible.role: Accessible.Button
                            onClicked: engine.groupRemoveDict(groupsPane.editingGroup, dictIndex)
                        }
                    }
                }
            }

            Label {
                Layout.fillWidth: true
                visible: groupsPane.editingGroup !== 0
                text: qsTr("Add dictionaries"); color: root.uiSubFg; font.pixelSize: 13
            }

            ListView {
                id: nonMemberList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                visible: groupsPane.editingGroup !== 0
                model: groupsPane.nonMemberRows
                spacing: 2
                Accessible.name: "Available dictionaries to add"
                Accessible.role: Accessible.List
                delegate: ItemDelegate {
                    id: nonMemberRow
                    property var rowData: modelData
                    readonly property bool isHeader: rowData && rowData.type === "header"
                    width: ListView.view.width
                    height: isHeader ? 40 : 44
                    padding: isHeader ? 8 : 4
                    Accessible.name: nonMemberRow.isHeader ? rowData.pair
                        : (rowData ? rowData.name : "")
                    Accessible.role: nonMemberRow.isHeader ? Accessible.StaticText
                        : Accessible.ListItem

                    contentItem: Loader {
                        anchors.fill: parent
                        sourceComponent: nonMemberRow.isHeader
                            ? nonMemberHeaderComp : nonMemberDictComp
                    }

                    // Pair caption row (By Pair on). Cosmetic separator only —
                    // available dictionaries are never reordered.
                    Component {
                        id: nonMemberHeaderComp
                        Item {
                            anchors.fill: parent
                            Rectangle {
                                anchors.fill: parent
                                color: root.uiSectionBg
                            }
                            Label {
                                anchors {
                                    left: parent.left; leftMargin: 10
                                    right: parent.right; rightMargin: 10
                                    verticalCenter: parent.verticalCenter
                                }
                                text: nonMemberRow.rowData.pair
                                font.pixelSize: 13
                                font.bold: true
                                color: root.uiSectionFg
                                elide: Text.ElideMiddle
                            }
                        }
                    }

                    Component {
                        id: nonMemberDictComp
                        Label {
                            // Reserve the trailing add button's width so a long
                            // name elides clear of it instead of running under it.
                            text: nonMemberRow.rowData.name
                            elide: Text.ElideMiddle
                            rightPadding: 56
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    ToolButton {
                        anchors {
                            right: parent.right
                            rightMargin: 4
                            verticalCenter: parent.verticalCenter
                        }
                        visible: !nonMemberRow.isHeader
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
        // Every top-level pane shares this anchor line, so the side insets that keep
        // content clear of a display cutout are applied in one place. A new pane
        // must copy this line verbatim, margins included, or it will run under a
        // side-mounted camera.
        anchors { top: topBar.bottom; left: parent.left; leftMargin: root._insetLeft
                  right: parent.right; rightMargin: root._insetRight; bottom: navDock.top }
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
                            text: root._groupLabel(favRow.group)
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
        // picked, or Back/Forward restored one). Keep the Search group button in
        // sync with the item's data.
        function onGroupsChanged() {
            if (!engine.groupExists(root.searchGroupId)) root.searchGroupId = 0
            if (!engine.groupExists(root.ftsGroupId)) root.ftsGroupId = 0
        }
        function onActiveGroupChanged() {
            root.searchGroupId = engine.activeGroupId
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
    Timer {
        id: findDebounce
        // Coalesce find-as-you-type so the DOM is not re-marked on every key.
        interval: 150
        onTriggered: root._applyFind()
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
            // The blank base document has no injected controller, so its canvas is
            // restated here directly; the article's own flip is handled inside
            // gdSetDarkMode. Both use the same two colors.
            const c = JSON.stringify(root.uiBgHex())
            root.inlineWv.runJavaScript(
                "try{if(document.documentElement)document.documentElement.style"
                + ".background=" + c + ";if(window.gdSetDarkMode)gdSetDarkMode("
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
                + "var h=a?a.href:'';"
                // Keep audio and gdlookup taps INSIDE the WebView: play the
                // sound / open the entry in place. Without preventDefault the
                // WebView navigates to the loopback audio URL, which hands it to
                // Android's native media player and blanks the article.
                + "if(h.indexOf('/gdau/')>=0||h.indexOf('/gdlookup/')>=0||h.indexOf('gdlookup://')===0){e.preventDefault();}"
                + "window.__tapped=h;},true);"
                + "window.__probeInstalled=true;}"
                + "var act=window.__gdAction||'';window.__gdAction='';"
                + "var s=window.__suggWord||'';window.__suggWord='';"
                // Consume the tap so a second tap on the same audio link still
                // replays (the value must not persist between polls).
                + "var tap=window.__tapped||'';window.__tapped='';"
                + "(act ? 'ACT:'+act : (s ? 'SUGG:'+s : tap))",
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
                    // Anchor taps (audio / gdlookup) are consumed in-page each
                    // poll, so every tap reaches here — including replaying the
                    // same audio link twice.
                    _handleArticleLink(v)
                })
        }
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
        // Every top-level pane shares this anchor line, so the side insets that keep
        // content clear of a display cutout are applied in one place. A new pane
        // must copy this line verbatim, margins included, or it will run under a
        // side-mounted camera.
        anchors { top: topBar.bottom; left: parent.left; leftMargin: root._insetLeft
                  right: parent.right; rightMargin: root._insetRight; bottom: navDock.top }
        color: root.uiBg
        visible: root.state === 4

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
                    Accessible.name: "Full-text search"
                    Accessible.role: Accessible.EditableText
                    // No font.pixelSize override: see the Search field above —
                    // enlarging it breaks the floating label's placement.
                    // Typing never runs a search, but it invalidates results that
                    // no longer match the box (control-state-and-fts-whole-words).
                    // displayText, not text: during IME composition `text` lags
                    // behind what the user sees, so the submit guard and the
                    // search control's enabled state must read what is on screen
                    // (same reason the Search tab's _doSuggest uses displayText).
                    onDisplayTextChanged: root._invalidateFtsResults()
                    onAccepted: root._runFts()
                }

                Button {
                    id: ftsGroupButton
                    Layout.fillWidth: true
                    Layout.preferredWidth: 3
                    Layout.minimumWidth: 0
                    // Same permanent accent fill as the Search tab's group button.
                    highlighted: true
                    padding: 4
                    font.pixelSize: 14
                    text: {
                        if (engine.groups.length === 0) return ""
                        const i = root._groupIndexForId(root.ftsGroupId)
                        const matches = i >= 0 && i < engine.groups.length
                            && engine.groups[i].id === root.ftsGroupId
                        return root._groupLabel(matches ? root.ftsGroupId : 0)
                    }
                    Accessible.name: "Full-text search group scope"
                    Accessible.role: Accessible.Button
                    onClicked: {
                        ftsInput.focus = false
                        groupPicker.openAt(root._groupIndexForId(root.ftsGroupId), "fts")
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
                    Accessible.name: "Whole words"
                    Accessible.role: Accessible.CheckBox
                    onClicked: {
                        // The toggle changes the NEXT search's mode; it does not
                        // run one. Results from the other mode are invalidated.
                        root.ftsWholeWordsOn = !root.ftsWholeWordsOn
                        root._invalidateFtsResults()
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

            // The one way to submit a full-text search. Its own row below the
            // query/scope/whole-words controls so those keep their original
            // sizes and the row keeps its original 7:3 split. Disabled while the
            // query is blank and for the whole duration of a submitted search, so
            // a slow search cannot be started twice.
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Button {
                    id: ftsSearchButton
                    Layout.preferredWidth: 48
                    leftPadding: 12
                    rightPadding: 12
                    highlighted: true
                    enabled: !root.ftsSearching && ftsInput.displayText.trim().length > 0
                    Accessible.name: "Search"
                    Accessible.role: Accessible.Button
                    onClicked: root._runFts()
                    contentItem: Text {
                        text: root.icon("search")
                        font.family: root.iconFontFamily
                        font.pixelSize: 20
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: ftsSearchButton.enabled
                            ? ftsSearchButton.Material.primaryHighlightedTextColor
                            : ftsSearchButton.Material.foreground
                    }
                }
                Item { Layout.fillWidth: true }
            }

            // 8.1: index-build progress is shown in the Dicts tab banner only.
            // The FTS controls stay enabled while a build runs: the build now
            // interleaves with the engine, so a search over other dictionaries
            // returns within about one indexing slice (fts-indexing-performance).

            Label {
                Layout.fillWidth: true
                // A whitespace-only message is not an error worth painting: the
                // engine can report a blank string, which used to show an empty
                // red "engine error:" line.
                visible: engine.lastError.trim().length > 0
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
                        const gid = engine.groupExists(root.ftsGroupId) ? root.ftsGroupId : 0
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
    // which group button to update on selection and whether the Search WebView
    // needs the teardown/restore dance (only the Search tab has an inline WebView).
    property string _pickerTarget: "search"
    // Set when a Search-scope selection started an article lookup. On close the
    // candidate surface must then be left for that article instead of being
    // re-queried for suggestions (which used to repaint over the article).
    property bool _pickerStartedLookup: false
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
            root._pickerStartedLookup = false
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
            // Exception: a Search-scope selection that started a lookup owns the
            // surface — do not re-query suggestions over the incoming article.
            if (root._pickerStartedLookup) {
                root._pickerStartedLookup = false
                return
            }
            if (input.displayText.trim().length > 0) searchPane._doSuggest()
            else root._showHistoryOverlay()
        }
        onOpened: {
            // Scroll to the currently-active group.
            let activeIndex = 0
            if (root._pickerTarget === "fts")
                activeIndex = root._groupIndexForId(root.ftsGroupId)
            else
                activeIndex = root._groupIndexForId(root.searchGroupId)
            if (activeIndex >= 0 && activeIndex < engine.groups.length) {
                groupPickerList.currentIndex = activeIndex
                groupPickerList.positionViewAtIndex(activeIndex, ListView.Center)
            }
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
                    text: root._groupLabel(modelData.id)
                    highlighted: groupPickerList.currentIndex === index
                    font.pixelSize: 16
                    Accessible.name: modelData.name
                    Accessible.role: Accessible.ListItem
                    onClicked: {
                        const g = engine.groups[index]
                        if (g) {
                            groupPickerList.currentIndex = index
                            if (root._pickerTarget === "fts") {
                                root.ftsGroupId = g.id
                                // A scope change does not run a search: it changes
                                // what the next submit will search, and invalidates
                                // results produced for the previous scope.
                                root._invalidateFtsResults()
                            } else {
                                root.searchGroupId = g.id
                                const q = input.displayText.trim()
                                if (q.length > 0) {
                                    // Switching the group actually triggers a lookup
                                    // of the typed query in the new group. This also
                                    // sets the active group and records the entry
                                    // (a fresh search → new history item). Flag it so
                                    // onClosed leaves the surface for the article.
                                    root._pickerStartedLookup = true
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
