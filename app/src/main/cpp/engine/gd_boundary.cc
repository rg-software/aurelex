// Aurelex boundary — the gd_* C API (design D2).
//
// This is the ONLY surface Kotlin talks to via JNI. It wires the carved
// goldendict-ng engine (WorldFinder, Stardict::makeDictionaries,
// ArticleMaker) without touching any upstream file: folder-scan policy,
// config-home override, and buffer/lifetime handling live here.
//
// StarDict-first for the Phase-0 smoke; DSL/MDX added the same way (their
// makeDictionaries are upstream API). FTS is deliberately not exposed.
#include "config.hh"
#include "globalbroadcaster.hh"
#include "instances.hh"
#include "dict/dictionary.hh"
#include "dict/stardict.hh"
#include "article_maker.hh"
#include "wordfinder.hh"

#include <QCoreApplication>
#include <QGuiApplication>
#include <QDir>
#include <QEventLoop>
#include <QTimer>
#include <cstring>
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
  if ( g_state )
    return 0;

  if ( !qEnvironmentVariableIsSet( "HOME" ) ) {
    qputenv( "HOME", QByteArray( config_dir ) );
  }

  // The engine is event-driven AND touches QGuiApplication symbols while
  // rendering articles (getOptimalIconSize reads qGuiApp->devicePixelRatio()).
  // A QCoreApplication would leave qGuiApp null and crash. Use QGuiApplication
  // (works headless; on Android the app owns the GUI anyway).
  if ( !QGuiApplication::instance() ) {
    if ( !qEnvironmentVariableIsSet( "QT_QPA_PLATFORM" ) ) {
      qputenv( "QT_QPA_PLATFORM", "offscreen" );
    }
    new QGuiApplication( g_argc_dummy, g_argv_dummy );
  }

  QCoreApplication::setOrganizationName( "aurelex" );
  QCoreApplication::setApplicationName( "aurelex" );

  g_state = new EngineState;
  g_state->indexDir = QString::fromUtf8( index_dir );
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
  if ( !g_state )
    return -1;

  const QString dirPath = QString::fromUtf8( folder );
  const QStringList filters{ QStringLiteral( "*.ifo" ), // StarDict
                             QStringLiteral( "*.dsl" ),  QStringLiteral( "*.dsl.dz" ), //
                             QStringLiteral( "*.mdx" ) };

  const vector< string > files = collectFiles( dirPath, filters );
  const QString indexDir       = g_state->indexDir;

  ProgressSink sink;
  auto stardicts = Stardict::makeDictionaries( files, indexDir.toStdString(), sink, 500000 );

  for ( auto & d : stardicts ) {
    g_state->dictionaries.push_back( std::move( d ) );
  }

  g_state->articleMaker =
    std::make_unique< ArticleMaker >( g_state->dictionaries, g_state->groups, g_state->cfg.preferences );

  return static_cast< int >( stardicts.size() );
}

int gd_suggest( const char * word, char * out, int out_size )
{
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

void gd_cleanup()
{
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