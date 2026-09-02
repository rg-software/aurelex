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
    // System-IME experiment: the embedded VirtualKeyboard works but the user
    // wants their own keyboard. ImhHiddenText hints on the TextInputs make
    // IMEs use direct key commit (no composing/extracted-text monitoring,
    // which is what breaks on Qt 6.6 + Android 15). If this env override is
    // re-enabled the embedded keyboard takes over instead.
    // qputenv("QT_IM_MODULE", QByteArray("qtvirtualkeyboard"));
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