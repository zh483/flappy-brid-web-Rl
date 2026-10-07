set(PYBIND11_FINDPYTHON ON)
find_package(Python 3.9 COMPONENTS Interpreter Development.Module REQUIRED)

# Prefer project-local sources, then an installed package, then download.
set(FLAPPY_PYBIND11_SOURCE "${PROJECT_SOURCE_DIR}/third_party/pybind11")
if(EXISTS "${FLAPPY_PYBIND11_SOURCE}/CMakeLists.txt")
    add_subdirectory("${FLAPPY_PYBIND11_SOURCE}"
                     "${CMAKE_CURRENT_BINARY_DIR}/pybind11")
else()
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -m pybind11 --cmakedir
        RESULT_VARIABLE FLAPPY_PYBIND11_RESULT
        OUTPUT_VARIABLE FLAPPY_PYBIND11_CMAKE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    if(FLAPPY_PYBIND11_RESULT EQUAL 0)
        find_package(pybind11 3.0 CONFIG QUIET
                     HINTS "${FLAPPY_PYBIND11_CMAKE_DIR}")
    else()
        find_package(pybind11 3.0 CONFIG QUIET)
    endif()

    if(NOT pybind11_FOUND)
        include(FetchContent)
        message(STATUS "Downloading pybind11 3.0.4 to ${FLAPPY_PYBIND11_SOURCE}")
        FetchContent_Declare(pybind11
            URL https://github.com/pybind/pybind11/archive/refs/tags/v3.0.4.tar.gz
            SOURCE_DIR "${FLAPPY_PYBIND11_SOURCE}"
            DOWNLOAD_EXTRACT_TIMESTAMP TRUE
        )
        FetchContent_MakeAvailable(pybind11)
    endif()
endif()

pybind11_add_module(flappy_engine python_bindings.cpp)
target_link_libraries(flappy_engine PRIVATE flappy::core)
if(MSVC)
    target_compile_options(flappy_engine PRIVATE /utf-8)
endif()

# PROJECT_BINARY_DIR is the engine build directory, even when used by the server.
set_target_properties(flappy_engine PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}/python/$<0:>"
    RUNTIME_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}/python/$<0:>"
)
install(TARGETS flappy_engine LIBRARY DESTINATION . RUNTIME DESTINATION .)

if(BUILD_TESTING)
    add_test(NAME python_bindings
        COMMAND "${Python_EXECUTABLE}"
                "${PROJECT_SOURCE_DIR}/tests/test_python_bindings.py"
                "$<TARGET_FILE_DIR:flappy_engine>"
    )
endif()
