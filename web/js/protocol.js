// 这一层只处理消息格式。新增后端消息时，从这里开始改。
export function normalizeServerUrl(value) {
  let url;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error("请输入完整地址，例如 ws://localhost:18080/ws");
  }
  if (!["ws:", "wss:"].includes(url.protocol) || url.username || url.password) {
    throw new Error("服务器地址需要以 ws:// 或 wss:// 开头，且不包含账号密码。");
  }
  if (url.hash) throw new Error("WebSocket 地址不能包含 # 片段。");
  if (url.pathname === "/") url.pathname = "/ws";
  return url.href;
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isSlot(value, allowMissing = false) {
  return Number.isInteger(value) && value >= (allowMissing ? -1 : 0) && value < 8;
}

function finiteFields(object, fields) {
  return isObject(object) && fields.every((field) => Number.isFinite(object[field]));
}

export function parseServerMessage(text) {
  let message;
  try {
    message = JSON.parse(text);
  } catch {
    throw new Error("服务器发来的消息不是合法 JSON。");
  }
  if (!isObject(message) || typeof message.type !== "string") {
    throw new Error("服务器消息缺少 type 字段。");
  }
  if (message.type === "connected" && !isSlot(message.client_id)) {
    throw new Error("服务器分配了无效的玩家编号。");
  }
  if (message.type === "lobby" &&
      (!Number.isInteger(message.player_count) || message.player_count < 1 || message.player_count > 8 ||
       typeof message.bot_available !== "boolean" || !Number.isInteger(message.default_bots) ||
       message.default_bots < 0 || message.default_bots > 7)) {
    throw new Error("大厅的玩家数量或机器人状态无效。");
  }
  if (message.type === "game_started" &&
      (!isSlot(message.client_id) || !isSlot(message.bird_id))) {
    throw new Error("开始消息中的玩家编号或鸟编号无效。");
  }
  if (["game_started", "game_state"].includes(message.type) && message.bot_count !== undefined &&
      (!Number.isInteger(message.bot_count) || message.bot_count < 0 || message.bot_count > 7)) {
    throw new Error("服务器的机器人数量无效。");
  }
  if (message.type === "game_state") {
    if (!Number.isSafeInteger(message.tick) || message.tick < 0 ||
        !["idle", "running", "finished"].includes(message.phase) ||
        !isSlot(message.client_id) || !isSlot(message.bird_id, true) ||
        !Number.isFinite(message.speed) ||
        !Array.isArray(message.birds) || message.birds.length !== 8 ||
        !Array.isArray(message.pipes)) {
      throw new Error("游戏状态的字段不完整或类型不正确。");
    }
    const birdFields = ["position_x", "position_y", "velocity_x", "velocity_y",
      "respawn_ms", "invincible_ms", "character"];
    if (!message.birds.every((bird, index) => finiteFields(bird, birdFields) &&
        bird.bird_id === index && typeof bird.present === "boolean" &&
        (bird.is_bot === undefined || typeof bird.is_bot === "boolean")) ||
        !message.pipes.every((pipe) => finiteFields(pipe, ["x", "up", "down"]))) {
      throw new Error("小鸟或管道的数据不完整。");
    }
  }
  return message;
}

export function createInitialState() {
  return { connected: false, clientId: null, birdId: null, phase: "idle", snapshot: null,
    playerCount: null, botAvailable: false, defaultBots: 0 };
}

export function botCapacity(state) {
  return state.connected && state.botAvailable && Number.isInteger(state.playerCount)
    ? Math.max(0, 8 - state.playerCount) : 0;
}

export function gameBeginMessage(state, speed, bots) {
  if (!state.connected || state.phase === "running") throw new Error("请在连接后、开局前设置机器人。");
  if (!Number.isInteger(bots) || bots < 0 || bots > botCapacity(state))
    throw new Error("机器人数量超过当前可用空位。");
  return { type: "game_begin", speed, bots };
}

// 返回新状态，不修改旧对象，方便单独测试，也方便你观察每条消息的影响。
export function applyServerMessage(state, message) {
  switch (message.type) {
    case "connected":
      return { ...createInitialState(), connected: true, clientId: message.client_id };
    case "game_started":
      return { ...state, birdId: message.bird_id, phase: "running", snapshot: null };
    case "lobby":
      return { ...state, playerCount: message.player_count, botAvailable: message.bot_available,
        defaultBots: message.default_bots };
    case "game_state":
      // 同一局丢弃过时状态；game_started 已经清空了上一局的 snapshot。
      if (state.snapshot && message.tick < state.snapshot.tick) return state;
      return { ...state, clientId: message.client_id, birdId: message.bird_id,
        phase: message.phase, snapshot: message };
    default:
      return state;
  }
}

export function ownBird(state) {
  if (!isSlot(state.birdId)) return null;
  const bird = state.snapshot?.birds[state.birdId];
  return bird?.present ? bird : null;
}

export function canJump(state) {
  const bird = ownBird(state);
  return state.connected && state.phase === "running" && bird !== null && bird.respawn_ms <= 0;
}
