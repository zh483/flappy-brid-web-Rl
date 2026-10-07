#include"birds.hpp"
#include"../config.hpp"
#include <algorithm>

//初始化
std::array<bird*,8>bird_pool::pool={nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr};

bird::bird()
:_satuation({0,0}),_v({0,0}),_character(0),_alive(0),_invin(0)
{}

bird::bird(Vec2 _s,int sk)
:_satuation(_s),_v({0,0}),_character(sk),_alive(0),_invin(0)
{}

bird::~bird(){}

void bird::fly(const bool& w){ //鸟自己动
    _satuation.y+=_v.y;
    _satuation.x+=_v.x;
    //惯性
    if(w){
        _v.y+=config::force;
    }
    _v.y-=config::g;
    //限制y速度
    _v.y=std::min(_v.y,config::max_vertical_speed*config::v_fps);
    _v.y=std::max(_v.y,-config::max_vertical_speed*config::v_fps);
    // min_v 原本是每步位移；把每秒上限换算为每步上限。
    _v.x=std::min(static_cast<double>(config::min_v)*config::game_speed,
                  config::max_horizontal_speed*config::v_fps);

}

const double bird::y_satuation() const {return _satuation.y;} //服务器校准的
const double bird::x_satuation() const {return _satuation.x;}


int bird_pool::on_join_in(Vec2 _s,int sk){//直接扫一遍
    for(int i=0;i<8;i++){
        if(pool[i]==nullptr){
            pool[i]=new bird(_s,sk);
            pool[i]->_alive=0;
            return i;
        }
    }
    return -1;
}

void bird_pool::on_leave(const int& i){
    if(i<0 || i>=8) return;
    if(pool[i]==nullptr)return;
    bird* p=pool[i];
    pool[i]=nullptr;
    delete p;
}
