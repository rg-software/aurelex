# Aurelex engine carve — compiles a subset of upstream goldendict-ng
# into libaurelex.so. Upstream sources (engine/) are selected, never modified;
# every deviation lives in the boundary layer (gd_boundary.cc, shims).
#
# Qt:  Core + Xml + Concurrent + Gui + Widgets (prebuilt kit via aqt).
#      QtGui is linked because article_maker uses QTextDocumentFragment/
#      QStyleHints and dict backends pull tiff.cc (QApplication/QScreen).
#      QtWidgets is needed by config.cc/utils.hh headers; linking it is
#      cheaper than stubbing.
# Deps: cross-compiled for android via vcpkg (zlib bzip2 liblzma lzo fmt
#       xapian); xapian for the android triplets is provided by
#       scripts/build-xapian-android.sh (see design.md D2). opencc/hunspell/
#       libiconv cut for v1 (design D6).
cmake_minimum_required(VERSION 3.18)
project(aurelex_engine LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

set(ENGINE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../engine")

# App-private file root for PROGRAM_DATA_DIR.
set(PROGRAM_FILES_ROOT "/data/data/aurelex.android/files")

# Qt kit + vcpkg base, passed from Gradle (machine-local paths come from
# local.properties, see app/build.gradle.kts).
if(NOT QT_BASE)
    message(FATAL_ERROR "QT_BASE must be set (gradle arg)")
endif()
if(NOT QT_HOST_PATH)
    message(FATAL_ERROR "QT_HOST_PATH must be set (gradle arg)")
endif()
if(NOT VCPKG_BASE)
    message(FATAL_ERROR "VCPKG_BASE must be set (gradle arg)")
endif()

# Map the ABI Gradle hands us to the matching Qt kit and vcpkg triplet.
# A host build (smoke test, no ANDROID_ABI) uses QT_BASE directly.
if(ANDROID_ABI STREQUAL "arm64-v8a")
    set(QT_ANDROID_ROOT "${QT_BASE}/android_arm64_v8a")
    set(VCPKG_TRIPLET "arm64-android")
elseif(ANDROID_ABI STREQUAL "x86_64")
    set(QT_ANDROID_ROOT "${QT_BASE}/android_x86_64")
    set(VCPKG_TRIPLET "x64-android")
elseif(NOT DEFINED ANDROID_ABI OR ANDROID_ABI STREQUAL "")
    set(QT_ANDROID_ROOT "${QT_BASE}")
    set(VCPKG_TRIPLET "x64-windows")
else()
    message(FATAL_ERROR "Unsupported ABI: ${ANDROID_ABI}")
endif()

# The android NDK toolchain resets CMAKE_PREFIX_PATH, so point each Qt
# package config directly. QT_HOST_PATH gives cross-compiles the host tools
# (moc, rcc) from a desktop kit of the same Qt version.
set(Qt6_DIR          "${QT_ANDROID_ROOT}/lib/cmake/Qt6"          CACHE PATH "" FORCE)
set(Qt6Core_DIR      "${QT_ANDROID_ROOT}/lib/cmake/Qt6Core"      CACHE PATH "" FORCE)
set(Qt6Gui_DIR       "${QT_ANDROID_ROOT}/lib/cmake/Qt6Gui"       CACHE PATH "" FORCE)
set(Qt6Xml_DIR       "${QT_ANDROID_ROOT}/lib/cmake/Qt6Xml"       CACHE PATH "" FORCE)
set(Qt6Concurrent_DIR "${QT_ANDROID_ROOT}/lib/cmake/Qt6Concurrent" CACHE PATH "" FORCE)
set(Qt6Widgets_DIR   "${QT_ANDROID_ROOT}/lib/cmake/Qt6Widgets"   CACHE PATH "" FORCE)
set(VCPKG_ANDROID_ROOT "${VCPKG_BASE}/installed/${VCPKG_TRIPLET}")
link_directories("${VCPKG_ANDROID_ROOT}/lib")

find_package(Qt6 REQUIRED COMPONENTS Core Xml Concurrent Gui Widgets)

set(AURELEX_CARVE_SOURCES
    # --- carved upstream sources (StarDict-first minimal set) ---
    ${ENGINE_DIR}/src/article_maker.cc
    ${ENGINE_DIR}/src/wordfinder.cc
    ${ENGINE_DIR}/src/config.cc
    ${ENGINE_DIR}/src/langcoder.cc
    ${ENGINE_DIR}/src/language.cc
    ${ENGINE_DIR}/src/dictionary_group.cc
    ${ENGINE_DIR}/src/instances.cc
    ${ENGINE_DIR}/src/pronounceengine.cc
    ${ENGINE_DIR}/src/tiff.cc

    ${ENGINE_DIR}/src/common/folding.cc
    ${ENGINE_DIR}/src/common/globalbroadcaster.cc
    ${ENGINE_DIR}/src/common/globalregex.cc
    ${ENGINE_DIR}/src/common/htmlescape.cc
    ${ENGINE_DIR}/src/common/iconv.cc
    ${ENGINE_DIR}/src/ftshelpers.cc
    ${ENGINE_DIR}/src/common/text.cc
    ${ENGINE_DIR}/src/common/utils.cc
    ${ENGINE_DIR}/src/common/wildcard.cc
    ${ENGINE_DIR}/src/common/filetype.cc
    ${ENGINE_DIR}/src/common/dictionary_icon_name.cc

    ${ENGINE_DIR}/src/dict/utils/decompress.cc
    ${ENGINE_DIR}/src/dict/utils/dictfile.cc
    ${ENGINE_DIR}/src/dict/utils/indexedzip.cc
    ${ENGINE_DIR}/src/dict/utils/ripemd.cc
    ${ENGINE_DIR}/src/dict/utils/splitfile.cc
    ${ENGINE_DIR}/src/dict/utils/ufile.cc
    ${ENGINE_DIR}/src/dict/utils/zipfile.cc
    ${ENGINE_DIR}/src/dict/utils/dictzip.c

    ${ENGINE_DIR}/src/audiolink.cc
    ${ENGINE_DIR}/src/dict/dictionary.cc
    ${ENGINE_DIR}/src/dict/btreeidx.cc
    ${ENGINE_DIR}/src/dict/chunkedstorage.cc
    ${ENGINE_DIR}/src/dict/stardict.cc
    ${ENGINE_DIR}/src/dict/xdxf2html.cc
    ${ENGINE_DIR}/src/dict/xdxf.cc

    ${ENGINE_DIR}/src/dict/mdx.cc
    ${ENGINE_DIR}/src/dict/mdictparser.cc
    ${ENGINE_DIR}/src/dict/dsl.cc
    ${ENGINE_DIR}/src/dict/dsl_details.cc

    # --- boundary layer (ours, not upstream) ---
    gd_boundary.cc
)

set(AURELEX_CARVE_INCLUDES
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${ENGINE_DIR}/src
    ${ENGINE_DIR}/src/common
    ${ENGINE_DIR}/src/dict
    ${ENGINE_DIR}/src/dict/utils
    ${ENGINE_DIR}/src/audio
    ${VCPKG_ANDROID_ROOT}/include
)

set(AURELEX_CARVE_LIBS
    Qt6::Core
    Qt6::Xml
    Qt6::Concurrent
    Qt6::Gui
    Qt6::Widgets
    xapian
    z
    bz2
    lzma
    lzo2
    fmt
)

# Host (Windows) builds need GNU libiconv for <iconv.h>; Android gets iconv
# from bionic at API 28+ (design D6) via the platform.
if(NOT ANDROID_ABI OR ANDROID_ABI STREQUAL "")
    list(APPEND AURELEX_CARVE_LIBS iconv)
endif()

# NOTE: deliberately NOT defining MAKE_CHINESE_CONVERSION_SUPPORT — that
# would pull opencc (cut in v1, design D6). Chinese transliteration is a
# desktop nicety; the 3 core formats don't need it for article body work.

# config.cc references PROGRAM_DATA_DIR (upstream defines it in the packaging
# files). Point it at Android app-private storage; used for locale/styles.
add_compile_definitions(PROGRAM_DATA_DIR="${PROGRAM_FILES_ROOT}")

# The carve compiles once (object library) and is reused by both the Android
# shared library and the host smoke-tool (design: boundary stays single-source).
add_library(aurelex_carve OBJECT ${AURELEX_CARVE_SOURCES})
set_target_properties(aurelex_carve PROPERTIES
    POSITION_INDEPENDENT_CODE ON
)
target_include_directories(aurelex_carve PRIVATE ${AURELEX_CARVE_INCLUDES})
target_link_libraries(aurelex_carve PRIVATE ${AURELEX_CARVE_LIBS})
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(aurelex_carve PRIVATE -Wall -Wextra)
endif()

add_library(aurelex SHARED
    $<TARGET_OBJECTS:aurelex_carve>
    ${CMAKE_CURRENT_SOURCE_DIR}/../jni/jni_bridge.cc
)
set_target_properties(aurelex PROPERTIES OUTPUT_NAME aurelex)
target_include_directories(aurelex PRIVATE ${AURELEX_CARVE_INCLUDES})
# The JNI bridge includes QtCore private headers (qjnihelpers_p.h for
# QtAndroidPrivate::initJNI); add the versioned QtCore include root so both
# "private/qjnihelpers_p.h" and "QtCore/private/qglobal_p.h" resolve.
if(QT_ANDROID_ROOT AND Qt6Core_VERSION)
    target_include_directories(aurelex PRIVATE
        "${QT_ANDROID_ROOT}/include/QtCore/${Qt6Core_VERSION}/QtCore"
        "${QT_ANDROID_ROOT}/include/QtCore/${Qt6Core_VERSION}")
endif()
target_link_libraries(aurelex PRIVATE aurelex_carve ${AURELEX_CARVE_LIBS})

# Host smoke tool (task 1.6 spike): only built when requested.
option(AURELEX_BUILD_SMOKE "Build the host gd_* smoke tool" OFF)
if(AURELEX_BUILD_SMOKE)
    add_executable(aurelex_smoke smoke/main.cpp $<TARGET_OBJECTS:aurelex_carve>)
    target_include_directories(aurelex_smoke PRIVATE ${AURELEX_CARVE_INCLUDES})
    target_link_libraries(aurelex_smoke PRIVATE aurelex_carve ${AURELEX_CARVE_LIBS})
    if(MSVC)
        target_link_options(aurelex_smoke PRIVATE /MAP)
    endif()
endif()

# Windows: ntohl/host-order functions come from Winsock; bionic provides them
# on Android.
if(WIN32 AND NOT ANDROID)
    target_link_libraries(aurelex_carve PRIVATE ws2_32)
endif()