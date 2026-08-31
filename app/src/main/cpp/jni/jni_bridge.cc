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

} // extern "C"