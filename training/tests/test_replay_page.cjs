// Run with Node.js. Pass an exported HTML path to also check its playback controls.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const path = require("node:path");

class Element {
  constructor(tag = "div") {
    this.tag = tag; this.children = []; this.events = {};
    this.value = ""; this.textContent = ""; this.hidden = false;
  }
  append(...items) { this.children.push(...items); }
  setAttribute() {}
  addEventListener(name, callback) { this.events[name] = callback; }
  createTHead() { const element = new Element(); this.append(element); return element; }
  createTBody() { return this.createTHead(); }
  insertRow() { return this.createTHead(); }
  insertCell() { return this.createTHead(); }
  getContext() { return new Proxy({}, { get: () => () => {}, set: () => true }); }
}

function load(html) {
  const elements = {};
  for (const match of html.matchAll(/id="([^"]+)"/g)) elements[match[1]] = new Element();
  elements["replay-data"].textContent = html.match(/<script id="replay-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
  elements.speed.value = "16";
  const events = {};
  const context = vm.createContext({
    document: {
      getElementById: id => { assert.ok(elements[id], `Missing element: ${id}`); return elements[id]; },
      createElement: tag => new Element(tag), documentElement: new Element(),
    },
    window: { addEventListener: (name, callback) => { events[name] = callback; } },
    getComputedStyle: () => ({ getPropertyValue: () => "#000000" }),
    requestAnimationFrame: () => {},
  });
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  return { elements, events };
}

const template = fs.readFileSync(path.join(__dirname, "../replay_template.html"), "utf8");
const missing = load(template).elements;
assert.match(missing["load-status"].textContent, /comparison-replay\.html/);
assert.equal(missing["load-status"].hidden, false);
assert.equal(missing.play.disabled, true);

const invalid = load(template.replace("__REPLAY_DATA__", "{invalid")).elements;
assert.match(invalid["load-status"].textContent, /回放加载失败/);
assert.equal(invalid["load-status"].hidden, false);

if (process.argv[2]) {
  const html = fs.readFileSync(process.argv[2], "utf8");
  const data = JSON.parse(html.match(/<script id="replay-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  const { elements, events } = load(html);
  assert.equal(elements["load-status"].hidden, true, elements["load-status"].textContent);
  assert.equal(elements.metrics.children.length, data.models.length);
  if (data.models[0].evaluation) {
    assert.equal(elements.episodes.children[1].children.length, data.models[0].evaluation.episodes.length);
  }
  const outcome = model => elements.players.children[model].children[2].children[2].textContent;
  data.seeds.forEach((_, seedIndex) => {
    elements.seed.value = String(seedIndex); elements.seed.events.change();
    assert.equal(elements.seek.value, 0);
    const maxStep = Math.max(...data.replays.map(model => model[seedIndex].result.engine_steps));
    elements.seek.value = String(maxStep); elements.seek.events.input();
    data.replays.forEach((model, index) => {
      const result = model[seedIndex].result;
      assert.equal(outcome(index), result.is_success ? "已通关" : result.crashed ? "已碰撞" : "时间上限");
    });
  });
  elements.restart.events.click();
  assert.equal(elements.seek.value, 0);
  elements.play.events.click();
  assert.equal(elements.play.textContent, "暂停");
  events.error({ message: "test runtime error" });
  assert.equal(elements["load-status"].hidden, false);
  assert.match(elements["load-status"].textContent, /test runtime error/);
}
console.log("Replay page checks passed.");
