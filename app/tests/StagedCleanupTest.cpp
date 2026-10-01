// Host-side tests for the staged-import deletion guards
// (stale-import-cleanup):
//   - containment: only a direct child of the staged root may be removed, and a
//     sibling whose name merely starts with the root's is refused;
//   - sharing: a directory any loaded dictionary reads from is not removable, so
//     removing a failed member cannot take working siblings with it;
//   - mayRemoveStagedDir composes both, and is the gate both callers use.
//
// Header-only, Qt Core only, no engine - mirrors IndexCleanupTest.cpp.
// Exit code 0 = all checks passed.

#include "StagedCleanup.hpp"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QTemporaryDir>

#include <cstdio>

namespace {

int g_failures = 0;

void check(bool cond, const QString &what) {
    if (cond) {
        std::fprintf(stdout, "ok: %s\n", qPrintable(what));
    } else {
        std::fprintf(stdout, "FAIL: %s\n", qPrintable(what));
        ++g_failures;
    }
}

} // namespace

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);

    QTemporaryDir tmp;
    if (!tmp.isValid()) {
        std::fprintf(stderr, "cannot create a temporary dir\n");
        return 2;
    }

    const QString root = tmp.filePath(QStringLiteral("files/staged"));
    QDir().mkpath(root);

    // ---- containment -------------------------------------------------------
    const QString child = QDir(root).filePath(QStringLiteral("abc123"));
    const QString nested = QDir(child).filePath(QStringLiteral("inner"));

    check(StagedCleanup::isDirectChildOf(child, root),
          "a direct child of the staged root is removable");
    check(!StagedCleanup::isDirectChildOf(root, root),
          "the staged root itself is never a removable child");
    check(!StagedCleanup::isDirectChildOf(nested, root),
          "a nested directory is not a direct child (only import dirs are)");

    // A sibling that shares the root's name prefix must not pass. This is the
    // case a naive startsWith() check gets wrong.
    const QString sibling = tmp.filePath(QStringLiteral("files/staged-evil/x"));
    check(!StagedCleanup::isDirectChildOf(sibling, root),
          "a sibling named like the root (staged-evil) is refused");

    // Trailing separators and "." segments must not defeat the check.
    check(StagedCleanup::isDirectChildOf(child + QLatin1Char('/'), root),
          "a trailing separator on the child still resolves as a direct child");
    check(!StagedCleanup::isDirectChildOf(root + QLatin1Char('/'), root + QLatin1Char('/')),
          "a trailing separator does not make the root its own child");

    // Paths outside the root entirely.
    check(!StagedCleanup::isDirectChildOf(QStringLiteral("/data/data/other/files"), root),
          "an unrelated absolute path is refused");
    check(!StagedCleanup::isDirectChildOf(QString(), root),
          "an empty child is refused");
    check(!StagedCleanup::isDirectChildOf(child, QString()),
          "an empty root refuses everything");

    // ---- sharing -----------------------------------------------------------
    const QString inChild = QDir(child).filePath(QStringLiteral("smoke.ifo"));
    const QStringList loaded{ inChild };
    check(StagedCleanup::isUsedByLoadedDictionary(child, loaded),
          "a directory holding a loaded dictionary's file is in use");

    check(!StagedCleanup::isUsedByLoadedDictionary(
              QDir(root).filePath(QStringLiteral("deadbeef")), loaded),
          "a directory with no loaded dictionary is not in use");

    // A shared import folder: one member loaded, another failed. The directory
    // must survive so the working member is not deleted with the failed one.
    const QString sharedFile = QDir(child).filePath(QStringLiteral("sibling.dsl"));
    check(StagedCleanup::isUsedByLoadedDictionary(child, QStringList{ sharedFile }),
          "a directory is in use when ANY loaded dictionary reads from it");

    check(!StagedCleanup::isUsedByLoadedDictionary(child, QStringList()),
          "no loaded dictionaries means the directory is not in use");
    check(!StagedCleanup::isUsedByLoadedDictionary(child, QStringList{ QString() }),
          "an empty source path is ignored rather than matching everything");

    // A source exactly equal to the directory itself counts as in use.
    check(StagedCleanup::isUsedByLoadedDictionary(child, QStringList{ child }),
          "a source equal to the directory is in use");

    // ---- the composed gate -------------------------------------------------
    const QString failed = QDir(root).filePath(QStringLiteral("deadbeef"));
    check(StagedCleanup::mayRemoveStagedDir(failed, root, loaded),
          "a failed import inside the root, unused, may be removed");

    // ---- reclaim-staged-dirs-on-removal ------------------------------------
    // The directory is reclaimable once the removed dictionary has been dropped
    // from the loaded set. The bug was that the removal path never dropped it, so
    // the guard still saw the dictionary it had just deleted. This pins the
    // predicate's side of that contract: given the right list, the answer is yes.
    check(StagedCleanup::mayRemoveStagedDir(child, root, QStringList{}),
          "a directory whose only owner is gone may be removed");

    // And the sibling case must still hold, with the removed one excluded:
    // one member left loaded keeps the whole directory.
    check(!StagedCleanup::mayRemoveStagedDir(child, root, QStringList{ sharedFile }),
          "a directory still read by a survivor is kept, even after one removal");
    check(!StagedCleanup::mayRemoveStagedDir(child, root, loaded),
          "an in-use import is not removable even though it is inside the root");
    check(!StagedCleanup::mayRemoveStagedDir(sibling, root, QStringList()),
          "an outside path is not removable even when unused");

    // A loaded dictionary that is NOT inside the candidate does not block it:
    // the failed import may go while the loaded one, in a different import
    // directory, is untouched. (A source inside the candidate IS blocked - that
    // is the "an in-use import is not removable" case above.)
    const QString otherImport = QDir(root).filePath(QStringLiteral("cafe01"));
    check(StagedCleanup::mayRemoveStagedDir(failed, root, QStringList{ otherImport }),
          "a loaded dictionary elsewhere does not block removing a failed import");
    check(!StagedCleanup::mayRemoveStagedDir(otherImport, root, QStringList{ otherImport }),
          "the directory the loaded dictionary lives in is itself blocked");

    std::fprintf(stdout, "%s: staged cleanup\n", g_failures == 0 ? "PASS" : "FAIL");
    return g_failures == 0 ? 0 : 1;
}
