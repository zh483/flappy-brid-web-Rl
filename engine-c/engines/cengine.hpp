#pragma once
#include"../objective/brids.hpp"
#include"../objective/pipe.hpp"
#include"../config.hpp"
#include<random>
#include<vector>

enum class game_phase{
      idle,
    running,
    finished
};

struct game_set
{
    int _size; //游戏人数
    int _speed; //初始难度
    std::array<int,8>character; //角色的信息 其实也就是皮肤了
};


struct pipe_state
{
    double _x;
    double _up;
    double _down;
};

struct bird_state
{
    bool present = false;       // 这个玩家槽位是否有人
    int character = 0;          // 皮肤
    Vec2 position{0, 0};
    Vec2 velocity{0, 0};  
    double respawn_ms = 0;      // 剩余复活时间
    double invincible_ms = 0;   // 剩余无敌时间
};

struct game_state {
    game_phase phase = game_phase::idle;
    int speed = 1;
    std::vector<pipe_state> pipes;
    std::array<bird_state, 8> birds{};
};


struct game_state; //游戏状态

class engine{//无实例   
public:
    static void begin(const game_set& sets,unsigned int seed=0); //开始游戏
    static void step(const std::array<bool,8>&actions); //就这一个 逻辑
    static game_state get_state(); // 供服务器和 Python 读取
    static bool is_finished();
    static void clear();           // 清空本局，归还活动管道

private:
    static bool generate_pipes();  // 计算位置、洞口，向池申请管道
    static void recycle_pipes();   // 回收所有摄像头后方的管道
    static void check_collisions();
    static void update_respawn();  // 如果保留自动复活规则
    static void check_finish();

    static std::mt19937 gen; // 统一的随机引擎
    static std::vector<pipe*> active_pipes;
    static game_phase _phase;

};


