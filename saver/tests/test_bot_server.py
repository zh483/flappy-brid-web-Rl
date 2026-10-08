"""Real WebSocket integration with the deployed C++ ONNX actor."""
import unittest
import test_server as helpers


class BotServerTest(unittest.TestCase):
    server_args = ["--bots", "1"]
    setUp = helpers.ServerTest.setUp
    stop_server = helpers.ServerTest.stop_server
    connect = helpers.ServerTest.connect
    wait_for = helpers.ServerTest.wait_for

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


if __name__ == "__main__":
    unittest.main()
