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
#include "ftshelpers.hh"
#include "goldendict.h"

#include <QAtomicInt>
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

// Boundary-side group definition (id/name/ordered dict indices). Materialized
// into Instances::Group (which holds sptr references to the dictionaries).
struct GroupDef
{
  unsigned id   = 0;
  QString name;
  vector< unsigned > dictIndices; // indices into EngineState::dictionaries
};

struct EngineState
{
  Config::Class cfg;
  vector< sptr< Dictionary::Class > > dictionaries;
  // ArticleMaker holds these vectors BY REFERENCE — they must outlive it.
  // Keep stable storage in the engine state; single-group (all dicts) in v1.
  vector< Instances::Group > groups;
  std::unique_ptr< ArticleMaker > articleMaker;
  QString indexDir;

  // --- groups model (task 2.x) ---
  // id 0 is the implicit "All" group (every dictionary, in global order).
  // Additional groups are defined here (id/name/ordered dict indices) and
  // materialized into Instances::Group (which references sptr dictionaries).
  unsigned activeGroupId   = 0;
  unsigned nextGroupId     = 1;
  vector< GroupDef > groupDefs;
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

// Materialize EngineState::groupDefs + dictionaries into EngineState::groups
// (Instances::Group holding sptr refs) and rebuild ArticleMaker, whose group
// vector it holds BY REFERENCE. Must be called with g_engineMutex held and
// after any change to groups or dictionaries.
void rebuildGroups()
{
  const auto & st  = *g_state;
  vector< Instances::Group > built;
  built.reserve( st.groupDefs.size() );

  // Group 0 = "All": every dictionary in global order.
  {
    Instances::Group all( 0, QStringLiteral( "All" ) );
    all.dictionaries = st.dictionaries;
    built.push_back( std::move( all ) );
  }
  for ( const auto & def : st.groupDefs ) {
    Instances::Group g( def.id, def.name );
    for ( unsigned idx : def.dictIndices ) {
      if ( idx < st.dictionaries.size() ) {
        g.dictionaries.push_back( st.dictionaries[ idx ] );
      }
    }
    built.push_back( std::move( g ) );
  }

  g_state->groups = std::move( built );
  g_state->articleMaker =
    std::make_unique< ArticleMaker >( g_state->dictionaries, g_state->groups, g_state->cfg.preferences );
}

// Find the boundary GroupDef with the given id, or nullptr (0 = "All" is
// implicit and has no GroupDef).
GroupDef * findGroupDef( unsigned id )
{
  for ( auto & d : g_state->groupDefs ) {
    if ( d.id == id )
      return &d;
  }
  return nullptr;
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
  // FTS is re-enabled on Android (full-text-search change): every v1 dict
  // (mdx/dsl/stardict) is full-text searchable by default. Upstream enables
  // this from cfg.preferences.fts in mainwindow.cc; the boundary must do the
  // same, otherwise Dictionary::Class::can_FTS stays false and indexing is a
  // no-op. maxDictionarySize=0 means no size cap.
  g_state->cfg.preferences.fts.enabled          = true;
  g_state->cfg.preferences.fts.maxDictionarySize = 0;
  g_state->cfg.preferences.fts.disabledTypes     = QString();
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

  // Dedup: a dictionary id is an MD5 over its (sorted) source file paths, and
  // the UI re-stages + re-scans the same folder on every add, so skip anything
  // whose id is already loaded rather than appending a duplicate.
  QSet< QString > loadedIds;
  loadedIds.reserve( static_cast< int >( g_state->dictionaries.size() ) );
  for ( const auto & d : g_state->dictionaries )
    loadedIds.insert( QString::fromStdString( d->getId() ) );

  auto stardicts = Stardict::makeDictionaries( files, idxPath, sink, 500000 );
  auto mdxs      = Mdx::makeDictionaries( files, idxPath, sink );
  auto dsls      = Dsl::makeDictionaries( files, idxPath, sink, 500000 );

  auto keepIfNew = [ &loadedIds ]( auto & v ) {
    auto it = std::remove_if( v.begin(), v.end(), [ &loadedIds ]( const auto & d ) {
      return loadedIds.contains( QString::fromStdString( d->getId() ) );
    } );
    v.erase( it, v.end() );
    for ( auto & d : v )
      loadedIds.insert( QString::fromStdString( d->getId() ) );
  };
  keepIfNew( stardicts );
  keepIfNew( mdxs );
  keepIfNew( dsls );

  for ( auto & d : stardicts ) {
    d->setFTSParameters( g_state->cfg.preferences.fts );
    g_state->dictionaries.push_back( std::move( d ) );
  }
  for ( auto & d : mdxs ) {
    d->setFTSParameters( g_state->cfg.preferences.fts );
    g_state->dictionaries.push_back( std::move( d ) );
  }
  for ( auto & d : dsls ) {
    d->setFTSParameters( g_state->cfg.preferences.fts );
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
  // Use the active group (0 = "All"); article_maker filters to its dictionaries.
  auto req = g_state->articleMaker->makeDefinitionFor(
    w, g_state->activeGroupId, QMap< QString, QString >(), QSet< QString >(), QStringList(), false );

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

  // ArticleMaker holds a const ref to the vector; rebuild so the "All" group
  // (and any group referencing dictionaries by index) reflects the new order.
  rebuildGroups();
  return 0;
}

// --- groups API (milestone multi-group-management) ---

int gd_group_count()
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state )
    return 0;
  // 1 (the implicit "All") + user groups.
  return 1 + static_cast< int >( g_state->groupDefs.size() );
}

int gd_group_info( int index, int * id_out, char * name, int name_size, int * dict_count_out )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state || !id_out || !name || name_size <= 0 || !dict_count_out )
    return -1;
  if ( index < 0 || index > static_cast< int >( g_state->groupDefs.size() ) )
    return -1;

  if ( index == 0 ) {
    // "All" group
    *id_out = 0;
    const string n = "All";
    if ( static_cast< int >( n.size() ) + 1 > name_size )
      return -1;
    std::memcpy( name, n.c_str(), n.size() + 1 );
    *dict_count_out = static_cast< int >( g_state->dictionaries.size() );
    return 0;
  }

  const GroupDef & def = g_state->groupDefs[ index - 1 ];
  *id_out              = static_cast< int >( def.id );
  const QByteArray nb  = def.name.toUtf8();
  if ( nb.size() + 1 > name_size )
    return -1;
  std::memcpy( name, nb.constData(), nb.size() + 1 );
  *dict_count_out = static_cast< int >( def.dictIndices.size() );
  return 0;
}

int gd_group_create( const char * name, int * id_out )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state || !id_out || !name || !*name )
    return -1;
  GroupDef def;
  def.id   = g_state->nextGroupId++;
  def.name = QString::fromUtf8( name );
  g_state->groupDefs.push_back( std::move( def ) );
  *id_out = static_cast< int >( g_state->groupDefs.back().id );
  rebuildGroups();
  return 0;
}

int gd_group_rename( int id, const char * name )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state || !name || !*name )
    return -1;
  if ( id == 0 )
    return -1; // "All" cannot be renamed
  GroupDef * def = findGroupDef( static_cast< unsigned >( id ) );
  if ( !def )
    return -1;
  def->name = QString::fromUtf8( name );
  rebuildGroups();
  return 0;
}

int gd_group_delete( int id )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;
  if ( id == 0 )
    return -1; // "All" cannot be deleted
  auto it = std::find_if( g_state->groupDefs.begin(), g_state->groupDefs.end(),
                          [ id ]( const GroupDef & d ) { return d.id == static_cast< unsigned >( id ); } );
  if ( it == g_state->groupDefs.end() )
    return -1;
  g_state->groupDefs.erase( it );
  // If the active group was deleted, revert to "All" (task 1.3).
  if ( g_state->activeGroupId == static_cast< unsigned >( id ) ) {
    g_state->activeGroupId = 0;
  }
  rebuildGroups();
  return 0;
}

int gd_group_add_dict( int id, int dict_index )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;
  if ( id == 0 || dict_index < 0 || dict_index >= static_cast< int >( g_state->dictionaries.size() ) )
    return -1;
  GroupDef * def = findGroupDef( static_cast< unsigned >( id ) );
  if ( !def )
    return -1;
  const unsigned u = static_cast< unsigned >( dict_index );
  if ( std::find( def->dictIndices.begin(), def->dictIndices.end(), u ) == def->dictIndices.end() ) {
    def->dictIndices.push_back( u );
    rebuildGroups();
  }
  return 0;
}

int gd_group_remove_dict( int id, int dict_index )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;
  if ( id == 0 || dict_index < 0 )
    return -1;
  GroupDef * def = findGroupDef( static_cast< unsigned >( id ) );
  if ( !def )
    return -1;
  auto & v = def->dictIndices;
  auto it  = std::find( v.begin(), v.end(), static_cast< unsigned >( dict_index ) );
  if ( it != v.end() ) {
    v.erase( it );
    rebuildGroups();
  }
  return 0;
}

int gd_group_move_dict( int id, int from, int to )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;
  if ( id == 0 )
    return -1; // "All" order is the global dictionary order (gd_move_dict)
  GroupDef * def = findGroupDef( static_cast< unsigned >( id ) );
  if ( !def )
    return -1;
  auto & v = def->dictIndices;
  const int n = static_cast< int >( v.size() );
  if ( from < 0 || to < 0 || from >= n || to >= n )
    return -1;
  auto it = v.begin() + from;
  unsigned item = *it;
  v.erase( it );
  v.insert( v.begin() + to, item );
  rebuildGroups();
  return 0;
}

int gd_group_active( int * id_out )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state || !id_out )
    return -1;
  *id_out = static_cast< int >( g_state->activeGroupId );
  return 0;
}

int gd_group_set_active( int id )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;
  if ( id != 0 && !findGroupDef( static_cast< unsigned >( id ) ) )
    return -1;
  g_state->activeGroupId = static_cast< unsigned >( id );
  return 0;
}

int gd_group_dicts( int id, int * out, int out_capacity )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state || !out || out_capacity <= 0 )
    return -1;

  if ( id == 0 ) {
    const int n = static_cast< int >( g_state->dictionaries.size() );
    if ( n > out_capacity )
      return -1;
    for ( int i = 0; i < n; ++i )
      out[ i ] = i;
    return n;
  }

  GroupDef * def = findGroupDef( static_cast< unsigned >( id ) );
  if ( !def )
    return -1;
  if ( static_cast< int >( def->dictIndices.size() ) > out_capacity )
    return -1;
  for ( size_t i = 0; i < def->dictIndices.size(); ++i )
    out[ i ] = static_cast< int >( def->dictIndices[ i ] );
  return static_cast< int >( def->dictIndices.size() );
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

// --- full-text search (xapian, re-enabled for v1) ---

int gd_fts_index( int dict_index )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state || dict_index < 0 || dict_index >= static_cast< int >( g_state->dictionaries.size() ) )
    return -1;

  Dictionary::Class & d = *g_state->dictionaries[ dict_index ];
  if ( !d.canFTS() )
    return -1; // not full-text searchable

  // makeFTSIndex() is the dict backend's virtual override (builds or reuses
  // the xapian index). Blocking by design (D4): Kotlin drives it on the
  // engine's single worker thread and shows a "building" state itself.
  QAtomicInt isCancelled;
  try {
    d.makeFTSIndex( isCancelled );
  }
  catch ( std::exception & ) {
    return -1;
  }
  return 0;
}

int gd_fts_index_state( int dict_index, int * out )
{
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state || !out || dict_index < 0 || dict_index >= static_cast< int >( g_state->dictionaries.size() ) )
    return -1;

  Dictionary::Class & d = *g_state->dictionaries[ dict_index ];
  if ( !d.canFTS() )
    return -1;

  *out = d.haveFTSIndex() ? 0 : 1; // 0 built, 1 missing/stale
  return 0;
}

int gd_fts_search( const char * query, int mode, int group_id, char * out, int out_size )
{
  if ( !query || !out || out_size <= 0 )
    return -1;
  std::lock_guard< std::mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;

  // Resolve group 0 ("All") or the named group to its ordered dict indices.
  vector< unsigned > dictIndices;
  if ( group_id == 0 ) {
    dictIndices.reserve( g_state->dictionaries.size() );
    for ( unsigned i = 0; i < g_state->dictionaries.size(); ++i )
      dictIndices.push_back( i );
  }
  else {
    GroupDef * def = findGroupDef( static_cast< unsigned >( group_id ) );
    if ( !def )
      return -1;
    dictIndices = def->dictIndices;
  }

  const QString q = QString::fromUtf8( query );

  string joined;
  bool anyIndexed = false;

  for ( unsigned idx : dictIndices ) {
    Dictionary::Class & d = *g_state->dictionaries[ idx ];
    // Skip dictionaries without an index; the caller builds one first
    // (gd_fts_index) and gets -3 when no indexed dictionary exists.
    if ( !d.canFTS() || !d.haveFTSIndex() )
      continue;
    anyIndexed = true;

    sptr< Dictionary::DataRequest > req;
    try {
      req = d.getSearchResults( q, mode, false, false );
    }
    catch ( std::exception & ) {
      continue;
    }
    if ( !req )
      continue;

    // FTSResultsRequest runs async internally; wait (bounded) like gd_lookup.
    QEventLoop loop;
    QTimer::singleShot( 15000, &loop, &QEventLoop::quit );
    QObject::connect( req.get(), &Dictionary::Request::finished, &loop, &QEventLoop::quit );
    if ( !req->isFinished() )
      loop.exec();
    if ( !req->isFinished() )
      continue;

    // The request serializes a pointer to its QList<FTS::FtsHeadword> into
    // the data buffer; copy it out the way upstream fulltextsearch.cc does.
    if ( req->dataSize() < static_cast< long >( sizeof( QList< FTS::FtsHeadword > * ) ) )
      continue; // no data: no matches in this dictionary

    QList< FTS::FtsHeadword > * found = nullptr;
    req->getDataSlice( 0, sizeof( found ), &found );
    if ( !found )
      continue;

    QList< FTS::FtsHeadword > headwords;
    headwords.swap( *found );
    delete found;

    // Second field is the dictionary's display name (gd_dict_info returns the
    // same string) so the UI can label the result without an id->name map;
    // the engine's internal id is opaque and GPL-log-based.
    const string dictName = d.getName();
    for ( const FTS::FtsHeadword & h : headwords ) {
      if ( !joined.empty() )
        joined += '\n';
      joined += h.headword.toUtf8().constData();
      joined += '\t';
      joined += dictName;
    }
  }

  if ( !anyIndexed )
    return -3; // no dictionary in the group has a full-text index yet

  if ( static_cast< int >( joined.size() ) + 1 > out_size )
    return -2;

  std::memcpy( out, joined.c_str(), joined.size() + 1 );

  int count = 0;
  for ( const char c : joined ) {
    if ( c == '\n' )
      ++count;
  }
  if ( !joined.empty() )
    ++count;
  return count;
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