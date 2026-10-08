cmake_minimum_required(VERSION 3.24)
project(FlappyBirdServer LANGUAGES CXX)

include(cmake/Dependencies.cmake)

# Rebuild the engine using the same compiler as the server.
set(FLAPPY_BUILD_PYTHON OFF CACHE BOOL "Build Python bindings in the server project")
add_subdirectory(../engine-c engine)
include(cmake/OnnxRuntime.cmake)
add_library(flappy_bot STATIC bot_policy.cpp)
target_compile_features(flappy_bot PUBLIC cxx_std_17)
target_include_directories(flappy_bot PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(flappy_bot PUBLIC flappy::core flappy_onnxruntime Crow::Crow)
if(MSVC)
    target_compile_options(flappy_bot PRIVATE /utf-8)
endif()

# Write your server entry point in main.cpp, then rerun CMake to add this target.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/main.cpp")
    add_executable(flappy_server main.cpp)
    target_compile_features(flappy_server PRIVATE cxx_std_17)
    target_link_libraries(flappy_server PRIVATE Crow::Crow flappy::core flappy_bot)
    flappy_deploy_bot(flappy_server)
    if(MSVC)
        target_compile_options(flappy_server PRIVATE /utf-8 /bigobj)
    endif()

    include(CTest)
    if(BUILD_TESTING)
        add_executable(test_bot tests/test_bot.cpp)
        target_link_libraries(test_bot PRIVATE flappy_bot)
        if(MSVC)
            target_compile_options(test_bot PRIVATE /utf-8)
        endif()
        flappy_deploy_bot(test_bot)
        add_test(NAME bot_single COMMAND test_bot
            "${CMAKE_CURRENT_SOURCE_DIR}/models/ppo-bird.onnx"
            "${CMAKE_CURRENT_SOURCE_DIR}/models/policy-cases.json" 1)
        set_tests_properties(bot_single PROPERTIES TIMEOUT 60)
        find_package(Python3 3.9 COMPONENTS Interpreter QUIET)
        if(Python3_Interpreter_FOUND)
            add_test(NAME server_websocket
                COMMAND "${Python3_EXECUTABLE}"
                    "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_server.py"
                    "$<TARGET_FILE:flappy_server>")
            set_tests_properties(server_websocket PROPERTIES TIMEOUT 45)
            add_test(NAME server_bots
                COMMAND "${Python3_EXECUTABLE}"
                    "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_bot_server.py"
                    "$<TARGET_FILE:flappy_server>")
            set_tests_properties(server_bots PROPERTIES TIMEOUT 45)
        endif()
    endif()
else()
    message(STATUS "Write saver/main.cpp to create the flappy_server executable")
endif()
