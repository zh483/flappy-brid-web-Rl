#pragma once

#include<vector>

class pipe{
    //只通过对象池创建

friend class pipe_pool; //友元类

public:

double _up;// 上洞口
double _down;// 下洞口
double _x; //世界位置

private:
    pipe(double,double,double);
    ~pipe();

    void react(double,double,double); //重置自己
public:
    //void move();             管道不动
};

class pipe_pool{//对象池 无实例
    //存指针
    static std::vector<pipe*>pool;

private:
    pipe_pool();
    ~pipe_pool();


public:
    static pipe* acquire(double,double,double); //h.s.x
    static void release(pipe*);
};

