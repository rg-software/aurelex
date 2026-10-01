// Host-side tests for the staging resource rules (StagingRules.hpp):
//   - a DSL "<dict>.files" tree is resources regardless of what else is around;
//   - a StarDict "res" directory is resources ONLY beside a `.ifo`, so an
//     unrelated "res" in a picked tree is not copied (the scoping guard);
//   - the match is exact and case-insensitive;
//   - an MDX set's loose assets (stylesheet, images, fonts) are recognised, and
//     the list stays bounded so an intersecting pick does not drag in unrelated
//     media (verify-mdx-import).
//
// Header-only, Qt Core only, no engine. The Java walk this mirrors is not host-
// runnable; docs/TESTING.md #8e covers the Java copy on device.
// Exit code 0 = all checks passed.

#include "StagingRules.hpp"

#include <QCoreApplication>
#include <QString>

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

} // namespace

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);

    // ---- DSL ".files" trees: name alone decides ----
    check(StagingRules::isResourceDirName(QStringLiteral("word.dsl.files"), false),
          "a DSL <dict>.files tree is resources even without a StarDict sibling");
    check(StagingRules::isResourceDirName(QStringLiteral("word.dsl.files"), true),
          "a DSL <dict>.files tree is resources beside a StarDict dictionary too");
    check(StagingRules::isResourceDirName(QStringLiteral("WORD.DSL.FILES"), false),
          "the .files match is case-insensitive");

    // ---- StarDict "res": only beside a `.ifo` ----
    check(StagingRules::isResourceDirName(QStringLiteral("res"), true),
          "a res directory beside a StarDict .ifo is resources");
    check(StagingRules::isResourceDirName(QStringLiteral("RES"), true),
          "the res match is case-insensitive");
    check(!StagingRules::isResourceDirName(QStringLiteral("res"), false),
          "an unrelated res directory (no .ifo beside it) is NOT resources");

    // ---- exactness: look-alikes are not resource trees ----
    check(!StagingRules::isResourceDirName(QStringLiteral("myres"), true),
          "a directory merely ending in 'res' is not the resource tree");
    check(!StagingRules::isResourceDirName(QStringLiteral("resources"), true),
          "a 'resources' directory is not the StarDict resource tree");
    check(!StagingRules::isResourceDirName(QStringLiteral("res.zip"), true),
          "a directory named res.zip is not the resource tree (the engine wants a file)");
    check(!StagingRules::isResourceDirName(QString(), true),
          "an empty name is never a resource tree");

    // ---- MDX loose assets, as shipped by Collins Dictionary of Law 2nd ed ----
    check(StagingRules::isMdxResourceFileName(QStringLiteral("collinslaw.css")),
          "a loose stylesheet beside an .mdx is a dictionary resource");
    check(StagingRules::isMdxResourceFileName(QStringLiteral("collinslaw2ed.jpg")),
          "a loose cover image beside an .mdx is a dictionary resource");
    check(StagingRules::isMdxResourceFileName(QStringLiteral("style.CSS")),
          "the MDX resource match is case-insensitive");

    // The real references these dictionaries emit, including the shapes that
    // carry spaces and commas in the path.
    check(StagingRules::isMdxResourceFileName(
              QStringLiteral("William J. Stewart, Robert Burgess - Collins Dictionary of Law (2001)"
                             "/Image_106.png")),
          "a nested image under a space- and comma-bearing folder is a resource");

    // ---- the bound: only extensions an article embeds ----
    check(!StagingRules::isMdxResourceFileName(QStringLiteral("notes.txt")),
          "an unrelated .txt beside a dictionary is NOT staged");
    check(!StagingRules::isMdxResourceFileName(QStringLiteral("backup.zip")),
          "an unrelated archive beside a dictionary is NOT staged");
    check(!StagingRules::isMdxResourceFileName(QStringLiteral("dict.mdx")),
          "the .mdx itself is a dictionary, not a resource (matched by the name filter)");
    check(!StagingRules::isMdxResourceFileName(QStringLiteral("dict.mdd")),
          "the .mdd is a dictionary, not a resource (matched by the name filter)");
    check(!StagingRules::isMdxResourceFileName(QStringLiteral("cover.otf")),
          ".otf is deliberately not on the list until a fixture justifies it");
    check(!StagingRules::isMdxResourceFileName(QStringLiteral("pronounce.mp3")),
          "loose audio is deliberately not on the list until a fixture justifies it");
    check(!StagingRules::isMdxResourceFileName(QString()),
          "an empty name is never an MDX resource");

    std::fprintf(stdout, "%s: staging rules\n", g_failures == 0 ? "PASS" : "FAIL");
    return g_failures == 0 ? 0 : 1;
}
