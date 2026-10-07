# 服务器目录

`main.cpp` 已实现最多 8 个连接、皮肤选择、开始游戏、跳跃输入、
固定步长更新和状态广播。当前一个服务器进程管理一局游戏。
`CMakeLists.txt` 创建 `flappy_server` 目标，链接 Crow 和引擎。

## 已下载的依赖

- Crow 1.3.4：`third_party/crow/include/crow.h`。
- Asio 1.38.2：`third_party/asio/include/asio.hpp`。

源码来自各项目官方 GitHub 仓库，原始许可证保留在源码目录中。
固定版本、下载地址和 SHA-256 记录在 `third_party/dependencies.json`。
第三方源码目录不提交到 Git；缺少时 CMake 会按清单自动下载并校验。
当前配置用于本机 `ws://` 开发，未启用 SSL 和压缩，因此不需要额外下载
OpenSSL、zlib 或 Boost。

从项目根目录构建（Visual Studio 2022）：

```powershell
cmake -S saver -B saver/build -G "Visual Studio 17 2022" -A x64
cmake --build saver/build --config Release
```

运行（默认端口 18080）：

```powershell
chcp 65001
.\saver\build\Release\flappy_server.exe
```

也可以传入端口，例如 `flappy_server.exe 18081`。
客户端连接 `ws://localhost:18080/ws`。当前没有注册 HTTP 首页，
在地址栏访问 `/` 返回 404 是预期行为。

## 消息协议

所有服务器消息均为 JSON 对象，客户端通过 `JSON.parse(event.data)` 解析。
鸟相关的类、头文件和消息字段统一为 `bird` / `birds`，旧字段不再发送。

客户端发送：

```json
{"type":"select_skin","skin":2}
{"type":"game_begin","speed":1}
{"type":"jump"}
{"type":"client_error","error":"客户端诊断信息"}
```

上述每行是一条独立消息。客户端身份由连接确定，不需要发送编号。
跳跃只记录到待处理数组，下一次固定更新消费一次。
多个跳跃在同一个更新时间间隔内到达时会合并为一次。
当前允许任意已连接玩家开始游戏，运行期间不能加入新玩家、修改皮肤或重开。
皮肤编号目前允许非负整数，实际可用皮肤的上限需与网页资源约定。

服务器发送的消息包括：

```json
{"type":"connected","client_id":0}
{"type":"skin_selected","skin_id":2}
{"type":"game_started","client_id":0,"bird_id":1,"skin_id":2,"speed":1}
{"type":"error","message":"游戏已经开始"}
```

开始游戏后立即发送 `tick=0` 的 `game_state`，以后每次推进后发送最新状态。
公共字段为 `tick`、`phase`、`speed`、`pipes`、`birds`；个人字段为
`client_id`、`bird_id`。`birds` 始终保留 8 个槽位，每项含 `bird_id`、
`present`、`character`、`position_x/y`、`velocity_x/y`、`respawn_ms`、
`invincible_ms`。用 `present` 判断槽位是否有人，不能把空槽位从数组移除。

计时器每隔约 5 毫秒检查时间，实际引擎步长取 `config::v_fps`（当前 1/24 秒）。
用单调时钟累计真实经过时间，每次回调最多补 8 步，剩余时间保留。
网络回调和定时回调通过同一把互斥锁保护共享状态。
一个玩家离开只移除自己的鸟；最后一个连接离开才清空整局。
终点状态广播后停止推进，客户端可以再次发送 `game_begin` 开新一局。

这是用于本机前后端联调的单局服务器；尚未实现多房间、断线恢复、
慢客户端发送队列控制和公网 TLS 部署。

## 验证

找到 Python 3.9+ 时，CMake 会注册只依赖 Python 标准库的端到端测试：

```powershell
ctest --test-dir saver/build -C Release --output-on-failure
```

也可直接运行：

```powershell
python saver/tests/test_server.py saver/build/Release/flappy_server.exe
```

测试在独立端口启动临时服务器，验证人数上限、编号复用、JSON 错误处理、
多人状态和皮肤映射、跳跃、断线清理、新局重置以及极高难度不能绕过速度上限。
终点冻结由引擎的 Python 测试通过正常操作跑完整关卡来验证。

服务器源码可使用：

```cpp
#include <crow.h>
#include "engines/cengine.hpp"
```

## 在其他项目中复用

```cmake
include("E:/my_work/Flappy-Bird/saver/cmake/Dependencies.cmake")
target_link_libraries(your_server PRIVATE Crow::Crow)
```

也可通过 `-DFLAPPY_SERVER_DEPENDENCY_DIR=其他路径` 指定公共依赖目录。
Crow 和 Asio 都通过头文件接入，在各项目中分别编译。

## 现有引擎静态库

- MSVC：`../engine-c/build/Release/flappy_core.lib`。
- MinGW：`../engine-c/build-core/libflappy_core.a`。

静态库没有可执行入口，不是双击启动的程序。服务器构建时链接它。
使用上述 CMake 构建服务器，会用同一编译器重新构建引擎，避免混用
MSVC 的 `.lib` 和 MinGW 的 `.a`。
