#pragma once

#include <QAtomicInt>
#include <QByteArray>
#include <QList>
#include <QMutex>
#include <QObject>
#include <QPointer>
#include <QSet>
#include <QString>
#include <QStringList>
#include <QTcpServer>
#include <QTcpSocket>
#include <QThread>
#include <QWaitCondition>

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
// THREADING. The server object lives on the QGuiApplication's main thread,
// which accepts connections and writes replies. Engine resolution does NOT run
// there: gd_get_resource/gd_get_audio spin a nested QEventLoop internally, and
// running that on the main thread let it redeliver QML events — when a Loader
// binding flipped mid-request and destroyed the article WebView, the next
// signal dispatch walked freed QML data and killed the app (SIGSEGV in
// QQmlData::isSignalConnected, 2026-09-27). Resolution is therefore handed to a
// small pool of ResourceSlot threads, which own no QObject the main thread can
// mutate, so the same nested loop is harmless there. The main thread only
// enqueues and never blocks. See openspec/changes/fix-article-server-gui-reentrancy.
//
// Asset routes are plain file reads that never touch the engine, so they stay
// inline on the main thread.
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
    void drainCompleted();

private:
    enum class Kind { Asset, Bres, Gdau };
    struct Route {
        Kind kind;
        QString suffix;
    };
    static Route classify(const QString &path);

    // Per-connection request state, parented to the socket so its lifetime is
    // exactly the socket's: when the socket is deleted (on disconnect, or as a
    // child at teardown) the Connection goes with it. The previous code
    // heap-allocated a QByteArray + bool per socket and freed them from the
    // `disconnected` lambda; a socket destroyed without emitting `disconnected`
    // leaked both, and the readyRead lambda captured them raw. This removes that
    // class of leak.
    //
    // A slot thread never dereferences a Connection. It carries the pointer only
    // as an identity token; the main thread checks membership in
    // m_liveConnections before using it. That is what keeps an abandoned
    // request from touching freed memory when the socket dies mid-flight.
    class Connection : public QObject
    {
    public:
        explicit Connection(QTcpSocket *sock) : QObject(sock), socket(sock) {}

        QTcpSocket *socket = nullptr;   // the parent; valid for this object's whole life
        QByteArray buf;                 // partial request header block
        bool headersParsed = false;
        bool cancelled = false;         // client went away; see design.md D3

        bool alive() const { return !cancelled && socket && socket->state() == QAbstractSocket::ConnectedState; }
        void cancel() { cancelled = true; }
    };

    // One pool slot. A real QThread, not a QThreadPool worker: a pool worker has
    // no Qt event dispatcher, and the boundary's nested QEventLoop cannot run
    // without one.
    class ResourceSlot;

    struct ResourceJob {
        Connection *conn = nullptr;   // identity token only; never dereferenced off the main thread
        Kind kind = Kind::Bres;
        QString engineUrl;
        bool headOnly = false;
    };

    // Outcome of a finished engine call, travelling slot -> main thread. Owned by
    // m_completed and deleted by the main thread (or at teardown), so nothing
    // leaks if the connection dies or the server shuts down first.
    struct Delivery {
        Connection *conn = nullptr;
        Kind kind = Kind::Bres;
        QString engineUrl;
        bool headOnly = false;
        int rc = -1;
        QByteArray body;
    };

    void handle(Connection *conn, const QString &method, const QString &pathIn, const QString &rawHeaders);
    void submitResource(Connection *conn, Kind kind, const QString &engineUrl, bool headOnly);
    void deliverResourceResult(Delivery *d);   // takes ownership of d

    static void writeReply(Connection *conn, int status, const QString &statusText,
                           const QString &contentType, const QByteArray &body, qint64 bodyLengthOverride = -1);
    static void writeNotFound(Connection *conn);
    static void writeBadRequest(Connection *conn, const QString &reason);
    static void writeServerError(Connection *conn, const QString &reason);

    void startSlots();
    void stopSlots();
    ResourceJob *takeNextJob();       // slot threads only; blocks until a job or stop

    QPointer<QTcpServer> m_server;
    quint16 m_port = 0;

    QMutex m_queueMutex;
    QWaitCondition m_queueReady;
    QList<ResourceJob *> m_queue;     // jobs waiting for a slot (main -> slot)
    QList<Delivery *> m_completed;    // results waiting for the main thread (slot -> main)
    QList<ResourceSlot *> m_slots;
    bool m_stopping = false;

    // Live connections, touched only on the main thread. A completed job is
    // dropped unless its connection is still in here, which is how an abandoned
    // request is discarded without ever dereferencing a dead pointer.
    QSet<Connection *> m_liveConnections;

    // Jobs enqueued but not yet finished by a slot. Bumped on the main thread in
    // submitResource(), dropped by the slot after the engine call returns (or by
    // stopSlots() for a job dropped at shutdown), so stopSlots() can assert the
    // join actually drained everything.
    QAtomicInt m_inFlight;

    // Live ArticleServer instances. The app never calls gd_cleanup() (only the
    // smoke tool does), so there is no in-process engine teardown to order
    // against today. If a future change adds one, it MUST run after every
    // ArticleServer is destroyed — that is what this counter is here to make
    // assertable at that call site, because a slot thread calling gd_get_resource
    // against a destroyed g_state is the failure this guards.
    static QAtomicInt s_liveInstances;
};
