#include"config.hpp"

const double config::camera_width = 600.0;
const double config::camera_height = 400.0;
const double config::world_width = 40000.0;
const double config::world_height = 400.0;

const double config::g=0.98;
const int config::min_v=2;
// 管道间可用距离为 200 - 50 - 25 = 125 像素；120 像素/秒留约 1 秒调整。
const double config::max_horizontal_speed=120.0;
const double config::max_vertical_speed=120;
const double config::force=9.8;
const int config::max_p = 8;//最高八个人联机
const double config::v_fps=1.0/24.0; //虚拟时间
const double config::p_df=20;
const double config::p_x=50;
const double config::p_s=80;
const double config::p_n_x=200;
const double config::b_x=25;
const double config::b_y=20;
const double config::invin_ms=1000;
const double config::alive_ms=3000;

int config::game_speed=1; //初始化为1
