#include "bot_policy.hpp"
#include "crow/json.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iterator>
#include <stdexcept>

BotPolicy::BotPolicy(const std::filesystem::path& model) {
    auto metadata_path = model;
    metadata_path.replace_extension(".json");
    std::ifstream file(metadata_path);
    const std::string text((std::istreambuf_iterator<char>(file)), {});
    const auto metadata = crow::json::load(text);
    if (!metadata || metadata["schema_version"].i() != 1 || metadata["observation_version"].i() != 1)
        throw std::runtime_error("Invalid bot model metadata");
    const auto& c = metadata["engine_config"];
#define MATCH_CONFIG(key) if (std::abs(c[#key].d() - static_cast<double>(config::key)) > 1e-12) \
    throw std::runtime_error("Bot model physics mismatch: " #key)
    MATCH_CONFIG(camera_width); MATCH_CONFIG(camera_height); MATCH_CONFIG(world_width);
    MATCH_CONFIG(world_height); MATCH_CONFIG(max_p); MATCH_CONFIG(v_fps); MATCH_CONFIG(g);
    MATCH_CONFIG(force); MATCH_CONFIG(min_v); MATCH_CONFIG(max_horizontal_speed);
    MATCH_CONFIG(max_vertical_speed); MATCH_CONFIG(p_x); MATCH_CONFIG(p_s); MATCH_CONFIG(p_n_x);
    MATCH_CONFIG(p_df); MATCH_CONFIG(b_x); MATCH_CONFIG(b_y); MATCH_CONFIG(alive_ms); MATCH_CONFIG(invin_ms);
#undef MATCH_CONFIG
    options_.SetIntraOpNumThreads(1);
    options_.SetInterOpNumThreads(1);
    options_.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
    session_ = Ort::Session(environment_, model.c_str(), options_);
    if (session_.GetInputCount() != 1 || session_.GetOutputCount() != 1)
        throw std::runtime_error("Expected one bot observation input and one logits output");
    const auto input_info = session_.GetInputTypeInfo(0);
    const auto output_info = session_.GetOutputTypeInfo(0);
    const auto input = input_info.GetTensorTypeAndShapeInfo();
    const auto output = output_info.GetTensorTypeAndShapeInfo();
    if (input.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT ||
        output.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT ||
        input.GetShape() != std::vector<int64_t>{-1, 8} ||
        output.GetShape() != std::vector<int64_t>{-1, 2})
        throw std::runtime_error("Unexpected bot model tensor format");
}

std::array<float, 8> BotPolicy::observation(const game_state& state, int bird_id) {
    const auto& bird = state.birds.at(bird_id);
    const auto pipe = std::find_if(state.pipes.begin(), state.pipes.end(), [&](const auto& p) {
        return p._x + config::p_x >= bird.position.x;
    });
    const bool has_pipe = pipe != state.pipes.end();
    return {static_cast<float>(bird.position.y / config::world_height),
            static_cast<float>(bird.velocity.y / (config::max_vertical_speed * config::v_fps)),
            static_cast<float>(bird.velocity.x / (config::max_horizontal_speed * config::v_fps)),
            has_pipe ? static_cast<float>((pipe->_x - bird.position.x) / config::camera_width) : 1.0f,
            has_pipe ? static_cast<float>(pipe->_down / config::world_height) : 0.0f,
            has_pipe ? static_cast<float>(pipe->_up / config::world_height) : 1.0f,
            static_cast<float>(bird.position.x / config::world_width), has_pipe ? 1.0f : 0.0f};
}

std::array<float, 2> BotPolicy::logits(const std::array<float, 8>& input) {
    auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    const std::array<int64_t, 2> shape{1, 8};
    auto tensor = Ort::Value::CreateTensor<float>(memory, const_cast<float*>(input.data()),
                                                input.size(), shape.data(), shape.size());
    const char* inputs[] = {"observation"};
    const char* outputs[] = {"logits"};
    auto result = session_.Run(Ort::RunOptions{nullptr}, inputs, &tensor, 1, outputs, 1);
    const auto* values = result[0].GetTensorData<float>();
    if (!std::isfinite(values[0]) || !std::isfinite(values[1]))
        throw std::runtime_error("Bot produced non-finite logits");
    return {values[0], values[1]};
}

bool BotPolicy::jump(const game_state& state, int bird_id) {
    const auto& bird = state.birds.at(bird_id);
    if (!bird.present || bird.respawn_ms > 1000 * config::v_fps) return false;
    if (bird.respawn_ms > 0) {
        // engine::step revives before moving. Predict from the state it will use.
        auto revived = state;
        revived.birds[bird_id].position.y = config::camera_height / 2;
        revived.birds[bird_id].velocity = {0, 0};
        const auto values = logits(observation(revived, bird_id));
        return values[1] > values[0];
    }
    const auto values = logits(observation(state, bird_id));
    return values[1] > values[0]; // Ties select action 0, matching deterministic SB3 argmax.
}
