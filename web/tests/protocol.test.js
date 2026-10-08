import test from "node:test";
import assert from "node:assert/strict";
import { applyServerMessage, botCapacity, canJump, createInitialState, gameBeginMessage, normalizeServerUrl, ownBird, parseServerMessage } from "../js/protocol.js";
import { birdScreenY, cameraXFor } from "../js/config.js";
import { interpolateBird } from "../js/renderer.js";

function snapshot(tick = 0) {
  return { type: "game_state", tick, phase: "running", speed: 1, client_id: 0, bird_id: 3,
    pipes: [{ x: 500, up: 250, down: 110 }],
    birds: Array.from({ length: 8 }, (_, i) => ({ bird_id: i, present: i === 3,
      character: 0, position_x: 0, position_y: 200, velocity_x: 1, velocity_y: 0,
      respawn_ms: 0, invincible_ms: 0 })) };
}

test("地址补全 /ws，拒绝 HTTP 和带账号密码的地址", () => {
  assert.equal(normalizeServerUrl(" ws://localhost:18080 "), "ws://localhost:18080/ws");
  assert.equal(normalizeServerUrl("wss://example.com/game"), "wss://example.com/game");
  for (const address of ["localhost", "http://localhost", "ws://user:password@localhost", "ws://localhost/#a"]) {
    assert.throws(() => normalizeServerUrl(address));
  }
});

test("消息检查拒绝坏 JSON、空值、缺失鸟和无穷坐标", () => {
  for (const text of ["{", "null", "[]", '{"type":"connected","client_id":8}']) {
    assert.throws(() => parseServerMessage(text));
  }
  assert.deepEqual(parseServerMessage(JSON.stringify(snapshot())), snapshot());
  const invalid = snapshot();
  invalid.birds.pop();
  assert.throws(() => parseServerMessage(JSON.stringify(invalid)));
  const badCoordinate = snapshot();
  badCoordinate.birds[3].position_y = null;
  assert.throws(() => parseServerMessage(JSON.stringify(badCoordinate)));
});

test("客户端编号和鸟编号不同，跳跃仍然定位自己的鸟", () => {
  let state = applyServerMessage(createInitialState(), { type: "connected", client_id: 0 });
  state = applyServerMessage(state, snapshot());
  assert.equal(ownBird(state).bird_id, 3);
  assert.equal(canJump(state), true);
  const dead = snapshot(1);
  dead.birds[3].respawn_ms = 5000;
  assert.equal(canJump(applyServerMessage(state, dead)), false);
  assert.equal(canJump({ ...state, connected: false }), false);
  assert.equal(canJump({ ...state, phase: "finished" }), false);
});

test("同局忽略旧状态，新一局接受从 0 开始的 tick", () => {
  const state = applyServerMessage(createInitialState(), snapshot(500));
  assert.equal(applyServerMessage(state, snapshot(499)), state);
  const restarted = applyServerMessage(state, { type: "game_started", bird_id: 3, client_id: 0 });
  assert.equal(applyServerMessage(restarted, snapshot(0)).snapshot.tick, 0);
});

test("摄像头限制与纵坐标转换对应引擎的坐标系", () => {
  assert.equal(cameraXFor(0), 0);
  assert.equal(cameraXFor(600), 400);
  assert.equal(cameraXFor(40000), 39400);
  assert.equal(birdScreenY(0), 380);
  assert.equal(birdScreenY(380), 0);
});

test("正常状态之间插值，死亡与复活位置直接切换", () => {
  const start = snapshot().birds[3];
  const end = { ...start, position_x: 10, position_y: 220 };
  assert.equal(interpolateBird(start, end, .5).position_x, 5);
  assert.equal(interpolateBird(start, end, .5).position_y, 210);
  const dead = { ...start, respawn_ms: 5000 };
  assert.equal(interpolateBird(dead, end, .5), end);
  assert.equal(interpolateBird(start, dead, .5), dead);
});

test("机器人选项随在线真人数量限制，开局消息携带选择", () => {
  let state = applyServerMessage(createInitialState(), { type: "connected", client_id: 0 });
  const lobby = { type: "lobby", player_count: 2, bot_available: true, default_bots: 1 };
  parseServerMessage(JSON.stringify(lobby));
  state = applyServerMessage(state, lobby);
  assert.equal(botCapacity(state), 6);
  assert.deepEqual(gameBeginMessage(state, 1, 6), { type: "game_begin", speed: 1, bots: 6 });
  assert.throws(() => gameBeginMessage(state, 1, 7));
  assert.throws(() => gameBeginMessage(state, 1, -1));
  assert.equal(botCapacity({ ...state, playerCount: 8 }), 0);
  assert.equal(botCapacity({ ...state, botAvailable: false }), 0);
  assert.throws(() => gameBeginMessage({ ...state, phase: "running" }, 1, 1));
  for (const player_count of [0, 9, 1.5, "2"]) {
    assert.throws(() => parseServerMessage(JSON.stringify({ ...lobby, player_count })));
  }
});

test("AI 标记保留在画面状态中，自己的鸟仍由服务器分配", () => {
  const message = snapshot();
  message.birds[7].present = true;
  message.birds[7].is_bot = true;
  const parsed = parseServerMessage(JSON.stringify(message));
  const state = applyServerMessage(createInitialState(), parsed);
  assert.equal(state.snapshot.birds[7].is_bot, true);
  assert.equal(ownBird(state).bird_id, 3);
  message.birds[7].is_bot = "true";
  assert.throws(() => parseServerMessage(JSON.stringify(message)));
});
