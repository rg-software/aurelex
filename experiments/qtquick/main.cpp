#include <QDir>
#include <QGuiApplication>
#include <QStandardPaths>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QUrl>
#include <QDebug>
#include <QtWebView/QtWebView>

#include <cstdio>
#include <vector>

#include "goldendict.h"

// The carve produces upstream qrc:/// asset URLs which the platform WebView
// cannot fetch by itself; rewrite to the bundled-asset scheme we ship in the
// experiment APK. (Gate 2: proving this rewrite is exactly what is needed on
// WebView, versus the Kotlin WebViewClient intercept.)
static QString qrcToAsset(const QString &html)
{
    QString out = html;
    out.replace(QStringLiteral("qrc:///"), QStringLiteral("file:///android_asset/"));
    return out;
}

int main(int argc, char *argv[])
{
    QtWebView::initialize();
    QGuiApplication app(argc, argv);

    const QString home = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
    QDir().mkpath(home);
    const QString staged = home + QStringLiteral("/staged");
    QDir().mkpath(staged);
    const QString indexDir = home + QStringLiteral("/index");
    QDir().mkpath(indexDir);

    qInfo() << "home:" << home;
    qInfo() << "gd_init:" << gd_init(home.toLocal8Bit().constData(),
                                     indexDir.toLocal8Bit().constData());
    int n = gd_scan_dicts(staged.toLocal8Bit().constData());
    qInfo() << "gd_scan_dicts(staged) ->" << n;
    qInfo() << "gd_dict_count ->" << gd_dict_count();

    std::vector<char> buf(1 << 20, 0);
    int sz = gd_lookup("apple", buf.data(), static_cast<int>(buf.size()));
    qInfo() << "gd_lookup(apple) ->" << sz;

    QString html;
    if (sz > 0)
        html = QString::fromUtf8(buf.data(), sz);
    else
        html = QStringLiteral("<html><body><h1>lookup failed (%1)</h1></body></html>").arg(sz);

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("articleHtml", qrcToAsset(html));
    engine.rootContext()->setContextProperty("articleBase", QStringLiteral("file:///android_asset/"));
    engine.load(QUrl(QStringLiteral("qrc:/AurelexExp/main.qml")));
    if (engine.rootObjects().isEmpty())
        return -1;

    return app.exec();
}