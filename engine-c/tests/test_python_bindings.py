"""Run via CTest, or pass the directory containing flappy_engine as argv[1]."""

import sys
import unittest

if len(sys.argv) > 1:
    sys.path.insert(0, sys.argv.pop(1))

import flappy_engine as engine


class PythonBindingsTest(unittest.TestCase):
    def setUp(self):
        engine.clear()

    def tearDown(self):
        engine.clear()

    def test_idle_and_clear_do_not_update(self):
        engine.step([False] * 8)
        state = engine.get_state()
        self.assertEqual(state.phase, engine.GamePhase.idle)
        self.assertEqual(state.pipes, [])
        self.assertFalse(any(bird.present for bird in state.birds))

    def test_setup_and_seeded_reset(self):
        settings = engine.GameSet(size=8, speed=4, characters=list(range(8)))
        engine.begin(settings, seed=123)
        state = engine.get_state()
        self.assertEqual(state.phase, engine.GamePhase.running)
        self.assertEqual(state.speed, 4)
        self.assertEqual(len(state.pipes), 10)
        self.assertEqual(state.pipes[0].x, 500)
        self.assertEqual(len(state.birds), 8)
        self.assertTrue(all(bird.present for bird in state.birds))
        self.assertEqual([bird.character for bird in state.birds], list(range(8)))
        layout = [(pipe.x, pipe.up, pipe.down) for pipe in state.pipes]
        engine.step([True] * 8)
        engine.begin(settings, seed=123)
        self.assertEqual(layout, [(p.x, p.up, p.down) for p in engine.get_state().pipes])

    def test_actions_and_snapshot_lifetime(self):
        engine.begin(engine.GameSet(size=2), seed=7)
        old = engine.get_state()
        engine.step([True] + [False] * 7)
        new = engine.get_state()
        self.assertGreater(new.birds[0].velocity.y, new.birds[1].velocity.y)
        self.assertEqual(old.birds[0].velocity.y, 0)
        # Modifying a Python snapshot cannot teleport the real bird.
        new.birds[0].position.x = -100
        self.assertGreaterEqual(engine.get_state().birds[0].position.x, 0)
        engine.clear()
        self.assertEqual(old.phase, engine.GamePhase.running)
        self.assertEqual(len(old.pipes), 10)
        self.assertTrue(old.birds[0].present)
        self.assertEqual(engine.get_state().phase, engine.GamePhase.idle)

    def test_invalid_arguments_preserve_current_game(self):
        engine.begin(engine.GameSet(), seed=9)
        for size in (0, 9):
            with self.assertRaises(ValueError):
                engine.begin(engine.GameSet(size=size))
        for length in (0, 7, 9):
            with self.assertRaises(TypeError):
                engine.step([False] * length)
        with self.assertRaises(TypeError):
            engine.GameSet(characters=[1, 2])
        self.assertEqual(engine.get_state().phase, engine.GamePhase.running)

    def test_large_difficulty_cannot_bypass_speed_limit(self):
        engine.begin(engine.GameSet(speed=2147483647), seed=3)
        previous_x = 0
        for _ in range(8):
            engine.step([False] * 8)
            bird = engine.get_state().birds[0]
            self.assertGreaterEqual(bird.velocity.x, 0)
            self.assertLessEqual(bird.velocity.x / engine.config.v_fps,
                                 engine.config.max_horizontal_speed)
            self.assertLessEqual(bird.position.x - previous_x,
                                 engine.config.max_horizontal_speed * engine.config.v_fps)
            previous_x = bird.position.x

    def test_finish_freezes_updates_and_new_game_resets(self):
        # 有速度上限后不能用极大难度瞬移终点；通过正常操作跑完有限关卡。
        engine.begin(engine.GameSet(speed=4), seed=3)
        max_steps = int(engine.config.world_width /
                        (engine.config.max_horizontal_speed * engine.config.v_fps)) * 4
        for _ in range(max_steps):
            current = engine.get_state()
            bird = current.birds[0]
            pipe = next((p for p in current.pipes
                         if p.x + engine.config.p_x >= bird.position.x), None)
            target = ((pipe.up + pipe.down - engine.config.b_y) / 2
                      if pipe else engine.config.world_height / 2)
            desired_velocity = max(-4.0, min(4.0, (target - bird.position.y) * 0.12))
            jump = bird.velocity.y - engine.config.g < desired_velocity - engine.config.force / 2
            engine.step([jump] + [False] * 7)
            if engine.is_finished():
                break
        self.assertTrue(engine.is_finished())
        state = engine.get_state()
        self.assertEqual(state.phase, engine.GamePhase.finished)
        engine.step([True] * 8)
        self.assertEqual(engine.get_state().birds[0].position.x, state.birds[0].position.x)
        self.assertEqual(engine.get_state().birds[0].position.y, state.birds[0].position.y)
        engine.begin(engine.GameSet(), seed=3)
        self.assertFalse(engine.is_finished())
        self.assertEqual(engine.get_state().birds[0].position.x, 0)


if __name__ == "__main__":
    unittest.main()
