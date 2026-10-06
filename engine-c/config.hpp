#pragma once
//暂时需要的超参数
struct config
{
    //不能创对象
    // 摄像头的逻辑尺寸，网页显示时按比例缩放
    static const double camera_width;
    static const double camera_height;

    // 有限横向关卡：鸟沿 x 轴前进，到达 world_width 时结束（由 Engine 实现）
    // Engine 仅回收已落在所有玩家摄像头后方、完全不可见的管道
    static const double world_width;
    static const double world_height;

    static const double g;
    static const int min_v;
    static const double force;
    static const int max_p;
    static const double v_fps;
    static const double p_df;
    static const double p_x; //pipe的大小
    static const double p_s;
    static const double b_y;
    static const double b_x;

    static const double invin_ms;
    static const double alive_ms;

    static int game_speed;
private:
    config(){}
    ~ config(){}
};
