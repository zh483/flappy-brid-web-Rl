include_guard(GLOBAL)
include(FetchContent)
set(FLAPPY_ONNXRUNTIME_DIR "${CMAKE_CURRENT_LIST_DIR}/../third_party/onnxruntime"
    CACHE PATH "ONNX Runtime CPU SDK")
if(NOT EXISTS "${FLAPPY_ONNXRUNTIME_DIR}/include/onnxruntime_cxx_api.h")
    if(WIN32 AND CMAKE_SIZEOF_VOID_P EQUAL 8)
        set(ort_archive "onnxruntime-win-x64-1.23.2.zip")
        set(ort_sha256 "0b38df9af21834e41e73d602d90db5cb06dbd1ca618948b8f1d66d607ac9f3cd")
    elseif(CMAKE_SYSTEM_NAME STREQUAL "Linux" AND CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64)$")
        set(ort_archive "onnxruntime-linux-x64-1.23.2.tgz")
        set(ort_sha256 "1fa4dcaef22f6f7d5cd81b28c2800414350c10116f5fdd46a2160082551c5f9b")
    else()
        message(FATAL_ERROR "Set FLAPPY_ONNXRUNTIME_DIR to an ONNX Runtime 1.23.2 CPU SDK for this platform")
    endif()
    FetchContent_Declare(flappy_ort
        URL "https://github.com/microsoft/onnxruntime/releases/download/v1.23.2/${ort_archive}"
        URL_HASH "SHA256=${ort_sha256}"
        SOURCE_DIR "${FLAPPY_ONNXRUNTIME_DIR}"
        SOURCE_SUBDIR _download_only DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
    FetchContent_MakeAvailable(flappy_ort)
endif()
add_library(flappy_onnxruntime SHARED IMPORTED GLOBAL)
set_target_properties(flappy_onnxruntime PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${FLAPPY_ONNXRUNTIME_DIR}/include")
if(WIN32)
    set_target_properties(flappy_onnxruntime PROPERTIES
        IMPORTED_IMPLIB "${FLAPPY_ONNXRUNTIME_DIR}/lib/onnxruntime.lib"
        IMPORTED_LOCATION "${FLAPPY_ONNXRUNTIME_DIR}/lib/onnxruntime.dll")
else()
    set_target_properties(flappy_onnxruntime PROPERTIES
        IMPORTED_LOCATION "${FLAPPY_ONNXRUNTIME_DIR}/lib/libonnxruntime.so.1.23.2")
endif()

function(flappy_deploy_bot target)
    # Both executables share an output directory. One task avoids parallel copy races
    # and refreshes exported models even when no executable needs relinking.
    if(NOT TARGET flappy_bot_assets)
    add_custom_target(flappy_bot_assets
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "$<TARGET_FILE:flappy_onnxruntime>" "$<TARGET_FILE_DIR:${target}>"
        COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:${target}>/models"
        COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:${target}>/licenses/onnxruntime"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${FLAPPY_ONNXRUNTIME_DIR}/LICENSE"
            "${FLAPPY_ONNXRUNTIME_DIR}/ThirdPartyNotices.txt"
            "$<TARGET_FILE_DIR:${target}>/licenses/onnxruntime"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/models/ppo-bird.onnx"
            "${CMAKE_CURRENT_SOURCE_DIR}/models/ppo-bird.json"
            "$<TARGET_FILE_DIR:${target}>/models")
    if(NOT WIN32)
        # The ELF SONAME omits the patch version.
        add_custom_command(TARGET flappy_bot_assets POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "$<TARGET_FILE:flappy_onnxruntime>" "$<TARGET_FILE_DIR:${target}>/libonnxruntime.so.1")
    endif()
    endif()
    add_dependencies(${target} flappy_bot_assets)
    if(NOT WIN32)
        set_target_properties(${target} PROPERTIES BUILD_RPATH "$ORIGIN" INSTALL_RPATH "$ORIGIN")
    endif()
endfunction()
