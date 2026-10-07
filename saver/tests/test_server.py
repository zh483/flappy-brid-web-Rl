"""Black-box WebSocket tests; only the Python standard library is required."""

import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest

SERVER = Path(sys.argv.pop(1)).resolve() if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "build/Release/flappy_server.exe"
)


class HandshakeRejected(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(f"WebSocket handshake rejected: {status}")


class WebSocket:
    def __init__(self, port):
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.closed = False
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        try:
            self.socket.sendall(request.encode("ascii"))
            header = bytearray()
            while not header.endswith(b"\r\n\r\n"):
                header.extend(self.read_exact(1))
                if len(header) > 16384:
                    raise AssertionError("HTTP response header is too large")
            lines = header.decode("ascii").split("\r\n")
            status = int(lines[0].split()[1])
            if status != 101:
                raise HandshakeRejected(status)
            headers = dict(line.split(":", 1) for line in lines[1:] if ":" in line)
            headers = {name.lower(): value.strip() for name, value in headers.items()}
            expected = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()).decode("ascii")
            assert headers["sec-websocket-accept"] == expected
        except Exception:
            self.socket.close()
            raise

    def read_exact(self, size):
        data = bytearray()
        while len(data) < size:
            part = self.socket.recv(size - len(data))
            if not part:
                raise ConnectionError("WebSocket disconnected")
            data.extend(part)
        return bytes(data)

    def send_frame(self, payload, opcode=1):
        # Browser-to-server WebSocket frames must be masked.
        header = bytearray([0x80 | opcode])
        if len(payload) < 126:
            header.append(0x80 | len(payload))
        elif len(payload) <= 65535:
            header.extend(struct.pack("!BH", 0x80 | 126, len(payload)))
        else:
            header.extend(struct.pack("!BQ", 0x80 | 127, len(payload)))
        mask = os.urandom(4)
        masked = bytes(value ^ mask[i % 4] for i, value in enumerate(payload))
        self.socket.sendall(header + mask + masked)

    def send(self, message):
        self.send_frame(json.dumps(message).encode("utf-8"))

    def receive(self, timeout=3):
        self.socket.settimeout(timeout)
        fragments = bytearray()
        while True:
            first, second = self.read_exact(2)
            size = second & 0x7F
            if size == 126:
                size = struct.unpack("!H", self.read_exact(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self.read_exact(8))[0]
            assert not second & 0x80, "Server frame should not be masked"
            payload = self.read_exact(size)
            opcode = first & 0x0F
            if opcode == 8:
                raise ConnectionError("Server closed the WebSocket")
            if opcode == 9:
                self.send_frame(payload, opcode=10)
                continue
            if opcode == 10:
                continue
            assert opcode in (0, 1), f"Unexpected opcode: {opcode}"
            fragments.extend(payload)
            if first & 0x80:
                return json.loads(fragments.decode("utf-8"))

    def close(self, abrupt=False):
        if self.closed:
            return
        self.closed = True
        if not abrupt:
            try:
                self.send_frame(struct.pack("!H", 1000), opcode=8)
            except OSError:
                pass
        self.socket.close()


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.clients = []
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.log = tempfile.TemporaryFile()
        self.process = subprocess.Popen(
            [str(SERVER), str(self.port)], stdout=self.log, stderr=self.log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.addCleanup(self.stop_server)
        deadline = time.monotonic() + 5
        while True:
            try:
                self.first, self.first_id = self.connect()
                break
            except OSError:
                if self.process.poll() is not None or time.monotonic() > deadline:
                    raise
                time.sleep(0.02)
        self.assertEqual(self.first_id, 0)

    def stop_server(self):
        for client in self.clients:
            client.close()
        self.process.terminate()
        self.process.wait(timeout=5)
        self.log.close()

    def connect(self):
        client = WebSocket(self.port)
        self.clients.append(client)
        welcome = client.receive()
        self.assertEqual(welcome["type"], "connected")
        return client, welcome["client_id"]

    def wait_for(self, client, message_type, predicate=lambda message: True):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            message = client.receive(timeout=max(0.01, deadline - time.monotonic()))
            if message["type"] == message_type and predicate(message):
                return message
        self.fail(f"Did not receive {message_type}")

    def test_capacity_and_id_reuse(self):
        ids = [self.first_id]
        for _ in range(7):
            _, client_id = self.connect()
            ids.append(client_id)
        self.assertEqual(ids, list(range(8)))
        with self.assertRaises(HandshakeRejected) as rejected:
            WebSocket(self.port)
        self.assertEqual(rejected.exception.status, 400)
        self.first.close()
        deadline = time.monotonic() + 2
        while True:
            try:
                _, client_id = self.connect()
                break
            except HandshakeRejected:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.02)
        self.assertEqual(client_id, 0)

    def test_invalid_messages_are_json_errors(self):
        self.first.send({"type": "jump"})  # No bird before the game starts.
        invalid = [
            "hello", "[]", "{}", '{"type":3}',
            '{"type":"unknown"}', '{"type":"select_skin"}',
            '{"type":"select_skin","skin":true}',
            '{"type":"select_skin","skin":2.5}',
            '{"type":"select_skin","skin":-1}',
            '{"type":"select_skin","skin":2147483648}',
            '{"type":"select_skin","skin":99999999999999999999999999999999}',
            '{"type":"game_begin","speed":0}',
        ]
        for text in invalid:
            with self.subTest(text=text):
                self.first.send_frame(text.encode("utf-8"))
                self.assertIsInstance(self.wait_for(self.first, "error")["message"], str)
        self.first.send_frame(b"binary", opcode=2)
        self.wait_for(self.first, "error")
        self.first.send({"type": "client_error", "error": "test diagnostic"})
        self.first.send({"type": "select_skin", "skin": 13})
        self.assertEqual(self.wait_for(self.first, "skin_selected")["skin_id"], 13)
        self.assertIsNone(self.process.poll())

    def test_state_jump_disconnect_and_new_game(self):
        second, second_id = self.connect()
        for client, skin in ((self.first, 13), (second, 29)):
            client.send({"type": "select_skin", "skin": skin})
            self.wait_for(client, "skin_selected")
        self.first.send({"type": "game_begin", "speed": 1})
        started = self.wait_for(self.first, "game_started")
        other_started = self.wait_for(second, "game_started")
        self.assertNotEqual(started["bird_id"], other_started["bird_id"])
        state = self.wait_for(self.first, "game_state")
        other_state = self.wait_for(second, "game_state")
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["client_id"], 0)
        self.assertEqual(other_state["client_id"], second_id)
        self.assertEqual(state["birds"], other_state["birds"])
        self.assertEqual(state["pipes"], other_state["pipes"])
        self.assertEqual(len(state["birds"]), 8)
        self.assertEqual([bird["bird_id"] for bird in state["birds"]], list(range(8)))
        self.assertEqual(sum(bird["present"] for bird in state["birds"]), 2)
        self.assertEqual(state["birds"][started["bird_id"]]["character"], 13)
        self.assertEqual(state["birds"][other_started["bird_id"]]["character"], 29)
        self.assertTrue(all("invincible_ms" in bird for bird in state["birds"]))
        self.assertEqual(len(state["pipes"]), 10)
        with self.assertRaises(HandshakeRejected):
            WebSocket(self.port)  # Cannot join during a running game.

        self.first.send({"type": "jump"})
        state = self.wait_for(self.first, "game_state", lambda m:
            m["tick"] > 0 and m["birds"][started["bird_id"]]["velocity_y"] > 0)
        self.assertLess(state["birds"][other_started["bird_id"]]["velocity_y"], 0)
        self.first.send({"type": "game_begin", "speed": 1})
        self.wait_for(self.first, "error")
        self.first.send({"type": "select_skin", "skin": 1})
        self.wait_for(self.first, "error")

        state = self.wait_for(self.first, "game_state", lambda m: m["tick"] >= 5)
        previous_tick = state["tick"]
        second.close(abrupt=True)
        state = self.wait_for(self.first, "game_state", lambda m:
            not m["birds"][other_started["bird_id"]]["present"])
        self.assertGreater(state["tick"], previous_tick)
        self.assertTrue(state["birds"][started["bird_id"]]["present"])
        self.first.close()

        deadline = time.monotonic() + 2
        while True:
            try:
                replacement, client_id = self.connect()
                break
            except HandshakeRejected:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.02)
        self.assertEqual(client_id, 0)
        replacement.send({"type": "game_begin", "speed": 1})
        self.wait_for(replacement, "game_started")
        state = self.wait_for(replacement, "game_state")
        self.assertEqual(state["tick"], 0)
        self.assertEqual(sum(bird["present"] for bird in state["birds"]), 1)

    def test_large_difficulty_cannot_bypass_speed_limit(self):
        self.first.send({"type": "game_begin", "speed": 40000})
        self.wait_for(self.first, "game_started")
        state = self.wait_for(self.first, "game_state", lambda m: m["tick"] >= 2)
        self.assertEqual(state["phase"], "running")
        bird = state["birds"][state["bird_id"]]
        self.assertLessEqual(bird["velocity_x"] * 24, 120)
        self.assertLessEqual(bird["position_x"], state["tick"] * 5)
        self.first.send({"type": "game_begin", "speed": 1})
        self.wait_for(self.first, "error")


if __name__ == "__main__":
    unittest.main()
