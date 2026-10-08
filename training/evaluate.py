"""独立评估；使用从未参与训练的 seed，输出距离/过管数/成功率。"""

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
import torch

from .engine_loader import check_engine_config, load_engine
from .env import FlappyEnv
from .settings import check_observation, find_run, read_json, write_json


def main():
    parser = argparse.ArgumentParser(description="评估一个 PPO 模型，不更新网络")
    parser.add_argument("model", type=Path, help="例如 training/runs/my-run/final.zip")
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1000000)
    parser.add_argument("--engine-dir", type=Path)
    parser.add_argument("--output", type=Path, help="评估报告 JSON 路径")
    args = parser.parse_args()
    if args.episodes < 1 or args.seed < 0 or args.seed + args.episodes >= 2**32:
        parser.error("episodes 必须大于 0，seed 及连续评估种子需在 uint32 范围内")
    run = find_run(args.model)
    config = read_json(run / "config.json")
    manifest = read_json(run / "manifest.json")
    check_observation(manifest)
    engine = load_engine(args.engine_dir)
    check_engine_config(engine, manifest["engine_config"])
    torch.set_num_threads(1)
    model = PPO.load(str(args.model.resolve()), device="cpu")
    episodes = []
    with FlappyEnv(config["env"], Path(engine.__file__).parent) as env:
        for index in range(args.episodes):
            observation, _ = env.reset(seed=args.seed + index)
            total_reward = 0.0
            while True:
                action, _ = model.predict(observation, deterministic=True)
                observation, reward, terminated, truncated, info = env.step(int(action))
                total_reward += reward
                if terminated or truncated:
                    break
            result = {"reset_seed": args.seed + index, "reward": total_reward, **info}
            episodes.append(result)
            print(f"第 {index + 1} 局：距离 {info['distance']:.0f}，"
                  f"过管 {info['pipes_passed']}，{info['end_reason']}", flush=True)
    report = {
        "model": str(args.model.resolve()),
        "episodes": episodes,
        "mean_reward": float(np.mean([e["reward"] for e in episodes])),
        "std_reward": float(np.std([e["reward"] for e in episodes])),
        "mean_distance": float(np.mean([e["distance"] for e in episodes])),
        "mean_pipes_passed": float(np.mean([e["pipes_passed"] for e in episodes])),
        "success_rate": float(np.mean([e["is_success"] for e in episodes])),
    }
    output = args.output or run / f"report-{datetime.now():%Y%m%d-%H%M%S-%f}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, report)
    print(f"平均距离 {report['mean_distance']:.1f}，平均过管 {report['mean_pipes_passed']:.2f}，"
          f"通关率 {report['success_rate']:.1%}；报告：{output}")


if __name__ == "__main__":
    main()
