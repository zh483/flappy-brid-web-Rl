#include"brids.hpp"
#include"../config.hpp"

//初始化
std::array<brids*,8>brids_pool::pool={nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr};

brids::brids()
:_satuation({0,0}),_v({0,0}),_character(0)
{}

brids::brids(Vec2 _s,int sk)
:_satuation(_s),_v({0,0}),_character(sk),_alive(0),_invin(0)
{}

brids::~brids(){}

void brids::fly(const bool& w){ //鸟自己动
    _satuation.y+=_v.y;
    _satuation.x+=_v.x;
    //惯性
    if(w){
        _v.y+=config::force;
    }
    _v.y-=config::g;
    _v.x=config::min_v*config::game_speed;
}

const double brids::y_satuation() const {return _satuation.y;} //服务器校准的
const double brids::x_satuation() const {return _satuation.x;}


int brids_pool::on_join_in(Vec2 _s,int sk){//直接扫一遍
    for(int i=0;i<8;i++){
        if(pool[i]==nullptr){
            pool[i]=new brids(_s,sk);
            pool[i]->_alive=0;
            return i;
        }
    }
    return -1;
}

void brids_pool::on_leave(const int& i){
    if(i<0 || i>=8) return;
    if(pool[i]==nullptr)return;
    brids* p=pool[i];
    pool[i]=nullptr;
    delete p;
}