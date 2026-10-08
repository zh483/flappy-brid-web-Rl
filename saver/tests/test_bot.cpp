#include "bot_policy.hpp"
#include "crow/json.h"
#include <cmath>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

int main(int argc, char** argv) {
    try {
        require(argc == 4, "Usage: test_bot model.onnx policy-cases.json count");
        BotPolicy policy(argv[1]);
        std::ifstream file(argv[2]);
        const std::string text((std::istreambuf_iterator<char>(file)), {});
        const auto fixtures = crow::json::load(text);
        require(static_cast<bool>(fixtures), "Missing parity cases");
        int verified = 0;
        for (const auto& test : fixtures["cases"]) {
            std::array<float, 8> input{};
            for (int i = 0; i < 8; ++i) input[i] = static_cast<float>(test["observation"][i].d());
            const auto actual = policy.logits(input);
            for (int i = 0; i < 2; ++i)
                require(std::abs(actual[i] - test["logits"][i].d()) < 0.0001, "C++ / SB3 logits differ");
            require((actual[1] > actual[0]) == (test["action"].i() == 1), "C++ / SB3 action differs");
            ++verified;
        }
        require(verified >= 100, "Too few parity cases");
        game_state sample;
        sample.birds[7].present = true;
        sample.birds[7].position = {600, 100};
        sample.birds[7].velocity = {5, -2.5};
        sample.pipes = {{500, 280, 200}, {700, 200, 120}};
        const auto obs = BotPolicy::observation(sample, 7);
        const std::array<float, 8> expected{0.25f, -0.5f, 1.0f, 1.0f / 6, 0.3f, 0.5f, 0.015f, 1};
        for (int i = 0; i < 8; ++i) require(std::abs(obs[i] - expected[i]) < 1e-6, "Wrong observation or bird slot");
        sample.pipes.clear();
        const auto empty = BotPolicy::observation(sample, 7);
        require(empty[3] == 1 && empty[4] == 0 && empty[5] == 1 && empty[7] == 0, "Wrong missing-pipe observation");
        const int count = std::stoi(argv[3]);
        require(count >= 1 && count <= 8, "Bot count out of range");
        for (unsigned int seed : {483679114u, 1646945053u, 42u}) {
            game_set settings{};
            settings._size = count; settings._speed = 1;
            const auto ids = engine::begin(settings, seed);
            require(ids[0] >= 0, "Unable to allocate bot birds");
            int steps = 0;
            while (!engine::is_finished() && steps < 30000) {
                const auto state = engine::get_state();
                std::array<bool, 8> actions{};
                for (int i = 0; i < count; ++i) {
                    require(state.birds[ids[i]].respawn_ms == 0, "Bot crashed before finish");
                    actions[ids[i]] = policy.jump(state, ids[i]);
                }
                engine::step(actions); ++steps;
            }
            require(engine::is_finished(), "Bots did not finish");
            const auto finished = engine::get_state();
            for (int i = 0; i < count; ++i)
                require(finished.birds[ids[i]].position.x >= config::world_width &&
                        finished.birds[ids[i]].respawn_ms == 0, "Bot has not reached the finish");
            engine::clear();
            std::cout << count << " bot(s), seed " << seed << ": finish in " << steps << " steps\n";
        }
        std::cout << verified << " C++ / SB3 parity cases passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
