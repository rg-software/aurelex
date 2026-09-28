// Host-side tests for the display-order -> engine-index mapping used by
// dictionary removal (fix-dictionary-removal-index-mismatch):
//   - engineIndexForDisplay reads the engine index carried on an entry;
//   - removalTargets drops invalid positions and duplicates;
//   - removalTargets is ordered highest-engine-index-first, so removing its
//     targets in order never shifts a not-yet-removed dictionary.
//
// Header-only, Qt Core only, no engine - mirrors IndexCleanupTest.cpp.
// Exit code 0 = all checks passed.

#include "DictionaryIndex.hpp"

#include <QCoreApplication>

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

// Build the model shape EngineController exposes: a name-sorted list where each
// entry carries the engine index it came from.
QVariantList model(const QList<QPair<int, QString>> &engineToName) {
    QVariantList list;
    for (const auto &e : engineToName) {
        QVariantMap m;
        m.insert("engineIndex", e.first);
        m.insert("name", e.second);
        list.append(m);
    }
    return list;
}

} // namespace

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);

    // ---- engineIndexForDisplay ----
    {
        // Display order deliberately differs from engine order:
        // display 0 -> engine 7, display 1 -> engine 2, display 2 -> engine 5.
        const QVariantList dicts = model({
            {7, QStringLiteral("Aurelex Basic")},
            {2, QStringLiteral("Aurelex Basic (DZ)")},
            {5, QStringLiteral("Aurelex Lingvo EN-RU")},
        });
        check(DictionaryIndex::engineIndexForDisplay(dicts, 0) == 7, "display 0 maps to engine 7");
        check(DictionaryIndex::engineIndexForDisplay(dicts, 1) == 2, "display 1 maps to engine 2");
        check(DictionaryIndex::engineIndexForDisplay(dicts, 2) == 5, "display 2 maps to engine 5");
        check(DictionaryIndex::engineIndexForDisplay(dicts, -1) == -1, "negative display index is invalid");
        check(DictionaryIndex::engineIndexForDisplay(dicts, 3) == -1, "past-the-end display index is invalid");

        QVariantMap noIndex;
        noIndex.insert("name", QStringLiteral("no index"));
        check(DictionaryIndex::engineIndexForDisplay({noIndex}, 0) == -1,
              "entry with no engineIndex is invalid");
    }

    // ---- removalTargets: order, mapping, dedupe ----
    {
        const QVariantList dicts = model({
            {7, QStringLiteral("Aurelex Basic")},
            {2, QStringLiteral("Aurelex Basic (DZ)")},
            {5, QStringLiteral("Aurelex Lingvo EN-RU")},
        });
        // Select display 0 (engine 7) and display 1 (engine 2). The result must
        // be engine 7 first, so removing it cannot shift engine 2 before it is
        // removed.
        const QVector<DictionaryIndex::RemovalTarget> targets =
            DictionaryIndex::removalTargets(dicts, QVariantList{0, 1});
        check(targets.size() == 2, QStringLiteral("two targets resolved (got %1)").arg(targets.size()));
        if (targets.size() == 2) {
            check(targets[0].engineIndex == 7 && targets[0].displayIndex == 0,
                  "highest engine index first, with its display position");
            check(targets[1].engineIndex == 2 && targets[1].displayIndex == 1,
                  "lower engine index second, with its display position");
        }

        // Reverse selection order must not change the removal order.
        const QVector<DictionaryIndex::RemovalTarget> reversed =
            DictionaryIndex::removalTargets(dicts, QVariantList{1, 0});
        check(reversed.size() == 2 && reversed[0].engineIndex == 7
                  && reversed[1].engineIndex == 2,
              "selection order does not change removal order");
    }

    // ---- removalTargets: invalid positions and duplicates dropped ----
    {
        const QVariantList dicts = model({
            {4, QStringLiteral("A")},
            {9, QStringLiteral("B")},
        });
        const QVector<DictionaryIndex::RemovalTarget> targets =
            DictionaryIndex::removalTargets(dicts, QVariantList{1, 1, 5, -3, 0});
        check(targets.size() == 2, QStringLiteral("duplicates/out-of-range dropped (got %1)").arg(targets.size()));
        if (targets.size() == 2) {
            check(targets[0].engineIndex == 9, "engine 9 first");
            check(targets[1].engineIndex == 4, "engine 4 second");
        }
    }

    // ---- removalTargets: empty selection ----
    {
        const QVariantList dicts = model({{0, QStringLiteral("A")}});
        check(DictionaryIndex::removalTargets(dicts, QVariantList{}).isEmpty(),
              "empty selection yields no targets");
        check(DictionaryIndex::removalTargets({}, QVariantList{0, 1}).isEmpty(),
              "empty model yields no targets");
    }

    std::fprintf(stdout, "%s: dictionary index mapping\n", g_failures == 0 ? "PASS" : "FAIL");
    return g_failures == 0 ? 0 : 1;
}
