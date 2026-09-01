import QtQuick
import QtWebView

// Minimal all-Qt window: a single article rendered in-process via QtWebView.
// Gate 1/2 probe — engine + QML + WebView in one process, no HWUI clash.
Window {
    width: 480
    height: 800
    visible: true
    title: "Aurelex QtQuick Experiment"
    color: "#ececec"

    Rectangle {
        width: parent.width
        height: 44
        color: "#333333"
        z: 2
        Text {
            anchors.centerIn: parent
            text: "Aurelex exp — apple"
            color: "white"
            font.pixelSize: 16
        }
    }

    WebView {
        id: view
        anchors { top: parent.top; topMargin: 44; left: parent.left; right: parent.right; bottom: parent.bottom }
        onLoadingChanged: console.log("WebView loading:", loading, "url:", url)
        onLoadProgressChanged: console.log("WebView progress:", loadProgress)
    }

    Component.onCompleted: {
        console.log("QML ready; articleHtml length:", String(articleHtml).length)
        view.loadHtml(articleHtml, articleBase)
    }
}