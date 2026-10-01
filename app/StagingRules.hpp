// Staging-name classification for the importer's folder walk.
//
// The SAF staging walk is Java (AurelexActivity.stageTreeInto); it needs a real
// ContentResolver and so cannot run on the host. The rules that decide what is
// copied are therefore mirrored here, exactly as the extension list already is
// (RemoteCatalog::isSupportedDictionaryName mirrors the Java filter). This
// header covers the piece that is not an extension: recognising a resource
// DIRECTORY.
//
//   - DSL keeps a dictionary's sounds and inline images in a sibling
//     "<dict>.files" tree.
//   - StarDict keeps them in a sibling "res" (engine/src/dict/stardict.cc:1631),
//     but "res" is a common name, so it is resources ONLY when a StarDict .ifo
//     sits beside it in the same folder. Matching the name alone would copy any
//     unrelated "res" in a picked tree (see design.md).
//   - MDX ships some assets LOOSE, beside the .mdx rather than inside a .mdd;
//     the engine resolves those from the dictionary folder first
//     (engine/src/dict/mdx.cc:1336). Those files are staged only when a .mdx
//     sits beside them, for the same over-capture reason as "res".
//
// Mirrors isDslResourceDirName / isStardictResDirName / isMdxResourceFileName and
// the pre-scan in AurelexActivity.java. The device recipe that exercises the
// Java copy is docs/TESTING.md #8e; keep the two in step.
#pragma once

#include <QString>

namespace StagingRules {

// True when a directory named `name` is copied wholesale as a dictionary's
// resource tree. `stardictIfoSibling` is whether the containing folder holds a
// StarDict `.ifo` (the walker's pre-scan result); a "res" directory is only
// resources when it is true.
inline bool isResourceDirName(const QString &name, bool stardictIfoSibling)
{
    const QString lower = name.toLower();
    if (lower.endsWith(QLatin1String(".files")))
        return true;
    return stardictIfoSibling && lower == QLatin1String("res");
}

// True for an asset an MDX set may ship loose beside its `.mdx` instead of
// inside a `.mdd`. Bounded to extensions an article actually embeds, so an
// intersecting pick of a folder holding several dictionaries does not drag in
// unrelated media. `.otf` and audio are intentionally absent: no real fixture
// justifies them yet.
inline bool isMdxResourceFileName(const QString &name)
{
    const QString lower = name.toLower();
    return lower.endsWith(QLatin1String(".css")) || lower.endsWith(QLatin1String(".js"))
            || lower.endsWith(QLatin1String(".png")) || lower.endsWith(QLatin1String(".jpg"))
            || lower.endsWith(QLatin1String(".jpeg")) || lower.endsWith(QLatin1String(".gif"))
            || lower.endsWith(QLatin1String(".svg")) || lower.endsWith(QLatin1String(".ttf"))
            || lower.endsWith(QLatin1String(".woff")) || lower.endsWith(QLatin1String(".woff2"));
}

} // namespace StagingRules
