// Deletes the on-disk index entries belonging to one dictionary.
// See openspec/changes/fix-dictionary-removal-cleanup (design.md D1/D2/D3).
//
// The engine names an index `<indexDir><dictId>` - the index directory is a
// *prefix*, not a directory (carve/index_path.hpp) - and EngineController points
// that prefix at `<appDir>/index/`. So a dictionary's entries are:
//
//   <appDir>/index/<id>            the btree index (a file)
//   <appDir>/index/<id>_FTS_x      the full-text index (a directory)
//   <appDir>/index/<id>_FTS_x_temp a transient build directory
//
// Matching `<id>*` inside `index/` catches all three. The id is 32 hex
// characters, so the prefix can never match another dictionary's entry.
//
// Before fix-index-directory-path-separator the same entries sat *beside* the
// directory as `<appDir>/index<id>*`. Those are removed too, so a removal stays
// correct if the layout migration has not run yet or a migration rename failed
// (it leaves the source for a later attempt by design). The two names are
// disjoint: `<id>` cannot match inside `index/`, and `index<id>` cannot match
// beside it, so nothing is removed twice.
//
// Kept as a header-only free function (rather than inline in EngineController)
// so a host test can exercise it without the Android build, following
// app/IndexMigration.hpp.
#pragma once

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QString>
#include <QStringList>

namespace IndexCleanup {

// Removes every index entry for `dictId` under `appDir` and returns the paths it
// removed (empty when there was nothing to remove or the arguments are empty).
// Directories are removed recursively; files by QFile::remove. Nothing else in
// the index directory is touched.
inline QStringList removeIndexEntries(const QString &appDir, const QString &dictId) {
    QStringList removed;
    if (appDir.isEmpty() || dictId.isEmpty())
        return removed;

    const QString indexDir = QDir(appDir).filePath(QStringLiteral("index"));

    struct Target {
        QString dir;
        QString prefix;
    };
    const Target targets[] = {
        { indexDir, dictId },                           // current layout: index/<id>*
        { appDir, QStringLiteral("index") + dictId },   // pre-fix strays: index<id>*
    };

    for (const Target &t : targets) {
        QDir d(t.dir);
        if (!d.exists())
            continue;
        const QStringList entries = d.entryList(
            QStringList() << (t.prefix + QLatin1Char('*')),
            QDir::Files | QDir::Dirs | QDir::NoDotAndDotDot);
        for (const QString &name : entries) {
            const QString full = d.filePath(name);
            const bool ok =
                QFileInfo(full).isDir() ? QDir(full).removeRecursively() : QFile::remove(full);
            if (ok)
                removed.append(full);
        }
    }
    return removed;
}

} // namespace IndexCleanup
