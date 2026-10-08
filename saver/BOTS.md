# PPO 机器人接入记录

## 回退基线

添加机器人前的源码已提交并推送：`c6dd722`。
阶段提交只在对应检查通过后创建。若已推送阶段出现问题，使用 `git revert` 撤销该阶段提交，保留历史和训练结果；不使用强制推送或清空工作区。

## 1. 单机器人

- 使用 40 万步的最佳 PPO 模型，导出 CPU ONNX actor；部署不依赖 Python。
- 512 组观测在 SB3、Python ONNX Runtime、C++ ONNX Runtime 中得到相同动作；C++ 同时校验 logits。
- C++ 真实引擎在三个固定种子下无碰撞通关；WebSocket 验证真人和机器人使用不同鸟槽位。
- 原有四项 WebSocket 测试通过。
- 风险控制：核对模型训练物理参数；每个补帧逻辑步重新推理；模型失效时只移除受影响机器人；最后一个真人离开清空机器人和本局。

CPU SDK 固定为 ONNX Runtime 1.23.2，从 Microsoft 官方 GitHub 发行包下载，SHA-256 写在 `cmake/OnnxRuntime.cmake` 中；SDK 及其许可证保存在 `third_party/onnxruntime`，SDK 不提交。模型及元数据提交在 `models/`。

重新导出模型：

```powershell
.\.venv\Scripts\python.exe -m pip install -r training/requirements-export.txt
.\.venv\Scripts\python.exe -m training.export_policy training/runs/cloud-20261008-132450-1905/best/best_model.zip
cmake --build saver/build --config Release
```

程序启动时加载模型一次，机器人共享该网络，每次按自己的鸟编号组织观测。网页仍负责显示，引擎仍负责物理、碰撞、复活和终点。

## 2. 多机器人

- C++ 真实引擎以 1、2、7、8 只机器人分别跑四个种子（包括联机默认种子 0），全部无碰撞通关。
- WebSocket 验证 1 真人 + 7 机器人、2 真人 + 6 机器人；两名玩家看到相同鸟列表。
- 超过 8 个总槽位以及负数、浮点数、布尔值、字符串、超大机器人数量被拒绝，并允许在原连接中改为合法数量重试。
- 真人跳跃只影响自己的鸟；真人断线不会删除其他真人或机器人；最后一个真人退出后，下一局不残留机器人。
- 模型物理参数不匹配时，显式要求机器人启动会失败；不会带着不兼容模型开局。

服务器启动参数 `--bots 0..7` 设置默认机器人数量；开局消息可用 `bots` 覆盖，例如 `{"type":"game_begin","speed":1,"bots":3}`。总数始终由服务器再次检查。`game_state.birds[].is_bot` 区分角色，`bot_count` 表示活动机器人数量。

多个机器人共享同一确定性策略，初始状态相同时会重叠飞行，这是预期行为。联机仍沿用现有引擎的终局规则：任意一只鸟到终点结束整局。复活后的表现不等同于单鸟训练的通关率，需要混合游玩验证。
