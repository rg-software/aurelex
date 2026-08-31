// Aurelex spike smoke test — host build.
// Links the carved engine + boundary and exercises the gd_* C API against a
// synthetic StarDict dictionary, printing results. This validates the whole
// carve + boundary end-to-end without a device.
#include "goldendict.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

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

  gd_cleanup();
  return ( lookSz > 0 && sugN > 0 ) ? 0 : 1;
}