// One-time migration for the index-directory separator bug.
// See openspec/changes/fix-index-directory-path-separator (design.md Migration
// Plan, Option A).
//
// Before the fix, `EngineController` passed `appDir + "/index"` to gd_init, but
// the engine treats the index dir as a prefix and appends the dictionary id, so
// indexes landed as siblings: `files/index<md5>` instead of
// `files/index/<md5>`. Correcting the separator makes the engine look inside
// `index/`, orphaning the old files. This sweep moves them into place so the
// upgrade does not force a full reindex.
//
// Kept as a header-only free function (rather than inline in EngineController)
// so a host test can exercise it without the Android build.
#pragma once

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QRegularExpression>
#include <QString>
#include <QStringList>

namespace IndexMigration {

// A dictionary's index id is an MD5 (32 hex chars); the engine writes that plus
// optional `_FTS_*` companion entries inside the index directory. So a stray is
// `index` followed by exactly that shape. The `index/` directory itself does not
// match (nothing follows "index"), nor does an unrelated `index.txt`, which is
// why the shape is checked rather than a bare startsWith("index").
inline QRegularExpression strayPattern() {
    return QRegularExpression(QStringLiteral("^index([0-9a-fA-F]{32}(_FTS_.*)?)$"));
}

// Moves every stray `<appDir>/index<rem>` to `<appDir>/index/<rem>`, stripping
// the artifact `index` prefix. When the destination already exists it removes
// the source instead of skipping, since the destination is the corrected,
// authoritative path and leaving the source would keep the leak. A failed rename
// leaves the source untouched so a later launch (or a reindex) can retry, and
// never aborts startup.
//
// Returns the number of entries moved or removed. Idempotent: after one
// successful pass nothing matches and a second call is a no-op.
inline int migrateStrayIndexes(const QString &appDir) {
    QDir appDirObj(appDir);
    const QString destDir = appDirObj.filePath(QStringLiteral("index"));
    QDir().mkpath(destDir);
    QDir destDirObj(destDir);

    const QRegularExpression rx = strayPattern();
    const QStringList entries =
        appDirObj.entryList(QDir::Files | QDir::Dirs | QDir::NoDotAndDotDot);

    int changed = 0;
    for (const QString &name : entries) {
        const QRegularExpressionMatch m = rx.match(name);
        if (!m.hasMatch())
            continue; // not something we created; leave it alone
        const QString src = appDirObj.filePath(name);
        const QString dst = destDirObj.filePath(m.captured(1));

        if (QFileInfo::exists(dst)) {
            if (QFileInfo(src).isDir()) {
                if (QDir(src).removeRecursively())
                    ++changed;
            } else if (QFile::remove(src)) {
                ++changed;
            }
        } else if (QDir().rename(src, dst)) {
            ++changed;
        }
        // else: rename failed; leave the source for a later attempt.
    }
    return changed;
}

} // namespace IndexMigration
