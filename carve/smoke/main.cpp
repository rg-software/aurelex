// Aurelex spike smoke test — host build.
// Links the carved engine + boundary and exercises the gd_* C API against a
// synthetic StarDict dictionary, printing results. This validates the whole
// carve + boundary end-to-end without a device.
#include "goldendict.h"
#include "index_path.hpp"
#include "DictIdentity.hpp"

#include <QDir>
#include <QCoreApplication>
#include <QFile>
#include <QFileInfo>
#include <QStringList>
#include <QThread>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

// The resource the "badge" headword of aurelex-basic references. Must match
// RESOURCE_NAME in scripts/make-example-dicts.py.
static const char * kFixtureResource = "aurelex-resource.svg";

// Rewrite one group's name directly in <configDir>/groups.json. The boundary
// exposes no way to edit the stored file behind the API's back, and the groups
// smoke needs one: a scan must reload the STORED group set, not merge into the
// in-memory one, and the only way to tell those apart is to change what is
// stored and check the app follows it. Returns false when the file or the name
// is not found, which fails the assertion that uses it.
static bool rewriteGroupName( const char * configDir, const char * from, const char * to )
{
  std::ostringstream path;
  path << configDir << "/groups.json";
  std::ifstream in( path.str().c_str(), std::ios::binary );
  if ( !in )
    return false;
  std::ostringstream buf;
  buf << in.rdbuf();

  std::string json = buf.str();
  const std::string needle = std::string( "\"name\":\"" ) + from + "\"";
  const std::string::size_type at = json.find( needle );
  if ( at == std::string::npos )
    return false;
  json.replace( at, needle.size(), std::string( "\"name\":\"" ) + to + "\"" );

  std::ofstream out( path.str().c_str(), std::ios::binary | std::ios::trunc );
  if ( !out )
    return false;
  out << json;
  return out.good();
}

// Resolve a dictionary index by its primary source file suffix. The scan loads
// one primary file at a time in filesystem order (see gd_scan_dicts), so
// indexes are not guaranteed to be stable across platforms/ordering; match on
// the file the way the app does. Returns -1 when no loaded dictionary matches.
static int findDictBySuffix( const char * suffix )
{
  const int n = gd_dict_count();
  const size_t slen = std::strlen( suffix );
  for ( int i = 0; i < n; ++i ) {
    char name[ 512 ] = { 0 }, file[ 1024 ] = { 0 };
    if ( gd_dict_info( i, name, sizeof name, file, sizeof file ) != 0 )
      continue;
    const size_t len = std::strlen( file );
    if ( len >= slen && std::strcmp( file + len - slen, suffix ) == 0 )
      return i;
  }
  return -1;
}

// ---- fixture presence ------------------------------------------------------
//
// This tool asserts everything about the engine in one walk, and it is run
// against more than one fixture folder: the combined CI folder (StarDict +
// .dsl.dz + nested .dsl) and an MDX-only folder. A block whose fixture is not
// present cannot test anything, so it reports SKIP rather than FAIL - but the
// skip is *asserted* per invocation in the workflow, because a folder missing
// everything must not pass vacuously (fix-smoke-fixture-scoping).
//
// Detected from the loaded dictionaries rather than the filesystem: this is the
// same "which fixture did the engine actually load" question the blocks ask, so
// detection and use cannot disagree.
struct FixturePresence
{
  bool stardict = false; // a StarDict primary file (.ifo)
  bool dsl = false;      // a DSL file (.dsl or .dsl.dz)
  bool mdx = false;      // an MDict primary file (.mdx)

  bool any() const { return stardict || dsl || mdx; }
};

static FixturePresence detectFixtures()
{
  FixturePresence p;
  const int n = gd_dict_count();
  for ( int i = 0; i < n; ++i ) {
    char name[ 512 ] = { 0 }, file[ 1024 ] = { 0 };
    if ( gd_dict_info( i, name, sizeof name, file, sizeof file ) != 0 )
      continue;
    const std::string f( file );
    auto endsWith = [ &f ]( const char * s ) {
      const size_t sl = std::strlen( s );
      return f.size() >= sl && f.compare( f.size() - sl, sl, s ) == 0;
    };
    if ( endsWith( ".ifo" ) )
      p.stardict = true;
    if ( endsWith( ".dsl" ) || endsWith( ".dsl.dz" ) )
      p.dsl = true;
    if ( endsWith( ".mdx" ) )
      p.mdx = true;
  }
  return p;
}

/// Print the inventory so a skip is readable from the log rather than inferred
/// from which assertion is missing.
static void printFixtures( const FixturePresence & p )
{
  std::printf( "FIXTURES:" );
  if ( p.stardict )
    std::printf( " stardict" );
  if ( p.dsl )
    std::printf( " dsl" );
  if ( p.mdx )
    std::printf( " mdx" );
  if ( !p.any() )
    std::printf( " none" );
  std::printf( "\n" );
}

/// A skipped block's result. Named so the workflow can assert it, and worded so
/// it reads as "not tested here" rather than "tested and passed".
static void reportSkip( const char * block, const char * fixture )
{
  std::printf( "%s=SKIP (no %s fixture)\n", block, fixture );
}


int main( int argc, char ** argv )
{
  setvbuf( stdout, nullptr, _IONBF, 0 );

  // Qt reports engine problems through qWarning/qDebug. Without an
  // application object those messages are dropped on the floor on some
  // platforms, which hides the reason a dictionary failed to load - exactly
  // the information this tool exists to surface. Install a handler that
  // prefixes them so they are distinguishable from the tool's own output.
  QCoreApplication app( argc, argv );
  qInstallMessageHandler( []( QtMsgType type, const QMessageLogContext &, const QString & msg ) {
    const char * sev = type == QtDebugMsg      ? "DEBUG"
                     : type == QtInfoMsg       ? "INFO"
                     : type == QtWarningMsg    ? "WARN"
                     : type == QtCriticalMsg   ? "CRIT"
                                               : "FATAL";
    // stderr so it never interleaves with the tool's stdout assertions.
    std::fprintf( stderr, "QT %s: %s\n", sev, msg.toLocal8Bit().constData() );
    std::fflush( stderr );
  } );

  if ( argc < 3 ) {
    std::fprintf( stderr, "usage: smoke_main <config_dir> <dict_dir> [word]\n" );
    return 2;
  }
  const char * configDir = argv[ 1 ];
  const char * dictDir   = argv[ 2 ];
  const char * word      = argc >= 4 ? argv[ 3 ] : "smoke";

  // The engine treats the index dir as a prefix, so the tool builds it the way
  // the app does: a dedicated `index/` subdirectory under config_dir. See
  // fix-index-directory-path-separator (design.md D3).
  const std::string indexDirRaw = std::string( configDir ) + "/index";
  // The engine concatenates the dict id onto this, but it does not create the
  // directory; the app does that (EngineController::initialize) and so must we.
  QDir().mkpath( QString::fromStdString( indexDirRaw ) );

  if ( !gd_init( configDir, indexDirRaw.c_str() ) ) {
    std::fprintf( stderr, "gd_init failed\n" );
    return 1;
  }

  const int n = gd_scan_dicts( dictDir );
  std::printf( "gd_scan_dicts -> %d dictionary(ies)\n", n );
  if ( n <= 0 ) {
    std::fprintf( stderr, "no dictionaries loaded\n" );
    gd_cleanup();
    return 1;
  }

  // Which fixtures this folder actually holds. Printed so a later SKIP is
  // readable from the log; the blocks below consult it instead of failing on a
  // fixture the invocation was never given.
  const FixturePresence fixtures = detectFixtures();
  printFixtures( fixtures );

  // ---- index placement (fix-index-directory-path-separator, design.md D4) ----
  // The engine writes a dictionary's index at `indexDir + dictId` (see
  // index_path.hpp). Assert every loaded dictionary's index actually landed
  // there and is a direct child of the index directory — a mis-supplied index
  // dir used to send it to the sibling `<indexDir><dictId>` instead, which no
  // consumer noticed because nothing checked. The normalization mirrors gd_init
  // so this checks the real formula rather than the raw argv.
  bool indexPlacementOk = true;
  {
    const std::string indexDir = gdNormalizeIndexDir( indexDirRaw );
    // QFileInfo::absolutePath() drops a trailing separator, and cleanPath does
    // too, so compare cleaned forms; comparing against the raw normalized string
    // would "fail" purely on the trailing slash.
    const QString indexDirAbs = QDir::cleanPath( QString::fromStdString( indexDir ) );
    for ( int i = 0; i < n; ++i ) {
      char id[ 128 ] = { 0 };
      if ( gd_dict_id( i, id, sizeof id ) != 0 )
        continue;
      const QString indexPath = QString::fromStdString( indexDir ) + QString::fromUtf8( id );
      const QFileInfo fi( indexPath );
      if ( !fi.exists() ) {
        std::fprintf( stderr, "INDEX_PLACEMENT=FAIL missing index for %s at %s\n",
                      id, qPrintable( indexPath ) );
        indexPlacementOk = false;
        continue;
      }
      const QString parentAbs = QDir::cleanPath( fi.absolutePath() );
      if ( parentAbs != indexDirAbs ) {
        std::fprintf( stderr, "INDEX_PLACEMENT=FAIL index %s is in %s, expected inside %s\n",
                      id, qPrintable( parentAbs ), qPrintable( indexDirAbs ) );
        indexPlacementOk = false;
        continue;
      }
    }
    std::printf( "INDEX_PLACEMENT=%s (index dir %s, %d dicts)\n",
                 indexPlacementOk ? "OK" : "FAIL", qPrintable( indexDirAbs ), n );
  }

  // Re-scanning the same folder must not duplicate already-loaded dictionaries
  // (the UI re-stages + re-scans on every add; id = md5 over the file paths).
  const int n2 = gd_scan_dicts( dictDir );
  std::printf( "gd_scan_dicts(again) -> %d new (expect 0)\n", n2 );
  const bool dedupOk = n2 == 0;

  // ---- scan-failure reporting smoke (gd_scan_failures) ----
  // A bulk import of a broken collection records one failure per unloadable
  // primary; the app renders them as the import-results banner and deletes the
  // files each names. The failure path is the primary's source path, which
  // preserves the original file name — so a non-ASCII name (Japanese/Russian
  // dictionaries are common) is the case that exercises the boundary's UTF-8
  // handling: gd_scan_failures must size-check and copy the ENCODED bytes, not
  // the UTF-16 unit count, and terminate the buffer.
  //
  // Self-contained: writes a broken non-ASCII .ifo into a subdir of the
  // per-invocation config dir (never the shared fixture folder — see the
  // identity block's dupDir note), scans it, and asserts the failure comes back
  // intact. The name is built from QChar code points so the source carries no
  // encoding dependency. Platform note: on Windows the path is recorded
  // through fromLocal8Bit (see gd_boundary.cc), which mojibakes non-ASCII and
  // — by making the UTF-16 count equal the byte count — masks the truncation
  // there; the block still gates the path everywhere and catches the
  // truncation on a UTF-8-local platform (the app's Android target).
  bool scanFailuresOk = true; // set false by the block below
  {
    const QString brokenName = QStringLiteral( "broken-" )
        + QString( QChar( 0x017C ) ) + QString( QChar( 0x00F3 ) )
        + QString( QChar( 0x0142 ) ) + QString( QChar( 0x0107 ) )
        + QString( QChar( 0x0105 ) ) + QStringLiteral( ".ifo" );
    const QString scanDir = QDir( QString::fromLocal8Bit( configDir ) )
                              .filePath( QStringLiteral( "scanfail" ) );
    QDir().mkpath( scanDir );
    const QString brokenIfo = QDir( scanDir ).filePath( brokenName );
    {
      QFile f( brokenIfo );
      if ( f.open( QIODevice::WriteOnly ) )
        f.write( "not a stardict ifo\n" );
    }
    gd_scan_dicts( scanDir.toLocal8Bit().constData() );

    std::vector< char > failBuf( 16384 );
    const int failN = gd_scan_failures( failBuf.data(), static_cast< int >( failBuf.size() ) );
    std::printf( "gd_scan_failures -> %d\n", failN );
    const QString failStr = QString::fromUtf8( failBuf.data() );
    // The exact non-ASCII filename must survive the round-trip: a size check on
    // the wrong unit (UTF-16 vs UTF-8) or a local-codec detour truncates it.
    const bool failIntact = failN > 0 && failStr.contains( brokenName );
    std::printf( "SCAN_FAILURES=%s\n", failIntact ? "OK" : "FAIL" );
    scanFailuresOk = failIntact;

    QFile::remove( brokenIfo );
    QDir().rmdir( scanDir );
  }
  bool dictOk = true; // refined by the removal block below
  // Blocks whose fixture may be absent start satisfied and are only lowered by a
  // real failure, so a SKIP cannot make the run fail. Their skip is asserted
  // separately in the workflow, where the expected fixture set is known.
  bool optPartsOk = true;      // DSL hidden-zone block; set false on failure
  bool stardictLinkOk = true;  // StarDict cross-reference block; set false on failure

  std::vector< char > sug( 1 << 12 );
  const int sugN = gd_suggest( "smok", sug.data(), static_cast< int >( sug.size() ) );
  std::printf( "gd_suggest(\"smok\") -> %d results\n", sugN );
  if ( sugN > 0 ) {
    std::printf( "SUGGEST: %s\n", sug.data() );
  }

  std::vector< char > out( 1 << 20 );
  const int lookSz = gd_lookup( word, out.data(), static_cast< int >( out.size() ) );
  std::printf( "gd_lookup(\"%s\") -> %d bytes\n", word, lookSz );
  const std::string html( out.data(), lookSz > 0 ? lookSz : 0 );

  // Collect every distinct resource URL the article references, so that the
  // fetch below exercises all of them rather than only the first. That
  // distinction decides whether the smoke tool can see an image at all: MDX
  // emits its stylesheet first, so "first bres://" is always the .css and the
  // .jpg/.png the article actually shows was never fetched.
  std::vector< std::string > refs;
  {
    // Bounded: an article referencing hundreds of resources is not the case
    // this exists to catch, and each ref costs a read through the engine.
    const size_t kMaxRefs = 40;
    for ( const char * scheme : { "bres://", "gdau://" } ) {
      for ( std::size_t p = html.find( scheme ); p != std::string::npos && refs.size() < kMaxRefs;
            p = html.find( scheme, p + std::strlen( scheme ) ) ) {
        // These URLs are quote-delimited in the markup, and they routinely
        // contain spaces and commas -- dictionary resource paths look like
        // "William J. Stewart, .../Image_106.png". Splitting on whitespace
        // truncated them into a bogus URL that then "failed to resolve" and
        // looked like a broken dictionary. Honour the surrounding quote when
        // there is one, and only fall back to delimiters for a bare scheme.
        std::size_t end;
        const char quote = ( p > 0 && ( html[ p - 1 ] == '"' || html[ p - 1 ] == '\'' ) ) ? html[ p - 1 ] : 0;
        if ( quote )
          end = html.find( quote, p );
        else
          end = html.find_first_of( "\"'() \t\r\n", p );
        if ( end == std::string::npos )
          end = html.size();
        std::string url = html.substr( p, end - p );
        if ( !url.empty() && std::find( refs.begin(), refs.end(), url ) == refs.end() )
          refs.push_back( url );
      }
    }
  }

  if ( lookSz > 0 ) {
    // Dump the whole body, not a head fragment. The old 800-char cap stopped
    // inside <head>, so an article's own <img src="bres://…"> references were
    // never visible and two resource investigations (StarDict res/, MDict mdd)
    // could not be settled from this output. A real article is a few KiB; the
    // buffer above is 1 MiB, so printing it whole is fine. The cap is a
    // visibility limit only — the engine still returns everything either way.
    std::printf( "BEGIN\\%.*s\nEND\n", lookSz, out.data() );
    std::printf( "MARKERS: gdarticlebody=%s gdarticle=%s\n",
                 html.find( "gdarticlebody" ) != std::string::npos ? "yes" : "no",
                 html.find( "gdarticle" ) != std::string::npos ? "yes" : "no" );
    for ( const std::string & r : refs )
      std::printf( "REF: %s\n", r.c_str() );
    std::printf( "REFS: %d\n", static_cast< int >( refs.size() ) );
  }

  // Optional dark-mode check: set dark mode and re-lookup, asserting the
  // darkreader script is emitted (task 7.1).
  const bool testDark = argc >= 5 && std::string( argv[ 4 ] ) == "dark";
  if ( testDark ) {
    const int rc = gd_set_dark_mode( 1 );
    std::printf( "gd_set_dark_mode(1) -> %d\n", rc );
    std::vector< char > darkOut( 1 << 20 );
    const int darkSz = gd_lookup( word, darkOut.data(), static_cast< int >( darkOut.size() ) );
    const std::string darkHtml( darkOut.data(), darkSz > 0 ? darkSz : 0 );
    std::printf( "DARK: darkreader=%s\n",
                 darkHtml.find( "darkreader.js" ) != std::string::npos ? "yes" : "no" );
  }

  // Exercise the resource/audio fetch: stream back through the boundary every
  // distinct URL the article references. Fetching only the first one meant a
  // dictionary's stylesheet was the only resource ever read, so a broken image
  // inside the .mdd or a StarDict res/ tree still reported a clean run.
  for ( const std::string & url : refs ) {
    std::vector< char > res( 1 << 20 );
    const int resSz = gd_get_resource( url.c_str(), res.data(), static_cast< int >( res.size() ) );
    // Sniff the payload's magic bytes. A resource route that answers with the
    // right *count* but wrong *content* — a truncated archive read, an HTML
    // error page, a stray index — still looks like a pass on length alone, and
    // in the WebView that is a broken image rather than a missing one.
    const char * magic = "n/a";
    if ( resSz >= 3 && static_cast< unsigned char >( res[ 0 ] ) == 0xFF
         && static_cast< unsigned char >( res[ 1 ] ) == 0xD8 )
      magic = "jpeg";
    else if ( resSz >= 8 && res[ 0 ] == '\x89' && res[ 1 ] == 'P' && res[ 2 ] == 'N' && res[ 3 ] == 'G' )
      magic = "png";
    else if ( resSz >= 3 && res[ 0 ] == 'G' && res[ 1 ] == 'I' && res[ 2 ] == 'F' )
      magic = "gif";
    else if ( resSz >= 4 && res[ 0 ] == '<' )
      magic = "html-or-text";
    std::printf( "gd_get_resource(\"%s\") -> %d bytes [magic=%s]%s\n",
                 url.c_str(),
                 resSz,
                 magic,
                 resSz <= 0 ? "  ** FAILED TO RESOLVE **" : "" );
    (void)res;
  }

  // ---- DSL optional/hidden-zone expander smoke (dsl-optional-parts-toggle) ----
  // The engine renders `[*]...[/opt]` as a hidden `.dsl_opt` span plus one
  // `<img class="hidden_expand_opt" onclick="gdExpandOptPart(...)">` per article
  // that has hidden zones. The app supplies the handler (assets/scripts/
  // gd-article-controls.js); this pins the engine-side markup that handler
  // depends on, so an upstream bump that stops emitting it fails CI here
  // instead of shipping a dead control.
  //
  // Needs the DSL fixture ("sun" and "water" are DSL headwords). Scoped rather
  // than assumed, so an MDX-only run skips it instead of failing on a fixture it
  // was never given; the workflow asserts this SKIP so the block cannot silently
  // stop being tested.
  if ( !fixtures.dsl ) {
    reportSkip( "OPT_ZONE", "dsl" );
    reportSkip( "OPT_NO_ZONE", "dsl" );
  }
  else {
    const int dslDzIdx = findDictBySuffix( ".dsl.dz" );
    std::vector< char > opt( 1 << 20 );
    const int sz = gd_lookup( "sun", opt.data(), static_cast< int >( opt.size() ) );
    const std::string optHtml( opt.data(), sz > 0 ? sz : 0 );
    const bool hasZone  = optHtml.find( "class=\"dsl_opt\"" ) != std::string::npos;
    const bool hasExpander = optHtml.find( "gdExpandOptPart(" ) != std::string::npos;
    const bool hasSection  = optHtml.find( "gdarticlebody" ) != std::string::npos;
    // The header must NOT carry the always-expand override. When
    // alwaysExpandOptionalParts is left at its upstream default (true),
    // makeHtmlHeader injects this block and the optional text renders expanded
    // with the expander icon hidden — the markup assertions above then pass
    // while the control is dead on screen (the bug this change fixes).
    const bool hasOverride =
        optHtml.find( "Expand optional parts css" ) != std::string::npos;
    std::printf( "gd_lookup(\"sun\") -> %d bytes [dict %d] OPT_ZONE=%s OPT_EXPANDER=%s "
                 "OPT_OVERRIDE=%s\n",
                 sz, dslDzIdx, hasZone ? "OK" : "FAIL", hasExpander ? "OK" : "FAIL",
                 hasOverride ? "FAIL" : "OK" );
    // A headword with no hidden zone must not gain an expander (the control is
    // per-article, not per-dictionary).
    std::vector< char > plain( 1 << 20 );
    const int plainSz = gd_lookup( "water", plain.data(), static_cast< int >( plain.size() ) );
    const std::string plainHtml( plain.data(), plainSz > 0 ? plainSz : 0 );
    const bool plainClean = plainSz > 0 && plainHtml.find( "gdExpandOptPart(" ) == std::string::npos;
    std::printf( "OPT_NO_ZONE=%s\n", plainClean ? "OK" : "FAIL" );
    optPartsOk = hasSection && hasZone && hasExpander && !hasOverride && plainClean;
  }

  // ---- StarDict cross-reference links (stardict-bword-link-navigation) ----
  // A StarDict article may cross-reference another entry with the bword:
  // scheme. The engine must rewrite it into a scheme the app resolves: before
  // the fix it was emitted verbatim and tapping it did nothing, because no
  // consumer understands bword:. The fixture's "clot" entry carries one.
  //
  // Needs the StarDict fixture. Scoped like the DSL block above; the workflow
  // asserts this SKIP so the check cannot silently stop running.
  if ( !fixtures.stardict ) {
    reportSkip( "STARDICT_LINK_NO_BWORD", "stardict" );
    reportSkip( "STARDICT_LINK_REWRITTEN", "stardict" );
  }
  else {
    std::vector< char > linkBuf( 1 << 20 );
    const int linkSz = gd_lookup( "clot", linkBuf.data(), static_cast< int >( linkBuf.size() ) );
    const std::string linkHtml( linkBuf.data(), linkSz > 0 ? linkSz : 0 );

    // The unhandled scheme must be gone from the output entirely.
    const bool noBword = linkHtml.find( "bword:" ) == std::string::npos;
    std::printf( "STARDICT_LINK_NO_BWORD=%s\n", noBword ? "OK" : "FAIL" );

    // And the cross-reference must have become a link the app resolves, in
    // exactly the shape the DSL reader produces (gdlookup://localhost/<word>).
    //
    // This assertion has now been wrong twice in the same way, which is worth
    // recording: it first accepted any "gdlookup:" prefix and passed while the
    // device showed "unknown url scheme"; then it required "gdlookup:///" and
    // passed while the device silently truncated the word at its space. Both
    // times it asserted a substring of the scheme rather than the complete URL
    // the app parses. So it now requires a full href, host included.
    const bool rewritten = linkHtml.find( "href=\"gdlookup://localhost/blood\"" ) != std::string::npos;
    std::printf( "STARDICT_LINK_REWRITTEN=%s\n", rewritten ? "OK" : "FAIL" );

    stardictLinkOk = noBword && rewritten;
  }

  // ---- groups smoke (multi-group-management) ----
  // CI folder has the StarDict ("smoke") plus a .dsl.dz (no "smoke") and a
  // nested .dsl; locate the primary files by suffix since scan order is not
  // guaranteed.
  bool groupsOk = true;
  {
    const int dslDzIdx = findDictBySuffix( ".dsl.dz" );
    const int gc = gd_group_count();
    std::printf( "gd_group_count -> %d\ngd_suffix(dsl.dz) -> %d\n", gc, dslDzIdx );
    int gid = -1;
    if ( gd_group_create( "OnlyDSL", &gid ) == 0 ) {
      std::printf( "gd_group_create -> %d\n", gid );
    }
    if ( gid > 0 && dslDzIdx >= 0 && gd_group_add_dict( gid, dslDzIdx ) == 0 ) {
      std::printf( "gd_group_add_dict(%d) -> 0\n", dslDzIdx );
    }
    if ( gid > 0 && gd_group_set_active( gid ) == 0 ) {
      std::printf( "gd_group_set_active -> 0\n" );
    }
    if ( gid > 0 ) {
      std::vector< char > out( 1 << 20 );
      const int sz = gd_lookup( "smoke", out.data(), static_cast< int >( out.size() ) );
      std::printf( "group-only-DSL gd_lookup(\"smoke\") -> %d bytes\n", sz );
      const std::string html( out.data(), sz > 0 ? sz : 0 );
      const bool found = html.find( "gdarticlebody" ) != std::string::npos;
      std::printf( "GROUP_NARROW=%s\n", found ? "FAIL" : "OK" );
      // Back to All: "smoke" found again.
      gd_group_set_active( 0 );
      const int sz2 = gd_lookup( "smoke", out.data(), static_cast< int >( out.size() ) );
      const std::string html2( out.data(), sz2 > 0 ? sz2 : 0 );
      std::printf( "GROUP_ALL=%s\n", html2.find( "gdarticlebody" ) != std::string::npos ? "OK" : "FAIL" );
    }

    // A scan reloads groups.json, which is how importing a dictionary used to
    // duplicate every group (the user ended up with two groups of the same
    // name, the second undeletable). Re-scanning must leave the group set
    // exactly as it was.
    const int gcBefore = gd_group_count();
    gd_scan_dicts( dictDir );
    const int gcAfter = gd_group_count();
    std::printf( "gd_group_count after re-scan -> %d (was %d)\n", gcAfter, gcBefore );
    const bool groupRescanOk = gcAfter == gcBefore;
    std::printf( "GROUP_RESCAN=%s\n", groupRescanOk ? "OK" : "FAIL" );

    // And the group the user made must still be reachable by id after the
    // reload (a duplicated id would make findGroupDef hit the wrong entry).
    int infoId = -1, infoCount = -1;
    char infoName[ 256 ] = { 0 };
    const int infoRc = gd_group_info( gcAfter - 1, &infoId, infoName, sizeof infoName, &infoCount );
    std::printf( "gd_group_info(%d) -> rc=%d id=%d name=%s dicts=%d\n",
                 gcAfter - 1, infoRc, infoId, infoName, infoCount );
    const bool groupIdOk = infoRc == 0 && infoId == gid && std::strcmp( infoName, "OnlyDSL" ) == 0;
    std::printf( "GROUP_ID_STABLE=%s\n", groupIdOk ? "OK" : "FAIL" );

    // ...and the reload must REPLACE the in-memory set rather than merge into
    // it. Editing the stored name and re-scanning must surface the new name: a
    // loader that appends (and then collapses the repeat) keeps the previous
    // in-memory copy instead, so this is what pins the actual defect — the count
    // check above passes even in that state.
    const bool reloadOk = rewriteGroupName( configDir, "OnlyDSL", "OnlyDSL2" )
                          && ( gd_scan_dicts( dictDir ), true );
    int infoId2 = -1, infoCount2 = -1;
    char infoName2[ 256 ] = { 0 };
    const int infoRc2 = gd_group_info( gcAfter - 1, &infoId2, infoName2, sizeof infoName2, &infoCount2 );
    std::printf( "gd_group_info(%d) after stored rename -> rc=%d id=%d name=%s\n",
                 gcAfter - 1, infoRc2, infoId2, infoName2 );
    const bool sourceOfTruthOk =
        reloadOk && infoRc2 == 0 && infoId2 == gid && std::strcmp( infoName2, "OnlyDSL2" ) == 0;
    std::printf( "GROUP_RELOAD_SOURCE=%s\n", sourceOfTruthOk ? "OK" : "FAIL" );

    groupsOk = gid > 0 && groupRescanOk && groupIdOk && sourceOfTruthOk;
  }

  // ---- full-text search smoke (xapian) ----
  // Index the StarDict fixture (found by its .ifo primary file), then search
  // for a term that appears in an article BODY but is not a headword ("mdx"
  // only occurs inside the "smoke" article); expect the article's headword
  // back. The dictionary index is located by suffix because scan order is not
  // guaranteed (Stardict is not necessarily first).
  //
  // This block indexes the StarDict fixture specifically, so it cannot run
  // without it. It used to `return 1` here, which aborted the whole walk — every
  // block after it (resource-thread, re-import, removal) never ran in a folder
  // that had no StarDict, and that made the MDX-only run impossible to pass
  // (fix-smoke-fixture-scoping). Skipping is the honest outcome: this folder
  // cannot test this, and the workflow asserts the skip.
  bool ftsOk = true; // satisfied unless the block runs and fails
  const int sdIdx = findDictBySuffix( ".ifo" );
  std::printf( "gd_suffix(.ifo) -> %d\n", sdIdx );
  if ( sdIdx < 0 ) {
    std::printf( "FTS_INDEX=SKIP (no stardict fixture)\n" );
    ftsOk = true;
  }
  else {
    ftsOk = false;
    int st = -1;
    if ( gd_fts_index_state( sdIdx, &st ) == 0 )
      std::printf( "gd_fts_index_state(%d) -> %d\n", sdIdx, st );
    const int idxRc = st == 0 ? 0 : gd_fts_index( sdIdx );
    std::printf( "gd_fts_index(%d) -> %d\n", sdIdx, idxRc );
    if ( gd_fts_index_state( sdIdx, &st ) == 0 )
      std::printf( "gd_fts_index_state(%d) after -> %d\n", sdIdx, st );

    // fts-indexing-performance: the build-state / cancel boundary contract. The
    // build just finished, so the dictionary must report idle (state 0) and a
    // cancel with nothing in flight must be a harmless no-op returning 0.
    {
      char idb[ 128 ] = { 0 };
      int bst = -1;
      const int bIdRc = gd_dict_id( sdIdx, idb, sizeof idb );
      const int bStateRc = bIdRc == 0 ? gd_fts_build_state( idb, &bst ) : -1;
      const int cancelRc = bIdRc == 0 ? gd_fts_cancel( idb ) : -1;
      const bool buildStateOk = bStateRc == 0 && bst == 0 && cancelRc == 0;
      std::printf( "gd_fts_build_state(%s) -> rc=%d state=%d; gd_fts_cancel -> %d\n",
                   idb, bStateRc, bst, cancelRc );
      std::printf( "FTS_BUILD_STATE=%s\n", buildStateOk ? "OK" : "FAIL" );
    }

    std::vector< char > fts( 1 << 12 );
    const int ftsN = gd_fts_search( "mdx", 1, 0, fts.data(), static_cast< int >( fts.size() ) );
    std::printf( "gd_fts_search(\"mdx\", plain) -> %d results\n", ftsN );
    if ( ftsN > 0 )
      std::printf( "FTS_RESULTS: %s\n", fts.data() );
    const std::string ftsStr( fts.data(), ftsN > 0 ? std::strlen( fts.data() ) : 0 );
    ftsOk = ftsN > 0 && ftsStr.find( "smoke" ) != std::string::npos;
    std::printf( "FTS_BODY=%s\n", ftsOk ? "OK" : "FAIL" );

    // A bogus word matches nothing (empty-result path, not an error).
    const int ftsNone = gd_fts_search( "zzzzqqqq", 1, 0, fts.data(), static_cast< int >( fts.size() ) );
    std::printf( "gd_fts_search(\"zzzzqqqq\") -> %d results\n", ftsNone );

    // Wildcards mode: "t*" expands to {test, the} — more than one term. This
    // pins Aurelex patch 0003 (upstream capped the expansion at 1 term and
    // threw WildcardError, silently returning nothing for any real prefix).
    const int ftsWild = gd_fts_search( "t*", 2, 0, fts.data(), static_cast< int >( fts.size() ) );
    std::printf( "gd_fts_search(\"t*\", wildcards) -> %d results [%s]\n", ftsWild, ftsWild > 0 ? fts.data() : "" );
    const std::string wildStr( fts.data(), ftsWild > 0 ? std::strlen( fts.data() ) : 0 );
    const bool ftsWildOk = ftsWild > 0 && ( wildStr.find( "smoke" ) != std::string::npos
                                            || wildStr.find( "blood" ) != std::string::npos );
    std::printf( "FTS_WILD=%s\n", ftsWildOk ? "OK" : "FAIL" );
  }

  // ---- embedded-resource smoke, on a third thread ----
  // fix-article-server-gui-reentrancy (design.md D1) moves bres:// resolution
  // onto a dedicated engine-resource thread. That thread is neither the thread
  // that constructed the dictionaries (the engine pool, reached via
  // gd_scan_dicts) nor the Qt main thread. gd_get_resource spins a nested
  // QEventLoop internally, so the calling thread needs a Qt event dispatcher -
  // hence QThread rather than std::thread, which would return immediately with
  // no dispatcher and read as a false pass/fail.
  //
  // This is the gate for D1: if a dictionary backend keeps thread-affine state,
  // a load from a foreign thread fails here (wrong rc, or a payload that is not
  // the SVG) even though the same load on the constructing thread succeeds.
  //
  // Needs the DSL fixture, whose resource bundle holds the SVG. Scoped so an
  // MDX-only run skips it; the workflow asserts the skip.
  bool resourceThreadOk = true; // satisfied unless the block runs and fails
  if ( !fixtures.dsl ) {
    reportSkip( "RESOURCE_ON_MAIN_THREAD", "dsl" );
    reportSkip( "RESOURCE_ON_WORKER_THREAD", "dsl" );
  }
  else {
    resourceThreadOk = false;
    const int resIdx = findDictBySuffix( ".dsl.dz" );
    char dictId[ 128 ] = { 0 };
    const int idRc = resIdx >= 0 ? gd_dict_id( resIdx, dictId, sizeof dictId ) : -1;
    std::printf( "gd_dict_id(%d) -> rc=%d id=%s\n", resIdx, idRc, dictId );

    const std::string resUrl =
        std::string( "bres://" ) + dictId + "/" + kFixtureResource;
    std::vector< char > resBuf( 64 * 1024 );

    // Control: the same URL on THIS thread. Both failing means the fixture or
    // the URL is wrong, not the engine's threading - the two cases must be
    // distinguishable or this check cannot diagnose anything.
    const int mainRc =
        gd_get_resource( resUrl.c_str(), resBuf.data(), static_cast< int >( resBuf.size() ) );
    const std::string mainBody( resBuf.data(), mainRc > 0 ? mainRc : 0 );
    const bool mainOk = mainRc > 0 && mainBody.find( "<svg" ) != std::string::npos;
    std::printf( "gd_get_resource(\"%s\") on main thread -> rc=%d (%d bytes)\n",
                 resUrl.c_str(), mainRc, mainRc > 0 ? mainRc : 0 );
    std::printf( "RESOURCE_ON_MAIN_THREAD=%s\n", mainOk ? "OK" : "FAIL" );

    int workerRc = -999;
    int workerSz = 0;
    QThread * worker = QThread::create( [ & ] {
      workerRc = gd_get_resource( resUrl.c_str(), resBuf.data(),
                                  static_cast< int >( resBuf.size() ) );
      workerSz = workerRc > 0 ? workerRc : 0;
    } );
    worker->start();
    worker->wait();
    delete worker;

    const std::string workerBody( resBuf.data(), workerSz );
    resourceThreadOk = mainOk && idRc == 0 && workerRc > 0
        && workerBody.find( "<svg" ) != std::string::npos;
    std::printf( "gd_get_resource(\"%s\") on worker thread -> rc=%d (%d bytes)\n",
                 resUrl.c_str(), workerRc, workerSz );
    std::printf( "RESOURCE_ON_WORKER_THREAD=%s\n", resourceThreadOk ? "OK" : "FAIL" );
  }

  // ---- re-import of a changed dictionary that keeps its id ----
  // A re-import replaces a source file in place. The dictionary id is an MD5 of
  // the source PATHS, so it does not change, and the scan must detect the change
  // and reload — not discard the freshly built object while the backend has
  // already rewritten the index underneath the live one, which left that
  // dictionary's searches failing ("Error reading from the file") and wedged
  // gd_suggest for its whole timeout (the on-device 2026-09-28 report).
  // Appending a newline changes the file's size + mtime without breaking the DSL.
  //
  // Needs the DSL fixture: it appends DSL markup to the nested .dsl and re-scans,
  // so an MDX-only folder cannot exercise it. Scoped; the workflow asserts the
  // skip.
  bool reimportOk = true; // satisfied unless the block runs and fails
  if ( !fixtures.dsl ) {
    reportSkip( "REIMPORT_RELOAD", "dsl" );
    reportSkip( "REIMPORT_CONTENT", "dsl" );
    reportSkip( "REIMPORT_SUGGEST", "dsl" );
  }
  else {
    reimportOk = false;
    const int dslIdx = findDictBySuffix( ".dsl" ); // the nested, uncompressed fixture
    char nameBuf[ 256 ]  = { 0 };
    char fileBuf[ 1024 ] = { 0 };
    const int infoRc = dslIdx >= 0
      ? gd_dict_info( dslIdx, nameBuf, static_cast< int >( sizeof nameBuf ),
                      fileBuf, static_cast< int >( sizeof fileBuf ) )
      : -1;
    std::printf( "re-import fixture dict %d: %s (%s)\n", dslIdx, nameBuf, fileBuf );

    bool appended = false;
    if ( infoRc == 0 ) {
      QFile f( QString::fromLocal8Bit( fileBuf ) );
      appended = f.open( QIODevice::Append );
      if ( appended ) {
        // A real new entry, not just a newline: the whole point of a re-import is
        // that the new data takes effect. Before the fix the scan deduped the
        // changed file by id, so the old object kept the old content and this
        // headword was never found.
        f.write( "\nreatest\n\t[m1]re-import test entry[/m]\n" );
        f.close();
      }
    }

    const int countBefore = gd_dict_count();
    const int reloaded    = appended ? gd_scan_dicts( dictDir ) : 0;
    const int countAfter  = gd_dict_count();
    std::printf( "gd_scan_dicts(after source change) -> %d new (count %d -> %d)\n",
                 reloaded, countBefore, countAfter );
    const bool reloadOk = appended && reloaded == 1 && countAfter == countBefore;
    std::printf( "REIMPORT_RELOAD=%s\n", reloadOk ? "OK" : "FAIL" );

    // The new content must resolve, and the reloaded dictionary must still
    // search: the defect also left the live object reading an index that had been
    // rewritten underneath it.
    std::vector< char > out( 1 << 20 );
    const int sz = gd_lookup( "reatest", out.data(), static_cast< int >( out.size() ) );
    const bool found =
      sz > 0 && std::string( out.data(), sz ).find( "gdarticlebody" ) != std::string::npos;
    std::printf( "REIMPORT_CONTENT=%s\n", found ? "OK" : "FAIL" );

    // Prefix search is what the Search field uses ("no dropdown" on device).
    std::vector< char > sug2( 1 << 12 );
    const int sug2N = gd_suggest( "reat", sug2.data(), static_cast< int >( sug2.size() ) );
    const std::string sug2Str( sug2.data(), sug2N > 0 ? std::strlen( sug2.data() ) : 0 );
    const bool sugFound = sug2N > 0 && sug2Str.find( "reatest" ) != std::string::npos;
    std::printf( "REIMPORT_SUGGEST=%s\n", sugFound ? "OK" : "FAIL" );

    reimportOk = reloadOk && found && sugFound;
  }

  // ---- dictionary removal smoke (remove-dictionary) ----
  // The DSL (.dsl.dz, found by suffix) has the headword "book"; remove it,
  // confirm the count drops and "book" stops resolving, then re-scan re-adds
  // it (removal is in-memory; dedup does not block a removed id).
  //
  // Needs the DSL fixture ("book" is a DSL headword). Scoped; the workflow
  // asserts the skip.
  if ( !fixtures.dsl ) {
    reportSkip( "REMOVE_DICT", "dsl" );
    reportSkip( "REMOVE_READD", "dsl" );
  }
  else {
    const int dslDzIdx = findDictBySuffix( ".dsl.dz" );
    std::vector< char > b( 1 << 20 );
    const int before = gd_dict_count();
    const int bookBefore = gd_lookup( "book", b.data(), static_cast< int >( b.size() ) );
    const bool bookFoundBefore = bookBefore > 0
      && std::string( b.data(), bookBefore ).find( "gdarticlebody" ) != std::string::npos;

    const int rmRc = dslDzIdx >= 0 ? gd_remove_dict( dslDzIdx ) : -1;
    const int after = gd_dict_count();
    std::printf( "gd_remove_dict(%d) -> %d (count %d -> %d)\n", dslDzIdx, rmRc, before, after );

    const int bookAfter = gd_lookup( "book", b.data(), static_cast< int >( b.size() ) );
    const bool bookFoundAfter = bookAfter > 0
      && std::string( b.data(), bookAfter ).find( "gdarticlebody" ) != std::string::npos;
    std::printf( "REMOVE_DICT=%s (book was %s, now %s)\n",
                 ( rmRc == 0 && after == before - 1 && bookFoundBefore && !bookFoundAfter ) ? "OK" : "FAIL",
                 bookFoundBefore ? "found" : "absent",
                 bookFoundAfter ? "found" : "absent" );

    // Re-adding the same folder brings the dictionary back (dedup compares
    // against loaded ids only).
    const int reAdd = gd_scan_dicts( dictDir );
    const int reCount = gd_dict_count();
    std::printf( "gd_scan_dicts(after remove) -> %d new (count %d)\n", reAdd, reCount );
    const bool readdOk = reAdd == 1 && reCount == before;
    std::printf( "REMOVE_READD=%s\n", readdOk ? "OK" : "FAIL" );
    dictOk = dictOk && rmRc == 0 && after == before - 1 && bookFoundBefore && !bookFoundAfter && readdOk;
  }

  // ---- dictionary identity smoke (resolve-duplicate-dictionaries) ----
  // Identity is name + content, never location. Copy a loaded dictionary to a
  // second path, rescan, and assert the two gd_dict_identity records compare
  // equal; then change the copy and assert they differ. This is the only place
  // the REAL boundary record shape is exercised on host, which is the contract
  // the app's grouping depends on (design.md D2 risk).
  bool identityOk = false;
  // The block's copy lives under the CONFIG dir, never under the shared fixture
  // folder -- see the note at dupDir below. Whether the shared folder was left
  // untouched is what gets asserted, after the block.
  bool identityCleanupOk = true;
  {
    // Pick a self-contained primary (a DSL or MDX has no companion files to
    // copy; a StarDict .ifo alone would fail to load and confound the test).
    char iname[ 512 ] = { 0 };
    char ifile[ 4096 ] = { 0 };
    int src = -1;
    for ( int i = 0; i < gd_dict_count(); ++i ) {
      if ( gd_dict_info( i, iname, sizeof iname, ifile, sizeof ifile ) != 0 || !ifile[0] )
        continue;
      const QString p = QString::fromLocal8Bit( ifile ).toLower();
      if ( p.endsWith( QLatin1String( ".dsl.dz" ) ) || p.endsWith( QLatin1String( ".dsl" ) )
           || p.endsWith( QLatin1String( ".mdx" ) ) ) {
        src = i;
        break;
      }
    }
    if ( src < 0 ) {
      std::printf( "DICT_IDENTITY_SKIP=no self-contained fixture\n" );
    }
    else {
      const QString primary = QString::fromLocal8Bit( ifile );
      const QString name    = QString::fromLocal8Bit( iname );
      // The copy goes under the CONFIG dir, which is per-invocation, and NOT
      // under the shared fixture folder. It used to be <dict_dir>/dupcheck, and
      // that made this block the only one in the tool that wrote into the folder
      // it was asked to scan -- with a consequence nobody could see: the drifted
      // copy CANNOT be deleted once loaded, because the engine leaks the QFile
      // that holds it. MdictParser::open does `file_ = new QFile(...)`
      // (engine/src/dict/mdictparser.cc:101) into a QPointer that is never
      // deleted, so the handle lives for the whole PROCESS -- gd_remove_dict and
      // gd_cleanup() both leave it open, which is why removing the copy after
      // gd_cleanup() still fails. A leaked copy inside the shared folder is then
      // found by the next invocation's scan and reported as an identity failure.
      // Under the config dir the leak is contained: nothing ever scans that
      // directory twice, so a copy that cannot be deleted is harmless. The
      // location-independence property under test is unaffected -- the two
      // dictionaries are still at different paths with the same name and
      // content, which is the whole point of the comparison.
      const QString dupDir = QDir( QString::fromLocal8Bit( configDir ) )
                               .filePath( QStringLiteral( "dupcheck" ) );
      QDir().mkpath( dupDir );
      const QString copy = QDir( dupDir ).filePath( QFileInfo( primary ).fileName() );
      QFile::remove( copy );
      const bool copied = QFile::copy( primary, copy );
      if ( copied ) {
        // Match the source's mtime so the 5 s tolerance is not what decides this:
        // the copy is byte-identical and staged now, the original is older.
        QFile c( copy );
        if ( c.open( QIODevice::ReadWrite ) )
          c.setFileTime( QFileInfo( primary ).lastModified(),
                         QFileDevice::FileModificationTime );
      }
      // Rescan the fixture folder for the original and the CONFIG dir for the
      // copy: two dictionaries with one name at different paths, which is what
      // the identity record is supposed to collapse. (Scanning both from one
      // folder is what leaked the copy in the first place.)
      const int added = copied ? gd_scan_dicts( configDir ) : 0;

      auto identitiesByName = [ & ]( const QString &n ) {
        QVector< DictIdentity::Identity > v;
        char nb[ 512 ] = { 0 };
        char fb[ 4096 ] = { 0 };
        for ( int i = 0; i < gd_dict_count(); ++i ) {
          if ( gd_dict_info( i, nb, sizeof nb, fb, sizeof fb ) == 0
               && QString::fromLocal8Bit( nb ) == n ) {
            std::vector< char > buf( 1 << 16 );
            if ( gd_dict_identity( i, buf.data(), static_cast< int >( buf.size() ) ) == 0 )
              v.append( DictIdentity::parseRecord( QString::fromUtf8( buf.data() ) ) );
          }
        }
        return v;
      };

      const QVector< DictIdentity::Identity > ids = identitiesByName( name );
      const bool same = ids.size() >= 2
        && DictIdentity::sameContent( ids.at( 0 ), ids.at( 1 ) );
      std::printf( "DICT_IDENTITY_SAME=%s (name=%s, copies=%d, scan+%d)\n",
                   same ? "OK" : "FAIL", qPrintable( name ),
                   static_cast< int >( ids.size() ), added );

      // Change the copy's size, rescan (the engine reloads it in place), and
      // assert the two no longer compare equal.
      bool differs = false;
      if ( copied ) {
        QFile f( copy );
        if ( f.open( QIODevice::Append ) )
          f.write( "\nidentitydrift\n\tmore\n" );
        f.close();
        gd_scan_dicts( configDir );
        const QVector< DictIdentity::Identity > ids2 = identitiesByName( name );
        if ( ids2.size() >= 2 )
          differs = !DictIdentity::sameContent( ids2.at( 0 ), ids2.at( 1 ) );
        else if ( ids2.size() == 1 )
          differs = true; // the copy did not reload as a same-name pair at all
      }
      std::printf( "DICT_IDENTITY_DIFF=%s\n", differs ? "OK" : "FAIL" );
      identityOk = same && differs;

      // Nothing to restore in the fixture folder: the copy was never put there
      // (see the dupDir note). Removing it here is best-effort tidying of the
      // config dir, and it is EXPECTED to fail while the copy is loaded -- the
      // engine leaks the QFile that holds it for the life of the process, so no
      // in-process teardown can free the handle. The copy is therefore left in
      // the config dir, which is per-invocation and never scanned twice, and the
      // assertion below is on the property CI actually depends on.
      QFile::remove( copy );
      QDir().rmdir( dupDir );
    }
  }

  // The shared fixture folder must be exactly as the workflow created it, so
  // that the NEXT invocation on it (the workflow scans the MDX folder three
  // times) sees the same dictionary set this one did. Asserted rather than
  // assumed: an unverified cleanup is precisely what made this fault invisible
  // for a whole run -- the leak reached the next invocation and was reported
  // there as an identity regression (fix-smoke-identity-cleanup-leak D2).
  {
    const QString leaked =
      QDir( QString::fromLocal8Bit( dictDir ) ).filePath( QStringLiteral( "dupcheck" ) );
    const QStringList entries =
      QFileInfo::exists( leaked )
        ? QDir( leaked ).entryList( QDir::AllEntries | QDir::NoDotAndDotDot )
        : QStringList();
    if ( !entries.isEmpty() ) {
      identityCleanupOk = false;
      std::printf( "DICT_IDENTITY_CLEANUP=FAIL (the fixture folder was modified: %s/%s)\n",
                   qPrintable( leaked ), qPrintable( entries.join( QLatin1Char( ' ' ) ) ) );
    }
    else {
      std::printf( "DICT_IDENTITY_CLEANUP=OK\n" );
    }
  }

  gd_cleanup();

  return ( lookSz > 0 && sugN > 0 && ftsOk && dedupOk && dictOk && optPartsOk && groupsOk
           && resourceThreadOk && reimportOk && stardictLinkOk && identityOk && identityCleanupOk
           && scanFailuresOk )
             ? 0
             : 1;
}