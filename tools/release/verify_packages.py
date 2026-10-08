import argparse
import zipfile
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description="Extract and verify a new Windows release workspace")
parser.add_argument("--version", required=True)
parser.add_argument("--workspace", type=Path, required=True)
parser.add_argument("--node", required=True, help="Node.js executable")
parser.add_argument("--cmake", required=True, help="CMake executable")
args = parser.parse_args()
WORK = args.workspace.resolve()
BASE = WORK / "unpacked"
BASE.mkdir(exist_ok=False)
assets = WORK / "assets"
for line in (assets / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
    digest, name = line.split("  ", 1)
    assert Path(name).name == name
    archive = assets / name
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == digest
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        for member in bundle.namelist():
            target = (BASE / member).resolve()
            assert target.is_relative_to(BASE)
        bundle.extractall(BASE)
print("All release archive checksums verified before extraction", flush=True)
game = BASE / f"flappy-bird-{args.version}-windows-x64"
python = BASE / f"flappy-engine-{args.version}-cp313-windows-x64"
sdk = BASE / f"flappy-engine-sdk-{args.version}-msvc-x64"
env = {key.upper(): value for key, value in os.environ.items()}
TEMP = WORK / "tmp"
TEMP.mkdir(exist_ok=True)
env.update(TEMP=str(TEMP), TMP=str(TEMP))
for package in (game, python, sdk):
    info = json.loads((package / "BUILD_INFO.json").read_text(encoding="utf-8"))
    assert info["version"] == args.version
    assert info["source_commit"] == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

subprocess.run([sys.executable, str(ROOT / "saver/tests/test_server.py"),
                str(game / "flappy_server.exe")], cwd=game, env=env, check=True)
subprocess.run([sys.executable, str(ROOT / "saver/tests/test_bot_server.py"),
                str(game / "flappy_server.exe")], cwd=game, env=env, check=True)
subprocess.run([sys.executable, "example.py"], cwd=python, env=env, check=True)
subprocess.run([sys.executable, "-c", "import flappy_engine as e; assert e.config.force == 9.8; assert e.config.max_horizontal_speed == 120; assert e.config.max_vertical_speed == 120; print('Packaged Python import and configuration OK')"],
               cwd=python, env=env, check=True)

with socket.socket() as reservation:
    reservation.bind(("127.0.0.1", 0))
    port = reservation.getsockname()[1]
web_env = dict(env, PORT=str(port))
with tempfile.TemporaryFile() as web_log:
    process = subprocess.Popen([args.node, "web/dev-server.js"], cwd=game,
                               env=web_env, stdout=web_log, stderr=web_log,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 8
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                    assert response.status == 200
                    page = response.read().decode("utf-8")
                    assert "一起向前" in page and 'id="bot-count"' in page
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise
                time.sleep(.1)
        for path in ("styles.css", "favicon.svg", "js/app.js", "js/network.js", "js/config.js", "js/protocol.js", "js/renderer.js"):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/{path}", timeout=2) as response:
                assert response.status == 200 and response.read()
        print("Packaged webpage and all modules return HTTP 200")
    finally:
        process.terminate()
        process.wait(timeout=5)

project = WORK / "verify-sdk"
project.mkdir(exist_ok=True)
(project / "CMakeLists.txt").write_text(f'''cmake_minimum_required(VERSION 3.24)
project(ReleaseSDKSmoke LANGUAGES CXX)
add_executable(sdk_smoke "{sdk.as_posix()}/example.cpp")
target_include_directories(sdk_smoke PRIVATE "{sdk.as_posix()}/include")
target_link_libraries(sdk_smoke PRIVATE "{sdk.as_posix()}/lib/flappy_core.lib")
target_compile_features(sdk_smoke PRIVATE cxx_std_17)
target_compile_options(sdk_smoke PRIVATE /utf-8)
''', encoding="utf-8")
cmake = args.cmake
subprocess.run([cmake, "-S", str(project), "-B", str(project / "build"), "-G", "Visual Studio 17 2022", "-A", "x64"], env=env, check=True)
subprocess.run([cmake, "--build", str(project / "build"), "--config", "Release", "--parallel", "1", "--", "/nodeReuse:false"], env=env, check=True)
subprocess.run([str(project / "build/Release/sdk_smoke.exe")], env=env, check=True)
print("Packaged SDK headers and library compile, link and run")

assets = WORK / "assets"
for line in (assets / "SHA256SUMS.txt").read_text().splitlines():
    digest, name = line.split("  ", 1)
    assert hashlib.sha256((assets / name).read_bytes()).hexdigest() == digest
print("All release archive checksums verified")
