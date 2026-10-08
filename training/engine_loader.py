"""寻找当前 Python 对应的 C++ 模块；不依赖用户手动设置 PYTHONPATH。"""

import importlib
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG_KEYS = (
    "camera_width", "camera_height", "world_width", "world_height", "max_p",
    "v_fps", "g", "force", "min_v", "max_horizontal_speed", "max_vertical_speed",
    "p_x", "p_s", "p_n_x", "p_df", "b_x", "b_y", "alive_ms", "invin_ms",
)


def load_engine(engine_dir=None):
    explicit = engine_dir or os.environ.get("FLAPPY_ENGINE_DIR")
    candidates = ([Path(explicit).expanduser().resolve()] if explicit else [
        ROOT / "engine-c/build-training/python", ROOT / "engine-c/build/python",
    ])
    selected = next((p for p in candidates if p.is_dir() and any(
        file.name.startswith("flappy_engine") and file.suffix in (".pyd", ".so")
        for file in p.iterdir()
    )), None)
    if selected is None:
        raise ImportError(
            "找不到 flappy_engine。请先使用当前 Python 执行："
            "python -m training.build_engine；或传入 --engine-dir 模块所在目录。"
        )
    loaded = sys.modules.get("flappy_engine")
    if loaded is not None and Path(loaded.__file__).resolve().parent != selected:
        raise RuntimeError("当前进程已加载另一个目录的引擎，请重新启动 Python。")
    if str(selected) not in sys.path:
        sys.path.insert(0, str(selected))
    try:
        engine = importlib.import_module("flappy_engine")
    except ImportError as exc:
        raise ImportError(
            f"无法加载 {selected} 中的引擎。当前 Python {sys.version.split()[0]}；"
            "请用这个 Python 重新执行 python -m training.build_engine。"
        ) from exc
    if not all(hasattr(engine.config, key) for key in CONFIG_KEYS):
        raise ImportError("引擎绑定版本过旧，请执行 python -m training.build_engine。")
    return engine


def engine_config(engine):
    """把真实物理参数随模型保存，避免换了 config 后误以为仍是同一实验。"""
    return {key: getattr(engine.config, key) for key in CONFIG_KEYS}


def check_engine_config(engine, expected):
    current = engine_config(engine)
    changed = [key for key in CONFIG_KEYS if current.get(key) != expected.get(key)]
    if changed:
        raise ValueError(
            "引擎参数与模型训练时不一致：" + ", ".join(changed) +
            "。请恢复原参数并重新编译，或在新参数下开始新实验。"
        )
