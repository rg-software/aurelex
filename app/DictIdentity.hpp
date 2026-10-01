// Dictionary identity: NAME + CONTENT, never location.
//
// Implements openspec/changes/resolve-duplicate-dictionaries (design.md D2/D7).
// Header-only and free of engine and staged-storage dependencies so it can be
// exercised by a plain host test, like StagedCleanup.hpp and IndexCleanup.hpp
// before it.
//
// The one rule everything else follows from: a dictionary's identity must not
// depend on WHERE its files live. The engine's own id is an MD5 over the
// absolute source paths (gd_boundary.cc), so two copies of one dictionary
// imported from two folders get two ids and appear twice in the list. That is
// the bug this file exists to remove.
//
// Header-only, no engine, no filesystem: it compares records that were already
// read elsewhere.
#pragma once

#include <QMap>
#include <QString>
#include <QVector>

namespace DictIdentity {

// The mtime slack the importer already applies when it skips an unchanged file
// (AurelexActivity.java). Reusing it here means "did this file change?" has one
// answer in the app rather than two that can disagree.
inline constexpr qint64 kMtimeToleranceMs = 5000;

// One file of a dictionary's source set. Only the BASENAME is kept: the engine
// always reports absolute paths, and stripping the directory is exactly what
// makes the same dictionary in staged/abc/ and staged/def/ compare equal.
struct SourceFile {
    QString baseName;
    qint64 size = -1;    // -1 when the file is absent (matches stampSourceFiles)
    qint64 mtimeMs = -1; // -1 when the file is absent

    // A missing file is absent in both, so it compares equal - two copies of a
    // dictionary whose companion was never staged are still the same dictionary.
    bool sameContentAs(const SourceFile &o, qint64 mtimeToleranceMs) const {
        if (baseName != o.baseName || size != o.size)
            return false;
        if (mtimeMs < 0 || o.mtimeMs < 0)
            return true; // both absent; nothing to compare
        const qint64 delta = mtimeMs - o.mtimeMs;
        return (delta < 0 ? -delta : delta) <= mtimeToleranceMs;
    }
};

// Forward declaration: Identity::normalizedName() calls this, and the definition
// sits below the struct next to the other free functions.
inline QString normalizeName(const QString &raw);

struct Identity {
    QString name;           // display name, as the engine reports it
    QString primaryFile;    // absolute path of the primary source file
    QVector<SourceFile> files;
    int engineIndex = -1;

    // The match key. Format is deliberately NOT part of it: a .dsl and an .mdx
    // both reporting "Longman Pronunciation Dictionary" must collide, or the two
    // identically-named rows this removes would simply come back.
    QString normalizedName() const { return normalizeName(name); }
};

// Case-fold, trim, and collapse internal whitespace runs to a single space.
//
// A publisher's stray double space, a trailing newline, or a name differing only
// in case must not read as a different dictionary - these are the same title.
inline QString normalizeName(const QString &raw) {
    QString collapsed;
    collapsed.reserve(raw.size());
    bool pendingSpace = false;
    for (const QChar c : raw.trimmed()) {
        if (c.isSpace()) {
            pendingSpace = true; // hold it; emit only if more content follows
            continue;
        }
        if (pendingSpace) {
            collapsed += QLatin1Char(' ');
            pendingSpace = false;
        }
        collapsed += c;
    }
    return collapsed.toCaseFolded();
}

// True when two dictionaries hold the same content: the same set of file
// BASENAMES, each with the same size and an mtime within tolerance.
//
// This is deliberately NOT a hash. A digest cannot express "mtime drifted by
// less than tolerance", and that tolerance is specified behaviour: it is the same
// slack the importer uses to decide an unchanged file needs no re-copy. The file
// set is small (a dictionary is a handful of source files - resource trees are
// not part of it), so comparing component-wise costs nothing.
//
// Two dictionaries with NO files are not identical: an empty set is not evidence
// that anything was copied.
inline bool sameContent(const Identity &a, const Identity &b,
                        qint64 mtimeToleranceMs = kMtimeToleranceMs) {
    if (a.files.isEmpty() || b.files.isEmpty())
        return false;
    if (a.files.size() != b.files.size())
        return false;
    for (const SourceFile &fa : a.files) {
        const SourceFile *match = nullptr;
        for (const SourceFile &fb : b.files) {
            if (fb.baseName == fa.baseName) {
                match = &fb;
                break;
            }
        }
        // A file present in one set and absent from the other means one copy is
        // missing a volume (a .mdd, a .idx): that is a different dictionary,
        // however identical the files that ARE present look.
        if (!match || !fa.sameContentAs(*match, mtimeToleranceMs))
            return false;
    }
    return true;
}

// Parse one gd_dict_identity() record:
//   "D<TAB>name<TAB>primaryFilePath"
//   "F<TAB>basename<TAB>sizeBytes<TAB>mtimeMs"   (repeated, primary file first)
//
// The trailing fields are taken from the END of each record and everything in
// between rejoined, so a name or basename containing a TAB shifts nothing - a
// mis-parse would silently compare the wrong bytes. Returns an Identity with
// engineIndex left unset; caller fills it in.
inline Identity parseRecord(const QString &record) {
    Identity id;
    const QStringList lines = record.split(QLatin1Char('\n'), Qt::SkipEmptyParts);
    for (const QString &line : lines) {
        const QStringList f = line.split(QLatin1Char('\t'));
        if (f.isEmpty())
            continue;
        if (f.first() == QLatin1String("D") && f.size() >= 3) {
            id.name = f.mid(1, f.size() - 2).join(QLatin1Char('\t'));
            id.primaryFile = f.last();
        } else if (f.first() == QLatin1String("F") && f.size() >= 4) {
            SourceFile sf;
            sf.baseName = f.mid(1, f.size() - 3).join(QLatin1Char('\t'));
            sf.size = f.at(f.size() - 2).toLongLong();
            sf.mtimeMs = f.last().toLongLong();
            id.files.append(sf);
        }
    }
    return id;
}

// Group dictionaries by their match key. Within a group the order is the engine
// order the caller passed in, so "keep the first" is a stable, explainable rule
// rather than an arbitrary one.
inline QMap<QString, QVector<Identity>> groupByName(const QVector<Identity> &all) {
    QMap<QString, QVector<Identity>> groups;
    for (const Identity &id : all) {
        const QString key = id.normalizedName();
        if (key.isEmpty())
            continue; // an unnamed dictionary cannot be matched; never dedupe it
        groups[key].append(id);
    }
    return groups;
}

} // namespace DictIdentity
