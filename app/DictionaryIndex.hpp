// Display-order vs engine-index helpers for the Dictionary list.
//
// EngineController::dictionaries() is sorted alphabetically for display, while
// the engine's gd_* functions (gd_dict_info, gd_dict_id, gd_remove_dict, ...)
// take an index into the engine's own order. Each exposed entry therefore
// carries its engine index as "engineIndex"; the reverse mapping and the safe
// removal order live here so they can be tested without the engine
// (fix-dictionary-removal-index-mismatch).
#pragma once

#include <QPair>
#include <QVariantList>
#include <QVariantMap>
#include <QVector>

#include <algorithm>

namespace DictionaryIndex {

// Engine index for the dictionary at display position `displayIndex`, or -1
// when the position is out of range or the entry carries no engine index.
inline int engineIndexForDisplay(const QVariantList &dictionaries, int displayIndex)
{
    if (displayIndex < 0 || displayIndex >= dictionaries.size())
        return -1;
    return dictionaries.at(displayIndex).toMap().value("engineIndex", -1).toInt();
}

// One dictionary to remove: its engine index plus the display position the
// caller used, so the caller can still read the entry's source path.
struct RemovalTarget {
    int engineIndex = -1;
    int displayIndex = -1;
};

// Resolve display positions to unique removal targets, ordered so that removing
// them in this order (highest engine index first) never shifts a target that
// has not been removed yet. Invalid/out-of-range positions are dropped.
inline QVector<RemovalTarget> removalTargets(const QVariantList &dictionaries,
                                             const QVariantList &displayIndices)
{
    QVector<RemovalTarget> out;
    out.reserve(displayIndices.size());
    for (const QVariant &v : displayIndices) {
        const int displayIndex = v.toInt();
        const int engineIndex = engineIndexForDisplay(dictionaries, displayIndex);
        if (engineIndex < 0)
            continue;
        const bool duplicate = std::any_of(
            out.begin(), out.end(),
            [engineIndex](const RemovalTarget &t){ return t.engineIndex == engineIndex; });
        if (duplicate)
            continue;
        out.append(RemovalTarget{engineIndex, displayIndex});
    }
    std::sort(out.begin(), out.end(), [](const RemovalTarget &a, const RemovalTarget &b){
        return a.engineIndex > b.engineIndex;
    });
    return out;
}

} // namespace DictionaryIndex
