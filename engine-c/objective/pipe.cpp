#include"pipe.hpp"
#include"../config.hpp"
#include<random>

std::vector<pipe*> pipe_pool::pool{};

pipe::pipe(double u,double d,double x)
:_up(u),_down(d),_x(x)
{}

pipe::~pipe(){
}

void pipe::react(double u,double d,double x){ //重置
    _up=u;
    _down=d;
    _x=x;
}

// void pipe::move(){ //移动
//     _x-=config::min_v*config::game_speed;
// }

pipe_pool::pipe_pool()
{}

pipe_pool::~pipe_pool()
{}

pipe* pipe_pool::acquire(double u,double d,double x){
    //不搞log n那一套了
    if(!pool.empty()){
        auto p=pool[pool.size()-1];
        pool.pop_back();
        p->react(u,d,x);
        return p;
    }
    return new pipe(u,d,x);
} 

void pipe_pool::release(pipe* p){
    if(p==nullptr)return;
    pool.push_back(p);
}