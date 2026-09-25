// 页面只负责把 data.json 摊开：泳道、事件点、因果连线、不可比较对。
// 所有数字都来自 JSON，不在浏览器里重算因果。

const ROW_H = 56;
const DX = 30;
const PAD_L = 40;
const PAD_R = 60;
const PAD_T = 24;
const PAD_B = 30;

const response = await fetch('data.json');
const data = await response.json();

const laneRow = new Map();
data.lanes.forEach((lane, i) => laneRow.set(lane.node, i));

const xOf = (pos) => PAD_L + (pos - 1) * DX;
const yOf = (row) => PAD_T + row * ROW_H + ROW_H / 2;

const width = PAD_L + (data.shown - 1) * DX + PAD_R;
const height = PAD_T + data.lanes.length * ROW_H + PAD_B;

// 顶部统计：两个计数都摆出来
document.getElementById('stats').textContent =
  `事件共 ${data.total} 条，显示全序前 ${data.shown} 条（上限 ${data.limit}）；` +
  `可见事件中可比较 ${data.stats.comparable_pairs} 对，` +
  `不可比较 ${data.stats.incomparable_pairs} 对`;

// 左侧泳道标签，顺序与 lanes 一致
const labels = document.getElementById('lane-labels');
labels.style.paddingTop = `${PAD_T}px`;
labels.style.paddingBottom = `${PAD_B}px`;
for (const lane of data.lanes) {
  const div = document.createElement('div');
  div.className = 'lane-label';
  const name = document.createElement('span');
  name.className = 'node';
  name.textContent = lane.node;
  const first = document.createElement('span');
  first.className = 'first';
  first.textContent = `首个事件 #${lane.first_pos}`;
  div.append(name, first);
  labels.append(div);
}

const svg = document.getElementById('canvas');
svg.setAttribute('width', width);
svg.setAttribute('height', height);
const NS = 'http://www.w3.org/2000/svg';
const make = (tag, attrs) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
};

// 箭头标记
const defs = make('defs', {});
const marker = make('marker', {
  id: 'arrow', viewBox: '0 0 10 10', refX: 9, refY: 5,
  markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse',
});
marker.append(make('path', { d: 'M 0 1 L 9 5 L 0 9 z', fill: '#4d8fd1' }));
defs.append(marker);
svg.append(defs);

// 泳道横线
for (let i = 0; i < data.lanes.length; i++) {
  svg.append(make('line', {
    class: 'lane-line',
    x1: PAD_L - 16, y1: yOf(i), x2: width - PAD_R + 16, y2: yOf(i),
  }));
}

const colorOf = (node) => {
  let hash = 0;
  for (const ch of node) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return `hsl(${hash % 360}, 55%, 60%)`;
};

// 因果连线：from 必在 to 左边（方向同全序），同泳道时向上绕一条弧
const byPos = new Map(data.events.map((e) => [e.pos, e]));
for (const edge of data.edges) {
  const from = byPos.get(edge.from);
  const to = byPos.get(edge.to);
  const x1 = xOf(from.pos);
  const y1 = yOf(laneRow.get(from.node));
  const x2 = xOf(to.pos);
  const y2 = yOf(laneRow.get(to.node));
  let d;
  if (y1 === y2) {
    const lift = Math.min(ROW_H * 0.9, 14 + (x2 - x1) * 0.08);
    d = `M ${x1} ${y1} C ${x1 + 12} ${y1 - lift}, ${x2 - 12} ${y2 - lift}, ${x2} ${y2}`;
  } else {
    d = `M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`;
  }
  const path = make('path', { class: 'edge', d, 'marker-end': 'url(#arrow)' });
  const title = make('title', {});
  title.textContent = `${from.id} → ${to.id}`;
  path.append(title);
  svg.append(path);
}

// 事件点：横坐标就是全序位置，标出 pos
for (const event of data.events) {
  const cx = xOf(event.pos);
  const cy = yOf(laneRow.get(event.node));
  const dot = make('circle', {
    class: 'dot', cx, cy, r: 6, fill: colorOf(event.node),
  });
  const title = make('title', {});
  const clock = event.clock.map(([k, v]) => `${k}:${v}`).join(', ');
  title.textContent =
    `#${event.pos} ${event.id} @ ${event.node}\nwall ${event.wall}\n${clock}`;
  dot.append(title);
  svg.append(dot);
  const label = make('text', {
    class: 'pos-label', x: cx, y: cy + 18,
  });
  label.textContent = event.pos;
  svg.append(label);
}

// 不可比较对清单
const list = document.getElementById('incomp-list');
if (data.incomparable.length === 0) {
  const li = document.createElement('li');
  li.textContent = '（可见事件两两可比较）';
  list.append(li);
}
for (const [a, b] of data.incomparable) {
  const li = document.createElement('li');
  const left = document.createElement('span');
  left.textContent = a;
  const sep = document.createElement('span');
  sep.className = 'sep';
  sep.textContent = '∥';
  const right = document.createElement('span');
  right.textContent = b;
  li.append(left, sep, right);
  list.append(li);
}
