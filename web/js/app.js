import { SKINS, WORLD, birdIcon, clamp, getSkin } from "./config.js";
import { applyServerMessage, botCapacity, canJump, createInitialState, gameBeginMessage, ownBird } from "./protocol.js";
import { GameConnection } from "./network.js";
import { GameRenderer } from "./renderer.js";

// app 是调度者：用户操作 → 发消息；服务器消息 → 更新状态 → 更新界面。
// 游戏规则仍然只在 C++ 引擎里运行。
const element = (id) => document.getElementById(id);
const canvas = element("game-canvas");
const renderer = new GameRenderer(canvas);
let state = createInitialState();
let connectionStatus = "disconnected";
let selectedSkin = 0;
let confirmedSkin = 0;
let skinPending = false;
let startPending = false;
let botSelectionInitialized = false;

function remember(key, value) {
  try { localStorage.setItem(key, value); } catch { /* 禁用存储时仍然可以玩。 */ }
}
function recall(key, fallback) {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
selectedSkin = getSkin(Number(recall("flappy.skin", "0"))).id;
confirmedSkin = selectedSkin;
element("server-url").value = recall("flappy.server", `${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname || "localhost"}:18080/ws`);

function logEvent(message, isError = false) {
  const item = document.createElement("li");
  item.classList.toggle("error", isError);
  const time = document.createElement("time");
  time.textContent = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  item.append(time, document.createTextNode(message));
  element("event-log").prepend(item);
  while (element("event-log").children.length > 30) element("event-log").lastChild.remove();
}

function notice(message = "", isError = false) {
  element("notice").hidden = !message;
  element("notice").textContent = message;
  element("notice").classList.toggle("error", isError);
}

function resetSession() {
  state = createInitialState();
  skinPending = false;
  startPending = false;
  botSelectionInitialized = false;
  element("bot-count").value = "0";
  renderer.reset();
}

const connection = new GameConnection({
  onStatus(status, reason) {
    connectionStatus = status;
    if (status === "connecting") logEvent("正在连接服务器…");
    if (status === "closed") {
      resetSession();
      notice(`${reason}。若无法加入，请检查服务器、人数和本局是否已经开始。`, true);
      logEvent(reason, true);
    }
    updateUI();
  },
  onProblem(message) {
    notice(message, true);
    logEvent(message, true);
  },
  onMessage: handleMessage,
});

// 按消息种类拆开处理，后续新增消息时只需增加一个分支。
function handleMessage(message) {
  const previousPhase = state.phase;
  const next = applyServerMessage(state, message);
  if (message.type === "game_state" && next === state) return;
  state = next;
  switch (message.type) {
    case "connected":
      connectionStatus = "online";
      skinPending = connection.send({ type: "select_skin", skin: selectedSkin });
      notice("连接成功。等朋友都加入后，任意一人点击开始即可。");
      logEvent(`已加入，玩家编号 P${pad(state.clientId)}。`);
      break;
    case "skin_selected":
      selectedSkin = getSkin(message.skin_id).id;
      confirmedSkin = selectedSkin;
      skinPending = false;
      remember("flappy.skin", selectedSkin);
      logEvent(`皮肤已确认：${getSkin(selectedSkin).name}。`);
      break;
    case "lobby":
      if (!botSelectionInitialized) {
        element("bot-count").value = String(Math.min(state.defaultBots, botCapacity(state)));
        botSelectionInitialized = true;
      }
      break;
    case "game_started":
      renderer.reset();
      startPending = false;
      skinPending = false;
      selectedSkin = getSkin(message.skin_id).id;
      confirmedSkin = selectedSkin;
      notice();
      logEvent(`开始飞行，你的小鸟编号是 B${pad(state.birdId)}，本局有 ${message.bot_count ?? 0} 只 AI。`);
      canvas.focus({ preventScroll: true });
      break;
    case "game_state":
      renderer.setSnapshot(message);
      if (message.phase === "finished" && previousPhase !== "finished") {
        notice("本局已经结束。可以重新选择皮肤和难度，再飞一次。");
        logEvent("本局结束。");
      }
      break;
    case "error":
      skinPending = false;
      startPending = false;
      selectedSkin = confirmedSkin;
      notice(typeof message.message === "string" ? message.message : "服务器拒绝了这次操作。", true);
      logEvent(typeof message.message === "string" ? message.message : "服务器返回错误。", true);
      break;
    default:
      logEvent(`收到暂未使用的消息：${message.type}`);
  }
  updateUI();
}

const pad = (value) => String(value).padStart(2, "0");

// 这些节点只创建一次。游戏每次更新时复用它们，避免重复注册事件。
const skinButtons = SKINS.map((skin) => {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "skin-button";
  button.title = skin.name;
  button.setAttribute("aria-label", skin.name);
  button.innerHTML = birdIcon(skin.id); // SVG 只来自本地固定颜色，不接收服务器 HTML。
  button.addEventListener("click", () => {
    if (state.phase === "running" || skinPending || startPending) return;
    selectedSkin = skin.id;
    if (state.connected) skinPending = connection.send({ type: "select_skin", skin: skin.id });
    else remember("flappy.skin", skin.id);
    updateUI();
  });
  element("skin-grid").append(button);
  return button;
});

const crewSlots = Array.from({ length: 8 }, () => {
  const slot = document.createElement("div");
  slot.className = "crew-slot";
  const icon = document.createElement("span");
  icon.className = "slot-icon";
  icon.setAttribute("aria-hidden", "true");
  const name = document.createElement("strong");
  const status = document.createElement("span");
  status.className = "crew-status";
  slot.append(icon, name, status);
  element("crew-grid").append(slot);
  return { slot, icon, name, status, skin: null };
});

function updateCrew() {
  const birds = state.snapshot?.birds;
  const count = birds?.filter((bird) => bird.present).length ?? 0;
  const botCount = birds?.filter((bird) => bird.present && bird.is_bot).length ?? 0;
  element("player-count").textContent = birds ? `${count - botCount} 位玩家 + ${botCount} 只 AI` : state.connected ? `${state.playerCount ?? 1} 位玩家已连接` : "还没有玩家起飞";
  element("crew-caption").textContent = birds ? "描边卡片是你 · AI 为机器人" : "开局后显示玩家与 AI";
  crewSlots.forEach((view, index) => {
    const bird = birds?.[index];
    // 开局前服务器没有广播全体名单，只显示已确认的自己，不猜测人数。
    const lobbySelf = !birds && state.connected && index === 0;
    const present = Boolean(bird?.present || lobbySelf);
    const own = lobbySelf || (present && index === state.birdId);
    const skin = present ? getSkin(lobbySelf ? selectedSkin : bird.character).id : null;
    view.slot.classList.toggle("present", present);
    view.slot.classList.toggle("own", own);
    if (skin !== view.skin) {
      view.icon.innerHTML = skin === null ? "+" : birdIcon(skin);
      view.skin = skin;
    } else if (skin === null) view.icon.textContent = "+";
    view.name.textContent = present ? `${bird?.is_bot ? "AI · " : ""}${lobbySelf ? `P${pad(state.clientId)}` : `B${pad(index)}`}${own ? " · 你" : ""}` : "空位";
    view.status.textContent = lobbySelf ? "已连接" : !present ? "等待伙伴" : bird.respawn_ms > 0 ? "等待复活" : bird.invincible_ms > 0 ? "短暂无敌" : state.phase === "finished" ? "本局结束" : "飞行中";
  });
}

function updateUI() {
  const bird = ownBird(state);
  const running = state.phase === "running";
  const connecting = ["connecting", "open"].includes(connectionStatus);
  const busy = connecting || state.connected;
  const mayStart = state.connected && !running && !skinPending && !startPending;
  const respawning = running && bird?.respawn_ms > 0;
  const finished = state.phase === "finished";
  renderer.previewSkin = selectedSkin;

  element("connection-badge").textContent = state.connected ? "已连接" : connecting ? "连接中" : "未连接";
  element("connection-badge").className = `connection-badge ${state.connected ? "online" : connecting ? "connecting" : ""}`;
  element("server-url").disabled = busy;
  element("connect-button").disabled = busy;
  element("connect-button").textContent = state.connected ? "已加入这片天空 ✓" : connecting ? "正在连接…" : "连接服务器 →";
  element("disconnect-button").hidden = !busy;
  element("client-number").textContent = state.connected ? `P${pad(state.clientId)}` : "尚未分配";
  element("skin-name").textContent = getSkin(selectedSkin).name;
  element("skin-help").textContent = running ? "飞行期间不能更换皮肤。" : skinPending ? "正在等待服务器确认颜色…" : state.connected ? "颜色已确认，准备好就开始吧。" : "先选好颜色，连接后自动确认。";
  skinButtons.forEach((button, index) => {
    button.setAttribute("aria-pressed", String(SKINS[index].id === selectedSkin));
    button.disabled = running || skinPending || startPending;
  });
  element("difficulty").disabled = running || startPending;
  const botLimit = botCapacity(state);
  const botSelect = element("bot-count");
  for (const option of botSelect.options) option.disabled = Number(option.value) > botLimit;
  if (Number(botSelect.value) > botLimit) botSelect.value = String(botLimit);
  botSelect.disabled = !mayStart || !state.botAvailable || botLimit === 0;
  element("bot-help").textContent = !state.connected ? "连接后可添加 AI，一起飞向终点。" :
    !state.botAvailable ? "服务器暂未提供机器人，仍可与朋友游玩。" :
    running ? "本局 AI 已确定，下局可调整数量。" :
    botLimit === 0 ? "真人已占满 8 个位置，本局无法添加 AI。" :
    `当前可添加 ${botLimit} 只 AI；相同状态下，AI 可能重叠飞行。`;
  element("start-button").disabled = !mayStart;
  element("start-button").textContent = startPending ? "正在开局…" : finished ? "再飞一局 ↗" : "开始这场飞行 ↗";
  element("jump-button").disabled = !canJump(state);
  element("game-dot").classList.toggle("online", state.connected);
  element("game-status").textContent = respawning ? "等待复活" : running ? "正在飞行" : finished ? "本局结束" : state.connected ? "准备起飞" : "等待起飞";
  element("stage-badge").textContent = running ? `B${pad(state.birdId)} · ${respawning ? "等待复活" : "正在飞行"}` : finished ? "本局已经结束" : "一场新的冒险";
  const distance = Math.round(clamp(bird?.position_x ?? 0, 0, WORLD.width));
  element("stage-distance").textContent = `${distance.toLocaleString("en-US")} / 40,000`;
  element("flight-progress").setAttribute("aria-valuenow", distance);
  element("progress-fill").style.width = `${distance / WORLD.width * 100}%`;
  element("own-bird-label").hidden = !state.snapshot;
  element("debug-summary").textContent = state.snapshot ? `tick ${state.snapshot.tick} · ${state.phase}` : state.connected ? `P${pad(state.clientId)} · 已连接` : connecting ? "连接中" : "等待连接";

  element("stage-overlay").hidden = running && !respawning;
  element("stage-overlay").classList.toggle("respawning", Boolean(respawning));
  element("stage-action").hidden = Boolean(respawning);
  element("stage-action").disabled = connecting || (state.connected && !mayStart);
  element("overlay-eyebrow").textContent = respawning ? "TAKE A LITTLE BREATH" : finished ? "UNTIL THE NEXT FLIGHT" : "YOUR NEXT LITTLE ADVENTURE";
  element("overlay-title").textContent = respawning ? `${(bird.respawn_ms / 1000).toFixed(1)} 秒后，再次起飞。` : finished ? "这一程，辛苦啦。" : connecting ? "正在寻找这片天空…" : state.connected ? "选好颜色，一起出发。" : "准备好，向天空出发。";
  element("overlay-description").textContent = respawning ? "碰到了障碍，休息一下。复活后会有短暂无敌。" : finished ? "调整一下节奏，和朋友再来一局。" : state.connected ? "等朋友都连接好，再点击开始。" : "先连接服务器，再和朋友一起开始。";
  element("stage-action").textContent = startPending ? "正在开局…" : connecting ? "正在连接…" : finished ? "再飞一次 ↗" : state.connected ? "开始飞行 ↗" : "连接并准备 ↗";
  updateCrew();
}

function connect() {
  if (state.connected || ["connecting", "open"].includes(connectionStatus)) return;
  try {
    resetSession();
    const address = connection.connect(element("server-url").value);
    element("server-url").value = address;
    remember("flappy.server", address);
    notice();
  } catch (error) {
    connectionStatus = "disconnected";
    notice(error.message, true);
    logEvent(error.message, true);
    updateUI();
  }
}

function startGame() {
  if (!state.connected || state.phase === "running" || startPending || skinPending) return;
  try {
    startPending = connection.send(gameBeginMessage(state, Number(element("difficulty").value), Number(element("bot-count").value)));
  } catch (error) { notice(error.message, true); }
  updateUI();
}

function jump() {
  if (canJump(state)) connection.send({ type: "jump" });
}

element("connection-form").addEventListener("submit", (event) => { event.preventDefault(); connect(); });
element("disconnect-button").addEventListener("click", () => {
  connection.disconnect();
  connectionStatus = "disconnected";
  resetSession();
  notice("你已离开。重新连接后可以加入下一局。");
  logEvent("已主动断开连接。");
  updateUI();
});
element("start-button").addEventListener("click", startGame);
element("stage-action").addEventListener("click", () => state.connected ? startGame() : connect());
element("jump-button").addEventListener("click", () => { jump(); canvas.focus({ preventScroll: true }); });
canvas.addEventListener("pointerdown", () => { canvas.focus({ preventScroll: true }); jump(); });
window.addEventListener("keydown", (event) => {
  if (!["Space", "KeyW", "ArrowUp"].includes(event.code) ||
      event.target.closest?.("input, select, textarea, button, [contenteditable=true]") || !canJump(state)) return;
  event.preventDefault();
  if (!event.repeat) jump(); // 一次点按发送一次，长按不重复发送。
});
window.addEventListener("beforeunload", () => connection.disconnect());
logEvent("网页已就绪，等待连接服务器。");
updateUI();
