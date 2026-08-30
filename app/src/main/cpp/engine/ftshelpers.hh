// Aurelex boundary — shadow header for upstream `ftshelpers.hh`.
//
// This is intentionally included in place of the upstream one (the boundary
// include dir precedes engine/src in the carve build). FTS/xapian is cut for
// v1 (design D6), so the FTS-specific surface upstream exposes to dict
// backends is replaced with a no-op implementation. Everything the backends
// reference (FtsHelpers::ftsIndexIsOldOrBad / makeFTSIndex /
// FTSResultsRequest with the exact ctor signature they call) is preserved;
// everything FTS-only (fulltextsearch.hh, ui_fulltextsearch.h) is omitted.
#pragma once

#include "dict/dictionary.hh"
#include "btreeidx.hh"
#include <QAtomicInt>
#include <QString>
#include <QtConcurrentRun>

namespace FtsHelpers {

// No FTS index in v1: never claim an existing one is stale.
bool ftsIndexIsOldOrBad( BtreeIndexing::BtreeDictionary * dict );

// No FTS index to build in v1.
void makeFTSIndex( BtreeIndexing::BtreeDictionary * dict, QAtomicInt & isCancelled );

class FTSResultsRequest: public Dictionary::DataRequest
{
public:
  FTSResultsRequest( BtreeIndexing::BtreeDictionary &,
                     const QString &,
                     int,
                     bool,
                     bool )
  {
    // FTS is unavailable: satisfy the request immediately with no data.
    finish();
  }

  void cancel() override {}
};

} // namespace FtsHelpers