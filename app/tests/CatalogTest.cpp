// Host-side tests for the remote-catalog manifest parser
// (remote-dictionary-catalog, tasks 1.2/1.3/2.6):
//   - the good fixture parses: three entries, derived sizes, and the
//     deliberately-missing-sha256 entry parses with an empty checksum (which
//     is what tells the download service to skip verification rather than
//     fail);
//   - installed-detection for the mdict pair is TRUE only when BOTH the .mdx
//     and the .mdd are present, so a half-installed pair never claims to be
//     installed;
//   - the DSL entry is installed by its single dictionary file, and its
//     optional resources bundle does not participate in the test;
//   - every malformed case in the bad fixture is rejected WHOLE: the document
//     is refused rather than half-populated, so a broken catalog cannot show a
//     partial list.
//
// Qt Core only, no network, no engine. Fixtures are read from disk relative to
// the source tree, so the test pins the checked-in files rather than an inline
// copy. Exit code 0 = all checks passed.

#include "RemoteCatalog.hpp"

#include <QCoreApplication>
#include <QByteArray>
#include <QDir>
#include <QFile>
#include <QStringList>

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

QByteArray readFixture(const QString &name) {
    QFile f(QStringLiteral(REMOTE_CATALOG_FIXTURE_DIR) + QLatin1Char('/') + name);
    if (!f.open(QIODevice::ReadOnly)) return QByteArray();
    return f.readAll();
}

const RemoteCatalog::Entry *findEntry(const RemoteCatalog::Manifest &m, const QString &id) {
    for (const RemoteCatalog::Entry &e : m.entries)
        if (e.id == id) return &e;
    return nullptr;
}

} // namespace

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);

    // ---- the good fixture (task 1.2) ----
    RemoteCatalog::Manifest m;
    QString error;
    const QByteArray good = readFixture(QStringLiteral("catalog.json"));
    check(!good.isEmpty(), "good fixture read");
    check(RemoteCatalog::parseManifest(good, &m, &error),
          QStringLiteral("good fixture parses (%1)").arg(error));
    check(m.schemaVersion == RemoteCatalog::kSchemaVersion, "schemaVersion is the supported one");
    check(m.entries.size() == 3,
          QStringLiteral("good fixture has three entries (got %1)").arg(m.entries.size()));

    if (m.entries.size() == 3) {
        // -- entry 1: DSL pair with an OPT-IN audio bundle --
        const RemoteCatalog::Entry *dsl = findEntry(m, QStringLiteral("kaikki-en-ru"));
        check(dsl != nullptr, "DSL entry present");
        if (dsl) {
            check(dsl->files.size() == 2, "DSL entry has two files (dictionary + resources)");
            check(dsl->requiredFiles().size() == 1, "exactly one required file");
            check(dsl->optionalFiles().size() == 1, "the audio bundle is optional");
            check(dsl->hasOptionalFiles(), "entry advertises optional files (Add audio)");
            check(dsl->dictionaryFiles().size() == 1, "one dictionary-role file");
            // Derived, not stored: 486539264 + 9663676416.
            check(dsl->totalBytes == 486539264LL + 9663676416LL,
                  QStringLiteral("total size derived from the file list (%1)").arg(dsl->totalBytes));
            check(dsl->requiredBytes == 486539264LL,
                  QStringLiteral("required size derived too (%1)").arg(dsl->requiredBytes));
            check(dsl->attribution.contains(QStringLiteral("Wiktionary")),
                  "attribution carried through");
            check(dsl->license == QStringLiteral("CC-BY-SA-4.0"), "license carried through");
        }

        // -- entry 2: mdict PAIR, the multi-file installed-detection case --
        const RemoteCatalog::Entry *mdx = findEntry(m, QStringLiteral("enwiktionary-mdict-en-de"));
        check(mdx != nullptr, "mdict entry present");
        if (mdx) {
            check(mdx->dictionaryFiles().size() == 2,
                  "both .mdx and .mdd are dictionary-role files");
            check(!mdx->hasOptionalFiles(), "mdict entry has no optional bundle");
            check(!RemoteCatalog::isInstalled(*mdx, {"enwiktionary-en-de.mdx"}),
                  "mdict pair is NOT installed with only the .mdx");
            check(!RemoteCatalog::isInstalled(*mdx, {"enwiktionary-en-de.mdd"}),
                  "mdict pair is NOT installed with only the .mdd");
            check(!RemoteCatalog::isInstalled(*mdx, {}),
                  "mdict pair is not installed with neither file");
            check(RemoteCatalog::isInstalled(
                      *mdx, {"some-other.dsl.dz", "enwiktionary-en-de.mdd",
                             "enwiktionary-en-de.mdx"}),
                  "mdict pair IS installed once both halves are present");
            check(RemoteCatalog::isInstalled(
                      *mdx, {"other/deep/path/enwiktionary-en-de.mdx",
                             "other/deep/path/enwiktionary-en-de.mdd"}),
                  "installed-detection matches on the basename, not the whole path");
        }

        // -- entry 3: deliberately missing sha256 --
        const RemoteCatalog::Entry *nosha = findEntry(m, QStringLiteral("collins-legacy-en-es"));
        check(nosha != nullptr, "no-checksum entry present");
        if (nosha) {
            check(nosha->files.size() == 1, "single file");
            check(nosha->files.first().sha256.isEmpty(),
                  "missing sha256 parses as empty (verification is skipped, not failed)");
            check(RemoteCatalog::isInstalled(*nosha, {"collins-legacy-en-es.dsl"}),
                  "no-checksum entry is installed by its dictionary file");
            check(nosha->installable, "no-checksum entry is installable");
        }

        // The optional audio bundle must not make the DSL entry "installed" by
        // itself -- installed-detection is about dictionary files only.
        if (dsl)
            check(!RemoteCatalog::isInstalled(*dsl, {"kaikki-en-ru.dsl.dz.files.zip"}),
                  "an entry with only its resources bundle is not installed");
    }

    // ---- contentHash (the staging directory name) ----
    {
        RemoteCatalog::Entry e;
        e.id = QStringLiteral("dsl-en-ru");
        RemoteCatalog::File dict;
        dict.name = QStringLiteral("dsl-en-ru.dsl.dz");
        dict.role = QStringLiteral("dictionary");
        dict.required = true;
        RemoteCatalog::File res;
        res.name = QStringLiteral("dsl-en-ru.dsl.dz.files.zip");
        res.role = QStringLiteral("resources");
        res.required = false;
        e.files = {dict, res};

        const QString h = RemoteCatalog::contentHash(e);
        check(h.size() == 32, "contentHash is 32 lowercase hex chars (MD5)");
        check(h == h.toLower(), "contentHash is lowercase");
        check(RemoteCatalog::contentHash(e) == h,
              "contentHash is stable across calls");

        // Order-independence: a manifest that lists the same required files in
        // the other order must hash identically, or re-ordering the document
        // would orphan an installed entry's files.
        RemoteCatalog::Entry reordered = e;
        reordered.files = {res, dict};
        check(RemoteCatalog::contentHash(reordered) == h,
              "contentHash ignores file order");

        // Optional files are NOT in the seed: adding audio to an installed
        // entry must reuse the same directory so the copies sit side by side.
        RemoteCatalog::Entry withAudio = e;
        withAudio.files.append(res);
        check(RemoteCatalog::contentHash(withAudio) == h,
              "contentHash ignores optional files (audio reuses the dir)");

        // Adding a REQUIRED file is a content change: it must move, or the new
        // dictionary would be written into the old one's directory.
        RemoteCatalog::Entry extra = e;
        RemoteCatalog::File mdd;
        mdd.name = QStringLiteral("dsl-en-ru.mdd");
        mdd.role = QStringLiteral("dictionary");
        mdd.required = true;
        extra.files.append(mdd);
        check(RemoteCatalog::contentHash(extra) != h,
              "contentHash changes when a required file is added");

        // Different ids must not collide, or two entries would share a directory.
        RemoteCatalog::Entry otherId = e;
        otherId.id = QStringLiteral("dsl-en-es");
        check(RemoteCatalog::contentHash(otherId) != h,
              "contentHash depends on the entry id");
    }

    // ---- the malformed fixture (task 1.3) ----
    {
        RemoteCatalog::Manifest bad;
        QString badError;
        const QByteArray raw = readFixture(QStringLiteral("catalog-malformed.json"));
        check(!raw.isEmpty(), "malformed fixture read");
        check(!RemoteCatalog::parseManifest(raw, &bad, &badError),
              "malformed fixture is REJECTED as a whole");
        check(bad.entries.isEmpty(),
              "a rejected document leaves no half-populated manifest behind");
        check(badError.contains(QStringLiteral("missing-url")),
              QStringLiteral("rejection names the missing-url entry (%1)").arg(badError));

        // Each malformed shape is rejected on its own too, so the message is
        // pinned per defect rather than only for whichever one comes first.
        const auto parseOne = [](const QByteArray &entryJson, QString *err) {
            QByteArray doc = QByteArrayLiteral("{\"schemaVersion\":1,\"entries\":[")
                             + entryJson + QByteArrayLiteral("]}");
            RemoteCatalog::Manifest tmp;
            return RemoteCatalog::parseManifest(doc, &tmp, err);
        };

        QString e1;
        check(!parseOne(R"({"id":"a","name":"A","langFrom":"en","langTo":"ru","files":[
                            {"role":"dictionary","required":true,"name":"a.dsl","sizeBytes":1}]})", &e1),
              "a file with no url is rejected");
        check(e1.contains(QStringLiteral("url")), QStringLiteral("...naming the missing key (%1)").arg(e1));

        QString e2;
        check(!parseOne(R"({"id":"b","name":"B","langFrom":"en","langTo":"ru","files":[
                            {"role":"dictionary","required":true,"name":"b.dsl",
                             "url":"https://x.example/b.dsl","sizeBytes":"1"}]})", &e2),
              "a non-numeric sizeBytes is rejected");
        check(e2.contains(QStringLiteral("sizeBytes")),
              QStringLiteral("...naming sizeBytes (%1)").arg(e2));

        QString e3;
        check(!parseOne(R"({"id":"c","name":"C","langFrom":"en","langTo":"ru","files":[
                            {"role":"index","required":true,"name":"c.mdx",
                             "url":"https://x.example/c.mdx","sizeBytes":1}]})", &e3),
              "an unknown role is rejected");
        check(e3.contains(QStringLiteral("role")),
              QStringLiteral("...naming the role (%1)").arg(e3));

        // Cleartext is refused at parse time: the app has no cleartext
        // exception for the catalog and never would (design D12).
        QString e4;
        check(!parseOne(R"({"id":"d","name":"D","langFrom":"en","langTo":"ru","files":[
                            {"role":"dictionary","required":true,"name":"d.dsl",
                             "url":"http://x.example/d.dsl","sizeBytes":1}]})", &e4),
              "a non-HTTPS url is rejected");

        // An entry whose files do not even CLAIM to include a required
        // dictionary has nothing to install, so the manifest is malformed.
        QString e5;
        check(!parseOne(R"({"id":"e","name":"E","langFrom":"en","langTo":"ru","files":[
                            {"role":"resources","required":false,"name":"e.zip",
                             "url":"https://x.example/e.zip","sizeBytes":1}]})", &e5),
              "an entry with no required dictionary role is rejected");

        // A required dictionary file in a format this build cannot load is NOT
        // fatal: it parses and is listed as not installable, so the user sees
        // why (RemoteCatalog.hpp). This is a valid future-catalog shape, not a
        // malformed document.
        QString e6;
        const QByteArray unsupportedDoc = QByteArrayLiteral(
            R"({"schemaVersion":1,"entries":[{"id":"f","name":"F","langFrom":"en","langTo":"ru","files":[{"role":"dictionary","required":true,"name":"f.epwing","url":"https://x.example/f.epwing","sizeBytes":1}]}]})");
        RemoteCatalog::Manifest unsupported;
        check(RemoteCatalog::parseManifest(unsupportedDoc, &unsupported, &e6),
              QStringLiteral("a required dictionary in an unsupported format still parses (%1)").arg(e6));
        check(unsupported.entries.size() == 1, "the unsupported entry is listed");
        check(!unsupported.entries.at(0).installable,
              "the unsupported entry is marked not installable");
        check(!unsupported.entries.at(0).unsupportedReason.isEmpty(),
              "the unsupported entry carries a reason");

        // A future schema version is refused whole rather than half-read.
        RemoteCatalog::Manifest future;
        QString e7;
        check(!RemoteCatalog::parseManifest(
                  QByteArrayLiteral("{\"schemaVersion\":99,\"entries\":[]}"), &future, &e7),
              "an unknown schemaVersion is rejected");

        // Garbage is rejected, not crashed on: the parser is total.
        RemoteCatalog::Manifest junk;
        QString e8;
        check(!RemoteCatalog::parseManifest(QByteArrayLiteral("not json at all"), &junk, &e8),
              "a non-JSON document is rejected");
        check(!RemoteCatalog::parseManifest(QByteArrayLiteral("[]"), &junk, &e8),
              "a non-object root is rejected");
        check(!RemoteCatalog::parseManifest(QByteArrayLiteral("{\"entries\":[]}"), &junk, &e8),
              "a missing schemaVersion is rejected");
    }

    // ---- free-space preflight tiers are one place and are what we think ----
    check(RemoteCatalog::kMinHeadroomBytes == 512LL * 1024 * 1024,
          "refuse tier is 512 MiB of headroom");
    check(RemoteCatalog::kWarnHeadroomBytes == 2LL * 1024 * 1024 * 1024,
          "warn tier is 2 GiB of headroom");

    std::fprintf(stdout, "%s: remote catalog\n", g_failures == 0 ? "PASS" : "FAIL");
    return g_failures == 0 ? 0 : 1;
}
