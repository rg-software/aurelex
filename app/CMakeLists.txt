cmake_minimum_required(VERSION 3.18)
project(aurelex LANGUAGES C CXX)

# The all-Qt (Qt Quick/WebView) Android app that drives the carve IN-PROCESS
# (no :engine process, no JNI bridge).
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# The Qt android toolchain doesn't define __ANDROID_API__, but bionic's iconv.h/
# libc APIs guard on it (`#if __ANDROID_API__ >= 28`). The shipped app targets
# API 28+; define it here so iconv and friends are declared.
add_compile_definitions(__ANDROID_API__=35)

if(NOT QT_BASE)
    message(FATAL_ERROR "QT_BASE must be set (C:/Qt/6.6.3)")
endif()
if(NOT QT_HOST_PATH)
    message(FATAL_ERROR "QT_HOST_PATH must be set (host desktop kit)")
endif()
if(NOT VCPKG_BASE)
    message(FATAL_ERROR "VCPKG_BASE must be set (C:/vcpkg)")
endif()

if(ANDROID_ABI STREQUAL "arm64-v8a")
    set(QT_ANDROID_ROOT "${QT_BASE}/android_arm64_v8a")
    set(VCPKG_TRIPLET "arm64-android")
elseif(ANDROID_ABI STREQUAL "x86_64")
    set(QT_ANDROID_ROOT "${QT_BASE}/android_x86_64")
    set(VCPKG_TRIPLET "x64-android")
else()
    message(FATAL_ERROR "the app builds for android ABIs only")
endif()

set(Qt6_DIR           "${QT_ANDROID_ROOT}/lib/cmake/Qt6"           CACHE PATH "" FORCE)
set(Qt6Core_DIR       "${QT_ANDROID_ROOT}/lib/cmake/Qt6Core"       CACHE PATH "" FORCE)
set(Qt6Gui_DIR        "${QT_ANDROID_ROOT}/lib/cmake/Qt6Gui"        CACHE PATH "" FORCE)
set(Qt6Xml_DIR        "${QT_ANDROID_ROOT}/lib/cmake/Qt6Xml"        CACHE PATH "" FORCE)
set(Qt6Concurrent_DIR "${QT_ANDROID_ROOT}/lib/cmake/Qt6Concurrent" CACHE PATH "" FORCE)
set(Qt6Qml_DIR        "${QT_ANDROID_ROOT}/lib/cmake/Qt6Qml"        CACHE PATH "" FORCE)
set(Qt6Quick_DIR      "${QT_ANDROID_ROOT}/lib/cmake/Qt6Quick"      CACHE PATH "" FORCE)
set(Qt6WebView_DIR    "${QT_ANDROID_ROOT}/lib/cmake/Qt6WebView"    CACHE PATH "" FORCE)
set(Qt6Network_DIR    "${QT_ANDROID_ROOT}/lib/cmake/Qt6Network"    CACHE PATH "" FORCE)
set(Qt6QuickControls2_DIR "${QT_ANDROID_ROOT}/lib/cmake/Qt6QuickControls2" CACHE PATH "" FORCE)
set(Qt6QuickControls2Impl_DIR "${QT_ANDROID_ROOT}/lib/cmake/Qt6QuickControls2Impl" CACHE PATH "" FORCE)
set(Qt6QuickControls2Material_DIR "${QT_ANDROID_ROOT}/lib/cmake/Qt6QuickControls2Material" CACHE PATH "" FORCE)
set(Qt6QuickControls2MaterialStyleImpl_DIR "${QT_ANDROID_ROOT}/lib/cmake/Qt6QuickControls2MaterialStyleImpl" CACHE PATH "" FORCE)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Xml Concurrent Qml Quick QuickControls2 WebView Network)

set(VCPKG_ANDROID_ROOT "${VCPKG_BASE}/installed/${VCPKG_TRIPLET}")
link_directories("${VCPKG_ANDROID_ROOT}/lib")

# Reuse the carve object library (real Qt engine). Its CMake requires the same
# -D QT_BASE/QT_HOST_PATH/VCPKG_BASE and the android ABI it already handles.
set(CARVE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../carve")
add_subdirectory("${CARVE_DIR}" carve)

set(ENGINE_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../engine")

qt_add_executable(aurelex
    main.cpp
    EngineController.cpp
    RemoteCatalog.cpp
    ArticleServer.cpp
    $<TARGET_OBJECTS:aurelex_carve>
)

# Bundled resources. Declared with qt_add_resources rather than .qrc files +
# AUTORCC: AUTORCC does not emit the payload files listed *inside* a .qrc as
# dependencies of the generated qrc_*.cpp, so regenerating a bundled font (e.g.
# the icon subset) left the stale glyphs in the APK. qt_add_resources tracks
# every FILES entry, so changing a .ttf or .qm re-runs rcc.
qt_add_resources(aurelex "fonts"
    PREFIX "/fonts"
    BASE "${CMAKE_CURRENT_SOURCE_DIR}/res/fonts"
    FILES
        "${CMAKE_CURRENT_SOURCE_DIR}/res/fonts/MaterialIcons-Regular.ttf"
        "${CMAKE_CURRENT_SOURCE_DIR}/res/fonts/MaterialSymbols-Outlined-subset.ttf"
)
qt_add_resources(aurelex "i18n"
    PREFIX "/i18n"
    BASE "${CMAKE_CURRENT_SOURCE_DIR}/i18n"
    FILES
        "${CMAKE_CURRENT_SOURCE_DIR}/i18n/aurelex_ru.qm"
        "${CMAKE_CURRENT_SOURCE_DIR}/i18n/aurelex_ja.qm"
)
target_include_directories(aurelex PRIVATE
    "${CARVE_DIR}"
    "${ENGINE_SRC}/src"
    "${ENGINE_SRC}/src/common"
    "${ENGINE_SRC}/src/dict"
    "${ENGINE_SRC}/src/dict/utils"
    "${ENGINE_SRC}/src/audio"
    "${VCPKG_ANDROID_ROOT}/include"
)
# In-process engine deps: the carve's own private deps must be re-listed for the
# final link (they are not propagated from an OBJECT library).
target_link_libraries(aurelex PRIVATE
    Qt6::Core Qt6::Gui Qt6::Xml Qt6::Concurrent
    Qt6::Qml Qt6::Quick Qt6::QuickControls2 Qt6::WebView Qt6::Network
    xapian z bz2 lzma lzo2 fmt
)

qt_add_qml_module(aurelex
    URI Aurelex
    VERSION 1.0
    QML_FILES
        main.qml
        )

set(PROGRAM_FILES_ROOT "/data/data/org.aurelex.pocket.dictionary/files")

# The carve needs bionic's iconv.h for android (design D6: no vcpkg libiconv on
# android; bionic provides iconv at API 28+). The Qt android toolchain doesn't
# add the NDK sysroot include automatically; add it for the carve build here.
set(_ndk_inc "${ANDROID_NDK_ROOT}/toolchains/llvm/prebuilt/windows-x86_64/sysroot/usr/include")
if(NOT EXISTS "${_ndk_inc}/iconv.h")
    set(_ndk_inc "${ANDROID_NDK_ROOT}/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include")
endif()
if(EXISTS "${_ndk_inc}/iconv.h")
    target_include_directories(aurelex_carve PRIVATE "${_ndk_inc}")
endif()

set_target_properties(aurelex PROPERTIES
    QT_ANDROID_PACKAGE_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/android"
)

# Android OpenSSL. Qt's TLS on Android is the OpenSSL backend, which dlopen()s
# libcrypto_3.so / libssl_3.so at run time -- and the Qt android kit does NOT
# ship them. Without these the app has NO working TLS: every
# QNetworkAccessManager HTTPS request fails with "TLS initialization failed".
# The WebView is unaffected (Chromium bundles its own TLS), which is why this
# only surfaced when the remote catalog introduced the first Qt-network HTTPS
# call. The prebuilt OpenSSL 3 libs are vendored in app/openssl/<abi> (see
# app/openssl/README.md for provenance and licence); QT_ANDROID_EXTRA_LIBS makes
# androiddeployqt copy them into the APK's lib/<abi>/.
#
# Gated on ANDROID: ANDROID_ABI is only set by the Android toolchain, and these
# libraries are an Android-runtime concern only. Configuring this file with any
# other toolchain must not trip the fatal check below.
if(ANDROID)
set(_aurelex_openssl_dir "${CMAKE_CURRENT_SOURCE_DIR}/openssl/${ANDROID_ABI}")
set(_aurelex_openssl_libs libcrypto_3.so libssl_3.so)
set(_aurelex_openssl_missing "")
foreach(_lib IN LISTS _aurelex_openssl_libs)
    if(NOT EXISTS "${_aurelex_openssl_dir}/${_lib}")
        list(APPEND _aurelex_openssl_missing "${_aurelex_openssl_dir}/${_lib}")
    endif()
endforeach()
if(_aurelex_openssl_missing)
    string(REPLACE ";" "\n  " _aurelex_openssl_missing_pretty "${_aurelex_openssl_missing}")
    # Fatal in every configuration, not a warning: these files are tracked in the
    # repository (see app/openssl/README.md), so their absence means a broken or
    # pruned checkout rather than a build that legitimately has nothing to link.
    # A build that continued here would produce an artifact whose Qt TLS cannot
    # initialize -- an app that looks fine until it makes its first HTTPS request
    # (the remote dictionary catalog), which is exactly the defect a release once
    # shipped. The WebView keeps working because Chromium has its own TLS, so
    # nothing else in the app reveals the problem.
    message(FATAL_ERROR
        "vendored Android OpenSSL missing for ABI ${ANDROID_ABI}; Qt's TLS "
        "backend dlopen()s these at run time and there is no fallback:\n"
        "  ${_aurelex_openssl_missing_pretty}\n"
        "They are tracked in git -- restore them with:\n"
        "  git checkout -- app/openssl\n"
        "See app/openssl/README.md for provenance.")
else()
    set_property(TARGET aurelex APPEND PROPERTY QT_ANDROID_EXTRA_LIBS
        "${_aurelex_openssl_dir}/libcrypto_3.so"
        "${_aurelex_openssl_dir}/libssl_3.so"
    )
endif()
endif() # ANDROID
# NOTE: qt_add_apk_target is absent from the installed Qt 6.6.3 carve subset
# (no Qt6AndroidDeployQt cmake package). The APK is packaged manually with
# androiddeployqt (see README notes).