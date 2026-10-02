// Host-side tests for the staged-import deletion guards
// (stale-import-cleanup):
//   - containment: only a direct child of the staged root may be removed, and a
//     sibling whose name merely starts with the root's is refused;
//   - sharing: a directory any loaded dictionary reads from is not removable, so
//     removing a failed member cannot take working siblings with it;
//   - mayRemoveStagedDir composes both, and is the gate both callers use.
//   - holdsPrimaryDictionaryFile finds a primary at any depth, because an import
//     mirrors the picked folder's layout (fix-stale-sweep-deletes-live-dictionaries).
//
// Header-only, Qt Core only, no engine - mirrors IndexCleanupTest.cpp.
// Exit code 0 = all checks passed.

#include "StagedCleanup.hpp"

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
        std::fprintf(stdout, "FAIL: %s\n", qPrintable(what));
        ++g_failures;
    }
}

// Create an empty placeholder file, creating parent directories as needed.
// Returns false if it could not be created - and a "holds nothing" check against
// a file that was never written would pass for the wrong reason, so the
// positive cases assert this too.
bool touch(const QString &path) {
    QDir().mkpath(QFileInfo(path).absolutePath());
    QFile f(path);
    return f.open(QIODevice::WriteOnly) && f.resize(1);
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

    // ---- recursive primary-file detection ---------------------------------
    // The predicate the staged sweep applies before it deletes. It has to look at
    // every depth, because an import mirrors the picked folder's layout: the
    // staged shape of a dictionary that is loaded and searchable at this moment
    // is staged/<sourceId>/<topic>/<name>/<dict>.dsl.dz. The sweep used to list
    // only the top level, found no primary there, and deleted exactly that
    // directory (fix-stale-sweep-deletes-live-dictionaries).

    // The incident shape, three levels down, plus a sibling topic folder in the
    // same import.
    const QString nestedImport =
        QDir(root).filePath(QStringLiteral("nested01"));
    const QString deepDir = QDir(nestedImport).filePath(
        QStringLiteral("English/American Heritage Dictionary (4th Ed)"));
    const QString deepDict =
        QDir(deepDir).filePath(QStringLiteral("En-En_American Heritage.dsl.dz"));
    check(touch(deepDict), "fixture: the deeply nested dictionary file exists");
    // Its DSL sound/image tree, as the incident's dictionary had. A real nested
    // import is a primary PLUS a resource tree, and the walk has to see the
    // primary before descending into thousands of .wav files.
    check(touch(QDir(deepDir).filePath(
                  QStringLiteral("En-En_American Heritage.files/w1_001.wav"))),
          "fixture: a file in the dictionary's resource tree exists");
    check(StagedCleanup::holdsPrimaryDictionaryFile(nestedImport),
          "a primary three levels down counts: the import holds a dictionary");
    check(StagedCleanup::holdsPrimaryDictionaryFile(deepDir),
          "the directory actually containing the primary holds a dictionary");

    // The pick held a single folder and the dictionary sits in it: one level below
// the import directory. This is the simplest shape of the incident, and it is
    // already enough for the old top-level-only test to miss it.
    const QString oneDownImport =
        QDir(root).filePath(QStringLiteral("nested02"));
    const QString oneDownDir = QDir(oneDownImport).filePath(QStringLiteral("Topic"));
    check(touch(QDir(oneDownDir).filePath(QStringLiteral("En-En_A.mdx"))),
          "fixture: the one-level-down dictionary file exists");
    check(StagedCleanup::holdsPrimaryDictionaryFile(oneDownImport),
          "a primary one level down counts (the shape that used to be swept)");
    check(StagedCleanup::holdsPrimaryDictionaryFile(oneDownDir),
          "the subfolder actually holding the primary counts too");

    // Two sibling dictionaries in separate subfolders: one of them is enough, so
    // the result cannot depend on which subfolder the walk happens to reach first.
    const QString siblingsImport =
        QDir(root).filePath(QStringLiteral("nested03"));
    check(touch(QDir(siblingsImport).filePath(QStringLiteral("A/En-En_A.mdx"))),
          "fixture: the first sibling dictionary exists");
    check(touch(QDir(siblingsImport).filePath(QStringLiteral("B/En-En_B.mdx"))),
          "fixture: the second sibling dictionary exists");
    check(StagedCleanup::holdsPrimaryDictionaryFile(siblingsImport),
          "a primary in either of two sibling subfolders counts");

    // The flat shape - a dictionary straight in the import directory - is what
    // the old top-level-only test was written for. It must still hold.
    const QString flatImport = QDir(root).filePath(QStringLiteral("flat03"));
    check(touch(QDir(flatImport).filePath(QStringLiteral("En-En_Flat.ifo"))),
          "fixture: the flat dictionary file exists");
    check(StagedCleanup::holdsPrimaryDictionaryFile(flatImport),
          "a primary at the top level counts (unchanged behaviour)");

    // Every primary extension is recognised, at depth, and case-insensitively:
    // these are exactly the four isPrimaryDictionaryName accepts.
    struct { const char *dir; const char *file; const char *what; } formats[] = {
        { "fmt_md4",  "a/b/Deep.mdx",      "a nested .mdx counts" },
        { "fmt_dsl5", "c/d/Deep.dsl",      "a nested .dsl counts" },
        { "fmt_dz6",  "e/f/Deep.dsl.dz",   "a nested .dsl.dz counts" },
        { "fmt_ifo7", "g/h/Deep.ifo",      "a nested .ifo counts" },
        { "fmt_up8",  "i/j/Deep.MDX",      "extension matching is case-insensitive" },
        { "fmt_up9",  "k/l/Deep.IFO",      "case-insensitive for .ifo too" },
    };
    for (const auto &fmt : formats) {
        const QString dir = QDir(root).filePath(QString::fromLatin1(fmt.dir));
        const QString file = QDir(dir).filePath(QString::fromLatin1(fmt.file));
        check(touch(file), QStringLiteral("fixture: %1").arg(QString::fromLatin1(fmt.file)));
        check(StagedCleanup::holdsPrimaryDictionaryFile(dir),
              QString::fromLatin1(fmt.what));
    }

    // A resource tree alone is not a dictionary. This is the DSL "<dict>.files"
    // sounds/images directory and the StarDict "res" directory: thousands of
    // files, none of them primary. Such a directory IS an orphan and must be
    // reported as one, or the sweep's own reclaim stops working.
    const QString resourcesOnly = QDir(root).filePath(QStringLiteral("res10"));
    check(touch(QDir(resourcesOnly).filePath(QStringLiteral("X.files/a1.wav"))),
          "fixture: a file inside the resource tree exists");
    check(!StagedCleanup::holdsPrimaryDictionaryFile(resourcesOnly),
          "a resource tree holding only sounds is not a dictionary");

    // Companions and archives are not primaries either. isPrimaryDictionaryName
    // deliberately excludes them, and that is what lets the sweep reclaim an
    // import whose dictionary was removed but whose companions were left.
    const QString companionsOnly = QDir(root).filePath(QStringLiteral("comp11"));
    static const char *companions[] = {
        "X.mdd", "X.idx", "X.dict", "X.syn", "X.css", "X.ann",
        "X.bmp", "X.wav", "X.dsl.zip", "X.readme.txt",
    };
    bool companionsMade = true;
    for (const char *c : companions)
        companionsMade &= touch(QDir(companionsOnly).filePath(QString::fromLatin1(c)));
    check(companionsMade, "fixture: the companion files exist");
    check(!StagedCleanup::holdsPrimaryDictionaryFile(companionsOnly),
          "companions, resource archives and loose assets are not primaries");

    // Subfolders that hold nothing primary, one level and deeper.
    const QString emptyTree = QDir(root).filePath(QStringLiteral("empty12"));
    check(touch(QDir(emptyTree).filePath(QStringLiteral("a/b/c/readme.md"))),
          "fixture: a file with no dictionary extension exists deep down");
    check(!StagedCleanup::holdsPrimaryDictionaryFile(emptyTree),
          "subfolders containing no primary do not make the import hold one");

    // Nothing at all.
    const QString trulyEmpty = QDir(root).filePath(QStringLiteral("empty13"));
    QDir().mkpath(trulyEmpty);
    check(!StagedCleanup::holdsPrimaryDictionaryFile(trulyEmpty),
          "an empty directory holds no dictionary");

    // Degenerate inputs must be false, never a crash or a true.
    check(!StagedCleanup::holdsPrimaryDictionaryFile(QString()),
          "an empty path holds no dictionary");
    check(!StagedCleanup::holdsPrimaryDictionaryFile(
              QDir(root).filePath(QStringLiteral("does-not-exist"))),
          "a path that does not exist holds no dictionary");

    // ---- file-set deletion for an unloadable source ------------------------
    // report-import-results D1: an unloadable source's own files are deleted even
    // when the directory also holds a dictionary that loaded. The sibling's files
    // must survive - deleting the whole directory is exactly the bug this fixes.
    check(StagedCleanup::primaryStem(QStringLiteral("X.dsl.dz")) == QLatin1String("X"),
          "the stem of X.dsl.dz is X");
    check(StagedCleanup::primaryStem(QStringLiteral("X.ifo")) == QLatin1String("X"),
          "the stem of X.ifo is X");
    check(StagedCleanup::belongsToStem(QStringLiteral("X"), QStringLiteral("X.ifo")),
          "X.ifo belongs to stem X");
    check(StagedCleanup::belongsToStem(QStringLiteral("X"), QStringLiteral("X.1.mdd")),
          "a numbered .mdd volume belongs to stem X");
    check(!StagedCleanup::belongsToStem(QStringLiteral("X"), QStringLiteral("X2.ifo")),
          "X2.ifo does NOT belong to stem X (no prefix over-reach)");
    check(!StagedCleanup::belongsToStem(QStringLiteral("X"), QStringLiteral("X.readme")),
          "an unrecognised sibling is never claimed");

    const QString sharedImport = QDir(root).filePath(QStringLiteral("shared20"));
    check(touch(QDir(sharedImport).filePath(QStringLiteral("broken.ifo")))
          && touch(QDir(sharedImport).filePath(QStringLiteral("broken.idx")))
          && touch(QDir(sharedImport).filePath(QStringLiteral("broken.dict"))),
          "fixture: the failing source's StarDict set exists");
    check(touch(QDir(sharedImport).filePath(QStringLiteral("good.ifo")))
          && touch(QDir(sharedImport).filePath(QStringLiteral("good.idx")))
          && touch(QDir(sharedImport).filePath(QStringLiteral("good.dict"))),
          "fixture: a sibling dictionary in the same folder exists");
    const int removed = StagedCleanup::removeSourceFileSet(
        QDir(sharedImport).filePath(QStringLiteral("broken.ifo")), root);
    check(removed == 3, "exactly the failing source's three files are deleted");
    check(!QFileInfo::exists(QDir(sharedImport).filePath(QStringLiteral("broken.ifo")))
          && !QFileInfo::exists(QDir(sharedImport).filePath(QStringLiteral("broken.idx")))
          && !QFileInfo::exists(QDir(sharedImport).filePath(QStringLiteral("broken.dict"))),
          "the failing source's files are gone");
    check(QFileInfo::exists(QDir(sharedImport).filePath(QStringLiteral("good.ifo")))
          && QFileInfo::exists(QDir(sharedImport).filePath(QStringLiteral("good.idx")))
          && QFileInfo::exists(QDir(sharedImport).filePath(QStringLiteral("good.dict"))),
          "the sibling dictionary sharing the folder is untouched");

    // A DSL source with a resource tree: the tree goes with the dictionary.
    const QString dslImport = QDir(root).filePath(QStringLiteral("shared21"));
    check(touch(QDir(dslImport).filePath(QStringLiteral("broken.dsl")))
          && touch(QDir(dslImport).filePath(QStringLiteral("broken.files/a.wav"))),
          "fixture: a DSL with a <name>.files tree exists");
    check(StagedCleanup::removeSourceFileSet(
              QDir(dslImport).filePath(QStringLiteral("broken.dsl")), root) == 2,
          "the DSL primary and its resource tree are deleted");
    check(!QFileInfo::exists(QDir(dslImport).filePath(QStringLiteral("broken.files"))),
          "the DSL resource tree is gone");

    // Containment: a path outside the staged root deletes nothing.
    check(touch(tmp.filePath(QStringLiteral("elsewhere/broken.ifo"))) &&
          StagedCleanup::removeSourceFileSet(
              tmp.filePath(QStringLiteral("elsewhere/broken.ifo")), root) == 0,
          "a source outside the staged root is refused");
    check(QFileInfo::exists(tmp.filePath(QStringLiteral("elsewhere/broken.ifo"))),
          "the outside file was not deleted");

    std::fprintf(stdout, "%s: staged cleanup\n", g_failures == 0 ? "PASS" : "FAIL");
    return g_failures == 0 ? 0 : 1;
}
