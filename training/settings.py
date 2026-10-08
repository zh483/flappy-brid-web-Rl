"""训练配置的读取、校验与实验目录定位。"""

import json
import math
from pathlib import Path

from .env import EnvConfig, OBSERVATION_VERSION

DEFAULT_CONFIG = Path(__file__).with_name("config.json")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def find_run(model_path):
    """支持 final.zip、best/best_model.zip 和 checkpoints/*.zip。"""
    model_path = Path(model_path).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"模型不存在：{model_path}")
    for parent in (model_path.parent, model_path.parent.parent):
        if (parent / "config.json").is_file() and (parent / "manifest.json").is_file():
            return parent
    raise FileNotFoundError("模型旁缺少本次实验的 config.json / manifest.json，请保留整个实验目录")


def validate_config(config):
    if set(config) != {"env", "ppo", "run"}:
        raise ValueError("配置顶层必须是 env、ppo、run")
    EnvConfig(**config["env"])
    reference = read_json(DEFAULT_CONFIG)
    for section in ("ppo", "run"):
        if set(config[section]) != set(reference[section]):
            raise ValueError(f"{section} 的字段应与 training/config.json 一致")
    run, ppo = config["run"], config["ppo"]
    for key in ("total_timesteps", "n_envs", "torch_threads", "eval_episodes"):
        if type(run[key]) is not int or run[key] < 1:
            raise ValueError(f"run.{key} 必须是正整数")
    for key in ("eval_freq", "checkpoint_freq", "seed"):
        if type(run[key]) is not int or run[key] < 0:
            raise ValueError(f"run.{key} 必须是非负整数；频率为 0 表示关闭")
    if run["seed"] + run["n_envs"] + 10000 >= 2**32:
        raise ValueError("seed 太大")
    for key in ("n_steps", "batch_size", "n_epochs"):
        if type(ppo[key]) is not int or ppo[key] < (1 if key == "n_epochs" else 2):
            raise ValueError(f"ppo.{key} 太小或不是整数")
    rollout = ppo["n_steps"] * run["n_envs"]
    if ppo["batch_size"] > rollout or rollout % ppo["batch_size"]:
        raise ValueError("n_steps × n_envs 必须能被 batch_size 整除")
    for key in ("learning_rate", "gamma", "gae_lambda", "clip_range", "ent_coef",
                "vf_coef", "max_grad_norm", "target_kl"):
        value = ppo[key]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"ppo.{key} 必须是有限非负数")
    if not 0 < ppo["gamma"] <= 1 or not 0 <= ppo["gae_lambda"] <= 1:
        raise ValueError("gamma 应在 (0, 1]，gae_lambda 应在 [0, 1]")
    if min(ppo["learning_rate"], ppo["clip_range"], ppo["max_grad_norm"], ppo["target_kl"]) <= 0:
        raise ValueError("learning_rate / clip_range / max_grad_norm / target_kl 必须大于 0")
    if set(ppo["policy_kwargs"]) != {"net_arch"} or not ppo["policy_kwargs"]["net_arch"]:
        raise ValueError("policy_kwargs 目前只支持非空 net_arch 列表")
    if any(type(size) is not int or size < 1 for size in ppo["policy_kwargs"]["net_arch"]):
        raise ValueError("net_arch 中的每一层宽度必须是正整数")


def check_observation(manifest):
    if manifest.get("observation_version") != OBSERVATION_VERSION:
        raise ValueError("模型使用的观测版本与当前代码不一致，不能直接恢复")
