// Aurelex boundary — the gd_* C API (design D2).
//
// This is the ONLY surface Kotlin talks to via JNI. It wires the carved
// goldendict-ng engine (WorldFinder, Stardict::makeDictionaries,
// ArticleMaker) without touching any upstream file: folder-scan policy,
// config-home override, and buffer/lifetime handling live here.
//
// The public contract is declared in goldendict.h; this file implements it.
// FTS is deliberately not exposed.
#include "config.hh"
#include "globalbroadcaster.hh"
#include "instances.hh"
#include "dict/dictionary.hh"
#include "dict/stardict.hh"
#include "dict/mdx.hh"
#include "dict/dsl.hh"
#include "article_maker.hh"
#include "wordfinder.hh"
#include "goldendict.h"

#include <QCoreApplication>
#include <QGuiApplication>
#include <QDir>
#include <QEventLoop>
#include <QTimer>
#include <QUrl>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

using std::string;
using std::vector;

namespace {

// QCoreApplication requires a non-null argv[0]; keep a stable dummy.
int g_argc_dummy = 1;
char g_argv0_dummy[] = "aurelex";
char * g_argv_dummy[ 2 ] = { g_argv0_dummy, nullptr };

struct EngineState
{
  Config::Class cfg;
  vector< sptr< Dictionary::Class > > dictionaries;
  // ArticleMaker holds these vectors BY REFERENCE — they must outlive it.
  // Keep stable storage in the engine state; single-group (all dicts) in v1.
  vector< Instances::Group > groups;
  std::unique_ptr< ArticleMaker > articleMaker;
  QString indexDir;
};

// Minimal Dictionary::Initializing — indexing progress is surfaced by the
// Kotlin side from explicit scan progress, so these are no-ops.
struct ProgressSink : Dictionary::Initializing
{
  void indexingDictionary( const string & ) noexcept override {}
  void loadingDictionary( const string & ) noexcept override {}
};

EngineState * g_state = nullptr;

// The engine (its dict backends, ArticleMaker, WordFinder) is not thread-safe.
// Kotlin calls through JNI on a background dispatcher, so serialize every
// entry point here. All gd_* functions are blocking and share g_state.
std::mutex g_engineMutex;

vector< string > collectFiles( const QString & dirPath, const QStringList & filters )
{
  vector< string > out;
  QDir dir( dirPath );
  const QFileInfoList entries = dir.entryInfoList( filters, QDir::Files | QDir::NoDotAndDotDot );
  for ( const QFileInfo & i : entries ) {
    out.push_back( QDir::toNativeSeparators( i.absoluteFilePath() ).toStdString() );
  }
  return out;
}

} // namespace

extern "C" {

int gd_init( const char * config_dir, const char * index_dir )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( g_state )
    return 0;

  if ( !qEnvironmentVariableIsSet( "HOME" ) ) {
    qputenv( "HOME", QByteArray( config_dir ) );
  }

  // The engine is event-driven; the carve links QtGui, but the Android Qt kit
  // ships no offscreen platform plugin (only the QtActivity-bound qtforandroid
  // one), so a QGuiApplication here would fatal "no platform plugin". The GUI
  // symbols the carve needs are stubbed in patches/ (getOptimalIconSize and
  // tiff's primaryScreen). On Android a plain QCoreApplication (created on the
  // main thread by the JNI layer) is created for the engine's event loops; on
  // host (Windows) the smoke tool still uses QGuiApplication/offscreen.
  if ( !QCoreApplication::instance() ) {
#ifndef Q_OS_ANDROID
    new QGuiApplication( g_argc_dummy, g_argv_dummy );
#else
    new QCoreApplication( g_argc_dummy, g_argv_dummy );
#endif
  }
  QCoreApplication::setOrganizationName( "aurelex" );
  QCoreApplication::setApplicationName( "aurelex" );

  g_state = new EngineState;
  g_state->indexDir = QString::fromUtf8( index_dir );
  // "modern" display style enables the dark mode stylesheet variant
  // (article_maker only emits article-style-darkmode.css for displayStyle
  // "modern"); darkreader.js is emitted for any style when dark mode is on.
  g_state->cfg.preferences.displayStyle = QStringLiteral( "modern" );
  // ArticleMaker holds const refs to dictionaries/groups; keep them stable and
  // empty groups -> makeDefinitionFor falls back to ALL dictionaries (the v1
  // single "unfiltered" group, design D-specs).
  g_state->articleMaker =
    std::make_unique< ArticleMaker >( g_state->dictionaries, g_state->groups, g_state->cfg.preferences );

  // GlobalBroadcaster's config/Preferences must be set before ArticleMaker
  // is used — makeHtmlHeader consults getPreference()/dark-mode.
  GlobalBroadcaster::instance()->setConfig( &g_state->cfg );
  return 1;
}

int gd_scan_dicts( const char * folder )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;

  const QString dirPath = QString::fromUtf8( folder );
  const QStringList filters{ QStringLiteral( "*.ifo" ), // StarDict
                             QStringLiteral( "*.dsl" ),  QStringLiteral( "*.dsl.dz" ), //
                             QStringLiteral( "*.mdx" ) };

  const vector< string > files = collectFiles( dirPath, filters );
  const QString indexDir       = g_state->indexDir;

  ProgressSink sink;
  const string idxPath = indexDir.toStdString();

  const size_t before = g_state->dictionaries.size();

  auto stardicts = Stardict::makeDictionaries( files, idxPath, sink, 500000 );
  auto mdxs      = Mdx::makeDictionaries( files, idxPath, sink );
  auto dsls      = Dsl::makeDictionaries( files, idxPath, sink, 500000 );

  for ( auto & d : stardicts ) {
    g_state->dictionaries.push_back( std::move( d ) );
  }
  for ( auto & d : mdxs ) {
    g_state->dictionaries.push_back( std::move( d ) );
  }
  for ( auto & d : dsls ) {
    g_state->dictionaries.push_back( std::move( d ) );
  }

  g_state->articleMaker =
    std::make_unique< ArticleMaker >( g_state->dictionaries, g_state->groups, g_state->cfg.preferences );

  return static_cast< int >( g_state->dictionaries.size() - before );
}

int gd_suggest( const char * word, char * out, int out_size )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state || !out || out_size <= 0 )
    return -1;

  WordFinder wf( nullptr );
  bool done = false;
  QObject::connect( &wf, &WordFinder::finished, &wf, [ &done ]() {
    done = true;
  } );
  wf.prefixMatch( QString::fromUtf8( word ), g_state->dictionaries, 100 );

  // Drive the async search to completion with a real event loop (WordFinder
  // uses a 1s results timer + queued signals). Bounded at ~10s.
  QEventLoop loop;
  QTimer::singleShot( 10000, &loop, &QEventLoop::quit );
  QObject::connect( &wf, &WordFinder::finished, &loop, &QEventLoop::quit );
  loop.exec();

  const WordFinder::SearchResults results = wf.getResults();

  string joined;
  for ( size_t i = 0; i < results.size() && i < 16; ++i ) {
    if ( i )
      joined += '\n';
    joined += results[ i ].first.toUtf8().constData();
  }

  if ( static_cast< int >( joined.size() ) + 1 > out_size )
    return -2;
  std::memcpy( out, joined.c_str(), joined.size() + 1 );
  return static_cast< int >( results.size() );
}

int gd_lookup( const char * word, char * out, int out_size )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state || !out || out_size <= 0 )
    return -1;

  const QString w = QString::fromUtf8( word );
  auto req = g_state->articleMaker->makeDefinitionFor(
    w, 0, QMap< QString, QString >(), QSet< QString >(), QStringList(), false );

  // ArticleRequest delivers via queued signals; pump a real event loop
  // (bounded). Keep req alive until it is truly finished.
  QEventLoop loop;
  QTimer::singleShot( 15000, &loop, &QEventLoop::quit );
  QObject::connect( req.get(), &Dictionary::Request::finished, &loop, &QEventLoop::quit );
  if ( !req->isFinished() )
    loop.exec();

  if ( !req->isFinished() )
    return -3;

  const auto & data = req->getFullData();
  if ( out_size <= static_cast< int >( data.size() ) )
    return -4;

  std::memcpy( out, data.data(), data.size() );
  out[ data.size() ] = '\0';
  return static_cast< int >( data.size() );
}

// Fetch an embedded resource (image/audio) by bres:// or gdau:// URL, the same
// way upstream ArticleNetworkAccessManager::handleDictionaryResource resolves
// it: url.host() = dictionary id, url.path() = resource path.
static int fetchResource( const QString & urlString, char * out, int out_size )
{
  if ( !g_state || !out || out_size <= 0 )
    return -1;

  const QUrl url( urlString );
  const string id = url.host().toStdString();

  std::lock_guard< std::mutex > lock( g_engineMutex );

  Dictionary::Class * found = nullptr;
  for ( const auto & d : g_state->dictionaries ) {
    if ( d->getId() == id ) {
      found = d.get();
      break;
    }
  }
  if ( !found )
    return -2;

  sptr< Dictionary::DataRequest > req;
  try {
    req = found->getResource( Utils::Url::path( url ).mid( 1 ).toUtf8().data() );
  }
  catch ( std::exception & e ) {
    qWarning( "getResource request error (%s) in \"%s\"", e.what(), found->getName().c_str() );
    return -2;
  }
  if ( !req.get() )
    return -2;

  QEventLoop loop;
  QTimer::singleShot( 15000, &loop, &QEventLoop::quit );
  QObject::connect( req.get(), &Dictionary::Request::finished, &loop, &QEventLoop::quit );
  if ( !req->isFinished() )
    loop.exec();

  if ( !req->isFinished() )
    return -3;

  const auto & data = req->getFullData();
  if ( out_size <= static_cast< int >( data.size() ) )
    return -4;

  std::memcpy( out, data.data(), data.size() );
  out[ data.size() ] = '\0';
  return static_cast< int >( data.size() );
}

int gd_get_resource( const char * url, char * out, int out_size )
{
  return fetchResource( QString::fromUtf8( url ), out, out_size );
}

int gd_get_audio( const char * url, char * out, int out_size )
{
  return fetchResource( QString::fromUtf8( url ), out, out_size );
}

int gd_dict_count()
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  return g_state ? static_cast< int >( g_state->dictionaries.size() ) : 0;
}

int gd_dict_info( int index, char * name, int name_size, char * file, int file_size )
{
  if ( !g_state || !name || name_size <= 0 || !file || file_size <= 0 )
    return -1;
  std::lock_guard< std::mutex > lock( g_engineMutex );

  if ( index < 0 || index >= static_cast< int >( g_state->dictionaries.size() ) )
    return -1;

  Dictionary::Class & d = *g_state->dictionaries[ index ];

  const string n = d.getName();
  if ( static_cast< int >( n.size() ) + 1 > name_size )
    return -1;
  std::memcpy( name, n.c_str(), n.size() + 1 );

  string f;
  const auto & filenames = d.getDictionaryFilenames();
  if ( !filenames.empty() )
    f = filenames.front();
  if ( static_cast< int >( f.size() ) + 1 > file_size )
    return -1;
  std::memcpy( file, f.c_str(), f.size() + 1 );

  return 0;
}

int gd_move_dict( int from, int to )
{
  if ( !g_state )
    return -1;
  std::lock_guard< std::mutex > lock( g_engineMutex );

  const int n = static_cast< int >( g_state->dictionaries.size() );
  if ( from < 0 || to < 0 || from >= n || to >= n )
    return -1;

  auto & v = g_state->dictionaries;
  auto it = v.begin() + from;
  sptr< Dictionary::Class > item = std::move( *it );
  v.erase( it );
  v.insert( v.begin() + to, std::move( item ) );

  // ArticleMaker holds a const ref to the vector; the vector object itself is
  // stable (only order changed), but rebuild anyway so group order is applied
  // on the next lookup.
  g_state->articleMaker =
    std::make_unique< ArticleMaker >( g_state->dictionaries, g_state->groups, g_state->cfg.preferences );
  return 0;
}

int gd_set_dark_mode( int on )
{
  if ( !g_state )
    return -1;
  std::lock_guard< std::mutex > lock( g_engineMutex );

  g_state->cfg.preferences.darkReaderMode =
    on ? Config::Dark::On : Config::Dark::Off;

  // ArticleMaker reads the preference via GlobalBroadcaster for the header.
  GlobalBroadcaster::instance()->setConfig( &g_state->cfg );
  return 0;
}

void gd_cleanup()
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  delete g_state;
  g_state = nullptr;
}

// Audio backends (QtMultimedia/ffmpeg) are not part of the v1 carve — but
// config.cc consults this to pick a default player. Report none available;
// the Kotlin side plays audio directly (design D4/D8).
#include "audio/internalplayerbackend.hh"
bool InternalPlayerBackend::anyAvailable()
{
  return false;
}

} // extern "C"