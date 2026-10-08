"""一个 Python 进程只拥有一个 C++ 游戏；并行训练由 SubprocVecEnv 隔离。"""

from dataclasses import asdict, dataclass
import math
import weakref

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from .engine_loader import load_engine

_active_env = None
OBSERVATION_VERSION = 1


@dataclass(frozen=True)
class EnvConfig:
    initial_speed: int = 1
    skin: int = 0
    max_episode_steps: int = 30000
    progress_reward: float = 0.1
    pipe_reward: float = 1.0
    crash_reward: float = -1.0
    finish_reward: float = 10.0

    def __post_init__(self):
        for key in ("initial_speed", "skin", "max_episode_steps"):
            value = getattr(self, key)
            if type(value) is not int or value < (0 if key == "skin" else 1):
                raise ValueError(f"{key} 必须是合法整数")
        if self.initial_speed > 2147483647 or self.skin > 2147483647:
            raise ValueError("initial_speed / skin 超出 C++ int 范围")
        for key in ("progress_reward", "pipe_reward", "crash_reward", "finish_reward"):
            if not math.isfinite(getattr(self, key)):
                raise ValueError(f"{key} 必须是有限数值")


class FlappyEnv(gym.Env):
    """动作 0=不跳，1=跳；碰撞立即终止 episode，保留原引擎的物理规则。"""

    metadata = {"render_modes": []}

    def __init__(self, config=None, engine_dir=None):
        global _active_env
        owner = _active_env() if _active_env is not None else None
        if owner is not None:
            raise RuntimeError(
                "C++ 引擎是静态的，同一进程不能创建两个 FlappyEnv。"
                "请用 SubprocVecEnv；旧环境用完需 close()。"
            )
        self.settings = config if isinstance(config, EnvConfig) else EnvConfig(**(config or {}))
        self.engine = load_engine(engine_dir)
        self.constants = self.engine.config
        c = self.constants
        if min(c.world_height, c.world_width, c.camera_width, c.v_fps,
               c.max_vertical_speed, c.max_horizontal_speed, c.p_n_x) <= 0:
            raise ValueError("引擎尺寸、步长、速度上限和管道间距必须大于 0")
        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(
            low=np.array([-1, -1, 0, -1, 0, 0, 0, 0], dtype=np.float32),
            high=np.array([2, 1, 1, c.world_width / c.camera_width + 1,
                           1, 1, 2, 1], dtype=np.float32),
            dtype=np.float32,
        )
        self._closed = False
        self._done = True
        self._state = None
        self._steps = 0
        self._passed = set()
        self._episode_seed = 0
        _active_env = weakref.ref(self)

    def reset(self, *, seed=None, options=None):
        if self._closed:
            raise RuntimeError("环境已关闭，请重新创建")
        super().reset(seed=seed)
        # seed=None 时推进随机序列；显式传相同 seed 时可重现同一局。
        self._episode_seed = int(self.np_random.integers(0, 2**32, dtype=np.uint32))
        characters = [self.settings.skin] + [0] * 7
        self.engine.begin(self.engine.GameSet(
            size=1, speed=self.settings.initial_speed, characters=characters,
        ), seed=self._episode_seed)
        self._state = self.engine.get_state()
        self._steps = 0
        self._passed.clear()
        self._done = False
        return self._observation(), self._info(False, False)

    def step(self, action):
        if self._closed or self._done:
            raise RuntimeError("step 前必须 reset；episode 结束后也需要 reset")
        if not self.action_space.contains(action):
            raise ValueError("action 必须是整数 0 或 1")
        previous = self._state
        previous_x = previous.birds[0].position.x
        self.engine.step([bool(action)] + [False] * 7)
        self._state = self.engine.get_state()
        self._steps += 1
        bird = self._state.birds[0]
        crashed = bird.respawn_ms > 0 or not bird.present
        success = not crashed and self._state.phase == self.engine.GamePhase.finished
        # 用上一步快照统计，防止引擎已经回收管道而漏掉过管奖励。
        newly_passed = {
            p.x for p in previous.pipes
            if bird.position.x > p.x + self.constants.p_x and p.x not in self._passed
        } if not crashed else set()
        self._passed.update(newly_passed)
        reward = self.settings.progress_reward * max(0, bird.position.x - previous_x) / self.constants.p_n_x
        reward += self.settings.pipe_reward * len(newly_passed)
        if crashed:
            reward += self.settings.crash_reward
        if success:
            reward += self.settings.finish_reward
        terminated = bool(crashed or success)
        truncated = self._steps >= self.settings.max_episode_steps and not terminated
        self._done = terminated or truncated
        return self._observation(), float(reward), terminated, bool(truncated), self._info(crashed, success)

    def _observation(self):
        c = self.constants
        bird = self._state.birds[0]
        pipe = next((p for p in self._state.pipes if p.x + c.p_x >= bird.position.x), None)
        # 引擎 y 轴向上；velocity 是像素/step，将像素/秒的上限乘步长后再归一化。
        return np.array([
            bird.position.y / c.world_height,
            bird.velocity.y / (c.max_vertical_speed * c.v_fps),
            bird.velocity.x / (c.max_horizontal_speed * c.v_fps),
            (pipe.x - bird.position.x) / c.camera_width if pipe else 1.0,
            pipe.down / c.world_height if pipe else 0.0,
            pipe.up / c.world_height if pipe else 1.0,
            bird.position.x / c.world_width,
            float(pipe is not None),
        ], dtype=np.float32)

    def _info(self, crashed, success):
        reason = ("crash" if crashed else "finish" if success else
                  "time_limit" if self._done else "running")
        return {
            "distance": float(self._state.birds[0].position.x),
            "pipes_passed": len(self._passed),
            "is_success": bool(success),
            "crashed": bool(crashed),
            "episode_seed": self._episode_seed,
            "game_speed": int(self._state.speed),
            "engine_steps": self._steps,
            "end_reason": reason,
        }

    def diagnostics(self):
        """只读诊断，方便检查并行环境是否相互干扰。"""
        return {"steps": self._steps, "seed": self._episode_seed,
                "position": (self._state.birds[0].position.x, self._state.birds[0].position.y)}

    def close(self):
        global _active_env
        if not self._closed:
            self.engine.clear()
            self._closed = True
            self._done = True
            if _active_env is not None and _active_env() is self:
                _active_env = None

    def configuration(self):
        return asdict(self.settings)
