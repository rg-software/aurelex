// Aurelex C API - the boundary contract between the Android app and the
// carved goldendict-ng engine (design D2).
//
// Kotlin talks to native through exactly these functions (via JNI). Semantics:
//
// - gd_init:      one-time init. config_dir is where engine user data goes
//                 (HOME override), index_dir is where dictionary indexes are
//                 cached. Returns 1 on success, 0 if already initialized.
// - gd_scan_dicts: scan `folder` for supported dictionaries (.mdx/.mdd,
//                 .dsl/.dsl.dz, .ifo), build indexes into index_dir, append to
//                 the loaded set. Returns the number of dictionaries loaded in
//                 this call, or -1 on error.
// - gd_suggest:   prefix-match suggestions for `word`. Fills out (NUL-terminated
//                 string) up to out_size with newline-separated headwords.
//                 Returns the number of results, -1 on invalid args, -2 if the
//                 buffer is too small.
// - gd_lookup:    article HTML for `word` (upstream article_maker output,
//                 including the qrc:/// resource header). Returns byte count
//                 (written to out, NUL-terminated), -1 invalid args, -3 engine
//                 timeout, -4 buffer too small.
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
// - gd_set_dark_mode: toggle article dark mode (task 7.1). on=1 → the engine
//                 emits article-style-darkmode.css + darkreader for subsequent
//                 lookups; on=0 → light. Returns 0 on success, -1 if the
//                 engine is not initialized.
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
int gd_suggest( const char * word, char * out, int out_size );
int gd_lookup( const char * word, char * out, int out_size );
int gd_get_resource( const char * url, char * out, int out_size );
int gd_get_audio( const char * url, char * out, int out_size );
int gd_dict_count();
int gd_dict_info( int index, char * name, int name_size, char * file, int file_size );
int gd_move_dict( int from, int to );
int gd_set_dark_mode( int on );
void gd_cleanup();

#ifdef __cplusplus
}
#endif