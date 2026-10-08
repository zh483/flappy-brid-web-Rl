"""用运行此脚本的 Python 编译绑定，避免 Python 版本/架构不匹配。"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

from .engine_loader import ROOT


def main():
    cmake = shutil.which("cmake")
    # pip 的 Windows 启动器可能受 Conda 的 DLL 搜索路径影响，优先调用实际二进制。
    try:
        import cmake as cmake_package
        bundled = Path(cmake_package.CMAKE_BIN_DIR) / ("cmake.exe" if os.name == "nt" else "cmake")
        if bundled.is_file():
            cmake = str(bundled)
    except ImportError:
        pass
    if not cmake:
        raise SystemExit("找不到 CMake，请先 python -m pip install cmake")
    build = ROOT / "engine-c/build-training"
    command = [cmake, "-S", str(ROOT / "engine-c"), "-B", str(build),
               "-DFLAPPY_BUILD_PYTHON=ON", f"-DPython_EXECUTABLE={sys.executable}",
               "-DCMAKE_BUILD_TYPE=Release"]
    if os.name == "nt" and not (build / "CMakeCache.txt").exists():
        command.extend(["-G", "Visual Studio 17 2022", "-A", "x64"])
    # Windows 环境中 Path/PATH 重复时 MSBuild 可能失败，统一大小写后传给子进程。
    environment = {key.upper(): value for key, value in os.environ.items()} if os.name == "nt" else os.environ.copy()
    # 把编译器临时文件放在本项目的构建目录，避免系统临时目录的权限问题。
    temporary = build / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    environment.update(TEMP=str(temporary), TMP=str(temporary))
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    command = [cmake, "--build", str(build), "--config", "Release", "--parallel", "1"]
    if os.name == "nt":
        command.extend(["--", "/nodeReuse:false"])
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    print(f"Python 模块目录：{build / 'python'}")


if __name__ == "__main__":
    main()
