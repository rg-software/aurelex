// Host-side tests for the dictionary-removal index cleanup
// (fix-dictionary-removal-cleanup):
//   - IndexCleanup::removeIndexEntries deletes the current-layout entries
//     (`<appDir>/index/<id>` and `<id>_FTS_x`) and leaves other dictionaries'
//     entries alone;
//   - it also deletes the pre-fix `<appDir>/index<id>*` strays, so a removal is
//     correct before the layout migration has run;
//   - it removes the returned paths' directories recursively and touches
//     nothing else in the app dir.
//
// Header-only, Qt Core only, no engine - mirrors IndexMigrationTest.cpp.
// Exit code 0 = all checks passed.

#include "IndexCleanup.hpp"

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
    QDir().mkpath(QFileInfo(path).absolutePath());
    QFile f(path);
    f.open(QIODevice::WriteOnly);
    f.write(data);
    f.close();
}

// A dictionary id is an MD5; fixed 32-hex strings keep the test stable.
const QString kId = QStringLiteral("0123456789abcdef0123456789abcdef");
const QString kId2 = QStringLiteral("fedcba9876543210fedcba9876543210");

} // namespace

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);

    // ---- current layout: index/<id>* deleted, index/<id2>* kept ----
    {
        QTemporaryDir tmp;
        check(tmp.isValid(), "temporary dir created");
        const QString appDir = tmp.path();

        writeFile(appDir + "/index/" + kId, "BTREE");
        writeFile(appDir + "/index/" + kId + "_FTS_x/posting", "FTS");
        writeFile(appDir + "/index/" + kId + "_FTS_x_temp/posting", "TEMP");
        writeFile(appDir + "/index/" + kId2, "OTHER");
        writeFile(appDir + "/index/" + kId2 + "_FTS_x/posting", "OTHERFTS");

        const QStringList removed = IndexCleanup::removeIndexEntries(appDir, kId);
        check(removed.size() == 3, QStringLiteral("removed the id's three entries (got %1)").arg(removed.size()));
        check(!QFileInfo::exists(appDir + "/index/" + kId), "btree index deleted");
        check(!QFileInfo::exists(appDir + "/index/" + kId + "_FTS_x"), "FTS index deleted recursively");
        check(!QFileInfo::exists(appDir + "/index/" + kId + "_FTS_x_temp"), "FTS temp deleted");

        check(QFileInfo::exists(appDir + "/index/" + kId2), "other dictionary's btree index kept");
        check(QFileInfo::exists(appDir + "/index/" + kId2 + "_FTS_x/posting"),
              "other dictionary's FTS index kept");

        // Idempotent: a second removal finds nothing.
        const QStringList again = IndexCleanup::removeIndexEntries(appDir, kId);
        check(again.isEmpty(), "second removal is a no-op");
    }

    // ---- pre-fix layout: index<id>* strays deleted, other names kept ----
    {
        QTemporaryDir tmp;
        const QString appDir = tmp.path();

        writeFile(appDir + "/index" + kId, "STRAYBTREE");
        writeFile(appDir + "/index" + kId + "_FTS_x/posting", "STRAYFTS");
        writeFile(appDir + "/index" + kId2, "OTHERSTRAY");
        writeFile(appDir + "/index.txt", "UNRELATED");

        const QStringList removed = IndexCleanup::removeIndexEntries(appDir, kId);
        check(removed.size() == 2, QStringLiteral("removed both pre-fix entries (got %1)").arg(removed.size()));
        check(!QFileInfo::exists(appDir + "/index" + kId), "pre-fix btree stray deleted");
        check(!QFileInfo::exists(appDir + "/index" + kId + "_FTS_x"), "pre-fix FTS stray deleted");
        check(QFileInfo::exists(appDir + "/index" + kId2), "another dictionary's stray kept");
        check(QFileInfo::exists(appDir + "/index.txt"), "unrelated index.txt untouched");
    }

    // ---- nothing to do / bad arguments ----
    {
        QTemporaryDir tmp;
        const QString appDir = tmp.path();
        check(IndexCleanup::removeIndexEntries(appDir, kId).isEmpty(), "no index dir: nothing removed");
        check(IndexCleanup::removeIndexEntries(appDir, QString()).isEmpty(), "empty id: nothing removed");
        check(IndexCleanup::removeIndexEntries(QString(), kId).isEmpty(), "empty appDir: nothing removed");
    }

    std::fprintf(stdout, "%s: index cleanup\n", g_failures == 0 ? "PASS" : "FAIL");
    return g_failures == 0 ? 0 : 1;
}
