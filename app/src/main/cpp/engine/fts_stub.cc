// Aurelex boundary — FTS (xapian) stub, used with the shadow ftshelpers.hh.
// FTS is cut for v1 (design D6): index health is always "fine" and building
// an index is a no-op. Search requests finish immediately via the header.
#include "ftshelpers.hh"
#include "btreeidx.hh"

namespace FtsHelpers {

bool ftsIndexIsOldOrBad( BtreeIndexing::BtreeDictionary * /*dict*/ )
{
  return false;
}

void makeFTSIndex( BtreeIndexing::BtreeDictionary * /*dict*/, QAtomicInt & /*isCancelled*/ )
{
}

} // namespace FtsHelpers