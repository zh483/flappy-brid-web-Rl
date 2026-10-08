# Linux 云端今晚运行

上传根目录的 `training-cloud.zip`，在云端终端解压。这个包只包含引擎源码和 Python 训练，不含 Windows 编译结果、模型、账号或整个服务器依赖。

## 上传后执行

把 ZIP 上传到准备存放实验的目录，然后在该目录打开终端：

```bash
python -m zipfile -e training-cloud.zip .
cd flappy-training
bash training/cloud_run.sh setup
```

建议使用 Linux、Python 3.10–3.13 和已有 PyTorch 的镜像。这个实验使用 CPU，先用 2 个环境；建议至少 2 个 CPU 核、8GB 内存，为多个 Python/PyTorch 进程留出空间。这是运行建议，不是实测最低配置。

如果提示缺少编译器，Ubuntu / Debian 的 root 终端执行：

```bash
apt-get update
apt-get install -y build-essential python3-dev python3-venv
```

非 root 用户需要管理员安装这些系统依赖。setup 默认使用 `python`，也可以指定 `FLAPPY_BASE_PYTHON=python3 bash training/cloud_run.sh setup`。

如果 pip 下载失败，可在当前终端执行 `export PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple` 后重试 setup。CPU PyTorch 的安装单独使用 PyTorch 官方源。

setup 会安装依赖、在 Linux 上重新编译 C++ 绑定并运行环境测试。确认出现 `Setup passed` 后再开始：

```bash
nohup bash training/cloud_run.sh run > cloud.log 2>&1 < /dev/null &
echo $!
tail -n 30 cloud.log
```

等待日志出现 `time/total_timesteps` 并持续增长，说明采样和训练已开始。`nohup` 后台运行与本地终端连接分离；本地断电不影响云端进程，云平台本身仍需保持实例运行。

默认最多训练 1000 万步，或达到 7 小时时请求保存 `interrupted.zip`；哪个先到就先结束训练，随后评估 10 局。实际可能提前完成。定期每 50000 步保存检查点，每 100000 步评估 3 局。若 120 秒内仍无法优雅停止，timeout 会强制结束，使用之前的检查点恢复。

修改本次任务的上限：

```bash
FLAPPY_HOURS=6 FLAPPY_TIMESTEPS=5000000 nohup bash training/cloud_run.sh run > cloud.log 2>&1 < /dev/null &
```

**脚本不自动关云实例，训练结束后实例可能继续计费。** 在平台控制台设置一个你能接受的定时关机时间，给训练保存和最终评估留出时间；例如从开始算 8 小时，而训练上限设为 7 小时。具体是否支持定时关机，以平台控制台为准。

第二天查看：

```bash
tail -n 60 cloud.log
ls training/runs
```

下载本次 `training/runs/cloud-.../` 整个目录，包含模型、配置、manifest、日志、检查点和评估报告。训练完成使用 `final.zip`；到时停止使用 `interrupted.zip`；意外退出可用最近检查点。保存好后再按需关机，避免误操作释放实例而丢失文件。

续训例子（把实际的目录名替换进去）：

```bash
nohup .venv/bin/python -m training.train \
  --resume training/runs/cloud-实际目录/interrupted.zip \
  --timesteps 1000000 --output training/runs/cloud-continued \
  > continued.log 2>&1 < /dev/null &
```

当前开发机验证过 C++ Windows 构建和 PPO 训练；云端 Linux 的实际编译与启动需要在目标实例上完成，不能仅凭上传包认为部署已经成功。

AutoDL 官方参考：[快速开始与上传](https://www.autodl.com/docs/quick_start/)、[后台运行](https://www.autodl.com/docs/daemon/)、[关机省钱](https://www.autodl.com/docs/save_money/)。
