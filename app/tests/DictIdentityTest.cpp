// Host-side tests for dictionary identity (resolve-duplicate-dictionaries):
//   - name normalization: case, surrounding and repeated internal whitespace;
//   - content comparison: file SETS (not just the primary), the 5000 ms mtime
//     tolerance, absent files, and the guarantee that an empty set is not
//     evidence of equality;
//   - the identity record round-trip, including a TAB inside a name or basename;
//   - grouping by match key, including the unnamed dictionary that must never be
//     deduplicated.
//
// Header-only, Qt Core only, no engine - mirrors StagedCleanupTest.cpp.
// Exit code 0 = all checks passed.

#include "DictIdentity.hpp"

#include <QCoreApplication>

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

DictIdentity::SourceFile file(const QString &base, qint64 size, qint64 mtime) {
    DictIdentity::SourceFile sf;
    sf.baseName = base;
    sf.size = size;
    sf.mtimeMs = mtime;
    return sf;
}

DictIdentity::Identity dict(const QString &name,
                            const QVector<DictIdentity::SourceFile> &files,
                            int index = 0) {
    DictIdentity::Identity id;
    id.name = name;
    id.files = files;
    id.engineIndex = index;
    return id;
}

} // namespace

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);

    // ---- name normalization -------------------------------------------------
    check(DictIdentity::normalizeName(QStringLiteral("Longman Pronunciation"))
              == DictIdentity::normalizeName(QStringLiteral("longman pronunciation")),
          "names differing only in case are one name");
    check(DictIdentity::normalizeName(QStringLiteral("  Longman  \n"))
              == DictIdentity::normalizeName(QStringLiteral("longman")),
          "leading, trailing and doubled whitespace collapse");
    check(DictIdentity::normalizeName(QStringLiteral("a\tb")) == DictIdentity::normalizeName(QStringLiteral("a b")),
          "a tab inside a name normalizes like a space");
    check(!DictIdentity::normalizeName(QStringLiteral("Longman Pronunciation"))
              .isEmpty(),
          "a real name is not empty");
    check(DictIdentity::normalizeName(QStringLiteral("   ")).isEmpty(),
          "a whitespace-only name normalizes to empty, so it is never a match key");

    // ---- content comparison -------------------------------------------------
    const QVector<DictIdentity::SourceFile> set = {
        file(QStringLiteral("longman.mdd"), 1024, 1700000000000LL),
        file(QStringLiteral("longman.mdx"), 4096, 1700000000000LL)};

    check(DictIdentity::sameContent(dict(QStringLiteral("A"), set),
                                    dict(QStringLiteral("B"), set)),
          "identical file sets are the same content");
    check(DictIdentity::sameContent(
              dict(QStringLiteral("A"), set),
              dict(QStringLiteral("B"),
                   {file(QStringLiteral("longman.mdd"), 1024, 1700000000000LL),
                    file(QStringLiteral("longman.mdx"), 4096, 1700000004000LL)})),
          "an mtime drift inside the 5000 ms tolerance is still the same content");
    check(!DictIdentity::sameContent(
              dict(QStringLiteral("A"), set),
              dict(QStringLiteral("B"),
                   {file(QStringLiteral("longman.mdd"), 1024, 1700000000000LL),
                    file(QStringLiteral("longman.mdx"), 4096, 1700000009000LL)})),
          "an mtime drift beyond the tolerance means differing content");
    check(!DictIdentity::sameContent(
              dict(QStringLiteral("A"), set),
              dict(QStringLiteral("B"),
                   {file(QStringLiteral("longman.mdd"), 1024, 1700000000000LL),
                    file(QStringLiteral("longman.mdx"), 4097, 1700000000000LL)})),
          "a different file size means differing content even at an identical mtime");
    check(!DictIdentity::sameContent(
              dict(QStringLiteral("A"), set),
              dict(QStringLiteral("B"),
                   {file(QStringLiteral("longman.mdx"), 4096, 1700000000000LL)})),
          "a copy missing a volume is a different dictionary");
    check(!DictIdentity::sameContent(
              dict(QStringLiteral("A"), set),
              dict(QStringLiteral("B"),
                   {file(QStringLiteral("longman.mdx"), 4096, 1700000000000LL),
                    file(QStringLiteral("other.mdd"), 1024, 1700000000000LL)})),
          "the same volumes under different basenames are a different dictionary");
    // A file the engine lists but that is gone from disk reports -1 for BOTH size
    // and mtime (one exists() check), so absent in both copies is the same fact
    // about both and must not be what makes them differ.
    const QVector<DictIdentity::SourceFile> oneGone = {
        file(QStringLiteral("a.mdd"), -1, -1),
        file(QStringLiteral("a.mdx"), 4096, 1700000000000LL)};
    const QVector<DictIdentity::SourceFile> onePresent = {
        file(QStringLiteral("a.mdd"), 1024, 1700000000000LL),
        file(QStringLiteral("a.mdx"), 4096, 1700000000000LL)};
    check(DictIdentity::sameContent(dict(QStringLiteral("A"), oneGone),
                                    dict(QStringLiteral("B"), oneGone)),
          "a file absent from both copies does not by itself make them differ");
    check(!DictIdentity::sameContent(dict(QStringLiteral("A"), onePresent),
                                     dict(QStringLiteral("B"), oneGone)),
          "a file present in one copy and absent from the other means differing");
    check(!DictIdentity::sameContent(dict(QStringLiteral("A"), set),
                                     dict(QStringLiteral("B"), {})),
          "an empty file set is not evidence that anything was copied");
    check(DictIdentity::kMtimeToleranceMs == 5000,
          "the tolerance is the 5000 ms the importer already applies");

    // ---- record round-trip --------------------------------------------------
    const QString record =
        QStringLiteral("D\tLongman Pronunciation\t/app/files/staged/abc/longman.mdx\n"
                       "F\tlongman.mdd\t1024\t1700000000000\n"
                       "F\tlongman.mdx\t4096\t1700000000000");
    const DictIdentity::Identity parsed = DictIdentity::parseRecord(record);
    check(parsed.name == QStringLiteral("Longman Pronunciation"),
          "the name round-trips out of the D record");
    check(parsed.primaryFile == QStringLiteral("/app/files/staged/abc/longman.mdx"),
          "the primary path round-trips out of the D record");
    check(parsed.files.size() == 2 && parsed.files.at(0).baseName == QStringLiteral("longman.mdd")
              && parsed.files.at(0).size == 1024 && parsed.files.at(0).mtimeMs == 1700000000000LL,
          "the F records round-trip size and mtime");

    // A TAB inside a name would shift the fields if the trailing ones were read
    // positionally. It must not be able to corrupt the comparison.
    const DictIdentity::Identity tabbed = DictIdentity::parseRecord(
        QStringLiteral("D\tOdd\tName\t/app/staged/x/d.mdx\nF\twe\tird.dsl\t10\t20"));
    check(tabbed.name == QStringLiteral("Odd\tName"),
          "a TAB in a name is preserved rather than shifting the fields");
    check(tabbed.primaryFile == QStringLiteral("/app/staged/x/d.mdx"),
          "a TAB in a name does not corrupt the primary path");
    check(tabbed.files.size() == 1 && tabbed.files.at(0).baseName == QStringLiteral("we\tird.dsl")
              && tabbed.files.at(0).size == 10 && tabbed.files.at(0).mtimeMs == 20,
          "a TAB in a basename does not corrupt size or mtime");

    // ---- grouping -----------------------------------------------------------
    const QVector<DictIdentity::Identity> all = {
        dict(QStringLiteral("Longman Pronunciation Dictionary"), set, 0),
        dict(QStringLiteral("  longman   pronunciation dictionary "), set, 1),
        dict(QStringLiteral("Collins"), {}, 2),
        dict(QStringLiteral("   "), set, 3)};
    const QMap<QString, QVector<DictIdentity::Identity>> groups =
        DictIdentity::groupByName(all);
    check(groups.size() == 2,
          "two distinct names group, and the unnamed dictionary is left out");
    check(groups.value(DictIdentity::normalizeName(QStringLiteral("Longman Pronunciation Dictionary"))).size() == 2,
          "the two copies of one title land in one group");
    check(groups.value(DictIdentity::normalizeName(QStringLiteral("Collins"))).size() == 1,
          "a unique title forms a group of one, which is never a duplicate");

    if (g_failures) {
        std::fprintf(stderr, "\n%d check(s) failed\n", g_failures);
        return 1;
    }
    std::fprintf(stdout, "\nDICT_IDENTITY OK\n");
    return 0;
}
