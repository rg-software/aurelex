#include "ArticleServer.hpp"

#include <QDebug>
#include <QFile>
#include <QHostAddress>
#include <QMimeDatabase>
#include <QMimeType>
#include <QMutexLocker>
#include <QNetworkProxy>
#include <QScopedPointer>
#include <QTcpServer>
#include <QTcpSocket>

#include <vector>

extern "C" {
#include "goldendict.h"
}

namespace {

constexpr int kMaxResourceBytes = 4 * 1024 * 1024; // matches JNI buffer (gd_boundary.cc:90)
constexpr int kRequestHeaderCap = 64 * 1024;        // 64 KiB; request headers are tiny

// Two slots, deliberately (design.md D1). This is a fault-isolation count, not
// a throughput one: reads are local and tiny, so a single slot would drain a
// typical article in single-digit milliseconds. The second slot exists so a
// request that wedges cannot gate every other resource, which is the cascade the
// 2026-09-27 logcat showed. Raise only against measured saturation.
constexpr int kResourceSlotCount = 2;

} // namespace

// ---------------------------------------------------------------------------
// ResourceSlot: one pool thread.
//
// run() pulls jobs off the shared queue. For the duration of each job the
// boundary's gd_get_resource/gd_get_audio spin their own nested QEventLoop on
// *this* thread, which is what supplies the event dispatcher they need; this is
// the same shape the task-1.1 gate proved works from a foreign QThread identity.
// This slot owns no QObject the GUI thread can mutate, so that nested loop can
// never redeliver QML events (the crash in the class comment).
// ---------------------------------------------------------------------------
class ArticleServer::ResourceSlot : public QThread
{
public:
    explicit ResourceSlot(ArticleServer *owner) : owner_(owner) {}

protected:
    void run() override {
        while (true) {
            ResourceJob *job = owner_->takeNextJob();
            if (!job) break; // stop requested and queue drained
            runJob(job);
            delete job;
        }
    }

private:
    void runJob(ResourceJob *job) {
        // This thread never touches the Connection. It might already be gone
        // (the client can disconnect while the engine runs), so the pointer is
        // carried as an opaque identity token and validated by the main thread
        // in drainCompleted(). Touching it here would be a use-after-free.
        std::vector<char> buf(kMaxResourceBytes);
        int (*fn)(const char *, char *, int) =
            (job->kind == Kind::Bres) ? &gd_get_resource : &gd_get_audio;
        const int rc = fn(job->engineUrl.toUtf8().constData(), buf.data(),
                          static_cast<int>(buf.size()));

        auto *d = new Delivery;
        d->conn = job->conn;
        d->kind = job->kind;
        d->engineUrl = job->engineUrl;
        d->headOnly = job->headOnly;
        d->rc = rc;
        if (rc > 0) d->body = QByteArray(buf.data(), rc);

        {
            QMutexLocker lock(&owner_->m_queueMutex);
            owner_->m_completed.append(d);
        }
        owner_->m_inFlight.deref();
        // Wake the main thread. Posting to the server itself (not the
        // connection) is what makes this safe: the server outlives every job,
        // and a queued call to a destroyed server is simply dropped by Qt.
        QMetaObject::invokeMethod(owner_, &ArticleServer::drainCompleted, Qt::QueuedConnection);
    }

    ArticleServer *owner_;
};

QAtomicInt ArticleServer::s_liveInstances;

ArticleServer::ArticleServer(QObject *parent) : QObject(parent) {
    s_liveInstances.ref();
}

ArticleServer::~ArticleServer() {
    stopSlots();
    close();
    s_liveInstances.deref();
}

void ArticleServer::startSlots() {
    if (!m_slots.isEmpty()) return;
    m_stopping = false;
    m_slots.reserve(kResourceSlotCount);
    for (int i = 0; i < kResourceSlotCount; ++i) {
        auto *slot = new ResourceSlot(this);
        slot->start();
        m_slots.append(slot);
    }
}

void ArticleServer::stopSlots() {
    if (m_slots.isEmpty()) return;
    {
        QMutexLocker lock(&m_queueMutex);
        m_stopping = true;
    }
    m_queueReady.wakeAll();
    // Join before returning: the engine may still be alive here, but the caller
    // tears it down right after, and a late gd_* return would then race a
    // destroyed g_state (design.md Risks). A slot mid-job finishes its current
    // (bounded) request before its run() re-checks m_stopping.
    for (auto *slot : m_slots) {
        slot->wait();
        delete slot;
    }
    m_slots.clear();
    // Anything still queued never ran, so no connection is referenced by a
    // result. Drop the jobs themselves and keep the in-flight count honest so
    // the assertion below holds.
    for (auto *job : m_queue) {
        m_inFlight.deref();
        delete job;
    }
    m_queue.clear();
    // Results that finished after the last drain but whose drainCompleted was
    // never delivered (the server is going away). Nothing will read them now.
    qDeleteAll(m_completed);
    m_completed.clear();
    // The join must have drained every enqueued job: no slot thread is left
    // holding a reference that could outlive us. In debug builds this catches a
    // stopSlots() that returns before the workers are actually done.
    Q_ASSERT(m_inFlight.loadAcquire() == 0);
}

ArticleServer::ResourceJob *ArticleServer::takeNextJob() {
    QMutexLocker lock(&m_queueMutex);
    while (m_queue.isEmpty() && !m_stopping)
        m_queueReady.wait(&m_queueMutex);
    if (m_queue.isEmpty()) return nullptr; // stopping
    return m_queue.takeFirst();
}

bool ArticleServer::listen() {
    if (isRunning()) return true;
    auto *server = new QTcpServer(this);
    server->setProxy(QNetworkProxy::NoProxy); // explicit: no env-inherited proxy on Android
    if (!server->listen(QHostAddress::LocalHost)) {
        qWarning() << "[article-server] listen() failed:" << server->errorString();
        delete server;
        return false;
    }
    m_server = server;
    m_port = server->serverPort();
    connect(server, &QTcpServer::newConnection, this, &ArticleServer::onIncomingConnection);
    startSlots();
    qInfo() << "[article-server] listening on" << baseUrl();
    emit runningChanged();
    emit baseUrlChanged();
    return true;
}

void ArticleServer::close() {
    if (!m_server) return;
    m_server->close();
    m_server->deleteLater();
    m_server = nullptr;
    m_port = 0;
    emit runningChanged();
    emit baseUrlChanged();
}

QString ArticleServer::baseUrl() const {
    if (!isRunning()) return QString();
    return QStringLiteral("http://127.0.0.1:%1").arg(m_port);
}

void ArticleServer::onIncomingConnection() {
    if (!m_server) return;
    while (auto *sock = m_server->nextPendingConnection()) {
        // Single-shot small read: collect headers up to the blank line, dispatch.
        // The engine routes are GET/HEAD only and carry no body.
        sock->setReadBufferSize(kRequestHeaderCap);
        // Connection is parented to the socket, so its lifetime is the socket's
        // and it cannot leak when a socket dies without emitting `disconnected`.
        auto *conn = new Connection(sock);
        m_liveConnections.insert(conn);
        // `destroyed` fires on this (the main) thread, so the set stays
        // single-threaded. The slot threads only ever compare against it.
        connect(conn, &QObject::destroyed, this, [this, conn]() { m_liveConnections.remove(conn); });
        connect(sock, &QTcpSocket::readyRead, conn, [this, conn]() {
            if (conn->headersParsed) {
                // Drain anything past the header block; we don't accept bodies
                // on the article routes.
                conn->socket->readAll();
                return;
            }
            if (conn->cancelled) return;
            conn->buf.append(conn->socket->readAll());
            const int headerEnd = conn->buf.indexOf("\r\n\r\n");
            if (headerEnd < 0) {
                if (conn->buf.size() > kRequestHeaderCap) {
                    writeBadRequest(conn, QStringLiteral("headers too large"));
                    conn->socket->disconnectFromHost();
                }
                return;
            }
            conn->headersParsed = true;
            const QString headerBlock = QString::fromUtf8(conn->buf.mid(0, headerEnd));
            const QStringList lines = headerBlock.split(QStringLiteral("\r\n"), Qt::SkipEmptyParts);
            if (lines.isEmpty()) {
                writeBadRequest(conn, QStringLiteral("empty request"));
                conn->socket->disconnectFromHost();
                return;
            }
            const QStringList requestLine = lines.first().split(QChar(' '));
            if (requestLine.size() < 2) {
                writeBadRequest(conn, QStringLiteral("malformed request line"));
                conn->socket->disconnectFromHost();
                return;
            }
            handle(conn, requestLine.at(0), requestLine.at(1), headerBlock);
        });
        connect(sock, &QTcpSocket::disconnected, conn, [conn]() {
            conn->cancel();
            // Delete the socket, and with it the Connection (its child). Deferred
            // because we are inside the socket's own signal emission.
            conn->socket->deleteLater();
        });
    }
}

ArticleServer::Route ArticleServer::classify(const QString &pathIn) {
    const int q = pathIn.indexOf(QChar('?'));
    const QString path = (q < 0) ? pathIn : pathIn.left(q);
    if (path.startsWith(QStringLiteral("/bres/"))) {
        return { Kind::Bres, path.mid(QStringLiteral("/bres/").size()) };
    }
    if (path.startsWith(QStringLiteral("/gdau/"))) {
        return { Kind::Gdau, path.mid(QStringLiteral("/gdau/").size()) };
    }
    QString suffix = path;
    if (suffix.startsWith(QChar('/'))) suffix = suffix.mid(1);
    return { Kind::Asset, suffix };
}

void ArticleServer::handle(Connection *conn, const QString &method, const QString &pathIn, const QString &rawHeaders) {
    Q_UNUSED(rawHeaders);
    if (!conn || !conn->alive()) return;
    if (method != QStringLiteral("GET") && method != QStringLiteral("HEAD")) {
        writeBadRequest(conn, QStringLiteral("method %1 not allowed").arg(method));
        conn->socket->disconnectFromHost();
        return;
    }

    const Route route = classify(pathIn);

    if (route.kind == Kind::Asset) {
        if (route.suffix.isEmpty() || route.suffix.contains("..")) {
            writeBadRequest(conn, QStringLiteral("invalid asset path"));
            conn->socket->disconnectFromHost();
            return;
        }
        // Mirror the shipped app's qrc:// -> assets resolution. The qrc URLs the
        // engine emits are qrc:///scripts/..., /qtwebchannel/..., /icons/...,
        // /flags/..., and bare article-style*.css.
        QString rel = route.suffix;
        if (rel.endsWith(QStringLiteral(".css"), Qt::CaseInsensitive) && !rel.contains(QChar('/')))
            rel = QStringLiteral("stylesheets/") + rel;
        const QStringList candidates = {
            QStringLiteral("assets:/%1").arg(rel),
            QStringLiteral("assets:/stylesheets/%1").arg(rel),
        };
        QByteArray body;
        for (const QString &candidate : candidates) {
            QFile f(candidate);
            if (f.exists() && f.open(QIODevice::ReadOnly)) {
                body = f.readAll();
                f.close();
                break;
            }
        }
        if (body.isEmpty()) {
            qWarning() << "[article-server] asset 404:" << rel;
            writeNotFound(conn);
            conn->socket->disconnectFromHost();
            return;
        }
        QMimeDatabase db;
        const QMimeType mt = db.mimeTypeForFileNameAndData(rel, body);
        writeReply(conn, 200, QStringLiteral("OK"), mt.name(), body,
                   method == QStringLiteral("HEAD") ? 0 : -1);
        conn->socket->disconnectFromHost();
        return;
    }

    const QString schemePrefix =
        (route.kind == Kind::Bres) ? QStringLiteral("bres://") : QStringLiteral("gdau://");
    submitResource(conn, route.kind, schemePrefix + route.suffix, method == QStringLiteral("HEAD"));
}

void ArticleServer::submitResource(Connection *conn, Kind kind, const QString &engineUrl, bool headOnly) {
    auto *job = new ResourceJob{conn, kind, engineUrl, headOnly};
    m_inFlight.ref();
    {
        QMutexLocker lock(&m_queueMutex);
        m_queue.append(job);
    }
    m_queueReady.wakeOne();
    // The reply is posted by the slot thread once it has a result (see
    // ResourceSlot::runJob). Nothing is posted here: the main thread must not be
    // able to deliver a reply before the engine has produced one.
}

void ArticleServer::drainCompleted() {
    QList<Delivery *> done;
    {
        QMutexLocker lock(&m_queueMutex);
        done.swap(m_completed);
    }
    for (Delivery *d : done) {
        deliverResourceResult(d); // takes ownership
    }
}

void ArticleServer::deliverResourceResult(Delivery *d) {
    QScopedPointer<Delivery> guard(d);
    Connection *conn = d->conn;
    // The connection may have died while the engine worked. Membership in the
    // main-thread-only live set is the liveness check; the pointer is never
    // dereferenced before this point.
    if (!m_liveConnections.contains(conn)) return;
    if (!conn->alive()) return; // client gone; nothing to answer

    const int sz = d->rc;
    const QByteArray &body = d->body;

    if (sz < 0) {
        if (sz == -2) {
            qWarning() << "[article-server] resource not found:" << d->engineUrl;
            writeNotFound(conn);
        } else if (sz == -4) {
            qWarning() << "[article-server] resource too large (>4MiB):" << d->engineUrl;
            writeServerError(conn, QStringLiteral("payload too large"));
        } else {
            qWarning() << "[article-server] engine error" << sz << "for" << d->engineUrl;
            writeServerError(conn, QStringLiteral("engine error %1").arg(sz));
        }
        conn->socket->disconnectFromHost();
        return;
    }

    if (sz == 0) {
        // Resolved but no bytes (e.g. a DSL sound whose ".dsl.files" tree was
        // not imported). Answer 404 so the media backend fails fast.
        qWarning() << "[article-server] empty resource:" << d->engineUrl;
        writeNotFound(conn);
        conn->socket->disconnectFromHost();
        return;
    }

    QMimeDatabase db;
    const QMimeType mt = db.mimeTypeForFileNameAndData(d->engineUrl, body);
    QString contentType = mt.name();
    if (d->kind == Kind::Gdau && contentType == QStringLiteral("application/octet-stream"))
        contentType = QStringLiteral("audio/mpeg");
    qInfo() << "[article-server] GET" << d->engineUrl << "->" << sz << "bytes" << contentType;
    writeReply(conn, 200, QStringLiteral("OK"), contentType, body, d->headOnly ? 0 : -1);
    conn->socket->disconnectFromHost();
}

void ArticleServer::writeReply(Connection *conn, int status, const QString &statusText,
                               const QString &contentType, const QByteArray &body, qint64 bodyLengthOverride) {
    if (!conn || !conn->alive()) return; // died while the engine ran
    const qint64 len = (bodyLengthOverride < 0) ? body.size() : bodyLengthOverride;
    const QByteArray headers =
        QStringLiteral("HTTP/1.1 %1 %2\r\n"
                       "Content-Type: %3\r\n"
                       "Content-Length: %4\r\n"
                       "Cache-Control: no-cache\r\n"
                       "Connection: close\r\n\r\n")
            .arg(status)
            .arg(statusText)
            .arg(contentType)
            .arg(len)
            .toUtf8();
    conn->socket->write(headers);
    if (bodyLengthOverride != 0) conn->socket->write(body);
    conn->socket->flush();
}

void ArticleServer::writeNotFound(Connection *conn) {
    writeReply(conn, 404, QStringLiteral("Not Found"), QStringLiteral("text/plain"), QByteArray("Not Found"));
}

void ArticleServer::writeBadRequest(Connection *conn, const QString &reason) {
    writeReply(conn, 400, QStringLiteral("Bad Request"), QStringLiteral("text/plain"), reason.toUtf8());
}

void ArticleServer::writeServerError(Connection *conn, const QString &reason) {
    writeReply(conn, 500, QStringLiteral("Internal Server Error"), QStringLiteral("text/plain"),
               reason.toUtf8());
}
