import unittest

from gymnasium.utils.env_checker import check_env as gym_check_env
import numpy as np
from stable_baselines3.common.env_checker import check_env as sb3_check_env
from stable_baselines3.common.vec_env import SubprocVecEnv

from training.env import EnvConfig, FlappyEnv
from training.train import make_env


class EnvironmentTest(unittest.TestCase):
    def test_official_environment_checkers(self):
        with FlappyEnv() as env:
            gym_check_env(env, skip_render_check=True)
            sb3_check_env(env, warn=True)

    def test_reset_seed_and_snapshot(self):
        with FlappyEnv() as env:
            first, info = env.reset(seed=11)
            layout = [(p.x, p.up, p.down) for p in env._state.pipes]
            env.step(1)
            second, next_info = env.reset(seed=11)
            np.testing.assert_array_equal(first, second)
            self.assertEqual(info, next_info)
            self.assertEqual(layout, [(p.x, p.up, p.down) for p in env._state.pipes])
            env.reset(seed=12)
            self.assertNotEqual(layout, [(p.x, p.up, p.down) for p in env._state.pipes])

    def test_death_terminates_before_respawn(self):
        with FlappyEnv() as env:
            env.reset(seed=3)
            for _ in range(100):
                obs, reward, terminated, truncated, info = env.step(0)
                self.assertTrue(env.observation_space.contains(obs))
                if terminated or truncated:
                    break
            self.assertTrue(terminated)
            self.assertFalse(truncated)
            self.assertTrue(info["crashed"])
            self.assertEqual(info["end_reason"], "crash")
            self.assertLess(reward, 0)
            self.assertGreater(env._state.birds[0].respawn_ms, 0)
            with self.assertRaises(RuntimeError):
                env.step(0)

    def test_time_limit_is_truncation(self):
        with FlappyEnv(EnvConfig(max_episode_steps=3)) as env:
            env.reset(seed=4)
            for _ in range(3):
                _, _, terminated, truncated, info = env.step(0)
            self.assertFalse(terminated)
            self.assertTrue(truncated)
            self.assertEqual(info["end_reason"], "time_limit")

    def test_single_process_guard_and_close(self):
        with FlappyEnv() as first:
            first.reset(seed=2)
            with self.assertRaises(RuntimeError):
                FlappyEnv()
        first.close()  # close 可重复调用。
        with FlappyEnv() as second:
            second.reset(seed=2)

    def test_pipe_rewards_once_and_finish(self):
        # 规则控制器只用于测试奖励/终点分支，不是 PPO 的训练标签。
        with FlappyEnv(EnvConfig(initial_speed=4)) as env:
            env.reset(seed=3)
            passed = 0
            for _ in range(10000):
                c = env.constants
                bird = env._state.birds[0]
                pipe = next((p for p in env._state.pipes if p.x + c.p_x >= bird.position.x), None)
                target = (pipe.up + pipe.down - c.b_y) / 2 if pipe else c.world_height / 2
                desired = max(-4.0, min(4.0, (target - bird.position.y) * 0.12))
                jump = int(bird.velocity.y - c.g < desired - c.force / 2)
                obs, reward, terminated, truncated, info = env.step(jump)
                self.assertTrue(env.observation_space.contains(obs))
                new_passed = info["pipes_passed"] - passed
                self.assertIn(new_passed, (0, 1))
                expected = env.settings.progress_reward * bird.velocity.x / c.p_n_x
                expected += env.settings.pipe_reward * new_passed
                if info["is_success"]:
                    expected += env.settings.finish_reward
                if info["crashed"]:
                    expected += env.settings.crash_reward
                self.assertAlmostEqual(reward, expected)
                passed = info["pipes_passed"]
                if terminated or truncated:
                    break
            self.assertFalse(truncated)
            self.assertFalse(info["crashed"])
            self.assertTrue(info["is_success"])
            self.assertGreater(passed, 100)
            self.assertEqual(info["end_reason"], "finish")

    def test_subprocesses_have_independent_engine_state(self):
        vec = SubprocVecEnv([make_env({}, None, None), make_env({}, None, None)], start_method="spawn")
        try:
            vec.seed(100)
            vec.reset()
            before = vec.env_method("diagnostics")
            self.assertNotEqual(before[0]["seed"], before[1]["seed"])
            obs, _, _, _ = vec.step(np.array([1, 0]))
            self.assertGreater(obs[0][1], obs[1][1])
            unchanged = vec.env_method("diagnostics", indices=1)[0]
            vec.env_method("reset", seed=800, indices=0)
            self.assertEqual(unchanged, vec.env_method("diagnostics", indices=1)[0])
        finally:
            vec.close()

    def test_configuration_rejects_invalid_values(self):
        for kwargs in ({"initial_speed": 0}, {"max_episode_steps": 0}, {"skin": -1},
                       {"crash_reward": float("nan")}):
            with self.assertRaises(ValueError):
                EnvConfig(**kwargs)


if __name__ == "__main__":
    unittest.main()
