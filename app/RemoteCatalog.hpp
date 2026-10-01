#pragma once

#include <QByteArray>
#include <QString>
#include <QStringList>
#include <QVector>

// RemoteCatalog: the manifest contract for the curated remote dictionary
// catalog (remote-dictionary-catalog), plus the pure logic the app and the
// download service both need: a total parser, derived entry sizes, and
// installed-detection.
//
// This header is deliberately free of Qt Network / engine dependencies so the
// host-side unit test (app/tests/CatalogTest.cpp) can link it against a plain
// desktop Qt Core. Fetching is EngineController's job; transferring is the
// Android DictionaryDownloadService's job.
//
// ---------------------------------------------------------------------------
// MANIFEST SCHEMA (schemaVersion 1)
// ---------------------------------------------------------------------------
//
// The catalog is ONE static, hand-authored JSON document fetched over HTTPS
// from a URL compiled into the app. There is no discovery, no scraping, no
// account, and no entry versioning or update checking.
//
//   {
//     "schemaVersion": 1,                  // int, required, must be 1
//     "updated": "2026-09-26",             // ISO date, optional (informational)
//     "entries": [ ... ]                   // array, required, may be empty
//   }
//
// entries[] elements:
//
//   id           string, required, non-empty, unique within the document,
//                matching [A-Za-z0-9._-]+. Stable forever: renaming an id
//                breaks installed-detection for anyone who already installed
//                the old name, so entries are append-only by convention.
//   name         string, required, non-empty. Display name shown in the list.
//   langFrom     string, required, non-empty. Source language code.
//   langTo       string, required, non-empty. Target language code.
//   attribution  string, optional. Required by the upstream data licence;
//                shown next to the entry. Defaults to "".
//   license      string, optional SPDX-ish id, e.g. "CC-BY-SA-4.0". Defaults
//                to "".
//   files[]      array, required, at least one element.
//
// files[] elements:
//
//   role       string, required, one of "dictionary" | "resources". "dictionary"
//              is a file the engine loads (a .mdx/.mdd/.dsl/.dsl.dz/.ifo);
//              "resources" is a companion bundle (a DSL <dict>.files.zip of
//              sounds/images). An UNRECOGNISED role rejects the document: the
//              app has to know whether a file participates in
//              installed-detection (dictionary) or is opt-in (resources), and a
//              role it cannot classify is a manifest bug, not a new bundle
//              type. Adding one later is a one-line change to kKnownRoles.
//   required   bool, required. false is what makes a bundle opt-in (audio).
//   name       string, required, non-empty BASENAME: no path separators, no
//              "..". This is the file name the engine will see under
//              files/staged/<contentHash>/ and the value installed-detection
//              matches against.
//   url        string, required, non-empty, MUST be https:// (the app is
//              HTTPS-only; network_security_config.xml has no cleartext
//              exception for the catalog and none is added).
//   sizeBytes  number, required, integer, > 0. Always present: it drives the
//              free-space preflight and the progress total. Hand-maintained, so
//              it is NOT verified — the transfer is bounded by the server's
//              Content-Length and a mismatch is a non-fatal warning.
//   sha256     string, OPTIONAL: 64 lowercase hex characters. Present -> the
//              downloaded file is verified and rejected on mismatch. Absent ->
//              accepted without verification (best-effort integrity, so the
//              first maintainer mistake is not a download that fails with no
//              way to tell a corrupt transfer from a wrong hash).
//
// Entry-level rules: at least one file with role "dictionary" and
// required: true (otherwise there is nothing to install), and the whole
// document is rejected if ANY entry is malformed. The parser is TOTAL: it
// returns false with a message rather than throwing or half-populating a
// manifest, so a bad catalog disables the feature instead of producing a
// half-populated, silently-wrong list.
//
// There is no total size in the manifest: entry totalBytes / requiredBytes are
// DERIVED by summing the file list, so they cannot drift from it.
//
// ---------------------------------------------------------------------------
// HOSTING
// ---------------------------------------------------------------------------
//
// Hosted on GitHub Pages (docs/REMOTE-CATALOG.md carries the maintainer
// how-to and the full rationale). GitHub Pages over raw.githubusercontent.com
// because: the URL is decoupled from a branch or tag name, so renaming or
// deleting a branch cannot break every installed app; it is served from a CDN
// with proper HTTP semantics (strong ETag + Last-Modified) rather than raw
// content's abuse throttling; and its cache headers are ours to reason about.
// The cost is one more moving part (a Pages deploy) in exchange for a URL that
// never rots, which is the right trade for a document every install reads.
// Practical consequence for the app: Pages caches aggressively, so re-probing
// on every Dictionaries-pane visit would be wasteful. The probe therefore runs
// on an explicit refresh and on first open after the cached copy's age passes
// kCatalogRereprobeMs; a stale-but-present cache still renders the list.
//
// ---------------------------------------------------------------------------
// SHARED IDENTITIES
// ---------------------------------------------------------------------------
//
// contentHash(entry) is the staging directory name used by the Android
// DictionaryDownloadService for files/staging-tmp/<h> and
// files/staged/<h>. It is derived from CONTENT identity — the entry id plus
// the sorted names of its required files — never from the URL, so re-downloading
// the same entry to the same path is a clean no-op (the engine's dictionary id
// is an MD5 over absolute source paths, so a path derived from the URL would
// produce a DUPLICATE list row on re-install). The Java implementation lives
// in DictionaryDownloadService.contentHashFor(); the recipe is stated there so
// the two sides cannot drift.
namespace RemoteCatalog {

// A single downloadable file inside an entry.
struct File {
    // "dictionary" (engine-loadable) or "resources" (opt-in companion bundle).
    QString role;
    // false makes the file opt-in: never fetched unless the user asks.
    bool required = false;
    // Basename; also the value installed-detection matches.
    QString name;
    // Always https://.
    QString url;
    // Hand-maintained; drives preflight + progress. Never a trust boundary.
    qint64 sizeBytes = 0;
    // Empty when the catalog supplies none -> skip verification.
    QString sha256;
    // Extension the engine can actually load (mdx/mdd/dsl/dsl.dz/ifo). A file
    // without one is a companion/resource blob, not a dictionary source.
    bool isDictionaryFormat() const;
};

// One installable entry.
struct Entry {
    QString id;
    QString name;
    QString langFrom;
    QString langTo;
    QString attribution;
    QString license;
    QVector<File> files;

    // DERIVED (never read from the manifest): sum of every file, and of the
    // required files only. The list shows the total so the user knows the size
    // of what is actually offered; the preflight reserves the required sum
    // plus headroom.
    qint64 totalBytes = 0;
    qint64 requiredBytes = 0;

    // False when no required file is in a format the engine can load, so the
    // entry cannot be installed at all. The catalog still parses (a bad entry
    // is reported, not silently dropped) and the list marks it not installable
    // rather than letting the user start a doomed download.
    bool installable = true;
    QString unsupportedReason;

    QVector<File> dictionaryFiles() const;
    QVector<File> requiredFiles() const;
    QVector<File> optionalFiles() const;
    // True when the entry can still gain something after it is installed, i.e.
    // it has an optional bundle the user has not asked for yet.
    bool hasOptionalFiles() const { return !optionalFiles().isEmpty(); }
};

// A parsed, validated document.
struct Manifest {
    int schemaVersion = 0;
    QString updated;
    QVector<Entry> entries;
};

// The schema version this build understands. A document declaring anything
// else is rejected whole (the app is not going to guess at a shape it has never
// seen).
inline constexpr int kSchemaVersion = 1;

// Dictionary file extensions the engine loads, lowercase and WITH the dot.
// Includes a StarDict dictionary's companion files (see the comment on the
// definition in RemoteCatalog.cpp): a StarDict entry is a set, not one file.
// The array is nullptr-terminated so a test can assert this count matches it.
extern const char *const kDictionaryExtensions[];
inline constexpr int kDictionaryExtensionCount = 13;

/** True when `name` ends in a format this build can install. */
bool isSupportedDictionaryName(const QString &name);

/**
 * Parse a manifest document. TOTAL: on any malformed entry this returns false,
 * leaves *out untouched, and sets *error to a message naming the offending
 * entry/file. Never throws, never partially populates.
 */
bool parseManifest(const QByteArray &json, Manifest *out, QString *error);

/**
 * Installed-detection: true when EVERY file with role "dictionary" has its
 * basename present among the basenames of `installedSourcePaths` (i.e. the
 * `source` values of dictionaries()). Matching the file LIST rather than a
 * single primary file is what makes an mdict pair (.mdx + .mdd) report
 * installed only when both halves are present.
 *
 * `installedSourcePaths` takes the sources VERBATIM — the basename step is done
 * here so a caller cannot accidentally pass full paths and get a
 * silently-wrong "not installed".
 */
bool isInstalled(const Entry &entry, const QStringList &installedSourcePaths);

/**
 * The staging directory name for `entry`: files/staging-tmp/<h> and
 * files/staged/<h> both use it.
 *
 * Derived from CONTENT identity — the entry id plus the SORTED names of its
 * required files — never from the URL. That matters because the engine's
 * dictionary id is an MD5 over the absolute source paths
 * (engine/src/dict/dictionary.cc, makeDictionaryId), so a path derived from
 * anything but the content would yield a different id for the same dictionary
 * and a DUPLICATE row in the list on re-install. Sorting makes the hash
 * independent of the order the manifest happens to list files in.
 *
 * Optional files are deliberately NOT part of the seed: adding audio to an
 * already-installed entry reuses the same directory, so the installed copy and
 * the new resources end up side by side.
 *
 * RECIPE (mirrored in DictionaryDownloadService.contentHashFor, which needs it
 * to recognise orphaned scratch dirs on a later run): MD5 over
 * `id + "\n" + join("\n", sorted(required file names))`, lowercase hex.
 */
QString contentHash(const Entry &entry);

// --- Free-space preflight constants (design D5). Both live here, in one place,
// tuned from real devices. The rename out of staging-tmp is same-volume, so
// there is no 2x doubling penalty to reserve; the 2 GiB tier exists because the
// automatic full-text build that follows needs room we cannot predict for a
// multi-GB dictionary. Mirrored by DictionaryDownloadService.MIN_HEADROOM_BYTES
// / WARN_HEADROOM_BYTES.

/** Below bundle + this, REFUSE the download and name the shortfall. */
inline constexpr qint64 kMinHeadroomBytes = 512LL * 1024 * 1024;
/** Below bundle + this, WARN and ask before proceeding. */
inline constexpr qint64 kWarnHeadroomBytes = 2LL * 1024 * 1024 * 1024;

} // namespace RemoteCatalog
