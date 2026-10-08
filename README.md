# flappy-bird-web-Rl

Flappy Bird 联机项目：C++ 游戏引擎、Crow WebSocket 服务器和网页前端，
以及供 Python 强化学习训练使用的 pybind11 接口。

当前已经实现固定步长更新、共享管道、碰撞、复活、无敌、终点判定和状态快照。
摄像头尺寸为 600 × 400，世界尺寸为 40000 × 400，最多支持 8 名玩家。

## 开发分工

这是 zh483 通过分块练习逐步完成的项目，开发过程中使用 Codex 辅助讲解、检查和实现部分模块。

- **游戏引擎核心逻辑**：由 **zh483 全程「古法 coding」手写实现**，包括小鸟、管道、对象池、游戏更新、碰撞、复活和终点判定。
- **服务器业务逻辑**：由 **zh483 编写**，包括连接管理和游戏消息处理。
- **服务器端的线程同步与互斥锁**：由 **Codex 实现**。
- **服务器输入校验加固**：由 **Codex 实现**，即 `saver/main.cpp` 中 `read_integer()` 的整数类型与溢出检查。
- **网页前端**：由 **Codex 实现**，包括页面样式、WebSocket 客户端、Canvas 绘图和交互。
- **工程辅助**：Codex 协助完成 CMake 配置、pybind11 绑定、测试、代码检查与参数调整。
- **Python 强化学习训练**：Codex 实现 Gymnasium 环境封装，以及调用 Stable-Baselines3 PPO 的训练、评估、保存和续训流程。

## 目录

- `engine-c/`：C++ 引擎、CMake 构建、Python 绑定与测试。
- `saver/`：单局 WebSocket 服务器、消息协议与联机测试。
- `web/`：原生 HTML/CSS/JavaScript 网页前端，Canvas 绘图。
- `training/`：Gymnasium 环境、Stable-Baselines3 PPO 训练、评估与续训。

构建与调用方法见 [引擎说明](engine-c/README.md)、[服务器说明](saver/README.md)、[网页说明](web/README.md) 和 [训练说明](training/README.md)。
服务器已实现玩家连接管理、皮肤选择、固定步长更新和状态广播。
网页已支持连接、选皮肤、开局、跳跃、多人状态、复活提示和终点进度。Python 已支持 PPO 训练流程，模型效果仍需正式训练与评估。

构建产物、虚拟环境、前端依赖和训练输出由 `.gitignore` 排除。

各文件的手写与生成分工见 [开发分工说明](DEVELOPMENT.md)。

## 下载试玩版本

预编译文件在 [GitHub Releases](https://github.com/zh483/flappy-brid-web-Rl/releases) 下载，源码也可以按上面的说明自行编译。

- **Windows x64 游戏包**：包含服务器程序、网页和 UTF-8 启动脚本。解压后运行 `start-server.cmd` 和 `start-web.cmd`，浏览器打开 `http://localhost:8000`。网页服务需要安装 Node.js，服务器需要 Microsoft Visual C++ x64 运行库。
- **Python 训练接口包**：适用于 Windows x64、CPython 3.13，包含 `flappy_engine` 模块与调用示例。Linux、其他 Python 版本需要从源码重新编译。此版本尚未包含训练算法或模型。
- **C++ 引擎 SDK**：包含 MSVC x64 Release 静态库与公共头文件，需使用兼容的编译器和运行库链接。

每个发布包包含使用说明和相关第三方许可证；`SHA256SUMS.txt` 可用于校验下载文件。
当前是用于学习与联机试玩的单局版本，游戏服务器默认端口为 18080，网页端口为 8000。
