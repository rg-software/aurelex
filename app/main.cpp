#include <QDir>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QStandardPaths>
#include <QUrl>
#include <QDebug>
#include <QFontDatabase>
#include <QtWebView/QtWebView>

#include "EngineController.hpp"

int main(int argc, char *argv[])
{
    // Text input uses the system IME (any keyboard). Full IME composing is
    // bypassed via displayText-driven suggestions (see main.qml) because Qt
    // 6.6's composing/extracted-text path breaks on Android 14+. If the
    // system keyboard ever proves unusable on some device, the embedded Qt
    // VirtualKeyboard is the fallback: re-enable the line below (and restore
    // the VK staging + InputPanel from git history, commit 7b26780).
    // qputenv("QT_IM_MODULE", QByteArray("qtvirtualkeyboard"));
    QtWebView::initialize();
    QGuiApplication app(argc, argv);

    // Register the Material Icons font (bundled via fonts.qrc) so QML can render
    // glyphs with the "Material Icons" family. See qt-material-ui change design D6.
    const int fontId = QFontDatabase::addApplicationFont(
        QStringLiteral(":/fonts/MaterialIcons-Regular.ttf"));
    if (fontId < 0) {
        qWarning() << "[aurelex] failed to register Material Icons font";
    } else {
        qInfo() << "[aurelex] Material Icons font families:"
                << QFontDatabase::applicationFontFamilies(fontId);
    }

    const QString home = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
    const QString staged = home + QStringLiteral("/staged");
    QDir().mkpath(home);
    QDir().mkpath(staged);

    EngineController engine;
    engine.initialize(home, staged);

    QQmlApplicationEngine qengine;
    qengine.rootContext()->setContextProperty("engine", &engine);
    qengine.load(QUrl(QStringLiteral("qrc:/Aurelex/main.qml")));
    if (qengine.rootObjects().isEmpty())
        return -1;

    return app.exec();
}