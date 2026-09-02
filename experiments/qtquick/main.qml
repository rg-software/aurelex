import QtQuick
import QtWebView

// Milestone 1 (core lookup): one Window that hosts both the search view and
// the article view, switched via local state. Bare QtQuick only (no
// QtQuick.Controls2, no separate QtQuick.Window import — Window comes from
// `import QtQuick` here, as proven in the original experiment).
Window {
    id: root
    width: 480
    height: 800
    visible: true
    title: "AurelexExp"
    color: "#ececec"

    property string currentWord: ""
    property string currentHtml: ""

    // The article bridge: in this minimal build we still rely on the rewrite of
    // upstream qrc:/// to file:///android_asset/ and the engine's in-process
    // render. EngineController.rewriteArticleUrls handles it; QtWebView cannot
    // intercept custom schemes. Audio / image resources (bres://, gdau://)
    // land in the loopback HTTP server milestone (design D3).
    function _showArticle(word, html) {
        currentWord = word
        currentHtml = html
        searchPane.visible = false
        articlePane.visible = true
    }
    function _backToSearch() {
        searchPane.visible = true
        articlePane.visible = false
    }

    // --- search view ---
    Rectangle {
        id: searchPane
        anchors.fill: parent
        color: "#ececec"

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

    // --- article view ---
    Rectangle {
        id: articlePane
        anchors.fill: parent
        color: "#ececec"
        visible: false

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
                        onClicked: root._backToSearch()
                    }
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.currentWord
                    color: "white"
                    font.pixelSize: 18
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
            // For the search-pane -> article-pane flow, the inline function above
            // also runs; this is the second connection (harmless: it just re-sets
            // the same properties). Kept so the inline switch works when the QML
            // engine dispatches the signal through any one of the connections.
            root._showArticle(word, html)
        }
    }

    Component.onCompleted: {
        // engine.rewriteArticleUrls is a Q_INVOKABLE on the controller; pass
        // the rewritten HTML to the WebView when navigating to article view.
        view.loadHtml(engine.rewriteArticleUrls(currentHtml), "file:///android_asset/")

        // Experiment self-test: one-shot lookup a few seconds after start so the
        // full engine -> signal -> QML -> WebView pipeline runs without requiring
        // adb input. Remove when the experiment is no longer a smoke test.
        oneShotTimer.start()
    }

    Timer {
        id: oneShotTimer
        interval: 2500
        repeat: false
        onTriggered: engine.lookup("apple")
    }

    onCurrentHtmlChanged: {
        if (articlePane.visible) {
            view.loadHtml(engine.rewriteArticleUrls(currentHtml), "file:///android_asset/")
        }
    }
}