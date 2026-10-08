# 开发分工说明

本文件记录项目中各文件的来源分工，用于说明哪些逻辑由 zh483「古法 coding」手写、
哪些属于 Codex/工程辅助生成的脚手架与工具链。

## 关于本文件的来源

本文件由 Codex 在审阅代码后生成，不是原始开发记录。它依据四类证据：

1. 代码风格标记：拼写、命名习惯、空格与缩进、注释口气；
2. Git 历史：两次提交的 diff，可以看到改动是功能性重写还是机械改名；
3. 文件时间戳：手写代码通常是长时间分次修改，生成代码往往同批出现；
4. 仓库自述：`README.md`、`saver/README.md`、`saver/main.cpp` 的注释。

因此下面的判断是**交叉推断，不是来源证明**。Git 中只有 `zh483` 一个作者、
没有 AI 署名或 trailer，无法逐行证明归属。若某条与你的实际记忆不符，以你的记忆为准，
直接改本文件即可。

## 总览

| 层 | 归属 |
| --- | --- |
| 引擎核心逻辑（鸟、管道、对象池、游戏更新、碰撞、复活、终点） | zh483 |
| 服务器业务逻辑（连接管理、消息处理、状态组装与广播） | zh483 |
| 物理与关卡参数取值（试玩后调出来的数值） | zh483 |
| 服务器端的线程同步与互斥锁 | Codex |
| 服务器输入校验加固（JSON 数值字段解析） | Codex |
| 网页前端（页面、样式、WebSocket 客户端、Canvas 绘图、交互） | Codex |
| 构建、绑定、测试、文档、打包 | Codex |
| 强化学习训练代码（Gymnasium 环境、PPO 训练与评估） | Codex |

## 文件级清单

### engine-c/

| 文件 | 归属 | 说明 |
| --- | --- | --- |
| `objective/ve2.hpp` | zh483 | 6 行的 `Vec2` 结构体 |
| `objective/birds.hpp` | zh483 | 鸟对象与鸟池声明，保留 `//只通过 鸟_pool 创造`、`//构造器 好像不用` 等草稿注释 |
| `objective/birds.cpp` | zh483 | 构造函数、`fly()`、`on_join_in()`、`on_leave()`。变量名 `_satuation` 是 situation 的拼写错误 |
| `objective/pipe.hpp` | zh483 | 管道与管道池声明，含被注释掉的 `//void move();` |
| `objective/pipe.cpp` | zh483 | `react()`、`acquire()`、`release()`，含 `//不搞log n那一套了` |
| `engines/cengine.hpp` | zh483 | `game_phase`、`game_set`、`game_state`、`engine` 接口 |
| `engines/cengine.cpp` | zh483 为主 | `begin()`、`clear()`、`generate_pipes()`、`recycle_pipes()`、`check_collisions()`、`update_respawn()`、`step()`、`check_finish()`、`get_state()` 的骨架 |
| `config.hpp` / `config.cpp` | zh483 | 配置字段与取值；`max_horizontal_speed = 120` 的注释（125 像素可用距离、约 1 秒调整窗口）来自试玩调参 |
| `bindings/python_bindings.cpp` | Codex | 全部 pybind11 绑定 |
| `bindings/CMakeLists.txt` | Codex | pybind11 查找、下载、模块输出目录、测试注册 |
| `CMakeLists.txt` | Codex | `flappy_core` 静态库、编译选项、CTest |
| `tests/test_python_bindings.py` | Codex | 6 条单元测试 |
| `examples/python_example.py` | Codex | 演示控制器 |
| `README.md` | Codex | 构建、调用与接线说明 |
| `.gitignore` | Codex | 2 行 |

`cengine.cpp` 中少数后加的分支属于辅助工具：

- `begin()` 的 `failed_ids` 错误返回与池满分支：为服务器区分「开不起来」而加；
- `bird::fly()` 的 `max_vertical_speed` / `max_horizontal_speed` 限速块：为「极高难度不能绕过速度上限」而加；
- `engine::on_leave()`：为服务器断线清理而加。

### saver/

| 文件 / 位置 | 归属 | 说明 |
| --- | --- | --- |
| `main.cpp:18-33` `client_info` / `server_state` | zh483 | 连接管理数据结构，`client_numb`、`pending_jump` 等命名 |
| `main.cpp:35-101` `send_error()`、`reset_game_clock()`、`handle_accept()`、`handle_open()`、`handle_close()` | zh483 | 人数上限、编号复用、最后一人离开才清空本局 |
| `main.cpp:104-131` `read_integer()` | Codex | `from_chars` 全量解析、整数类型检查、范围检查 |
| `main.cpp:134-144` `read_string()` | zh483 | 原型版本，只检查字段存在与类型 |
| `main.cpp:146-241` 三个 `handle_*` 与 `handle_jump()` | zh483 | 消息业务逻辑；`handle_client_error()` 是典型手写痕迹 |
| `main.cpp:244-283` `handle_message()` | zh483（Codex 补异常包裹） | 解析公共字段后按类型分发 |
| `main.cpp:285-347` `pipes_to_json()`、`birds_to_json()`、`broadcast_state()` | zh483 | 状态快照组装，含公共/个人字段拆分 |
| `main.cpp:349-392` `update_server()` | 混写 | 定步长累积逻辑与注释偏辅助风格；`//服务器每次更新` 一行像手写残留 |
| `main.cpp:394-441` `main()` 与路由注册 | Codex | 端口解析、`std::mutex`、五个回调统一加锁、`app.tick(5ms)` |
| `CMakeLists.txt`、`cmake/Dependencies.cmake`、`third_party/dependencies.json` | Codex | 依赖固定版本、SHA-256 校验、自动下载 |
| `tests/test_server.py` | Codex | 端到端 WebSocket 测试 |
| `README.md` | Codex | 协议与部署说明 |

### web/

整个目录由 Codex 生成，包括 `index.html`、`styles.css`、`js/config.js`、
`js/network.js`、`js/protocol.js`、`js/renderer.js`、`js/app.js`、
`tests/protocol.test.js`、`dev-server.js`、`package.json`、`README.md`、`favicon.svg`。

其中 `js/config.js` 的尺寸常量和皮肤颜色是从 `engine-c/config.cpp` 读取后写死的，
修改引擎尺寸时需要同步更新，这一点已写入 `web/README.md`。

### training/

整个目录由 Codex 生成：`env.py`（Gymnasium 环境）、`settings.py`（配置校验与实验目录）、
`engine_loader.py`（定位已编译的 `flappy_engine`）、`build_engine.py`、
`train.py`、`evaluate.py`、`config.json`、`requirements.txt`、
`tests/test_environment.py` 与 `README.md`。

该目录在 10-07 22:39-22:43 一次性出现，是 `traing/` 占位目录的落地版本。
奖励函数、观测定义和 episode 终止规则属于新增设计，引擎本身未改动。

### 根目录

| 文件 | 归属 |
| --- | --- |
| `README.md`（目录、构建、下载、分工） | Codex |
| `DEVELOPMENT.md`（本文件） | Codex |
| `.gitignore` | Codex |

## 判断依据

### 手写部分的标记

- 拼写与缩写：`_satuation`、`brids`（首次提交时 `brids_pool`、`objective/brids.hpp` 都拼错了）、`mx_b_x`、`b_is`、`otp`、`pp`、`client_numb`；
- 口语注释：`//鸟自己动`、`//不搞log n那一套了`、`//只通过 鸟_pool 创造`、`//构造器 好像不用`、`//此处写错误日志 TODO`、`//数值到时候调`、`//直接扫一遍`；
- 排版随手：`#include"birds.hpp"` 无空格、`for(int i=0;i<8;i++){//遍历鸟`、成员缩进错位、文件结尾缺换行；
- 留白与取舍：`//void move(); //管道不动`、`//是否保留自动复活规则`、`//TODO: 确定皮肤数量后，在这里检查皮肤编号的上限`。

### 生成部分的标记

- 英文注释与解释性中文注释成段出现：`// Keep the GIL: ...`、`// Prefer project-local sources, then an installed package, then download.`、`// 这里只负责解析公共字段、识别消息类型，再分发给对应函数。`；
- 参数文档化：`py::arg("seed") = 0` 后跟说明字符串、`add_test(...)` + `set_tests_properties(... TIMEOUT 45)`；
- 全站一致的基础设施：五个 WebSocket 回调统一 `std::lock_guard`、`/W4`、`/utf-8`、`FetchContent` 固定版本、SHA-256 清单；
- 教程式写法：`web/README.md` 给出「按这个顺序阅读」，并建议先改背景色再改字段。

### Git 历史

- `5a20efd`（初始化）：第一次提交里 `begin()` 是 `void`、全程写作 `brids_pool`，并且自带 `//写错误日志`、`//此处写错误日志 TODO`、`//数值到时候调`；
- `560bace`（服务器与网页）：`brids` → `bird` 全局改名、`max_horizontal_speed` 限速、`p_n_x` 提取、`begin()` 改为返回鸟编号数组。

机械改名与「为服务器而加」的返回值是一类改动，参数取值调整是另一类改动。

## 附：时间戳

文件修改时间只能说明「什么时候被写入磁盘」，不能证明作者，仅供对照。
本机记录的若干节点（UTC+8）：

| 时间 | 事件 |
| --- | --- |
| 10-05 17:50-17:55 | 引擎核心文件建立 |
| 10-05 23:25 | `config.cpp` 建立 |
| 10-06 23:18 | Python 绑定、测试、示例、`.gitignore` 同批出现 |
| 10-06 23:55-23:58 | 依赖清单与 `Dependencies.cmake` |
| 10-07 14:15 | `CMakeLists.txt`、`bindings/CMakeLists.txt` 整理 |
| 10-07 15:22 | `saver/main.cpp` 建立 |
| 10-07 20:25-20:33 | 网页前端整批出现 |
| 10-07 20:47-21:00 | 引擎核心最后调整（限速、参数） |
| 10-07 21:18 | 提交 `560bace` |
| 10-07 21:27 | 服务器构建并通过 `ctest` |
| 10-07 22:39-22:43 | `training/` 整批出现，`README.md` 同步更新 |

同一批出现的文件（秒级接近）更像一次生成；跨小时反复改动的文件更像手写迭代。
