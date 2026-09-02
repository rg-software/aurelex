#include <QDir>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QStandardPaths>
#include <QUrl>
#include <QDebug>
#include <QtWebView/QtWebView>

#include "EngineController.hpp"

int main(int argc, char *argv[])
{
    // Route Qt text input through the embedded VirtualKeyboard: the system
    // IME stack (SwiftKey/Gboard + Qt 6.6's InputConnection) proved broken on
    // this device (composing reverts, inactive connections, IME deadlocks).
    // Must be set before QGuiApplication constructs the platform integration.
    qputenv("QT_IM_MODULE", QByteArray("qtvirtualkeyboard"));
    QtWebView::initialize();
    QGuiApplication app(argc, argv);

    const QString home = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
    const QString staged = home + QStringLiteral("/staged");
    QDir().mkpath(home);
    QDir().mkpath(staged);

    EngineController engine;
    engine.initialize(home, staged);

    QQmlApplicationEngine qengine;
    // The VirtualKeyboard QML module is staged under assets/qml (see
    // build.ps1); the default import path doesn't include it on Android.
    qengine.addImportPath(QStringLiteral("assets:/qml"));
    qengine.rootContext()->setContextProperty("engine", &engine);
    qengine.load(QUrl(QStringLiteral("qrc:/AurelexExp/main.qml")));
    if (qengine.rootObjects().isEmpty())
        return -1;

    return app.exec();
}