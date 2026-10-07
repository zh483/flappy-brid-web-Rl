# 网页前端

原生 HTML + CSS + JavaScript，使用 Canvas 绘图，没有第三方前端依赖。
服务器计算物理、碰撞、复活和终点；网页只发送操作并显示状态。

## 运行

在项目根目录打开两个终端。

终端一，运行已经编译好的游戏服务器：

```powershell
.\saver\build\Release\flappy_server.exe
```

终端二，运行网页服务器：

```powershell
node .\web\dev-server.js
```

浏览器打开 **http://localhost:8000**，点击连接，选择皮肤，再开始。
也可以用 `npm --prefix web start` 启动网页，无需 `npm install`。
不要直接双击 HTML；JavaScript 模块需要通过 HTTP 加载。

测试两人联机时，先打开两个标签页，**两边都连接后再开始**。
开局后服务器会拒绝新连接。空格、W、↑、点击画面或“跳一下”按钮均可跳跃。
一次点按对应一次操作，长按键盘不会连续跳跃。

另一台设备在同一局域网中可以访问 `http://服务器电脑的局域网IP:8000`，
WebSocket 地址填写 `ws://服务器电脑的局域网IP:18080/ws`。
需要电脑防火墙允许这两个端口；手机上的 localhost 指的是手机本身。
这是本地开发服务器，公网部署还需要 HTTPS/WSS、访问控制等部署工作。

如果网页端口被占用，可以先设置 `$env:PORT = 8001` 再启动网页服务器。

## 按这个顺序阅读

1. `index.html`：页面有哪些元素，id 怎样让 JavaScript 找到它们。
2. `styles.css`：布局、颜色、按钮状态与手机适配。
3. `js/app.js`：入口。先看末尾的事件监听，再看 `handleMessage`、`updateUI`。
4. `js/network.js`：连接 WebSocket，接收和发送 JSON。
5. `js/protocol.js`：消息检查、自己的鸟、是否允许跳跃。
6. `js/renderer.js`：把游戏坐标换成画布坐标，再绘制。
7. `js/config.js`：画面尺寸、皮肤颜色等显示设置。

先练习修改背景颜色、按钮文案或皮肤颜色；再尝试增加一个显示字段，例如显示自己的速度。
每次只改一个小功能，在浏览器确认结果后再继续。

## 一次跳跃经过哪些地方

`keydown / pointerdown` → `app.js: jump()` → `network.js: send()` →
C++ 接收 `{"type":"jump"}` → 下一次固定更新使用操作 →
广播 `game_state` → `app.js: handleMessage()` → `renderer.js` 绘图。

网页不会等待每个客户端回复才更新。绘图采用收到的两个状态之间的约 50ms 插值，
只改善显示平滑度，不在客户端额外计算物理，也不预测网络尚未传来的位置。

## 与引擎保持一致的地方

- 摄像头 600×400，世界 40000×400，小鸟 25×20，管道宽 50。
- 引擎 y 向上增加，画布 y 向下增加。小鸟屏幕 y = `400 - position_y - 20`。
- 摄像头 x = `clamp(自己的 x - 200, 0, 39400)`。
- `client_id` 是连接编号，`bird_id` 是鸟池编号，两者可能不同。
- 死亡倒计时与无敌时间直接显示服务器值；没有本地倒计时修改引擎状态。
- 服务器尚未提供大厅全员名单，因此开局前只显示自己已经连接。
- 皮肤由前端绘制为 6 种颜色。修改引擎尺寸时，也要同步更新 `js/config.js`。

消息协议见 [服务器说明](../saver/README.md)。连接记录可在网页底部展开查看。

## 测试

```powershell
node --test web/tests/protocol.test.js
```

检查消息格式、玩家与鸟的映射、新一局 tick 重置、摄像头和复活插值行为。
