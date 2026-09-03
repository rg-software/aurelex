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
    title: "AurelexExp"

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

    // Material icon font family (registered from fonts.qrc in main.cpp) + the
    // icon-name -> codepoint helper (qt-material-ui task 7.2).
    property string iconFontFamily: "Material Icons"
    function icon( name ) {
        var map = {
            "search": 0xe8b6,
            "library_books": 0xe254,
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
        // Single v1 mode: Wildcards (FTS::SearchMode=2). See full-text-search.
        engine.ftsSearch(ftsInput.text, 2, engine.activeGroupId)
    }
    // Navigation labels/icons for the bottom TabBar.
    property var navItems: [
        { idx: 0, label: "Search",   icon: "search" },
        { idx: 1, label: "Dicts",    icon: "library_books" },
        { idx: 3, label: "Groups",   icon: "folder" },
        { idx: 4, label: "FTS",      icon: "history" },
        { idx: 5, label: "History",  icon: "history" },
        { idx: 6, label: "Favs",     icon: "star" }
    ]
    function _navTo(idx) {
        if (idx === 0) { _blurActive(); state = 0; return }
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
                    : root.state === 3 ? "Groups (" + engine.groups.length + ", active=" + engine.activeGroupId + ")"
                    : root.state === 4 ? "FTS (" + root.ftsResults.length + ")"
                    : root.state === 5 ? "History (" + engine.history.length + ")"
                    : root.state === 6 ? "Favorites (" + engine.favorites.length + ")"
                    : root.currentWord
            }

            ToolButton {
                // Manual dark override D toggle. When following system it forces
                // dark; when forcing dark it returns to following the system theme.
                property string _name: "dark_mode"
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
                        font.pixelSize: 11
                        color: tabBtn.down || tabBtn.checked ? tabBtn.Material.accentColor
                                                             : tabBtn.Material.foreground
                    }
                }
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
                searchPane.pendingSuggestions = suggestions
                suggestApplyTimer.restart()
            }
            function onArticleNotFound(word) {
                suggestionList.model = ["(no results for " + word + ")"]
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                TextField {
                    id: input
                    Layout.fillWidth: true
                    placeholderText: "Search dictionaries"
                    font.pixelSize: 18
                    onDisplayTextChanged: debounce.restart()
                    onAccepted: { input.focus = false; engine.lookup(text.trim()) }
                    Component.onCompleted: forceActiveFocus()
                }

                Button {
                    text: "Clipboard"
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

            Label {
                Layout.fillWidth: true
                visible: engine.lastError.length > 0
                text: "engine error: " + engine.lastError
                color: Material.color(Material.Red)
                wrapMode: Text.Wrap
            }

            ListView {
                id: suggestionList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: []
                delegate: ItemDelegate {
                    width: ListView.view.width
                    height: 44
                    text: modelData
                    onClicked: engine.lookup(modelData)
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
        function _requestRemove(index, name) { removeIndex = index; removeName = name }
        function _confirmRemove() {
            const idx = removeIndex
            if (idx >= 0) engine.removeDictionary(idx)
            removeIndex = -1
            removeName = ""
        }
        function _cancelRemove() { removeIndex = -1; removeName = "" }
        Connections {
            target: engine
            function onDictionariesChanged() { dictsList.model = engine.dictionaries }
            function onReadyChanged() { if (engine.ready) engine.refreshDictionaries() }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    text: "Rescan"
                    onClicked: engine.rescan()
                }
                // 8.2: "Add dictionaries" (folder-scoped SAF picker). Qt 6.6
                // RoundButton stands in for the Material 3 FloatingActionButton.
                RoundButton {
                    text: "Add dictionaries"
                    highlighted: true
                    onClicked: engine.addDictionaryFolder()
                }
            }

            Label {
                Layout.fillWidth: true
                text: engine.sources.length > 0 ? "Sources" : ""
                color: root.uiSubFg
                font.pixelSize: 13
                visible: engine.sources.length > 0
            }

            ListView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(engine.sources.length, 3) * 44
                visible: engine.sources.length > 0
                clip: true
                model: engine.sources
                spacing: 2
                delegate: ItemDelegate {
                    id: srcRow
                    property var srcIndex: index
                    property var srcData: modelData
                    width: ListView.view.width
                    height: 44
                    padding: 4

                    contentItem: ColumnLayout {
                        spacing: 0
                        Label {
                            text: srcRow.srcData.orig && srcRow.srcData.orig.length > 0
                                  ? srcRow.srcData.orig
                                  : srcRow.srcData.path
                            font.pixelSize: 13
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }
                        Label {
                            text: srcRow.srcData.staged ? "(staged into app storage)" : "folder"
                            color: root.uiSubFg
                            font.pixelSize: 10
                        }
                    }

                    ToolButton {
                        anchors {
                            right: parent.right
                            rightMargin: 4
                            verticalCenter: parent.verticalCenter
                        }
                        text: "Remove"
                        onClicked: engine.removeSource(srcRow.srcIndex)
                    }
                }
            }

            Label {
                Layout.fillWidth: true
                color: root.uiSubFg
                font.pixelSize: 12
                wrapMode: Text.Wrap
                text: "Tap Add dictionaries to pick a folder containing dictionary files (.mdx, .dsl, .dsl.dz, .ifo). The folder stays accessible via a scoped grant; no system-wide storage access is needed."
            }

            ListView {
                id: dictsList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: engine.dictionaries
                spacing: 2
                delegate: ItemDelegate {
                    id: dictRow
                    property int dictIndex: index
                    property var dictData: modelData
                    width: ListView.view.width
                    height: 76
                    padding: 8

                    contentItem: ColumnLayout {
                        spacing: 2
                        Label {
                            text: dictRow.dictData.name
                            font.pixelSize: 16
                            font.bold: true
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }
                        Label {
                            text: dictRow.dictData.source
                            color: root.uiSubFg
                            font.pixelSize: 12
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }
                    }

                    // 4.2: Up/Down/Index/Remove as ToolButtons in a RowLayout.
                    RowLayout {
                        anchors {
                            right: parent.right
                            rightMargin: 4
                            verticalCenter: parent.verticalCenter
                        }
                        spacing: 2
                        visible: dictRow.hovered || true

                        ToolButton {
                            text: "Up"
                            onClicked: {
                                const idx = dictRow.dictIndex
                                const target = Math.max(0, idx - 1)
                                if (target !== idx) engine.moveDictionary(idx, target)
                            }
                        }
                        ToolButton {
                            text: "Down"
                            onClicked: {
                                const idx = dictRow.dictIndex
                                const target = Math.min(engine.dictionaries.length - 1, idx + 1)
                                if (target !== idx) engine.moveDictionary(idx, target)
                            }
                        }
                        ToolButton {
                            text: "Index"
                            onClicked: engine.ftsIndex(dictRow.dictIndex)
                        }
                        ToolButton {
                            text: "Remove"
                            onClicked: dictsPane._requestRemove(dictRow.dictIndex, dictRow.dictData.name)
                        }
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
                    text: "It will be unloaded from the app. The file stays on disk."
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

            TextField {
                id: newGroupInput
                Layout.fillWidth: true
                placeholderText: "New group name"
                font.pixelSize: 18
                onAccepted: {
                    if (text.trim().length > 0) {
                        engine.createGroup(text.trim())
                        text = ""
                    }
                }
            }

            ListView {
                id: groupsList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: engine.groups
                spacing: 2
                delegate: ItemDelegate {
                    id: groupRow
                    property var groupData: modelData
                    width: ListView.view.width
                    height: 56
                    padding: 4

                    // 4.3: active-group highlight via Material.primary.
                    highlighted: groupRow.groupData.id === engine.activeGroupId

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
                            text: "Active"
                            visible: groupRow.groupData.id !== engine.activeGroupId
                            enabled: groupRow.groupData.id !== 0
                            onClicked: engine.setActiveGroup(groupRow.groupData.id)
                        }
                        ToolButton {
                            text: "Dicts"
                            visible: groupRow.groupData.id !== 0
                            onClicked: groupsPane._openMembership(groupRow.groupData.id, groupRow.groupData.name)
                        }
                        Menu {
                            id: groupMenu
                            MenuItem {
                                text: "Rename"
                                onTriggered: {
                                    const id = groupRow.groupData.id
                                    if (id !== 0) engine.renameGroup(id, groupRow.groupData.name + "_r")
                                }
                            }
                            MenuItem {
                                text: "Delete"
                                onTriggered: {
                                    const id = groupRow.groupData.id
                                    if (id !== 0) engine.deleteGroup(id)
                                }
                            }
                        }
                        ToolButton {
                            text: "..."
                            visible: groupRow.groupData.id !== 0
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
                delegate: ItemDelegate {
                    id: memberRow
                    property var rowData: modelData
                    width: ListView.view.width
                    height: 44
                    padding: 4

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
                            onClicked: {
                                const pos = memberRow.rowData.memberIndex
                                engine.groupMoveDict(groupsPane.editingGroup, pos, pos - 1)
                                groupsPane._refreshMembership()
                            }
                        }
                        ToolButton {
                            text: "Down"
                            enabled: memberRow.rowData.memberIndex < groupsPane.groupMembers.length - 1
                            onClicked: {
                                const pos = memberRow.rowData.memberIndex
                                engine.groupMoveDict(groupsPane.editingGroup, pos, pos + 1)
                                groupsPane._refreshMembership()
                            }
                        }
                        ToolButton {
                            text: "Remove"
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
                delegate: ItemDelegate {
                    id: nonMemberRow
                    property var rowData: modelData
                    width: ListView.view.width
                    height: 44
                    padding: 4

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
                    ToolTip.visible: hovered
                    ToolTip.text: active ? "Remove from favorites" : "Add to favorites"
                    onClicked: engine.toggleFavorite(root.currentWord)
                }
            }
        }

        Loader {
            id: articleLoader
            anchors { top: parent.top; topMargin: 44; left: parent.left; right: parent.right; bottom: parent.bottom }
            // Only create the WebView while the article pane is active, so the
            // QtWebView native Android view never overlays the other panes.
            active: root.state === 2
            visible: root.state === 2
            sourceComponent: articleViewComponent
        }
    }

    Component {
        id: articleViewComponent
        WebView {
            id: view
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
                onClicked: engine.clearHistory()
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: engine.history
                spacing: 2
                delegate: SwipeDelegate {
                    id: histRow
                    property string word: modelData
                    width: ListView.view.width
                    height: 48
                    text: histRow.word
                    // tap -> lookup
                    onClicked: engine.lookup(histRow.word)

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
            delegate: SwipeDelegate {
                id: favRow
                property string word: modelData
                width: ListView.view.width
                height: 48
                text: favRow.word
                onClicked: engine.lookup(favRow.word)

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
    property real loadedAtHeight: 0
    function _loadArticleNow() {
        if (state !== 2) return
        loadedAtHeight = view.height
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
                    placeholderText: "Full-text query (supports * wildcards)"
                    font.pixelSize: 18
                    enabled: !engine.buildingFts
                    onAccepted: { ftsInput.focus = false; root._runFts() }
                }
                // 4.4: single search mode. Wildcards (FTS::SearchMode=2) is the
                // mode that parses `read*`-style prefixes and matches a plain
                // term exactly; Xapian-syntax/Plain/Regexp were cut for v1 (see
                // full-text-search spec — Wildcards subsumes plain matching).
            }

            // 8.1: index-build progress bar.
            ProgressBar {
                Layout.fillWidth: true
                visible: engine.buildingFts
                indeterminate: true
            }
            Label {
                Layout.fillWidth: true
                visible: engine.buildingFts
                color: root.uiSubFg
                font.pixelSize: 13
                text: "Indexing..."
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    id: ftsSearchBtn
                    text: "Search"
                    highlighted: true
                    enabled: !engine.buildingFts
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
                delegate: ItemDelegate {
                    width: ListView.view.width
                    height: 52
                    padding: 8
                    contentItem: ColumnLayout {
                        spacing: 0
                        Label { text: modelData.headword; font.pixelSize: 16; font.bold: true }
                        Label { text: modelData.dictName; color: root.uiSubFg; font.pixelSize: 11 }
                    }
                    onClicked: engine.lookup(modelData.headword)
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
                text: "Add dictionaries by tapping Add dictionaries in the Dicts tab and picking a folder with dictionary files (.mdx, .dsl, .dsl.dz, .ifo) — the app keeps that folder saved via a scoped grant (no system-wide file access needed). Use the bottom bar to switch between Search, Dictionaries, Groups, FTS, History and Favorites."
                font.pixelSize: 15
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            Button {
                Layout.alignment: Qt.AlignHCenter
                text: "Get started"
                highlighted: true
                onClicked: engine.onboarded = true
            }
        }
    }
}
