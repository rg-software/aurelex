#include "RemoteCatalog.hpp"

#include <QFileInfo>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QJsonValue>
#include <QSet>

namespace RemoteCatalog {

// The formats the engine loads natively (v1 scope). Anything else in a
// `dictionary`-role file makes the entry not installable rather than failing
// the download.
//
// A StarDict dictionary is a SET of sibling files sharing a basename, so its
// companions are listed here alongside the `.ifo` header: the header alone
// carries no content (the reader fails with "No corresponding .idx file was
// found"). The suffixes are the lower-cased set engine/src/dict/stardict.cc
// resolves by basename; note there is no `.dict.gz` (dictzip is the only
// compressed definitions form). The resource archive forms the reader opens
// (res.zip / <base>.res.zip) join the list too.
//
// Keep in sync with isStardictCompanionName and isStardictResourceArchiveName
// in app/android/src/org/aurelex/pocket/dictionary/AurelexActivity.java — those
// gate what the SAF importer copies, and the two must not drift.
const char *const kDictionaryExtensions[] = {
    ".mdx", ".mdd", ".dsl", ".dsl.dz", ".ifo",
    ".idx", ".idx.gz", ".idx.dz", ".dict", ".dict.dz",
    ".syn", ".syn.gz", ".syn.dz",
    ".res.zip",
    nullptr // sentinel: lets a test assert the table and the count agree
};

bool isSupportedDictionaryName(const QString &name)
{
    const QString lower = name.toLower();
    // The bare "res.zip" the engine tries first (stardict.cc:1911) has no
    // leading dot, so endsWith(".res.zip") would miss it. The sibling
    // "<base>.res.zip" matches the table entry below.
    if (lower == QLatin1String("res.zip"))
        return true;
    for (int i = 0; i < kDictionaryExtensionCount; ++i)
        if (lower.endsWith(QLatin1String(kDictionaryExtensions[i])))
            return true;
    return false;
}

bool File::isDictionaryFormat() const
{
    return isSupportedDictionaryName(name);
}

namespace {

// A role the app can classify. "dictionary" participates in
// installed-detection; "resources" is opt-in. Anything else is rejected: the
// app cannot decide whether the file is required, and guessing would silently
// mis-detect installed state or fetch a multi-GB bundle unasked.
const char *const kKnownRoles[] = { "dictionary", "resources" };

bool isKnownRole(const QString &role)
{
    for (const char *r : kKnownRoles)
        if (role == QLatin1String(r))
            return true;
    return false;
}

// A basename, not a path: the engine only ever sees this name under
// files/staged/<contentHash>/, and a manifest that smuggles in a path
// separator or ".." is a manifest bug we refuse rather than resolve.
bool isValidFileName(const QString &name)
{
    if (name.isEmpty()) return false;
    if (name.contains(QLatin1Char('/')) || name.contains(QLatin1Char('\\')))
        return false;
    if (name == QLatin1String(".") || name == QLatin1String("..")) return false;
    return true;
}

// 64 lowercase hex characters, when present at all.
bool isValidSha256(const QString &s)
{
    if (s.isEmpty()) return false;
    if (s.size() != 64) return false;
    for (const QChar c : s) {
        const char ch = c.toLatin1();
        const bool hex = (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
        if (!hex) return false;
    }
    return true;
}

// ids and languages are restricted to a conservative identifier set: they end
// up in directory names (as the content-hash seed) and in the UI, and a stray
// control character or separator there is a bug we can catch at parse time.
bool isValidToken(const QString &s)
{
    if (s.isEmpty()) return false;
    for (const QChar c : s) {
        if (c.unicode() < 0x20) return false;
        if (c == QLatin1Char('/') || c == QLatin1Char('\\')) return false;
    }
    return true;
}

QString requireString(const QJsonObject &o, const QString &key, const QString &where,
                      QString *error)
{
    const QJsonValue v = o.value(key);
    if (v.isUndefined() || v.isNull()) {
        *error = QStringLiteral("%1: missing required \"%2\"").arg(where, key);
        return QString();
    }
    if (!v.isString()) {
        *error = QStringLiteral("%1: \"%2\" must be a string").arg(where, key);
        return QString();
    }
    const QString s = v.toString();
    if (s.trimmed().isEmpty()) {
        *error = QStringLiteral("%1: \"%2\" is empty").arg(where, key);
        return QString();
    }
    return s;
}

bool parseFile(const QJsonObject &o, const QString &where, File *out, QString *error)
{
    error->clear();
    const QString role = requireString(o, QStringLiteral("role"), where, error);
    if (!error->isEmpty()) return false;
    if (!isKnownRole(role)) {
        *error = QStringLiteral("%1: unknown role \"%2\" (expected \"dictionary\" "
                               "or \"resources\")").arg(where, role);
        return false;
    }
    out->role = role;

    const QJsonValue req = o.value(QStringLiteral("required"));
    if (!req.isBool()) {
        *error = QStringLiteral("%1: \"required\" must be a boolean").arg(where);
        return false;
    }
    out->required = req.toBool();

    out->name = requireString(o, QStringLiteral("name"), where, error);
    if (!error->isEmpty()) return false;
    if (!isValidFileName(out->name)) {
        *error = QStringLiteral("%1: \"name\" must be a bare file name, got \"%2\"")
                     .arg(where, out->name);
        return false;
    }

    out->url = requireString(o, QStringLiteral("url"), where, error);
    if (!error->isEmpty()) return false;
    if (!out->url.startsWith(QLatin1String("https://"), Qt::CaseInsensitive)) {
        *error = QStringLiteral("%1: \"url\" must be HTTPS, got \"%2\"")
                     .arg(where, out->url);
        return false;
    }

    const QJsonValue size = o.value(QStringLiteral("sizeBytes"));
    if (size.isUndefined() || size.isNull() || !size.isDouble()) {
        *error = QStringLiteral("%1: \"sizeBytes\" must be a number").arg(where);
        return false;
    }
    const double d = size.toDouble();
    // A hand-maintained size is unverified, but it must at least BE a whole
    // non-negative number of bytes: a fractional or negative value means the
    // manifest is wrong in a way that would corrupt the preflight.
    if (d < 1 || d != static_cast<double>(static_cast<qint64>(d))) {
        *error = QStringLiteral("%1: \"sizeBytes\" must be a positive whole number, "
                               "got %2").arg(where).arg(d);
        return false;
    }
    out->sizeBytes = static_cast<qint64>(d);

    const QJsonValue sha = o.value(QStringLiteral("sha256"));
    if (!sha.isUndefined() && !sha.isNull()) {
        if (!sha.isString()) {
            *error = QStringLiteral("%1: \"sha256\" must be a string").arg(where);
            return false;
        }
        out->sha256 = sha.toString().trimmed().toLower();
        if (!isValidSha256(out->sha256)) {
            *error = QStringLiteral("%1: \"sha256\" must be 64 lowercase hex "
                                   "characters").arg(where);
            return false;
        }
    }
    return true;
}

} // namespace

QVector<File> Entry::dictionaryFiles() const
{
    QVector<File> out;
    for (const File &f : files)
        if (f.role == QLatin1String("dictionary"))
            out.append(f);
    return out;
}

QVector<File> Entry::requiredFiles() const
{
    QVector<File> out;
    for (const File &f : files)
        if (f.required)
            out.append(f);
    return out;
}

QVector<File> Entry::optionalFiles() const
{
    QVector<File> out;
    for (const File &f : files)
        if (!f.required)
            out.append(f);
    return out;
}

QString Entry::nameFor(const QStringList &uiLanguages) const
{
    if (names.isEmpty())
        return name;
    for (const QString &ui : uiLanguages) {
        QString key = ui;
        key.replace(QLatin1Char('_'), QLatin1Char('-'));
        key = key.toLower();
        auto it = names.constFind(key);
        if (it != names.constEnd())
            return it.value();
        const int dash = key.indexOf(QLatin1Char('-'));
        if (dash > 0) {
            it = names.constFind(key.left(dash));
            if (it != names.constEnd())
                return it.value();
        }
    }
    return name;
}

bool parseManifest(const QByteArray &json, Manifest *out, QString *error)
{
    Manifest m;
    QString err;

    QJsonParseError pe {};
    const QJsonDocument doc = QJsonDocument::fromJson(json, &pe);
    if (pe.error != QJsonParseError::NoError) {
        if (error) *error = QStringLiteral("catalog is not valid JSON: %1").arg(pe.errorString());
        return false;
    }
    if (!doc.isObject()) {
        if (error) *error = QStringLiteral("catalog root is not a JSON object");
        return false;
    }
    const QJsonObject root = doc.object();

    const QJsonValue sv = root.value(QStringLiteral("schemaVersion"));
    if (!sv.isDouble()) {
        if (error) *error = QStringLiteral("catalog: missing numeric \"schemaVersion\"");
        return false;
    }
    m.schemaVersion = sv.toInt();
    if (m.schemaVersion != kSchemaVersion) {
        if (error) *error = QStringLiteral("catalog schemaVersion %1 is not supported "
                                          "(this build understands %2)")
                               .arg(m.schemaVersion).arg(kSchemaVersion);
        return false;
    }
    // Informational only: a missing/unparsable date is not a reason to hide the
    // whole catalog, so it is normalized to empty rather than rejected.
    m.updated = root.value(QStringLiteral("updated")).toString().trimmed();

    const QJsonValue ev = root.value(QStringLiteral("entries"));
    if (!ev.isArray()) {
        if (error) *error = QStringLiteral("catalog: \"entries\" must be an array");
        return false;
    }
    const QJsonArray entries = ev.toArray();

    QSet<QString> seenIds;
    for (int i = 0; i < entries.size(); ++i) {
        if (!entries.at(i).isObject()) {
            if (error) *error = QStringLiteral("entries[%1] is not an object").arg(i);
            return false;
        }
        const QJsonObject o = entries.at(i).toObject();
        const QString where = QStringLiteral("entries[%1]").arg(i);

        Entry e;
        e.id = requireString(o, QStringLiteral("id"), where, &err);
        if (!err.isEmpty()) { if (error) *error = err; return false; }
        if (!isValidToken(e.id)) {
            if (error) *error = QStringLiteral("%1: invalid id \"%2\"").arg(where, e.id);
            return false;
        }
        if (seenIds.contains(e.id)) {
            if (error) *error = QStringLiteral("%1: duplicate id \"%2\"").arg(where, e.id);
            return false;
        }
        seenIds.insert(e.id);
        const QString entryWhere = where + QStringLiteral(" (%1)").arg(e.id);

        e.name = requireString(o, QStringLiteral("name"), entryWhere, &err);
        if (!err.isEmpty()) { if (error) *error = err; return false; }
        e.langFrom = requireString(o, QStringLiteral("langFrom"), entryWhere, &err);
        if (!err.isEmpty()) { if (error) *error = err; return false; }
        e.langTo = requireString(o, QStringLiteral("langTo"), entryWhere, &err);
        if (!err.isEmpty()) { if (error) *error = err; return false; }
        e.attribution = o.value(QStringLiteral("attribution")).toString().trimmed();
        e.license = o.value(QStringLiteral("license")).toString().trimmed();

        // Optional localized display names: an object of language code -> name.
        const QJsonValue namesValue = o.value(QStringLiteral("names"));
        if (!namesValue.isUndefined() && !namesValue.isNull()) {
            if (!namesValue.isObject()) {
                if (error) *error = QStringLiteral("%1: \"names\" must be an object")
                                        .arg(entryWhere);
                return false;
            }
            const QJsonObject namesObj = namesValue.toObject();
            for (auto it = namesObj.begin(); it != namesObj.end(); ++it) {
                if (!it.value().isString()) {
                    if (error) *error = QStringLiteral("%1: names[\"%2\"] must be a string")
                                            .arg(entryWhere, it.key());
                    return false;
                }
                const QString value = it.value().toString().trimmed();
                if (!value.isEmpty())
                    e.names.insert(it.key().toLower(), value);
            }
        }

        const QJsonValue fv = o.value(QStringLiteral("files"));
        if (!fv.isArray()) {
            if (error) *error = QStringLiteral("%1: \"files\" must be an array").arg(entryWhere);
            return false;
        }
        const QJsonArray files = fv.toArray();
        if (files.isEmpty()) {
            if (error) *error = QStringLiteral("%1: \"files\" is empty").arg(entryWhere);
            return false;
        }
        QSet<QString> seenNames;
        for (int f = 0; f < files.size(); ++f) {
            if (!files.at(f).isObject()) {
                if (error) *error = QStringLiteral("%1: files[%2] is not an object")
                                        .arg(entryWhere).arg(f);
                return false;
            }
            File file;
            const QString fileWhere = QStringLiteral("%1 files[%2]").arg(entryWhere).arg(f);
            if (!parseFile(files.at(f).toObject(), fileWhere, &file, &err)) {
                if (error) *error = err;
                return false;
            }
            if (seenNames.contains(file.name)) {
                if (error) *error = QStringLiteral("%1: duplicate file name \"%2\"")
                                        .arg(entryWhere, file.name);
                return false;
            }
            seenNames.insert(file.name);
            e.files.append(file);
        }

        // Derived, never stored: sums over the file list, so a manifest cannot
        // declare a total that disagrees with its own files.
        e.totalBytes = 0;
        e.requiredBytes = 0;
        bool anyRequiredDictionaryRole = false;   // required file claiming role
                                                  // "dictionary", any extension
        bool anyLoadableDictionary = false;       // ...and in a format we load
        for (const File &file : e.files) {
            e.totalBytes += file.sizeBytes;
            if (file.required) {
                e.requiredBytes += file.sizeBytes;
                if (file.role == QLatin1String("dictionary")) {
                    anyRequiredDictionaryRole = true;
                    if (file.isDictionaryFormat())
                        anyLoadableDictionary = true;
                }
            }
        }
        // Two DIFFERENT failures, deliberately treated differently:
        //  - no required file even CLAIMS to be a dictionary: there is nothing
        //    to install, and the manifest is simply malformed -> reject whole.
        //  - a required dictionary file exists but in a format this build does
        //    not load (.epwing, .bgl, ...): a valid FUTURE catalog entry. It
        //    parses, is listed, and is marked not installable with the reason,
        //    so the user sees why instead of an entry that silently vanishes.
        if (!anyRequiredDictionaryRole) {
            if (error) *error = QStringLiteral("%1: no required file with role "
                                              "\"dictionary\"").arg(entryWhere);
            return false;
        }
        e.installable = anyLoadableDictionary;
        if (!anyLoadableDictionary)
            e.unsupportedReason = QStringLiteral(
                "requires a dictionary file in a format this build cannot load");
        // Optional bundles may be any blob (a .files.zip is not loadable by the
        // engine), so they never affect installability.

        m.entries.append(e);
    }

    if (out) *out = m;
    if (error) error->clear();
    return true;
}

bool isInstalled(const Entry &entry, const QStringList &installedSourcePaths){
    const QVector<File> dictFiles = entry.dictionaryFiles();
    if (dictFiles.isEmpty()) return false;
    // Basenames, taken here so every caller matches the same way.
    QSet<QString> have;
    for (const QString &p : installedSourcePaths)
        have.insert(QFileInfo(p).fileName());
    // EVERY dictionary file, not just the first: an mdict pair is only really
    // installed once its .mdd is there too.
    for (const File &f : dictFiles)
        if (!have.contains(f.name))
            return false;
    return true;
}

QString contentHash(const Entry &entry)
{
    QStringList names;
    for (const File &f : entry.requiredFiles())
        names.append(f.name);
    // Sorted so the hash does not depend on the order the manifest lists files
    // in: re-ordering a manifest must not orphan an installed entry's files.
    names.sort();
    QString seed = entry.id;
    for (const QString &n : names)
        seed += QLatin1Char('\n') + n;
    const QByteArray digest =
        QCryptographicHash::hash(seed.toUtf8(), QCryptographicHash::Md5);
    return QString::fromLatin1(digest.toHex());
}

} // namespace RemoteCatalog