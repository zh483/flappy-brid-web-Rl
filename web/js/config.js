// 这些数值对应 engine-c/config.cpp。前端只用它们绘图，不计算碰撞。
export const WORLD = Object.freeze({
  cameraWidth: 600,
  cameraHeight: 400,
  width: 40000,
  height: 400,
  birdWidth: 25,
  birdHeight: 20,
  pipeWidth: 50,
  stepSeconds: 1 / 24,
});

export const SKINS = Object.freeze([
  { id: 0, name: "柠檬黄", color: "#f3ca57", wing: "#fff0a4" },
  { id: 1, name: "薄荷绿", color: "#88b88a", wing: "#c9e4ad" },
  { id: 2, name: "珊瑚红", color: "#e99980", wing: "#ffd4b0" },
  { id: 3, name: "天空蓝", color: "#85b5c9", wing: "#c7e2e8" },
  { id: 4, name: "奶油白", color: "#e6dbc0", wing: "#fff6dc" },
  { id: 5, name: "葡萄紫", color: "#b3a0c7", wing: "#dfccea" },
]);

export function getSkin(id) {
  return SKINS.find((skin) => skin.id === id) ?? SKINS[0];
}

export function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

// C++ 的 y 向上增大；Canvas 的 y 向下增大。
export function birdScreenY(worldY) {
  return WORLD.height - worldY - WORLD.birdHeight;
}

export function cameraXFor(birdX) {
  return clamp(birdX - WORLD.cameraWidth / 3, 0, WORLD.width - WORLD.cameraWidth);
}

// 皮肤图标由矢量形状生成，颜色只来自上面的固定配置。
export function birdIcon(id) {
  const skin = getSkin(id);
  return `<svg viewBox="0 0 35 28" aria-hidden="true"><path d="M3 10h5V5h17v5h4v12H8v-5H3z" fill="${skin.color}" stroke="#526246" stroke-width="1.6" stroke-linejoin="round"/><path d="M7 14h12v7H7z" fill="${skin.wing}"/><path d="M26 15h7v6h-7z" fill="#e7a16b" stroke="#526246" stroke-width="1.4"/><path d="M22 9h4v5h-4z" fill="#fffdf2"/><path d="M24 10h2v3h-2z" fill="#34432e"/></svg>`;
}
