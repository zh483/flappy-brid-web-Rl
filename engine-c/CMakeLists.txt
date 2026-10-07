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
    add_subdirectory(bindings)
endif()
