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
// and without JS errors.
//
// IMPORTANT: window.articleview must be a real (stub) object, not undefined.
// gd-builtin.js attaches click handlers that call articleview.* methods; when
// articleview is undefined those handlers throw, and Chromium's event handling
// then cancels the DEFAULT anchor navigation (so gdlookup:// and gdau:// links
// never navigate to the loopback URL for QtWebView's onUrlChanged to see).
// With stub methods present the handlers return cleanly and the browser follows
// the href as normal.
window.QWebChannel = window.QWebChannel || function (transport, callback) {
    if (typeof callback === "function") {
        callback({
            objects: {
                articleview: window.__aurelexArticleViewStub || {
                    onJsActiveArticleChanged: function () {},
                    linkClickedInHtml: function () {},
                    collapseInHtml: function () {},
                    newArticleView: function () {},
                    scrollTo: function () {},
                    getActiveArticleId: function () { return ""; },
                    onCopyText: function () {},
                    onPronounceText: function () {},
                    onLookupWord: function () {},
                    onOpenLink: function () {}
                }
            }
        });
    }
};

window.qt = window.qt || {
    webChannelTransport: null
};
