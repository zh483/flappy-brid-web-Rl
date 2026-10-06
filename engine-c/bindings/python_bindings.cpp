#include <array>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "engines/cengine.hpp"

namespace py = pybind11;

PYBIND11_MODULE(flappy_engine, module) {
    module.doc() = "Fixed-step Flappy Bird engine for Python training. "
                   "All calls in one process share one game.";

    py::enum_<game_phase>(module, "GamePhase")
        .value("idle", game_phase::idle)
        .value("running", game_phase::running)
        .value("finished", game_phase::finished);

    py::class_<Vec2>(module, "Vec2")
        .def(py::init([](double x, double y) { return Vec2{x, y}; }),
             py::arg("x") = 0.0, py::arg("y") = 0.0)
        .def_readwrite("x", &Vec2::x)
        .def_readwrite("y", &Vec2::y);

    py::class_<game_set>(module, "GameSet")
        .def(py::init([](int size, int speed, const std::array<int, 8>& characters) {
            return game_set{size, speed, characters};
        }), py::arg("size") = 1, py::arg("speed") = 1,
            py::arg("characters") = std::array<int, 8>{})
        .def_readwrite("size", &game_set::_size)
        .def_readwrite("speed", &game_set::_speed)
        .def_readwrite("characters", &game_set::character);

    py::class_<pipe_state>(module, "PipeState")
        .def_readonly("x", &pipe_state::_x)
        .def_readonly("up", &pipe_state::_up)
        .def_readonly("down", &pipe_state::_down);

    py::class_<bird_state>(module, "BirdState")
        .def_readonly("present", &bird_state::present)
        .def_readonly("character", &bird_state::character)
        .def_readonly("position", &bird_state::position)
        .def_readonly("velocity", &bird_state::velocity)
        .def_readonly("respawn_ms", &bird_state::respawn_ms)
        .def_readonly("invincible_ms", &bird_state::invincible_ms);

    py::class_<game_state>(module, "GameState")
        .def_readonly("phase", &game_state::phase)
        .def_readonly("speed", &game_state::speed)
        .def_readonly("pipes", &game_state::pipes)
        .def_readonly("birds", &game_state::birds);

    // Keep the GIL: the existing static engine and pools are shared mutable state.
    module.def("begin", [](const game_set& settings, unsigned int seed) {
        if (settings._size < 1 || settings._size > config::max_p) {
            throw py::value_error("size must be between 1 and 8");
        }
        engine::begin(settings, seed);
    }, py::arg("settings"), py::arg("seed") = 0,
       "Start a new game. The same seed reproduces the initial pipe layout.");
    module.def("step", &engine::step, py::arg("actions"),
               "Advance one fixed step with exactly 8 player actions.");
    module.def("get_state", &engine::get_state,
               "Return a snapshot independent of subsequent steps and clear().");
    module.def("is_finished", &engine::is_finished);
    module.def("clear", &engine::clear);

    auto constants = module.def_submodule("config", "Engine configuration values.");
    constants.attr("camera_width") = config::camera_width;
    constants.attr("camera_height") = config::camera_height;
    constants.attr("world_width") = config::world_width;
    constants.attr("world_height") = config::world_height;
    constants.attr("max_p") = config::max_p;
    constants.attr("v_fps") = config::v_fps;
    constants.attr("g") = config::g;
    constants.attr("force") = config::force;
    constants.attr("min_v") = config::min_v;
    constants.attr("p_x") = config::p_x;
    constants.attr("p_s") = config::p_s;
    constants.attr("p_df") = config::p_df;
    constants.attr("b_x") = config::b_x;
    constants.attr("b_y") = config::b_y;
    constants.attr("alive_ms") = config::alive_ms;
    constants.attr("invin_ms") = config::invin_ms;
}
