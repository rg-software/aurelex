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
    QtWebView::initialize();
    QGuiApplication app(argc, argv);

    const QString home = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
    const QString staged = home + QStringLiteral("/staged");
    QDir().mkpath(home);
    QDir().mkpath(staged);

    EngineController engine;
    engine.initialize(home, staged);

    QQmlApplicationEngine qengine;
    qengine.rootContext()->setContextProperty("engine", &engine);
    qengine.load(QUrl(QStringLiteral("qrc:/AurelexExp/main.qml")));
    if (qengine.rootObjects().isEmpty())
        return -1;

    return app.exec();
}