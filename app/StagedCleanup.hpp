// Decides whether a staged import directory may be deleted.
// See openspec/changes/stale-import-cleanup (design.md).
//
// A dictionary that fails to load stages files that nothing else can reach: the
// Remove button is driven by the loaded-dictionary list, and a failed dictionary
// is not in it. So a failed import's directory has to be deletable through the
// scan-failure report instead - which makes this the one place a path supplied
// from outside (the engine's failure list) turns into a filesystem deletion.
//
// Two guards, both required:
//
//   1. CONTAINMENT. Only a directory that is a direct child of the staged root
//      may be removed. The failure path is trusted for display, not for
//      deletion; a path outside the staged root is refused outright.
//
//   2. SHARING. One import folder can hold several dictionaries. A directory
//      that any loaded dictionary still reads from must survive, so removing a
//      failed member cannot take its working siblings with it.
//
// Plus one predicate the caller applies before either: holdsPrimaryDictionaryFile.
// It is here rather than inline in EngineController because the sweep's copy of
// it shipped untested and read only the top level, which deleted nested imports
// that were loading fine (fix-stale-sweep-deletes-live-dictionaries).
//
// Kept as header-only free functions (rather than inline in EngineController) so
// a host test can exercise them without the Android build, following
// app/IndexCleanup.hpp.
#pragma once

#include "StagingRules.hpp"

#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QString>
#include <QStringList>

namespace StagedCleanup {

// True when `dir` is a direct child directory of `stagedRoot`.
// Both sides are canonicalised, so a trailing separator or a "." segment does
// not defeat the check, and a sibling of the root (e.g. ".../staged-evil") is
// not mistaken for a child.
inline bool isDirectChildOf(const QString &dir, const QString &stagedRoot) {
    if (dir.isEmpty() || stagedRoot.isEmpty())
        return false;
    const QString rootAbs = QDir(stagedRoot).absolutePath();
    const QString dirAbs = QDir(dir).absolutePath();
    if (dirAbs == rootAbs)
        return false; // the root itself is never a removable child
    return QFileInfo(dirAbs).dir().absolutePath() == rootAbs;
}

// True when any of `loadedSources` (the `source` paths of loaded dictionaries)
// lives inside `dir`. Such a directory is in use and must not be removed.
inline bool isUsedByLoadedDictionary(const QString &dir,
                                     const QStringList &loadedSources) {
    if (dir.isEmpty())
        return false;
    const QString dirAbs = QDir(dir).absolutePath();
    for (const QString &s : loadedSources) {
        if (s.isEmpty())
            continue;
        // Qt puts a trailing separator on a directory path, which would defeat
        // a plain prefix test; normalise both sides the same way.
        const QString sClean = QDir::cleanPath(s);
        if (sClean == dirAbs || sClean.startsWith(dirAbs + QLatin1Char('/')))
            return true;
    }
    return false;
}

// True when `dir` holds a primary dictionary file (.mdx / .dsl / .dsl.dz / .ifo)
// ANYWHERE beneath it, at any depth.
//
// The walk descends because an import preserves the picked folder's layout, so
// `staged/<sourceId>/<topic>/<name>/<dict>.dsl.dz` is the normal shape - not an
// edge case. The sweep's previous test listed only the top level with
// QDir::Files and no QDir::Subdirectories, found no primary, and deleted every
// such directory while its dictionaries were loaded and searchable.
//
// QDirIterator rather than QDir::entryInfoList(QDir::Subdirectories): the latter
// materialises the whole listing, so a match at the first entry still costs a
// stat of every file in the tree - and a `<dict>.files` or StarDict `res` tree
// holds thousands. Iterating short-circuits on the first hit, which is the
// common case. Symlinked directories are not followed (no FollowSymlinks flag),
// so a cycle cannot trap the sweep.
//
// Descending into resource trees is deliberate and errs safe: a nested `.dsl`
// found inside some resource archive makes the directory look occupied, which
// keeps it rather than deletes it.
inline bool holdsPrimaryDictionaryFile(const QString &dir) {
    if (dir.isEmpty())
        return false;
    QDirIterator it(dir, QStringList(), QDir::Files | QDir::NoDotAndDotDot,
                    QDirIterator::Subdirectories);
    while (it.hasNext()) {
        it.next();
        if (StagingRules::isPrimaryDictionaryName(it.fileName()))
            return true;
    }
    return false;
}

// The single gate both callers go through: removable only when it is inside the
// staged root AND no loaded dictionary uses it.
inline bool mayRemoveStagedDir(const QString &dir, const QString &stagedRoot,
                               const QStringList &loadedSources) {
    return isDirectChildOf(dir, stagedRoot)
        && !isUsedByLoadedDictionary(dir, loadedSources);
}

// ---------------------------------------------------------------------------
// File-set deletion for a source that could not be loaded
// (openspec/changes/report-import-results, design D1)
// ---------------------------------------------------------------------------

// True when `path` resolves to something under `root` (at any depth). Unlike
// isDirectChildOf, which guards a directory reclaim against the staged root's
// own children, this guards a per-FILE delete: a nested import puts the
// dictionary in `staged/<id>/<topic>/<name>/`, not directly under the root.
inline bool isUnderRoot(const QString &path, const QString &root) {
    if (path.isEmpty() || root.isEmpty())
        return false;
    const QString rootAbs = QDir(root).absolutePath();
    const QString pathAbs = QDir(QFileInfo(path).absolutePath()).absolutePath();
    return pathAbs == rootAbs || pathAbs.startsWith(rootAbs + QLatin1Char('/'));
}

// The "stem" of a primary dictionary file: its filename with the primary
// extension removed. `.dsl.dz` removes both parts. A name that is not a primary
// is returned unchanged. The stem is what ties a primary to its companions
// (`X.ifo` -> `X` -> `X.idx`, `X.dict`; `X.mdx` -> `X` -> `X.mdd`, `X.1.mdd`;
// `X.dsl(.dz)` -> `X`).
inline QString primaryStem(const QString &fileName) {
    const QString lower = fileName.toLower();
    if (lower.endsWith(QLatin1String(".dsl.dz")))
        return fileName.left(fileName.size() - 7);
    const struct { const char *ext; } kPrimary[] = { { ".mdx" }, { ".dsl" }, { ".ifo" } };
    for (const auto &p : kPrimary) {
        const QString ext = QLatin1String(p.ext);
        if (lower.endsWith(ext))
            return fileName.left(fileName.size() - ext.size());
    }
    return fileName;
}

// True when `fileName` belongs to the dictionary whose primary has this stem:
// the primary itself, or one of its format's companion files beside it. Used to
// delete a failed source's own files without touching a sibling dictionary that
// shares the folder. Deliberately conservative: an unrecognised name is not
// claimed, so it is never deleted by mistake.
inline bool belongsToStem(const QString &stem, const QString &fileName) {
    if (stem.isEmpty() || fileName.isEmpty())
        return false;
    const QString s = stem.toLower();
    const QString n = fileName.toLower();

    // StarDict companions: .ifo + .idx/.dict/.syn (and the compressed forms).
    static const char *const kStardict[] = { ".ifo", ".idx", ".dict", ".syn",
                                             ".idx.gz", ".dict.dz" };
    for (const char *ext : kStardict)
        if (n == s + QLatin1String(ext))
            return true;

    // MDict: the primary, its resource archive, and numbered .mdd volumes.
    if (n == s + QLatin1String(".mdx") || n == s + QLatin1String(".mdd"))
        return true;
    if (n.startsWith(s + QLatin1Char('.')) && n.endsWith(QLatin1String(".mdd"))) {
        const QString mid = n.mid(s.size() + 1, n.size() - s.size() - 1 - 4);
        bool digits = !mid.isEmpty();
        for (const QChar c : mid)
            if (!c.isDigit()) { digits = false; break; }
        if (digits)
            return true;
    }

    // DSL: .dsl / .dsl.dz
    if (n == s + QLatin1String(".dsl") || n == s + QLatin1String(".dsl.dz"))
        return true;

    return false;
}

// Delete the staged files that belong to the dictionary whose primary is
// `primaryPath`: the primary itself and its companions in the SAME directory,
// matched by stem. Returns how many files were removed.
//
// This is the file-set delete report-import-results needs (design D1): it works
// inside a directory a loaded dictionary shares, which the whole-directory sweep
// cannot, and it never touches a sibling dictionary's files because only the
// failed source's stem is claimed. Containment is enforced per file (under the
// staged root, at any depth) so a path from the engine's failure report can never
// name something the app does not own. Resource trees are the caller's job.
inline int removeSourceFileSet(const QString &primaryPath, const QString &stagedRoot) {
    if (primaryPath.isEmpty() || stagedRoot.isEmpty())
        return 0;
    const QFileInfo pfi(primaryPath);
    const QString dir = pfi.absolutePath();
    if (!isUnderRoot(primaryPath, stagedRoot))
        return 0;
    const QString stem = primaryStem(pfi.fileName());
    const QDir d(dir);
    int removed = 0;
    const QStringList names = d.entryList(QDir::Files | QDir::NoDotAndDotDot);
    for (const QString &n : names) {
        if (!belongsToStem(stem, n))
            continue;
        const QString full = d.filePath(n);
        if (!isUnderRoot(full, stagedRoot))
            continue;
        if (QFile::remove(full))
            ++removed;
    }
    const QString treePath = d.filePath(stem + QLatin1String(".files"));
    if (QFileInfo(treePath).isDir() && isUnderRoot(treePath, stagedRoot)) {
        if (QDir(treePath).removeRecursively())
            ++removed;
    }
    return removed;
}

} // namespace StagedCleanup
