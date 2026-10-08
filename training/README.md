# Python PPO 训练

这里使用官方 **Stable-Baselines3 2.7.1 的 PPO**，自行封装 **Gymnasium 1.2.3 环境**，通过 pybind11 直接调用本项目 C++ 引擎。训练不启动 Crow、WebSocket 或网页，也不按真实时间等待：一次 `step()` 推进一个固定逻辑步，能跑多快就跑多快。

这是一套可训练、保存、评估、续训的起始实现，默认超参数尚未针对本游戏调优。短训练验证流程，不代表模型已经学会通关。

## 1. 安装与构建

所有命令都在项目根目录 `E:\my_work\Flappy-Bird` 执行。目前本机已经创建 `.venv` 并复用 Anaconda 中的 PyTorch。后续直接使用这个环境的 Python，无需激活。

新电脑首次安装（已有 `.venv` 时不要重复创建）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r training/requirements.txt
.\.venv\Scripts\python.exe -m training.build_engine
```

如果已有 Anaconda/PyTorch，希望省去重复下载，可以把第一条改为 `python -m venv --system-site-packages .venv`。普通虚拟环境更独立，复用环境则会受到原环境升级的影响。

如果 PyPI 文件下载失败，可以在安装命令后添加 `--index-url https://mirrors.aliyun.com/pypi/simple`。本机安装已使用这个镜像，项目没有修改系统代理或全局 pip 配置。

Windows 构建需要 Visual Studio 2022 的 C++ 桌面开发工具。构建脚本会用当前 Python 编译到 `engine-c/build-training/python/`，训练入口会自动找到它。改过 C++ 的 `config.cpp` 后，需要重新执行构建脚本。

也可以用 `--engine-dir 路径` 指定其他编译目录，或设置环境变量 `FLAPPY_ENGINE_DIR`。模块必须与 Python 版本和系统架构一致；Windows 的 `.pyd` 不能直接拿去 Linux 使用。

先检查环境接口与真实引擎：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s training/tests -v
```

## 2. 跑一次短训练

```powershell
.\.venv\Scripts\python.exe -m training.train --timesteps 4096 --n-envs 2 --n-steps 256 --batch-size 128 --eval-freq 2048 --eval-episodes 2 --checkpoint-freq 2048 --output training/runs/first-ppo
```

`--output` 必须指向尚不存在的新目录，避免覆盖模型。第一次启动子进程需要一些时间。PPO 会收集完整 rollout，因此实际步数可能向上取整到 `n_steps × n_envs` 的倍数。`timesteps` 是所有环境的步数总和。

确认流程正确后，使用默认配置开始正式实验：

```powershell
.\.venv\Scripts\python.exe -m training.train --output training/runs/ppo-1m
```

默认使用 CPU、小型 `[64, 64]` MLP、4 个环境、100 万逻辑步。可在 `config.json` 调整参数，或用 `--config 自己的配置.json` 保留多套配置。并行数先试 2 或 4；更多进程不保证更快，也会增加内存使用。这个项目没有图像编码，先用 CPU 跑基准，再考虑租 GPU。

训练主进程使用 1 个 PyTorch 计算线程，避免小网络占用过多线程。网络采用离散动作 PPO，不需要 Double DQN 的经验回放池或目标 Q 网络。

## 3. 输出、评估与续训

每个实验目录保存：

- `final.zip`：训练完成时的 PPO 网络、优化器和算法参数。
- `best/best_model.zip`：独立评估环境中，平均奖励最高的模型；未触发评估时没有此文件。
- `checkpoints/`：按总环境步数定期保存的模型，频率会换算成向量环境调用次数。
- `logs/`：训练 CSV 和 TensorBoard 日志。
- `monitor/`：每局的奖励、长度、距离、过管数和通关标记。
- `evaluation/evaluations.npz`：定期评估结果。
- `config.json` / `manifest.json`：本次配置、版本、实际引擎参数、模型来源和训练状态。

模型与配置文件请一起保存。输出位于 `runs/`，已被 Git 忽略。

SB3 的 `.zip` 通过 Python/PyTorch 加载。将来要在 C++ 服务器里推理，需要另做模型导出与推理接线，并保持相同的 8 维观测顺序；当前训练入口没有改动服务器。

评估固定种子的 20 局，输出 JSON 报告：

```powershell
.\.venv\Scripts\python.exe -m training.evaluate training/runs/first-ppo/final.zip --episodes 20
```

也可以将路径换成 `best/best_model.zip`。评估使用确定性动作，不更新模型；主要看平均过管数、平均距离和通关率。`best` 是按评估平均奖励选择，不保证通关率一定最高。独立评估种子默认从 1000000 开始，避免使用训练随机序列。

导出可在浏览器直接打开的 AI 回放，例如：

```powershell
.\.venv\Scripts\python.exe -m training.replay training/runs/first-ppo/final.zip --seeds 1000000 --output training/runs/first-ppo/replay.html
```

支持同时传入两个模型对比同一关卡；用 `--reports 报告1.json 报告2.json` 可以将相同种子的评估结果一起展示。回放使用 C++ 引擎记录的真实轨迹，每两个逻辑步记录一帧，网页可暂停、拖动进度和加速播放，不需要启动服务器。

请打开 `--output` 生成的 HTML 文件。`training/replay_template.html` 只是页面模板，不含模型轨迹，直接打开无法播放。

继续训练，例如在已有模型上**增加** 10 万步：

```powershell
.\.venv\Scripts\python.exe -m training.train --resume training/runs/first-ppo/final.zip --timesteps 100000 --output training/runs/first-ppo-continued
```

续训自动使用原实验的环境和 PPO 配置，并恢复网络、优化器及累计训练步数。新实验目录保留旧模型。环境、随机状态和未完成的 rollout 不会逐字节恢复，而是从新的一局继续采样。改变 PPO 或奖励参数时请新开实验；改了引擎物理参数后，旧模型的续训/评估会明确提示不匹配。

按 `Ctrl+C` 会尝试保存 `interrupted.zip`，可用同样的 `--resume` 命令恢复。强制杀进程、关机或云平台强制回收时可能来不及保存，因此仍要保留定期检查点。

查看学习曲线：

```powershell
.\.venv\Scripts\python.exe -m tensorboard.main --logdir training/runs
```

## 4. 环境规则

`FlappyEnv.reset(seed=...)` 返回 `(observation, info)`；`step(action)` 返回 `(observation, reward, terminated, truncated, info)`。

动作：`0` 不跳，`1` 跳。一次动作对应一次引擎更新，没有额外跳帧。保留原引擎“先移动、再施加跳跃”的惯性规则。

观测是 `float32` 的 8 维向量，依次为：

1. 鸟的底边 y / 世界高度。
2. 鸟的竖直速度 / 每步竖直速度上限。
3. 鸟的水平速度 / 每步水平速度上限。
4. 下一管道左边缘与鸟的 x 距离 / 摄像头宽度。
5. 下一洞口下边缘 / 世界高度。
6. 下一洞口上边缘 / 世界高度。
7. 鸟的 x / 世界长度，提供进度信息。
8. 是否存在下一管道（0 或 1）。

坐标 y 向上。C++ 快照速度的单位是 **像素/逻辑步**，而 config 的速度上限是 **像素/秒**，归一化时已经通过 `v_fps` 换算。没有下一管道时，洞口设为整个高度，距离设为 1，同时第 8 维为 0。

默认奖励：每前进一个管道间距累计 `+0.1`，完整越过一根管道 `+1`，碰撞 `-1`，到终点额外 `+10`。管道奖励只算一次，利用更新前的快照避免管道回收导致漏记。配置里的奖励数值均可调整。

碰撞或通关：`terminated=True`。达到 `max_episode_steps`：`truncated=True`。碰撞后不等待复活，下一次 reset 重新开局；联机游戏中的复活逻辑没有修改。达到时间限制也不视为死亡，SB3 按时间截断处理价值估计。单局最多 30000 步，足够当前正常速度到达 40000 像素的终点。

**一个进程只能有一个环境**，因为 C++ 引擎、鸟池和管道池是静态数据。训练使用 `SubprocVecEnv(start_method="spawn")`，评估也独占一个进程；不要换成包含多个环境的 `DummyVecEnv`，也不要用线程共享一个引擎。自行编写 Windows 训练脚本时，入口必须放在 `if __name__ == "__main__":` 内。

相同 reset seed 可复现同一局；`reset()` 不传 seed 会继续随机序列，避免每局管道都相同。更换平台、依赖或并行配置不保证训练结果完全一致。

## 5. Linux / 云平台

临时上云跑一晚的上传包与后台运行步骤见 [云端快速说明](CLOUD.md)。

上传源码，安装 C++ 编译器、Python 开发头文件，再执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r training/requirements.txt
.venv/bin/python -m training.build_engine
.venv/bin/python -m training.train --n-envs 2 --output training/runs/cloud-ppo
```

仅使用 CPU 时，可以先按 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/) 安装对应系统的 CPU 版本，再安装 requirements，减少 CUDA 依赖下载。云平台需要保存整个实验目录，尤其是检查点；这里没有自动租机器或上传数据。

## 文件分工与官方文档

- `env.py`：动作、观测、奖励、结束规则和种子。
- `engine_loader.py`：定位模块与读取真实物理参数。
- `config.json` / `settings.py`：实验参数及校验。
- `train.py`：PPO、独立采样进程、定期评估、保存和续训。
- `callbacks.py`：收到 Ctrl+C 后，由主进程统一停止并保存。
- `evaluate.py`：加载模型并评估，不训练。
- `build_engine.py`：用当前 Python 构建 pybind11 模块。
- `tests/`：官方环境检查器、碰撞、截断、过管奖励、终点和进程隔离测试。

PPO 和 Gymnasium 通过 pip 安装官方实现，没有把第三方整个源码复制进项目。对接代码由 Codex 编写，C++ 引擎核心仍由 zh483 手写。

参考：[SB3 PPO](https://stable-baselines3.readthedocs.io/en/v2.7.1/modules/ppo.html)、[SB3 回调](https://stable-baselines3.readthedocs.io/en/v2.7.1/guide/callbacks.html)、[向量环境](https://stable-baselines3.readthedocs.io/en/v2.7.1/guide/vec_envs.html)、[Gymnasium 自定义环境](https://gymnasium.farama.org/introduction/create_custom_env/)。
