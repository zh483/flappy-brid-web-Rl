# C++ 引擎与 Python 绑定

构建会生成两个目标：

- `flappy_core`：C++ 引擎静态库，未来服务器可链接 `flappy::core`。
- `flappy_engine`：Python 扩展模块，Windows 下为 `.pyd`，Linux 下为 `.so`。

## 构建

需要 CMake 3.24+、支持 C++17 的编译器，以及 Python 3.9+ 的开发文件。
优先使用 `third_party/pybind11` 中的源码或已安装的 pybind11 3.x。
如果都没有，CMake 会下载固定版本 3.0.4 到 `engine-c/third_party/pybind11`。
下载来源：https://github.com/pybind/pybind11/tree/v3.0.4
构建方式参考：https://pybind11.readthedocs.io/en/stable/compiling.html

在项目根目录执行。以下命令使用当前 `python` 对应的解释器，Windows PowerShell 示例：

```powershell
$enginePython = python -c "import sys; print(sys.executable)"
cmake -S engine-c -B engine-c/build -G "Visual Studio 17 2022" -A x64 "-DPython_EXECUTABLE=$enginePython"
cmake --build engine-c/build --config Release --parallel
ctest --test-dir engine-c/build -C Release --output-on-failure
```

其他平台可省略 `-G "Visual Studio 17 2022" -A x64`，使用当地可用的生成器。
构建时指定的 Python 应与之后导入模块的 Python 版本、架构保持一致。
模块统一输出到 `engine-c/build/python`，不需要复制到系统目录。

只构建 C++ 核心，不查找 Python 或下载 pybind11：

```powershell
cmake -S engine-c -B engine-c/build-core -DFLAPPY_BUILD_PYTHON=OFF
cmake --build engine-c/build-core --config Release --parallel
```

## Python 调用

从项目根目录启动 Python，将模块目录加入搜索路径：

```python
import sys
sys.path.insert(0, "engine-c/build/python")
import flappy_engine as engine

settings = engine.GameSet(size=1, speed=1, characters=[0] * 8)
engine.begin(settings, seed=42)

actions = [False] * 8
actions[0] = True
engine.step(actions)
state = engine.get_state()

print(state.phase, state.speed)
print(state.birds[0].position.x, state.birds[0].position.y)
print([(p.x, p.up, p.down) for p in state.pipes])
engine.clear()
```

`characters`、`actions` 均使用固定的 8 个槽位，即使本局只有一名玩家也如此。
`state.birds[i]` 对应 `actions[i]`；`present=False` 表示该槽位没有玩家。
`respawn_ms > 0` 表示等待复活，`invincible_ms > 0` 表示无敌。
`engine.config` 可读取世界尺寸、鸟和管道尺寸、物理参数、计时参数。
这些是配置数值的副本，在 Python 中修改它们不会改变 C++ 引擎配置。
`engine.config.v_fps` 是每次更新的秒数，当前为 `1/24` 秒。
训练中每调用一次 `step()` 就推进一步，无需真实时间等待。

状态是数据副本。后续 `step()`、`clear()` 不会改变已经取得的状态。
pybind11 的 STL 转换会复制容器，修改 `settings.characters[0]` 不会更新 C++ 设置；
应先修改 Python 列表，再整体赋值给 `settings.characters`。

当前引擎及对象池使用静态成员，同一进程内共享一局游戏。
并行训练应使用独立进程，每个进程各自导入模块、开局。
绑定保留 Python GIL；目前不支持 Python 和其他 C++ 线程同时更新同一局游戏。
本次仅提供训练接口，没有添加奖励函数、Gym 环境或模型推理代码。

演示控制器位于 `examples/python_example.py`。
从项目根目录执行：

```powershell
$env:PYTHONPATH = (Resolve-Path engine-c/build/python).Path
python engine-c/examples/python_example.py
```

## C++ 服务器链接

服务器项目可通过 `add_subdirectory()` 引入本目录：

```cmake
set(FLAPPY_BUILD_PYTHON OFF CACHE BOOL "" FORCE)
add_subdirectory(path/to/engine-c engine-build)
target_link_libraries(your_server PRIVATE flappy::core)
```

服务器代码包含 `engines/cengine.hpp`，继续调用原来的 `engine` 接口即可。
服务器和引擎静态库必须使用同一种编译器、架构及兼容的运行库构建。
例如 MinGW 服务器使用 MinGW 构建的 `libflappy_core.a`，MSVC 服务器使用
MSVC 构建的 `flappy_core.lib`。
