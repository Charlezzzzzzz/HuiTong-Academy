/* 会通书院 · 七席纸皮头像人物
 *
 * 视觉基准来自七席头像板：浅色纸面、同色系墨线、圆头纸身、角色专属发型
 * 与一个静态功能道具。Canvas 纹理作为 billboard 贴图挂到 Three.js 平面上，
 * 保留主系统依赖的 createFigure / setFigureState / getFigureState /
 * revealFigure / disposeFigure 接口。
 */

import * as THREE from 'three';
import { mixColor } from './ink.js';

const INK = '#1E1B17';
const PAPER_BASE = '#EFE3C8';
const PAPER_LIGHT = '#F7EFDC';
const FIGURE_ANCHOR = 0.16;
const SEAT_RADIUS = 2.40;

let shadowTexture = null;

function rgba(hex, alpha = 1) {
  const value = hex.replace('#', '');
  const full = value.length === 3
    ? value.split('').map((part) => part + part).join('')
    : value;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function makeCanvas(width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

function withPath(ctx, draw, fill, stroke, lineWidth = 6, alpha = 1) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  draw(ctx);
  if (fill) {
    ctx.fillStyle = fill;
    ctx.fill();
  }
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = lineWidth;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
  }
  ctx.restore();
}

function line(ctx, points, color, width = 8, alpha = 1) {
  if (!points.length) return;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.globalAlpha = alpha;
  ctx.lineWidth = width;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i += 1) {
    ctx.lineTo(points[i].x, points[i].y);
  }
  ctx.stroke();
  ctx.restore();
}

function ellipse(ctx, x, y, rx, ry, fill, stroke, width = 6, alpha = 1) {
  withPath(
    ctx,
    (path) => path.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2),
    fill,
    stroke,
    width,
    alpha
  );
}

function roundedRect(ctx, x, y, width, height, radius, fill, stroke, lineWidth = 6, alpha = 1) {
  const r = Math.min(radius, width / 2, height / 2);
  withPath(
    ctx,
    (path) => {
      path.moveTo(x + r, y);
      path.lineTo(x + width - r, y);
      path.quadraticCurveTo(x + width, y, x + width, y + r);
      path.lineTo(x + width, y + height - r);
      path.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
      path.lineTo(x + r, y + height);
      path.quadraticCurveTo(x, y + height, x, y + height - r);
      path.lineTo(x, y + r);
      path.quadraticCurveTo(x, y, x + r, y);
      path.closePath();
    },
    fill,
    stroke,
    lineWidth,
    alpha
  );
}

function getColors(role) {
  const accent = role?.color || '#4B5566';
  return {
    accent,
    ink: mixColor(accent, INK, 0.26),
    body: mixColor(accent, PAPER_LIGHT, 0.84),
    face: mixColor(accent, PAPER_LIGHT, 0.95),
    edge: mixColor(accent, INK, 0.42),
    paper: PAPER_LIGHT,
  };
}

function drawContactShadow(ctx, cx, y, accent, ink) {
  ellipse(ctx, cx, y + 20, 126, 22, rgba(accent, 0.16), ink, 5, 0.48);
  line(ctx, [
    { x: cx - 94, y: y + 20 },
    { x: cx - 50, y: y + 31 },
    { x: cx + 30, y: y + 31 },
    { x: cx + 96, y: y + 20 },
  ], ink, 4, 0.30);
}

function drawBody(ctx, cx, colors) {
  const top = 278;
  const hem = 600;
  const bodyPath = (path, dy = 0) => {
    path.moveTo(cx - 68, top + dy);
    path.quadraticCurveTo(cx - 105, 326 + dy, cx - 128, 470 + dy);
    path.quadraticCurveTo(cx - 138, 548 + dy, cx - 101, 584 + dy);
    path.quadraticCurveTo(cx - 55, 618 + dy, cx, hem + dy);
    path.quadraticCurveTo(cx + 55, 618 + dy, cx + 101, 584 + dy);
    path.quadraticCurveTo(cx + 138, 548 + dy, cx + 128, 470 + dy);
    path.quadraticCurveTo(cx + 105, 326 + dy, cx + 68, top + dy);
    path.quadraticCurveTo(cx + 28, 248 + dy, cx, 248 + dy);
    path.quadraticCurveTo(cx - 28, 248 + dy, cx - 68, top + dy);
    path.closePath();
  };

  withPath(ctx, (path) => bodyPath(path, 10), rgba(colors.edge, 0.36), colors.ink, 7, 0.86);
  withPath(ctx, (path) => bodyPath(path), colors.body, colors.ink, 8, 0.98);
  line(ctx, [
    { x: cx - 101, y: 584 },
    { x: cx - 56, y: 606 },
    { x: cx, y: 612 },
    { x: cx + 56, y: 606 },
    { x: cx + 101, y: 584 },
  ], colors.accent, 10, 0.52);
}

function drawHair(ctx, roleId, cx, headY, colors) {
  const dark = colors.ink;
  const accent = colors.accent;

  if (roleId === 'chair') {
    line(ctx, [
      { x: cx - 64, y: headY - 78 },
      { x: cx + 64, y: headY - 78 },
    ], dark, 14, 0.98);
    ellipse(ctx, cx, headY - 92, 25, 23, dark, dark, 4, 0.98);
    line(ctx, [
      { x: cx - 50, y: headY - 71 },
      { x: cx + 50, y: headY - 71 },
    ], accent, 3, 0.40);
    return;
  }

  if (roleId === 'speaker' || roleId === 'evidence') {
    const tall = roleId === 'evidence';
    const top = headY - (tall ? 132 : 124);
    const bottom = headY - 61;
    withPath(ctx, (path) => {
      path.moveTo(cx - 78, bottom);
      path.lineTo(cx - 88, top + 24);
      path.quadraticCurveTo(cx - 74, top, cx - 48, top - 8);
      path.lineTo(cx + 72, top - 8);
      path.quadraticCurveTo(cx + 88, top + 8, cx + 82, top + 32);
      path.lineTo(cx + 70, bottom);
      path.closePath();
    }, dark, dark, 7, 0.98);
    line(ctx, [
      { x: cx - 57, y: bottom - 19 },
      { x: cx + 58, y: bottom - 19 },
    ], colors.face, 8, 0.92);
    line(ctx, [
      { x: cx - 58, y: bottom - 9 },
      { x: cx + 58, y: bottom - 9 },
    ], accent, 3, 0.48);
    return;
  }

  if (roleId === 'clarifier') {
    ellipse(ctx, cx - 54, headY - 70, 29, 28, dark, dark, 5, 0.98);
    return;
  }

  if (roleId === 'challenger') {
    ellipse(ctx, cx - 54, headY - 70, 29, 28, dark, dark, 5, 0.98);
    line(ctx, [
      { x: cx - 78, y: headY - 52 },
      { x: cx - 101, y: headY - 24 },
      { x: cx - 108, y: headY + 12 },
    ], dark, 15, 0.98);
    return;
  }

  if (roleId === 'recorder') {
    ellipse(ctx, cx - 58, headY - 34, 48, 58, dark, dark, 5, 0.98);
    ellipse(ctx, cx - 46, headY - 73, 31, 28, dark, dark, 5, 0.98);
    return;
  }

  if (roleId === 'editor') {
    ellipse(ctx, cx - 45, headY - 80, 27, 25, null, dark, 13, 0.98);
    line(ctx, [
      { x: cx - 66, y: headY - 55 },
      { x: cx - 92, y: headY - 24 },
      { x: cx - 104, y: headY + 14 },
    ], dark, 14, 0.98);
    line(ctx, [
      { x: cx - 56, y: headY - 80 },
      { x: cx - 34, y: headY - 80 },
    ], accent, 3, 0.40);
  }
}

function drawFace(ctx, cx, headY, colors) {
  const shadow = rgba(mixColor(colors.accent, INK, 0.32), 0.25);
  ellipse(ctx, cx, headY + 6, 67, 70, shadow, colors.ink, 7, 0.80);
  ellipse(ctx, cx, headY, 64, 67, colors.face, colors.ink, 8, 0.98);
}

function drawFan(ctx, x, y, colors) {
  withPath(ctx, (path) => {
    path.moveTo(x - 58, y + 24);
    path.quadraticCurveTo(x, y - 54, x + 58, y + 24);
    path.quadraticCurveTo(x, y + 42, x - 58, y + 24);
    path.closePath();
  }, colors.paper, colors.ink, 7, 0.98);
  line(ctx, [{ x, y: y + 25 }, { x: x - 39, y: y - 25 }], colors.ink, 5, 0.84);
  line(ctx, [{ x, y: y + 25 }, { x: x - 13, y: y - 42 }], colors.ink, 5, 0.84);
  line(ctx, [{ x, y: y + 25 }, { x: x + 14, y: y - 42 }], colors.ink, 5, 0.84);
  line(ctx, [{ x, y: y + 25 }, { x: x + 40, y: y - 24 }], colors.ink, 5, 0.84);
  line(ctx, [{ x: x - 6, y: y + 42 }, { x: x + 8, y: y + 42 }], colors.accent, 8, 0.74);
}

function drawScroll(ctx, x, y, colors) {
  roundedRect(ctx, x - 68, y - 22, 126, 58, 8, colors.paper, colors.ink, 7, 0.98);
  ellipse(ctx, x - 70, y + 7, 15, 23, colors.accent, colors.ink, 4, 0.90);
  ellipse(ctx, x + 59, y + 7, 15, 23, colors.paper, colors.ink, 4, 0.98);
  line(ctx, [{ x: x - 38, y: y - 5 }, { x: x + 30, y: y - 5 }], colors.accent, 4, 0.52);
  line(ctx, [{ x: x - 38, y: y + 12 }, { x: x + 20, y: y + 12 }], colors.accent, 4, 0.34);
}

function drawLamp(ctx, x, y, colors) {
  withPath(ctx, (path) => {
    path.moveTo(x, y - 40);
    path.quadraticCurveTo(x - 38, y - 9, x - 25, y + 24);
    path.quadraticCurveTo(x - 15, y + 41, x, y + 40);
    path.quadraticCurveTo(x + 15, y + 41, x + 25, y + 24);
    path.quadraticCurveTo(x + 38, y - 9, x, y - 40);
    path.closePath();
  }, colors.paper, colors.ink, 8, 0.98);
  line(ctx, [{ x, y: y + 40 }, { x, y: y + 54 }], colors.ink, 8, 0.86);
  line(ctx, [{ x: x - 17, y: y + 57 }, { x: x + 17, y: y + 57 }], colors.ink, 8, 0.86);
  line(ctx, [{ x: x - 16, y: y - 65 }, { x: x - 8, y: y - 50 }], colors.ink, 10, 0.92);
  line(ctx, [{ x, y: y - 70 }, { x, y: y - 52 }], colors.ink, 10, 0.92);
  line(ctx, [{ x: x + 16, y: y - 65 }, { x: x + 8, y: y - 50 }], colors.ink, 10, 0.92);
}

function drawQuestion(ctx, x, y, colors) {
  line(ctx, [
    { x: x - 18, y: y - 18 },
    { x: x - 5, y: y - 34 },
    { x: x + 18, y: y - 30 },
    { x: x + 24, y: y - 10 },
    { x: x + 4, y: y + 8 },
    { x: x + 3, y: y + 23 },
  ], colors.ink, 13, 0.96);
  ellipse(ctx, x + 3, y + 48, 7, 7, colors.ink, null, 0, 0.96);
}

function drawMagnifier(ctx, x, y, colors) {
  ellipse(ctx, x, y, 34, 34, colors.paper, colors.ink, 8, 0.98);
  line(ctx, [{ x: x + 24, y: y + 24 }, { x: x + 54, y: y + 54 }], colors.ink, 14, 0.94);
  line(ctx, [
    { x: x - 17, y },
    { x: x - 3, y: y + 12 },
    { x: x + 20, y: y - 14 },
  ], colors.accent, 8, 0.92);
}

function drawSpeechBubble(ctx, x, y, colors) {
  withPath(ctx, (path) => {
    path.moveTo(x - 57, y - 30);
    path.quadraticCurveTo(x - 57, y - 52, x - 32, y - 56);
    path.lineTo(x + 42, y - 56);
    path.quadraticCurveTo(x + 66, y - 52, x + 66, y - 28);
    path.quadraticCurveTo(x + 66, y - 3, x + 41, y + 2);
    path.lineTo(x + 19, y + 6);
    path.lineTo(x + 3, y + 25);
    path.lineTo(x + 5, y + 3);
    path.lineTo(x - 32, y + 1);
    path.quadraticCurveTo(x - 57, y - 4, x - 57, y - 30);
    path.closePath();
  }, colors.paper, colors.ink, 7, 0.98);
  ellipse(ctx, x - 25, y - 28, 6, 6, colors.ink, null, 0, 0.92);
  ellipse(ctx, x, y - 28, 6, 6, colors.ink, null, 0, 0.92);
  ellipse(ctx, x + 25, y - 28, 6, 6, colors.ink, null, 0, 0.92);
}

function drawBrush(ctx, x, y, colors) {
  line(ctx, [
    { x: x - 34, y: y + 44 },
    { x: x + 35, y: y - 42 },
  ], colors.ink, 14, 0.92);
  line(ctx, [
    { x: x - 36, y: y + 47 },
    { x: x - 55, y: y + 68 },
    { x: x - 78, y: y + 71 },
    { x: x - 58, y: y + 47 },
  ], colors.ink, 14, 0.92);
  line(ctx, [{ x: x + 11, y: y - 15 }, { x: x + 48, y: y - 60 }], colors.accent, 5, 0.72);
  line(ctx, [
    { x: x - 88, y: y + 81 },
    { x: x - 22, y: y + 94 },
    { x: x + 52, y: y + 81 },
  ], colors.ink, 7, 0.46);
}

function drawRoleProp(ctx, roleId, cx, colors) {
  switch (roleId) {
    case 'chair':
      drawFan(ctx, cx + 150, 356, colors);
      break;
    case 'speaker':
      drawScroll(ctx, cx + 154, 340, colors);
      break;
    case 'clarifier':
      drawLamp(ctx, cx + 154, 168, colors);
      break;
    case 'challenger':
      drawQuestion(ctx, cx + 154, 168, colors);
      break;
    case 'evidence':
      drawMagnifier(ctx, cx + 150, 360, colors);
      break;
    case 'recorder':
      drawSpeechBubble(ctx, cx + 150, 196, colors);
      break;
    case 'editor':
      drawBrush(ctx, cx + 138, 354, colors);
      break;
    default:
      break;
  }
}

function buildPaperAvatarTexture(role, opts = {}) {
  const size = opts.size || 768;
  const canvas = makeCanvas(size, size);
  const ctx = canvas.getContext('2d');
  const scale = size / 768;
  const colors = getColors(role);
  const cx = 384;
  const headY = 184;

  ctx.save();
  ctx.scale(scale, scale);
  ctx.clearRect(0, 0, 768, 768);

  drawContactShadow(ctx, cx, 628, colors.accent, colors.ink);
  drawBody(ctx, cx, colors);
  drawHair(ctx, role.id, cx, headY, colors);
  drawFace(ctx, cx, headY, colors);
  drawRoleProp(ctx, role.id, cx, colors);

  ctx.restore();
  return canvas;
}

// 两个导出名都保留，避免其他页面或外部工具调用时落回旧人物。
export function buildFigureTexture(role, opts = {}) {
  return buildPaperAvatarTexture(role, opts);
}

export function buildScholarFigureTexture(role, opts = {}) {
  return buildPaperAvatarTexture(role, opts);
}

function makeShadowTexture() {
  if (shadowTexture) return shadowTexture;
  const canvas = makeCanvas(256, 256);
  const ctx = canvas.getContext('2d');
  const gradient = ctx.createRadialGradient(128, 128, 8, 128, 128, 126);
  gradient.addColorStop(0, 'rgba(30,27,23,0.22)');
  gradient.addColorStop(0.6, 'rgba(30,27,23,0.12)');
  gradient.addColorStop(1, 'rgba(30,27,23,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 256, 256);
  shadowTexture = new THREE.CanvasTexture(canvas);
  shadowTexture.colorSpace = THREE.SRGBColorSpace;
  shadowTexture.needsUpdate = true;
  return shadowTexture;
}

const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = `
  uniform sampler2D uMap;
  uniform float uReveal;
  uniform float uInk;
  uniform float uOpacity;
  uniform vec3 uPaper;
  uniform vec3 uSeat;
  uniform float uTime;
  varying vec2 vUv;

  void main() {
    vec4 src = texture2D(uMap, vUv);
    float a = src.a;
    float edge = 1.0 - smoothstep(uReveal - 0.14, uReveal, vUv.y);
    a *= edge;

    vec3 col = mix(src.rgb, uSeat, 0.12);
    col = mix(col, uPaper, (1.0 - uInk) * 0.18);

    if (!gl_FrontFacing) {
      a *= 0.72;
      col = mix(col, uPaper, 0.18);
    }

    gl_FragColor = vec4(col, a * uOpacity);
    float wet = smoothstep(uReveal - 0.02, uReveal + 0.01, vUv.y)
      * 0.5 * max(0.0, 1.0 - uReveal);
    gl_FragColor.rgb = mix(gl_FragColor.rgb, uPaper, wet);
  }
`;

export function createFigure(role, options = {}) {
  const seat = role.seat || 0;
  const seatCount = Math.max(1, Number(options.seatCount) || 7);
  const angle = Number.isFinite(options.angle)
    ? options.angle
    : (seat * Math.PI * 2) / seatCount;
  const textureCanvas = buildPaperAvatarTexture(role, { size: 768 });
  const texture = new THREE.CanvasTexture(textureCanvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 2;
  texture.needsUpdate = true;

  const paper = new THREE.Color(options.paperColor || PAPER_BASE).convertSRGBToLinear();
  const seatColor = new THREE.Color(role.color || '#4B5566').convertSRGBToLinear();
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uMap: { value: texture },
      uReveal: { value: 0 },
      uInk: { value: 1 },
      uOpacity: { value: 0 },
      uPaper: { value: paper },
      uSeat: { value: seatColor },
      uTime: { value: 0 },
    },
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: false,
    depthTest: true,
    side: THREE.DoubleSide,
    blending: THREE.NormalBlending,
  });

  const geometry = new THREE.PlaneGeometry(0.78, 0.78);
  geometry.translate(0, 0.39, 0);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(
    Math.sin(angle) * SEAT_RADIUS,
    FIGURE_ANCHOR,
    -Math.cos(angle) * SEAT_RADIUS
  );
  mesh.rotation.y = -angle;
  mesh.renderOrder = 2;
  mesh.userData.role = role;
  mesh.userData.seat = seat;
  mesh.userData.reveal = 0;
  mesh.userData.disposed = false;

  const shadowGeometry = new THREE.PlaneGeometry(0.72, 0.72);
  shadowGeometry.rotateX(-Math.PI / 2);
  const shadowMaterial = new THREE.MeshBasicMaterial({
    map: makeShadowTexture(),
    transparent: true,
    depthWrite: false,
    depthTest: true,
    opacity: 1,
  });
  const shadow = new THREE.Mesh(shadowGeometry, shadowMaterial);
  shadow.position.y = 0.012 - FIGURE_ANCHOR;
  shadow.renderOrder = 1;
  shadow.userData.isContactShadow = true;
  mesh.add(shadow);

  return mesh;
}

export function setFigureState(mesh, state = {}) {
  if (!mesh || !mesh.material || !mesh.material.uniforms) return;
  const uniforms = mesh.material.uniforms;
  if (state.ink != null) uniforms.uInk.value = state.ink;
  if (state.opacity != null) uniforms.uOpacity.value = state.opacity;
}

export function getFigureState(mesh) {
  if (!mesh || !mesh.material || !mesh.material.uniforms) {
    return { ink: 1, opacity: 0 };
  }
  return {
    ink: mesh.material.uniforms.uInk.value,
    opacity: mesh.material.uniforms.uOpacity.value,
  };
}

export function revealFigure(mesh, duration = 520, delay = 0) {
  if (!mesh || !mesh.material) return Promise.resolve();
  const uniforms = mesh.material.uniforms;
  const target = 1.06;
  const startReveal = mesh.userData.reveal || 0;
  return new Promise((resolve) => {
    const begin = performance.now() + delay;
    const step = (now) => {
      if (mesh.userData.disposed) {
        resolve();
        return;
      }
      if (now < begin) {
        requestAnimationFrame(step);
        return;
      }
      const t = Math.min(1, (now - begin) / Math.max(1, duration));
      const eased = 1 - Math.pow(1 - t, 3);
      const value = startReveal + (target - startReveal) * eased;
      uniforms.uReveal.value = value;
      mesh.userData.reveal = value;
      if (t >= 1) {
        uniforms.uReveal.value = target;
        mesh.userData.reveal = target;
        resolve();
      } else {
        requestAnimationFrame(step);
      }
    };
    requestAnimationFrame(step);
  });
}

export function disposeFigure(mesh) {
  if (!mesh || mesh.userData.disposed) return;
  mesh.userData.disposed = true;
  if (mesh.material) {
    if (mesh.material.uniforms && mesh.material.uniforms.uMap) {
      const texture = mesh.material.uniforms.uMap.value;
      if (texture && texture.dispose) texture.dispose();
    }
    mesh.material.dispose();
  }
  if (mesh.geometry) mesh.geometry.dispose();
  for (const child of mesh.children) {
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      if (child.material.map && child.material.map !== shadowTexture) {
        child.material.map.dispose();
      }
      child.material.dispose();
    }
  }
  mesh.clear();
}
