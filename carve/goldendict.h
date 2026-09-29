// Aurelex C API - the boundary contract between the Android app and the
// carved goldendict-ng engine (design D2).
//
// Kotlin talks to native through exactly these functions (via JNI). Semantics:
//
// - gd_init:      one-time init. config_dir is where engine user data goes
//                 (HOME override), index_dir is where dictionary indexes are
//                 cached: indexes are written as `index_dir/<dictionary-id>`, so
//                 the engine treats it as a directory prefix. A missing trailing
//                 separator is tolerated (the boundary appends one); an empty or
//                 separator-only index_dir is rejected. Returns 1 on success, 0
//                 if already initialized, -2 for an unusable index_dir.
// - gd_scan_dicts: scan `folder` for supported dictionaries (.mdx/.mdd,
//                 .dsl/.dsl.dz, .ifo), build indexes into index_dir, append to
//                 the loaded set. Scans recursively (nested subfolders are
//                 included). Returns the number of dictionaries loaded in
//                 this call, or -1 on error.
// - gd_suggest:   prefix-match suggestions for `word`. Fills out (NUL-terminated
//                 string) up to out_size with newline-separated headwords.
//                 Returns the number of results, -1 on invalid args, -2 if the
//                 buffer is too small.
// - gd_lookup:    article HTML for `word` (upstream article_maker output,
//                 including the qrc:/// resource header). Returns byte count
//                 (written to out, NUL-terminated), -1 invalid args, -3 engine
//                 timeout, -4 buffer too small.
// - gd_lookup_in_group: same as gd_lookup but scoped to the dictionaries of the
//                 group `group_id` (0 = "All"), independent of the active group.
//                 Same return contract as gd_lookup.
// - gd_get_resource: fetch a dictionary embedded resource named by a bres://
//                 or gdau:// URL (images, audio from .mdd). Returns byte count,
//                 -1 invalid args, -2 not found, -3 timeout, -4 buffer too small.
// - gd_get_audio:  fetch audio bytes for a gdau:// URL. Same contract as
//                 gd_get_resource; kept separate so the Kotlin player can pass
//                 the bytes straight to MediaPlayer.
// - gd_dict_count: number of loaded dictionaries (0 when not scanned yet).
// - gd_dict_info:  metadata for dictionary `index`: display name and the first
//                 source file. Returns 0 on success, -1 if index is out of
//                 range or buffers are too small. Buffers are NUL-terminated.
// - gd_move_dict:  move a dictionary in the single (unfiltered) group order;
//                 the combined article respects this order. Returns 0 on
//                 success, -1 on invalid indices.
// - gd_remove_dict: remove a loaded dictionary by its index in the global
//                 loaded set. It is dropped from the set and from every group
//                 (including the implicit "All"); lookups, groups, and
//                 full-text search no longer reference it. Returns 0 on
//                 success, -1 on an invalid index / uninitialized engine.
//                 Removal is in-memory only: a later gd_scan_dicts of the same
//                 folder re-adds it.
// - gd_group_count: number of groups (always >= 1; group 0 is the implicit
//                 "All" group). Returns 0 if the engine is not initialized.
// - gd_group_info:  group `index` (0..count-1): its id, name, and dictionary
//                 count. Returns 0 on success, -1 on invalid index/buffer.
// - gd_group_create: create a named group; stores its id in *id_out.
//                 Returns 0 on success, -1 on error / if the engine is not
//                 initialized.
// - gd_group_rename/delete: rename or delete a group by id (0 = "All" cannot
//                 be deleted; deleting clears its name only). Deleting the
//                 active group reverts the active id to 0. Returns 0/-1.
// - gd_group_add_dict / remove_dict / move_dict: edit a group's membership and
//                 order. The dictionary is referenced by its index in the
//                 global loaded set. Returns 0 on success, -1 on error.
//                 For id 0 ("All") only move_dict is valid (membership is fixed
//                 to every dictionary; moving sets the ARTICLE ORDER); add/remove
//                 return -1.
// - gd_group_active: query (store into *id_out) or set the active group id for
//                 lookups. Returns 0/-1.
// - gd_set_dark_mode: toggle article dark mode (task 7.1). on=1 → the engine
//                 emits article-style-darkmode.css + darkreader for subsequent
//                 lookups; on=0 → light. Returns 0 on success, -1 if the
//                 engine is not initialized.
// - gd_fts_index:  build/refresh the full-text (xapian) index for dictionary
//                 `dict_index` if it is missing or stale. Blocking; runs on
//                 the calling thread, but interleaves with other gd_* calls:
//                 the engine lock is released between bounded build slices, so
//                 lookups/searches/scans/removal proceed. The dictionary being
//                 built is withheld from lookup and full-text search until its
//                 index completes. Returns 0 on success, -1 if the dict index
//                 is out of range / the dictionary cannot be indexed / another
//                 build is already in flight, -2 if cancelled (see
//                 gd_fts_cancel).
// - gd_fts_cancel: request cancellation of the full-text build for `dict_id`
//                 (the id gd_dict_id returns). The build stops at its next
//                 slice. Returns 0 if the build was signalled (or nothing was
//                 in flight), 1 if a DIFFERENT dictionary is being built, -1 on
//                 invalid args.
// - gd_fts_build_state: report whether `dict_id` has a full-text build in
//                 flight: *out = 1 building, 0 idle. Returns 0 on success,
//                 -1 on invalid args.
// - gd_fts_index_state: report per-dictionary full-text index availability:
//                 0 = built, 1 = missing/stale. Returns 0 on success, -1 if
//                 the dictionary does not exist or does not support FTS.
// - gd_fts_search: run a full-text search for `query` (interpreted by `mode`,
//                 see FTS::SearchMode: 0 whole-words/xapian syntax, 1 plain
//                 text, 2 wildcards, 3 regexp) across the dictionaries of
//                 group `group_id` (0 = "All"). Fills `out` with matching
//                 headwords, each line "headword<TAB>dict_name" (dict_name is
//                 the same display name gd_dict_info returns), NUL-terminated.
//                 Returns the number of results, -1 invalid args, -2 buffer too
//                 small, -3 none of the group's dictionaries has a full-text
//                 index yet (call gd_fts_index first).
// - gd_cleanup:   tear the engine down. Safe to call when not initialized.
//
// All functions block on the calling thread until the engine request completes
// (bounded internally). Buffers: caller-owned, out_size must include the NUL.
//
// Copyright (C) 2026 Aurelex contributors. GPLv3 or later, matching upstream.
#pragma once

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int gd_init( const char * config_dir, const char * index_dir );
int gd_scan_dicts( const char * folder );
// Report the primary dictionary files that failed to load in the most recent
// gd_scan_dicts call(s). Fills `out` (capacity out_size) with a NUL-terminated,
// newline-separated list of the offending paths and returns the count; the
// recorded list is consumed (cleared) by this call. Returns 0 when everything
// loaded, 1+ with the number of broken files, -1 uninitialized/invalid args,
// -2 buffer too small.
int gd_scan_failures( char * out, int out_size );
int gd_suggest( const char * word, char * out, int out_size );
int gd_lookup( const char * word, char * out, int out_size );
int gd_lookup_in_group( const char * word, int group_id, char * out, int out_size );
int gd_get_resource( const char * url, char * out, int out_size );
int gd_get_audio( const char * url, char * out, int out_size );
int gd_dict_count();
int gd_dict_info( int index, char * name, int name_size, char * file, int file_size );
// Return the engine dictionary id (MD5 hex) for `index`. The engine uses this
// id as the prefix for the dictionary's index cache files (files/index<id>,
// files/index<id>_FTS_x), which the app deletes when the dictionary is removed
// permanently. Fills `out` (capacity out_size) with a NUL-terminated id.
// Returns 0 on success, -1 on invalid args / out-of-range / buffer too small.
int gd_dict_id( int index, char * out, int out_size );
// Return display metadata for dictionary `index`: the source and target
// language names (human-readable, empty when unknown) and an approximate on-disk
// size in bytes. Fills lang_from/lang_to (NUL-terminated, capacity
// lang_from_size/lang_to_size) and *size_bytes. Returns 0 on success, -1 on
// invalid args / out-of-range / buffer too small.
int gd_dict_meta( int index, char * lang_from, int lang_from_size,
                  char * lang_to, int lang_to_size, long long * size_bytes );
int gd_move_dict( int from, int to );
int gd_remove_dict( int dict_index );
int gd_group_count();
int gd_group_info( int index, int * id_out, char * name, int name_size, int * dict_count_out );
int gd_group_create( const char * name, int * id_out );
int gd_group_rename( int id, const char * name );
int gd_group_delete( int id );
int gd_group_add_dict( int id, int dict_index );
int gd_group_remove_dict( int id, int dict_index );
int gd_group_move_dict( int id, int from, int to );
// Fill `out` (capacity out_capacity) with the dict indices of group `id`
// (0 = "All" returns every loaded index). Returns the number written, or -1 on
// error / buffer too small.
int gd_group_dicts( int id, int * out, int out_capacity );
int gd_group_active( int * id_out );
int gd_group_set_active( int id );
int gd_set_dark_mode( int on );
int gd_fts_index( int dict_index );
int gd_fts_cancel( const char * dict_id );
int gd_fts_build_state( const char * dict_id, int * out );
// Report live full-text index progress of the dictionary currently being built
// by gd_fts_index (safe to call from another thread while the build runs).
// Fills *out_percent with 0..100. Returns 1 if a build is in flight, 0 if idle
// (out_percent=0), -1 on invalid args.
int gd_fts_progress( int * out_percent );
int gd_fts_index_state( int dict_index, int * out );
int gd_fts_search( const char * query, int mode, int group_id, char * out, int out_size );
void gd_cleanup();

#ifdef __cplusplus
}
#endif