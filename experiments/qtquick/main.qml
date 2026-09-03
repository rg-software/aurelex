import QtQuick
import QtWebView

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
    // Back-stack for in-article navigation. Each entry is a {word, html} pair
    // so the Back button can pop to the previous article without losing scroll
    // position (we re-render the prior article's HTML).
    property var navStack: []

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
        if (currentWord !== "" && currentWord !== word) {
            navStack.push({ word: currentWord, html: currentHtml })
        }
        currentWord = word
        currentHtml = html
        _blurActive()
        state = 2
        // Deferred load: loading while the keyboard-hide resize is in flight
        // can leave the Chromium surface blank; wait for it to settle.
        articleLoadTimer.restart()
    }
    function _backFromArticle() {
        if (navStack.length === 0) {
            state = 0
            return
        }
        const prev = navStack.pop()
        currentWord = prev.word
        currentHtml = prev.html
        state = 2
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
            // displayText = committed text + IME preedit: during SwiftKey/
            // Gboard composition, `text` is empty while the word lives in the
            // preedit — suggesting on `text` alone misses typing entirely.
            const t = input.displayText
            if (t.trim().length === 0) {
                suggestionList.model = []
                return
            }
            engine.suggest(t)
        }

        property var pendingSuggestions: []
        Timer {
            id: suggestApplyTimer
            interval: 60
            onTriggered: {
                suggestionList.model = searchPane.pendingSuggestions
                suggestionList.forceLayout()
                suggestionList.positionViewAtBeginning()
            }
        }

        Connections {
            target: engine
            function onSuggestionsReady(prefix, suggestions) {
                    // No prefix check here: the C++ side drops stale generations,
                // and the IME can rewrite the preedit after the suggest fired.
                // NOTE: qualify explicitly — an unqualified write inside a
                // Connections handler resolves to a GLOBAL (silently failing,
                // "Invalid write to global property").
                // Apply DEFERRED (60ms): assigning the model synchronously
                // inside the IME's composition event storm leaves the ListView
                // visually stale (Qt Quick frame starvation, same family as
                // the blank WebView bug).
                searchPane.pendingSuggestions = suggestions
                suggestApplyTimer.restart()
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
                    // ImhHiddenText: the IME treats the field as password-style
                    // and commits keys directly (no composing/extracted-text
                    // monitoring) — the mechanism that breaks on Qt 6.6 +
                    // Android 15. The field still echoes normal text.
                    activeFocusOnTab: false
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    verticalAlignment: TextInput.AlignVCenter
                    font.pixelSize: 18
                    color: root.fg
                    // Trigger on displayText (= text + IME preedit): during
                    // composition `text` is empty while the word lives in the
                    // preedit, so textChanged alone misses typing.
                    onDisplayTextChanged: debounce.restart()
                    onAccepted: { focus = false; engine.lookup(text.trim()) }
                    Component.onCompleted: forceActiveFocus()
                }
            }

            Rectangle {
                width: 120
                height: 32
                color: "#3a3a3a"
                Text { anchors.centerIn: parent; color: "white"; font.pixelSize: 13; text: "Clipboard" }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        const t = engine.clipboardText()
                        if (t.length > 0) engine.lookup(t)
                    }
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
        property int removeIndex: -1
        property string removeName: ""
        function _requestRemove(index, name) { removeIndex = index; removeName = name }
        function _confirmRemove() {
            const idx = removeIndex
            if (idx >= 0) engine.removeDictionary(idx)
            removeIndex = -1
            removeName = ""
        }
        function _cancelRemove() { removeIndex = -1; removeName = "" }
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
                                                dictsPane._requestRemove(idx, dictRow.dictData.name)
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

        // --- remove-dictionary confirm dialog ---
        Rectangle {
            visible: dictsPane.removeIndex >= 0
            anchors.fill: parent
            color: "#80000000"
            z: 10

            Rectangle {
                anchors.centerIn: parent
                width: parent.width - 80
                height: 170
                color: root.card
                border.color: root.cardBorder

                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    Text {
                        width: parent.width
                        color: root.fg
                        font.pixelSize: 16
                        wrapMode: Text.Wrap
                        text: "Remove dictionary \"" + (dictsPane.removeName !== "" ? dictsPane.removeName : "(unknown)") + "\"?"
                    }
                    Text {
                        width: parent.width
                        color: root.subFg
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                        text: "It will be unloaded from the app. The file stays on disk."
                    }

                    Row {
                        spacing: 12
                        anchors.horizontalCenter: parent.horizontalCenter
                        Rectangle {
                            width: 120; height: 36
                            color: "#3a3a3a"
                            Text { anchors.centerIn: parent; text: "Cancel"; color: "white"; font.pixelSize: 14 }
                            MouseArea { anchors.fill: parent; onClicked: dictsPane._cancelRemove() }
                        }
                        Rectangle {
                            width: 120; height: 36
                            color: "#882222"
                            Text { anchors.centerIn: parent; text: "Remove"; color: "white"; font.pixelSize: 14 }
                            MouseArea { anchors.fill: parent; onClicked: dictsPane._confirmRemove() }
                        }
                    }
                }
            }
        }
    }
    Rectangle {
        id: groupsPane
        anchors { top: topBar.bottom; left: parent.left; right: parent.right; bottom: parent.bottom }
        color: root.bg
        visible: root.state === 3

        // Membership editor state. editingGroup === -1 shows the group list;
        // otherwise the group's dict membership editor is shown.
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
        Column {
            visible: groupsPane.editingGroup === -1
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
                            width: parent.width - 470
                            spacing: 0
                            Text {
                                text: groupRow.groupData.name + " (" + groupRow.groupData.dictCount + ")"
                                color: groupRow.groupData.id === engine.activeGroupId ? "white" : root.fg
                                font.pixelSize: 16; font.bold: true
                            }
                            Text { text: "id=" + groupRow.groupData.id; color: root.subFg; font.pixelSize: 11 }
                        }

                        Rectangle {
                            width: 70
                            height: 28
                            anchors.verticalCenter: parent.verticalCenter
                            visible: groupRow.groupData.id !== 0
                            color: "#3a3a3a"
                            Text { anchors.centerIn: parent; text: "Dicts"; color: "white"; font.pixelSize: 12 }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: groupsPane._openMembership(groupRow.groupData.id, groupRow.groupData.name)
                            }
                        }

                        Repeater {
                            model: [
                                { label: "Active", op: "activate" },
                                { label: "Rename", op: "rename" },
                                { label: "Delete", op: "delete" }
                            ]
                            delegate: Rectangle {
                                width: 70
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

        // --- membership editor mode ---
        Column {
            visible: groupsPane.editingGroup !== -1
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            Row {
                spacing: 10
                height: 36
                width: parent.width

                Rectangle {
                    width: 80
                    height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#555555"
                    Text { anchors.centerIn: parent; text: "<- Back"; color: "white"; font.pixelSize: 13 }
                    MouseArea { anchors.fill: parent; onClicked: groupsPane.editingGroup = -1 }
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.fg
                    font.pixelSize: 16; font.bold: true
                    text: "Group: " + groupsPane.editingGroupName
                }
            }

            Text { text: "In this group (" + groupsPane.groupMembers.length + ")"; color: root.subFg; font.pixelSize: 13 }

            ListView {
                id: memberList
                width: parent.width
                height: 190
                clip: true
                model: groupsPane.groupMembers
                spacing: 4
                delegate: Rectangle {
                    id: memberRow
                    property var rowData: modelData
                    width: ListView.view.width
                    height: 40
                    color: root.card
                    border.color: root.cardBorder
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left; anchors.leftMargin: 10
                        width: parent.width - 250
                        elide: Text.ElideMiddle
                        text: memberRow.rowData.name; color: root.fg; font.pixelSize: 14
                    }
                    Row {
                        anchors.right: parent.right; anchors.rightMargin: 6
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 6
                        Repeater {
                            model: ["Up", "Down", "Remove"]
                            delegate: Rectangle {
                                width: 70; height: 28
                                color: modelData === "Remove" ? "#882222" : "#3a3a3a"
                                Text { anchors.centerIn: parent; text: modelData; color: "white"; font.pixelSize: 12 }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        const pos = memberRow.rowData.memberIndex
                                        const op = modelData
                                        if (op === "Up" && pos > 0) engine.groupMoveDict(groupsPane.editingGroup, pos, pos - 1)
                                        else if (op === "Down" && pos < groupsPane.groupMembers.length - 1) engine.groupMoveDict(groupsPane.editingGroup, pos, pos + 1)
                                        else if (op === "Remove") engine.groupRemoveDict(groupsPane.editingGroup, memberRow.rowData.index)
                                        groupsPane._refreshMembership()
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Text { text: "Add dictionaries"; color: root.subFg; font.pixelSize: 13 }

            ListView {
                width: parent.width
                height: parent.height - 36 - 190 - 60
                clip: true
                model: groupsPane.groupNonMembers
                spacing: 4
                delegate: Rectangle {
                    id: nonMemberRow
                    property var rowData: modelData
                    width: ListView.view.width
                    height: 40
                    color: root.card
                    border.color: root.cardBorder
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left; anchors.leftMargin: 10
                        width: parent.width - 100
                        elide: Text.ElideMiddle
                        text: nonMemberRow.rowData.name; color: root.fg; font.pixelSize: 14
                    }
                    Rectangle {
                        width: 70; height: 28
                        anchors.right: parent.right; anchors.rightMargin: 6
                        anchors.verticalCenter: parent.verticalCenter
                        color: "#224488"
                        Text { anchors.centerIn: parent; text: "Add"; color: "white"; font.pixelSize: 12 }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                engine.groupAddDict(groupsPane.editingGroup, nonMemberRow.rowData.index)
                                groupsPane._refreshMembership()
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
                        onClicked: root._backFromArticle()
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
            // In-article gdlookup:// interception. QtWebView 6.6 has no
            // navigationRequested; onUrlChanged fires after the WebView has
            // already started navigating to the link. We (a) parse the word,
            // (b) call engine.lookup(), and (c) rewind the WebView with a
            // loadHtml(about:blank) so the user does not see a "page not
            // found" frame before the new article lands. The new article's
            // articleLoaded handler then sets state=2 and re-loads.
            onUrlChanged: {
                const u = url.toString()
                const base = engine.articleBaseUrl
                if (base.length > 0 && u.indexOf(base + "/gdlookup/") === 0) {
                    const word = _parseGdlookupHttpUrl(u, base)
                    if (word.length > 0) {
                        _gdlookupInFlight = word
                        engine.lookup(word)
                    }
                    view.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
                    return
                }
                if (u.indexOf("gdlookup://") === 0) {
                    const word = _parseGdlookupUrl(u)
                    if (word.length > 0) {
                        _gdlookupInFlight = word
                        engine.lookup(word)
                    }
                    view.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
                    return
                }
                if (base.length > 0 && u.indexOf(base + "/gdau/") === 0) {
                    // Audio anchor: the ArticleServer serves the wav over
                    // loopback. Play via Android MediaPlayer (in-app) instead of
                    // navigating the WebView away from the article.
                    engine.playAudio(u)
                    view.loadHtml("<html><body></body></html>", engine.articleBaseUrl)
                    return
                }
                console.log("WebView url:", u)
            }
            onLoadingChanged: console.log("WebView loading:", loading, "url:", url)
            onHeightChanged: {
                if (root.state === 2 && view.height !== root.loadedAtHeight && root.currentHtml.length > 0)
                    articleReloader.restart()
            }
        }
    }

    // Parse the upstream gdlookup URL into a word we can pass back into
    // engine.lookup(). The engine emits two forms (engine/src/article_netmgr.cc):
    //   gdlookup://localhost/<word>          (path-based)
    //   gdlookup://localhost/?word=<w>&...   (query-based, after netmgr rewrite)
    // We also see gdlookup://localhost (the welcome/empty page) — return "".
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
    // Tracks the in-flight lookup triggered by a gdlookup click so we don't
    // re-trigger on the resulting onUrlChanged for the about:blank rewind.
    property string _gdlookupInFlight: ""

    // Parse the loopback-rewritten form of a gdlookup link. rewriteArticleUrls
    // maps gdlookup://localhost/<word> to http://127.0.0.1:PORT/gdlookup/<word>
    // and gdlookup://localhost/?word=x&group=... to .../gdlookup/?word=x&group=...
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

    Connections {
        target: engine
        function onArticleBaseUrlChanged() {
            if (state === 2 && currentHtml.length > 0)
                _loadArticleNow()
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
        // Base URL must be the loopback origin so relative URLs in the article
        // (and the engine's rewritten qrc:/// / bres:// / gdau://) resolve via
        // the ArticleServer. Pass an empty base to use the default; the WebView
        // resolves relative URLs against the loaded HTML's origin.
        view.loadHtml(engine.rewriteArticleUrls(currentHtml),
                      engine.articleBaseUrl.length > 0 ? engine.articleBaseUrl + "/" : "")
    }
    Timer {
        id: articleLinkPoller
        interval: 400
        repeat: true
        running: root.state === 2
        onTriggered: {
            if (view.url.toString().length < 5) return
            // QtWebView 6.6 on Android swallows anchor navigation (onUrlChanged
            // never fires for in-page link clicks). Instead, poll a click
            // listener injected into the article: it records the last anchor's
            // href, which we read here and dispatch for gdau:// (audio) and
            // gdlookup:// (in-app lookup). This is the loopback bridge for
            // QtWebView — see all-qt-ui-port design D3.
            view.runJavaScript(
                "if(!window.__probeInstalled){"
                + "window.__tapped='';"
                + "document.addEventListener('click',function(e){"
                + "var a=e.target.closest?e.target.closest('a'):null;"
                + "window.__tapped=(a?a.href:'');},true);"
                + "window.__probeInstalled=true;}"
                + "(window.__tapped || '')",
                function(v){
                    if (v && v !== articleLinkPoller._prev) {
                        articleLinkPoller._prev = v
                        _handleArticleLink(v)
                    }
                })
        }
        property string _prev: ""
    }

    // Dispatch an in-article anchor href. Links come in two flavors:
    //   http://127.0.0.1:PORT/gdau/<dictId>/<file>   -> play audio
    //   http://127.0.0.1:PORT/gdlookup/<word>        -> in-app lookup
    // (rewriteArticleUrls rewrites gdau:// and gdlookup://localhost/ to these.)
    function _handleArticleLink(link) {
        const base = engine.articleBaseUrl
        if (base.length < 5) return
        if (link.indexOf(base + "/gdau/") === 0) {
            engine.playAudio(link)
            return
        }
        if (link.indexOf(base + "/gdlookup/") === 0) {
            const word = _parseGdlookupHttpUrl(link, base)
            if (word.length > 0) engine.lookup(word)
            return
        }
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
