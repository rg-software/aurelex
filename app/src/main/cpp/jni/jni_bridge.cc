// Aurelex JNI bridge (task 3.1) — maps the goldendict.h C API (design D2) to
// Kotlin-callable natives. Thin by design: no logic here beyond marshalling
// buffers; all engine behavior lives behind the gd_* C functions.
//
// The C API fills caller-owned buffers, so we allocate generously, call, then
// marshal into a JNI jstring/jbyteArray. Errors (< 0) map to null/empty so
// Kotlin can distinguish "not found/too big" from valid data.
#include "goldendict.h"

#include <jni.h>
#include <string>
#include <vector>

// QtCore declares QtAndroidPrivate::initJNI in a private header; we call it in
// JNI_OnLoad below so QJniEnvironment::javaVM() is non-null when gd_init
// constructs QCoreApplication on the main thread (QCoreApplicationPrivate::init
// reads the app version via QJniEnvironment). Without it, that init segfaults.
#include "private/qjnihelpers_p.h"

extern "C" {

// libaurelex.so is linked against Qt6Core, which exports its own JNI_OnLoad
// (Qt-Android specific: it looks up org.qtproject.qt.android.QtActivity and
// returns JNI_ERR in a plain Android app that has no QtActivity). ART resolves
// JNI_OnLoad for System.loadLibrary("aurelex") across the library's DT_NEEDED
// chain when the loaded library does not export it — so we MUST define our own
// here to shadow Qt's and return a version ART accepts. We register Qt's JavaVM
// via QtAndroidPrivate::initJNI (needed for QCoreApplication's QJniEnvironment).

JNIEXPORT jint JNICALL JNI_OnLoad( JavaVM * vm, void * reserved )
{
  (void)reserved;
  JNIEnv * env = nullptr;
  if ( vm->GetEnv( reinterpret_cast< void ** >( &env ), JNI_VERSION_1_6 ) == JNI_OK && env ) {
    QtAndroidPrivate::initJNI( vm, env );
  }
  return JNI_VERSION_1_6;
}

JNIEXPORT void JNICALL
Java_aurelex_android_NativeEngine_nativeInit( JNIEnv * env, jobject /*thiz*/, jstring configDir, jstring indexDir )
{
  const char * cfg = env->GetStringUTFChars( configDir, nullptr );
  const char * idx = env->GetStringUTFChars( indexDir, nullptr );
  gd_init( cfg, idx );
  env->ReleaseStringUTFChars( configDir, cfg );
  env->ReleaseStringUTFChars( indexDir, idx );
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeScanDicts( JNIEnv * env, jobject /*thiz*/, jstring folder )
{
  const char * f = env->GetStringUTFChars( folder, nullptr );
  const jint n   = gd_scan_dicts( f );
  env->ReleaseStringUTFChars( folder, f );
  return n;
}

JNIEXPORT jstring JNICALL
Java_aurelex_android_NativeEngine_nativeSuggest( JNIEnv * env, jobject /*thiz*/, jstring word )
{
  const char * w = env->GetStringUTFChars( word, nullptr );
  std::vector< char > buf( 1 << 16, 0 );
  const int n = gd_suggest( w, buf.data(), static_cast< int >( buf.size() ) );
  env->ReleaseStringUTFChars( word, w );
  if ( n <= 0 )
    return env->NewStringUTF( "" );
  return env->NewStringUTF( buf.data() );
}

JNIEXPORT jbyteArray JNICALL
Java_aurelex_android_NativeEngine_nativeLookup( JNIEnv * env, jobject /*thiz*/, jstring word )
{
  const char * w = env->GetStringUTFChars( word, nullptr );
  std::vector< char > buf( 1 << 22, 0 ); // 4 MiB article buffer
  const int n = gd_lookup( w, buf.data(), static_cast< int >( buf.size() ) );
  env->ReleaseStringUTFChars( word, w );
  if ( n <= 0 )
    return nullptr;

  jbyteArray out = env->NewByteArray( n );
  env->SetByteArrayRegion( out, 0, n, reinterpret_cast< const jbyte * >( buf.data() ) );
  return out;
}

JNIEXPORT jbyteArray JNICALL
Java_aurelex_android_NativeEngine_nativeGetResource( JNIEnv * env, jobject /*thiz*/, jstring url )
{
  const char * u = env->GetStringUTFChars( url, nullptr );
  std::vector< char > buf( 1 << 22, 0 );
  const int n = gd_get_resource( u, buf.data(), static_cast< int >( buf.size() ) );
  env->ReleaseStringUTFChars( url, u );
  if ( n <= 0 )
    return nullptr;

  jbyteArray out = env->NewByteArray( n );
  env->SetByteArrayRegion( out, 0, n, reinterpret_cast< const jbyte * >( buf.data() ) );
  return out;
}

JNIEXPORT jbyteArray JNICALL
Java_aurelex_android_NativeEngine_nativeGetAudio( JNIEnv * env, jobject /*thiz*/, jstring url )
{
  const char * u = env->GetStringUTFChars( url, nullptr );
  std::vector< char > buf( 1 << 22, 0 );
  const int n = gd_get_audio( u, buf.data(), static_cast< int >( buf.size() ) );
  env->ReleaseStringUTFChars( url, u );
  if ( n <= 0 )
    return nullptr;

  jbyteArray out = env->NewByteArray( n );
  env->SetByteArrayRegion( out, 0, n, reinterpret_cast< const jbyte * >( buf.data() ) );
  return out;
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeSetDarkMode( JNIEnv * env, jobject /*thiz*/, jboolean on )
{
  (void)env;
  return gd_set_dark_mode( on ? 1 : 0 );
}

JNIEXPORT void JNICALL
Java_aurelex_android_NativeEngine_nativeCleanup( JNIEnv * env, jobject /*thiz*/ )
{
  (void)env;
  gd_cleanup();
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeDictCount( JNIEnv * env, jobject /*thiz*/ )
{
  (void)env;
  return gd_dict_count();
}

JNIEXPORT jobjectArray JNICALL
Java_aurelex_android_NativeEngine_nativeDictInfo( JNIEnv * env, jobject /*thiz*/ )
{
  const jint n = gd_dict_count();
  jclass strCls = env->FindClass( "java/lang/String" );
  if ( !strCls || env->ExceptionCheck() ) {
    env->ExceptionClear();
    return nullptr;
  }
  // Outer array must be an array OF String[] (jobjectArray whose elements are
  // String[] pairs). NewObjectArray needs the element class = String[].class.
  jclass arrStrCls = env->FindClass( "[Ljava/lang/String;" );
  if ( !arrStrCls || env->ExceptionCheck() ) {
    env->ExceptionClear();
    return nullptr;
  }
  jobjectArray out = env->NewObjectArray( n, arrStrCls, nullptr );
  if ( !out || env->ExceptionCheck() ) {
    env->ExceptionClear();
    return nullptr;
  }

  // Each entry: [0]=name, [1]=source file. Guard each element against JNI
  // exceptions (e.g. invalid UTF-8 in a dictionary header) so we never abort
  // the engine process; unparseable entries are left empty.
  for ( jint i = 0; i < n; ++i ) {
    char name[ 1024 ]  = { 0 };
    char file[ 4096 ]  = { 0 };
    if ( gd_dict_info( i, name, sizeof( name ), file, sizeof( file ) ) == 0 ) {
      jobjectArray pair = env->NewObjectArray( 2, strCls, nullptr );
      if ( !pair || env->ExceptionCheck() ) {
        env->ExceptionClear();
        continue;
      }
      jstring jn = env->NewStringUTF( name );
      if ( env->ExceptionCheck() ) {
        env->ExceptionClear();
        jn = nullptr;
      }
      jstring jf = env->NewStringUTF( file );
      if ( env->ExceptionCheck() ) {
        env->ExceptionClear();
        jf = nullptr;
      }
      if ( jn ) env->SetObjectArrayElement( pair, 0, jn );
      if ( jf ) env->SetObjectArrayElement( pair, 1, jf );
      env->SetObjectArrayElement( out, i, pair );
      env->DeleteLocalRef( jn );
      env->DeleteLocalRef( jf );
      env->DeleteLocalRef( pair );
    }
  }
  env->DeleteLocalRef( strCls );
  env->DeleteLocalRef( arrStrCls );
  return out;
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeMoveDict( JNIEnv * env, jobject /*thiz*/, jint from, jint to )
{
  (void)env;
  return gd_move_dict( from, to );
}

// --- groups (multi-group-management) ---

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeGroupCount( JNIEnv * env, jobject /*thiz*/ )
{
  (void)env;
  return gd_group_count();
}

// Returns a String[] per group: [id, name, dictCount]. Outer array is String[][].
JNIEXPORT jobjectArray JNICALL
Java_aurelex_android_NativeEngine_nativeGroupInfo( JNIEnv * env, jobject /*thiz*/ )
{
  const jint n = gd_group_count();
  jclass strCls = env->FindClass( "java/lang/String" );
  if ( !strCls || env->ExceptionCheck() ) { env->ExceptionClear(); return nullptr; }
  jclass arrStrCls = env->FindClass( "[Ljava/lang/String;" );
  if ( !arrStrCls || env->ExceptionCheck() ) { env->ExceptionClear(); return nullptr; }
  jobjectArray out = env->NewObjectArray( n, arrStrCls, nullptr );
  if ( !out || env->ExceptionCheck() ) { env->ExceptionClear(); return nullptr; }

  for ( jint i = 0; i < n; ++i ) {
    char name[ 1024 ] = { 0 };
    jint id = -1, cnt = 0;
    if ( gd_group_info( i, &id, name, sizeof( name ), &cnt ) != 0 )
      continue;
    jobjectArray row = env->NewObjectArray( 3, strCls, nullptr );
    if ( !row || env->ExceptionCheck() ) { env->ExceptionClear(); continue; }
    jstring jid = env->NewStringUTF( std::to_string( id ).c_str() );
    jstring jnm = env->NewStringUTF( name );
    jstring jct = env->NewStringUTF( std::to_string( cnt ).c_str() );
    for ( auto * s : { jid, jnm, jct } ) {
      if ( env->ExceptionCheck() ) { env->ExceptionClear(); s = nullptr; }
      (void)s;
    }
    env->SetObjectArrayElement( row, 0, jid );
    env->SetObjectArrayElement( row, 1, jnm );
    env->SetObjectArrayElement( row, 2, jct );
    env->SetObjectArrayElement( out, i, row );
    env->DeleteLocalRef( jid ); env->DeleteLocalRef( jnm ); env->DeleteLocalRef( jct ); env->DeleteLocalRef( row );
  }
  env->DeleteLocalRef( strCls );
  env->DeleteLocalRef( arrStrCls );
  return out;
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeGroupCreate( JNIEnv * env, jobject /*thiz*/, jstring name )
{
  const char * n = env->GetStringUTFChars( name, nullptr );
  int id = -1;
  const jint rc = gd_group_create( n, &id );
  env->ReleaseStringUTFChars( name, n );
  return rc == 0 ? id : -1;
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeGroupRename( JNIEnv * env, jobject /*thiz*/, jint id, jstring name )
{
  const char * n = env->GetStringUTFChars( name, nullptr );
  const jint rc = gd_group_rename( id, n );
  env->ReleaseStringUTFChars( name, n );
  return rc;
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeGroupDelete( JNIEnv * env, jobject /*thiz*/, jint id )
{
  (void)env;
  return gd_group_delete( id );
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeGroupAddDict( JNIEnv * env, jobject /*thiz*/, jint id, jint dictIndex )
{
  (void)env;
  return gd_group_add_dict( id, dictIndex );
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeGroupRemoveDict( JNIEnv * env, jobject /*thiz*/, jint id, jint dictIndex )
{
  (void)env;
  return gd_group_remove_dict( id, dictIndex );
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeGroupMoveDict( JNIEnv * env, jobject /*thiz*/, jint id, jint from, jint to )
{
  (void)env;
  return gd_group_move_dict( id, from, to );
}

// Returns an int[] of the dict indices in group `id`.
JNIEXPORT jintArray JNICALL
Java_aurelex_android_NativeEngine_nativeGroupDicts( JNIEnv * env, jobject /*thiz*/, jint id )
{
  const jint cap = 1 << 12;
  std::vector< jint > buf( cap );
  const jint n = gd_group_dicts( id, buf.data(), cap );
  if ( n < 0 )
    return nullptr;
  jintArray out = env->NewIntArray( n );
  env->SetIntArrayRegion( out, 0, n, buf.data() );
  return out;
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeGroupActive( JNIEnv * env, jobject /*thiz*/ )
{
  (void)env;
  int id = 0;
  gd_group_active( &id );
  return id;
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeGroupSetActive( JNIEnv * env, jobject /*thiz*/, jint id )
{
  (void)env;
  return gd_group_set_active( id );
}

} // extern "C"