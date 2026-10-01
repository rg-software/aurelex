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
// Kept as header-only free functions (rather than inline in EngineController) so
// a host test can exercise them without the Android build, following
// app/IndexCleanup.hpp.
#pragma once

#include <QDir>
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

// The single gate both callers go through: removable only when it is inside the
// staged root AND no loaded dictionary uses it.
inline bool mayRemoveStagedDir(const QString &dir, const QString &stagedRoot,
                               const QStringList &loadedSources) {
    return isDirectChildOf(dir, stagedRoot)
        && !isUsedByLoadedDictionary(dir, loadedSources);
}

} // namespace StagedCleanup
