// Host-side tests for ArticleServer's resource pool.
//
// ArticleServer's only engine dependency is gd_get_resource / gd_get_audio, so
// this test links the real app/ArticleServer.cpp against stubbed versions of
// those two functions and drives the server over a real loopback socket. That is
// enough to exercise the parts of fix-article-server-gui-reentrancy that are
// app-side and otherwise only reachable on a device:
//
//   1. a normal bres:// request is resolved and answered;
//   2. while one request is stuck inside the engine, a second request on another
//      connection is still answered — the 2-slot pool's whole point (design D1);
//   3. a client that disconnects while its request is in flight does not crash
//      the server and leaves no residue: the next request still resolves
//      (design D3, and the "abandoned by the client" spec scenario).
//
// The stub lets a request block inside the "engine" until the test releases it,
// which is how a wedge is simulated without touching real dictionaries.
//
// Exit code 0 = all checks passed.

#include "ArticleServer.hpp"

#include <QCoreApplication>
#include <QHostAddress>
#include <QMutex>
#include <QMutexLocker>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTimer>
#include <QWaitCondition>

#include <cstdio>
#include <cstring>
#include <functional>

// ---------------------------------------------------------------------------
// Stub engine
// ---------------------------------------------------------------------------
namespace {

QMutex g_mutex;
QWaitCondition g_cv;
int g_hangsActive = 0;   // requests currently blocked inside the stub
bool g_release = false;  // set by the test to let blocked requests finish

int respond(const char *url, char *out, int outSize, const char *tag) {
    const QByteArray body = QByteArray(tag) + ":" + QByteArray(url ? url : "");
    if (body.size() + 1 > outSize) return -4;
    std::memcpy(out, body.constData(), body.size());
    out[body.size()] = '\0';
    return body.size();
}

int stubFetch(const char *url, char *out, int outSize) {
    if (!url || !out || outSize <= 0) return -1;
    // Any URL containing "/hang" blocks here until the test releases it, so the
    // test can hold one slot busy deterministically.
    if (QByteArray(url).contains("/hang")) {
        QMutexLocker lock(&g_mutex);
        ++g_hangsActive;
        g_cv.wakeAll();
        while (!g_release) g_cv.wait(&g_mutex);
        --g_hangsActive;
        return respond(url, out, outSize, "HANG");
    }
    return respond(url, out, outSize, "OK");
}

} // namespace

extern "C" int gd_get_resource(const char *url, char *out, int out_size) {
    return stubFetch(url, out, out_size);
}

extern "C" int gd_get_audio(const char *url, char *out, int out_size) {
    return stubFetch(url, out, out_size);
}

// ---------------------------------------------------------------------------
// Test scaffolding
// ---------------------------------------------------------------------------
namespace {

int g_failures = 0;

void fail(const QString &msg) {
    std::fprintf(stderr, "FAIL: %s\n", qPrintable(msg));
    ++g_failures;
}

void pass(const QString &msg) {
    std::fprintf(stdout, "ok: %s\n", qPrintable(msg));
}

// Minimal HTTP client: sends one GET, accumulates the response, and reports
// completion when the server closes (it sends "Connection: close").
class Client : public QObject {
public:
    explicit Client(QObject *parent = nullptr) : QObject(parent) {
        connect(&sock, &QTcpSocket::readyRead, this, [this] { resp += sock.readAll(); });
        connect(&sock, &QTcpSocket::disconnected, this, [this] { markDone(); });
        connect(&sock, &QTcpSocket::errorOccurred, this, [this](QAbstractSocket::SocketError) { markDone(); });
    }

    void get(quint16 port, const QByteArray &path) {
        const QByteArray req = "GET " + path + " HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
        connect(&sock, &QTcpSocket::connected, this, [this, req] {
            sock.write(req);
            sock.flush();
        });
        sock.connectToHost(QHostAddress::LocalHost, port);
    }

    void abandon() { sock.abort(); }

    QTcpSocket sock;
    QByteArray resp;
    bool done = false;

private:
    void markDone() {
        if (done) return;
        done = true;
        if (onDone) onDone();
    }

public:
    std::function<void()> onDone;
};

int hangsActive() {
    QMutexLocker lock(&g_mutex);
    return g_hangsActive;
}

void releaseHangs() {
    QMutexLocker lock(&g_mutex);
    g_release = true;
    g_cv.wakeAll();
}

void rearmHangs() {
    QMutexLocker lock(&g_mutex);
    g_release = false;
}

} // namespace

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);

    ArticleServer server;
    if (!server.listen()) {
        std::fprintf(stderr, "FAIL: server.listen() failed\n");
        return 2;
    }
    const quint16 port = server.port();

    // One client per connection, kept alive for the whole run.
    Client clientHang, clientOk, clientAbandon, clientAfter;

    // A simple tick-driven state machine, so no check depends on an arbitrary
    // sleep being long enough.
    enum Step {
        StartHang, WaitHangActive, StartOk, WaitOk, ReleaseHangs, WaitHangDone,
        AbandonStart, AbandonAbort, StartAfter, WaitAfter, Done
    };
    Step step = StartHang;
    int ticks = 0;

    auto finish = [&](const char *verdict) {
        std::fprintf(stdout, "%s: %s\n", g_failures == 0 ? "PASS" : "FAIL", verdict);
        app.exit(g_failures == 0 ? 0 : 1);
    };

    QTimer tick;
    tick.setInterval(25);
    QObject::connect(&tick, &QTimer::timeout, [&]() {
        switch (step) {
        case StartHang:
            clientHang.get(port, "/bres/d1/hang");
            step = WaitHangActive;
            ticks = 0;
            break;

        case WaitHangActive:
            if (hangsActive() >= 1) {              // the wedge is in the engine
                clientOk.get(port, "/bres/d1/ok");
                step = WaitOk;
                ticks = 0;
            } else if (++ticks > 80) {
                fail("hung request never reached the engine");
                step = Done;
            }
            break;

        case WaitOk:
            if (clientOk.done) {
                if (!clientOk.resp.startsWith("HTTP/1.1 200"))
                    fail("second request did not get a 200: " + clientOk.resp.left(48));
                else if (!clientOk.resp.contains("OK:bres://d1/ok"))
                    fail("second request body wrong: " + clientOk.resp.right(48));
                else if (hangsActive() < 1)
                    fail("second request was served only after the first finished — no slot isolation");
                else
                    pass("second request answered while the first is still stuck (2-slot isolation)");
                releaseHangs();
                step = WaitHangDone;
                ticks = 0;
            } else if (++ticks > 120) {
                fail("second request did not complete while the first was stuck");
                releaseHangs();
                step = Done;
            }
            break;

        case WaitHangDone:
            if (clientHang.done) {
                if (!clientHang.resp.contains("HANG:bres://d1/hang"))
                    fail("hung request body wrong: " + clientHang.resp.right(48));
                else
                    pass("stuck request completed after release");
                rearmHangs();
                step = AbandonStart;
                ticks = 0;
            } else if (++ticks > 80) {
                fail("hung request never completed after release");
                step = Done;
            }
            break;

        case AbandonStart:
            clientAbandon.get(port, "/bres/d1/hang2");
            step = AbandonAbort;
            ticks = 0;
            break;

        case AbandonAbort:
            if (hangsActive() >= 1) {
                clientAbandon.abandon();  // client goes away mid-request
                releaseHangs();
                step = StartAfter;
                ticks = 0;
            } else if (++ticks > 80) {
                fail("abandoned request never reached the engine");
                step = Done;
            }
            break;

        case StartAfter:
            // Give the dying connection a chance to be reaped before the next
            // request, so this also exercises the "no residue" path.
            if (++ticks > 8) {
                clientAfter.get(port, "/bres/d1/ok3");
                step = WaitAfter;
                ticks = 0;
            }
            break;

        case WaitAfter:
            if (clientAfter.done) {
                if (clientAfter.resp.contains("OK:bres://d1/ok3"))
                    pass("request after an abandoned one still resolves (no residue)");
                else
                    fail("request after abandon failed: " + clientAfter.resp.left(48));
                step = Done;
            } else if (++ticks > 120) {
                fail("request after abandon never completed");
                step = Done;
            }
            break;

        case Done:
            tick.stop();
            finish("article-server resource pool");
            break;
        }
    });
    tick.start();

    return app.exec();
}
