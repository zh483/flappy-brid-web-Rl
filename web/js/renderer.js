import { WORLD, birdScreenY, cameraXFor, clamp, getSkin } from "./config.js";

export function interpolateBird(a, b, amount) {
  // 复活是瞬间换位置，不能把它画成从死亡位置慢慢飘回去。
  if (!a?.present || !b?.present || a.respawn_ms > 0 || b.respawn_ms > 0) return b;
  return { ...b,
    position_x: a.position_x + (b.position_x - a.position_x) * amount,
    position_y: a.position_y + (b.position_y - a.position_y) * amount,
  };
}

export class GameRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.frames = [];
    this.birdId = null;
    this.previewSkin = 0;
    this.reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas);
    this.resize();
    this.animate = this.animate.bind(this);
    this.animationId = requestAnimationFrame(this.animate);
  }

  resize() {
    const bounds = this.canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.max(1, Math.round(bounds.width * dpr));
    this.canvas.height = Math.max(1, Math.round(bounds.height * dpr));
  }

  reset() {
    this.frames = [];
    this.birdId = null;
  }

  setSnapshot(snapshot) {
    this.birdId = snapshot.bird_id;
    this.frames.push({ state: snapshot, receivedAt: performance.now() });
    if (this.frames.length > 6) this.frames.shift();
  }

  currentFrame(now) {
    if (!this.frames.length) return null;
    const newest = this.frames.at(-1).state;
    if (newest.phase !== "running" || this.reducedMotion) return newest;

    // 只在已收到的两个状态之间插值；不预测位置，不运行客户端物理。
    const displayTime = now - 50;
    while (this.frames.length > 2 && this.frames[1].receivedAt <= displayTime) this.frames.shift();
    const first = this.frames[0];
    const second = this.frames[1] ?? first;
    const duration = second.receivedAt - first.receivedAt;
    const amount = duration > 0 ? clamp((displayTime - first.receivedAt) / duration, 0, 1) : 1;
    return { ...second.state, birds: second.state.birds.map((bird, i) =>
      interpolateBird(first.state.birds[i], bird, amount)) };
  }

  animate(now) {
    this.draw(this.currentFrame(now), now);
    this.animationId = requestAnimationFrame(this.animate);
  }

  draw(state, now) {
    const ctx = this.ctx;
    ctx.setTransform(this.canvas.width / WORLD.cameraWidth, 0, 0,
      this.canvas.height / WORLD.cameraHeight, 0, 0);
    ctx.clearRect(0, 0, 600, 400);
    const own = state?.birds[this.birdId];
    const camera = own?.present ? cameraXFor(own.position_x) : 0;
    this.drawLandscape(camera);

    if (!state) {
      this.drawPipe(453, 265, 125);
      this.drawPipe(590, 235, 95);
      this.drawBird({ position_x: 123, position_y: 172, character: this.previewSkin,
        velocity_y: 0, respawn_ms: 0, invincible_ms: 0 }, 0, true, now, true);
      this.drawBird({ position_x: 74, position_y: 134, character: 1,
        velocity_y: 0, respawn_ms: 0, invincible_ms: 0 }, 0, false, now, true);
      return;
    }

    for (const pipe of state.pipes) {
      const x = pipe.x - camera;
      if (x + WORLD.pipeWidth >= 0 && x <= 600) this.drawPipe(x, pipe.up, pipe.down);
    }
    if (WORLD.width - camera <= 600) this.drawFinish(WORLD.width - camera);

    // 自己最后绘制，起点重叠时也能看见自己的颜色和描边。
    for (const bird of state.birds) {
      if (bird.present && bird.bird_id !== this.birdId) this.drawBird(bird, camera, false, now);
    }
    if (own?.present) this.drawBird(own, camera, true, now);
  }

  drawLandscape(camera) {
    const ctx = this.ctx;
    const sky = ctx.createLinearGradient(0, 0, 0, 400);
    sky.addColorStop(0, "#d3eee7");
    sky.addColorStop(.75, "#e5f2df");
    sky.addColorStop(1, "#eff2cf");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, 600, 400);
    ctx.fillStyle = "#f7f4cf";
    ctx.beginPath(); ctx.arc(490, 79, 27, 0, Math.PI * 2); ctx.fill();
    this.drawCloud(80 - (camera * .08 % 720), 76, 1);
    this.drawCloud(340 - (camera * .05 % 720), 119, .75);
    this.drawCloud(620 - (camera * .08 % 720), 64, .8);

    const hills = (color, height, offset) => {
      ctx.fillStyle = color;
      ctx.beginPath(); ctx.moveTo(0, 400);
      for (let x = -70; x <= 680; x += 10) {
        ctx.lineTo(x, height + Math.sin((x + camera * offset) / 88) * 22 + Math.cos(x / 53) * 7);
      }
      ctx.lineTo(680, 400); ctx.closePath(); ctx.fill();
    };
    hills("#c7dcb4", 337, .15);
    hills("#b3ce9e", 370, .3);
    ctx.fillStyle = "#97b27f";
    ctx.fillRect(0, 396, 600, 4);
    ctx.globalAlpha = .18;
    ctx.fillStyle = "#f7ffe8";
    for (let x = 0; x < 600; x += 23) ctx.fillRect(x - (camera * .3 % 23), 397, 10, 2);
    ctx.globalAlpha = 1;
  }

  drawCloud(x, y, scale) {
    const ctx = this.ctx;
    ctx.save(); ctx.translate(x, y); ctx.scale(scale, scale);
    ctx.fillStyle = "#f9fbeeaa";
    ctx.beginPath(); ctx.roundRect(-30, 0, 78, 14, 7); ctx.fill();
    ctx.beginPath(); ctx.arc(-4, 0, 18, Math.PI, 0); ctx.arc(20, 0, 12, Math.PI, 0); ctx.fill();
    ctx.restore();
  }

  drawPipe(x, up, down) {
    const ctx = this.ctx;
    const topHeight = WORLD.height - up;
    const bottomY = WORLD.height - down;
    const segment = (y, height, capY) => {
      if (height <= 0) return;
      ctx.fillStyle = "#8eaf69";
      ctx.fillRect(x + 3, y, 44, height);
      ctx.fillStyle = "#adca85";
      ctx.fillRect(x + 7, y, 8, height);
      ctx.fillStyle = "#7e9d5f";
      ctx.fillRect(x + 39, y, 7, height);
      ctx.strokeStyle = "#627d4f"; ctx.lineWidth = 1.5;
      ctx.strokeRect(x + 3, y - 1, 44, height + 2);
      ctx.fillStyle = "#a1bf79";
      ctx.fillRect(x, capY, 50, 12);
      ctx.strokeRect(x, capY, 50, 12);
      ctx.fillStyle = "#c0d99c"; ctx.fillRect(x + 3, capY + 2, 44, 2);
    };
    segment(0, topHeight, topHeight - 12);
    segment(bottomY, down, bottomY);
  }

  drawBird(bird, camera, isOwn, now, preview = false) {
    const x = bird.position_x - camera;
    const y = birdScreenY(bird.position_y);
    if (x < -35 || x > 635 || y < -50 || y > 430) return;
    const ctx = this.ctx;
    const skin = getSkin(bird.character);
    ctx.save(); ctx.translate(x + 12.5, y + 10);
    if (bird.respawn_ms > 0) ctx.globalAlpha = .3;
    else if (!isOwn) ctx.globalAlpha = .7;
    if (bird.invincible_ms > 0) {
      ctx.strokeStyle = "#fffbdd"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(0, 0, 20, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = "#fffbc63b"; ctx.fill();
    }
    if (isOwn) {
      ctx.shadowColor = "#faf8d9"; ctx.shadowBlur = 9;
      ctx.strokeStyle = "#fffce2"; ctx.lineWidth = 4;
      ctx.beginPath(); ctx.roundRect(-13, -10, 25, 20, 6); ctx.stroke();
      ctx.shadowBlur = 0;
    }
    ctx.fillStyle = skin.color; ctx.strokeStyle = "#536449"; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.roundRect(-12, -9, 23, 18, 6); ctx.fill(); ctx.stroke();
    ctx.fillStyle = skin.wing;
    const flap = this.reducedMotion ? 0 : Math.sin(now / 105) * 1.5;
    ctx.beginPath(); ctx.roundRect(-11, flap, 11, 7, 3); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#fffdf2"; ctx.fillRect(3, -7, 6, 8);
    ctx.fillStyle = "#344630"; ctx.fillRect(6, -5, 2.5, 4);
    ctx.fillStyle = "#e7a169"; ctx.fillRect(7, 1, 6, 5); ctx.strokeRect(7, 1, 6, 5);
    ctx.restore();
    if (isOwn && !preview) {
      ctx.fillStyle = "#35523a"; ctx.font = "bold 8px sans-serif"; ctx.textAlign = "center";
      ctx.fillText("YOU", x + 12.5, y - 10);
    } else if (bird.is_bot && !preview) {
      ctx.fillStyle = "#35523a"; ctx.font = "bold 8px sans-serif"; ctx.textAlign = "center";
      ctx.fillText("AI", x + 12.5, y - 10);
    }
  }

  drawFinish(x) {
    const ctx = this.ctx;
    ctx.fillStyle = "#627653"; ctx.fillRect(x - 6, 0, 3, 400);
    for (let row = 0; row < 5; row++) {
      for (let col = 0; col < 4; col++) {
        ctx.fillStyle = (row + col) % 2 ? "#eef2da" : "#71865c";
        ctx.fillRect(x - 45 + col * 10, 63 + row * 10, 10, 10);
      }
    }
  }
}
