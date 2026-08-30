// Aurelex spike smoke test — host build.
// Links the carved engine + boundary and exercises the gd_* C API against a
// synthetic StarDict dictionary, printing results. This validates the whole
// carve + boundary end-to-end without a device.
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

extern "C" {
int gd_init( const char * config_dir, const char * index_dir );
int gd_scan_dicts( const char * folder );
int gd_suggest( const char * word, char * out, int out_size );
int gd_lookup( const char * word, char * out, int out_size );
void gd_cleanup();
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
  }

  gd_cleanup();
  return ( lookSz > 0 && sugN > 0 ) ? 0 : 1;
}