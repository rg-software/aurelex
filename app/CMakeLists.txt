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
    ArticleServer.cpp
    fonts.qrc
    $<TARGET_OBJECTS:aurelex_carve>
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

set(PROGRAM_FILES_ROOT "/data/data/aurelex.android/files")

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
# NOTE: qt_add_apk_target is absent from the installed Qt 6.6.3 carve subset
# (no Qt6AndroidDeployQt cmake package). The APK is packaged manually with
# androiddeployqt (see README notes).