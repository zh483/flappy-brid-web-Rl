"""Real WebSocket integration with the deployed C++ ONNX actor."""
import unittest
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import test_server as helpers


class BotServerTest(unittest.TestCase):
    server_args = ["--bots", "1"]
    setUp = helpers.ServerTest.setUp
    stop_server = helpers.ServerTest.stop_server
    connect = helpers.ServerTest.connect
    wait_for = helpers.ServerTest.wait_for

    def test_lobby_tracks_human_capacity(self):
        lobby = self.wait_for(self.first, "lobby")
        self.assertEqual(lobby["player_count"], 1)
        self.assertTrue(lobby["bot_available"])
        other, _ = self.connect()
        self.assertEqual(self.wait_for(self.first, "lobby")["player_count"], 2)
        self.assertEqual(self.wait_for(other, "lobby")["player_count"], 2)
        other.close()
        self.assertEqual(self.wait_for(self.first, "lobby")["player_count"], 1)

    def test_one_bot_and_human_have_separate_birds(self):
        self.first.send({"type": "game_begin", "speed": 1})
        started = self.wait_for(self.first, "game_started")
        state = self.wait_for(self.first, "game_state")
        human = started["bird_id"]
        bots = [b for b in state["birds"] if b["present"] and b["is_bot"]]
        self.assertEqual(len(bots), 1)
        self.assertNotEqual(bots[0]["bird_id"], human)
        self.assertFalse(state["birds"][human]["is_bot"])
        state = self.wait_for(self.first, "game_state", lambda m: m["tick"] >= 48)
        bot = state["birds"][bots[0]["bird_id"]]
        self.assertGreater(bot["position_x"], 80)
        self.assertEqual(bot["respawn_ms"], 0)
        self.assertLess(state["birds"][human]["position_y"], bot["position_y"])
        self.assertIsNone(self.process.poll())

    def test_invalid_bot_counts_leave_lobby_usable(self):
        for value in (-1, 8, 1.5, True, "2", 999999999999999999999):
            with self.subTest(value=value):
                self.first.send({"type": "game_begin", "speed": 1, "bots": value})
                self.wait_for(self.first, "error")
        self.first.send({"type": "game_begin", "speed": 1, "bots": 7})
        self.wait_for(self.first, "game_started")
        state = self.wait_for(self.first, "game_state")
        self.assertEqual(state["bot_count"], 7)
        self.assertEqual(sum(b["present"] for b in state["birds"]), 8)
        self.assertEqual(sum(b["is_bot"] for b in state["birds"]), 7)

    def test_two_humans_six_bots_capacity_disconnect_restart(self):
        other, _ = self.connect()
        self.first.send({"type": "game_begin", "speed": 1, "bots": 7})
        self.wait_for(self.first, "error")
        self.first.send({"type": "game_begin", "speed": 1, "bots": 6})
        own_start = self.wait_for(self.first, "game_started")
        other_start = self.wait_for(other, "game_started")
        state = self.wait_for(self.first, "game_state")
        other_state = self.wait_for(other, "game_state")
        self.assertEqual(state["birds"], other_state["birds"])
        self.assertNotEqual(own_start["bird_id"], other_start["bird_id"])
        self.assertEqual(state["bot_count"], 6)
        self.assertEqual(sum(b["present"] for b in state["birds"]), 8)
        self.first.send({"type": "jump", "bird_id": 7})  # Client cannot control a bot by ID.
        state = self.wait_for(self.first, "game_state", lambda m: m["tick"] > 0)
        self.assertGreater(state["birds"][own_start["bird_id"]]["velocity_y"], 0)
        self.assertLess(state["birds"][other_start["bird_id"]]["velocity_y"], 0)
        other.close(abrupt=True)
        state = self.wait_for(self.first, "game_state", lambda m: not m["birds"][other_start["bird_id"]]["present"])
        self.assertEqual(state["bot_count"], 6)
        self.assertTrue(state["birds"][own_start["bird_id"]]["present"])
        self.first.close()
        deadline = time.monotonic() + 3
        while True:
            try:
                replacement, _ = self.connect()
                break
            except helpers.HandshakeRejected:
                if time.monotonic() >= deadline: raise
                time.sleep(0.02)
        replacement.send({"type": "game_begin", "speed": 1, "bots": 0})
        self.wait_for(replacement, "game_started")
        clean = self.wait_for(replacement, "game_state")
        self.assertEqual(clean["tick"], 0)
        self.assertEqual(clean["bot_count"], 0)
        self.assertEqual(sum(b["present"] for b in clean["birds"]), 1)
        self.assertFalse(any(b["is_bot"] for b in clean["birds"]))

    def test_wrong_physics_model_is_rejected_before_listening(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary) / "wrong.onnx"
            original = helpers.SERVER.parent / "models/ppo-bird.onnx"
            shutil.copyfile(original, model)
            metadata = json.loads(original.with_suffix(".json").read_text(encoding="utf-8"))
            metadata["engine_config"]["force"] += 1
            model.with_suffix(".json").write_text(json.dumps(metadata), encoding="utf-8")
            result = subprocess.run([str(helpers.SERVER), "--bots", "1", "--model", str(model)],
                                    capture_output=True, timeout=5,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"physics mismatch: force", result.stderr)


class UnavailableBotTest(unittest.TestCase):
    server_args = ["--model", "missing-test-model.onnx"]
    setUp = helpers.ServerTest.setUp
    stop_server = helpers.ServerTest.stop_server
    connect = helpers.ServerTest.connect
    wait_for = helpers.ServerTest.wait_for

    def test_missing_model_disables_bots_but_allows_humans(self):
        lobby = self.wait_for(self.first, "lobby")
        self.assertFalse(lobby["bot_available"])
        self.first.send({"type": "game_begin", "speed": 1, "bots": 1})
        self.wait_for(self.first, "error")
        self.first.send({"type": "game_begin", "speed": 1, "bots": 0})
        self.wait_for(self.first, "game_started")
        state = self.wait_for(self.first, "game_state")
        self.assertEqual(state["bot_count"], 0)


if __name__ == "__main__":
    unittest.main()
