#pragma once

#include<memory>
#include<array>
#include"ve2.hpp"

class engine;

class brids
{
//只通过 鸟_pool 创造
// using BridsAlloc = std::allocator<brids>;
// using BridsAllocTraits = std::allocator_traits<BridsAlloc>;

friend class brids_pool;
friend class engine;

Vec2 _satuation;

Vec2 _v;
// BridsAlloc _alloc; 构造器 好像不用

int _character;

double _alive;
double _invin;

private:
    brids();
    brids(Vec2,int); //地点和皮肤
    ~brids();


public:
    void fly(const bool&);
    const double y_satuation() const;
    const double x_satuation() const;
};


class brids_pool{ //管理所有的鸟
    brids_pool(){};
    ~brids_pool(){};
public:    
    static std::array<brids*,8>pool;

    static int on_join_in(Vec2,int);
    static void on_leave(const int&);

};
