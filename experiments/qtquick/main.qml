import QtQuick
import QtWebView

// Milestone 3 (groups): a fourth pane (Groups) joins the cycle
// search -> dictionaries -> groups -> search. Bare QtQuick only.
Window {
    id: root
    width: 480
    height: 800
    visible: true
    title: "AurelexExp"
    color: "#ececec"

    // 0 = search, 1 = dictionaries, 2 = article, 3 = groups, 4 = fts.
    property int state: 0
    property string currentWord: ""
    property string currentHtml: ""
    property int ftsMode: 0
    property var ftsResults: []

    function _showArticle(word, html) {
        currentWord = word
        currentHtml = html
        state = 2
    }
    function _backToSearch() {
        state = 0
    }
    function _openDicts() {
        engine.refreshDictionaries()
        state = 1
    }
    function _openGroups() {
        engine.refreshGroups()
        state = 3
    }
    function _openFts() {
        ftsResults = []
        state = 4
    }
    function _runFts() {
        engine.ftsSearch(ftsInput.text, ftsMode, engine.activeGroupId)
    }

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

            // Cycle button: search -> dicts -> groups -> fts -> search.
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
                        : root.state === 4 ? "<- Search"
                        : "Dicts"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (root.state === 0) root._openDicts()
                        else if (root.state === 1) root._openGroups()
                        else if (root.state === 3) root._openFts()
                        else if (root.state === 4) root.state = 0
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
                    : root.currentWord
            }
        }
    }

    // --- search view ---
    Rectangle {
        id: searchPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: "#ececec"
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
                if (prefix !== input.text) return
                suggestionList.model = suggestions
            }
            function onArticleLoaded(word, html) {
                root._showArticle(word, html)
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
                color: "white"
                border.color: "#cccccc"

                TextInput {
                    id: input
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    verticalAlignment: TextInput.AlignVCenter
                    font.pixelSize: 18
                    onTextChanged: debounce.restart()
                    onAccepted: engine.lookup(text.trim())
                    Component.onCompleted: forceActiveFocus()
                }
            }

            Timer {
                id: debounce
                interval: 250
                onTriggered: searchPane._doSuggest()
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
                height: parent.height - 56
                clip: true
                model: []
                delegate: Rectangle {
                    width: ListView.view.width
                    height: 40
                    color: "white"
                    Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; text: modelData; color: "black"; font.pixelSize: 16 }
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
        color: "#ececec"
        visible: root.state === 1

        Component.onCompleted: engine.refreshDictionaries()
        Connections {
            target: engine
            function onDictionariesChanged() { dictsList.model = engine.dictionaries }
            function onReadyChanged() { if (engine.ready) engine.refreshDictionaries() }
        }

        ListView {
            id: dictsList
            anchors.fill: parent
            anchors.margins: 12
            clip: true
            model: engine.dictionaries
            spacing: 6
            delegate: Rectangle {
                width: ListView.view.width
                height: 56
                color: "white"
                border.color: "#dddddd"
                Column {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 2
                    Text { text: modelData.name; color: "black"; font.pixelSize: 16; font.bold: true }
                    Text { text: modelData.source; color: "#777"; font.pixelSize: 12; elide: Text.ElideMiddle; width: parent.width }
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
                                        const idx = index
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

    // --- groups view ---
    Rectangle {
        id: groupsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: "#ececec"
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
                color: "white"
                border.color: "#cccccc"

                TextInput {
                    id: newGroupInput
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    verticalAlignment: TextInput.AlignVCenter
                    font.pixelSize: 18
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
                    width: ListView.view.width
                    height: 48
                    color: modelData.id === engine.activeGroupId ? "#224422" : "white"
                    border.color: "#dddddd"
                    Row {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 280
                            spacing: 0
                            Text { text: modelData.name + " (" + modelData.dictCount + ")"; color: "white"; font.pixelSize: 16; font.bold: true }
                            Text { text: "id=" + modelData.id; color: "#cccccc"; font.pixelSize: 11 }
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
                                        const id = modelData.id
                                        const op = modelData.op
                                        if (op === "activate") engine.setActiveGroup(id)
                                        else if (op === "rename") {
                                            // Quick rename: append "_r" for demonstration; a real
                                            // UI would use a dialog. For the experiment gate, the
                                            // round-trip is what matters.
                                            engine.renameGroup(id, modelData.name + "_r")
                                        } else if (op === "delete") engine.deleteGroup(id)
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
        color: "#ececec"
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
        }
    }

    Connections {
        target: engine
        function onArticleLoaded(word, html) {
            root._showArticle(word, html)
        }
        // Experiment smoke test for FTS: when the dictionary list is ready, build
        // the FTS index for every loaded dict, then run a body-word search for
        // "app" and log the result. Lets us verify the FTS pipeline end-to-end
        // on-device without tapping through the UI. This block can be removed once
        // the QML UI is interactive enough to drive directly.
        function onDictionariesChanged() {
            if (!engine.ready) return
            if (engine.dictCount === 0) return
            if (ftsSmokeArmed === false) return
            ftsSmokeArmed = false
            for (let i = 0; i < engine.dictCount; ++i) engine.ftsIndex(i)
            ftsBuildWaitTimer.start()
        }
    }

    property bool ftsSmokeArmed: true

    Timer {
        id: ftsBuildWaitTimer
        interval: 500
        repeat: true
        onTriggered: {
            if (engine.buildingFts) return
            ftsBuildWaitTimer.stop()
            const r = engine.ftsSearch("apple", 0, 0)
            if (r && r.length > 0) console.log("[smoke] ftsSearch sync returned", r.length)
        }
    }

    Connections {
        target: engine
        function onFtsSearchReady(query, results) {
            console.log("[smoke] ftsSearchReady query='" + query + "' results=" + results.length)
            for (let i = 0; i < results.length; ++i) {
                console.log("  " + results[i].headword + " (" + results[i].dictName + ")")
            }
        }
    }

    Component.onCompleted: {
        const pending = engine.readPendingLookup()
        if (pending && pending.length > 0) {
            console.log('[aurelex] pending lookup:', pending)
            engine.lookup(pending)
        }
    }

    onCurrentHtmlChanged: {
        if (state === 2) {
            view.loadHtml(engine.rewriteArticleUrls(currentHtml), "file:///android_asset/")
        }
    }
    
    // --- FTS view ---
    Rectangle {
        id: ftsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: "#ececec"
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
                    color: "white"
                    border.color: "#cccccc"
                    TextInput {
                        id: ftsInput
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        verticalAlignment: TextInput.AlignVCenter
                        font.pixelSize: 18
                        onAccepted: root._runFts()
                    }
                }

                Rectangle {
                    width: 90
                    height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#3a3a3a"
                    Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 14; text: root.ftsMode === 0 ? "Xapian" : root.ftsMode === 1 ? "Plain" : root.ftsMode === 2 ? "Wild*" : "Regex" }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.ftsMode = (root.ftsMode + 1) % 4
                    }
                }
            }

            Rectangle {
                id: ftsSearchBtn
                width: 100
                height: 32
                color: "#224488"
                Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 14; text: "Search" }
                MouseArea {
                    anchors.fill: parent
                    onClicked: root._runFts()
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
                    color: "white"
                    border.color: "#dddddd"
                    Row {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 16
                            spacing: 0
                            Text { text: modelData.headword; color: "black"; font.pixelSize: 16; font.bold: true }
                            Text { text: modelData.dictName; color: "#777"; font.pixelSize: 11 }
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
}
