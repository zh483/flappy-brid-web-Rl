"""让 Ctrl+C 在一次完整的采样通信结束后停止，避免 worker 被同时打断。"""

import signal

from stable_baselines3.common.callbacks import BaseCallback


def ignore_worker_interrupts():
    # 子进程只接受主进程发来的 close；Ctrl+C 由主进程统一处理和保存。
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.SIG_IGN)


class GracefulStop(BaseCallback):
    def __init__(self):
        super().__init__()
        self.requested = False
        self._previous = {}

    def install(self):
        signals = [signal.SIGINT]
        if hasattr(signal, "SIGBREAK"):
            signals.append(signal.SIGBREAK)
        for number in signals:
            self._previous[number] = signal.signal(number, self._request)

    def _request(self, number, frame):
        self.requested = True
        print("收到停止请求，当前采样通信完成后保存模型……", flush=True)

    def _on_step(self):
        return not self.requested

    def restore(self):
        for number, handler in self._previous.items():
            signal.signal(number, handler)
        self._previous.clear()
