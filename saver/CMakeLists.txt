cmake_minimum_required(VERSION 3.24)
project(FlappyBirdServer LANGUAGES CXX)

include(cmake/Dependencies.cmake)

# Rebuild the engine using the same compiler as the server.
set(FLAPPY_BUILD_PYTHON OFF CACHE BOOL "Build Python bindings in the server project")
add_subdirectory(../engine-c engine)

# Write your server entry point in main.cpp, then rerun CMake to add this target.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/main.cpp")
    add_executable(flappy_server main.cpp)
    target_compile_features(flappy_server PRIVATE cxx_std_17)
    target_link_libraries(flappy_server PRIVATE Crow::Crow flappy::core)
    if(MSVC)
        target_compile_options(flappy_server PRIVATE /utf-8 /bigobj)
    endif()

    include(CTest)
    if(BUILD_TESTING)
        find_package(Python3 3.9 COMPONENTS Interpreter QUIET)
        if(Python3_Interpreter_FOUND)
            add_test(NAME server_websocket
                COMMAND "${Python3_EXECUTABLE}"
                    "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_server.py"
                    "$<TARGET_FILE:flappy_server>")
            set_tests_properties(server_websocket PROPERTIES TIMEOUT 45)
        endif()
    endif()
else()
    message(STATUS "Write saver/main.cpp to create the flappy_server executable")
endif()
