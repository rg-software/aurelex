#pragma once

#include <QObject>
#include <QString>
#include <QStringList>
#include <QFuture>
#include <QFutureWatcher>

extern "C" {
#include "goldendict.h"
}

// EngineController: QML-facing wrapper around the in-process goldendict engine.
// Owns the engine lifetime; calls are off-thread (QtConcurrent) so the UI
// thread never blocks on the (potentially slow) gd_* C API.
class EngineController : public QObject
{
    Q_OBJECT
    Q_PROPERTY(int dictCount READ dictCount NOTIFY dictCountChanged)
    Q_PROPERTY(bool ready READ ready NOTIFY readyChanged)
    Q_PROPERTY(QString lastError READ lastError NOTIFY lastErrorChanged)
public:
    explicit EngineController(QObject *parent = nullptr);
    ~EngineController() override;

    int dictCount() const { return m_dictCount; }
    bool ready() const { return m_ready; }
    QString lastError() const { return m_lastError; }

    // Initialise the engine. `configDir`/`indexDir` are usually the same
    // AppLocalDataLocation; `stagedDir` is the dict folder the app stages to.
    Q_INVOKABLE void initialize(const QString &appDir, const QString &stagedDir);
    Q_INVOKABLE void rescan();

    // Lookup a word. `articleLoaded(word, html)` on success, or
    // `articleNotFound(word)` when the engine returned a "no match" article.
    Q_INVOKABLE void lookup(const QString &word);
    Q_INVOKABLE void suggest(const QString &prefix);

    // Rewrite upstream article asset URLs (qrc:///, :/<module>/) to
    // file:///android_asset/ so the platform WebView can load them.
    // Engine image / audio resources (bres://, gdau://) get a local loopback
    // HTTP server in a later milestone (article bridge D3 in the all-qt-ui-port
    // design); for milestone 1 the test dict has no images/audio, so this
    // rewrite is enough.
    Q_INVOKABLE QString rewriteArticleUrls(const QString &html) const;

signals:
    void dictCountChanged();
    void readyChanged();
    void lastErrorChanged();
    void articleLoaded(const QString &word, const QString &html);
    void articleNotFound(const QString &word);
    void suggestionsReady(const QString &prefix, const QStringList &suggestions);

private:
    void runScan();
    void setDictCount(int n);
    void setReady(bool r);
    void setLastError(const QString &e);

    int m_dictCount = 0;
    bool m_ready = false;
    QString m_lastError;
    QString m_appDir;
    QString m_stagedDir;
};
