#include"cengine.hpp"
#include<random>
#include<iostream>
#include<algorithm>

std::mt19937 engine::gen{}; 
std::vector<pipe*> engine::active_pipes{};
game_phase engine::_phase=game_phase::idle;

std::array<int,8> engine::begin(const game_set& sets,unsigned int seed){//游戏初始化 返回鸟
    std::array<int, 8> failed_ids;
    failed_ids.fill(-1);
    if(sets._size<1 || sets._size>config::max_p){
        //写错误日志
        std::cerr << "[engine::begin] Invalid player count: "
            << sets._size
            << ". Expected 1 to " << config::max_p << '\n';
        return failed_ids;
    }

    //清理
    clear();

    std::array<int,8>b_is{};
    gen.seed(seed);               
    config::game_speed=std::max(1,sets._speed);  //初始化难度

    for(int i=0;i<sets._size;i++){//初始人数
        int b_i=bird_pool::on_join_in({0,config::world_height/2},sets.character[i]);
        if(b_i==-1){ //角色可以重叠
            //此处写错误日志 TODO
            std::cerr << "[engine::begin] Failed to create player "
                << i << ": bird pool is full.\n";

            clear(); // 清理本次已经创建的玩家
            return failed_ids;
        }
        b_is[i]=b_i;
    }
    //申请10个管子
    for(int i=0;i<10;i++)
        generate_pipes();
    //开始游戏
    _phase=game_phase::running;
    return b_is;
};

void engine::clear(){
    for(auto &x:active_pipes){ //返回x
        pipe_pool::release(x);
    }

    active_pipes.resize(0);

    for(int i=0;i<8;i++){
        if(bird_pool::pool[i]!=nullptr){
            bird_pool::on_leave(i);
        }
    }
    _phase=game_phase::idle;
}

bool engine::is_finished(){//判断鸟到没到终点
    return _phase==game_phase::finished;
}

bool engine::generate_pipes(){
    //取最后一个
    //数值到时候调
    if(active_pipes.empty()){
        std::uniform_real_distribution<double> _p(config::world_height/4,3*config::world_height/4);
        double n_u=_p(gen);
        auto f_p= pipe_pool::acquire(n_u,n_u-config::p_s,500);
        active_pipes.push_back(f_p);
        return true;
    }

    auto x=active_pipes[active_pipes.size()-1];
    double dif=config::p_df/config::game_speed;
    std::uniform_real_distribution<double> up(x->_up-dif,x->_up+dif);
    double n_u=up(gen);
    if(n_u>3*config::world_height/4) n_u=3*config::world_height/4;
    if(n_u<config::world_height/4) n_u=config::world_height/4;
    auto n_x=x->_x+config::p_n_x;

    if(n_x>config::world_width-2*config::p_x) return false; //超出世界之外

    auto n_p= pipe_pool::acquire(n_u,n_u-config::p_s,n_x);
    active_pipes.push_back(n_p);
    return true;
}

void engine::recycle_pipes(){
    if(active_pipes.empty())return;
    auto pp=active_pipes[0];
    for(int i=0;i<8;i++){
        auto x=bird_pool::pool[i];
        if(x!=nullptr){//
            if(pp->_x>=x->x_satuation()-config::camera_width/3){ //默认鸟位于1/4 1/3更安全
                return;
            }
        }
    }
    //一次第一个
    pipe_pool::release(pp);
    active_pipes.erase(active_pipes.begin());
}

void engine::check_collisions(){
    for(int i=0;i<8;i++){//遍历鸟
        auto x=bird_pool::pool[i];
        if(x==nullptr || x->_alive!=0 || x->_invin!=0)continue; //死了 和无敌都不检查

        if(x->y_satuation() < 0 ||  x->y_satuation()+ config::b_y > config::world_height){
            x->_alive=config::alive_ms;
            continue;
        }

        auto at=[x](const pipe* p){
           bool overlap_x =
                x->x_satuation() + config::b_x >= p->_x &&
                x->x_satuation() <= p->_x + config::p_x;

            bool outside_hole =
                x->y_satuation() + config::b_y > p->_up ||
                x->y_satuation() < p->_down;

            return overlap_x && outside_hole;
        };
        if(active_pipes.end()!=std::find_if(active_pipes.begin(),active_pipes.end(),at))
            x->_alive=config::alive_ms;//复活时间
    }
}


void engine::update_respawn(){
    for(int i=0;i<8;i++){//遍历鸟
        auto x=bird_pool::pool[i];
        if(x==nullptr)continue;
        //更新无敌时间
        if(x->_invin!=0){
            double reinvin=x->_invin;
            reinvin=std::max(0.0,reinvin-1000*config::v_fps);
            x->_invin=reinvin;
        }
        if(x->_alive==0) continue;
        double remain=x->_alive;
        remain=std::max(0.0,remain-1000*config::v_fps);
        if(remain==0.0){//复活了
            x->_satuation.y=config::camera_height/2;
            x->_invin=config::invin_ms;
            x->_v={0,0};
        }
        x->_alive=remain;
    }
}

void engine::step(const std::array<bool,8>&actions){
    //游戏已经结束
    if(_phase!=game_phase::running) return; //后面服务器来做决定

    update_respawn();//更新复合和无敌时间

    double mx_b_x=0; //最低是0
    for(int i=0;i<8;i++){//遍历鸟
        auto x=bird_pool::pool[i];
        if(x==nullptr) continue;

        if(x->_alive==0) x->fly(actions[i]);
        //找最远的
        mx_b_x=std::max(mx_b_x,x->_satuation.x);
    }

    //飞完直接检查碰撞
    check_collisions();

    //都死了也ok
    int achieve=(4*mx_b_x+config::world_width)/config::world_width;
    //更新游戏难度
    config::game_speed=std::max(achieve,config::game_speed);

    //先回收
    recycle_pipes();

    //后更新管道
    while(active_pipes.empty() 
    || active_pipes[active_pipes.size()-1]->_x<mx_b_x+config::camera_width)//保守起见
    {
       if(!generate_pipes())break;
    }
    check_finish();
}

void engine::check_finish(){
    //只有运行时检查有意义
    if(_phase!=game_phase::running)return;

    for(int i=0;i<8;i++){
        auto x=bird_pool::pool[i];
        if(x!=nullptr && x->_alive==0){//
            if(x->x_satuation()>=config::world_width){
                _phase=game_phase::finished;
            }
        }
    }
}

game_state engine::get_state(){
    game_state state{};

    state.phase=_phase;
    state.speed=config::game_speed;

    state.pipes.reserve(active_pipes.size());
    for(auto & p:active_pipes){
        state.pipes.push_back({
            p->_x,
            p->_up,
            p->_down
        });
    }

    for(int i=0;i<8;i++){
        auto otp=bird_pool::pool[i];
        if(otp==nullptr)continue;

        auto& outputs = state.birds[i];

        outputs.present=true;
        outputs.character=otp->_character;
        outputs.position=otp->_satuation;
        outputs.velocity=otp->_v;
        outputs.respawn_ms=otp->_alive;
        outputs.invincible_ms=otp->_invin;
    }
    return state;
}

void engine::on_leave(int x){
    bird_pool::on_leave(x);
}
