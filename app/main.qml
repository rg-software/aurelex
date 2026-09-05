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
    // The article WebView is created on demand (articleLoader) to avoid
    // standing up a full-bleed native Android WebView over the UI at startup;
    // root.view aliases the loaded item (null until article mode).
    property var view: articleLoader.item
    // Back-stack for in-article navigation. Each entry is a {word, html} pair
    // so the Back button can pop to the previous article without losing scroll
    // position (we re-render the prior article's HTML).
    property var navStack: []
    // True while the foreground StagingService is copy-staging a picked folder.
    // Drives the Dicts-tab "Preparing dictionaries…" banner.
    property bool _stagingActive: engine.stagingActive

    // Material icon font family (registered from fonts.qrc in main.cpp) + the
    // icon-name -> codepoint helper (qt-material-ui task 7.2).
    property string iconFontFamily: "Material Icons"
    function icon( name ) {
        var map = {
            "search": 0xe8b6,
            "menu_book": 0xe3c9,
            "library_books": 0xe02f,
            "manage_search": 0xe3d9,
            "content_paste_search": 0xe94a,
            "folder": 0xe2c7,
            "history": 0xe889,
            "star": 0xe838,
            "star_border": 0xe83a,
            "arrow_back": 0xe5c4,
            "close": 0xe5cd,
            "add": 0xe145,
            "delete": 0xe872,
            "bookmark": 0xe866,
            "dark_mode": 0xe51c
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
        if (bytes >= gb) return (Math.round(bytes * 10 / gb) / 10) + " GB"
        if (bytes >= mb) return Math.round(bytes / mb) + " MB"
        if (bytes >= kb) return Math.round(bytes / kb) + " KB"
        return bytes + " B"
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
            // its suggestion overlay are destroyed on leaving).
            root._returningToSearch = true
            root.inlineWebReady = false
            root.inlineWebTimer.stop()
        } else if (root._returningToSearch) {
            // Back on the Search tab: refocus the field (so Enter works again)
            // and re-populate candidates for the text that's still typed. The
            // fresh inline WebView is (re)created by inlineWebTimer shortly
            // after; the pending suggestions are flushed once it's ready.
            root._returningToSearch = false
            input.forceActiveFocus()
            if (input.text.trim().length > 0) searchPane._doSuggest()
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
        root._hideSuggestOverlay()
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
        root._suggWords = words
        articleLinkPoller._lastSugg = ""
        root._applySuggestOverlay()
    }
    function _applySuggestOverlay() {
        const words = root._suggWords
        const wv = root.inlineWv
        // Need a live WebView that actually has a loaded document (URL present).
        // runJavaScript on a doc-less WebView silently does nothing.
        if (!wv || root._blankPending || words.length === 0) return
        const url = wv.url.toString()
        if (url.length < 6) return
        const base = engine.articleBaseUrl
        if (base.length < 5) return
        const dark = engine.darkMode
        const bg = dark ? "#242526" : "#ffffff"
        const fg = dark ? "#e0e0e0" : "#202124"
        const sep = dark ? "#3a3b3c" : "#eeeeee"
        var html = '<div id="gd-sugg" style="position:fixed;top:0;left:0;right:0;'
            + 'z-index:9999;background:' + bg + ';color:' + fg + ';'
            + 'box-shadow:0 2px 10px rgba(0,0,0,0.4);overflow-y:auto;max-height:72%;'
            + 'font-family:Roboto,sans-serif;font-size:16px;text-align:left;">'
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
        html += '</div>'
        const script = '(function(){var e=document.getElementById("gd-sugg");if(e)e.remove();'
            + 'var d=document.createElement("div");d.id="gd-sugg";d.innerHTML='
            + JSON.stringify(html) + ';document.body.appendChild(d);})()'
        wv.runJavaScript(script)
        root._suggVisible = true
    }
    function _hideSuggestOverlay() {
        root._suggWords = []
        articleLinkPoller._lastSugg = ""
        if (root.inlineWv && root._suggVisible) {
            root.inlineWv.runJavaScript(
                '(function(){var e=document.getElementById("gd-sugg");if(e)e.remove();})()')
        }
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
        if (root.inlineWv && root.currentHtml.length === 0 && engine.articleBaseUrl.length > 5) {
            root._blankPending = true
            root.inlineWv.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
        }
    }
    function _showArticle(word, html) {
        // A picked word replaces the candidate list — collapse the dropdown.
        root._hideSuggestOverlay()
        if (currentWord !== "" && currentWord !== word) {
            navStack.push({ word: currentWord, html: currentHtml })
        }
        currentWord = word
        currentHtml = html
        _blurActive()
        if (state === 0) {
            // Inline mode: show article below suggestions in the search tab.
            inlineArticle = true
            articleLoadTimer.restart()
        } else {
            state = 2
            articleLoadTimer.restart()
        }
    }
    function _backFromArticle() {
        if (navStack.length === 0) {
            // No more articles in the stack.
            if (root.inlineArticle) {
                // Clear inline article and return to pure suggestions view. The
                // query is still in the field, so re-show its candidates (the
                // regular typing path doesn't fire — the text didn't change).
                root._clearInlineArticle()
                searchPane._doSuggest()
                return
            }
            state = 0
            return
        }
        const prev = navStack.pop()
        currentWord = prev.word
        currentHtml = prev.html
        if (root.inlineArticle) {
            // Stay in inline mode, re-render the previous article.
            articleLoadTimer.restart()
        } else {
            state = 2
            articleLoadTimer.restart()
        }
    }
    function _blurActive() {
        if (root.activeFocusItem && root.activeFocusItem.forceActiveFocus === undefined) return
        if (input.activeFocus) input.focus = false
        if (newGroupInput.activeFocus) newGroupInput.focus = false
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
        ftsResults = []
        state = 4
    }
    function _openHistory() {
        _blurActive()
        state = 5
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
        engine.ftsSearch(ftsInput.text, 2, gid, ftsWholeWords.checked)
    }
    // Navigation labels/icons for the bottom TabBar.
    property var navItems: [
        { idx: 0, label: "Search",   icon: "search" },
        { idx: 1, label: "Dicts",    icon: "menu_book" },
        { idx: 3, label: "Groups",   icon: "library_books" },
        { idx: 4, label: "FTS",      icon: "manage_search" },
        { idx: 5, label: "History",  icon: "history" },
        { idx: 6, label: "Favs",     icon: "star" }
    ]
    function _navTo(idx) {
        if (idx === 0) {
            _blurActive()
            // An article left over from another pane (full-pane article opened
            // from Favs/History/FTS) must not carry into a fresh Search — a
            // stale article would steal the WebView and the typed query's
            // suggestions would never show. Inline articles (opened IN Search)
            // were already wiped above on the way out.
            if (root.currentHtml.length > 0 && !root.inlineArticle) {
                root.currentWord = ""
                root.currentHtml = ""
                root.navStack = []
            }
            state = 0
            return
        }
        // Leaving the search tab: clear any inline article state.
        if (root.inlineArticle) {
            root._clearInlineArticle()
        }
        if (idx === 1) { _openDicts(); return }
        if (idx === 3) { _openGroups(); return }
        if (idx === 4) { _openFts(); return }
        if (idx === 5) { _openHistory(); return }
        if (idx === 6) { _openFavorites(); return }
    }

    Connections {
        target: engine
        function onFtsSearchReady(query, results) {
            if (query !== ftsInput.text) return
            ftsResults = results
        }
    }

    // --- shared top bar (Material ToolBar) ---
    ToolBar {
        id: topBar
        width: parent.width
        z: 5
        Accessible.name: "Top toolbar"
        Accessible.role: Accessible.ToolBar

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 8
            spacing: 8

            Label {
                Layout.fillWidth: true
                elide: Text.ElideRight
                text: root.state === 0 ? "Search"
                    : root.state === 1 ? "Dictionaries (" + engine.dictCount + ")"
                    : root.state === 3 ? "Groups (" + engine.groups.length + ")"
                    : root.state === 4 ? "FTS (" + root.ftsResults.length + ")"
                    : root.state === 5 ? "History (" + engine.history.length + ")"
                    : root.state === 6 ? "Favorites (" + engine.favorites.length + ")"
                    : root.currentWord
            }

            ToolButton {
                // Manual dark override D toggle. When following system it forces
                // dark; when forcing dark it returns to following the system theme.
                property string _name: "dark_mode"
                Accessible.name: engine.userDarkOverride || engine.systemDark ? "Light mode" : "Dark mode"
                Accessible.role: Accessible.Button
                text: root.icon("dark_mode")
                font.family: root.iconFontFamily
                font.pixelSize: 20
                ToolTip.visible: hovered
                ToolTip.text: engine.userDarkOverride ? "Dark (forced) — tap to follow system"
                                                       : "Follow system — tap to force dark"
                onClicked: {
                    engine.toggleDarkOverride()
                    root._blurActive()
                }
            }
        }
    }

    // --- bottom navigation (Material TabBar, replaces the old cycle button) ---
    TabBar {
        id: navBar
        // 5.2: anchor to the BOTTOM. Without anchors the TabBar defaulted to
        // (0,0) and rendered as a second top bar overlapping the ToolBar; every
        // pane (bottom: navBar.top) then collapsed against y=0.
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        z: 5
        Accessible.name: "Main navigation"
        Accessible.role: Accessible.TabBar
        // 5.2: highlight the active tab by driving the TabBar's own selection
        // (TabButton has no `highlighted` in Qt 6.6). State -> tab index; the
        // article pane (state 2) has no tab, so clear the selection.
        currentIndex: root.state === 2 ? -1
                    : root.state === 3 ? 2
                    : root.state === 4 ? 3
                    : root.state === 5 ? 4
                    : root.state === 6 ? 5
                    : root.state

        Repeater {
            model: root.navItems
            delegate: TabButton {
                id: tabBtn
                // Equal-width tabs from the fixed window width (avoiding a
                // TabButton width <-> TabBar implicitWidth binding loop).
                width: root.width / root.navItems.length
                // 5.3: icon glyph in the Material Icons font + label in the theme
                // font. The default TabButton renders `text` in a single font, so
                // applying the icon font hid the labels (icon font has no Latin
                // glyphs). Custom two-line contentItem mirrors the Material
                // TabButton color rule (checked/down -> accent).
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
                Accessible.name: modelData.label
                Accessible.role: Accessible.TabButton
                onClicked: root._navTo(modelData.idx)
            }
        }
    }

    // --- search view ---
    Rectangle {
        id: searchPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navBar.top }
        color: root.uiBg
        visible: root.state === 0

        function _doSuggest() {
            const t = input.displayText
            if (t.trim().length === 0) {
                root._hideSuggestOverlay()
                return
            }
            // When the user types a new query, clear any inline article.
            if (root.inlineArticle) {
                root._clearInlineArticle()
            }
            engine.suggest(t)
        }

        property var pendingSuggestions: []

        Connections {
            target: engine
            function onSuggestionsReady(prefix, suggestions) {
                searchPane.pendingSuggestions = suggestions
                root._renderSuggestOverlay(suggestions)
            }
            function onArticleNotFound(word) {
                root._renderSuggestOverlay(["(no results for " + word + ")"])
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
                    placeholderText: "Search dictionaries"
                    Accessible.name: "Search dictionaries"
                    Accessible.role: Accessible.EditableText
                    font.pixelSize: 18
                    onDisplayTextChanged: searchPane._doSuggest()
                    onAccepted: { input.focus = false; root._requestedWord = text.trim(); engine.lookup(text.trim()) }
                    Component.onCompleted: forceActiveFocus()
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
                    // Dismiss the search field's IME when the dropdown opens, else
                    // the keyboard obscures/blocks the popup while typing.
                    popup.onOpened: input.focus = false
                    onActivated: (index) => {
                        const g = engine.groups[index]
                        if (g) engine.setActiveGroup(g.id)
                        // Re-run suggestions for the newly selected group's scope.
                        if (input.text.trim().length > 0) searchPane._doSuggest()
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
                text: "engine error: " + engine.lastError
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
                    width: parent.width
                    height: 40
                    color: root.uiCard
                    border.color: root.uiBorder

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 4
                        anchors.rightMargin: 4
                        spacing: 4

                        ToolButton {
                            text: root.icon("arrow_back")
                            font.family: root.iconFontFamily
                            font.pixelSize: 22
                            enabled: root.inlineArticle
                            Accessible.name: "Back"
                            Accessible.role: Accessible.Button
                            onClicked: root._backFromArticle()
                        }
                        ToolButton {
                            property bool active: root.inlineArticle
                                && engine.favorites.indexOf(root.currentWord) >= 0
                            text: root.icon(active ? "star" : "star_border")
                            font.family: root.iconFontFamily
                            font.pixelSize: 22
                            enabled: root.inlineArticle
                            Material.foreground: active ? Material.primary : root.uiSubFg
                            Accessible.name: active ? "Remove from favorites" : "Add to favorites"
                            Accessible.role: Accessible.Button
                            onClicked: engine.toggleFavorite(root.currentWord)
                        }
                        Label {
                            Layout.fillWidth: true
                            text: root.inlineArticle ? root.currentWord : "Dictionary article"
                            elide: Text.ElideRight
                            color: root.inlineArticle ? root.uiFg : root.uiSubFg
                            font.pixelSize: 14
                        }
                    }
                }

                Loader {
                    id: searchArticleLoader
                    anchors { top: parent.top; topMargin: 40; left: parent.left; right: parent.right; bottom: parent.bottom }
                    // Defer WebView creation until the scene is measured.
                    // On Android, a WebView created before layout runs locks its
                    // native surface to a wrong (full-window) size that then
                    // overtakes the whole screen. inlineWebReady is set by a
                    // short timer once the Search tab is actually visible.
                    active: root.state === 0 && root.inlineWebReady
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
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navBar.top }
        color: root.uiBg
        visible: root.state === 1

        Component.onCompleted: engine.refreshDictionaries()
        property int removeIndex: -1
        property string removeName: ""
        property bool byPair: false
        // Indices of selected dictionary rows (for RemoveSelected).
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
        function _requestRemove(index, name) { removeIndex = index; removeName = name }
        function _confirmRemove() {
            const idx = removeIndex
            if (idx >= 0) engine.removeDictionary(idx)
            removeIndex = -1
            removeName = ""
        }
        function _cancelRemove() { removeIndex = -1; removeName = "" }
        function _toggleSelect(idx) {
            const sel = dictsPane.selectedDicts
            const i = sel.indexOf(idx)
            if (i >= 0) sel.splice(i, 1)
            else sel.push(idx)
            dictsPane.selectedDicts = sel
        }
        function _removeSelected() {
            // Copy indices high-to-low so removal doesn't shift later ones; then
            // clear the selection and refresh.
            const sel = dictsPane.selectedDicts.slice().sort((a,b)=>b-a)
            for (const idx of sel) engine.removeDictionary(idx)
            dictsPane.selectedDicts = []
        }
        // Per-pair removal: remove every dictionary whose pair == the caption's.
        function _removePair(pair) {
            for (let i = engine.dictionaries.length - 1; i >= 0; i--) {
                if (root.fmtPair(engine.dictionaries[i]) === pair)
                    engine.removeDictionary(i)
            }
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
                        text: root._stagingActive ? "Preparing dictionaries…"
                            : engine.scanningActive ? "Scanning dictionaries…"
                            : "Indexing (" + (engine.ftsIndexDone + 1) + " of "
                              + engine.ftsIndexTotal + "): " + engine.ftsCurrentDictName
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
                              ? "Copying dictionary files into app storage. Your dictionaries will appear here when it's done."
                              : "Reading dictionary files…"
                        color: root.uiSubFg
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // 8.2: "Add dictionaries" (folder-scoped SAF picker). Qt 6.6
                // RoundButton stands in for the Material 3 FloatingActionButton.
                RoundButton {
                    text: "Add dictionaries"
                    highlighted: true
                    Accessible.name: "Add dictionaries"
                    Accessible.role: Accessible.Button
                    onClicked: engine.addDictionaryFolder()
                }
                // By Pair toggle: group the dictionary list by Source/Target.
                Button {
                    text: "By Pair"
                    highlighted: dictsPane.byPair
                    Accessible.name: "By Pair"
                    Accessible.role: Accessible.Button
                    onClicked: dictsPane.byPair = !dictsPane.byPair
                }
                // Multi-select removal (enabled when >=1 row is selected).
                Button {
                    text: "Remove"
                    enabled: dictsPane.selectedDicts.length > 0
                    Accessible.name: "Remove"
                    Accessible.role: Accessible.Button
                    onClicked: dictsPane._removeSelected()
                }
            }

            Label {
                Layout.fillWidth: true
                color: root.uiSubFg
                font.pixelSize: 12
                wrapMode: Text.Wrap
                text: "Tap Add dictionaries to import a folder containing dictionary files (.mdx, .dsl, .dsl.dz, .ifo). The folder is copied into the app once; no system-wide storage access is needed."
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
                        text: engine.scanFailures.length + " dictionary file(s) failed to load"
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
                        text: "The file may be incomplete or corrupt. Tap Add dictionaries and pick the same folder again to re-copy it."
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
                        ToolButton {
                            text: "Remove"
                            Accessible.name: "Remove"
                            Accessible.role: Accessible.Button
                            onClicked: dictsPane._requestRemove(dictRow.dictIndex, dictRow.dictData.name)
                        }
                    }
                }
            }

            // Grouped list (By Pair on): header rows + dict rows from a flattened model.
            ListView {
                id: dictsListByPair
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
                            ToolButton {
                                text: "Remove"
                                Accessible.name: "Remove pair"
                                Accessible.role: Accessible.Button
                                onClicked: dictsPane._removePair(modelData.pair)
                            }
                        }
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
                            ToolButton {
                                text: "Remove"
                                Accessible.name: "Remove"
                                Accessible.role: Accessible.Button
                                onClicked: dictsPane._requestRemove(modelData.dictIndex, modelData.item.name)
                            }
                        }
                    }

                    onClicked: {
                        if (modelData.type !== "header")
                            dictsPane._toggleSelect(modelData.dictIndex)
                    }
                }
            }
        }

        // --- remove-dictionary confirm dialog ---
        Dialog {
            id: removeDialog
            anchors.centerIn: parent
            width: Math.min(parent.width - 80, 360)
            modal: true
            title: "Remove dictionary"
            visible: dictsPane.removeIndex >= 0
            Accessible.name: "Remove dictionary confirmation"
            Accessible.role: Accessible.Dialog

            ColumnLayout {
                width: parent.width
                spacing: 8
                Label {
                    Layout.fillWidth: true
                    text: "Remove dictionary \"" + (dictsPane.removeName !== "" ? dictsPane.removeName : "(unknown)") + "\"?"
                    wrapMode: Text.Wrap
                }
                Label {
                    Layout.fillWidth: true
                    color: root.uiSubFg
                    text: "It will be permanently removed: the app's copy of the dictionary files and its search index will be deleted. The original folder is never touched."
                    wrapMode: Text.Wrap
                }
            }

            standardButtons: Dialog.Cancel | Dialog.Ok

            onAccepted: dictsPane._confirmRemove()
            onRejected: dictsPane._cancelRemove()
        }
    }

    Rectangle {
        id: groupsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navBar.top }
        color: root.uiBg
        visible: root.state === 3

        property int editingGroup: -1
        property string editingGroupName: ""
        property var groupMembers: []
        property var groupNonMembers: []

        function _openMembership(id, name) {
            editingGroup = id
            editingGroupName = name
            engine.groupDicts(id)
        }
        function _refreshMembership() {
            if (editingGroup !== -1) {
                engine.groupDicts(editingGroup)
                engine.refreshGroups()
            }
        }
        function _createGroup() {
            const name = newGroupInput.text.trim()
            if (name.length === 0) return
            engine.createGroup(name)
            newGroupInput.text = ""
            // Keep focus + re-open the IME so the user can immediately type the
            // next group name.
            newGroupInput.forceActiveFocus()
        }

        Component.onCompleted: engine.refreshGroups()
        Connections {
            target: engine
            function onGroupsChanged() { groupsList.model = engine.groups }
            function onReadyChanged() { if (engine.ready) engine.refreshGroups() }
            function onGroupDictsReady(groupId, dicts) {
                if (groupId !== groupsPane.editingGroup) return
                const m = []
                const nm = []
                for (let i = 0; i < dicts.length; i++) {
                    if (dicts[i].member) m.push(dicts[i])
                    else nm.push(dicts[i])
                }
                groupsPane.groupMembers = m
                groupsPane.groupNonMembers = nm
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

                TextField {
                    id: newGroupInput
                    Layout.fillWidth: true
                    placeholderText: "New group name"
                    font.pixelSize: 18
                    Accessible.name: "New group name"
                    Accessible.role: Accessible.EditableText
                    onAccepted: groupsPane._createGroup()
                }
                Button {
                    text: "Create"
                    highlighted: true
                    Accessible.name: "Create"
                    Accessible.role: Accessible.Button
                    onClicked: groupsPane._createGroup()
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

                    contentItem: ColumnLayout {
                        spacing: 0
                        Label {
                            text: groupRow.groupData.name + " (" + groupRow.groupData.dictCount + ")"
                            font.pixelSize: 16
                            font.bold: true
                            Layout.fillWidth: true
                        }
                        Label {
                            text: groupRow.groupData.id === 0 ? "All dictionaries" : "id=" + groupRow.groupData.id
                            color: root.uiSubFg
                            font.pixelSize: 11
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
                            text: "Dicts"
                            visible: groupRow.groupData.id !== 0
                            Accessible.name: "Edit group dictionaries"
                            Accessible.role: Accessible.Button
                            onClicked: groupsPane._openMembership(groupRow.groupData.id, groupRow.groupData.name)
                        }
                        Menu {
                            id: groupMenu
                            Accessible.name: "Group options menu"
                            Accessible.role: Accessible.Menu
                            MenuItem {
                                text: "Rename"
                                Accessible.name: "Rename"
                                Accessible.role: Accessible.MenuItem
                                onTriggered: {
                                    const id = groupRow.groupData.id
                                    if (id !== 0) engine.renameGroup(id, groupRow.groupData.name + "_r")
                                }
                            }
                            MenuItem {
                                text: "Delete"
                                Accessible.name: "Delete"
                                Accessible.role: Accessible.MenuItem
                                onTriggered: {
                                    const id = groupRow.groupData.id
                                    if (id !== 0) engine.deleteGroup(id)
                                }
                            }
                        }
                        ToolButton {
                            text: "..."
                            visible: groupRow.groupData.id !== 0
                            Accessible.name: "Group options"
                            Accessible.role: Accessible.Button
                            onClicked: groupMenu.popup()
                        }
                    }
                }
            }
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

                Button {
                    text: "<- Back"
                    Accessible.name: "Back"
                    Accessible.role: Accessible.Button
                    onClicked: groupsPane.editingGroup = -1
                }
                Label {
                    Layout.fillWidth: true
                    text: "Group: " + groupsPane.editingGroupName
                    font.pixelSize: 16
                    font.bold: true
                    elide: Text.ElideMiddle
                }
            }

            Label { text: "In this group (" + groupsPane.groupMembers.length + ")"; color: root.uiSubFg; font.pixelSize: 13 }

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
                    Accessible.name: memberRow.rowData.name
                    Accessible.role: Accessible.ListItem

                    contentItem: Label {
                        text: memberRow.rowData.name
                        elide: Text.ElideMiddle
                        verticalAlignment: Text.AlignVCenter
                    }

                    RowLayout {
                        anchors {
                            right: parent.right
                            rightMargin: 4
                            verticalCenter: parent.verticalCenter
                        }
                        spacing: 2
                        ToolButton {
                            text: "Up"
                            enabled: memberRow.rowData.memberIndex > 0
                            Accessible.name: "Move up"
                            Accessible.role: Accessible.Button
                            onClicked: {
                                const pos = memberRow.rowData.memberIndex
                                engine.groupMoveDict(groupsPane.editingGroup, pos, pos - 1)
                                groupsPane._refreshMembership()
                            }
                        }
                        ToolButton {
                            text: "Down"
                            enabled: memberRow.rowData.memberIndex < groupsPane.groupMembers.length - 1
                            Accessible.name: "Move down"
                            Accessible.role: Accessible.Button
                            onClicked: {
                                const pos = memberRow.rowData.memberIndex
                                engine.groupMoveDict(groupsPane.editingGroup, pos, pos + 1)
                                groupsPane._refreshMembership()
                            }
                        }
                        ToolButton {
                            text: "Remove"
                            Accessible.name: "Remove from group"
                            Accessible.role: Accessible.Button
                            onClicked: {
                                engine.groupRemoveDict(groupsPane.editingGroup, memberRow.rowData.index)
                                groupsPane._refreshMembership()
                            }
                        }
                    }
                }
            }

            Label { text: "Add dictionaries"; color: root.uiSubFg; font.pixelSize: 13 }

            ListView {
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
                        text: "Add"
                        Accessible.name: "Add to group"
                        Accessible.role: Accessible.Button
                        onClicked: {
                            engine.groupAddDict(groupsPane.editingGroup, nonMemberRow.rowData.index)
                            groupsPane._refreshMembership()
                        }
                    }
                }
            }
        }
    }

    // --- article view ---
    Rectangle {
        id: articlePane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navBar.top }
        color: root.uiBg
        visible: root.state === 2

        Rectangle {
            width: parent.width
            height: 44
            color: root.uiCard
            border.color: root.uiBorder
            z: 2

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 4
                anchors.rightMargin: 4
                spacing: 4

                // 4.7: back button -> ToolButton with arrow_back icon.
                ToolButton {
                    text: root.icon("arrow_back")
                    font.family: root.iconFontFamily
                    font.pixelSize: 22
                    Accessible.name: "Back"
                    Accessible.role: Accessible.Button
                    ToolTip.visible: hovered
                    ToolTip.text: "Back"
                    onClicked: root._backFromArticle()
                }
                // 4.7: favorite star -> ToolButton, Material.primary when active.
                ToolButton {
                    property bool active: engine.favorites.indexOf(root.currentWord) >= 0
                    text: root.icon(active ? "star" : "star_border")
                    font.family: root.iconFontFamily
                    font.pixelSize: 22
                    Material.foreground: active ? Material.primary : root.uiSubFg
                    Accessible.name: active ? "Remove from favorites" : "Add to favorites"
                    Accessible.role: Accessible.Button
                    ToolTip.visible: hovered
                    ToolTip.text: active ? "Remove from favorites" : "Add to favorites"
                    onClicked: engine.toggleFavorite(root.currentWord)
                }
            }
        }

        Loader {
            id: articleLoader
            anchors { top: parent.top; topMargin: 44; left: parent.left; right: parent.right; bottom: parent.bottom }
            // Only create the full-pane WebView while the article pane is active.
            // A native Android WebView kept alive while hidden still participates
            // in the native view hierarchy and swallows touches across the whole
            // UI (it coexisted with the inline search WebView -> unusable screen).
            active: root.state === 2
            sourceComponent: articleViewComponent
            Accessible.name: "Article content"
            Accessible.role: Accessible.Group
        }
    }

    Component {
        id: articleViewComponent
        WebView {
            id: view
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
                    view.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
                    return
                }
                if (u.indexOf("gdlookup://") === 0) {
                    const word = _parseGdlookupUrl(u)
                    if (word.length > 0) {
                        _gdlookupInFlight = word
                        root._requestedWord = word
                        engine.lookup(word)
                    }
                    view.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
                    return
                }
                if (base.length > 0 && u.indexOf(base + "/gdau/") === 0) {
                    engine.playAudio(u)
                    view.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
                    return
                }
            }
            onHeightChanged: {
                if (root.state === 2 && view.height !== root.loadedAtHeight && root.currentHtml.length > 0)
                    articleReloader.restart()
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

    // --- history view ---
    Rectangle {
        id: historyPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navBar.top }
        color: root.uiBg
        visible: root.state === 5

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            // 4.5: Clear all -> flat Button (Material danger color).
            Button {
                text: "Clear all"
                flat: true
                highlighted: true
                Material.foreground: Material.color(Material.Red)
                Accessible.name: "Clear all"
                Accessible.role: Accessible.Button
                onClicked: engine.clearHistory()
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: engine.history
                spacing: 2
                Accessible.name: "Lookup history"
                Accessible.role: Accessible.List
                delegate: SwipeDelegate {
                    id: histRow
                    property string word: modelData
                    width: ListView.view.width
                    height: 48
                    text: histRow.word
                    Accessible.name: histRow.word
                    Accessible.role: Accessible.ListItem
                    // tap -> lookup
                    onClicked: { root._requestedWord = histRow.word; engine.lookup(histRow.word) }

                    // 4.5: swipe-to-remove.
                    swipe.right: Rectangle {
                        clip: true
                        color: Material.Red
                        RowLayout {
                            anchors.fill: parent
                            Button {
                                text: "Delete"
                                Material.background: Material.Red
                                Material.foreground: "white"
                                Layout.fillHeight: true
                                Layout.fillWidth: true
                                Accessible.name: "Delete"
                                Accessible.role: Accessible.Button
                                onClicked: {
                                    engine.removeHistory(histRow.word)
                                    histRow.swipe.close()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // --- favorites view ---
    Rectangle {
        id: favoritesPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navBar.top }
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
            delegate: SwipeDelegate {
                id: favRow
                property string word: modelData
                width: ListView.view.width
                height: 48
                text: favRow.word
                Accessible.name: favRow.word
                Accessible.role: Accessible.ListItem
                onClicked: { root._requestedWord = favRow.word; engine.lookup(favRow.word) }

                // 4.6: swipe-to-remove.
                swipe.right: Rectangle {
                    clip: true
                    color: Material.Red
                    RowLayout {
                        anchors.fill: parent
                        Button {
                            text: "Remove"
                            Material.background: Material.Red
                            Material.foreground: "white"
                            Layout.fillHeight: true
                            Layout.fillWidth: true
                            Accessible.name: "Remove"
                            Accessible.role: Accessible.Button
                            onClicked: {
                                engine.toggleFavorite(favRow.word)
                                favRow.swipe.close()
                            }
                        }
                    }
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
        // Dark mode flips the OPEN article in place: rewriteArticleUrls always
        // injects darkreader + a gdSetDarkMode controller, so on the toggle we
        // just call it on the live document — no re-lookup/reload, no scroll
        // reset. Runs synchronously on darkModeChanged.
        function onDarkModeChanged() { root._applyArticleDarkMode() }
    }

    Connections {
        target: engine
        function onArticleBaseUrlChanged() {
            if ((state === 2 || (state === 0 && inlineArticle)) && currentHtml.length > 0)
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
        if (state === 0 && inlineArticle && root.inlineWv) {
            loadedAtHeight = root.inlineWv.height
            root.inlineWv.loadHtml(html, base)
            return
        }
        if (state !== 2) return
        loadedAtHeight = view.height
        view.loadHtml(html, base)
    }
    // Flip the OPEN article's dark mode in place via the injected gdSetDarkMode
    // controller — instant, no reload, scroll position preserved. No article
    // open? The next rendered document gets the baked-in mode from
    // rewriteArticleUrls, so nothing to do here.
    function _applyArticleDarkMode() {
        const wv = (state === 0 && root.inlineWv) ? root.inlineWv : (state === 2 ? view : null)
        if (wv && wv.url.toString().length > 5) {
            wv.runJavaScript("try{if(window.gdSetDarkMode)gdSetDarkMode("
                + (engine.darkMode ? 1 : 0) + ");}catch(e){}")
        }
    }
    Timer {
        id: articleLinkPoller
        // 120 ms: fast enough that suggestion-dropdown taps feel instant, slow
        // enough to not hammer the WebView with runJavaScript calls.
        interval: 120
        repeat: true
        running: root.state === 2 || root.state === 0
        onTriggered: {
            // Pick the active WebView: inline in search or full article pane.
            const wv = (root.state === 0 && root.inlineWv) ? root.inlineWv : view
            if (!wv || wv.url.toString().length < 5) return
            wv.runJavaScript(
                "if(!window.__probeInstalled){"
                + "window.__tapped='';window.__suggWord='';"
                + "document.addEventListener('click',function(e){"
                + "var a=e.target.closest?e.target.closest('a'):null;"
                + "if(a&&a.id==='gd-sugg-link'){window.__suggWord=a.getAttribute('data-w');e.preventDefault();}"
                + "else{window.__tapped=(a?a.href:'');}},true);"
                + "window.__probeInstalled=true;}"
                + "var s=window.__suggWord||'';window.__suggWord='';"
                + "(s ? 'SUGG:'+s : (window.__tapped || ''))",
                function(v){
                    if (!v) return
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
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: navBar.top }
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
                spacing: 8

                TextField {
                    id: ftsInput
                    Layout.fillWidth: true
                    placeholderText: "Full-text search"
                    font.pixelSize: 18
                    enabled: !engine.buildingFts
                    Accessible.name: "Full-text search"
                    Accessible.role: Accessible.EditableText
                    onAccepted: { ftsInput.focus = false; root._runFts() }
                }
                CheckBox {
                    id: ftsWholeWords
                    text: "Whole words"
                    Layout.alignment: Qt.AlignVCenter
                    Accessible.name: "Whole words"
                    Accessible.role: Accessible.CheckBox
                }
            }

            // Group scope for full-text search. "All" (index 0) is first and
            // selected by default; choosing a group searches only that group's
            // dictionaries.
            ComboBox {
                id: ftsGroupCombo
                Layout.fillWidth: true
                model: engine.groups
                textRole: "name"
                Accessible.name: "Full-text search group scope"
                Accessible.role: Accessible.ComboBox
                // Dismiss the FTS field's IME when the dropdown opens.
                popup.onOpened: ftsInput.focus = false
                // Re-run the FTS for the newly selected group's scope.
                onActivated: (index) => {
                    if (ftsInput.text.trim().length > 0) root._runFts()
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
                    text: "Search"
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
                text: "engine error: " + engine.lastError
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
                        engine.lookupInGroup(modelData.headword, gid)
                    }
                }
            }
        }
    }

    // --- onboarding overlay (full-page Material Dialog) ---
    Dialog {
        anchors.centerIn: parent
        width: parent.width
        height: parent.height
        modal: false
        visible: !engine.onboarded
        padding: 24
        closePolicy: Popup.NoAutoClose
        Accessible.name: "Welcome"
        Accessible.role: Accessible.Dialog

        contentItem: ColumnLayout {
            anchors.fill: parent
            spacing: 16

            Label {
                Layout.fillWidth: true
                text: "Welcome to Aurelex"
                font.pixelSize: 22
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
            }
            Label {
                Layout.fillWidth: true
                Layout.fillHeight: true
                text: "Add dictionaries by tapping Add dictionaries in the Dicts tab and picking a folder with dictionary files (.mdx, .dsl, .dsl.dz, .ifo) — the folder is copied into the app once (no system-wide file access needed). Use the bottom bar to switch between Search, Dictionaries, Groups, FTS, History and Favorites."
                font.pixelSize: 15
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            Button {
                Layout.alignment: Qt.AlignHCenter
                text: "Get started"
                highlighted: true
                Accessible.name: "Get started"
                Accessible.role: Accessible.Button
                onClicked: engine.onboarded = true
            }
        }
    }
}
