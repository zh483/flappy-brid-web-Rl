"""训练入口：python -m training.train。子进程入口必须有 __main__ 保护。"""

import argparse
from datetime import datetime
import importlib.metadata
import multiprocessing as mp
from pathlib import Path
import sys

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback, EvalCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv

from .callbacks import GracefulStop, ignore_worker_interrupts
from .engine_loader import ROOT, check_engine_config, engine_config, load_engine
from .env import FlappyEnv, OBSERVATION_VERSION
from .settings import (DEFAULT_CONFIG, check_observation, find_run, read_json,
                       validate_config, write_json)


def make_env(env_config, engine_dir, monitor_file):
    """返回工厂函数；C++ 引擎在 worker 内加载、创建，父进程不创建游戏。"""
    def create():
        ignore_worker_interrupts()
        return Monitor(FlappyEnv(env_config, engine_dir), filename=monitor_file,
                       info_keywords=("distance", "pipes_passed", "is_success"))
    return create


def parse_args():
    parser = argparse.ArgumentParser(description="使用 C++ 引擎训练 SB3 PPO")
    parser.add_argument("--config", type=Path, help="JSON 配置；续训默认使用原实验配置")
    parser.add_argument("--output", type=Path, help="新实验目录，必须不存在")
    parser.add_argument("--engine-dir", type=Path, help="flappy_engine 模块所在目录")
    parser.add_argument("--resume", type=Path, help="恢复 final.zip / best_model.zip / checkpoint.zip")
    for name in ("timesteps", "n-envs", "n-steps", "batch-size", "seed",
                 "eval-freq", "eval-episodes", "checkpoint-freq", "max-episode-steps"):
        parser.add_argument(f"--{name}", type=int)
    parser.add_argument("--device", help="默认 cpu；也可指定 cuda")
    return parser.parse_args()


def main():
    args = parse_args()
    old_run = find_run(args.resume) if args.resume else None
    config = read_json(args.config or (old_run / "config.json" if old_run else DEFAULT_CONFIG))
    for key in ("n_steps", "batch_size"):
        if getattr(args, key) is not None:
            config["ppo"][key] = getattr(args, key)
    for argument, key in (("timesteps", "total_timesteps"), ("n_envs", "n_envs"),
                          ("seed", "seed"), ("device", "device"), ("eval_freq", "eval_freq"),
                          ("eval_episodes", "eval_episodes"), ("checkpoint_freq", "checkpoint_freq")):
        if getattr(args, argument) is not None:
            config["run"][key] = getattr(args, argument)
    if args.max_episode_steps is not None:
        config["env"]["max_episode_steps"] = args.max_episode_steps
    validate_config(config)
    run = config["run"]
    engine = load_engine(args.engine_dir)
    module_dir = str(Path(engine.__file__).resolve().parent)
    if old_run:
        old_manifest = read_json(old_run / "manifest.json")
        old_config = read_json(old_run / "config.json")
        check_observation(old_manifest)
        check_engine_config(engine, old_manifest["engine_config"])
        if config["env"] != old_config["env"] or config["ppo"] != old_config["ppo"]:
            raise ValueError("续训保留原模型的 env / ppo 设置；修改这些参数请开始新实验")

    output = (args.output or ROOT / "training/runs" / datetime.now().strftime("ppo-%Y%m%d-%H%M%S-%f")).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "monitor").mkdir()
    write_json(output / "config.json", config)
    manifest = {
        "observation_version": OBSERVATION_VERSION,
        "engine_config": engine_config(engine),
        "engine_module": engine.__file__,
        "python": sys.version,
        "versions": {name: importlib.metadata.version(name) for name in
                     ("stable-baselines3", "gymnasium", "torch", "numpy")},
        "resume_from": str(args.resume.resolve()) if args.resume else None,
        "status": "starting",
        "requested_additional_timesteps": run["total_timesteps"],
    }
    write_json(output / "manifest.json", manifest)
    torch.set_num_threads(run["torch_threads"])
    train_env = eval_env = model = None
    interrupted = False
    stopper = GracefulStop()
    try:
        # 即便 n_envs=1 也隔离进程，这样单独的评估游戏不会清空训练中的静态池。
        train_env = SubprocVecEnv([
            make_env(config["env"], module_dir, str(output / "monitor" / f"train-{i}"))
            for i in range(run["n_envs"])
        ], start_method="spawn")
        train_env.seed(run["seed"])
        callbacks = [stopper]
        if run["checkpoint_freq"]:
            callbacks.append(CheckpointCallback(
                save_freq=max(run["checkpoint_freq"] // run["n_envs"], 1),
                save_path=str(output / "checkpoints"), name_prefix="ppo",
            ))
        if run["eval_freq"]:
            eval_env = SubprocVecEnv([
                make_env(config["env"], module_dir, str(output / "monitor/eval")),
            ], start_method="spawn")
            eval_env.seed(run["seed"] + 10000)
            callbacks.append(EvalCallback(
                eval_env, best_model_save_path=str(output / "best"),
                log_path=str(output / "evaluation"),
                eval_freq=max(run["eval_freq"] // run["n_envs"], 1),
                n_eval_episodes=run["eval_episodes"], deterministic=True,
            ))
        if args.resume:
            # SB3 的 zip 包保存网络和优化器；环境和未完成的 rollout 从新局开始。
            model = PPO.load(str(args.resume.resolve()), env=train_env, device=run["device"])
            model.set_random_seed(run["seed"])
        else:
            model = PPO("MlpPolicy", train_env, seed=run["seed"], device=run["device"],
                        verbose=1, **config["ppo"])
        model.set_logger(configure(str(output / "logs"), ["stdout", "csv", "tensorboard"]))
        manifest.update(status="training", initial_timesteps=int(model.num_timesteps))
        write_json(output / "manifest.json", manifest)
        print(f"实验目录：{output}", flush=True)
        stopper.install()
        model.learn(total_timesteps=run["total_timesteps"],
                    callback=CallbackList(callbacks), reset_num_timesteps=not bool(args.resume))
        interrupted = stopper.requested
        destination = output / ("interrupted.zip" if interrupted else "final.zip")
        model.save(str(destination))
        manifest["status"] = "interrupted" if interrupted else "completed"
        if interrupted:
            print(f"训练已中断，模型保存到 {destination}", flush=True)
    except KeyboardInterrupt:
        interrupted = True
        if model is not None:
            model.save(str(output / "interrupted.zip"))
            manifest["status"] = "interrupted"
            print(f"训练已中断，模型保存到 {output / 'interrupted.zip'}", flush=True)
        else:
            manifest["status"] = "interrupted_before_model"
    except Exception:
        manifest["status"] = "failed"
        raise
    finally:
        stopper.restore()
        if model is not None:
            manifest["total_timesteps"] = int(model.num_timesteps)
            model.logger.close()
        write_json(output / "manifest.json", manifest)
        if eval_env is not None:
            eval_env.close()
        if train_env is not None:
            train_env.close()
    if not interrupted:
        print(f"模型已保存：{output / 'final.zip'}", flush=True)


if __name__ == "__main__":
    mp.freeze_support()
    main()
