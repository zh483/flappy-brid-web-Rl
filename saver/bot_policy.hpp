#pragma once
#include "engines/cengine.hpp"
#include <onnxruntime_cxx_api.h>
#include <array>
#include <filesystem>

// One immutable network shared by all bots; each decision uses that bird's snapshot.
class BotPolicy {
public:
    explicit BotPolicy(const std::filesystem::path& model);
    static std::array<float, 8> observation(const game_state& state, int bird_id);
    std::array<float, 2> logits(const std::array<float, 8>& input);
    bool jump(const game_state& state, int bird_id);
private:
    Ort::Env environment_{ORT_LOGGING_LEVEL_WARNING, "flappy-bot"};
    Ort::SessionOptions options_;
    Ort::Session session_{nullptr};
};
