"""Prepare versioned release archives from the current tested build."""
import argparse
import re
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--version", required=True, help="Release tag, e.g. v0.2.0")
parser.add_argument("--output", type=Path, help="New release workspace (must not already exist)")
parser.add_argument("--server-build", type=Path, default=ROOT / "saver/build/Release")
parser.add_argument("--engine-build", type=Path, default=ROOT / "engine-c/build-training")
parser.add_argument("--pybind-license", type=Path, required=True)
args = parser.parse_args()
VERSION = args.version
if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", VERSION):
    parser.error("version must have the form v1.2.3")
WORK = (args.output or ROOT / "build" / ("release-" + VERSION)).resolve()
WORK.mkdir(parents=True, exist_ok=False)
OUT = WORK / "assets"
OUT.mkdir()
SERVER = args.server_build.resolve()
ENGINE = args.engine_build.resolve()
COMMIT = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
metadata = json.dumps({"version": VERSION, "source_commit": COMMIT,
                       "platform": "windows-x64", "configuration": "Release",
                       "compiler": "MSVC 14.44", "runtime": "MSVC dynamic (/MD)",
                       "python_module": "CPython 3.13 x64 (standard GIL build)"}, indent=2) + "\n"

credits = """开发分工
游戏引擎核心：zh483 全程古法 coding 手写。
服务器业务逻辑：zh483。
服务器线程同步、互斥锁与网页前端：Codex。
Gymnasium/PPO 训练封装、ONNX 导出与机器人接入：Codex。
工程构建、Python 绑定、测试和部分检查调整：Codex 协助。
仓库：https://github.com/zh483/flappy-brid-web-Rl
"""

def archive(name, source_files, extra_files):
    path = OUT / (name + ".zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for target, source in source_files.items():
            bundle.write(source, name + "/" + target)
        for target, content in {"BUILD_INFO.json": metadata, "CREDITS.txt": credits, **extra_files}.items():
            bundle.writestr(name + "/" + target, content.encode("utf-8"))
    with zipfile.ZipFile(path) as bundle:
        assert bundle.testzip() is None
    print(f"Packaged {path.name}: {path.stat().st_size} bytes")

game_files = {"flappy_server.exe": SERVER / "flappy_server.exe"}
for relative in ("onnxruntime.dll", "models/ppo-bird.onnx", "models/ppo-bird.json",
                 "licenses/onnxruntime/LICENSE", "licenses/onnxruntime/ThirdPartyNotices.txt"):
    game_files[relative] = SERVER / relative
model_info = json.loads(game_files["models/ppo-bird.json"].read_text(encoding="utf-8"))
assert sha256(game_files["models/ppo-bird.onnx"].read_bytes()).hexdigest() == model_info["onnx_sha256"]
assert game_files["models/ppo-bird.onnx"].read_bytes() == (ROOT / "saver/models/ppo-bird.onnx").read_bytes()
assert game_files["models/ppo-bird.json"].read_bytes() == (ROOT / "saver/models/ppo-bird.json").read_bytes()
for file in (ROOT / "web").rglob("*"):
    if file.is_file() and (file.parent == ROOT / "web" and file.name in {
            "index.html", "styles.css", "favicon.svg", "dev-server.js", "package.json"}
            or file.parent == ROOT / "web/js"):
        game_files[file.relative_to(ROOT).as_posix()] = file
game_files["licenses/Crow-LICENSE.txt"] = ROOT / "saver/third_party/crow/LICENSE"
game_files["licenses/Asio-LICENSE.txt"] = ROOT / "saver/third_party/asio/LICENSE_1_0.txt"

archive(f"flappy-bird-{VERSION}-windows-x64", game_files, {
    "README.txt": f"""Flappy Bird {VERSION} — Windows x64 联机试玩包

要求：Windows x64、Node.js、Microsoft Visual C++ x64 运行库。
Node.js：https://nodejs.org/
VC++ 运行库：https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist

1. 将整个压缩包解压到一个目录，不要在压缩包内直接启动。
2. 双击 start-server.cmd 启动游戏服务器，保留窗口。
3. 双击 start-web.cmd 启动网页服务，保留窗口。
4. 浏览器打开 http://localhost:8000 ，点击连接服务器。
5. 连接后选择 0–7 只 PPO 机器人，再开始游戏。真人和 AI 合计最多 8 只鸟。
6. 多人测试时，所有标签页先连接，再由一人开始游戏。建议初始速度先选 1。

AI 在 CPU 上推理，已包含模型与 ONNX Runtime，无需 Python、CUDA 或 GPU。
请保留 onnxruntime.dll、models/ 和 licenses/ 与服务器的相对位置。
模型不匹配或缺失会禁用机器人，仍可纯真人游玩；配置 --bots 时会拒绝无效模型启动。

跳跃：空格、W、向上箭头、点击游戏画面，或“跳一下”按钮。
停止：在各自窗口按 Ctrl+C。再次启动前请确认旧进程已退出。
默认游戏端口 18080，网页端口 8000。可在终端运行 flappy_server.exe 18081 更改游戏端口。
网页端口可通过 PORT 环境变量修改，服务器地址可在网页内填写。
同一局域网的其他设备访问 http://服务器电脑IP:8000，
并连接 ws://服务器电脑IP:18080/ws。需要电脑防火墙允许对应连接。
游戏开始后不能加入；所有玩家离开后会清空当前局。

本版本是学习与联机试玩项目，尚未包含多房间、断线恢复或 TLS 公网部署。
机器人使用云端 PPO 最佳模型。已验证的关卡和初始速度不能保证在所有设置下通关。
服务器保留原有规则：任意一只鸟抵达终点即结束整局。
训练源码、参数和接入记录见仓库 training/ 与 saver/BOTS.md。
如果缺少 VCRUNTIME140.dll、VCRUNTIME140_1.dll 或 MSVCP140.dll，请安装微软官方 x64 运行库。
网页无法访问时，检查 start-web.cmd 窗口；无法连接游戏时，检查 start-server.cmd 窗口。
""",
    "start-server.cmd": '@echo off\r\nchcp 65001 >nul\r\ncd /d "%~dp0"\r\nflappy_server.exe %*\r\npause\r\n',
    "start-web.cmd": '@echo off\r\nchcp 65001 >nul\r\ncd /d "%~dp0"\r\nwhere node >nul 2>&1\r\nif errorlevel 1 (\r\n  echo Node.js is required. Install it from https://nodejs.org/ and reopen this window.\r\n  pause\r\n  exit /b 1\r\n)\r\nnode web\\dev-server.js\r\npause\r\n',
})

python_files = {
    "flappy_engine.cp313-win_amd64.pyd": ENGINE / "python/flappy_engine.cp313-win_amd64.pyd",
    "example.py": ROOT / "engine-c/examples/python_example.py",
    "licenses/pybind11-LICENSE.txt": args.pybind_license.resolve(),
}
archive(f"flappy-engine-{VERSION}-cp313-windows-x64", python_files, {
    "README.txt": f"""Flappy Bird Python 训练接口 {VERSION}

要求：Windows x64、标准 CPython 3.13 x64、Microsoft Visual C++ x64 运行库。
这个 .pyd 不支持 Linux、其他 Python 次版本或 Python free-threaded 解释器。
其他平台请从仓库源码用 CMake 和 pybind11 重新编译。

解压后在本目录打开终端：
    python example.py

在自己的脚本中使用时，将本目录加入 sys.path，然后：
    import flappy_engine as engine
    engine.begin(engine.GameSet(size=1, speed=1, characters=[0] * 8))
    engine.step([False] * 8)
    state = engine.get_state()
    print(state.birds[0].position.x, state.birds[0].position.y)
    engine.clear()

actions 始终是 8 个 bool；鸟槽位由 present 判断是否有人。
step 推进固定虚拟时间，不需要 sleep，也不需要启动网页或游戏服务器。
同一进程共享一个静态引擎；多环境并行训练应使用独立进程。
快照中的 velocity 单位为每步位移，除以 config.v_fps 可得到像素/秒。
example.py 是简单调用演示。本包只提供引擎绑定；奖励函数、PPO 算法封装和云端脚本见源码 training/。
完整 API 说明：https://github.com/zh483/flappy-brid-web-Rl/tree/main/engine-c
""",
})

sdk_files = {"lib/flappy_core.lib": ENGINE / "Release/flappy_core.lib"}
for file in (ROOT / "engine-c").rglob("*.hpp"):
    if file.parent == ROOT / "engine-c" or file.parent.name in ("engines", "objective"):
        sdk_files["include/" + file.relative_to(ROOT / "engine-c").as_posix()] = file
archive(f"flappy-engine-sdk-{VERSION}-msvc-x64", sdk_files, {
    "README.txt": f"""Flappy Bird C++ Engine SDK {VERSION}

Windows x64，MSVC 14.44，Release，动态 CRT (/MD)，C++17。
include/ 包含公共头文件，lib/flappy_core.lib 是静态库。
使用兼容的 MSVC x64 工具链与 /MD 运行库链接；MinGW、Linux 或其他架构应从源码重新编译。
引擎不依赖 Crow、Asio、Node.js 或 Python；静态库自身没有可执行入口。

CMake 接入示例：
    target_include_directories(your_target PRIVATE path/to/sdk/include)
    target_link_libraries(your_target PRIVATE path/to/sdk/lib/flappy_core.lib)
    target_compile_features(your_target PRIVATE cxx_std_17)

程序包含 engines/cengine.hpp，使用 engine::begin、step、get_state、clear。
同一进程共享一局游戏；从多个线程访问时需要调用方进行同步。
源码及说明：https://github.com/zh483/flappy-brid-web-Rl/tree/main/engine-c
""",
    "example.cpp": """#include <iostream>
#include "engines/cengine.hpp"
int main() {
    engine::begin(game_set{1, 1, {}}, 42);
    engine::step({false, false, false, false, false, false, false, false});
    const auto state = engine::get_state();
    std::cout << state.birds[0].position.x << ", " << state.birds[0].position.y << '\\n';
    engine::clear();
}
""",
})

checksums = "".join(sha256(file.read_bytes()).hexdigest() + "  " + file.name + "\n"
                    for file in sorted(OUT.glob("*.zip")))
(OUT / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")

(WORK / "notes.md").write_text(f"""PPO 机器人联机版本。Windows 游戏包已包含训练后的模型与 CPU 推理库，试玩无需 Python 或 GPU。

### 本次更新
- 网页可选 0–7 只 PPO 机器人；真人与 AI 合计最多 8 只鸟。
- C++ 服务器通过 ONNX Runtime 在 CPU 推理，每只机器人读取自己的观测；网页标记 AI。
- 校验模型与引擎参数，处理人数上限、断线清理、机器人禁用和开局同步。
- 新增 Gymnasium 环境、Stable-Baselines3 PPO 训练、评估、续训、云端脚本及 ONNX 导出。
- 同步更新 Python 绑定、C++ SDK 和解压后的发布包验证。

### 下载与启动
- `flappy-bird-{VERSION}-windows-x64.zip`：游戏包，包含服务器、网页、模型、推理库和 UTF-8 启动脚本。需要 Node.js 与 Microsoft Visual C++ x64 运行库。
- `flappy-engine-{VERSION}-cp313-windows-x64.zip`：Windows x64 / 标准 CPython 3.13 引擎绑定与示例；训练流程见源码 `training/`。
- `flappy-engine-sdk-{VERSION}-msvc-x64.zip`：MSVC 14.44 x64 Release、/MD 静态库、公共头文件与示例。
- `SHA256SUMS.txt`：以上压缩包的 SHA-256 校验值。源码压缩包由 GitHub 提供；Linux 和其他 Python 版本请自行编译。

完整解压游戏包后，分别运行 `start-server.cmd` 和 `start-web.cmd`，打开 http://localhost:8000 。连接后选择机器人数量，再开始游戏；建议初始速度先选 1。多人游戏先让所有真人连接。默认游戏端口 18080、网页端口 8000。

### 验证与范围
已验证单机器人、多机器人及真人混合游玩；发布前验证解压后的 WebSocket/机器人测试、网页资源、Python 导入与 SDK 编译链接，并校验所有压缩包。发布包来自提交 `{COMMIT}`，包含 BUILD_INFO 与第三方许可证。
这是学习和联机试玩的单局版本，尚不支持多房间、断线恢复或公网 TLS。模型在验证关卡上的表现不代表所有设置均能通关。保留原引擎规则：任意一只鸟到终点即结束整局。

### 开发分工
引擎核心由 **zh483 全程「古法 coding」手写**；服务器业务逻辑由 zh483 编写；**服务器线程同步、互斥锁与网页前端由 Codex 完成**。Codex 也协助构建、绑定、测试、Gymnasium/PPO 训练封装、模型导出和机器人接入。PPO 算法使用 Stable-Baselines3。
""", encoding="utf-8")
print(f"Release workspace: {WORK}")
