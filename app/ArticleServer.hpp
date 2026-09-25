#pragma once

#include <QObject>
#include <QTcpServer>
#include <QTcpSocket>
#include <QHash>
#include <QPointer>
#include <QString>
#include <QStringList>

class QTcpServer;

// ArticleServer: local loopback HTTP server for article rendering.
//
// QtWebView (unlike QtWebEngine) cannot intercept custom URL schemes
// (bres://, gdau://, gdlookup://). The design-of-record
// (openspec/changes/all-qt-ui-port/design.md D3) is to run a local HTTP server
// on 127.0.0.1 and rewrite article URLs to it. The WebView renders the same
// document; the server resolves the routes:
//   GET /<path>          -> bundled engine asset mirror (scripts/, stylesheets/,
//                           icons/, flags/, qtwebchannel/) — read from
//                           "assets:/<path>" so it works inside the APK sandbox.
//   GET /bres/<id>/<p>   -> gd_get_resource("bres://<id>/<p>")
//   GET /gdau/<id>/<p>   -> gd_get_audio("gdau://<id>/<p>")
//   GET /anything-else   -> 404
//
// baseUrl() returns the origin (e.g. "http://127.0.0.1:54321") that the article
// URL rewriter prefixes onto the upstream schemes.
//
// The server is single-threaded (runs on the QGuiApplication's main thread);
// per-request work (gd_get_*) blocks briefly but is bounded by the engine
// timeout, and one in-flight article render at a time matches the rest of the
// controller (lookups, suggests, FTS are all off-thread).
class ArticleServer : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString baseUrl READ baseUrl NOTIFY baseUrlChanged)
    Q_PROPERTY(bool running READ isRunning NOTIFY runningChanged)
public:
    explicit ArticleServer(QObject *parent = nullptr);
    ~ArticleServer() override;

    bool listen();           // bind to 127.0.0.1, random free port; emits runningChanged/baseUrlChanged on success
    void close();            // graceful shutdown; safe to call when not running
    bool isRunning() const { return m_server && m_server->isListening(); }
    QString baseUrl() const;
    quint16 port() const { return m_port; }

signals:
    void baseUrlChanged();
    void runningChanged();

private slots:
    void onIncomingConnection();

private:
    enum class Kind { Asset, Bres, Gdau };
    struct Route {
        Kind kind;
        QString suffix;
    };
    static Route classify(const QString &path);

    // The socket is held via QPointer: handle() calls into the engine
    // (gd_get_resource/gd_get_audio), which spins a nested QEventLoop while the
    // dictionary's async ResourceRequest finishes. That nested loop can run a
    // pending deleteLater() for a socket whose peer already disconnected, so a
    // raw pointer would dangle before we write the response.
    void handle(const QPointer<QTcpSocket> &socket, const QString &method, const QString &path, const QString &rawHeaders);

    static void writeReply(const QPointer<QTcpSocket> &socket, int status, const QString &statusText,
                           const QString &contentType, const QByteArray &body, qint64 bodyLengthOverride = -1);
    static void writeNotFound(const QPointer<QTcpSocket> &socket);
    static void writeBadRequest(const QPointer<QTcpSocket> &socket, const QString &reason);
    static void writeServerError(const QPointer<QTcpSocket> &socket, const QString &reason);

    QPointer<QTcpServer> m_server;
    quint16 m_port = 0;
};