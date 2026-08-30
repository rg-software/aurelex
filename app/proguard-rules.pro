# Keep native binding calls; the gd_* engine symbols are loaded via System.loadLibrary
-keep class aurelex.android.NativeEngine { *; }