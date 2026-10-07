#pragma once

#include<memory>
#include<array>
#include"ve2.hpp"

class engine;

class bird
{
//只通过 鸟_pool 创造
// using BirdAlloc = std::allocator<bird>;
// using BirdAllocTraits = std::allocator_traits<BirdAlloc>;

friend class bird_pool;
friend class engine;

Vec2 _satuation;

Vec2 _v;
// BirdAlloc _alloc; 构造器 好像不用

int _character;

double _alive;
double _invin;

private:
    bird();
    bird(Vec2,int); //地点和皮肤
    ~bird();


public:
    void fly(const bool&);
    const double y_satuation() const;
    const double x_satuation() const;
};


class bird_pool{ //管理所有的鸟
    bird_pool(){};
    ~bird_pool(){};
public:    
    static std::array<bird*,8>pool;

    static int on_join_in(Vec2,int);
    static void on_leave(const int&);

};
