"""导出真实 C++ 引擎轨迹，浏览器只负责播放；不会再次训练模型。"""

import argparse
from pathlib import Path

from stable_baselines3 import PPO
import torch

from .engine_loader import check_engine_config, engine_config, load_engine
from .env import FlappyEnv
from .settings import check_observation, find_run, read_json, write_json


def record_episode(model, env, seed, stride=2):
    observation, info = env.reset(seed=seed)
    frames = []
    pipes = {}

    def capture(action):
        state = env._state
        bird = state.birds[0]
        # 管道为静态世界坐标，去重保存；每帧只需保存鸟和计分信息。
        for pipe in state.pipes:
            pipes[pipe.x] = [pipe.x, pipe.up, pipe.down]
        frames.append([info["engine_steps"], round(bird.position.x, 3),
                       round(bird.position.y, 3), round(bird.velocity.y, 3),
                       action, info["pipes_passed"]])

    capture(-1)
    total_reward = 0.0
    while True:
        action, _ = model.predict(observation, deterministic=True)
        observation, reward, terminated, truncated, info = env.step(int(action))
        total_reward += reward
        # 新生成的管道需要保存，即使这一逻辑步不保存鸟的帧。
        for pipe in env._state.pipes:
            pipes[pipe.x] = [pipe.x, pipe.up, pipe.down]
        if info["engine_steps"] % stride == 0 or terminated or truncated:
            capture(int(action))
        if terminated or truncated:
            return {"seed": seed, "frames": frames, "pipes": list(pipes.values()),
                    "reward": total_reward, "result": info}


def main():
    parser = argparse.ArgumentParser(description="导出可直接在浏览器打开的 AI 对比回放")
    parser.add_argument("models", type=Path, nargs="+")
    parser.add_argument("--seeds", type=int, nargs="+", default=[2000000, 2000001])
    parser.add_argument("--reports", type=Path, nargs="+", help="对应模型的独立评估 JSON，可选")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine-dir", type=Path)
    args = parser.parse_args()
    if len(args.models) > 2:
        parser.error("一个回放页面最多对比两个模型")
    if any(seed < 0 or seed >= 2**32 for seed in args.seeds):
        parser.error("seed 必须在 uint32 范围内")
    if args.reports is not None and len(args.reports) != len(args.models):
        parser.error("--reports 的数量必须与模型数量一致")
    engine = load_engine(args.engine_dir)
    torch.set_num_threads(1)
    data = {"engine_config": engine_config(engine), "seeds": args.seeds,
            "frame_stride": 2, "models": [], "replays": []}
    paired_evaluation_seeds = None
    for index, path in enumerate(args.models):
        run = find_run(path)
        config = read_json(run / "config.json")
        manifest = read_json(run / "manifest.json")
        check_observation(manifest)
        check_engine_config(engine, manifest["engine_config"])
        report = read_json(args.reports[index]) if args.reports else None
        if report:
            if Path(report["model"]).resolve() != path.resolve():
                raise ValueError("评估报告与模型文件不匹配")
            evaluation_seeds = [episode["reset_seed"] for episode in report["episodes"]]
            if paired_evaluation_seeds is not None and evaluation_seeds != paired_evaluation_seeds:
                raise ValueError("两个评估报告必须使用相同顺序的种子")
            paired_evaluation_seeds = evaluation_seeds
        model = PPO.load(str(path.resolve()), device="cpu")
        label = {"best_model": "最佳模型", "final": "最终模型"}.get(path.stem, path.stem)
        data["models"].append({"label": label, "path": str(path.resolve()),
                               "timesteps": int(model.num_timesteps), "evaluation": report})
        recordings = []
        with FlappyEnv(config["env"], Path(engine.__file__).parent) as env:
            for seed in args.seeds:
                replay = record_episode(model, env, seed)
                recordings.append(replay)
                print(f"{label} / seed={seed}：{replay['result']['end_reason']}，"
                      f"过管 {replay['result']['pipes_passed']}", flush=True)
        data["replays"].append(recordings)
    # 将数据嵌入页面，离线播放不需要启动 HTTP 或 WebSocket 服务。
    import json
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = Path(__file__).with_name("replay_template.html").read_text(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template.replace("__REPLAY_DATA__", payload), encoding="utf-8")
    write_json(args.output.with_suffix(".summary.json"), {
        "models": data["models"], "seeds": args.seeds,
        "source": "本地 C++ 引擎 / PPO 确定性动作 / 每两个逻辑步记录一帧",
    })
    print(f"回放已保存：{args.output.resolve()}", flush=True)


if __name__ == "__main__":
    main()
