/* 会通书院 · 墨与纸
 * 纸纹、笔法、印章、立轴、远山、烟、墨溅、墨晕过场与点击墨点。
 * 只依赖 Canvas2D 与 DOM，不依赖 three。
 */

const PAPER_BASE = '#EFE3C8';
const INK = '#1E1B17';
const SEAL = '#A83224';
const PAPER_LIGHT = '#F7EFDC';

let paperCanvas = null;
let inkCtx = null;
let inkCanvas = null;
let wipeSeq = 0;
let dropActive = 0;
let dropClearTimer = 0;

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function random() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashText(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function hexToRgb(hex) {
  const value = hex.replace('#', '');
  const full =
    value.length === 3
      ? value
          .split('')
          .map((ch) => ch + ch)
          .join('')
      : value;
  return {
    r: parseInt(full.slice(0, 2), 16),
    g: parseInt(full.slice(2, 4), 16),
    b: parseInt(full.slice(4, 6), 16),
  };
}

function rgba(hex, alpha) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r},${g},${b},${alpha})`;
}

export function mixColor(hexA, hexB, amount) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  const mix = (x, y) => Math.round(x + (y - x) * amount);
  return `#${[mix(a.r, b.r), mix(a.g, b.g), mix(a.b, b.b)]
    .map((v) => v.toString(16).padStart(2, '0'))
    .join('')}`;
}

function makeCanvas(width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

function fontString(size, family) {
  const stack =
    family ||
    "'Ma Shan Zheng','Kaiti SC','STKaiti','KaiTi','Songti SC',serif";
  return `${size}px ${stack}`;
}

/* ------------------------------------------------------------------ */
/* 宣纸                                                                */
/* ------------------------------------------------------------------ */

export function makePaper(size = 2048) {
  if (paperCanvas) return paperCanvas;
  const canvas = makeCanvas(size, size);
  const ctx = canvas.getContext('2d');
  const random = mulberry32(20261028);

  ctx.fillStyle = PAPER_BASE;
  ctx.fillRect(0, 0, size, size);

  // 云斑
  for (let i = 0; i < 900; i += 1) {
    const x = random() * size;
    const y = random() * size;
    const radius = 40 + random() * 180;
    const light = random() > 0.5;
    const color = light ? '#F6EEDC' : '#E3CFA6';
    const alpha = 0.012 + random() * 0.023;
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, rgba(color, alpha));
    gradient.addColorStop(1, rgba(color, 0));
    ctx.fillStyle = gradient;
    ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
  }

  // 长纤维
  const angleBase = (-8 * Math.PI) / 180;
  for (let i = 0; i < 26000; i += 1) {
    const x = random() * size;
    const y = random() * size;
    const length = 6 + random() * 22;
    const angle = angleBase + (random() - 0.5) * ((16 * Math.PI) / 180);
    const color = random() > 0.5 ? '#C9B48C' : '#FBF4E4';
    ctx.strokeStyle = color;
    ctx.globalAlpha = 0.02 + random() * 0.04;
    ctx.lineWidth = 0.6 + random() * 0.6;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(angle) * length, y + Math.sin(angle) * length);
    ctx.stroke();
  }

  // 长丝
  for (let i = 0; i < 4000; i += 1) {
    const x = random() * size;
    const y = random() * size;
    const length = 40 + random() * 50;
    const angle = angleBase + (random() - 0.5) * ((10 * Math.PI) / 180);
    ctx.strokeStyle = random() > 0.5 ? '#C9B48C' : '#FBF4E4';
    ctx.globalAlpha = 0.03;
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(angle) * length, y + Math.sin(angle) * length);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // 水渍
  for (let i = 0; i < 40; i += 1) {
    const x = random() * size;
    const y = random() * size;
    const radius = 60 + random() * 240;
    const color = random() < 0.3 ? '#9C8256' : '#BFA275';
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, rgba(color, 0.02));
    gradient.addColorStop(1, rgba(color, 0));
    ctx.fillStyle = gradient;
    ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
  }

  // 颗粒：512² 离屏，平铺
  const grain = makeCanvas(512, 512);
  const grainCtx = grain.getContext('2d');
  const image = grainCtx.createImageData(512, 512);
  for (let i = 0; i < image.data.length; i += 4) {
    const value = 128 + Math.round((random() - 0.5) * 12);
    image.data[i] = value;
    image.data[i + 1] = value;
    image.data[i + 2] = value;
    image.data[i + 3] = 255;
  }
  grainCtx.putImageData(image, 0, 0);
  const pattern = ctx.createPattern(grain, 'repeat');
  ctx.save();
  ctx.globalCompositeOperation = 'overlay';
  ctx.globalAlpha = 0.5;
  ctx.fillStyle = pattern;
  ctx.fillRect(0, 0, size, size);
  ctx.restore();

  // 四边陈化
  const edge = 120;
  const edgeColor = 'rgba(160,130,80,0.10)';
  const edgeFade = 'rgba(160,130,80,0)';
  let gradient = ctx.createLinearGradient(0, 0, 0, edge);
  gradient.addColorStop(0, edgeColor);
  gradient.addColorStop(1, edgeFade);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, edge);
  gradient = ctx.createLinearGradient(0, size, 0, size - edge);
  gradient.addColorStop(0, edgeColor);
  gradient.addColorStop(1, edgeFade);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, size - edge, size, edge);
  gradient = ctx.createLinearGradient(0, 0, edge, 0);
  gradient.addColorStop(0, edgeColor);
  gradient.addColorStop(1, edgeFade);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, edge, size);
  gradient = ctx.createLinearGradient(size, 0, size - edge, 0);
  gradient.addColorStop(0, edgeColor);
  gradient.addColorStop(1, edgeFade);
  ctx.fillStyle = gradient;
  ctx.fillRect(size - edge, 0, edge, size);

  // 暗角
  const vignette = ctx.createRadialGradient(size / 2, size / 2, size * 0.25, size / 2, size / 2, size * 0.72);
  vignette.addColorStop(0, 'rgba(150,120,70,0)');
  vignette.addColorStop(1, 'rgba(150,120,70,0.07)');
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, size, size);

  paperCanvas = canvas;
  return canvas;
}

/* ------------------------------------------------------------------ */
/* 蒲团纹理                                                            */
/* ------------------------------------------------------------------ */

export function makeCushionTexture(color, index) {
  const size = 512;
  const canvas = makeCanvas(size, size);
  const ctx = canvas.getContext('2d');
  const random = mulberry32(7000 + index * 131);

  ctx.fillStyle = PAPER_BASE;
  ctx.fillRect(0, 0, size, size);

  const gradient = ctx.createRadialGradient(
    size / 2,
    size / 2,
    size * 0.04,
    size / 2,
    size / 2,
    size * 0.72
  );
  gradient.addColorStop(0, rgba(color, 0.55));
  gradient.addColorStop(1, rgba(color, 0.85));
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);

  // 布纹弧线
  ctx.strokeStyle = rgba('#2B2620', 0.18);
  for (let i = 0; i < 28; i += 1) {
    const radius = 40 + random() * 210;
    const start = random() * Math.PI * 2;
    ctx.lineWidth = 1 + random();
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, radius, start, start + 0.7 + random() * 1.1);
    ctx.stroke();
  }

  // 三圈同心墨线
  ctx.strokeStyle = rgba(INK, 0.22);
  ctx.lineWidth = 2;
  for (const factor of [0.22, 0.3, 0.38]) {
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, size * factor, 0, Math.PI * 2);
    ctx.stroke();
  }

  // 外缘一段干笔飞白
  const points = [];
  const start = -0.35;
  const end = 0.35;
  for (let i = 0; i <= 18; i += 1) {
    const angle = start + ((end - start) * i) / 18;
    points.push({
      x: size / 2 + Math.cos(angle) * size * 0.455,
      y: size / 2 + Math.sin(angle) * size * 0.455,
    });
  }
  drawStroke(ctx, points, {
    width: 12,
    color: INK,
    alpha: 0.3,
    seed: 900 + index,
    baseWidth: 0.9,
  });

  return canvas;
}

/* ------------------------------------------------------------------ */
/* 印章                                                                */
/* ------------------------------------------------------------------ */

const sealCache = new Map();

export function makeSeal(text, opts = {}) {
  const size = opts.size || 256;
  const ink = opts.ink || SEAL;
  const key = `${text}|${size}|${ink}`;
  if (sealCache.has(key)) return sealCache.get(key);

  const canvas = makeCanvas(size, size);
  const ctx = canvas.getContext('2d');
  const hash = hashText(text);
  const random = mulberry32(hash);
  const radius = size * 0.06;

  ctx.save();
  ctx.translate(size / 2, size / 2);
  ctx.rotate(((-4 + ((hash % 61) / 10 - 3)) * Math.PI) / 180);

  ctx.fillStyle = ink;
  ctx.beginPath();
  ctx.roundRect(-size / 2, -size / 2, size, size, radius);
  ctx.fill();

  ctx.fillStyle = PAPER_LIGHT;
  const chars = Array.from(text);
  const fontSize =
    chars.length <= 1
      ? size * 0.36
      : chars.length <= 2
        ? size * 0.3
        : size * 0.24;
  const letter = size * 0.04;
  ctx.font = fontString(fontSize);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const step = fontSize + letter;
  const startY = -((chars.length - 1) * step) / 2;
  chars.forEach((char, index) => {
    ctx.fillText(char, 0, startY + index * step);
  });

  // 石章崩口
  ctx.globalCompositeOperation = 'destination-out';
  for (let i = 0; i < 60; i += 1) {
    const side = i % 4;
    const along = (random() - 0.5) * size;
    let x = 0;
    let y = 0;
    if (side === 0) {
      x = along;
      y = -size / 2 + (random() - 0.5) * size * 0.03;
    } else if (side === 1) {
      x = size / 2 + (random() - 0.5) * size * 0.03;
      y = along;
    } else if (side === 2) {
      x = along;
      y = size / 2 + (random() - 0.5) * size * 0.03;
    } else {
      x = -size / 2 + (random() - 0.5) * size * 0.03;
      y = along;
    }
    ctx.globalAlpha = 0.25 + random() * 0.35;
    ctx.beginPath();
    ctx.arc(x, y, size * 0.02, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 0.08;
  for (let i = 0; i < 12; i += 1) {
    const x = (random() - 0.5) * size * 0.82;
    const y = (random() - 0.5) * size * 0.82;
    ctx.beginPath();
    ctx.ellipse(
      x,
      y,
      size * (0.01 + random() * 0.03),
      size * (0.008 + random() * 0.024),
      random() * Math.PI,
      0,
      Math.PI * 2
    );
    ctx.fill();
  }
  ctx.restore();

  const url = canvas.toDataURL('image/png');
  sealCache.set(key, url);
  return url;
}

/* ------------------------------------------------------------------ */
/* 立轴 / 门匾 / 楹联                                                  */
/* ------------------------------------------------------------------ */

export function makeScrollTexture(text, opts = {}) {
  const width = opts.w || 512;
  const height = opts.h || 1024;
  const vertical = opts.vertical !== false;
  const fontSize = opts.fontSize || (vertical ? 96 : 150);
  const color = opts.color || INK;
  const background = opts.bg === false ? null : opts.bg || PAPER_LIGHT;
  const rods = opts.rods !== false;
  const family = opts.font || null;
  const canvas = makeCanvas(width, height);
  const ctx = canvas.getContext('2d');

  if (background) {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = rgba('#C9B48C', 0.16);
    for (let i = 0; i < 18; i += 1) {
      const y = (hashText(text) % 97 + i * 53) % height;
      ctx.fillRect(0, y, width, 1);
    }
  }

  ctx.fillStyle = color;
  ctx.font = fontString(fontSize, family);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  if (vertical) {
    const chars = Array.from(text).filter((ch) => ch !== ' ');
    const step = fontSize * 1.18;
    const total = (chars.length - 1) * step;
    const start = height / 2 - total / 2;
    chars.forEach((char, index) => {
      ctx.fillText(char, width / 2, start + index * step);
    });
  } else {
    const chars = Array.from(text);
    const step = fontSize * 1.18;
    const total = (chars.length - 1) * step;
    const start = width / 2 - total / 2;
    chars.forEach((char, index) => {
      ctx.fillText(char, start + index * step, height / 2);
    });
  }

  if (rods) {
    ctx.strokeStyle = rgba('#5E5648', 0.9);
    ctx.lineWidth = Math.max(3, width * 0.014);
    ctx.beginPath();
    ctx.moveTo(width * 0.06, height * 0.035);
    ctx.lineTo(width * 0.94, height * 0.035);
    ctx.moveTo(width * 0.06, height * 0.965);
    ctx.lineTo(width * 0.94, height * 0.965);
    ctx.stroke();
    ctx.fillStyle = rgba('#3A342C', 0.9);
    ctx.beginPath();
    ctx.arc(width * 0.05, height * 0.035, width * 0.018, 0, Math.PI * 2);
    ctx.arc(width * 0.95, height * 0.035, width * 0.018, 0, Math.PI * 2);
    ctx.arc(width * 0.05, height * 0.965, width * 0.018, 0, Math.PI * 2);
    ctx.arc(width * 0.95, height * 0.965, width * 0.018, 0, Math.PI * 2);
    ctx.fill();
  }

  return canvas;
}

/* ------------------------------------------------------------------ */
/* 远山                                                                */
/* ------------------------------------------------------------------ */

export function makeMountainTexture(layer) {
  const width = 1024;
  const height = 512;
  const canvas = makeCanvas(width, height);
  const ctx = canvas.getContext('2d');
  const random = mulberry32(4100 + layer * 733);
  const inks = ['#1E1B17', '#3A342C', '#5E5648', '#8B806C', '#B7AB92'];
  const base = inks[Math.min(4, layer + 1)];
  const bands = 5;

  for (let band = 0; band < bands; band += 1) {
    const level = height * (0.34 + band * 0.1);
    ctx.beginPath();
    ctx.moveTo(0, height);
    const phase = random() * Math.PI * 2;
    const amp = 26 + random() * 48;
    for (let x = 0; x <= width; x += 8) {
      const nx = x / width;
      const ridge =
        level -
        amp * Math.sin(nx * Math.PI * (1.2 + band * 0.35) + phase) -
        amp * 0.45 * Math.sin(nx * Math.PI * 5.3 + phase * 1.7) -
        (random() - 0.5) * (10 + band * 4);
      ctx.lineTo(x, ridge);
    }
    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fillStyle = rgba(base, 0.14 + band * 0.06);
    ctx.fill();
  }

  // 五档墨阶的折线山脊
  for (let i = 0; i < 5; i += 1) {
    const level = height * (0.22 + i * 0.09);
    ctx.strokeStyle = rgba(inks[i], 0.55 - i * 0.08);
    ctx.lineWidth = 2.2 - i * 0.28;
    ctx.beginPath();
    const phase = random() * Math.PI;
    for (let x = 0; x <= width; x += 6) {
      const nx = x / width;
      const y =
        level -
        30 * Math.sin(nx * Math.PI * (1 + i * 0.22) + phase) -
        14 * Math.sin(nx * Math.PI * 4.6 + phase * 2.1);
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  return canvas;
}

/* ------------------------------------------------------------------ */
/* 烟 / 墨溅                                                           */
/* ------------------------------------------------------------------ */

export function makeSmokeTexture() {
  const size = 256;
  const canvas = makeCanvas(size, size);
  const ctx = canvas.getContext('2d');
  const random = mulberry32(8123);
  for (let i = 0; i < 22; i += 1) {
    const x = size * (0.3 + random() * 0.4);
    const y = size * (0.3 + random() * 0.4);
    const radius = size * (0.1 + random() * 0.24);
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, 'rgba(255,255,255,0.10)');
    gradient.addColorStop(0.6, 'rgba(255,255,255,0.045)');
    gradient.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
  }
  return canvas;
}

export function makeSplatTexture() {
  const size = 1024;
  const canvas = makeCanvas(size, size);
  const ctx = canvas.getContext('2d');
  const random = mulberry32(4242);
  const cx = size / 2;
  const cy = size / 2;

  ctx.fillStyle = INK;
  for (let i = 0; i < 9; i += 1) {
    const angle = random() * Math.PI * 2;
    const distance = random() * 26;
    const radius = 92 + random() * 38;
    ctx.globalAlpha = 0.85;
    ctx.beginPath();
    ctx.arc(cx + Math.cos(angle) * distance, cy + Math.sin(angle) * distance, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.globalAlpha = 0.9;
  for (let i = 0; i < 6; i += 1) {
    const angle = (i / 6) * Math.PI * 2 + random() * 0.3;
    const inner = 80 + random() * 40;
    const outer = 300 + random() * 170;
    const width = 10 + random() * 26;
    const x1 = cx + Math.cos(angle) * inner;
    const y1 = cy + Math.sin(angle) * inner;
    const x2 = cx + Math.cos(angle) * outer;
    const y2 = cy + Math.sin(angle) * outer;
    const mx = cx + Math.cos(angle + 0.18) * (inner + outer) * 0.55;
    const my = cy + Math.sin(angle + 0.18) * (inner + outer) * 0.55;
    ctx.strokeStyle = INK;
    ctx.lineWidth = width;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.quadraticCurveTo(mx, my, x2, y2);
    ctx.stroke();
  }

  for (let i = 0; i < 14; i += 1) {
    const angle = random() * Math.PI * 2;
    const distance = 150 + random() * 300;
    const radius = 7 + random() * 26;
    const x = cx + Math.cos(angle) * distance;
    const y = cy + Math.sin(angle) * distance;
    ctx.globalAlpha = 0.55 + random() * 0.35;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    if (random() > 0.55) {
      ctx.beginPath();
      ctx.ellipse(
        x + Math.cos(angle) * radius * 1.8,
        y + Math.sin(angle) * radius * 1.8,
        radius * 0.5,
        radius * 0.26,
        angle,
        0,
        Math.PI * 2
      );
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
  return canvas;
}

/* ------------------------------------------------------------------ */
/* 笔法                                                                */
/* ------------------------------------------------------------------ */

function catmullRom(points, step = 2) {
  if (!points || points.length < 2) return points ? points.slice() : [];
  const result = [];
  const p = [points[0], ...points, points[points.length - 1]];
  for (let i = 1; i < p.length - 2; i += 1) {
    const p0 = p[i - 1];
    const p1 = p[i];
    const p2 = p[i + 1];
    const p3 = p[i + 2];
    const distance = Math.hypot(p2.x - p1.x, p2.y - p1.y);
    const steps = Math.max(1, Math.ceil(distance / step));
    for (let s = 0; s < steps; s += 1) {
      const t = s / steps;
      const t2 = t * t;
      const t3 = t2 * t;
      const x =
        0.5 *
        (2 * p1.x +
          (-p0.x + p2.x) * t +
          (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 +
          (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3);
      const y =
        0.5 *
        (2 * p1.y +
          (-p0.y + p2.y) * t +
          (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 +
          (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3);
      result.push({ x, y });
    }
  }
  result.push({ x: points[points.length - 1].x, y: points[points.length - 1].y });
  return result;
}

export function drawStroke(ctx, pts, o = {}) {
  if (!pts || pts.length < 2) return;
  const width = o.width || 8;
  const color = o.color || INK;
  const baseAlpha = o.alpha == null ? 1 : o.alpha;
  const seed = o.seed == null ? 1 : o.seed;
  const bristles = o.bristles || 40;
  const points = catmullRom(pts, o.step || 2);
  if (points.length < 2) return;

  const normals = [];
  for (let i = 0; i < points.length; i += 1) {
    const prev = points[Math.max(0, i - 1)];
    const next = points[Math.min(points.length - 1, i + 1)];
    let dx = next.x - prev.x;
    let dy = next.y - prev.y;
    const length = Math.hypot(dx, dy) || 1;
    dx /= length;
    dy /= length;
    normals.push({ x: -dy, y: dx });
  }

  const random = mulberry32(seed);
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  for (let b = 0; b < bristles; b += 1) {
    const u = b / (bristles - 1) - 0.5;
    const offset = u * width;
    let ink = 1 - 0.18 * Math.abs(u * 2);
    const deplete = 0.006 + 0.01 * Math.abs(u * 2);
    let run = [];
    let runInk = ink;

    const flush = () => {
      if (run.length < 2) {
        run = [];
        return;
      }
      ctx.globalAlpha = Math.max(0, Math.min(1, runInk)) * baseAlpha;
      ctx.lineWidth = (width / bristles) * (0.8 + 0.4 * random());
      ctx.beginPath();
      ctx.moveTo(run[0].x, run[0].y);
      for (let i = 1; i < run.length; i += 1) ctx.lineTo(run[i].x, run[i].y);
      ctx.stroke();
      run = [];
    };

    for (let i = 0; i < points.length; i += 1) {
      const point = points[i];
      const normal = normals[i];
      const x = point.x + normal.x * offset;
      const y = point.y + normal.y * offset;
      const noise = random();
      if (i > 0) {
        ink -= deplete;
        const prev = points[i - 1];
        const dx = point.x - prev.x;
        const dy = point.y - prev.y;
        const speed = Math.hypot(dx, dy) / 2;
        if (speed > 0.8 && noise < 0.2) {
          flush();
          continue;
        }
      }
      const threshold = 0.18 + 0.25 * noise;
      if (ink < threshold) {
        flush();
        continue;
      }
      if (run.length === 0) runInk = ink;
      run.push({ x, y });
    }
    flush();
    ctx.globalAlpha = 1;
  }
  ctx.restore();
}

/* ------------------------------------------------------------------ */
/* 墨晕过场                                                            */
/* ------------------------------------------------------------------ */

function ensureWipeCanvas() {
  const wipe = document.getElementById('wipe');
  let canvas = wipe.querySelector('canvas');
  if (!canvas) {
    canvas = document.createElement('canvas');
    wipe.appendChild(canvas);
  }
  const width = window.innerWidth;
  const height = window.innerHeight;
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  return { wipe, canvas };
}

function blobSprite(radius, random) {
  const size = Math.max(8, Math.ceil(radius * 2));
  const sprite = makeCanvas(size, size);
  const ctx = sprite.getContext('2d');
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, 'rgba(30,27,23,0.96)');
  gradient.addColorStop(0.72, 'rgba(30,27,23,0.92)');
  gradient.addColorStop(1, 'rgba(30,27,23,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  return sprite;
}

export function inkWipe(options = {}) {
  const {
    seal = '',
    reducedMotion = false,
    onCovered = null,
  } = options;
  const { wipe, canvas } = ensureWipeCanvas();
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  const duration = options.duration || 700;
  const coverMs = reducedMotion ? 180 : duration;
  const revealMs = reducedMotion ? 180 : 520;
  wipe.classList.add('swallowing');

  const sealImg = seal ? new Image() : null;
  if (sealImg) sealImg.src = makeSeal(seal, { size: 256 });
  const sealSize = 88;

  if (reducedMotion) {
    return new Promise((resolve) => {
      const start = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - start) / coverMs);
        ctx.clearRect(0, 0, width, height);
        ctx.globalAlpha = t;
        ctx.fillStyle = INK;
        ctx.fillRect(0, 0, width, height);
        ctx.globalAlpha = 1;
        if (t >= 1) {
          if (onCovered) onCovered();
          const outStart = performance.now();
          const outStep = (now2) => {
            const u = Math.min(1, (now2 - outStart) / revealMs);
            ctx.clearRect(0, 0, width, height);
            ctx.globalAlpha = 1 - u;
            ctx.fillStyle = INK;
            ctx.fillRect(0, 0, width, height);
            ctx.globalAlpha = 1;
            if (u >= 1) {
              ctx.clearRect(0, 0, width, height);
              wipe.classList.remove('swallowing');
              resolve(true);
            } else {
              requestAnimationFrame(outStep);
            }
          };
          requestAnimationFrame(outStep);
        } else {
          requestAnimationFrame(step);
        }
      };
      requestAnimationFrame(step);
    });
  }

  const edges = ['top', 'right', 'bottom', 'left'];
  const dir = options.dir && edges.includes(options.dir) ? options.dir : edges[wipeSeq++ % 4];
  const random = mulberry32(wipeSeq * 7919 + 17);
  const blobs = [];
  for (let i = 0; i < 150; i += 1) {
    const t = i / 150;
    const jitter = (random() - 0.5) * 0.44;
    let x = 0;
    let y = 0;
    if (dir === 'top') {
      x = (t + jitter * 0.6) * width;
      y = t * height;
    } else if (dir === 'bottom') {
      x = (t + jitter * 0.6) * width;
      y = (1 - t) * height;
    } else if (dir === 'left') {
      x = t * width;
      y = (t + jitter * 0.6) * height;
    } else {
      x = (1 - t) * width;
      y = (t + jitter * 0.6) * height;
    }
    blobs.push({
      x,
      y,
      radius: 40 + random() * 160,
      delay: (duration * 0.886) * Math.pow(t, 0.78),
      done: false,
      sprite: null,
    });
  }

  return new Promise((resolve) => {
    const start = performance.now();
    let covered = false;
    let cleared = false;

    const drawCover = (now) => {
      const elapsed = now - start;
      for (const blob of blobs) {
        if (blob.done) continue;
        if (elapsed < blob.delay) continue;
        const progress = Math.min(1, (elapsed - blob.delay) / 180);
        if (!blob.sprite) blob.sprite = blobSprite(blob.radius, random);
        const radius = blob.radius * progress;
        ctx.globalAlpha = 1;
        ctx.drawImage(blob.sprite, blob.x - radius, blob.y - radius, radius * 2, radius * 2);
        if (progress >= 1) blob.done = true;
      }
      if (!covered) {
        const sealT = Math.min(1, elapsed / (duration * 0.5));
        if (sealImg && sealImg.complete && sealT > 0.2) {
          const fade = sealT < 0.75 ? Math.min(1, (sealT - 0.2) / 0.25) : Math.max(0, 1 - (sealT - 0.75) / 0.25);
          ctx.globalAlpha = 0.9 * fade;
          ctx.drawImage(sealImg, width / 2 - sealSize / 2, height / 2 - sealSize / 2, sealSize, sealSize);
          ctx.globalAlpha = 1;
        }
      }
      if (elapsed >= duration * 0.886 && !covered) {
        covered = true;
        ctx.globalAlpha = 0.96;
        ctx.fillStyle = INK;
        ctx.fillRect(0, 0, width, height);
        ctx.globalAlpha = 1;
        if (onCovered) onCovered();
      }
      if (covered && !cleared) {
        cleared = true;
        ctx.fillStyle = INK;
        ctx.fillRect(0, 0, width, height);
        ctx.clearRect(0, 0, 0, 0);
        requestAnimationFrame(reveal);
        return;
      }
      requestAnimationFrame(drawCover);
    };

    const reveal = (now) => {
      const elapsed = now - start;
      const revealStart = duration * 0.886 + 40;
      const u = Math.min(1, (elapsed - revealStart) / revealMs);
      if (!reveal.blobs) {
        reveal.blobs = [];
        const revealRandom = mulberry32(wipeSeq * 3571 + 29);
        for (let i = 0; i < 120; i += 1) {
          const t = i / 120;
          reveal.blobs.push({
            t,
            radius: 50 + revealRandom() * 190,
            delay: revealMs * Math.pow(1 - t, 1.15),
            done: false,
          });
        }
        if (onCovered) onCovered();
      }
      for (const blob of reveal.blobs) {
        if (blob.done || u * revealMs < blob.delay) continue;
        const t = (u * revealMs - blob.delay) / (revealMs * 0.6);
        const progress = Math.min(1, t);
        const radius = blob.radius * progress;
        let x = 0;
        let y = 0;
        if (dir === 'top') {
          x = blob.t * width;
          y = blob.t * height;
        } else if (dir === 'bottom') {
          x = blob.t * width;
          y = (1 - blob.t) * height;
        } else if (dir === 'left') {
          x = blob.t * width;
          y = blob.t * height;
        } else {
          x = (1 - blob.t) * width;
          y = blob.t * height;
        }
        ctx.globalCompositeOperation = 'destination-out';
        ctx.globalAlpha = 1;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalCompositeOperation = 'source-over';
        if (progress >= 1) blob.done = true;
      }
      if (u >= 1) {
        ctx.clearRect(0, 0, width, height);
        wipe.classList.remove('swallowing');
        resolve(true);
      } else {
        requestAnimationFrame(reveal);
      }
    };

    requestAnimationFrame(drawCover);
  });
}

/* ------------------------------------------------------------------ */
/* 点击墨点                                                            */
/* ------------------------------------------------------------------ */

export function initInkFX() {
  inkCanvas = document.getElementById('inkfx');
  if (!inkCanvas) return;
  inkCtx = inkCanvas.getContext('2d');
  const resize = () => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    if (inkCanvas.width !== width || inkCanvas.height !== height) {
      inkCanvas.width = width;
      inkCanvas.height = height;
    }
  };
  resize();
  let timer = 0;
  window.addEventListener('resize', () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(resize, 120);
  });
}

export function dropAt(x, y, opts = {}) {
  if (!inkCtx) return;
  const ctx = inkCtx;
  const color = opts.color || SEAL;
  const drops = [
    { from: 2, to: 12, delay: 0 },
    { from: 4, to: 26, delay: 120 },
    { from: 7, to: 44, delay: 240 },
  ];
  const start = performance.now();
  dropActive += 1;
  window.clearTimeout(dropClearTimer);

  const step = (now) => {
    const elapsed = now - start;
    ctx.clearRect(0, 0, 0, 0);
    for (const drop of drops) {
      const t = Math.min(1, Math.max(0, (elapsed - drop.delay) / 700));
      if (t <= 0) continue;
      const radius = drop.from + (drop.to - drop.from) * t;
      ctx.globalAlpha = 0.55 * (1 - t);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();
    }
    const ringT = Math.min(1, elapsed / 700);
    if (ringT > 0 && ringT < 1) {
      ctx.globalAlpha = 0.35 * (1 - ringT);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(x, y, 8 + 44 * ringT, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    if (elapsed < 940) {
      requestAnimationFrame(step);
    } else {
      dropActive -= 1;
      if (dropActive <= 0) {
        dropClearTimer = window.setTimeout(() => {
          if (dropActive <= 0 && inkCtx) inkCtx.clearRect(0, 0, inkCanvas.width, inkCanvas.height);
        }, 80);
      }
    }
  };
  requestAnimationFrame(step);
}

/* ------------------------------------------------------------------ */
/* 字体等待                                                            */
/* ------------------------------------------------------------------ */

export async function awaitInkFonts(timeoutMs = 2000) {
  if (!document.fonts) return false;
  let timer = 0;
  const timeout = new Promise((resolve) => {
    timer = window.setTimeout(() => resolve(false), timeoutMs);
  });
  try {
    const ready = await Promise.race([
      document.fonts.ready.then(() => true),
      timeout,
    ]);
    window.clearTimeout(timer);
    if (!ready) return false;
    return document.fonts.check('48px "Ma Shan Zheng"');
  } catch {
    window.clearTimeout(timer);
    return false;
  }
}

export function onInkFontsLoaded(callback) {
  if (!document.fonts || !callback) return () => {};
  const handler = () => callback();
  document.fonts.addEventListener('loadingdone', handler);
  return () => document.fonts.removeEventListener('loadingdone', handler);
}
