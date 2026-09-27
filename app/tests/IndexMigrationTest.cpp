// Host-side tests for the index-directory separator fix
// (fix-index-directory-path-separator):
//   - gdNormalizeIndexDir: appends the separator once, never doubles it;
//   - IndexMigration::migrateStrayIndexes: moves the pre-fix `index<md5>` strays
//     (and their `_FTS_*` companions) into `index/`, leaves unrelated names
//     alone, is idempotent, and removes a source when the destination exists.
//
// Neither dependency touches the engine, so this links nothing but Qt Core.
// Exit code 0 = all checks passed.

#include "IndexMigration.hpp"
#include "index_path.hpp"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QTemporaryDir>

#include <cstdio>

namespace {

int g_failures = 0;

void check(bool cond, const QString &what) {
    if (cond) {
        std::fprintf(stdout, "ok: %s\n", qPrintable(what));
    } else {
        std::fprintf(stderr, "FAIL: %s\n", qPrintable(what));
        ++g_failures;
    }
}

void writeFile(const QString &path, const QByteArray &data = "x") {
    QFile f(path);
    f.open(QIODevice::WriteOnly);
    f.write(data);
    f.close();
}

// A dictionary id is an MD5; use fixed 32-hex strings so the test is stable.
const QString kId = QStringLiteral("0123456789abcdef0123456789abcdef");
const QString kId2 = QStringLiteral("fedcba9876543210fedcba9876543210");

} // namespace

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);

    // ---- gdNormalizeIndexDir (task 4.2) ----
    check(gdNormalizeIndexDir("") == "", "empty stays empty (gd_init rejects it separately)");
    check(gdNormalizeIndexDir("/a/b") == "/a/b/", "a path without a separator is normalized once");
    check(gdNormalizeIndexDir("/a/b/") == "/a/b/", "a path already ending in '/' is not doubled");
    check(gdNormalizeIndexDir("/a/b\\") == "/a/b\\", "a path ending in '\\\\' is not doubled");
    check(gdNormalizeIndexDir("/a/b//") == "/a/b//", "an already-doubled separator is left alone");

    // ---- migration, plain + FTS + non-matching (task 5.4) ----
    {
        QTemporaryDir tmp;
        check(tmp.isValid(), "temporary dir created");
        const QString appDir = tmp.path();

        writeFile(appDir + "/index" + kId, "INDEXDATA");
        QDir().mkpath(appDir + "/index" + kId2 + "_FTS_x");
        writeFile(appDir + "/index" + kId2 + "_FTS_x/posting");
        writeFile(appDir + "/index.txt", "UNRELATED"); // must be untouched

        const int moved = IndexMigration::migrateStrayIndexes(appDir);
        check(moved == 2, QStringLiteral("two strays migrated (got %1)").arg(moved));

        check(QFileInfo::exists(appDir + "/index/" + kId), "plain index moved into index/");
        check(QFileInfo(appDir + "/index/" + kId).isFile(), "moved entry is still a file");
        check(QFileInfo::exists(appDir + "/index/" + kId2 + "_FTS_x"), "FTS companion moved");
        check(QFileInfo(appDir + "/index/" + kId2 + "_FTS_x/posting").isFile(),
              "FTS companion contents moved with it");
        check(!QFileInfo::exists(appDir + "/index" + kId), "no stray sibling left behind");
        check(!QFileInfo::exists(appDir + "/index" + kId2 + "_FTS_x"), "no stray FTS sibling left behind");
        check(QFileInfo::exists(appDir + "/index.txt"), "unrelated index.txt is left alone");

        // Idempotent: nothing matches a second time.
        const int again = IndexMigration::migrateStrayIndexes(appDir);
        check(again == 0, QStringLiteral("second pass is a no-op (got %1)").arg(again));
        check(QFileInfo::exists(appDir + "/index/" + kId), "index still present after second pass");
    }

    // ---- destination already exists: source removed, destination kept ----
    {
        QTemporaryDir tmp;
        const QString appDir = tmp.path();
        writeFile(appDir + "/index" + kId, "STALE");
        QDir().mkpath(appDir + "/index");
        writeFile(appDir + "/index/" + kId, "FRESH");

        const int changed = IndexMigration::migrateStrayIndexes(appDir);
        check(changed == 1, QStringLiteral("existing-destination case reports one change (got %1)").arg(changed));
        check(!QFileInfo::exists(appDir + "/index" + kId), "stale source removed");
        check(QFileInfo::exists(appDir + "/index/" + kId), "authoritative destination kept");

        QFile f(appDir + "/index/" + kId);
        f.open(QIODevice::ReadOnly);
        const QByteArray content = f.readAll();
        check(content == "FRESH", "destination content was not overwritten");
    }

    std::fprintf(stdout, "%s: index path + migration\n", g_failures == 0 ? "PASS" : "FAIL");
    return g_failures == 0 ? 0 : 1;
}
