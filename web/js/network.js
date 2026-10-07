import { normalizeServerUrl, parseServerMessage } from "./protocol.js";

// WebSocket 收发单独放在这里。它不绘图，也不决定游戏规则。
export class GameConnection {
  constructor({ onStatus, onMessage, onProblem }) {
    this.socket = null;
    this.callbacks = { onStatus, onMessage, onProblem };
  }

  connect(address) {
    const url = normalizeServerUrl(address);
    this.disconnect();
    const socket = new WebSocket(url);
    this.socket = socket;
    this.callbacks.onStatus("connecting");

    // 重连后，旧 socket 的迟到事件不能覆盖新连接的界面。
    const isCurrent = () => this.socket === socket;
    socket.addEventListener("open", () => {
      if (isCurrent()) this.callbacks.onStatus("open");
    });
    socket.addEventListener("message", (event) => {
      if (!isCurrent()) return;
      try {
        this.callbacks.onMessage(parseServerMessage(event.data));
      } catch (error) {
        this.callbacks.onProblem(error.message);
      }
    });
    socket.addEventListener("error", () => {
      if (isCurrent()) this.callbacks.onProblem("连接未能完成。请确认服务器正在运行，房间未满且游戏尚未开始。");
    });
    socket.addEventListener("close", (event) => {
      if (!isCurrent()) return;
      this.socket = null;
      this.callbacks.onStatus("closed", event.reason || (event.code === 1000 ? "连接已关闭" : "连接中断，请重新连接"));
    });
    return url;
  }

  send(message) {
    if (this.socket?.readyState !== WebSocket.OPEN) return false;
    try {
      this.socket.send(JSON.stringify(message));
      return true;
    } catch (error) {
      this.callbacks.onProblem(error.message);
      return false;
    }
  }

  disconnect() {
    const socket = this.socket;
    this.socket = null;
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, "玩家主动离开");
  }
}
