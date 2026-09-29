// Aurelex spike smoke test — host build.
// Links the carved engine + boundary and exercises the gd_* C API against a
// synthetic StarDict dictionary, printing results. This validates the whole
// carve + boundary end-to-end without a device.
#include "goldendict.h"
#include "index_path.hpp"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QThread>

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

int main( int argc, char ** argv )
{
  setvbuf( stdout, nullptr, _IONBF, 0 );

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
  bool dictOk = true; // refined by the removal block below
  bool optPartsOk = false; // refined by the DSL hidden-zone block below

  std::vector< char > sug( 1 << 12 );
  const int sugN = gd_suggest( "smok", sug.data(), static_cast< int >( sug.size() ) );
  std::printf( "gd_suggest(\"smok\") -> %d results\n", sugN );
  if ( sugN > 0 ) {
    std::printf( "SUGGEST: %s\n", sug.data() );
  }

  std::vector< char > out( 1 << 20 );
  const int lookSz = gd_lookup( word, out.data(), static_cast< int >( out.size() ) );
  std::printf( "gd_lookup(\"%s\") -> %d bytes\n", word, lookSz );
  if ( lookSz > 0 ) {
    std::printf( "BEGIN\\%.*s\nEND\n", lookSz < 800 ? lookSz : 800, out.data() );
    const std::string html( out.data(), lookSz );
    std::printf( "MARKERS: gdarticlebody=%s gdarticle=%s\n",
                 html.find( "gdarticlebody" ) != std::string::npos ? "yes" : "no",
                 html.find( "gdarticle" ) != std::string::npos ? "yes" : "no" );
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

  // Exercise the resource/audio fetch: pick the first bres:// or gdau:// URL
  // the article references (if any) and stream it back through the boundary.
  const std::string html( out.data(), lookSz > 0 ? lookSz : 0 );
  for ( const char * scheme : { "bres://", "gdau://" } ) {
    const size_t pos = html.find( scheme );
    if ( pos == std::string::npos )
      continue;
    size_t end = pos;
    while ( end < html.size() && html[ end ] != '"' && html[ end ] != '>' && html[ end ] != '\n' )
      ++end;
    const std::string url = html.substr( pos, end - pos );
    std::vector< char > res( 1 << 20 );
    const int resSz = gd_get_resource( url.c_str(), res.data(), static_cast< int >( res.size() ) );
    std::printf( "gd_get_resource(\"%s\") -> %d bytes (used as audio: gd_get_audio same path)\n",
                 url.c_str(),
                 resSz );
    (void)res;
    break;
  }

  // ---- DSL optional/hidden-zone expander smoke (dsl-optional-parts-toggle) ----
  // The engine renders `[*]...[/opt]` as a hidden `.dsl_opt` span plus one
  // `<img class="hidden_expand_opt" onclick="gdExpandOptPart(...)">` per article
  // that has hidden zones. The app supplies the handler (assets/scripts/
  // gd-article-controls.js); this pins the engine-side markup that handler
  // depends on, so an upstream bump that stops emitting it fails CI here
  // instead of shipping a dead control.
  {
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
  bool ftsOk = false;
  const int sdIdx = findDictBySuffix( ".ifo" );
  std::printf( "gd_suffix(.ifo) -> %d\n", sdIdx );
  if ( sdIdx < 0 ) {
    std::fprintf( stderr, "StarDict fixture not found (no .ifo primary)\n" );
    gd_cleanup();
    return 1;
  }
  {
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
  bool resourceThreadOk = false;
  {
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
  bool reimportOk = false;
  {
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
  {
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

  gd_cleanup();
  return ( lookSz > 0 && sugN > 0 && ftsOk && dedupOk && dictOk && optPartsOk && groupsOk
           && resourceThreadOk && reimportOk )
             ? 0
             : 1;
}