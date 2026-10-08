#include "crow.h"
#include "engines/cengine.hpp"
#include "bot_policy.hpp"

#include <array>
#include <string>
#include <unordered_map>
#include <exception>

//计时和锁
#include <chrono>
#include <cstdint>
#include <mutex>
#include <charconv>
#include <iostream>
#include <memory>
#include <filesystem>

using game_clock = std::chrono::steady_clock;

struct client_info {
    int client_id;
    int bird_id = -1; // -1 表示还没有鸟
    int skin = 0;
};

// 所有连接管理数据放在一起，由 main 创建并传给处理函数。
struct server_state {
    std::array<bool, 8> clients{};
    int client_numb = 0;
    std::unordered_map<crow::websocket::connection*, client_info> connections;
    std::array<bool,8>pending_jump{};
    game_clock::time_point last_update = game_clock::now();
    double accumulated_seconds = 0.0;
    std::uint64_t tick = 0;
    BotPolicy* bot_policy = nullptr;
    int configured_bots = 0;
    std::array<bool, 8> bot_birds{};
};

void send_error(crow::websocket::connection& conn, const std::string& error) {
    crow::json::wvalue message;
    message["type"] = "error";
    message["message"] = error;
    conn.send_text(message.dump());
}

void reset_game_clock(server_state& server) {
    server.pending_jump.fill(false);
    server.accumulated_seconds = 0.0;
    server.last_update = game_clock::now();
    server.tick = 0;
}

void broadcast_state(const server_state& server, const game_state& state);

bool handle_accept(const server_state& server) {
    return server.client_numb < 8 && engine::_phase != game_phase::running;
}

void handle_open(server_state& server, crow::websocket::connection& conn) {
    // 接受握手后再检查一次，避免这期间房间状态发生变化。
    if (!handle_accept(server)) {
        conn.close("玩家已满或游戏已开始");
        return;
    }
    for (int i = 0; i < 8; ++i) {
        if (server.clients[i])
            continue;

        server.connections[&conn] = {i};
        server.clients[i] = true;
        ++server.client_numb;
        crow::json::wvalue message;
        message["type"] = "connected";
        message["client_id"] = i;
        conn.send_text(message.dump());
        CROW_LOG_INFO << "玩家 " << i << " 连接上了";
        return;
    }

    // 没有分配编号的连接，关闭时不会减少在线人数。
    conn.close("玩家已满");
}

void handle_close(server_state& server, crow::websocket::connection& conn) {
    auto it = server.connections.find(&conn);
    if (it == server.connections.end())
        return;

    const client_info info = it->second;
    if (info.bird_id >= 0)
        engine::on_leave(info.bird_id);

    server.clients[info.client_id] = false;
    --server.client_numb;
    server.connections.erase(it);
    CROW_LOG_INFO << "玩家 " << info.client_id << " 离开了";
    //重置计时
    if (info.bird_id >= 0 && info.bird_id < 8)
        server.pending_jump[info.bird_id] = false;

    if (server.client_numb == 0) {
        reset_game_clock(server);
        engine::clear();
        server.bot_birds.fill(false);
    }
}

//阅读数字字段
bool read_integer(crow::websocket::connection& conn,
                  const crow::json::rvalue& data,
                  const char* field, int minimum, int& result) {
    if (!data.has(field) || data[field].t() != crow::json::type::Number) {
        send_error(conn, std::string("需要整数字段: ") + field);
        return false;
    }

    const auto number_type = data[field].nt();
    if (number_type != crow::json::num_type::Signed_integer &&
        number_type != crow::json::num_type::Unsigned_integer) {
        send_error(conn, std::string("字段必须是整数: ") + field);
        return false;
    }

    // 直接检查转换结果，极大的整数也不能溢出后变成合法编号。
    const std::string text = static_cast<std::string>(data[field]);
    int value = 0;
    const auto parsed = std::from_chars(text.data(), text.data() + text.size(), value);
    if (parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size() ||
        value < minimum) {
        send_error(conn, std::string("字段数值超出范围: ") + field);
        return false;
    }

    result = static_cast<int>(value);
    return true;
}

//阅读string
bool read_string(crow::websocket::connection& conn,
                  const crow::json::rvalue& data,
                  const char* field,std::string& result){
    if (!data.has(field) || data[field].t() != crow::json::type::String) {
        send_error(conn, std::string("需要字符串字段: ") + field);
        return false;
    }

    result = static_cast<std::string>(data[field].s());
    return true;
}

void handle_select_skin(server_state& server,
                        crow::websocket::connection& conn,
                        const crow::json::rvalue& data) {
    if (engine::_phase == game_phase::running) {
        send_error(conn, "游戏中不能修改皮肤");
        return;
    }

    auto it = server.connections.find(&conn);
    if (it == server.connections.end())
        return;

    int skin = 0;
    if (!read_integer(conn, data, "skin", 0, skin))
        return;

    // TODO: 确定皮肤数量后，在这里检查皮肤编号的上限。
    it->second.skin = skin;
    crow::json::wvalue message;
    message["type"] = "skin_selected";
    message["skin_id"] = skin;
    conn.send_text(message.dump());
}

void handle_game_begin(server_state& server,
                       crow::websocket::connection& conn,
                       const crow::json::rvalue& data) {
    if (engine::_phase == game_phase::running) {
        send_error(conn, "游戏已经开始");
        return;
    }

    int speed = 1;
    if (!read_integer(conn, data, "speed", 1, speed))
        return;

    game_set settings{};
    int bots = server.configured_bots;
    if (data.has("bots") && !read_integer(conn, data, "bots", 0, bots)) return;
    if (bots > 7) {
        send_error(conn, "机器人数量必须在 0 到 7 之间");
        return;
    }
    if (server.client_numb + bots > 8) {
        send_error(conn, "真人与机器人合计不能超过 8 只鸟");
        return;
    }
    if (bots > 0 && !server.bot_policy) {
        send_error(conn, "机器人模型未加载");
        return;
    }
    settings._size = server.client_numb + bots;
    settings._speed = speed;

    int i = 0;
    for (const auto& connection : server.connections)
        settings.character[i++] = connection.second.skin;
    for (int b = 0; b < bots; ++b) settings.character[i + b] = (b + 4) % 6;

    const auto bird_ids = engine::begin(settings);
    if (bird_ids[0] < 0) {
        send_error(conn, "开始游戏失败");
        return;
    }

    reset_game_clock(server);
    server.bot_birds.fill(false);
    for (int b = server.client_numb; b < settings._size; ++b)
        server.bot_birds[bird_ids[b]] = true;
    // 两次遍历之间没有修改 connections，顺序一致。
    i = 0;
    for (auto& connection : server.connections){
        auto& info=connection.second;
        auto* conn=connection.first;
        info.bird_id = bird_ids[i++];


        crow::json::wvalue message;
        message["type"]="game_started";
        message["client_id"]=info.client_id;
        message["bird_id"]=info.bird_id;
        message["skin_id"]=info.skin;
        message["speed"]=speed;
        message["bot_count"] = bots;
        conn->send_text(message.dump());
    }
    CROW_LOG_INFO << "游戏开始，玩家数: " << settings._size;
    // 立即发送 tick=0 的初始画面，不必等待第一次更新。
    broadcast_state(server, engine::get_state());
}

void handle_client_error(server_state& server,
                       crow::websocket::connection& conn,
                       const crow::json::rvalue& data){
    std::string error{};
    if(!read_string(conn,data,"error",error))
        return;
    CROW_LOG_ERROR<<"客户端产生错误,错误是:"<<error;
}

void handle_jump(server_state& server,
                       crow::websocket::connection& conn,
                       const crow::json::rvalue& data){
    if (engine::_phase != game_phase::running)
        return;
    auto it=server.connections.find(&conn);
    if(it==server.connections.end())
        return;

    int b_i=it->second.bird_id;
    if(b_i<0 || b_i>=8)
        return;

    server.pending_jump[b_i]=true;
}

// 这里只负责解析公共字段、识别消息类型，再分发给对应函数。
void handle_message(server_state& server,
                    crow::websocket::connection& conn,
                    const std::string& message, bool is_binary) {
    try {
        if (server.connections.find(&conn) == server.connections.end())
            return;

        if (is_binary) {
            send_error(conn, "不解析二进制信息");
            return;
        }

        const auto data = crow::json::load(message);
        if (!data || data.t() != crow::json::type::Object) {
            send_error(conn, "只解析 JSON 对象");
            return;
        }

        if (!data.has("type") || data["type"].t() != crow::json::type::String) {
            send_error(conn, "需要字符串字段: type");
            return;
        }

        const std::string type = data["type"].s();
        if (type == "select_skin") {
            handle_select_skin(server, conn, data);
        } else if (type == "game_begin") {
            handle_game_begin(server, conn, data);
        } else if (type == "client_error") {
            handle_client_error(server, conn, data);
        } else if (type == "jump") {
            handle_jump(server, conn, data);
        } else {
            send_error(conn, "未知的消息类型");
        }
    } catch (const std::exception& error) {
        CROW_LOG_ERROR << "无法处理客户端信息: " << error.what();
        send_error(conn, "信息处理失败");
    }
}

crow::json::wvalue pipes_to_json(
    const std::vector<pipe_state>& pipes) {

    // 初始化为空数组，即使没有管道也会输出 []
    crow::json::wvalue result(crow::json::wvalue::list{});

    unsigned i = 0;
    for (const auto& pipe : pipes) {
        auto& item = result[i++];

        item["x"] = pipe._x;
        item["up"] = pipe._up;
        item["down"] = pipe._down;
    }

    return result;
}

crow::json::wvalue birds_to_json(
    const std::array<bird_state, 8> & birds) {

    crow::json::wvalue result(crow::json::wvalue::list{});
    for (unsigned i = 0; i < birds.size(); ++i) {
        const auto& bird = birds[i];
        auto& item = result[i];
        item["bird_id"] = i;
        item["present"]=bird.present;
        item["character"]=bird.character;
        item["position_x"]=bird.position.x;
        item["position_y"]=bird.position.y;
        item["velocity_x"]=bird.velocity.x;
        item["velocity_y"]=bird.velocity.y;
        item["respawn_ms"]=bird.respawn_ms;
        item["invincible_ms"]=bird.invincible_ms;
    }
    return result;
}

// 公共状态组装一次，每个客户端只补自己的编号。
void broadcast_state(const server_state& server, const game_state& state) {
    crow::json::wvalue message;
    std::string phase;
    switch (state.phase) {
    case game_phase::idle: phase = "idle"; break;
    case game_phase::running: phase = "running"; break;
    case game_phase::finished: phase = "finished"; break;
    default: phase = "undefined"; break;
    }

    message["type"] = "game_state";
    message["tick"] = server.tick;
    message["phase"] = phase;
    message["speed"] = state.speed;
    message["pipes"] = pipes_to_json(state.pipes);
    message["birds"] = birds_to_json(state.birds);
    message["bot_count"] = static_cast<int>(std::count(server.bot_birds.begin(), server.bot_birds.end(), true));
    for (unsigned i = 0; i < 8; ++i)
        message["birds"][i]["is_bot"] = server.bot_birds[i];

    for (const auto& connection : server.connections) {
        crow::json::wvalue client_message(message);
        client_message["client_id"] = connection.second.client_id;
        client_message["bird_id"] = connection.second.bird_id;
        connection.first->send_text(client_message.dump());
    }
}

void update_server(server_state& server) {
    const auto now = game_clock::now();

    const double elapsed =
        std::chrono::duration<double>(
            now - server.last_update
        ).count();

    server.last_update = now;

    if (engine::_phase != game_phase::running) {
        server.accumulated_seconds = 0.0;
        return;
    }

    server.accumulated_seconds += elapsed;

    const double step_seconds = config::v_fps;
    int steps = 0;

    // 每次回调最多补 8 步，避免长期占住服务器。
    // 没处理完的累计时间保留到下次。
    while (server.accumulated_seconds >= step_seconds &&
           steps < 8 &&
           engine::_phase == game_phase::running) {
        auto actions = server.pending_jump;
        server.pending_jump.fill(false);
        if (server.bot_policy) {
            const auto snapshot = engine::get_state();
            for (int i = 0; i < 8; ++i) {
                if (!server.bot_birds[i]) continue;
                try {
                    actions[i] = server.bot_policy->jump(snapshot, i);
                } catch (const std::exception& error) {
                    // Stop only this bot; a bad model must not terminate the server.
                    CROW_LOG_ERROR << "机器人推理失败: " << error.what();
                    server.bot_birds[i] = false;
                    engine::on_leave(i);
                    for (const auto& entry : server.connections)
                        send_error(*entry.first, "机器人推理失败，该机器人已退出");
                }
            }
        }

        engine::step(actions);

        server.accumulated_seconds -= step_seconds;
        ++server.tick;
        ++steps;

        // 暂时每 24 步打印一次，验证更新是否持续执行。
        if (server.tick % 24 == 0) {
            CROW_LOG_INFO << "游戏已更新 "
                          << server.tick << " 步";
        }
    }

    if (steps > 0)
        broadcast_state(server, engine::get_state());
}

int main(int argc, char* argv[]) {
    // 默认端口不变，测试时可传入独立端口，避免占用正在运行的服务器。
    int port = 18080;
    int bots = 0;
    auto model = std::filesystem::absolute(argv[0]).parent_path() / "models/ppo-bird.onnx";
    bool port_given = false;
    for (int index = 1; index < argc; ++index) {
        const std::string option = argv[index];
        if (option == "--model" && index + 1 < argc) { model = argv[++index]; continue; }
        const bool bot_option = option == "--bots";
        if ((bot_option && index + 1 == argc) || (!bot_option && port_given)) {
            std::cerr << "Usage: flappy_server [port] [--bots 0..7] [--model path]\n"; return 1;
        }
        const std::string text = bot_option ? argv[++index] : option;
        int value = 0;
        const auto parsed = std::from_chars(text.data(), text.data() + text.size(), value);
        if (parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size() ||
            value < (bot_option ? 0 : 1) || value > (bot_option ? 7 : 65535)) {
            std::cerr << "Invalid port or bot count\n"; return 1;
        }
        if (bot_option) bots = value;
        else { port = value; port_given = true; }
    }
    crow::SimpleApp app;
    server_state server;
    std::unique_ptr<BotPolicy> bot_policy;
    try {
        bot_policy = std::make_unique<BotPolicy>(model);
        server.bot_policy = bot_policy.get();
    } catch (const std::exception& error) {
        CROW_LOG_WARNING << "机器人不可用: " << error.what();
        if (bots > 0) return 1;
    }
    server.configured_bots = bots;
    std::mutex server_mutex;

    CROW_WEBSOCKET_ROUTE(app, "/ws")
        .max_payload(64 * 1024)
        .onaccept([&](const crow::request&, void**) {
            std::lock_guard<std::mutex> lock(server_mutex);
            return handle_accept(server);
        })
        .onopen([&](crow::websocket::connection& conn) {
            std::lock_guard<std::mutex> lock(server_mutex);
            handle_open(server, conn);
        })
        .onclose([&](crow::websocket::connection& conn,
                     const std::string&, uint16_t) {
            std::lock_guard<std::mutex> lock(server_mutex);
            handle_close(server, conn);
        })
        .onmessage([&](crow::websocket::connection& conn,
                       const std::string& message, bool is_binary) {
            std::lock_guard<std::mutex> lock(server_mutex);
            handle_message(server, conn, message, is_binary);
        });

    //服务器每次更新
    app.tick(std::chrono::milliseconds(5), [&]() {
        std::lock_guard<std::mutex> lock(server_mutex);
        update_server(server);
    });

    app.port(static_cast<uint16_t>(port)).run();
}
