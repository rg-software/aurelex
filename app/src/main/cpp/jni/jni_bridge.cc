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

extern "C" {

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
  jobjectArray out = env->NewObjectArray( n, strCls, nullptr );

  // Each entry: [0]=name, [1]=source file.
  for ( jint i = 0; i < n; ++i ) {
    char name[ 1024 ]  = { 0 };
    char file[ 4096 ]  = { 0 };
    if ( gd_dict_info( i, name, sizeof( name ), file, sizeof( file ) ) == 0 ) {
      jobjectArray pair = env->NewObjectArray( 2, strCls, nullptr );
      env->SetObjectArrayElement( pair, 0, env->NewStringUTF( name ) );
      env->SetObjectArrayElement( pair, 1, env->NewStringUTF( file ) );
      env->SetObjectArrayElement( out, i, pair );
      env->DeleteLocalRef( pair );
    }
  }
  env->DeleteLocalRef( strCls );
  return out;
}

JNIEXPORT jint JNICALL
Java_aurelex_android_NativeEngine_nativeMoveDict( JNIEnv * env, jobject /*thiz*/, jint from, jint to )
{
  (void)env;
  return gd_move_dict( from, to );
}

} // extern "C"