#include "ArticleServer.hpp"

#include <QDebug>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QHostAddress>
#include <QMimeDatabase>
#include <QMimeType>
#include <QNetworkProxy>
#include <QRegularExpression>
#include <QTcpServer>
#include <QTcpSocket>
#include <QUrl>
#include <QUrlQuery>

#include <vector>

extern "C" {
#include "goldendict.h"
}

namespace {

constexpr int kMaxResourceBytes = 4 * 1024 * 1024; // matches JNI buffer (gd_boundary.cc:90)
constexpr int kRequestHeaderCap = 64 * 1024;        // 64 KiB; request headers are tiny

} // namespace

ArticleServer::ArticleServer(QObject *parent) : QObject(parent) {}

ArticleServer::~ArticleServer() {
    close();
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
        // Per-route processing handles the body (none for now: the engine routes
        // are GET-only).
        sock->setReadBufferSize(kRequestHeaderCap);
        auto *buf = new QByteArray();
        auto *headersParsed = new bool(false);
        // Guard the socket for the lifetime of the readyRead handler: handle()
        // may spin a nested event loop (see the header), during which this
        // socket can be disconnected and deleted.
        QPointer<QTcpSocket> sockGuard(sock);
        connect(sock, &QTcpSocket::readyRead, this, [this, sockGuard, buf, headersParsed]() {
            QTcpSocket *sock = sockGuard.data();
            if (!sock) return;
            if (*headersParsed) {
                // Drain anything past the header block; we don't accept bodies
                // on the article routes, but keep the socket readable until
                // we close it in handle().
                sock->readAll();
                return;
            }
            buf->append(sock->readAll());
            const int headerEnd = buf->indexOf("\r\n\r\n");
            if (headerEnd < 0) {
                if (buf->size() > kRequestHeaderCap) {
                    writeBadRequest(sock, QStringLiteral("headers too large"));
                    sock->disconnectFromHost();
                }
                return;
            }
            *headersParsed = true;
            const QString headerBlock = QString::fromUtf8(buf->mid(0, headerEnd));
            const QStringList lines = headerBlock.split(QStringLiteral("\r\n"), Qt::SkipEmptyParts);
            if (lines.isEmpty()) {
                writeBadRequest(sock, QStringLiteral("empty request"));
                sock->disconnectFromHost();
                return;
            }
            const QStringList requestLine = lines.first().split(QChar(' '));
            if (requestLine.size() < 2) {
                writeBadRequest(sock, QStringLiteral("malformed request line"));
                sock->disconnectFromHost();
                return;
            }
            const QString method = requestLine.at(0);
            const QString path = requestLine.at(1);
            handle(sockGuard, method, path, headerBlock);
        });
        connect(sock, &QTcpSocket::disconnected, sock, [sock, buf, headersParsed]() {
            delete buf;
            delete headersParsed;
            sock->deleteLater();
        });
    }
}

ArticleServer::Route ArticleServer::classify(const QString &pathIn) {
    // pathIn is the request-target (may include ?query). Strip query/fragment.
    const int q = pathIn.indexOf(QChar('?'));
    const QString path = (q < 0) ? pathIn : pathIn.left(q);
    if (path.startsWith(QStringLiteral("/bres/"))) {
        return { Kind::Bres, path.mid(QStringLiteral("/bres/").size()) };
    }
    if (path.startsWith(QStringLiteral("/gdau/"))) {
        return { Kind::Gdau, path.mid(QStringLiteral("/gdau/").size()) };
    }
    // Anything else is treated as an asset path (sandboxed under /).
    QString suffix = path;
    if (suffix.startsWith(QChar('/'))) suffix = suffix.mid(1);
    return { Kind::Asset, suffix };
}

void ArticleServer::handle(const QPointer<QTcpSocket> &socket, const QString &method, const QString &pathIn, const QString &rawHeaders) {
    Q_UNUSED(rawHeaders);
    if (socket.isNull()) return;
    if (method != QStringLiteral("GET") && method != QStringLiteral("HEAD")) {
        writeBadRequest(socket, QStringLiteral("method %1 not allowed").arg(method));
        socket->disconnectFromHost();
        return;
    }

    const Route route = classify(pathIn);

    if (route.kind == Kind::Asset) {
        if (route.suffix.isEmpty() || route.suffix.contains("..")) {
            writeBadRequest(socket, QStringLiteral("invalid asset path"));
            socket->disconnectFromHost();
            return;
        }
        // Mirror the shipped app's qrc:// -> assets resolution
        // (ArticleWebView.serveQrc). The qrc URLs the engine emits are:
        //   qrc:///scripts/jquery-3.6.0.slim.min.js   -> assets/scripts/...
        //   qrc:///qtwebchannel/qwebchannel.js        -> assets/qtwebchannel/...
        //   qrc:///icons/playsound.svg                -> assets/icons/...
        //   qrc:///flags/<cc>.png                     -> assets/flags/...
        //   qrc:///article-style.css                  -> assets/stylesheets/... (bare css)
        //   qrc:///article-style-st-modern.css        -> assets/stylesheets/...
        QString rel = route.suffix;
        if (rel.endsWith(QStringLiteral(".css"), Qt::CaseInsensitive) && !rel.contains(QChar('/'))) {
            rel = QStringLiteral("stylesheets/") + rel;
        }
        // Try the exact assets subdir first, then bare.
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
            writeNotFound(socket);
            socket->disconnectFromHost();
            return;
        }
        QMimeDatabase db;
        const QMimeType mt = db.mimeTypeForFileNameAndData(rel, body);
        const QString contentType = mt.name();
        writeReply(socket, 200, QStringLiteral("OK"), contentType, body, method == QStringLiteral("HEAD") ? 0 : -1);
        socket->disconnectFromHost();
        return;
    }

    // bres:// or gdau:// -> call into the engine via the C boundary.
    // Route format: /<scheme>/<dictId>/<path...>. dictId is the MD5 host the
    // upstream engine uses (Dictionary::getId()). We rebuild the engine-style
    // URL "bres://<dictId>/<rest>" or "gdau://<dictId>/<rest>" and call the
    // boundary.
    const QString schemePrefix = (route.kind == Kind::Bres) ? QStringLiteral("bres://") : QStringLiteral("gdau://");
    const QString engineUrl = schemePrefix + route.suffix; // <dictId>/<path...>

    std::vector<char> buf(kMaxResourceBytes);
    int (*fn)(const char *, char *, int) = (route.kind == Kind::Bres) ? &gd_get_resource : &gd_get_audio;
    const int sz = fn(engineUrl.toUtf8().constData(), buf.data(), static_cast<int>(buf.size()));
    // gd_get_* spins a nested event loop while the dictionary resource loads
    // (see fetchResource in carve/gd_boundary.cc). The peer may have gone away
    // and the socket's pending deleteLater() may have run inside that loop, so
    // the guard can be null now even though it was valid on entry.
    if (socket.isNull()) return;
    if (sz < 0) {
        if (sz == -2) {
            qWarning() << "[article-server] resource not found:" << engineUrl;
            writeNotFound(socket);
        } else if (sz == -4) {
            qWarning() << "[article-server] resource too large (>4MiB):" << engineUrl;
            writeServerError(socket, QStringLiteral("payload too large"));
        } else {
            qWarning() << "[article-server] engine error" << sz << "for" << engineUrl;
            writeServerError(socket, QStringLiteral("engine error %1").arg(sz));
        }
        socket->disconnectFromHost();
        return;
    }

    if (sz == 0) {
        // The engine resolved the URL but has no bytes for it (e.g. a DSL
        // spelling sound whose ".dsl.files" tree was not imported). Answer 404
        // so the media backend fails fast instead of preparing an empty stream.
        qWarning() << "[article-server] empty resource:" << engineUrl;
        writeNotFound(socket);
        socket->disconnectFromHost();
        return;
    }

    QMimeDatabase db;
    const QMimeType mt = db.mimeTypeForFileNameAndData(engineUrl, QByteArray(buf.data(), sz));
    QString contentType = mt.name();
    if (route.kind == Kind::Gdau && contentType == QStringLiteral("application/octet-stream")) {
        // gdau paths often lack an extension; default to mp3 when unknown.
        contentType = QStringLiteral("audio/mpeg");
    }
    qInfo() << "[article-server] GET" << route.suffix << "->" << sz << "bytes" << contentType;
    writeReply(socket, 200, QStringLiteral("OK"), contentType, QByteArray(buf.data(), sz),
               method == QStringLiteral("HEAD") ? 0 : -1);
    socket->disconnectFromHost();
}

void ArticleServer::writeReply(const QPointer<QTcpSocket> &socket, int status, const QString &statusText,
                               const QString &contentType, const QByteArray &body, qint64 bodyLengthOverride) {
    if (socket.isNull()) return; // died while the engine ran a nested event loop
    const qint64 len = (bodyLengthOverride < 0) ? body.size() : bodyLengthOverride;
    QByteArray headers = QStringLiteral("HTTP/1.1 %1 %2\r\n"
                                        "Content-Type: %3\r\n"
                                        "Content-Length: %4\r\n"
                                        "Cache-Control: no-cache\r\n"
                                        "Connection: close\r\n\r\n")
                            .arg(status)
                            .arg(statusText)
                            .arg(contentType)
                            .arg(len)
                            .toUtf8();
    socket->write(headers);
    if (bodyLengthOverride != 0) socket->write(body);
    socket->flush();
}

void ArticleServer::writeNotFound(const QPointer<QTcpSocket> &socket) {
    const QByteArray body = "Not Found";
    writeReply(socket, 404, QStringLiteral("Not Found"), QStringLiteral("text/plain"), body);
}

void ArticleServer::writeBadRequest(const QPointer<QTcpSocket> &socket, const QString &reason) {
    const QByteArray body = reason.toUtf8();
    writeReply(socket, 400, QStringLiteral("Bad Request"), QStringLiteral("text/plain"), body);
}

void ArticleServer::writeServerError(const QPointer<QTcpSocket> &socket, const QString &reason) {
    const QByteArray body = reason.toUtf8();
    writeReply(socket, 500, QStringLiteral("Internal Server Error"), QStringLiteral("text/plain"), body);
}