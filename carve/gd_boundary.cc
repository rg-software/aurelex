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
#include "langcoder.hh"
#include "goldendict.h"
#include "index_path.hpp"

#include <QAtomicInt>
#include <QCoreApplication>
#include <QGuiApplication>
#include <QDir>
#include <QDirIterator>
#include <QEventLoop>
#include <QElapsedTimer>
#include <QThread>
#include <QThreadPool>
#include <QTimer>
#include <QUrl>
#include <QStringList>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <cstring>
#include <exception>
#include <map>
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

// How long a single engine request may run before the boundary gives up on it
// and reports a timeout. This used to double as the GUI-freeze budget, because
// fetchResource() ran its wait on the Qt main thread; it no longer does (see
// openspec/changes/fix-article-server-gui-reentrancy). It is now purely a
// worker-occupancy budget: it bounds how long one wedged request can hold the
// caller's thread, and it is deliberately NOT a responsiveness number, so it
// should be re-chosen against measured engine times rather than inherited.
// The value is unchanged from the original inline 15000 pending that
// measurement; see design.md D3.
constexpr int kEngineRequestDeadlineMs = 15000;

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
  // User-defined order of the implicit "All" group, as dictionary IDs. The
  // underlying `dictionaries` vector stays in load order (groupDefs reference it
  // by index); rebuildGroups() materializes "All" in this order and normalizes
  // the list (drops removed dicts, appends newly imported ones). Empty = load
  // order. Persisted in groups.json.
  vector< std::string > allOrder;

  // Primary dictionary files that failed to load in the most recent
  // gd_scan_dicts calls (a corrupt/truncated/unparseable source). Consumed by
  // gd_scan_failures() so the app can surface exactly which dictionaries are
  // broken and tell the user to re-add the folder.
  QStringList lastScanFailures;

  // App-private config dir (from gd_init) — groups.json is persisted here.
  QString groupsConfigDir;

  // Per loaded dictionary (by id): the size + mtime of each of its source files
  // as they were when the dictionary was loaded. A re-import replaces a source
  // file in place, and the dictionary id (an MD5 of the source paths) does not
  // change, so a scan cannot tell "already loaded" from "replaced" by id alone.
  // These stamps are that missing signal: gd_scan_dicts drops an entry whose
  // files no longer match, so the replaced dictionary is reloaded instead of
  // being deduped away while the backend has rewritten its index underneath the
  // live object (see gd_scan_dicts). In-memory only: a fresh process has no
  // loaded dictionaries, and its first scan loads everything.
  struct SourceStamp
  {
    qint64 size    = -1;
    qint64 mtimeMs = -1;
  };
  std::map< std::string, std::vector< SourceStamp > > sourceStamps;

  // Dictionary currently being full-text indexed, kept alive by a shared ref
  // so a progress reader (UI poller) can sample getIndexingFtsProgress() even
  // while gd_fts_index is mid-build. Guarded by g_ftsProgressMutex (never by
  // g_engineMutex, so the poller never blocks behind a long build).
  sptr< Dictionary::Class > ftsProgressDict;
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
// Calls arrive from several threads (the app's engine pool, the FTS worker, and
// the Qt thread running the loopback ArticleServer), so serialize every entry
// point here. All gd_* functions are blocking and share g_state.
//
// RECURSIVE: several gd_* functions drive an async engine request to completion
// by pumping a nested QEventLoop (gd_lookup, gd_suggest, fetchResource, ...).
// A nested loop processes that thread's other events, so the SAME thread can
// re-enter a gd_* function while it still holds the lock. That happens in
// practice: the ArticleServer handles parallel bres:// request sockets on the
// Qt thread, and the first fetchResource's nested loop delivers the next
// socket's readyRead -> fetchResource again on the same thread. With a plain
// std::mutex that self-deadlocks (frozen UI, no crash). A recursive mutex lets
// the re-entrant call proceed while still serializing across different threads.
std::recursive_mutex g_engineMutex;

// Separate mutex for the FTS-progress slot. A long gd_fts_index build holds
// g_engineMutex for the whole run; a progress reader must be able to read the
// current build's percentage WITHOUT blocking behind it, so it never touches
// g_engineMutex. Lock order is always g_engineMutex -> g_ftsProgressMutex.
std::mutex g_ftsProgressMutex;

// --- FTS build state (fts-indexing-performance) ---
// The full-text build in flight, if any: its dictionary id is used by the
// lookup path to withhold it from results (design D2) and by gd_fts_cancel;
// g_ftsCancel is the token the engine polls (currently the never-set
// isCancelled is replaced by this). All guarded by g_ftsProgressMutex so
// readers never wait behind the build.
bool g_ftsBuildActive = false;
std::string g_ftsBuildId;
QAtomicInt g_ftsCancel;

// The set of dictionaries currently being built, for makeDefinitionFor's
// mutedDicts. Empty when idle. Caller holds g_engineMutex (lock order
// g_engineMutex -> g_ftsProgressMutex).
QSet< QString > mutedInFlightDict()
{
  QSet< QString > muted;
  std::lock_guard< std::mutex > plock( g_ftsProgressMutex );
  if ( g_ftsBuildActive && !g_ftsBuildId.empty() )
    muted.insert( QString::fromStdString( g_ftsBuildId ) );
  return muted;
}

vector< string > collectFiles( const QString & dirPath, const QStringList & filters )
{
  vector< string > out;
  // Recursive: a picked source folder is scanned including nested subfolders
  // (e.g. GoldenDict/English/, GoldenDict/Japanese/) so dictionaries in them
  // load. See folder-scoped-storage design D7.
  QDirIterator it( dirPath, filters,
                   QDir::Files | QDir::NoDotAndDotDot,
                   QDirIterator::Subdirectories );
  while ( it.hasNext() ) {
    out.push_back( QDir::toNativeSeparators( it.next() ).toStdString() );
  }
  return out;
}

// The size + mtime of each of a dictionary's source files, taken when it is
// loaded so a later scan can tell that the file was replaced (a re-import of an
// updated version, which keeps the same path and therefore the same id).
vector< EngineState::SourceStamp > stampSourceFiles( Dictionary::Class & d )
{
  vector< EngineState::SourceStamp > stamps;
  for ( const auto & f : d.getDictionaryFilenames() ) {
    const QFileInfo fi( QString::fromStdString( f ) );
    const bool exists = fi.exists();
    stamps.push_back( { exists ? fi.size() : -1, exists ? fi.lastModified().toMSecsSinceEpoch() : -1 } );
  }
  return stamps;
}

// True when a loaded dictionary's source files no longer match the stamps taken
// when it was loaded: a file was replaced or removed. A dictionary with no
// stamps is treated as changed.
bool dictionarySourceChanged( Dictionary::Class & d )
{
  const auto it = g_state->sourceStamps.find( d.getId() );
  if ( it == g_state->sourceStamps.end() )
    return true;
  const vector< string > & files                    = d.getDictionaryFilenames();
  const vector< EngineState::SourceStamp > & stamps = it->second;
  if ( files.size() != stamps.size() )
    return true;
  for ( size_t i = 0; i < files.size(); ++i ) {
    const QFileInfo fi( QString::fromStdString( files[ i ] ) );
    if ( !fi.exists() || fi.size() != stamps[ i ].size
         || fi.lastModified().toMSecsSinceEpoch() != stamps[ i ].mtimeMs )
      return true;
  }
  return false;
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

  // Group 0 = "All": every dictionary, in the user's chosen order (allOrder),
  // with any dictionary not yet listed appended in load order. Normalize
  // allOrder here so it always mirrors what is actually shown (and so a move
  // can index into it directly).
  {
    Instances::Group all( 0, QStringLiteral( "All" ) );
    all.dictionaries.reserve( st.dictionaries.size() );
    vector< std::string > normalized;
    normalized.reserve( st.dictionaries.size() );
    vector< bool > used( st.dictionaries.size(), false );
    for ( const auto & id : st.allOrder ) {
      for ( size_t i = 0; i < st.dictionaries.size(); ++i ) {
        if ( !used[ i ] && st.dictionaries[ i ]->getId() == id ) {
          all.dictionaries.push_back( st.dictionaries[ i ] );
          normalized.push_back( id );
          used[ i ] = true;
          break;
        }
      }
    }
    for ( size_t i = 0; i < st.dictionaries.size(); ++i ) {
      if ( !used[ i ] ) {
        all.dictionaries.push_back( st.dictionaries[ i ] );
        normalized.push_back( st.dictionaries[ i ]->getId() );
        used[ i ]      = true;
      }
    }
    g_state->allOrder = std::move( normalized );
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

// --- group persistence -----------------------------------------------------
// Groups live entirely in EngineState today and were never written to disk, so
// every app start recreated only the implicit "All" group. Persist groupDefs +
// activeGroupId to <configDir>/groups.json so user-defined groups survive
// relaunches (and upgrades: the config dir is app-private and persists).
//
// Membership is stored as dictionary IDs (the MD5 over the source-file paths),
// which are stable across restarts of the same staged dictionaries; on load we
// resolve each ID back to its index. Unknown/lost dicts are simply dropped.

QString groupsFilePath()
{
  return ( g_state && !g_state->groupsConfigDir.isEmpty() )
    ? g_state->groupsConfigDir + QStringLiteral( "/groups.json" )
    : QString();
}

void saveGroupsLocked()
{
  const QString path = groupsFilePath();
  if ( path.isEmpty() ) return;
  QJsonArray arr;
  for ( const auto & def : g_state->groupDefs ) {
    QJsonObject o;
    o.insert( "id", static_cast< double >( def.id ) );
    o.insert( "name", def.name );
    QJsonArray ids;
    for ( unsigned idx : def.dictIndices ) {
      if ( idx < g_state->dictionaries.size() ) {
        ids.append( QString::fromStdString( g_state->dictionaries[ idx ]->getId() ) );
      }
    }
    o.insert( "dictIds", ids );
    arr.append( o );
  }
  QJsonObject root;
  root.insert( "activeGroupId", static_cast< double >( g_state->activeGroupId ) );
  root.insert( "nextGroupId", static_cast< double >( g_state->nextGroupId ) );
  root.insert( "groups", arr );
  QJsonArray order;
  for ( const auto & id : g_state->allOrder )
    order.append( QString::fromStdString( id ) );
  root.insert( "allOrder", order );
  QFile f( path );
  if ( f.open( QIODevice::WriteOnly | QIODevice::Truncate ) ) {
    f.write( QJsonDocument( root ).toJson( QJsonDocument::Compact ) );
    qInfo( "groups saved to %s", qPrintable( path ) );
  }
}

void loadGroupsLocked()
{
  const QString path = groupsFilePath();
  if ( path.isEmpty() ) return;
  QFile f( path );
  if ( !f.open( QIODevice::ReadOnly ) ) return;
  QJsonParseError err;
  const QJsonDocument doc = QJsonDocument::fromJson( f.readAll(), &err );
  if ( err.error != QJsonParseError::NoError ) {
    qWarning( "groups.json parse error" );
    return;
  }
  const QJsonObject root = doc.object();
  g_state->activeGroupId = static_cast< unsigned >( root.value( "activeGroupId" ).toInt( 0 ) );
  g_state->nextGroupId   = static_cast< unsigned >( root.value( "nextGroupId" ).toInt( 1 ) );
  // Reload (not append): gd_scan_dicts calls this on EVERY scan, and every
  // group mutation writes groups.json immediately, so the file is the source of
  // truth. Appending instead of clearing duplicated every user group on each
  // scan: importing a dictionary re-stages the folder and re-scans, so the user
  // got a second group of the same name after every import — and it could not
  // be deleted, because gd_group_delete erases only the first id match.
  g_state->allOrder.clear();
  g_state->groupDefs.clear();
  bool repaired = false;
  for ( const QJsonValue &v : root.value( "allOrder" ).toArray() )
    g_state->allOrder.push_back( v.toString().toStdString() );
  for ( const QJsonValue &gv : root.value( "groups" ).toArray() ) {
    const QJsonObject o = gv.toObject();
    GroupDef def;
    def.id   = static_cast< unsigned >( o.value( "id" ).toInt( 0 ) );
    def.name = o.value( "name" ).toString();
    // Resolve dict ids -> indices against the currently loaded dictionaries.
    for ( const QJsonValue &idv : o.value( "dictIds" ).toArray() ) {
      const QString want = idv.toString();
      for ( size_t i = 0; i < g_state->dictionaries.size(); ++i ) {
        if ( QString::fromStdString( g_state->dictionaries[ i ]->getId() ) == want ) {
          def.dictIndices.push_back( static_cast< unsigned >( i ) );
          break;
        }
      }
    }
    if ( def.id == 0 ) continue; // "All" is implicit
    // Self-heal: a groups.json written while the append bug was live holds the
    // same id more than once. Keep one group per id and union its membership, so
    // a device that already accumulated duplicates repairs itself on the next
    // scan instead of needing its config file hand-edited.
    auto dup = std::find_if( g_state->groupDefs.begin(), g_state->groupDefs.end(),
                             [ &def ]( const GroupDef & d ) { return d.id == def.id; } );
    if ( dup != g_state->groupDefs.end() ) {
      repaired = true;
      for ( const unsigned idx : def.dictIndices ) {
        if ( std::find( dup->dictIndices.begin(), dup->dictIndices.end(), idx )
             == dup->dictIndices.end() )
          dup->dictIndices.push_back( idx );
      }
      continue;
    }
    g_state->groupDefs.push_back( std::move( def ) );
  }
  qInfo( "groups loaded: %d user groups%s",
         static_cast< int >( g_state->groupDefs.size() ),
         repaired ? " (repaired duplicate ids in groups.json)" : "" );
  // Make a repair durable instead of re-healing the same file on every scan.
  if ( repaired )
    saveGroupsLocked();
}

void gdLogCall( const char * name, const char * word, qint64 mutexMs, qint64 pumpMs, bool finished )
{
  // Only log calls that took (or waited) noticeably long: the diagnostic file
  // logger does synchronous I/O, so logging every fast call would itself add
  // latency to the very engine calls we are trying to measure. A call that
  // never finished is inherently slow (it burned its loop bound), so it logs.
  if ( mutexMs < 20 && pumpMs < 20 && finished )
    return;
  qInfo( "%s word=%s mutex=%lldms pump=%lldms finished=%d",
         name, word, mutexMs, pumpMs, finished ? 1 : 0 );
}

} // namespace

extern "C" {

int gd_init( const char * config_dir, const char * index_dir )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( g_state )
    return 0;

  // The engine treats index_dir as a prefix: every backend does
  // `indicesDir + dictId` (index_path.hpp). So index_dir must end in a
  // separator, and an unusable one must be rejected rather than normalized into
  // a root-relative path that would scatter indexes at the filesystem root.
  if ( !index_dir )
    return -2;
  const std::string indexDirRaw( index_dir );
  if ( indexDirRaw.empty() || indexDirRaw.find_first_not_of( "/\\" ) == std::string::npos )
    return -2;

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
  // Normalized: callers may omit the trailing separator (the app did), and the
  // engine's prefix contract means that silently sends indexes to a sibling
  // path. The boundary owns the contract, so it is enforced here once.
  g_state->indexDir = QString::fromStdString( gdNormalizeIndexDir( indexDirRaw ) );
  g_state->groupsConfigDir = QString::fromUtf8( config_dir );
  // "modern" display style enables the dark mode stylesheet variant
  // (article_maker only emits article-style-darkmode.css for displayStyle
  // "modern"); darkreader.js is emitted for any style when dark mode is on.
  g_state->cfg.preferences.displayStyle = QStringLiteral( "modern" );
  // DSL `[*]...[/opt]` zones stay collapsed behind the engine's expander
  // (dsl-optional-parts-toggle). Upstream defaults this to true, and
  // makeHtmlHeader then injects `.dsl_opt{display:inline}` +
  // `.hidden_expand_opt{display:none}`, which shows the optional text and hides
  // the expander icon — the control the article emits is present in the markup
  // but dead on screen. Keep it false so article-style.css's
  // `.dsl_opt{display:none}` wins and the 16px expander stays visible;
  // assets/scripts/gd-article-controls.js supplies the toggle handler.
  g_state->cfg.preferences.alwaysExpandOptionalParts = false;
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
  QElapsedTimer wall; wall.start();
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
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

  // Reload any dictionary whose source files changed since it was loaded. A
  // re-import replaces a source file in place and the id (an MD5 of the paths)
  // does not change, so without this the dedup below would discard the freshly
  // built object and keep the stale one — while the backend had already rewritten
  // the index underneath it (needToRebuildIndex saw the new file), leaving that
  // dictionary's searches failing with "Error reading from the file" until the
  // app restarted. Dropping the changed entry here lets the scan rebuild it
  // cleanly and makes the updated content take effect.
  {
    vector< sptr< Dictionary::Class > > kept;
    kept.reserve( g_state->dictionaries.size() );
    for ( auto & d : g_state->dictionaries ) {
      if ( dictionarySourceChanged( *d ) ) {
        qInfo( "gd_scan_dicts: source changed, reloading %s", d->getId().c_str() );
        g_state->sourceStamps.erase( d->getId() );
        continue;
      }
      kept.push_back( std::move( d ) );
    }
    g_state->dictionaries.swap( kept );
  }

  const size_t before = g_state->dictionaries.size();

  // Dedup: a dictionary id is an MD5 over its (sorted) source file paths, and
  // the UI re-stages + re-scans the same folder on every add, so skip anything
  // whose id is already loaded rather than appending a duplicate. The block
  // above has already dropped any loaded entry whose files changed, so a
  // re-import still reloads here.
  QSet< QString > loadedIds;
  loadedIds.reserve( static_cast< int >( g_state->dictionaries.size() ) );
  for ( const auto & d : g_state->dictionaries )
    loadedIds.insert( QString::fromStdString( d->getId() ) );

  // Load the dictionary backends ONE PRIMARY FILE at a time, each wrapped in
  // its own try/catch. A corrupt or truncated source (a killed stage-copy, a
  // truncated .mdx/.dsl.dz, a bad .ifo) must never crash the process NOR hide
  // the good dictionaries sitting next to it. Upstream batches a whole format
  // into one makeDictionaries call and aborts the batch on the first throw;
  // here one bad file is isolated, recorded, and the scan continues. This is
  // the ONLY boundary deviation from upstream (never editing engine sources).
  auto loadPrimary = [ & ]( const string & primary, auto factory ) {
    vector< sptr< Dictionary::Class > > made;
    try {
      made = factory();
    }
    catch ( const std::exception & e ) {
      qWarning( "GD: dictionary load failed for %s: %s", primary.c_str(), e.what() );
      g_state->lastScanFailures.append( QString::fromLocal8Bit( primary.c_str() ) );
      return;
    }
    catch ( ... ) {
      qWarning( "GD: dictionary load failed for %s (unknown error)", primary.c_str() );
      g_state->lastScanFailures.append( QString::fromLocal8Bit( primary.c_str() ) );
      return;
    }
    // An unopenable/truncated primary does NOT throw in every backend — some
    // (mdx) just fail to open and return nothing. Treat a primary that produced
    // zero dictionaries as broken too, so the user is told it is missing. The
    // only legitimately-empty primaries are abbreviation files ("*_abrv"), which
    // the backends skip on purpose; never flag those.
    const bool isAbbreviation =
      QString::fromLocal8Bit( primary.c_str() ).toLower().contains( QLatin1String( "_abrv" ) );
    if ( made.empty() && !isAbbreviation ) {
      qWarning( "GD: dictionary failed to load (unreadable or no entries): %s", primary.c_str() );
      g_state->lastScanFailures.append( QString::fromLocal8Bit( primary.c_str() ) );
      return;
    }
    for ( auto & d : made ) {
      const QString id = QString::fromStdString( d->getId() );
      if ( loadedIds.contains( id ) )
        continue;
      loadedIds.insert( id );
      d->setFTSParameters( g_state->cfg.preferences.fts );
      // Remember the source file state so a later scan detects an in-place
      // replacement (same id, new content) and reloads instead of deduping.
      g_state->sourceStamps[ d->getId() ] = stampSourceFiles( *d );
      g_state->dictionaries.push_back( std::move( d ) );
    }
  };

  for ( const auto & f : files ) {
    const QString fn = QString::fromUtf8( f.c_str() );
    if ( fn.endsWith( QLatin1String( ".mdx" ), Qt::CaseInsensitive ) ) {
      loadPrimary( f, [ & ] {
        return Mdx::makeDictionaries( vector< string >{ f }, idxPath, sink );
      } );
    }
    else if ( fn.endsWith( QLatin1String( ".dsl.dz" ), Qt::CaseInsensitive )
              || fn.endsWith( QLatin1String( ".dsl" ), Qt::CaseInsensitive ) ) {
      loadPrimary( f, [ & ] {
        return Dsl::makeDictionaries( vector< string >{ f }, idxPath, sink, 500000 );
      } );
    }
    else if ( fn.endsWith( QLatin1String( ".ifo" ), Qt::CaseInsensitive ) ) {
      loadPrimary( f, [ & ] {
        return Stardict::makeDictionaries( vector< string >{ f }, idxPath, sink, 500000 );
      } );
    }
  }

  // Load persisted user groups now that dictionaries are known (membership is
  // resolved from stored dict ids), then rebuild the materialized group set.
  loadGroupsLocked();
  rebuildGroups();

  g_state->articleMaker =
    std::make_unique< ArticleMaker >( g_state->dictionaries, g_state->groups, g_state->cfg.preferences );

  qInfo( "gd_scan_dicts took %lld ms", wall.elapsed() );

  return static_cast< int >( g_state->dictionaries.size() - before );
}

int gd_scan_failures( char * out, int out_size )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;
  if ( g_state->lastScanFailures.isEmpty() )
    return 0;
  if ( !out || out_size <= 0 )
    return -1;
  const QStringList list = g_state->lastScanFailures;
  g_state->lastScanFailures.clear(); // consume
  QString joined = list.join( QLatin1Char( '\n' ) );
  if ( joined.size() + 1 > out_size )
    return -2;
  std::memcpy( out, joined.toLocal8Bit().constData(), joined.size() + 1 );
  return list.size();
}

int gd_suggest( const char * word, char * out, int out_size )
{
  QElapsedTimer wall; wall.start();
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state || !out || out_size <= 0 )
    return -1;

  const qint64 mutexMs = wall.restart();

  // Suggest only within the active group (0 = "All"), matching gd_lookup's
  // scoping so the Search tab's selected group scopes suggestions too. groups[0]
  // is always "All"; group i (>=1) corresponds to groupDefs[i-1].
  const vector< sptr< Dictionary::Class > > * dicts = &g_state->dictionaries;
  const unsigned active = g_state->activeGroupId;
  if ( active != 0 ) {
    for ( size_t i = 0; i < g_state->groupDefs.size(); ++i ) {
      if ( g_state->groupDefs[ i ].id == active ) {
        dicts = &g_state->groups[ i + 1 ].dictionaries;
        break;
      }
    }
  }

  // Empty group (e.g. a freshly-created group with no dictionaries): nothing to
  // suggest. Without this, WordFinder::prefixMatch on an empty dictionary list
  // never emits finished and gd_suggest blocks the engine for the full 10s
  // loop timeout — serialized behind g_engineMutex, that starves every queued
  // phrase (typed autocomplete appears frozen).
  if ( dicts->empty() ) {
    qInfo( "gd_suggest: empty active group -> no suggestions" );
    return 0;
  }

  WordFinder wf( nullptr );
  QAtomicInt finishedFlag = 0;
  QEventLoop loop;
  QTimer::singleShot( 10000, &loop, &QEventLoop::quit );

  // Register the loop-quit connection BEFORE prefixMatch(): WordFinder can
  // complete synchronously on a small/fast dictionary (the finished signal
  // fires inside prefixMatch itself). A connection made after that point would
  // miss the emit and loop.exec() would only exit via the 10s timer — the
  // "suggestion dropdown takes ~10s" bug on small dictionaries.
  QObject::connect( &wf, &WordFinder::finished, &loop, &QEventLoop::quit );
  QObject::connect( &wf, &WordFinder::finished, &wf, [ &finishedFlag ]() {
    finishedFlag.storeRelaxed( 1 );
  } );
  wf.prefixMatch( QString::fromUtf8( word ), *dicts, 100 );

  // Drive the async search to completion with a real event loop. If the search
  // already finished synchronously, skip the pump entirely (mirrors
  // gd_lookup's `if (!req->isFinished())` guard); otherwise exec() runs until
  // finished (connection above) or the 10s bound.
  wall.restart();
  if ( !finishedFlag.loadRelaxed() )
    loop.exec();

  gdLogCall( "gd_suggest", word, mutexMs, wall.elapsed(), finishedFlag.loadRelaxed() != 0 );

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
  QElapsedTimer wall; wall.start();
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state || !out || out_size <= 0 )
    return -1;
  const qint64 mutexMs = wall.restart();

  const QString w = QString::fromUtf8( word );
  // Use the active group (0 = "All"); article_maker filters to its dictionaries.
  // A dictionary whose full-text index is currently being built is withheld
  // (design D2) so a lookup never reads a dictionary the build is touching.
  auto req = g_state->articleMaker->makeDefinitionFor(
    w, g_state->activeGroupId, QMap< QString, QString >(), mutedInFlightDict(), QStringList(), false );

  // ArticleRequest delivers via queued signals; pump a real event loop
  // (bounded). Keep req alive until it is truly finished.
  QEventLoop loop;
  QTimer::singleShot( 15000, &loop, &QEventLoop::quit );
  QObject::connect( req.get(), &Dictionary::Request::finished, &loop, &QEventLoop::quit );
  if ( !req->isFinished() )
    loop.exec();

  gdLogCall( "gd_lookup", word, mutexMs, wall.elapsed(), req->isFinished() );

  if ( !req->isFinished() )
    return -3;

  const auto & data = req->getFullData();
  if ( out_size <= static_cast< int >( data.size() ) )
    return -4;

  std::memcpy( out, data.data(), data.size() );
  out[ data.size() ] = '\0';
  return static_cast< int >( data.size() );
}

int gd_lookup_in_group( const char * word, int group_id, char * out, int out_size )
{
  QElapsedTimer wall; wall.start();
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state || !out || out_size <= 0 || group_id < 0 )
    return -1;
  const qint64 mutexMs = wall.restart();

  const QString w = QString::fromUtf8( word );
  // Empty group (no dictionaries): nothing can match — return empty immediately
  // instead of blocking the engine's 15s lookup loop (the app shows a not-found
  // / history fallback). Skip for "All" (group 0), which always has dicts.
  if ( group_id != 0 ) {
    GroupDef * def = findGroupDef( static_cast< unsigned >( group_id ) );
    if ( !def || def->dictIndices.empty() ) {
      if ( out_size > 0 ) out[ 0 ] = '\0';
      return 0;
    }
  }
  // Scope to an explicit group (0 = "All"), independent of the active group —
  // used so a result from a scoped context (e.g. FTS tab) opens in the same
  // group it was found in.
  auto req = g_state->articleMaker->makeDefinitionFor(
    w, static_cast< unsigned >( group_id ), QMap< QString, QString >(), mutedInFlightDict(), QStringList(), false );

  QEventLoop loop;
  QTimer::singleShot( 15000, &loop, &QEventLoop::quit );
  QObject::connect( req.get(), &Dictionary::Request::finished, &loop, &QEventLoop::quit );
  if ( !req->isFinished() )
    loop.exec();

  gdLogCall( "gd_lookup_in_group", word, mutexMs, wall.elapsed(), req->isFinished() );

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

  // Issue the request under the engine lock: getResource() mutates the
  // dictionary and reads the loaded-dictionary list. The lock is deliberately
  // scoped to this block only. Holding it across the wait below would serve no
  // purpose (waiting mutates nothing) and would block every other gd_* caller —
  // FTS builds, lookups, suggestions — behind an unrelated slow resource.
  // See design.md D2 in fix-article-server-gui-reentrancy.
  sptr< Dictionary::DataRequest > req;
  {
    std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
    if ( !g_state )
      return -1;

    Dictionary::Class * found = nullptr;
    for ( const auto & d : g_state->dictionaries ) {
      if ( d->getId() == id ) {
        found = d.get();
        break;
      }
    }
    if ( !found )
      return -2;

    try {
      req = found->getResource( Utils::Url::path( url ).mid( 1 ).toUtf8().data() );
    }
    catch ( std::exception & e ) {
      qWarning( "getResource request error (%s) in \"%s\"", e.what(), found->getName().c_str() );
      return -2;
    }
    if ( !req.get() )
      return -2;
  }

  // Engine lock released. `req` is a refcounted sptr, so the request object
  // stays alive for the whole wait regardless of what the engine does, and
  // nothing below touches g_state.
  QEventLoop loop;
  QTimer::singleShot( kEngineRequestDeadlineMs, &loop, &QEventLoop::quit );
  QObject::connect( req.get(), &Dictionary::Request::finished, &loop, &QEventLoop::quit );
  if ( !req->isFinished() )
    loop.exec();

  // Copy the bytes out under the lock. A finished request owns stable data, so
  // this only needs to exclude a concurrent engine caller for the memcpy.
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
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
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  return g_state ? static_cast< int >( g_state->dictionaries.size() ) : 0;
}

int gd_dict_info( int index, char * name, int name_size, char * file, int file_size )
{
  if ( !g_state || !name || name_size <= 0 || !file || file_size <= 0 )
    return -1;
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );

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

int gd_dict_id( int index, char * out, int out_size )
{
  if ( !g_state || !out || out_size <= 0 )
    return -1;
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( index < 0 || index >= static_cast< int >( g_state->dictionaries.size() ) )
    return -1;
  const string id = g_state->dictionaries[ index ]->getId();
  if ( static_cast< int >( id.size() ) + 1 > out_size )
    return -1;
  std::memcpy( out, id.c_str(), id.size() + 1 );
  return 0;
}

int gd_dict_meta( int index, char * lang_from, int lang_from_size,
                  char * lang_to, int lang_to_size, long long * size_bytes )
{
  if ( !g_state || !size_bytes || !lang_from || lang_from_size <= 0
       || !lang_to || lang_to_size <= 0 )
    return -1;
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( index < 0 || index >= static_cast< int >( g_state->dictionaries.size() ) )
    return -1;

  Dictionary::Class & d = *g_state->dictionaries[ index ];

  const QString from = LangCoder::decode( d.getLangFrom() );
  const QString to   = LangCoder::decode( d.getLangTo() );
  const QByteArray fb = from.toUtf8(), tb = to.toUtf8();
  if ( fb.size() + 1 > lang_from_size || tb.size() + 1 > lang_to_size )
    return -1;
  std::memcpy( lang_from, fb.constData(), fb.size() + 1 );
  std::memcpy( lang_to, tb.constData(), tb.size() + 1 );

  // Approximate on-disk size: sum the dictionary's source files (primary +
  // resource files) as reported by the backend. These are the staged copies the
  // engine reads, so this is a fair "approx MB/GB".
  long long total = 0;
  const auto & files = d.getDictionaryFilenames();
  for ( const auto & f : files ) {
    QFileInfo fi( QString::fromUtf8( f.c_str() ) );
    if ( fi.exists() && fi.isFile() )
      total += fi.size();
  }
  *size_bytes = total;
  return 0;
}

// Identity for duplicate resolution (design.md D2 in
// openspec/changes/resolve-duplicate-dictionaries): display name, primary source
// file, and the complete source-file set as (basename, size, mtimeMs).
//
// Two deliberate choices, both about making the CALLER's comparison correct:
//
//   - The directory is stripped to basename. Identity is name + content, so the
//     same dictionary in two staged roots must compare equal. Including the path
//     would make every duplicate undetectable, which is the bug this exists for.
//   - The file records are emitted raw rather than digested. The caller compares
//     them with the same mtime tolerance the importer uses when it skips unchanged
//     files, and a digest cannot express a tolerance. The set is small by
//     construction (resource trees are not in getDictionaryFilenames()), so a
//     component-wise comparison costs nothing.
//
// -1 for a missing file's size/mtime matches stampSourceFiles(), so the two
// signals agree on what "absent" looks like.
int gd_dict_identity( int index, char * out, int out_size )
{
  if ( !g_state || !out || out_size <= 0 )
    return -1;
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );

  if ( index < 0 || index >= static_cast< int >( g_state->dictionaries.size() ) )
    return -2;

  Dictionary::Class & d = *g_state->dictionaries[ index ];
  const auto & files = d.getDictionaryFilenames();

  QString rec = QStringLiteral( "D\t" ) + QString::fromStdString( d.getName() ) + QLatin1Char( '\t' )
                + ( files.empty() ? QString() : QString::fromStdString( files.front() ) );

  for ( const auto & f : files ) {
    const QFileInfo fi( QString::fromStdString( f ) );
    const bool exists = fi.exists();
    rec += QLatin1Char( '\n' ) + QStringLiteral( "F\t" ) + fi.fileName() + QLatin1Char( '\t' )
           + QString::number( exists ? fi.size() : -1 ) + QLatin1Char( '\t' )
           + QString::number( exists ? fi.lastModified().toMSecsSinceEpoch() : -1 );
  }

  const QByteArray bytes = rec.toUtf8();
  if ( bytes.size() + 1 > out_size )
    return -1;
  std::memcpy( out, bytes.constData(), bytes.size() + 1 );
  return 0;
}

int gd_move_dict( int from, int to )
{
  if ( !g_state )
    return -1;
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );

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

int gd_remove_dict( int dict_index )
{
  if ( !g_state )
    return -1;
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );

  const int n = static_cast< int >( g_state->dictionaries.size() );
  if ( dict_index < 0 || dict_index >= n )
    return -1;

  const unsigned removed = static_cast< unsigned >( dict_index );

  // Erase from the loaded set; the last sptr ref is released here (or by the
  // caller holding a temporary), and ArticleMaker is rebuilt so its by-value
  // group/dict vectors match the new list.
  g_state->dictionaries.erase( g_state->dictionaries.begin() + dict_index );

  // Drop the dictionary from every group and remap the surviving indices that
  // pointed past it (they shifted down by one).
  for ( auto & def : g_state->groupDefs ) {
    auto & v = def.dictIndices;
    v.erase( std::remove( v.begin(), v.end(), removed ), v.end() );
    for ( auto & idx : v ) {
      if ( idx > removed )
        --idx;
    }
  }

  rebuildGroups();
  // Membership changed, so persist it now: without this groups.json keeps the
  // removed id (and its allOrder entry) until the next scan or group mutation
  // rewrites the file, leaving the stored group set briefly inconsistent with
  // what the app shows (fix-dictionary-removal-cleanup, design D5).
  saveGroupsLocked();
  return 0;
}

// --- groups API (milestone multi-group-management) ---

int gd_group_count()
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state )
    return 0;
  // 1 (the implicit "All") + user groups.
  return 1 + static_cast< int >( g_state->groupDefs.size() );
}

int gd_group_info( int index, int * id_out, char * name, int name_size, int * dict_count_out )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
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
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state || !id_out || !name || !*name )
    return -1;
  const QString n = QString::fromUtf8( name );
  // Unique group names: reject an exact (case-insensitive) duplicate so no two
  // groups can share a name. -2 = "name already exists" (distinct from -1).
  for ( const GroupDef & d : g_state->groupDefs ) {
    if ( d.name.compare( n, Qt::CaseInsensitive ) == 0 )
      return -2;
  }
  GroupDef def;
  def.id   = g_state->nextGroupId++;
  def.name = n;
  g_state->groupDefs.push_back( std::move( def ) );
  *id_out = static_cast< int >( g_state->groupDefs.back().id );
  rebuildGroups();
  saveGroupsLocked();
  return 0;
}

int gd_group_rename( int id, const char * name )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state || !name || !*name )
    return -1;
  if ( id == 0 )
    return -1; // "All" cannot be renamed
  GroupDef * def = findGroupDef( static_cast< unsigned >( id ) );
  if ( !def )
    return -1;
  const QString n = QString::fromUtf8( name );
  for ( const GroupDef & d : g_state->groupDefs ) {
    if ( d.id != static_cast< unsigned >( id )
         && d.name.compare( n, Qt::CaseInsensitive ) == 0 )
      return -2; // another group already has this name
  }
  def->name = n;
  rebuildGroups();
  saveGroupsLocked();
  return 0;
}

int gd_group_delete( int id )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
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
  saveGroupsLocked();
  return 0;
}

int gd_group_add_dict( int id, int dict_index )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
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
    saveGroupsLocked();
  }
  return 0;
}

int gd_group_remove_dict( int id, int dict_index )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
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
    saveGroupsLocked();
  }
  return 0;
}

int gd_group_move_dict( int id, int from, int to )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;
  if ( id == 0 ) {
    // "All" is reorderable (it drives article order) but not addable/removable.
    // g_state->allOrder was normalized to the shown order by the last
    // rebuildGroups(), so from/to index into it directly.
    auto & v = g_state->allOrder;
    const int n = static_cast< int >( v.size() );
    if ( from < 0 || to < 0 || from >= n || to >= n )
      return -1;
    std::string item = v[ from ];
    v.erase( v.begin() + from );
    v.insert( v.begin() + to, item );
    rebuildGroups();
    saveGroupsLocked();
    return 0;
  }
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
  saveGroupsLocked();
  return 0;
}

int gd_group_active( int * id_out )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state || !id_out )
    return -1;
  *id_out = static_cast< int >( g_state->activeGroupId );
  return 0;
}

int gd_group_set_active( int id )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state )
    return -1;
  if ( id != 0 && !findGroupDef( static_cast< unsigned >( id ) ) )
    return -1;
  g_state->activeGroupId = static_cast< unsigned >( id );
  saveGroupsLocked();
  return 0;
}

int gd_group_dicts( int id, int * out, int out_capacity )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state || !out || out_capacity <= 0 )
    return -1;

  if ( id == 0 ) {
    // Global indices in the user's All order (rebuildGroups keeps allOrder in
    // sync with the loaded dictionaries).
    const int n = static_cast< int >( g_state->allOrder.size() );
    if ( n > out_capacity )
      return -1;
    for ( int k = 0; k < n; ++k ) {
      int idx = -1;
      for ( size_t i = 0; i < g_state->dictionaries.size(); ++i ) {
        if ( g_state->dictionaries[ i ]->getId() == g_state->allOrder[ k ] ) {
          idx = static_cast< int >( i );
          break;
        }
      }
      out[ k ] = idx;
    }
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
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );

  g_state->cfg.preferences.darkReaderMode =
    on ? Config::Dark::On : Config::Dark::Off;

  // ArticleMaker reads the preference via GlobalBroadcaster for the header.
  GlobalBroadcaster::instance()->setConfig( &g_state->cfg );
  return 0;
}

// --- full-text search (xapian, re-enabled for v1) ---

int gd_fts_index( int dict_index )
{
  QElapsedTimer wall; wall.start();
  std::unique_lock< std::recursive_mutex > lock( g_engineMutex );
  if ( !g_state || dict_index < 0 || dict_index >= static_cast< int >( g_state->dictionaries.size() ) )
    return -1;

  // Keep the dictionary alive across the build even if it is concurrently
  // removed from g_state (removal erases the sptr; this copy holds the object,
  // so the build never touches freed memory).
  sptr< Dictionary::Class > dict = g_state->dictionaries[ dict_index ];
  if ( !dict->canFTS() )
    return -1; // not full-text searchable

  // Register the in-flight build: its id lets the lookup path withhold it
  // (design D2) and lets gd_fts_cancel / gd_fts_build_state address it. Guarded
  // by g_ftsProgressMutex (lock order g_engineMutex -> g_ftsProgressMutex) so a
  // poller/canceller never blocks behind the build. One build at a time.
  {
    std::lock_guard< std::mutex > plock( g_ftsProgressMutex );
    if ( g_ftsBuildActive )
      return -1; // another build is already in flight
    g_ftsBuildActive         = true;
    g_ftsBuildId             = dict->getId();
    g_ftsCancel              = 0;
    g_state->ftsProgressDict = dict;
  }

  // Cooperative slicing (design D1): the engine calls this hook every slice so
  // we briefly release g_engineMutex and let queued operations (lookups,
  // searches, scans, removal) interleave with the build. The build reacquires
  // before touching the engine again. The hook runs on this thread, so
  // unlocking a recursive_mutex the unique_lock owns is safe.
  FtsHelpers::setYieldCallback( [ &lock ]() {
    lock.unlock();
    QThread::msleep( 1 ); // let a waiter acquire before we reacquire
    lock.lock();
  } );

  int rc = 0;
  try {
    dict->makeFTSIndex( g_ftsCancel );
  }
  catch ( std::exception & ) {
    rc = -1;
  }
  FtsHelpers::setYieldCallback( nullptr );

  const bool cancelled = ( g_ftsCancel.loadAcquire() != 0 );

  {
    std::lock_guard< std::mutex > plock( g_ftsProgressMutex );
    g_ftsBuildActive = false;
    g_ftsBuildId.clear();
    g_state->ftsProgressDict.reset();
  }

  if ( cancelled )
    rc = -2; // distinct "cancelled" result (design D4)
  qInfo( "gd_fts_index dict=%d rc=%d took %lld ms", dict_index, rc, wall.elapsed() );
  return rc;
}

int gd_fts_cancel( const char * dict_id )
{
  if ( !dict_id || !*dict_id )
    return -1;
  std::lock_guard< std::mutex > plock( g_ftsProgressMutex );
  if ( !g_ftsBuildActive )
    return 0; // nothing in flight
  if ( g_ftsBuildId != dict_id )
    return 1; // a different dictionary is being built
  g_ftsCancel = 1;
  return 0;
}

int gd_fts_build_state( const char * dict_id, int * out )
{
  if ( !dict_id || !*dict_id || !out )
    return -1;
  std::lock_guard< std::mutex > plock( g_ftsProgressMutex );
  *out = ( g_ftsBuildActive && g_ftsBuildId == dict_id ) ? 1 : 0; // 1 building, 0 idle
  return 0;
}

int gd_fts_progress( int * out_percent )
{
  if ( !out_percent )
    return -1;
  *out_percent = 0;
  sptr< Dictionary::Class > dict;
  {
    std::lock_guard< std::mutex > plock( g_ftsProgressMutex );
    if ( g_state )
      dict = g_state->ftsProgressDict;
  }
  if ( !dict )
    return 0; // no build in flight
  int pct = dict->getIndexingFtsProgress();
  *out_percent = pct < 0 ? 0 : ( pct > 100 ? 100 : pct );
  return 1;
}

int gd_fts_index_state( int dict_index, int * out )
{
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
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
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
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
  // Wait (bounded) for an in-flight full-text build to finish before freeing
  // g_state: the build is interleaved and between slices still touches
  // g_state's progress slot, so deleting state underneath it would
  // use-after-free. As it winds down, ask it to stop at its next slice. The app
  // does not call gd_cleanup in v1; this is a boundary invariant.
  for ( ;; ) {
    {
      std::lock_guard< std::mutex > plock( g_ftsProgressMutex );
      if ( !g_ftsBuildActive )
        break;
      g_ftsCancel = 1;
    }
    QThread::msleep( 10 );
  }
  std::lock_guard< std::recursive_mutex > lock( g_engineMutex );
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