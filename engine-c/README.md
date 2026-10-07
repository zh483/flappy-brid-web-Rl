# C++ 引擎与 Python 绑定

构建会生成两个目标：

- `flappy_core`：C++ 引擎静态库，未来服务器可链接 `flappy::core`。
- `flappy_engine`：Python 扩展模块，Windows 下为 `.pyd`，Linux 下为 `.so`。

主 `CMakeLists.txt` 负责引擎静态库，通过 `add_subdirectory(bindings)` 引入
`bindings/CMakeLists.txt`。Python、pybind11 的查找、模块生成和 Python 测试注册
都在子目录中完成；关闭 `FLAPPY_BUILD_PYTHON` 就不会进入该目录。

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

### Python 测试如何找到引擎

`bindings/CMakeLists.txt` 的 `target_link_libraries(flappy_engine PRIVATE flappy::core)`
把 C++ 引擎链接到 Python 扩展模块中。Python 导入的是编译后的 `.pyd` / `.so`，
不是直接读取 `.cpp` 文件，也不是直接导入静态库。

`add_test()` 注册一条供 CTest 执行的命令，并把 `$<TARGET_FILE_DIR:flappy_engine>`
作为参数传给测试脚本。这个表达式会被 CMake 替换为模块实际输出目录。
本机执行的命令等价于：

```powershell
D:/Anaconda3/python.exe engine-c/tests/test_python_bindings.py engine-c/build/python
```

测试脚本中的 `sys.path.insert(0, sys.argv.pop(1))` 取出这个目录并放到 Python
模块搜索路径的最前面，随后 `import flappy_engine as engine` 就能找到扩展模块。
`pop(1)` 也移除了这个参数，避免 `unittest` 把目录误当成测试名称。
`add_test()` 只注册测试，不会自动编译，所以应先构建，再运行 `ctest`。

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

水平速度上限由 `config::max_horizontal_speed` 控制，单位是像素/秒，当前为 120。
引擎把它乘以 `v_fps` 得到每步位移上限；即使初始难度很高也不能超过这个速度。
`min_v` 仍为每步基础位移，`game_speed` 是难度倍率，不代表实际每秒速度。
当前管道间可用水平距离为 `p_n_x - p_x - b_x = 125`，以最高速度通过约需 1.04 秒。
这个时间是管道之间的调整窗口，不能保证所有高度变化都容易通过；继续根据试玩调整。
若修改管道间距或尺寸，也需要重新评估速度上限。

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
