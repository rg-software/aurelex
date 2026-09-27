// Internal carve header (NOT part of the gd_* C boundary in goldendict.h).
//
// The engine's index directory is a *prefix*, not a directory: every backend
// computes `string indexFile = indicesDir + dictId;` with no separator of its
// own (engine/src/dict/dsl.cc:1752 and 17 siblings), which is why upstream's
// Config::getIndexDir() returns `result.path() + QDir::separator()`
// (engine/src/config.cc:2212). gd_init normalizes the caller's index_dir with
// this helper so a caller that omits the separator cannot send indexes to the
// sibling path.
//
// It lives in its own header so the smoke tool can apply the exact same
// normalization when it asserts on where the indexes landed
// (fix-index-directory-path-separator, design.md D1/D4).
#pragma once

#include <string>

// Returns `dir` with a trailing '/' appended when it has none. '/' is used
// rather than QDir::separator() because the engine accepts it on every platform
// the carve runs on, and it keeps this header Qt-free so the smoke assertion and
// the unit test can include it without the engine.
//
// An empty string is returned unchanged; gd_init rejects that case separately
// rather than turning it into "/".
inline std::string gdNormalizeIndexDir( std::string dir )
{
  if ( !dir.empty() && dir.back() != '/' && dir.back() != '\\' )
    dir += '/';
  return dir;
}
