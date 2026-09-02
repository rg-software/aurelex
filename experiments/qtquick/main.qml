import QtQuick
import QtWebView
import QtQuick.VirtualKeyboard

// All-Qt UI: search / dictionaries / groups / FTS / history / favorites /
// article panes switched by `state`, plus onboarding + dark mode.
// Bare QtQuick only (no Controls2 in the carve-subset install).
Window {
    id: root
    width: 480
    height: 800
    visible: true
    title: "AurelexExp"
    color: root.bg

    // 0 = search, 1 = dictionaries, 2 = article, 3 = groups, 4 = fts,
    // 5 = history, 6 = favorites.
    property int state: 0
    property string currentWord: ""
    property string currentHtml: ""
    property var ftsResults: []

    // Dark-mode-aware palette.
    property color bg: engine.darkMode ? "#222222" : "#ececec"
    property color card: engine.darkMode ? "#2e2e2e" : "white"
    property color cardBorder: engine.darkMode ? "#444444" : "#dddddd"
    property color fg: engine.darkMode ? "#eeeeee" : "black"
    property color subFg: engine.darkMode ? "#999999" : "#777777"

    // All pane switches blur the focused input BEFORE hiding its pane:
    // an IME query arriving at a focused-but-hidden item can spin the
    // Qt tab-focus-chain walker forever (ANR deadlock with the IME's
    // blocking finishComposingText on the Android main thread).
    function _showArticle(word, html) {
        currentWord = word
        currentHtml = html
        _blurActive()
        state = 2
        // Deferred load: loading while the keyboard-hide resize is in flight
        // can leave the Chromium surface blank; wait for it to settle.
        articleLoadTimer.restart()
    }
    function _blurActive() {
        if (root.activeFocusItem && root.activeFocusItem.forceActiveFocus === undefined) return
        // Move active focus to the root window item (no activeFocusOnTab items
        // remain in the chain while inputs are blurred).
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
        // Wildcards is the only mode that works reliably (regex is broken
        // upstream; plain == wildcard search without wildcards).
        engine.ftsSearch(ftsInput.text, 2, engine.activeGroupId)
    }

    Component.onCompleted: console.log("[qml] root ready, state:", state)

    Connections {
        target: engine
        function onFtsSearchReady(query, results) {
            if (query !== ftsInput.text) return
            ftsResults = results
        }
    }

    // --- shared top bar ---
    Rectangle {
        id: topBar
        width: parent.width
        height: 44
        color: "#222222"
        z: 5

        Row {
            anchors.fill: parent
            anchors.leftMargin: 12
            spacing: 12

            // Cycle button: search -> dicts -> groups -> fts -> hist -> favs -> search.
            Rectangle {
                width: 90
                height: 30
                anchors.verticalCenter: parent.verticalCenter
                color: "#3a3a3a"
                Text {
                    anchors.centerIn: parent
                    color: "white"
                    font.pixelSize: 13
                    text: root.state === 0 ? "Dicts"
                        : root.state === 1 ? "Groups"
                        : root.state === 3 ? "FTS"
                        : root.state === 4 ? "Hist"
                        : root.state === 5 ? "Favs"
                        : root.state === 6 ? "<- Search"
                        : "Dicts"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (root.state === 0) root._openDicts()
                        else if (root.state === 1) root._openGroups()
                        else if (root.state === 3) root._openFts()
                        else if (root.state === 4) root._openHistory()
                        else if (root.state === 5) root._openFavorites()
                        else root.state = 0
                    }
                }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                color: "white"
                font.pixelSize: 16
                text: root.state === 0 ? "Search"
                    : root.state === 1 ? "Dictionaries (" + engine.dictCount + ")"
                    : root.state === 3 ? "Groups (" + engine.groups.length + ", active=" + engine.activeGroupId + ")"
                    : root.state === 4 ? "FTS (" + root.ftsResults.length + ")"
                    : root.state === 5 ? "History (" + engine.history.length + ")"
                    : root.state === 6 ? "Favorites (" + engine.favorites.length + ")"
                    : root.currentWord
            }

            Rectangle {
                width: 32
                height: 30
                anchors.verticalCenter: parent.verticalCenter
                color: "#3a3a3a"
                Text {
                    anchors.centerIn: parent
                    color: engine.darkMode ? "gold" : "white"
                    font.pixelSize: 14
                    text: "D"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: engine.darkMode = !engine.darkMode
                }
            }
        }
    }

    // --- search view ---
    Rectangle {
        id: searchPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: root.bg
        visible: root.state === 0

        function _doSuggest() {
            if (input.text.trim().length === 0) {
                suggestionList.model = []
                return
            }
            engine.suggest(input.text)
        }

        Connections {
            target: engine
            function onSuggestionsReady(prefix, suggestions) {
                console.log("[qml] suggestionsReady", prefix, "count:", suggestions.length)
                // No prefix check here: the C++ side drops stale generations,
                // and Gboard's composing/autocorrect can rewrite input.text
                // after the suggest fired (the old filter rejected valid
                // results, leaving the list stale).
                suggestionList.model = suggestions
                suggestionList.forceLayout()
                suggestionList.positionViewAtBeginning()
            }
            function onArticleNotFound(word) {
                suggestionList.model = ["(no results for " + word + ")"]
            }
        }

        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 8

            Rectangle {
                width: parent.width
                height: 48
                color: root.card
                border.color: root.cardBorder

                TextInput {
                    id: input
                    // ImhNoPredictiveText reduces IME composing side effects;
                    // activeFocusOnTab=false keeps the tab-focus chain empty so
                    // IME queries never walk it (infinite-loop ANR, see _blurActive).
                    activeFocusOnTab: false
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    verticalAlignment: TextInput.AlignVCenter
                    font.pixelSize: 18
                    color: root.fg
                    onTextChanged: { console.log("[qml] textChanged:", text); debounce.restart() }
                    onAccepted: { focus = false; engine.lookup(text.trim()) }
                    Component.onCompleted: forceActiveFocus()
                }
            }

            Row {
                spacing: 8
                Rectangle {
                    width: 120
                    height: 32
                    color: "#3a3a3a"
                    Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 13; text: "Clipb2" }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            const t = engine.clipboardText()
                            if (t.length > 0) engine.lookup(t)
                        }
                    }
                }
                Rectangle {
                    width: 80
                    height: 32
                    color: "#224488"
                    Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 13; text: "SUG" }
                    MouseArea { anchors.fill: parent; onClicked: engine.suggest("app") }
                }
            }

            Timer {
                id: debounce
                interval: 250
                onTriggered: { console.log("[qml] debounce fired, text:", input.text); searchPane._doSuggest() }
            }

            Text {
                visible: engine.lastError.length > 0
                text: "engine error: " + engine.lastError
                color: "red"
                wrapMode: Text.Wrap
                width: parent.width
            }

            ListView {
                id: suggestionList
                width: parent.width
                height: parent.height - 100
                clip: true
                model: []
                delegate: Rectangle {
                    width: ListView.view.width
                    height: 40
                    color: root.card
                    Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; text: modelData; color: root.fg; font.pixelSize: 16 }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: engine.lookup(modelData)
                    }
                }
            }
        }
    }

    // --- dictionaries view ---
    Rectangle {
        id: dictsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: root.bg
        visible: root.state === 1

        Component.onCompleted: engine.refreshDictionaries()
        // Refresh the storage-access state while the pane is visible (the grant
        // happens in the system Settings; bindings can't see it change).
        property bool storageGranted: engine.isAllFilesAccessGranted()
        Timer {
            interval: 1000
            repeat: true
            running: root.state === 1
            onTriggered: dictsPane.storageGranted = engine.isAllFilesAccessGranted()
        }
        Connections {
            target: engine
            function onDictionariesChanged() { dictsList.model = engine.dictionaries }
            function onReadyChanged() { if (engine.ready) engine.refreshDictionaries() }
        }

        Column {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            Rectangle {
                width: 120
                height: 32
                color: "#3a3a3a"
                Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 13; text: "Rescan" }
                MouseArea { anchors.fill: parent; onClicked: engine.rescan() }
            }

            Rectangle {
                visible: !dictsPane.storageGranted
                width: parent.width
                height: 44
                color: "#224488"
                Text {
                    anchors.centerIn: parent
                    color: "white"; font.pixelSize: 13
                    text: "Add dictionaries: grant storage access"
                }
                MouseArea { anchors.fill: parent; onClicked: engine.openAllFilesAccessSettings() }
            }

            Text {
                visible: dictsPane.storageGranted
                color: root.subFg
                font.pixelSize: 12
                wrapMode: Text.Wrap
                width: parent.width
                text: "Storage access granted. Copy dictionary files (.mdx, .dsl, .dsl.dz, .ifo) into the GoldenDict folder on the device storage, then tap Rescan."
            }

            ListView {
                id: dictsList
                width: parent.width
                height: parent.height - 40
                clip: true
                model: engine.dictionaries
                spacing: 6
                delegate: Rectangle {
                    id: dictRow
                    // Capture the outer ListView's model roles: the inner button
                    // Repeater shadows `index`/`modelData`.
                    property int dictIndex: index
                    property var dictData: modelData
                    width: ListView.view.width
                    height: 56
                    color: root.card
                    border.color: root.cardBorder
                    Column {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 2
                        Text { text: dictRow.dictData.name; color: root.fg; font.pixelSize: 16; font.bold: true }
                        Text { text: dictRow.dictData.source; color: root.subFg; font.pixelSize: 12; elide: Text.ElideMiddle; width: parent.width }
                        Row {
                            spacing: 8
                            height: 28
                            Repeater {
                                model: [
                                    { label: "Up",   delta: -1 },
                                    { label: "Down", delta:  1 },
                                    { label: "Index", delta: -2 },
                                    { label: "Remove", delta: 0 }
                                ]
                                delegate: Rectangle {
                                    width: 76
                                    height: 28
                                    color: modelData.label === "Remove" ? "#882222"
                                        : modelData.label === "Index" ? "#224488" : "#3a3a3a"
                                    Text { anchors.centerIn: parent; text: modelData.label; color: "white"; font.pixelSize: 12 }
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: {
                                            const idx = dictRow.dictIndex
                                            const op = modelData.label
                                            if (op === "Remove") {
                                                engine.removeDictionary(idx)
                                            } else if (op === "Index") {
                                                engine.ftsIndex(idx)
                                            } else {
                                                const target = Math.max(0, Math.min(engine.dictionaries.length - 1, idx + modelData.delta))
                                                if (target !== idx) engine.moveDictionary(idx, target)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // --- groups view ---
    Rectangle {
        id: groupsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: root.bg
        visible: root.state === 3

        Component.onCompleted: engine.refreshGroups()
        Connections {
            target: engine
            function onGroupsChanged() { groupsList.model = engine.groups }
            function onReadyChanged() { if (engine.ready) engine.refreshGroups() }
        }

        Column {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            Rectangle {
                width: parent.width
                height: 48
                color: root.card
                border.color: root.cardBorder

                TextInput {
                    id: newGroupInput
                    activeFocusOnTab: false
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    verticalAlignment: TextInput.AlignVCenter
                    font.pixelSize: 18
                    color: root.fg
                    onAccepted: {
                        if (text.trim().length > 0) {
                            engine.createGroup(text.trim())
                            text = ""
                        }
                    }
                }
            }

            ListView {
                id: groupsList
                width: parent.width
                height: parent.height - 56
                clip: true
                model: engine.groups
                spacing: 6
                delegate: Rectangle {
                    id: groupRow
                    // Capture the outer ListView's model roles: the inner button
                    // Repeater shadows `index`/`modelData`.
                    property var groupData: modelData
                    width: ListView.view.width
                    height: 48
                    color: groupRow.groupData.id === engine.activeGroupId ? "#224422" : root.card
                    border.color: root.cardBorder
                    Row {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 280
                            spacing: 0
                            Text {
                                text: groupRow.groupData.name + " (" + groupRow.groupData.dictCount + ")"
                                color: groupRow.groupData.id === engine.activeGroupId ? "white" : root.fg
                                font.pixelSize: 16; font.bold: true
                            }
                            Text { text: "id=" + groupRow.groupData.id; color: root.subFg; font.pixelSize: 11 }
                        }

                        Repeater {
                            model: [
                                { label: "Active", op: "activate" },
                                { label: "Rename", op: "rename" },
                                { label: "Delete", op: "delete" }
                            ]
                            delegate: Rectangle {
                                width: 80
                                height: 28
                                color: modelData.op === "delete" ? "#882222"
                                    : modelData.op === "activate" ? "#224488" : "#3a3a3a"
                                Text { anchors.centerIn: parent; text: modelData.label; color: "white"; font.pixelSize: 12 }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        const id = groupRow.groupData.id
                                        const op = modelData.op
                                        if (op === "activate") engine.setActiveGroup(id)
                                        else if (op === "rename") engine.renameGroup(id, groupRow.groupData.name + "_r")
                                        else if (op === "delete") engine.deleteGroup(id)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // --- article view ---
    Rectangle {
        id: articlePane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: root.bg
        visible: root.state === 2

        Rectangle {
            width: parent.width
            height: 44
            color: "#333333"
            z: 2

            Row {
                anchors.fill: parent
                anchors.leftMargin: 8
                spacing: 8

                Rectangle {
                    width: 80
                    height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#555555"
                    Text { anchors.centerIn: parent; text: "<- Back"; color: "white"; font.pixelSize: 14 }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.state = 0
                    }
                }

                Rectangle {
                    width: 40
                    height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#3a3a3a"
                    Text { anchors.centerIn: parent; color: engine.favorites.indexOf(root.currentWord) >= 0 ? "gold" : "#cccccc"; font.pixelSize: 18; text: "*" }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: engine.toggleFavorite(root.currentWord)
                    }
                }
            }
        }

        WebView {
            id: view
            anchors { top: parent.top; topMargin: 44; left: parent.left; right: parent.right; bottom: parent.bottom }
            onLoadingChanged: console.log("WebView loading:", loading, "url:", url)
            onHeightChanged: {
                if (root.state === 2 && view.height !== root.loadedAtHeight && root.currentHtml.length > 0)
                    articleReloader.restart()
            }
        }
    }

    // --- history view ---
    Rectangle {
        id: historyPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: root.bg
        visible: root.state === 5

        Column {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            Rectangle {
                width: 120
                height: 32
                color: "#882222"
                Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 13; text: "Clear all" }
                MouseArea { anchors.fill: parent; onClicked: engine.clearHistory() }
            }

            ListView {
                width: parent.width
                height: parent.height - 40
                clip: true
                model: engine.history
                spacing: 4
                delegate: Rectangle {
                    id: histRow
                    property string word: modelData
                    width: ListView.view.width
                    height: 44
                    color: root.card
                    border.color: root.cardBorder
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left; anchors.leftMargin: 12
                        text: histRow.word; color: root.fg; font.pixelSize: 16
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: engine.lookup(histRow.word)
                    }
                    Rectangle {
                        width: 40; height: 32
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right; anchors.rightMargin: 8
                        color: "#882222"
                        Text { anchors.centerIn: parent; color: "white"; text: "X" }
                        MouseArea { anchors.fill: parent; onClicked: engine.removeHistory(histRow.word) }
                    }
                }
            }
        }
    }

    // --- favorites view ---
    Rectangle {
        id: favoritesPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: root.bg
        visible: root.state === 6

        ListView {
            anchors.fill: parent
            anchors.margins: 12
            clip: true
            model: engine.favorites
            spacing: 4
            delegate: Rectangle {
                id: favRow
                property string word: modelData
                width: ListView.view.width
                height: 44
                color: root.card
                border.color: root.cardBorder
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left; anchors.leftMargin: 12
                    text: favRow.word; color: root.fg; font.pixelSize: 16
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: engine.lookup(favRow.word)
                }
                Rectangle {
                    width: 40; height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right; anchors.rightMargin: 8
                    color: "#882222"
                    Text { anchors.centerIn: parent; color: "white"; text: "X" }
                    MouseArea { anchors.fill: parent; onClicked: engine.toggleFavorite(favRow.word) }
                }
            }
        }
    }

    Connections {
        target: engine
        function onArticleLoaded(word, html) {
            root._showArticle(word, html)
        }
    }

    Timer {
        id: articleLoadTimer
        interval: 400
        onTriggered: root._loadArticleNow()
    }
    Timer {
        id: articleReloader
        interval: 200
        onTriggered: root._loadArticleNow()
    }
    // Height of the WebView at the time of the last load; a mismatch means the
    // window was resized (keyboard hide/show, rotation) after the load started
    // — Chromium silently starves loads during a surface resize, leaving a
    // blank page — so we re-load once the size settles.
    property real loadedAtHeight: 0
    function _loadArticleNow() {
        if (state !== 2) return
        loadedAtHeight = view.height
        view.loadHtml(engine.rewriteArticleUrls(currentHtml), "file:///android_asset/")
    }

    // Incoming lookups (share / PROCESS_TEXT / deep link / QS tile) are consumed
    // by the EngineController's poller — see pollPendingLookup in C++.

    // --- FTS view ---
    Rectangle {
        id: ftsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: root.bg
        visible: root.state === 4

        Connections {
            target: engine
            function onBuildingFtsChanged() { ftsInput.enabled = !engine.buildingFts; ftsSearchBtn.enabled = !engine.buildingFts }
        }

        Column {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            Row {
                spacing: 8
                height: 48
                width: parent.width

                Rectangle {
                    width: parent.width - 110
                    height: 48
                    color: root.card
                    border.color: root.cardBorder
                    TextInput {
                        id: ftsInput
                        activeFocusOnTab: false
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        verticalAlignment: TextInput.AlignVCenter
                        font.pixelSize: 18
                        color: root.fg
                        onAccepted: { focus = false; root._runFts() }
                    }
                }

                Rectangle {
                    width: 90
                    height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#3a3a3a"
                    Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 14; text: "Wild*" }
                }
            }

            Row {
                spacing: 8
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: engine.buildingFts
                    color: root.subFg
                    font.pixelSize: 13
                    text: "Indexing..."
                }
                Rectangle {
                    id: ftsSearchBtn
                    width: 100
                    height: 32
                    color: ftsSearchBtn.enabled ? "#224488" : "#555555"
                    Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 14; text: "Search" }
                    MouseArea {
                        anchors.fill: parent
                        enabled: ftsSearchBtn.enabled
                        onClicked: root._runFts()
                    }
                }
            }

            Text {
                visible: engine.lastError.length > 0
                text: "engine error: " + engine.lastError
                color: "red"
                wrapMode: Text.Wrap
                width: parent.width
            }

            ListView {
                width: parent.width
                height: parent.height - 96 - 32
                clip: true
                model: root.ftsResults
                spacing: 4
                delegate: Rectangle {
                    width: ListView.view.width
                    height: 44
                    color: root.card
                    border.color: root.cardBorder
                    Row {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 16
                            spacing: 0
                            Text { text: modelData.headword; color: root.fg; font.pixelSize: 16; font.bold: true }
                            Text { text: modelData.dictName; color: root.subFg; font.pixelSize: 11 }
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: engine.lookup(modelData.headword)
                    }
                }
            }
        }
    }

    // --- virtual keyboard (Qt Quick VirtualKeyboard) ---
    // The system IME (SwiftKey/Gboard) proved unreliable with Qt 6.6 on this
    // device: composing text reverted instantly, IME deadlocks, inactive
    // input connections. The embedded keyboard bypasses the system IME
    // entirely for Qt fields.
    InputPanel {
        id: inputPanel
        z: 99
        x: 0
        y: root.height
        width: root.width
        visible: Qt.inputMethod.visible

        states: State {
            name: "visible"
            when: inputPanel.visible
            PropertyChanges { target: inputPanel; y: root.height - inputPanel.height }
        }
        transitions: Transition {
            from: ""
            to: "visible"
            reversible: true
            ParallelAnimation {
                NumberAnimation { properties: "y"; duration: 250; easing.type: Easing.InOutQuad }
            }
        }
    }

    // --- onboarding overlay ---
    Rectangle {
        anchors.fill: parent
        z: 100
        visible: !engine.onboarded
        color: "#222222"

        Column {
            anchors.centerIn: parent
            spacing: 16
            width: parent.width - 48

            Text {
                text: "Welcome to Aurelex"
                color: "white"
                font.pixelSize: 22
                font.bold: true
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
            }
            Text {
                text: "Add dictionaries by copying supported files (.mdx, .dsl, .dsl.dz, .ifo) into the app's data folder, then open Dicts and tap Rescan. Use the top-left button to switch between Search, Dictionaries, Groups, FTS, History and Favorites."
                color: "#cccccc"
                font.pixelSize: 15
                wrapMode: Text.Wrap
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
            }
            Rectangle {
                width: 200
                height: 44
                anchors.horizontalCenter: parent.horizontalCenter
                color: "#224488"
                Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 16; text: "Get started" }
                MouseArea { anchors.fill: parent; onClicked: engine.onboarded = true }
            }
        }
    }
}
