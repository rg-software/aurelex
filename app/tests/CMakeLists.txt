# Host-side test for app/ArticleServer.cpp (fix-article-server-gui-reentrancy).
#
# Deliberately NOT part of app/CMakeLists.txt: that project is Android-only and
# pulls in the whole carved engine. ArticleServer's only engine dependency is
# gd_get_resource / gd_get_audio, which ArticleServerTest.cpp stubs, so this test
# builds against a plain desktop Qt (Core + Network) and writes no engine code.
#
# Build (host):
#   cmake -S app/tests -B build-article-server-test \
#         -DCMAKE_PREFIX_PATH=C:/Qt/6.6.3/msvc2019_64 -G "Visual Studio 17 2022" -A x64
#   cmake --build build-article-server-test --config Release
#   build-article-server-test/Release/article_server_test.exe
cmake_minimum_required(VERSION 3.18)
project(aurelex_article_server_test LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

if(ANDROID)
    message(FATAL_ERROR "article_server_test is a host-only test")
endif()

find_package(Qt6 REQUIRED COMPONENTS Core Network)

add_executable(article_server_test
    ArticleServerTest.cpp
    "${CMAKE_CURRENT_SOURCE_DIR}/../ArticleServer.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/../ArticleServer.hpp"
)

target_include_directories(article_server_test PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/.."
    "${CMAKE_CURRENT_SOURCE_DIR}/../../carve"
)

target_link_libraries(article_server_test PRIVATE Qt6::Core Qt6::Network)

# Index-directory separator + migration tests (fix-index-directory-path-separator).
# Links only Qt Core; the two headers under test are header-only.
add_executable(index_migration_test IndexMigrationTest.cpp)
target_include_directories(index_migration_test PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/.."
    "${CMAKE_CURRENT_SOURCE_DIR}/../../carve"
)
target_link_libraries(index_migration_test PRIVATE Qt6::Core)

# Dictionary-removal index cleanup tests (fix-dictionary-removal-cleanup).
# Links only Qt Core; IndexCleanup.hpp is header-only.
add_executable(index_cleanup_test IndexCleanupTest.cpp)
target_include_directories(index_cleanup_test PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/.."
    "${CMAKE_CURRENT_SOURCE_DIR}/../../carve"
)
target_link_libraries(index_cleanup_test PRIVATE Qt6::Core)

# Display-order -> engine-index mapping tests
# (fix-dictionary-removal-index-mismatch). Links only Qt Core;
# DictionaryIndex.hpp is header-only.
add_executable(dictionary_index_test DictionaryIndexTest.cpp)
target_include_directories(dictionary_index_test PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/.."
    "${CMAKE_CURRENT_SOURCE_DIR}/../../carve"
)
target_link_libraries(dictionary_index_test PRIVATE Qt6::Core)

# Staged-import deletion guard tests (stale-import-cleanup). Links only Qt Core;
# StagedCleanup.hpp is header-only. These are the guards that stand between an
# untrusted path from the scan-failure report and a filesystem deletion.
add_executable(staged_cleanup_test StagedCleanupTest.cpp)
target_include_directories(staged_cleanup_test PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/.."
)
target_link_libraries(staged_cleanup_test PRIVATE Qt6::Core)

# Staging resource-directory classification (stardict-resource-staging). Links
# only Qt Core; StagingRules.hpp is header-only. The Java staging walk is not
# host-runnable, so this pins the rule it mirrors (the .files tree, and "res"
# only beside a StarDict .ifo).
add_executable(staging_rules_test StagingRulesTest.cpp)
target_include_directories(staging_rules_test PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/.."
)
target_link_libraries(staging_rules_test PRIVATE Qt6::Core)

# Dictionary identity + duplicate comparison (resolve-duplicate-dictionaries).
# Links only Qt Core; DictIdentity.hpp is header-only. This decides whether two
# copies of one dictionary are the same dictionary, and it is deliberately
# location-independent - the whole point of it.
add_executable(dict_identity_test DictIdentityTest.cpp)
target_include_directories(dict_identity_test PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/.."
)
target_link_libraries(dict_identity_test PRIVATE Qt6::Core)

# Remote-catalog manifest parser tests (remote-dictionary-catalog). Links only
# Qt Core: RemoteCatalog is the parser + installed-detection + preflight
# constants, with no network and no engine, so the checked-in fixtures under
# fixtures/ are the contract.
add_executable(catalog_test CatalogTest.cpp "${CMAKE_CURRENT_SOURCE_DIR}/../RemoteCatalog.cpp")
target_include_directories(catalog_test PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/..")
target_compile_definitions(catalog_test PRIVATE
    "REMOTE_CATALOG_FIXTURE_DIR=\"${CMAKE_CURRENT_SOURCE_DIR}/fixtures\""
)
target_link_libraries(catalog_test PRIVATE Qt6::Core)
