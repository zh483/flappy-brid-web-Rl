# flappy-brid-web-Rl

Flappy Bird 联机项目：C++ 游戏引擎、计划中的 WebSocket 服务器和网页前端，
以及供 Python 强化学习训练使用的 pybind11 接口。

当前已经实现固定步长更新、共享管道、碰撞、复活、无敌、终点判定和状态快照。
摄像头尺寸为 600 × 400，世界尺寸为 40000 × 400，最多支持 8 名玩家。

## 目录

- `engine-c/`：C++ 引擎、CMake 构建、Python 绑定与测试。
- `web/`：网页前端，待实现。
- `traing/`：Python 训练代码，待实现。

构建与调用方法见 [引擎说明](engine-c/README.md)。
WebSocket 服务器、网页前端和强化学习模型尚未实现。

构建产物、虚拟环境、前端依赖和训练输出由 `.gitignore` 排除。
