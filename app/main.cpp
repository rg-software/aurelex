#include <QDir>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QStandardPaths>
#include <QStringList>
#include <QUrl>
#include <QDebug>
#include <QFontDatabase>
#include <QLocale>
#include <QTranslator>
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

    // Localization: install the best-matching compiled catalog for the
    // device's UI language (embedded as :/i18n/aurelex_<lang>.qm, see the
    // qt_add_resources("i18n") call in CMakeLists.txt).
    // Try each full locale first, then its language-only code; the first that
    // loads wins. No match falls back to English (no translator) — non-fatal.
    QTranslator *translator = new QTranslator(&app);
    QString loadedLocale;
    const QStringList uiLangs = QLocale().uiLanguages();
    for (const QString &localeName : uiLangs) {
        const QString base = QString(localeName).replace(QLatin1Char('-'), QLatin1Char('_'));
        const QStringList candidates = base.contains(QLatin1Char('_'))
            ? QStringList{ base, base.section(QLatin1Char('_'), 0, 0) }
            : QStringList{ base };
        for (const QString &candidate : candidates) {
            if (translator->load(QStringLiteral(":/i18n/aurelex_") + candidate)) {
                if (app.installTranslator(translator)) {
                    loadedLocale = candidate;
                    break;
                }
            }
        }
        if (!loadedLocale.isEmpty())
            break;
    }
    if (!loadedLocale.isEmpty())
        qInfo() << "[aurelex] using translation catalog:" << loadedLocale
                << "for" << uiLangs.join(QLatin1Char(','));
    else
        qInfo() << "[aurelex] no matching translation catalog; using English base strings";

    // Register the Material Icons font (bundled via qt_add_resources("fonts") in
    // CMakeLists.txt) so QML can render
    // glyphs with the "Material Icons" family. See qt-material-ui change design D6.
    const int fontId = QFontDatabase::addApplicationFont(
        QStringLiteral(":/fonts/MaterialIcons-Regular.ttf"));
    if (fontId < 0) {
        qWarning() << "[aurelex] failed to register Material Icons font";
    } else {
        qInfo() << "[aurelex] Material Icons font families:"
                << QFontDatabase::applicationFontFamilies(fontId);
    }

    // Material Symbols Outlined (subset): a small secondary icon font holding a
    // few glyphs the classic Material Icons set doesn't have (folder_open,
    // match_word and light_mode_auto in the Material Symbols design). Rendered
    // with the "Material Symbols Outlined" family. See the groups-tab-polish and
    // tri-state-theme-control changes.
    const int msFontId = QFontDatabase::addApplicationFont(
        QStringLiteral(":/fonts/MaterialSymbols-Outlined-subset.ttf"));
    if (msFontId < 0) {
        qWarning() << "[aurelex] failed to register Material Symbols font";
    } else {
        qInfo() << "[aurelex] Material Symbols font families:"
                << QFontDatabase::applicationFontFamilies(msFontId);
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