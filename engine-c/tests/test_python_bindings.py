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

    def test_finish_freezes_updates_and_new_game_resets(self):
        engine.begin(engine.GameSet(speed=int(engine.config.world_width)), seed=3)
        engine.step([False] * 8)
        engine.step([False] * 8)
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
