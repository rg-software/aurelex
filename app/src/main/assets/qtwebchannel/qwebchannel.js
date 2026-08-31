// Aurelex qwebchannel.js shim (design D9).
//
// The upstream article header unconditionally runs:
//   new QWebChannel(qt.webChannelTransport, function(channel) {
//     window.articleview = channel.objects.articleview;
//   });
//
// On desktop that bridge carries in-page articleview interactions (copy,
// pronounce, scroll) that the Android Kotlin UI replaces. Article *content*
// rendering never depended on the live bridge, so a no-op shim that defines
// QWebChannel/qt lets the unchanged upstream header run without a C++ bridge
// and without JS errors. A real bridge can be mounted later if a (b)-list
// feature needs it; none in v1 does.
window.QWebChannel = window.QWebChannel || function (transport, callback) {
    if (typeof callback === "function") {
        callback({ objects: {} });
    }
};

window.qt = window.qt || {
    webChannelTransport: null
};