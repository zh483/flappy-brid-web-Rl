# Reusable dependency setup: include this file, then link Crow::Crow.
include_guard(GLOBAL)
include(FetchContent)

set(FLAPPY_SERVER_DEPENDENCY_DIR "${CMAKE_CURRENT_LIST_DIR}/../third_party"
    CACHE PATH "Directory containing the Crow and Asio sources")
file(READ "${CMAKE_CURRENT_LIST_DIR}/../third_party/dependencies.json"
     FLAPPY_SERVER_DEPENDENCY_MANIFEST)

# Download only missing sources, using the recorded version and archive checksum.
foreach(dependency IN ITEMS asio crow)
    if(dependency STREQUAL "asio")
        set(required_header "include/asio.hpp")
    else()
        set(required_header "include/crow.h")
    endif()
    if(NOT EXISTS "${FLAPPY_SERVER_DEPENDENCY_DIR}/${dependency}/${required_header}")
        string(JSON archive_url GET "${FLAPPY_SERVER_DEPENDENCY_MANIFEST}"
               "${dependency}" archive_url)
        string(JSON archive_hash GET "${FLAPPY_SERVER_DEPENDENCY_MANIFEST}"
               "${dependency}" sha256)
        FetchContent_Declare(flappy_server_${dependency}
            URL "${archive_url}"
            URL_HASH "SHA256=${archive_hash}"
            SOURCE_DIR "${FLAPPY_SERVER_DEPENDENCY_DIR}/${dependency}"
            SOURCE_SUBDIR _download_only
            DOWNLOAD_EXTRACT_TIMESTAMP TRUE
        )
        FetchContent_MakeAvailable(flappy_server_${dependency})
    endif()
endforeach()

set(ASIO_INCLUDE_DIR "${FLAPPY_SERVER_DEPENDENCY_DIR}/asio/include"
    CACHE PATH "Standalone Asio headers")
set(CROW_BUILD_EXAMPLES OFF CACHE BOOL "Build Crow examples")
set(CROW_BUILD_TESTS OFF CACHE BOOL "Build Crow tests")
set(CROW_INSTALL OFF CACHE BOOL "Install Crow")
set(CROW_ENABLE_SSL OFF CACHE BOOL "Enable Crow TLS")
set(CROW_ENABLE_COMPRESSION OFF CACHE BOOL "Enable Crow compression")

if(NOT TARGET Crow::Crow)
    add_subdirectory("${FLAPPY_SERVER_DEPENDENCY_DIR}/crow"
                     "${CMAKE_CURRENT_BINARY_DIR}/crow")
    if(WIN32)
        target_link_libraries(Crow INTERFACE ws2_32 mswsock)
    endif()
endif()
