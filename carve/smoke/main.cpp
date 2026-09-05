// Aurelex spike smoke test — host build.
// Links the carved engine + boundary and exercises the gd_* C API against a
// synthetic StarDict dictionary, printing results. This validates the whole
// carve + boundary end-to-end without a device.
#include "goldendict.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

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

  if ( !gd_init( configDir, configDir ) ) {
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

  // Re-scanning the same folder must not duplicate already-loaded dictionaries
  // (the UI re-stages + re-scans on every add; id = md5 over the file paths).
  const int n2 = gd_scan_dicts( dictDir );
  std::printf( "gd_scan_dicts(again) -> %d new (expect 0)\n", n2 );
  const bool dedupOk = n2 == 0;
  bool dictOk = true; // refined by the removal block below

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

  // ---- groups smoke (multi-group-management) ----
  // CI folder has the StarDict ("smoke") plus a .dsl.dz (no "smoke") and a
  // nested .dsl; locate the primary files by suffix since scan order is not
  // guaranteed.
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
  return ( lookSz > 0 && sugN > 0 && ftsOk && dedupOk && dictOk ) ? 0 : 1;
}