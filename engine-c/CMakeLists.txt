cmake_minimum_required(VERSION 3.24)
project(FlappyBirdEngine VERSION 0.1.0 LANGUAGES CXX)

option(FLAPPY_BUILD_PYTHON "Build the Python training module" ON)

# The future C++ server can link this target without depending on Python.
add_library(flappy_core STATIC
    config.cpp
    engines/cengine.cpp
    objective/birds.cpp
    objective/pipe.cpp
)
add_library(flappy::core ALIAS flappy_core)
target_include_directories(flappy_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_features(flappy_core PUBLIC cxx_std_17)
set_target_properties(flappy_core PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    CXX_EXTENSIONS OFF
)

if(MSVC)
    target_compile_options(flappy_core PRIVATE /W4 /utf-8)
else()
    target_compile_options(flappy_core PRIVATE
        -Wall -Wextra -Wpedantic -Wno-ignored-qualifiers
    )
endif()

include(CTest)

if(FLAPPY_BUILD_PYTHON)
    set(PYBIND11_FINDPYTHON ON)
    find_package(Python 3.9 COMPONENTS Interpreter Development.Module REQUIRED)

    # Prefer the dependency bundled inside this project, then an installed package.
    set(FLAPPY_PYBIND11_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/third_party/pybind11")
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

    pybind11_add_module(flappy_engine bindings/python_bindings.cpp)
    target_link_libraries(flappy_engine PRIVATE flappy::core)
    if(MSVC)
        target_compile_options(flappy_engine PRIVATE /utf-8)
    endif()

    # A fixed output folder also works with Visual Studio's Release/Debug builds.
    set_target_properties(flappy_engine PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/python/$<0:>"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/python/$<0:>"
    )
    install(TARGETS flappy_engine LIBRARY DESTINATION . RUNTIME DESTINATION .)

    if(BUILD_TESTING)
        add_test(NAME python_bindings
            COMMAND "${Python_EXECUTABLE}"
                    "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_python_bindings.py"
                    "$<TARGET_FILE_DIR:flappy_engine>"
        )
    endif()
endif()
