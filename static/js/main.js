/* 会通书院 · 主程序
 * 状态机、厅堂搭建、相机过场、拾取、会话轮询与布局。
 */

import {
  makePaper,
  makeSeal,
  makeCushionTexture,
  makeScrollTexture,
  makeMountainTexture,
  awaitInkFonts,
  onInkFontsLoaded,
} from './ink.js';

const S = {
  BOOT: 'BOOT',
  GATE: 'GATE',
  WIPE: 'WIPE',
  OVERVIEW: 'OVERVIEW',
  DESCEND: 'DESCEND',
  SEATED: 'SEATED',
  PANEL: 'PANEL',
  CLOSING: 'CLOSING',
  FALLBACK: 'FALLBACK',
};

const R = 2.40;
const PAPER_HEX = '#EFE3C8';
const INK_HEX = '#1E1B17';
const INK_4 = '#B7AB92';
const INK_5 = '#DCCB9F';
const SEAT_TARGET = { x: 0, y: 0.52, z: 0 };

const CAM = {
  gate: { pos: [0, 1.70, 1.30], target: [0, 1.90, 5.95], fov: 55 },
  overview: {
    target: [0, 0.15, -0.20],
    r: 9.20,
    polar: (31.44 * Math.PI) / 180,
  },
  seats: [],
};

const state = {
  name: S.BOOT,
  mode: window.huitongMode || 'learning',
  seat: null,
  chair: 0,
  panelOpen: false,
  session: null,
  config: null,
  topic: 'chair',
  polling: false,
  lastSeq: 0,
  awaiting: false,
  hovered: null,
  pointer: { x: 0, y: 0 },
  pointerPx: { x: -1, y: -1 },
  gatePointer: { x: 0, y: 0 },
  camTarget: { x: 0, y: 1.75, z: 5.95 },
  viewport: { w: 1, h: 1 },
  figureMeshes: [],
  reducedMotion: false,
  starting: false,
  leaving: false,
  entering: false,
  entrancePlayed: false,
  doorLeaves: [],
  raf: 0,
  lastT: 0,
  enterToken: 0,
  hudTimers: [],
};

let THREE = null;
let figures = null;

let renderer = null;
let scene = null;
let camera = null;
let paperTexture = null;
let postScene = null;
let postCamera = null;
let postMaterial = null;
let postTarget = null;
let degraded = false;
let frameTimes = [];
let frameCount = 0;
let dprMedia = null;
let dprHandler = null;

const dom = {};
window.addEventListener('huitong:mode-change', (event) => {
  const mode = event.detail?.mode;
  if (mode === 'learning' || mode === 'production') state.mode = mode;
});
let seatAngles = [];
function configureSeatGeometry(count) {
  const safeCount = Math.max(1, Number(count) || 7);
  seatAngles = Array.from({ length: safeCount }, (_, k) => {
    const angle = (k * Math.PI * 2) / safeCount;
    return { angle, x: Math.sin(angle) * R, z: -Math.cos(angle) * R };
  });
  CAM.seats = seatAngles.map((seat) => ({ pos: [seat.x * 0.95, 1.05, seat.z * 0.95] }));
}
const seatTargetVec = { x: 0, y: 0.52, z: 0 };

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function ui() {
  return (state.config && state.config.ui) || {};
}

function roles() {
  return (state.config && state.config.roles) || [];
}

function stages() {
  return (state.config && state.config.stages) || [];
}

function topics() {
  return (state.config && state.config.topics) || [];
}

function roleBySeat(seat) {
  return roles().find((role) => role.seat === seat) || null;
}

function avatarUrl(seat) {
  return Number.isInteger(seat) && seat >= 0 ? `./assets/avatars/seat-${seat}.png` : '';
}

function stageById(id) {
  return stages().find((stage) => stage.id === id) || null;
}

function fmt(template, vars = {}) {
  return String(template || '').replace(/\{(\w+)\}/g, (match, key) =>
    vars[key] == null ? '' : String(vars[key])
  );
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function reduced() {
  return state.reducedMotion;
}

function duration(ms) {
  return reduced() ? ms * 0.35 : ms;
}

function nextFrame() {
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

function colorVec(hex) {
  const c = new THREE.Color(hex);
  return { r: c.r, g: c.g, b: c.b };
}

function fetchJSON(url, options = {}, timeoutMs = 8000) {
  const controller = new AbortController();
  const external = options.signal;
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener('abort', () => controller.abort(), { once: true });
  }
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() => {
    window.clearTimeout(timer);
  });
}

function hasWebGL() {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(
      window.WebGLRenderingContext &&
        (canvas.getContext('webgl2') || canvas.getContext('webgl'))
    );
  } catch {
    return false;
  }
}

/* ------------------------------------------------------------------ */
/* 启动                                                                */
/* ------------------------------------------------------------------ */

async function boot() {
  await setState(S.BOOT, {}, true);
  hideAllHud();
  showBootNote('', false);

  let config = null;
  try {
    const response = await fetchJSON('/api/config', { cache: 'no-store' }, 6000);
    if (!response.ok) throw new Error('config');
    config = await response.json();
    if (!config || !config.ok) throw new Error('config');
  } catch {
    showBootNote(ui().config_failed || '', true);
    markSceneReady(true);
    return;
  }

  state.config = config;
  configureSeatGeometry((config.roles || []).length || 7);
  state.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  verifySeatColors();
  applySeatVariables();

  try {
    THREE = await import('three');
  } catch {
    setState(S.FALLBACK, { reason: 'three' });
    markSceneReady(true);
    return;
  }
  try {
    figures = await import('./figures.js');
  } catch {
    setState(S.FALLBACK, { reason: 'three' });
    markSceneReady(true);
    return;
  }

  if (!hasWebGL()) {
    setState(S.FALLBACK, { reason: 'nogl' });
    markSceneReady(true);
    return;
  }

  try {
    await initScene();
  } catch {
    setState(S.FALLBACK, { reason: 'nogl' });
    markSceneReady(true);
    return;
  }

  await awaitInkFonts(2000);
  buildHud();
  bindGlobalEvents();
  hideBootNote();

  setState(S.GATE);
  markSceneReady(false);
}

function markSceneReady(fallback) {
  window.huitongSceneReady = true;
  window.dispatchEvent(new CustomEvent('huitong:scene-ready', { detail: { fallback: Boolean(fallback) } }));
}

function dispatchSceneEntered() {
  window.dispatchEvent(new CustomEvent('huitong:entered'));
}

/* 工作区登录完成后直接进入厅堂，避免额外的墨线和墨晕过场。 */
async function handleWorkspaceEnter() {
  if (state.entrancePlayed || state.name === S.FALLBACK || !scene || state.name !== S.GATE) {
    dispatchSceneEntered();
    return;
  }
  state.entrancePlayed = true;
  state.entering = true;
  if (dom.gateMark) dom.gateMark.hidden = true;
  showDoorLeaves();
  await openDoors();
  setCameraOverviewInstant();
  showHallObjects();
  state.entering = false;
  await setState(S.OVERVIEW);
  dispatchSceneEntered();
}

function applySeatVariables() {
  for (const role of roles()) {
    document.documentElement.style.setProperty(`--seat-${role.seat}`, role.color);
  }
}

function verifySeatColors() {
  const styles = window.getComputedStyle(document.documentElement);
  for (const role of roles()) {
    const cssColor = styles.getPropertyValue(`--seat-${role.seat}`).trim().toLowerCase();
    if (cssColor !== String(role.color).toLowerCase()) {
      console.warn('seat color mismatch', role.seat, cssColor, role.color);
    }
  }
}

function hideAllHud() {
  for (const node of [
    dom.gateMark,
    dom.stageHud,
    dom.youPlate,
    dom.seatPlate,
    dom.leaveBtn,
    dom.startBtn,
    dom.toast,
  ]) {
    if (node) node.hidden = true;
  }
  for (const button of dom.seatHits || []) {
    button.hidden = true;
    button.disabled = true;
  }
}

function showBootNote(message, retry) {
  hideBootNote();
  const note = el('div', 'boot-note');
  const title = el('h1', null, ui().loading_title || document.title);
  const line = el('p', null, message || '');
  note.appendChild(title);
  if (message) note.appendChild(line);
  if (retry) {
    const button = el('button', 'paper-btn', ui().retry || '↻');
    button.type = 'button';
    button.addEventListener('click', () => {
      hideBootNote();
      boot();
    });
    note.appendChild(button);
  }
  dom.bootNote = note;
  document.body.appendChild(note);
}

function hideBootNote() {
  if (dom.bootNote && dom.bootNote.parentNode) {
    dom.bootNote.parentNode.removeChild(dom.bootNote);
  }
  dom.bootNote = null;
}

/* ------------------------------------------------------------------ */
/* 场景                                                                */
/* ------------------------------------------------------------------ */

async function initScene() {
  const canvas = document.getElementById('scene');
  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  renderer.setClearColor(new THREE.Color(PAPER_HEX), 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = false;
  renderer.autoClear = true;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(PAPER_HEX);

  // three r160 使用物理光照单位；按设计稿的观感换算回传统强度
  const lightScale = Math.PI;
  const hemisphere = new THREE.HemisphereLight(0xF2E8D2, 0x2A2E38, 0.95 * lightScale);
  scene.add(hemisphere);
  const keyLight = new THREE.DirectionalLight(0xFFF6E2, 0.35 * lightScale);
  keyLight.position.set(4, 10, 6);
  scene.add(keyLight);
  const doorLight = new THREE.DirectionalLight(0xC9D6E0, 0.15 * lightScale);
  doorLight.position.set(0, 3, 8);
  scene.add(doorLight);

  camera = new THREE.PerspectiveCamera(
    CAM.gate.fov,
    window.innerWidth / Math.max(1, window.innerHeight),
    0.05,
    120
  );
  camera.position.set(...CAM.gate.pos);
  state.camTarget = {
    x: CAM.gate.target[0],
    y: CAM.gate.target[1],
    z: CAM.gate.target[2],
  };
  camera.lookAt(state.camTarget.x, state.camTarget.y, state.camTarget.z);

  await nextFrame();
  const paper = makePaper(2048);
  paperTexture = new THREE.CanvasTexture(paper);
  paperTexture.colorSpace = THREE.SRGBColorSpace;
  paperTexture.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
  paperTexture.needsUpdate = true;

  buildHall();

  window.addEventListener('resize', onResize);
  window.addEventListener('orientationchange', onResize);
  buildSeatHits();
  onVisibility();
  watchDpr();
  applyLayout();
  onInkFontsLoaded(rebakeTexts);
  startLoop();
}

function makeStandardMaterial(options = {}) {
  const material = new THREE.MeshStandardMaterial({
    map: options.map === false ? null : paperTexture,
    color: new THREE.Color(options.color || '#FFFFFF'),
    roughness: options.roughness == null ? 1 : options.roughness,
    metalness: 0,
    transparent: Boolean(options.transparent),
    opacity: options.opacity == null ? 1 : options.opacity,
    side: options.side || THREE.FrontSide,
    depthWrite: options.depthWrite !== false,
  });
  if (options.ink != null) material.userData.ink = options.ink;
  return material;
}

function makePaperBasic(options = {}) {
  return new THREE.MeshBasicMaterial({
    map: paperTexture,
    color: new THREE.Color(options.color || '#FFFFFF'),
    transparent: Boolean(options.transparent),
    opacity: options.opacity == null ? 1 : options.opacity,
    side: options.side || THREE.FrontSide,
    depthWrite: options.depthWrite !== false,
  });
}

function addBox(width, height, depth, material, x, y, z, parent = scene) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
  mesh.position.set(x, y, z);
  parent.add(mesh);
  return mesh;
}

function addEdges(mesh, color = INK_HEX, opacity = 0.55) {
  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(mesh.geometry),
    new THREE.LineBasicMaterial({
      color: new THREE.Color(color),
      transparent: true,
      opacity,
    })
  );
  mesh.add(edges);
  return edges;
}

function addPlane(width, height, material, x, y, z, rotationY = 0, parent = scene) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height), material);
  mesh.position.set(x, y, z);
  mesh.rotation.y = rotationY;
  parent.add(mesh);
  return mesh;
}

function buildHall() {
  const floorMaterial = makePaperBasic();
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), floorMaterial);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = 0;
  scene.add(floor);

  const wash = new THREE.Mesh(
    new THREE.CircleGeometry(5.4, 64),
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(INK_HEX),
      transparent: true,
      opacity: 0.06,
      depthWrite: false,
    })
  );
  wash.rotation.x = -Math.PI / 2;
  wash.position.y = 0.002;
  scene.add(wash);

  const radialPositions = [];
  for (const seat of seatAngles) {
    radialPositions.push(0, 0.004, 0, seat.x * 0.46, 0.004, seat.z * 0.46);
  }
  const radialGeometry = new THREE.BufferGeometry();
  radialGeometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(radialPositions, 3)
  );
  scene.add(
    new THREE.LineSegments(
      radialGeometry,
      new THREE.LineBasicMaterial({
        color: new THREE.Color(INK_HEX),
        transparent: true,
        opacity: 0.03,
      })
    )
  );

  const wallMaterial = makePaperBasic();
  const south = 6.15;
  const north = -6.15;
  addBox(12, 5, 0.3, wallMaterial, 0, 2.5, north);
  addBox(0.3, 5, 12, wallMaterial, 6.15, 2.5, 0);
  addBox(0.3, 5, 12, wallMaterial, -6.15, 2.5, 0);

  // 南墙四块拼出门洞：左、右、上、下（下为门槛）
  addBox(4.5, 5, 0.3, wallMaterial, -3.75, 2.5, south);
  addBox(4.5, 5, 0.3, wallMaterial, 3.75, 2.5, south);
  addBox(3, 1.4, 0.3, wallMaterial, 0, 4.3, south);
  addBox(3, 0.04, 0.3, wallMaterial, 0, 0.02, south);

  const baseMaterial = new THREE.MeshBasicMaterial({ color: new THREE.Color(INK_4) });
  addBox(12, 0.12, 0.02, baseMaterial, 0, 0.06, -5.99);
  addBox(12, 0.12, 0.02, baseMaterial, 0, 0.06, 5.99);
  addBox(0.02, 0.12, 12, baseMaterial, 5.99, 0.06, 0);
  addBox(0.02, 0.12, 12, baseMaterial, -5.99, 0.06, 0);

  // 门楼：两柱、额枋、檐口
  const frameMaterial = makeStandardMaterial({
    map: false,
    color: '#5A5146',
    roughness: 0.88,
    metalness: 0.04,
  });
  const columnLeft = addBox(0.30, 4.10, 0.30, frameMaterial, -1.65, 2.05, 6.02);
  const columnRight = addBox(0.30, 4.10, 0.30, frameMaterial, 1.65, 2.05, 6.02);
  const lintel = addBox(3.90, 0.50, 0.34, frameMaterial, 0, 3.85, 6.02);
  const eave = addBox(4.40, 0.28, 0.90, frameMaterial, 0, 4.30, 6.24);
  eave.rotation.x = -0.16;
  addEdges(columnLeft, INK_HEX, 0.5);
  addEdges(columnRight, INK_HEX, 0.5);
  addEdges(lintel, INK_HEX, 0.5);
  addEdges(eave, INK_HEX, 0.5);
  state.doorFrame = [columnLeft, columnRight, lintel, eave];
  for (const part of state.doorFrame) part.visible = false;

  buildDoors();
  buildPlaque();
  buildScrolls();
  buildCouplets();
  buildLandscape();
  buildTable();
  buildCushions();
  buildOutside();
}

function buildDoors() {
  const doorMaterial = makeStandardMaterial({
    map: false,
    color: '#645A4D',
    roughness: 0.82,
    metalness: 0.02,
  });
  const railMaterial = makeStandardMaterial({
    map: false,
    color: '#4B4339',
    roughness: 0.88,
  });
  const insetMaterial = makeStandardMaterial({
    map: false,
    color: '#8D7D68',
    roughness: 0.94,
  });
  const bronzeMaterial = new THREE.MeshStandardMaterial({
    color: new THREE.Color('#8B6C45'),
    roughness: 0.48,
    metalness: 0.58,
  });
  const vermilionMaterial = new THREE.MeshStandardMaterial({
    color: new THREE.Color('#A83224'),
    roughness: 0.62,
    metalness: 0.05,
  });
  const pivots = [];
  state.doorLeaves = [];
  for (const side of [-1, 1]) {
    const pivot = new THREE.Object3D();
    pivot.position.set(side * 1.5, 1.8, 6.0);
    scene.add(pivot);
    const leaf = new THREE.Group();
    leaf.position.x = -side * 0.75;
    leaf.visible = false;
    pivot.add(leaf);
    state.doorLeaves.push(leaf);

    const panel = addBox(1.46, 3.34, 0.10, doorMaterial, 0, 0, 0, leaf);
    addEdges(panel, '#2A2722', 0.40);
    // 六格内嵌门芯：用浅一层的木色和细墨线做出木构比例。
    const panelYs = [-1.12, 0, 1.12];
    for (const y of panelYs) {
      const inset = addBox(1.05, 0.82, 0.018, insetMaterial, 0, y, -0.061, leaf);
      addEdges(inset, '#4B4339', 0.30);
      addBox(0.07, 0.84, 0.035, railMaterial, -0.58, y, -0.065, leaf);
      addBox(0.07, 0.84, 0.035, railMaterial, 0.58, y, -0.065, leaf);
    }
    for (const y of [-1.67, -0.56, 0.56, 1.67]) {
      addBox(1.54, 0.11, 0.13, railMaterial, 0, y, -0.015, leaf);
    }
    for (const x of [-0.70, 0.70]) {
      addBox(0.12, 3.42, 0.13, railMaterial, x, 0, -0.015, leaf);
    }

    // 低调的朱砂门钉，替换旧版 5×5 黑色圆点阵。
    const nailGeometry = new THREE.SphereGeometry(0.026, 10, 6);
    const nails = new THREE.InstancedMesh(nailGeometry, bronzeMaterial, 12);
    const matrix = new THREE.Matrix4();
    let index = 0;
    for (const y of [-1.12, 0, 1.12]) {
      for (const x of [-0.48, 0.48]) {
        matrix.makeTranslation(x, y + 0.30, -0.095);
        nails.setMatrixAt(index, matrix);
        index += 1;
        matrix.makeTranslation(x, y - 0.30, -0.095);
        nails.setMatrixAt(index, matrix);
        index += 1;
      }
    }
    nails.instanceMatrix.needsUpdate = true;
    leaf.add(nails);

    const latchPlate = addBox(0.18, 0.28, 0.035, bronzeMaterial, side * 0.67, 0.02, -0.105, leaf);
    latchPlate.rotation.z = side * 0.08;
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.105, 0.016, 10, 32), bronzeMaterial);
    ring.position.set(side * 0.67, -0.05, -0.135);
    ring.rotation.x = 0;
    leaf.add(ring);
    const pin = new THREE.Mesh(new THREE.SphereGeometry(0.022, 10, 6), vermilionMaterial);
    pin.position.set(side * 0.67, 0.10, -0.145);
    leaf.add(pin);

    // 中心门缝的纵向墨线让两扇门在远景仍然清楚。
    const seam = addBox(0.018, 3.18, 0.018, railMaterial, side * 0.04, 0, -0.084, leaf);
    seam.userData.kind = 'door-seam';
    pivots.push(pivot);
  }
  state.doorPivots = pivots;
}

function showDoorLeaves() {
  for (const leaf of state.doorLeaves) leaf.visible = true;
  for (const part of state.doorFrame || []) part.visible = true;
  for (const plane of state.couplets || []) plane.visible = true;
}

function buildPlaque() {
  const text = ui().gate_title || '';
  const texture = new THREE.CanvasTexture(
    makeScrollTexture(text, {
      w: 1024,
      h: 288,
      fontSize: 176,
      vertical: false,
      rods: false,
      bg: '#F7EFDC',
    })
  );
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.MeshBasicMaterial({ map: texture });
  const plaque = addPlane(3.2, 0.9, material, 0, 4.2, -5.95);
  plaque.userData.texture = texture;
  plaque.userData.kind = 'plaque';
  state.plaque = plaque;

  const borderGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-1.58, -0.43, 0.01),
    new THREE.Vector3(1.58, -0.43, 0.01),
    new THREE.Vector3(1.58, 0.43, 0.01),
    new THREE.Vector3(-1.58, 0.43, 0.01),
  ]);
  const border = new THREE.LineLoop(
    borderGeometry,
    new THREE.LineBasicMaterial({
      color: new THREE.Color('#A83224'),
      transparent: true,
      opacity: 0.3,
    })
  );
  plaque.add(border);
}

function buildScrolls() {
  state.scrollMeshes = {};
  state.scrollMaterials = {};
  const list = stages();
  const zs = [-3.3, -1.1, 1.1, 3.3];
  for (let i = 0; i < list.length; i += 1) {
    const stage = list[i];
    const texture = new THREE.CanvasTexture(
      makeScrollTexture(stage.name, {
        w: 256,
        h: 1024,
        fontSize: 96,
        vertical: true,
        rods: true,
      })
    );
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      color: new THREE.Color('#D8CCB2'),
    });
    const east = i < 4;
    const mesh = addPlane(
      0.62,
      2.2,
      material,
      east ? 5.96 : -5.96,
      2.55,
      zs[i % 4],
      east ? -Math.PI / 2 : Math.PI / 2
    );
    mesh.userData.stageId = stage.id;
    state.scrollMeshes[stage.id] = mesh;
    state.scrollMaterials[stage.id] = material;
  }
}

function buildCouplets() {
  const family = "'Zhi Mang Xing','Kaiti SC','STKaiti',serif";
  const rightTexture = new THREE.CanvasTexture(
    makeScrollTexture(ui().couplet_right || '', {
      w: 256,
      h: 1024,
      fontSize: 70,
      vertical: true,
      rods: false,
      bg: false,
      color: '#3A342C',
      font: family,
    })
  );
  const leftTexture = new THREE.CanvasTexture(
    makeScrollTexture(ui().couplet_left || '', {
      w: 256,
      h: 1024,
      fontSize: 70,
      vertical: true,
      rods: false,
      bg: false,
      color: '#3A342C',
      font: family,
    })
  );
  rightTexture.colorSpace = THREE.SRGBColorSpace;
  leftTexture.colorSpace = THREE.SRGBColorSpace;
  state.coupletTextures = [rightTexture, leftTexture];
  const right = addPlane(
    0.34,
    2.4,
    new THREE.MeshBasicMaterial({ map: rightTexture, transparent: true }),
    -1.78,
    1.75,
    5.95,
    Math.PI
  );
  const left = addPlane(
    0.34,
    2.4,
    new THREE.MeshBasicMaterial({ map: leftTexture, transparent: true }),
    1.78,
    1.75,
    5.95,
    Math.PI
  );
  right.userData.kind = 'couplet';
  left.userData.kind = 'couplet';
  right.visible = false;
  left.visible = false;
  state.couplets = [right, left];
}

function buildLandscape() {
  const layers = [
    { opacity: 0.55, z: -5.94 },
    { opacity: 0.38, z: -5.93 },
    { opacity: 0.22, z: -5.92 },
  ];
  for (let i = 0; i < layers.length; i += 1) {
    const texture = new THREE.CanvasTexture(makeMountainTexture(i));
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      opacity: layers[i].opacity,
      depthWrite: false,
    });
    addPlane(1.6, 1.2, material, 0, 2.3, layers[i].z);
  }
}

function buildTable() {
  const material = makeStandardMaterial();
  const top = addBox(1.9, 0.06, 0.72, material, 0, 0.42, 0);
  addEdges(top, INK_HEX, 0.45);
  for (const x of [-0.89, 0.89]) {
    for (const z of [-0.33, 0.33]) {
      addBox(0.06, 0.39, 0.06, material, x, 0.195, z);
    }
  }

  const ledgerMaterial = makeStandardMaterial({ color: '#F7EFDC' });
  const ledger = addBox(0.42, 0.03, 0.30, ledgerMaterial, -0.45, 0.465, 0.05);
  addEdges(ledger, INK_HEX, 0.35);

  const bronze = makeStandardMaterial({ color: '#5E5648' });
  const censer = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.08, 0.10, 18), bronze);
  censer.position.set(0.18, 0.50, -0.08);
  scene.add(censer);
  for (let i = 0; i < 3; i += 1) {
    const angle = (i / 3) * Math.PI * 2;
    const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.04, 6), bronze);
    foot.position.set(
      0.18 + Math.cos(angle) * 0.06,
      0.44,
      -0.08 + Math.sin(angle) * 0.06
    );
    scene.add(foot);
  }

  const lampMaterial = makeStandardMaterial({ color: '#F7EFDC' });
  const lamp = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.045, 0.12, 16), lampMaterial);
  lamp.position.set(0.62, 0.51, 0.10);
  scene.add(lamp);
  const flame = new THREE.Mesh(
    new THREE.SphereGeometry(0.014, 8, 6),
    new THREE.MeshBasicMaterial({ color: new THREE.Color('#A83224') })
  );
  flame.position.set(0.62, 0.585, 0.10);
  scene.add(flame);

}

function buildCushions() {
  state.cushions = [];
  state.rings = [];
  state.props = [];
  state.pickTargets = [];
  for (const role of roles()) {
    const seat = role.seat;
    const geometry = new THREE.CylinderGeometry(0.48, 0.52, 0.18, 40, 4, false);
    const position = geometry.attributes.position;
    for (let i = 0; i < position.count; i += 1) {
      const y = position.getY(i);
      if (y > 0.079) {
        const x = position.getX(i);
        const z = position.getZ(i);
        const radius = Math.min(1, Math.hypot(x, z) / 0.48);
        position.setY(i, y - 0.015 * (1 - radius * 0.58));
      }
    }
    position.needsUpdate = true;
    geometry.computeVertexNormals();

    const cushionTexture = new THREE.CanvasTexture(makeCushionTexture(role.color, seat));
    cushionTexture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.MeshStandardMaterial({
      map: cushionTexture,
      roughness: 1,
      metalness: 0,
    });
    const group = new THREE.Group();
    group.position.set(seatAngles[seat].x, 0, seatAngles[seat].z);
    group.rotation.y = -seatAngles[seat].angle;
    group.visible = false;
    const body = new THREE.Mesh(geometry, material);
    body.position.y = 0.08;
    body.userData.seatIndex = seat;
    group.add(body);
    scene.add(group);

    const waistColor = new THREE.Color(role.color).multiplyScalar(0.78);
    const waist = new THREE.Mesh(
      new THREE.TorusGeometry(0.50, 0.014, 8, 40),
      new THREE.MeshStandardMaterial({ color: waistColor, roughness: 1, metalness: 0 })
    );
    waist.rotation.x = Math.PI / 2;
    waist.position.y = 0.14;
    group.add(waist);

    const stitch = new THREE.Mesh(
      new THREE.TorusGeometry(0.34, 0.008, 6, 36),
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(role.color),
        transparent: true,
        opacity: 0.58,
        roughness: 0.9,
        metalness: 0,
      })
    );
    stitch.rotation.x = Math.PI / 2;
    stitch.position.y = 0.176;
    group.add(stitch);

    const tuft = new THREE.Mesh(
      new THREE.SphereGeometry(0.028, 10, 6),
      new THREE.MeshStandardMaterial({ color: new THREE.Color('#F7EFDC'), roughness: 1, metalness: 0 })
    );
    tuft.position.y = 0.178;
    group.add(tuft);

    const tasselPositions = [];
    for (let i = 0; i < 6; i += 1) {
      const angle = (i / 6) * Math.PI * 2;
      const x = Math.cos(angle) * 0.47;
      const z = Math.sin(angle) * 0.47;
      tasselPositions.push(x, 0.15, z, x, 0.10, z);
    }
    const tasselGeometry = new THREE.BufferGeometry();
    tasselGeometry.setAttribute(
      'position',
      new THREE.Float32BufferAttribute(tasselPositions, 3)
    );
    group.add(
      new THREE.LineSegments(
        tasselGeometry,
        new THREE.LineBasicMaterial({
          color: new THREE.Color(INK_4),
          transparent: true,
          opacity: 0.5,
        })
      )
    );

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.5, 0.62, 48, 1),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(INK_HEX),
        transparent: true,
        opacity: 0,
        side: THREE.DoubleSide,
        depthWrite: false,
      })
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(seatAngles[seat].x, 0.006, seatAngles[seat].z);
    ring.visible = false;
    scene.add(ring);

    state.cushions[seat] = group;
    state.rings[seat] = ring;
    state.pickTargets.push(body);
    buildProp(role);
  }
}

function buildProp(role) {
  const seat = role.seat;
  const angle = seatAngles[seat].angle;
  const dirX = Math.sin(angle);
  const dirZ = -Math.cos(angle);
  const tangentX = Math.cos(angle);
  const tangentZ = Math.sin(angle);
  const offset = seat % 2 ? 0.10 : 0;
  const x = seatAngles[seat].x + dirX * 0.52 + tangentX * offset;
  const z = seatAngles[seat].z + dirZ * 0.52 + tangentZ * offset;
  const group = new THREE.Group();
  group.position.set(x, 0.20, z);
  group.rotation.y = -angle;
  group.visible = false;
  scene.add(group);
  state.props[seat] = group;

  const inkMaterial = makeStandardMaterial({ color: '#3A342C' });
  const paperMaterial = makeStandardMaterial({ color: '#F7EFDC' });
  const accentMaterial = makeStandardMaterial({ color: role.color });

  switch (role.prop_id) {
    case 'ruler': {
      const ruler = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.022, 0.05), inkMaterial);
      ruler.rotation.z = 0.26;
      ruler.position.y = 0.02;
      group.add(ruler);
      state.rulerMesh = ruler;
      break;
    }
    case 'scroll': {
      const roll = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.42, 12), paperMaterial);
      roll.rotation.z = Math.PI / 2;
      roll.position.y = 0.02;
      group.add(roll);
      const sheet = new THREE.Mesh(new THREE.PlaneGeometry(0.20, 0.16), paperMaterial);
      sheet.rotation.x = -Math.PI / 2;
      sheet.position.set(0.12, 0.035, 0.09);
      group.add(sheet);
      break;
    }
    case 'slips': {
      const base = new THREE.Mesh(new THREE.BoxGeometry(0.30, 0.02, 0.18), paperMaterial);
      base.position.y = 0.02;
      group.add(base);
      for (let i = 0; i < 8; i += 1) {
        const line = new THREE.Mesh(
          new THREE.BoxGeometry(0.004, 0.004, 0.16),
          inkMaterial
        );
        line.position.set(-0.126 + i * 0.036, 0.032, 0);
        group.add(line);
      }
      break;
    }
    case 'brush': {
      const restLeft = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.03, 6), inkMaterial);
      restLeft.position.set(-0.09, 0.015, 0);
      group.add(restLeft);
      const restRight = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.03, 6), inkMaterial);
      restRight.position.set(0.09, 0.015, 0);
      group.add(restRight);
      const brush = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.001, 0.26, 6), inkMaterial);
      brush.rotation.z = Math.PI / 2;
      brush.position.y = 0.05;
      group.add(brush);
      break;
    }
    case 'ledger': {
      const book = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.035, 0.19), paperMaterial);
      book.position.y = 0.02;
      group.add(book);
      for (let i = 0; i < 3; i += 1) {
        const line = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.003, 0.003), inkMaterial);
        line.position.set(0, 0.04, -0.05 + i * 0.05);
        group.add(line);
      }
      break;
    }
    case 'seal': {
      const block = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.09, 0.07), inkMaterial);
      block.position.y = 0.045;
      group.add(block);
      const top = new THREE.Mesh(new THREE.BoxGeometry(0.064, 0.006, 0.064), accentMaterial);
      top.position.y = 0.093;
      group.add(top);
      break;
    }
    default:
      break;
  }
}

function buildOutside() {
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(200, 100),
    makePaperBasic()
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0, -0.02, 30);
  scene.add(ground);

  const stepMaterial = makeStandardMaterial({ roughness: 1 });
  for (let i = 0; i < 6; i += 1) {
    const step = addBox(3.2, 0.16, 0.35, stepMaterial, 0, -0.08 - i * 0.16, 6.42 + i * 0.35);
    addEdges(step, INK_HEX, 0.25);
  }

  for (const side of [-1, 1]) {
    const x = side * 2.6;
    const trunk = new THREE.Mesh(
      new THREE.CylinderGeometry(0.03, 0.05, 1.2, 8),
      makeStandardMaterial({ color: '#3A342C' })
    );
    trunk.position.set(x, 0.6, 9.0);
    scene.add(trunk);
  }

  const mountains = [
    { z: 14, width: 40, y: 2.4, color: '#8B806C', opacity: 0.55, height: 8 },
    { z: 20, width: 56, y: 3.2, color: '#B7AB92', opacity: 0.38, height: 10 },
    { z: 28, width: 72, y: 4.0, color: '#DCCB9F', opacity: 0.22, height: 12 },
  ];
  for (let i = 0; i < mountains.length; i += 1) {
    const layer = mountains[i];
    const texture = new THREE.CanvasTexture(makeMountainTexture(2 - i));
    texture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      color: new THREE.Color(layer.color),
      transparent: true,
      opacity: layer.opacity,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(layer.width, layer.height), material);
    plane.position.set(0, layer.y, layer.z);
    plane.rotation.y = Math.PI;
    scene.add(plane);
  }
}

/* ------------------------------------------------------------------ */
/* 墨化注入与后期                                                       */
/* ------------------------------------------------------------------ */

function inkify(material, rim = 0.45) {
  if (!material || !material.isMeshStandardMaterial) return;
  if (material.userData.inkified) return;
  material.userData.inkified = true;
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uInkColor = { value: new THREE.Color(INK_HEX) };
    shader.uniforms.uRim = { value: rim };
    shader.fragmentShader =
      'uniform vec3 uInkColor; uniform float uRim;\n' + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <opaque_fragment>',
      `float rimF = pow(1.0 - clamp(dot(normalize(vNormal), normalize(vViewPosition)), 0.0, 1.0), 2.2);
       outgoingLight = mix(outgoingLight, uInkColor, rimF * uRim);
       #include <opaque_fragment>`
    );
  };
  material.customProgramCacheKey = () => `ink${rim}`;
}

function applyInkify() {
  const seen = new Set();
  scene.traverse((object) => {
    if (!object.isMesh || !object.material) return;
    const list = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of list) {
      if (!material.isMeshStandardMaterial || seen.has(material)) continue;
      seen.add(material);
      const rim = object.userData.rim || material.userData.rim || 0.45;
      inkify(material, rim);
    }
  });
}

function buildPost() {
  const width = Math.max(2, Math.floor((window.innerWidth * renderer.getPixelRatio()) / 2));
  const height = Math.max(2, Math.floor((window.innerHeight * renderer.getPixelRatio()) / 2));
  postTarget = new THREE.WebGLRenderTarget(width, height, {
    type: THREE.UnsignedByteType,
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    depthBuffer: true,
    stencilBuffer: false,
  });
  postScene = new THREE.Scene();
  postCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  postMaterial = new THREE.ShaderMaterial({
    uniforms: {
      tScene: { value: postTarget.texture },
      tPaper: { value: paperTexture },
      uTexel: { value: new THREE.Vector2(1 / width, 1 / height) },
      uPaperColor: { value: new THREE.Color(PAPER_HEX).convertSRGBToLinear() },
      uAspect: { value: window.innerWidth / Math.max(1, window.innerHeight) },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = vec4(position.xy, 0.0, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D tScene;
      uniform sampler2D tPaper;
      uniform vec2 uTexel;
      uniform vec3 uPaperColor;
      uniform float uAspect;
      varying vec2 vUv;

      void main() {
        vec2 o = uTexel * 2.0;
        vec3 base = texture2D(tScene, vUv).rgb;
        vec3 blur = vec3(0.0);
        blur += 0.0625 * texture2D(tScene, vUv + vec2(-o.x, -o.y)).rgb;
        blur += 0.1250 * texture2D(tScene, vUv + vec2( 0.0, -o.y)).rgb;
        blur += 0.0625 * texture2D(tScene, vUv + vec2( o.x, -o.y)).rgb;
        blur += 0.1250 * texture2D(tScene, vUv + vec2(-o.x,  0.0)).rgb;
        blur += 0.2500 * texture2D(tScene, vUv).rgb;
        blur += 0.1250 * texture2D(tScene, vUv + vec2( o.x,  0.0)).rgb;
        blur += 0.0625 * texture2D(tScene, vUv + vec2(-o.x,  o.y)).rgb;
        blur += 0.1250 * texture2D(tScene, vUv + vec2( 0.0,  o.y)).rgb;
        blur += 0.0625 * texture2D(tScene, vUv + vec2( o.x,  o.y)).rgb;
        vec3 col = mix(base, blur, 0.35);
        col = pow(max(col, vec3(0.0)), vec3(1.06));
        vec2 paperUv = fract(vUv * vec2(uAspect, 1.0));
        col *= texture2D(tPaper, paperUv).rgb;
        float mist = smoothstep(0.14, 0.0, vUv.y);
        col = mix(col, uPaperColor, mist * 0.55);
        float vig = smoothstep(0.30, 0.95, length(vUv - 0.5));
        col = mix(col, uPaperColor, vig * 0.10);
        col = pow(max(col, vec3(0.0)), vec3(1.0 / 2.2));
        gl_FragColor = vec4(col, 1.0);
      }
    `,
    depthTest: false,
    depthWrite: false,
  });
  const triangle = new THREE.BufferGeometry();
  triangle.setAttribute(
    'position',
    new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3)
  );
  triangle.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
  postScene.add(new THREE.Mesh(triangle, postMaterial));
}

/* ------------------------------------------------------------------ */
/* 布局与渲染                                                           */
/* ------------------------------------------------------------------ */

function panelWidth() {
  if (!state.panelOpen) return 0;
  const panel = document.getElementById('panel');
  if (!panel) return 0;
  if (window.innerWidth <= 720) return 0;
  return panel.offsetWidth || 0;
}

function applyLayout() {
  if (!renderer || !camera) return;
  const width = window.innerWidth;
  const height = window.innerHeight;
  if (width < 2 || height < 2) return;
  const dpr = Math.min(window.devicePixelRatio || 1, degraded ? 1 : 2);
  renderer.setPixelRatio(dpr);
  renderer.setSize(width, height, false);

  const vw = Math.max(2, width - panelWidth());
  const vh = Math.max(2, height);
  state.viewport = { w: vw, h: vh };
  camera.aspect = vw / vh;
  if (state.name === S.SEATED || state.name === S.PANEL) {
    camera.fov = clamp(56 + Math.max(0, (1 / camera.aspect - 1) * 12), 56, 66);
  }
  camera.updateProjectionMatrix();

  if (postTarget) {
    postTarget.setSize(
      Math.max(2, Math.floor((width * dpr) / 2)),
      Math.max(2, Math.floor((height * dpr) / 2))
    );
    if (postMaterial) {
      postMaterial.uniforms.uTexel.value.set(1 / postTarget.width, 1 / postTarget.height);
      postMaterial.uniforms.uAspect.value = width / height;
    }
  }
  if (state.name === S.OVERVIEW) fitOverview();
  updateSeatHitPositions();
}

function fitOverview() {
  if (!camera) return;
  const width = window.innerWidth;
  const height = window.innerHeight;
  if (width < 2 || height < 2) return;
  const vw = Math.max(2, width - panelWidth());
  const aspect = vw / height;
  let k = Math.max(1, 1.18 / aspect);
  if (aspect < 0.6) k = Math.min(k, 1.45);
  const target = CAM.overview.target;
  const r = CAM.overview.r * k;
  const polar = CAM.overview.polar;
  camera.position.set(
    0,
    target[1] + Math.cos(polar) * r,
    target[2] + Math.sin(polar) * r
  );
  camera.fov = aspect < 0.85 ? 50 : 45;
  camera.updateProjectionMatrix();
  camera.lookAt(target[0], target[1], target[2]);
  state.camTarget = { x: target[0], y: target[1], z: target[2] };
}

function setCameraGate() {
  const aspect = window.innerWidth / Math.max(1, window.innerHeight);
  const distance = aspect < 0.85 ? 6.70 : 4.65;
  camera.position.set(0, 1.70, 5.95 - distance);
  state.camTarget = {
    x: CAM.gate.target[0],
    y: CAM.gate.target[1],
    z: CAM.gate.target[2],
  };
  camera.fov = CAM.gate.fov;
  camera.updateProjectionMatrix();
  camera.lookAt(state.camTarget.x, state.camTarget.y, state.camTarget.z);
  state.gatePointer = { x: 0, y: 0 };
}

function setCameraSeat(seat) {
  const config = CAM.seats[seat];
  camera.position.set(...config.pos);
  state.camTarget = { ...seatTargetVec };
  camera.fov = clamp(
    56 + Math.max(0, (1 / (state.viewport.w / state.viewport.h) - 1) * 12),
    56,
    66
  );
  camera.updateProjectionMatrix();
  camera.lookAt(state.camTarget.x, state.camTarget.y, state.camTarget.z);
}

function renderFrame() {
  if (!renderer || !scene || !camera) return;
  const width = window.innerWidth;
  const height = window.innerHeight;
  const vw = state.viewport.w;
  const vh = state.viewport.h;
  const pixelRatio = renderer.getPixelRatio();

  if (degraded || !postTarget || !postMaterial) {
    renderer.setRenderTarget(null);
    renderer.setScissorTest(false);
    renderer.setViewport(0, 0, width, height);
    renderer.setClearColor(new THREE.Color(PAPER_HEX), 1);
    renderer.clear();
    renderer.setScissorTest(true);
    renderer.setScissor(0, 0, vw, vh);
    renderer.setViewport(0, 0, vw, vh);
    renderer.render(scene, camera);
    renderer.setScissorTest(false);
    return;
  }

  renderer.setRenderTarget(postTarget);
  renderer.setScissorTest(false);
  renderer.setViewport(0, 0, postTarget.width / pixelRatio, postTarget.height / pixelRatio);
  renderer.setClearColor(new THREE.Color(PAPER_HEX), 1);
  renderer.clear();
  renderer.setScissorTest(true);
  renderer.setScissor(0, 0, vw / 2, vh / 2);
  renderer.setViewport(0, 0, vw / 2, vh / 2);
  renderer.render(scene, camera);

  renderer.setScissorTest(false);
  renderer.setRenderTarget(null);
  renderer.setViewport(0, 0, width, height);
  renderer.setClearColor(new THREE.Color(PAPER_HEX), 1);
  renderer.clear();
  renderer.render(postScene, postCamera);
}

function startLoop() {
  if (state.raf) cancelAnimationFrame(state.raf);
  state.lastT = performance.now();
  const loop = (now) => {
    state.raf = requestAnimationFrame(loop);
    if (document.hidden) return;
    const dt = Math.min(0.05, Math.max(0, (now - state.lastT) / 1000));
    state.lastT = now;
    animate(now, dt);
    renderFrame();

    frameTimes.push(dt * 1000);
    frameCount += 1;
    if (frameTimes.length > 60) frameTimes.shift();
    if (!degraded && frameCount % 60 === 0 && frameTimes.length === 60) {
      const sorted = frameTimes.slice().sort((a, b) => a - b);
      const p95 = sorted[Math.floor(sorted.length * 0.95)];
      if (p95 > 24) {
        degraded = true;
        applyLayout();
      }
    }
  };
  state.raf = requestAnimationFrame(loop);
}

function animate(now, dt) {
  if (!THREE) return;
  if (state.name === S.GATE && !state.entering) updateGateParallax(dt);
  updateCushionHover(dt);
  updateScrollLight(dt);
  updateFigures(now, dt);
  updateSeatPlates();
}

function updateGateParallax(dt) {
  const targetX = state.pointer.x * 0.06;
  const targetY = state.pointer.y * 0.03;
  const k = 1 - Math.exp(-dt * 4.8);
  state.gatePointer.x += (targetX - state.gatePointer.x) * k;
  state.gatePointer.y += (targetY - state.gatePointer.y) * k;
  camera.position.x = CAM.gate.pos[0] + state.gatePointer.x;
  camera.position.y = CAM.gate.pos[1] + state.gatePointer.y;
  const tx = CAM.gate.target[0] + state.pointer.x * 0.10;
  state.camTarget.x += (tx - state.camTarget.x) * k;
  camera.lookAt(state.camTarget.x, CAM.gate.target[1], CAM.gate.target[2]);
}

function updateCushionHover(dt) {
  if (!state.cushions) return;
  const k = 1 - Math.exp(-dt * (1000 / 120));
  for (let seat = 0; seat < state.cushions.length; seat += 1) {
    const group = state.cushions[seat];
    if (!group) continue;
    const targetY = state.name === S.OVERVIEW && state.hovered === seat ? 0.03 : 0;
    group.position.y += (targetY - group.position.y) * k;
    const ring = state.rings[seat];
    if (ring) {
      const targetOpacity = state.name === S.OVERVIEW && state.hovered === seat ? 0.25 : 0;
      ring.material.opacity += (targetOpacity - ring.material.opacity) * k;
    }
  }
}

function updateScrollLight(dt) {
  if (!state.scrollMaterials) return;
  const k = 1 - Math.exp(-dt * 6);
  const active = state.stageId;
  if (!state.scrollColors) {
    state.scrollColors = {
      bright: new THREE.Color('#FFFFFF'),
      dim: new THREE.Color('#CFC1A5'),
    };
  }
  const { bright, dim } = state.scrollColors;
  for (const stage of stages()) {
    const material = state.scrollMaterials[stage.id];
    if (!material) continue;
    const target = stage.id === active ? bright : dim;
    material.color.lerp(target, k);
  }
}

function updateFigures(now, dt) {
  for (const mesh of state.figureMeshes) {
    if (!mesh || !mesh.material) continue;
    mesh.material.uniforms.uTime.value = now / 1000;
    if (!reduced()) {
      mesh.position.y = 0.16 + Math.sin(now / 1800 + mesh.userData.seat) * 0.0025;
    }
  }
}

/* ------------------------------------------------------------------ */
/* 状态机                                                              */
/* ------------------------------------------------------------------ */

let seatRaycaster = null;
let lastHoverAt = 0;

function numeral(order) {
  const list = ui().numeral || [];
  return list[order - 1] || String(order);
}

function enterState(name, payload = {}, token = 0) {
  switch (name) {
    case S.GATE:
      return enterGate(payload, token);
    case S.WIPE:
      return enterWipe(payload, token);
    case S.OVERVIEW:
      return enterOverview(payload, token);
    case S.DESCEND:
      return enterDescend(payload, token);
    case S.SEATED:
      return enterSeated(payload, token);
    case S.PANEL:
      return enterPanel(payload, token);
    case S.CLOSING:
      return enterClosing(payload, token);
    case S.FALLBACK:
      return enterFallback(payload, token);
    default:
      return Promise.resolve();
  }
}

function exitState(previous, next) {
  clearHudTimers();
  if (previous === S.PANEL && next !== S.CLOSING) {
    stopPolling();
    if (next === S.SEATED) closePanel();
  }
  if (previous === S.SEATED && next === S.WIPE) {
    stopPolling();
  }
  if (previous === S.OVERVIEW) {
    state.hovered = null;
  }
}

async function setState(next, payload = {}, force = false) {
  if (state.name === next && !force) return;
  const previous = state.name;
  exitState(previous, next);
  state.name = next;
  document.body.dataset.state = next;
  setHudForState(next);
  const token = ++state.enterToken;
  await enterState(next, payload, token);
}

function clearHudTimers() {
  for (const timer of state.hudTimers || []) window.clearTimeout(timer);
  state.hudTimers = [];
}

function later(fn, ms) {
  const timer = window.setTimeout(fn, ms);
  if (!state.hudTimers) state.hudTimers = [];
  state.hudTimers.push(timer);
  return timer;
}

function setHudForState(name) {
  if (!dom.hud) return;
  const gate = name === S.GATE;
  dom.gateMark.hidden = !gate;
  dom.stageHud.hidden = !(name === S.PANEL || name === S.CLOSING);
  dom.stageHud.classList.toggle(
    'show',
    (name === S.PANEL || name === S.CLOSING) && Boolean(state.stageId)
  );
  dom.leaveBtn.hidden = name !== S.SEATED;
  dom.startBtn.hidden = name !== S.SEATED;
  dom.youPlate.hidden = name !== S.SEATED;
  dom.youPlate.classList.toggle('show', name === S.SEATED);
  if (name !== S.SEATED && name !== S.GATE) dom.toast.hidden = true;

  const overview = name === S.OVERVIEW;
  for (const button of dom.seatHits || []) {
    button.hidden = !overview;
    button.disabled = !overview;
  }
  if (!overview) {
    state.hovered = null;
    if (dom.seatPlate) dom.seatPlate.hidden = true;
  }
  if (renderer && renderer.domElement) {
    const blocked = name === S.WIPE || name === S.DESCEND || name === S.CLOSING || state.entering;
    renderer.domElement.style.pointerEvents = blocked ? 'none' : 'auto';
  }
}

function showToast(message, ms = 2600) {
  if (!dom.toast || !message) return;
  dom.toast.textContent = message;
  dom.toast.hidden = false;
  window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => {
    if (dom.toast) dom.toast.hidden = true;
  }, ms);
}

function enterGate(payload, token) {
  state.seat = null;
  state.session = null;
  state.awaiting = false;
  state.leaving = false;
  state.stageId = null;
  stopPolling();
  resetPanel();
  setCameraGate();
}


function openDoors() {
  if (!state.doorPivots || state.doorPivots.length < 2) return Promise.resolve();
  const left = state.doorPivots[0];
  const right = state.doorPivots[1];
  if (reduced()) {
    left.rotation.y = -1.745;
    right.rotation.y = 1.745;
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const total = 880;
    const begin = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - begin) / total);
      const eased = easeInOutCubic(t);
      left.rotation.y = -1.745 * eased;
      right.rotation.y = 1.745 * eased;
      if (t >= 1) resolve();
      else requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

async function enterWipe(payload, token) {
  stopPolling();
  closePanel();
  const to = payload.to || 'overview';
  if (token !== state.enterToken) return;
  if (to === 'overview') {
    setCameraOverviewInstant();
    showHallObjects();
    setState(S.OVERVIEW);
  }
}

function showHallObjects() {
  for (const group of state.cushions || []) if (group) group.visible = true;
  for (const group of state.props || []) if (group) group.visible = true;
  for (const ring of state.rings || []) if (ring) ring.visible = true;
}

function setCameraOverviewInstant() {
  if (!camera) return;
  fitOverview();
  updateSeatHitPositions();
}

function enterOverview(payload, token) {
  stopPolling();
  cleanupFigures(true);
  resetRuler();
  resetPanel();
  state.seat = null;
  state.session = null;
  state.awaiting = false;
  state.leaving = false;
  state.stageId = null;
  state.lastSeq = 0;
  state.hovered = null;
  showHallObjects();
  setCameraOverviewInstant();
}

async function enterDescend(payload, token) {
  const seat = payload.seat;
  if (!Number.isInteger(seat) || seat < 0 || seat >= roles().length) {
    setState(S.OVERVIEW);
    return;
  }
  state.seat = seat;
  state.hovered = null;
  state.leaving = false;
  if (dom.seatPlate) dom.seatPlate.hidden = true;
  const ok = await descendCamera(seat, token);
  if (!ok || token !== state.enterToken) return;
  createFiguresForSeat(seat);
  if (token !== state.enterToken) return;
  setState(S.SEATED, { figuresReady: true });
}

function descendCamera(seat, token) {
  return new Promise((resolve) => {
    if (!camera) {
      resolve(false);
      return;
    }
    const startPos = camera.position.clone();
    const startTarget = new THREE.Vector3(
      state.camTarget.x,
      state.camTarget.y,
      state.camTarget.z
    );
    const endPos = new THREE.Vector3(...CAM.seats[seat].pos);
    const endTarget = new THREE.Vector3(SEAT_TARGET.x, SEAT_TARGET.y, SEAT_TARGET.z);
    const startDelta = startPos.clone().sub(startTarget);
    const startR = startDelta.length();
    const startPolar = Math.acos(clamp(startDelta.y / Math.max(startR, 0.0001), -1, 1));
    const startAzim = Math.atan2(startDelta.x, startDelta.z);
    const endDelta = endPos.clone().sub(endTarget);
    const endR = endDelta.length();
    const endPolar = Math.acos(clamp(endDelta.y / Math.max(endR, 0.0001), -1, 1));
    const endAzim = Math.atan2(endDelta.x, endDelta.z);
    let deltaAzim = endAzim - startAzim;
    while (deltaAzim > Math.PI) deltaAzim -= Math.PI * 2;
    while (deltaAzim < -Math.PI) deltaAzim += Math.PI * 2;
    const startFov = camera.fov;
    const aspect = state.viewport.w / Math.max(1, state.viewport.h);
    const endFov = clamp(56 + Math.max(0, (1 / aspect - 1) * 12), 56, 66);
    const total = duration(1150);
    const settleMs = duration(300);
    const begin = performance.now();

    const apply = (r, polar, azim, target, fov, extraY) => {
      const sinPolar = Math.sin(polar);
      camera.position.set(
        target.x + r * sinPolar * Math.sin(azim),
        target.y + r * Math.cos(polar) + extraY,
        target.z + r * sinPolar * Math.cos(azim)
      );
      camera.fov = fov;
      camera.updateProjectionMatrix();
      camera.lookAt(target.x, target.y, target.z);
      state.camTarget = { x: target.x, y: target.y, z: target.z };
    };

    const step = (now) => {
      if (token !== state.enterToken) {
        resolve(false);
        return;
      }
      const t = Math.min(1, (now - begin) / Math.max(1, total));
      const eased = easeInOutCubic(t);
      const target = startTarget.clone().lerp(endTarget, eased);
      const r = startR + (endR - startR) * eased;
      const polar = startPolar + (endPolar - startPolar) * eased;
      const azim = startAzim + deltaAzim * eased;
      const fov = startFov + (endFov - startFov) * eased;
      apply(r, polar, azim, target, fov, 0);
      if (t < 1) {
        requestAnimationFrame(step);
        return;
      }
      const settleBegin = performance.now();
      const settle = (now2) => {
        if (token !== state.enterToken) {
          resolve(false);
          return;
        }
        const u = Math.min(1, (now2 - settleBegin) / Math.max(1, settleMs));
        const extra = 0.04 * (1 - easeOutCubic(u));
        apply(endR, endPolar, endAzim, endTarget, endFov, extra);
        if (u < 1) {
          requestAnimationFrame(settle);
        } else {
          setCameraSeat(seat);
          resolve(true);
        }
      };
      requestAnimationFrame(settle);
    };
    requestAnimationFrame(step);
  });
}

function createFiguresForSeat(seat) {
  cleanupFigures(true);
  if (!figures) return;
  const others = roles()
    .filter((role) => role.seat !== seat)
    .sort((a, b) => {
      const count = Math.max(1, roles().length);
      const da = Math.min((a.seat - seat + count) % count, (seat - a.seat + count) % count);
      const db = Math.min((b.seat - seat + count) % count, (seat - b.seat + count) % count);
      return da - db;
    });
  others.forEach((role, index) => {
    const mesh = figures.createFigure(role, {
      camera,
      paperColor: PAPER_HEX,
      seatCount: Math.max(1, roles().length),
      angle: seatAngles[role.seat]?.angle,
    });
    mesh.userData.seat = role.seat;
    figures.setFigureState(mesh, { ink: 1.0, opacity: 1.0 });
    scene.add(mesh);
    state.figureMeshes.push(mesh);
    figures.revealFigure(mesh, duration(520), duration(140) * index);
  });
}

function cleanupFigures(immediate) {
  if (!state.figureMeshes || !state.figureMeshes.length) return;
  for (const mesh of state.figureMeshes) {
    if (!mesh) continue;
    if (!immediate) {
      figures.setFigureState(mesh, { opacity: 0 });
    }
    scene.remove(mesh);
    figures.disposeFigure(mesh);
  }
  state.figureMeshes = [];
}

function fadeFiguresOut(ms) {
  if (!state.figureMeshes.length) return Promise.resolve();
  return new Promise((resolve) => {
    const begin = performance.now();
    const initial = state.figureMeshes.map((mesh) => {
      const figureState = figures.getFigureState(mesh);
      return figureState.opacity;
    });
    const step = (now) => {
      const t = Math.min(1, (now - begin) / Math.max(1, ms));
      const eased = easeOutCubic(t);
      state.figureMeshes.forEach((mesh, index) => {
        figures.setFigureState(mesh, { opacity: initial[index] * (1 - eased) });
      });
      if (t >= 1) resolve();
      else requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

function updateSpeakers(seat) {
  if (!figures) return;
  for (const mesh of state.figureMeshes) {
    if (!mesh) continue;
    const speaking = seat != null && mesh.userData.seat === seat;
    figures.setFigureState(mesh, speaking ? { ink: 1, opacity: 1 } : { ink: 0.42, opacity: 0.58 });
  }
}

function enterSeated(payload, token) {
  state.leaving = false;
  state.starting = false;
  if (dom.startBtn) {
    dom.startBtn.disabled = false;
    dom.startBtn.classList.remove('ready', 'hinted');
  }
  if (!state.figureMeshes.length) createFiguresForSeat(state.seat);
  updateSpeakers(null);
  const role = roleBySeat(state.seat);
  if (role && dom.youPlate) {
    dom.youPlate.textContent = fmt(ui().seated_as, {
      glyph: role.glyph,
      name: role.name,
    });
    dom.youPlate.style.setProperty('--plate-color', role.color);
  }
  later(() => {
    if (state.name === S.SEATED && dom.startBtn) dom.startBtn.classList.add('ready');
  }, duration(1200));
  later(() => {
    if (state.name === S.SEATED && dom.startBtn) dom.startBtn.classList.add('hinted');
  }, duration(2400));
}

async function handleStartClick() {
  if (state.name !== S.SEATED || state.starting) return;
  if (state.session && !state.session.done) {
    setState(S.PANEL);
    return;
  }
  state.starting = true;
  if (dom.startBtn) dom.startBtn.disabled = true;
  const selectedSeat = Number(document.querySelector('#seat-select')?.value);
  if (Number.isInteger(selectedSeat) && selectedSeat >= 0 && selectedSeat < roles().length) {
    updateSeatedIdentity(selectedSeat);
  }
  const selectedTopic = document.querySelector('#topic-select')?.value;
  const customTopic = document.querySelector('#custom-topic')?.value.trim() || '';
  const topic = selectedTopic && selectedTopic !== 'custom'
    ? selectedTopic
    : (topics().find((item) => item.default) || topics()[0] || {}).id || 'chair';
  const material = document.querySelector('#material-input')?.value.trim() || '';
  const mode = window.huitongMode || state.mode || 'learning';
  let response;
  try {
    response = await fetchJSON('/api/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seat: state.seat, topic, topic_text: selectedTopic === 'custom' ? customTopic : '', mode, material }),
    }, 90000);
  } catch {
    state.starting = false;
    if (dom.startBtn) dom.startBtn.disabled = false;
    showToast(ui().error_generic);
    return;
  }
  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  state.starting = false;
  if (dom.startBtn) dom.startBtn.disabled = false;
  if (response.status === 201 && data.ok) {
    resetPanel();
    state.lastSeq = 0;
    state.awaiting = false;
    state.stageId = null;
    state.session = {
      sid: data.sid,
      seat: data.seat,
      topic: data.topic,
      topicTitle: data.topic_title || '',
      mode: data.mode || mode,
      total: data.total,
      done: false,
    };
    setState(S.PANEL);
    return;
  }
  if (response.status === 429) {
    showToast(ui().session_busy, 3200);
    return;
  }
  showToast(ui().error_generic);
}

async function leaveSeat() {
  if (state.name !== S.SEATED || state.leaving) return;
  state.leaving = true;
  stopPolling();
  state.session = null;
  state.lastSeq = 0;
  await fadeFiguresOut(duration(300));
  if (state.name !== S.SEATED) return;
  setState(S.WIPE, { seal: ui().seal_leave });
}

/* ------------------------------------------------------------------ */
/* HUD                                                                 */
/* ------------------------------------------------------------------ */

function buildHud() {
  dom.hud = document.getElementById('hud');
  dom.panel = document.getElementById('panel');
  if (!dom.hud) return;
  dom.hud.innerHTML = '';

  const mark = el('div', 'gate-mark');
  const title = el('h1', 'gate-title vertical', ui().gate_title || '');
  const subtitle = el('p', 'gate-sub', ui().gate_subtitle || '');
  mark.append(title, subtitle);
  dom.gateMark = mark;

  const stageHud = el('div', 'stage-hud');
  stageHud.hidden = true;
  dom.stageHud = stageHud;

  const youPlate = el('div', 'you-plate');
  youPlate.hidden = true;
  dom.youPlate = youPlate;

  const plate = el('div', 'seat-plate vertical');
  plate.hidden = true;
  dom.seatPlate = plate;

  const leave = el('button', 'leave-btn', ui().leave || '');
  leave.type = 'button';
  leave.hidden = true;
  leave.addEventListener('click', () => {
    if (state.name === S.SEATED) leaveSeat();
  });
  dom.leaveBtn = leave;

  const start = el('button', 'start-btn');
  start.type = 'button';
  start.hidden = true;
  const dot = el('span', 'dot');
  start.append(dot, document.createTextNode(ui().start || ''));
  start.addEventListener('click', () => handleStartClick());
  dom.startBtn = start;

  const toast = el('div', 'gate-hint');
  toast.hidden = true;
  toast.style.bottom = 'clamp(180px,24vh,240px)';
  dom.toast = toast;

  const sceneHelp = el('p', 'sr-only', ui().scene_help || '');
  dom.sceneHelp = sceneHelp;

  const actions = el('div', 'hud-actions');
  actions.append(leave, start);
  dom.hudActions = actions;
  dom.hud.append(mark, stageHud, plate, youPlate, actions, toast, sceneHelp);
  buildSeatHits();
}

function buildSeatHits() {
  if (!dom.hud) return;
  if (dom.seatHits && dom.seatHits.length) return;
  dom.seatHits = [];
  for (const role of roles()) {
    const button = el('button', 'seat-hit');
    button.type = 'button';
    button.textContent = `${role.glyph || '入席'}\n${role.name || ''}`;
    button.dataset.seat = String(role.seat);
    button.setAttribute(
      'aria-label',
      fmt(ui().seat_hit, { glyph: role.glyph, name: role.name })
    );
    button.hidden = true;
    button.disabled = true;
    button.addEventListener('click', () => selectSeat(role.seat));
    dom.hud.appendChild(button);
    dom.seatHits.push(button);
  }
}

function selectSeat(seat) {
  if (state.name !== S.OVERVIEW) return;
  if (!Number.isInteger(seat) || seat < 0 || seat >= roles().length) return;
  syncSeatPicker(seat);
  setState(S.DESCEND, { seat });
}

function syncSeatPicker(seat) {
  const picker = document.querySelector('#seat-select');
  if (!picker || !Number.isInteger(seat)) return;
  const value = String(seat);
  if (picker.value !== value) picker.value = value;
}

function updateSeatedIdentity(seat) {
  if (!Number.isInteger(seat) || seat < 0 || seat >= roles().length) return;
  state.seat = seat;
  syncSeatPicker(seat);
  if (state.name !== S.SEATED) return;
  createFiguresForSeat(seat);
  setCameraSeat(seat);
  const role = roleBySeat(seat);
  if (role && dom.youPlate) {
    dom.youPlate.textContent = fmt(ui().seated_as, {
      glyph: role.glyph,
      name: role.name,
    });
    dom.youPlate.style.setProperty('--plate-color', role.color);
  }
}

function projectSeat(seat) {
  if (!camera || !state.pickTargets || !state.pickTargets[seat]) return null;
  const world = state.pickTargets[seat].getWorldPosition(new THREE.Vector3());
  world.y += 0.10;
  world.project(camera);
  if (world.z > 1) return null;
  const vw = state.viewport.w || window.innerWidth;
  const vh = state.viewport.h || window.innerHeight;
  const x = (world.x * 0.5 + 0.5) * vw;
  const y = (-world.y * 0.5 + 0.5) * vh;
  if (x < -40 || y < -40 || x > vw + 40 || y > vh + 40) return null;
  return { x, y };
}

function updateSeatHitPositions() {
  if (!dom.seatHits) return;
  const overview = state.name === S.OVERVIEW;
  for (let seat = 0; seat < dom.seatHits.length; seat += 1) {
    const button = dom.seatHits[seat];
    const point = overview ? projectSeat(seat) : null;
    if (!point) {
      button.hidden = true;
      continue;
    }
    button.hidden = false;
    button.style.left = `${point.x}px`;
    button.style.top = `${point.y}px`;
  }
}

function pickSeatAt(clientX, clientY) {
  if (!camera || !renderer || clientX < 0 || clientY < 0) return null;
  if (!seatRaycaster) seatRaycaster = new THREE.Raycaster();
  const rect = renderer.domElement.getBoundingClientRect();
  const vw = state.viewport.w || rect.width;
  if (clientX > rect.left + vw || clientY > rect.bottom) return null;
  const x = ((clientX - rect.left) / Math.max(1, vw)) * 2 - 1;
  const y = -(((clientY - rect.top) / Math.max(1, rect.height)) * 2 - 1);
  seatRaycaster.setFromCamera({ x, y }, camera);
  const hits = seatRaycaster.intersectObjects(state.pickTargets || [], false);
  if (!hits.length) return null;
  if (hits[0].distance > 30) return null;
  const seat = hits[0].object.userData.seatIndex;
  return Number.isInteger(seat) ? seat : null;
}

function updateSeatPlates() {
  if (!dom.seatPlate) return;
  if (state.name !== S.OVERVIEW) {
    dom.seatPlate.hidden = true;
    state.hovered = null;
    return;
  }
  const now = performance.now();
  if (now - lastHoverAt > 50) {
    lastHoverAt = now;
    const seat = pickSeatAt(state.pointerPx.x, state.pointerPx.y);
    if (seat !== state.hovered) {
      state.hovered = seat;
      if (seat != null) {
        const role = roleBySeat(seat);
        if (role) {
          dom.seatPlate.textContent = `${role.glyph}·${role.name}`;
          dom.seatPlate.style.setProperty('--plate-color', role.color);
        }
      }
    }
  }
  if (state.hovered == null) {
    dom.seatPlate.hidden = true;
    return;
  }
  const point = projectSeat(state.hovered);
  if (!point) {
    dom.seatPlate.hidden = true;
    return;
  }
  dom.seatPlate.hidden = false;
  const width = dom.seatPlate.offsetWidth || 70;
  const height = dom.seatPlate.offsetHeight || 84;
  const vw = state.viewport.w || window.innerWidth;
  const vh = state.viewport.h || window.innerHeight;
  let left = point.x - width / 2;
  let top = point.y - height - 10;
  left = clamp(left, 8, Math.max(8, vw - width - 8));
  top = clamp(top, 8, Math.max(8, vh - height - 8));
  dom.seatPlate.style.left = `${Math.round(left)}px`;
  dom.seatPlate.style.top = `${Math.round(top)}px`;
}

/* ------------------------------------------------------------------ */
/* 侧栏                                                                */
/* ------------------------------------------------------------------ */

function buildPanel() {
  if (!dom.panel || !state.session) return;
  const panel = dom.panel;
  panel.innerHTML = '';
  panel.hidden = false;

  const wrap = el('div', 'panel-wrap');
  const main = el('div', 'panel-main');
  const head = el('div', 'panel-head');
  const kicker = el('div', 'kicker', ui().panel_head || '');
  const topic = state.session.topicTitle ||
    (topics().find((item) => item.id === state.session.topic) || {}).title || '';
  const topicNode = el('div', 'topic', topic);
  const exit = el('button', 'panel-exit', '退出论证');
  exit.type = 'button';
  exit.addEventListener('click', () => {
    stopPolling();
    setState(S.OVERVIEW);
  });
  head.append(kicker, topicNode, exit);

  const log = el('div', 'panel-log');
  log.id = 'transcript';
  log.setAttribute('role', 'log');
  log.setAttribute('aria-live', 'polite');
  log.setAttribute('aria-relevant', 'additions');

  const foot = el('div', 'panel-foot');
  const status = el('div', 'foot-status');
  status.setAttribute('role', 'status');
  const textEntry = el('div', 'text-entry');
  const textInput = el('textarea', 'text-entry-input');
  textInput.rows = 3;
  textInput.maxLength = 4000;
  textInput.placeholder = '也可以直接输入你的观点、材料或回应……';
  textInput.setAttribute('aria-label', '直接输入回应');
  const textSubmit = el('button', 'paper-btn seal-btn', '提交文字');
  textSubmit.type = 'button';
  textSubmit.addEventListener('click', () => submitTextReply());
  textInput.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      submitTextReply();
    }
  });
  textEntry.append(textInput, textSubmit);
  textEntry.hidden = true;
  const learningHint = el('aside', 'learning-hint');
  learningHint.hidden = true;
  learningHint.setAttribute('aria-live', 'polite');
  const responseRow = el('div', 'response-row');
  responseRow.append(textEntry, learningHint);
  const actions = el('div', 'foot-actions');
  foot.append(status, responseRow, actions);

  main.append(head, log, foot);
  const rail = el('div', 'panel-rail');
  const railStage = el('div', 'rail-stage');
  const railSeal = el('img', 'seal rail-seal');
  railSeal.alt = '';
  railSeal.setAttribute('aria-hidden', 'true');
  rail.append(railStage, railSeal);
  wrap.append(main, rail);

  const newLines = el('button', 'new-lines', ui().new_lines || '');
  newLines.type = 'button';
  newLines.hidden = true;
  newLines.addEventListener('click', () => scrollLogToBottom(true));
  wrap.appendChild(newLines);

  panel.appendChild(wrap);
  dom.panelLog = log;
  dom.panelFoot = foot;
  dom.footStatus = status;
  dom.textEntry = textEntry;
  dom.textInput = textInput;
  dom.textSubmit = textSubmit;
  dom.learningHint = learningHint;
  dom.footActions = actions;
  dom.railStage = railStage;
  dom.railSeal = railSeal;
  dom.newLines = newLines;
  state.panelSessionId = state.session.sid;
  state.choiceNode = null;
  state.chipsVisible = false;

  log.addEventListener('scroll', () => {
    if (isNearLogBottom() && dom.newLines) dom.newLines.hidden = true;
  });

  const initial =
    (state.stageId && stageById(state.stageId)) || stages()[0] || null;
  if (initial) setStage(initial);

  if (state.awaiting) {
    textEntry.hidden = false;
    setFootStatus('', false, false);
  } else if (state.session.done) {
    textEntry.hidden = true;
    setFootStatus('', false, false);
  } else {
    textEntry.hidden = true;
    setFootStatus('', false, true);
  }
}

function ensurePanel() {
  if (!state.session) return;
  if (state.panelSessionId === state.session.sid && dom.panelLog) return;
  buildPanel();
}

function openPanel() {
  if (!dom.panel) return;
  dom.panel.hidden = false;
  state.panelOpen = true;
  state.panelCloseToken = (state.panelCloseToken || 0) + 1;
  const token = state.panelCloseToken;
  requestAnimationFrame(() => {
    if (state.panelOpen && token === state.panelCloseToken) {
      dom.panel.classList.add('open');
    }
  });
  scheduleLayout();
}

function closePanel() {
  if (!dom.panel) return;
  state.panelOpen = false;
  const token = (state.panelCloseToken || 0) + 1;
  state.panelCloseToken = token;
  dom.panel.classList.remove('open');
  scheduleLayout();
  window.setTimeout(() => {
    if (!state.panelOpen && token === state.panelCloseToken && dom.panel) {
      dom.panel.hidden = true;
    }
  }, 460);
}

function resetPanel() {
  if (!dom.panel) return;
  state.panelCloseToken = (state.panelCloseToken || 0) + 1;
  state.panelOpen = false;
  dom.panel.classList.remove('open');
  dom.panel.hidden = true;
  dom.panel.innerHTML = '';
  dom.panelLog = null;
  dom.footStatus = null;
  dom.footActions = null;
  dom.railStage = null;
  dom.railSeal = null;
  dom.learningHint = null;
  dom.newLines = null;
  state.panelSessionId = null;
  state.choiceNode = null;
  state.chipsVisible = false;
  state.stageId = null;
  scheduleLayout();
}

function setStage(stage) {
  if (!stage) return;
  state.stageId = stage.id;
  const order = numeral(stage.order);
  if (dom.railStage) {
    dom.railStage.textContent = fmt(ui().stage_rail, {
      order,
      name: stage.name,
    });
  }
  if (dom.railSeal) {
    dom.railSeal.src = makeSeal(stage.seal, { size: 128 });
    dom.railSeal.hidden = false;
  }
  if (dom.stageHud) {
    dom.stageHud.textContent = fmt(ui().stage_hud, {
      order,
      name: stage.name,
    });
    const visible = state.name === S.PANEL || state.name === S.CLOSING;
    dom.stageHud.hidden = !visible;
    dom.stageHud.classList.toggle('show', visible);
  }
}

function isNearLogBottom() {
  const log = dom.panelLog;
  if (!log) return true;
  return log.scrollHeight - log.scrollTop - 60 <= log.clientHeight;
}

function scrollLogToBottom(smooth) {
  const log = dom.panelLog;
  if (!log) return;
  const behavior = smooth && !reduced() ? 'smooth' : 'auto';
  log.scrollTo({ top: log.scrollHeight, behavior });
  if (dom.newLines) dom.newLines.hidden = true;
}

function appendNode(node, forceFollow = false) {
  if (!dom.panelLog) return;
  const follow = forceFollow || isNearLogBottom();
  dom.panelLog.appendChild(node);
  if (follow) scrollLogToBottom(false);
  else if (dom.newLines) dom.newLines.hidden = false;
}

function hexToRgba(hex, alpha) {
  let value = String(hex || '').replace('#', '');
  if (value.length === 3) {
    value = value
      .split('')
      .map((part) => part + part)
      .join('');
  }
  const number = Number.parseInt(value, 16);
  if (!Number.isFinite(number)) return `rgba(139,128,108,${alpha})`;
  const r = (number >> 16) & 255;
  const g = (number >> 8) & 255;
  const b = number & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

function appendEntry(entry, options = {}) {
  if (!entry || entry.seq == null) return;
  const force = Boolean(options.force);
  if (!force && entry.seq <= state.lastSeq) return;
  state.lastSeq = Math.max(state.lastSeq, entry.seq);

  if (entry.human_prompt && entry.await_user) {
    if (entry.stage) setStage(stageById(entry.stage) || stages()[0]);
    updateSpeakers(null);
    showUserPrompt(entry);
    return;
  }

  if (entry.kind === 'stage') {
    appendStageEntry(entry);
    updateSpeakers(null);
    return;
  }
  if (entry.kind === 'system') {
    appendSystemEntry(entry);
    updateSpeakers(null);
    return;
  }
  if (entry.kind === 'choice') {
    appendChoiceEntry(entry);
    return;
  }
  const isUser = entry.kind === 'user' || entry.role_name === ui().you;
  appendBubble(entry, isUser);
  if (entry.kind === 'utterance') updateSpeakers(entry.seat);
}

function appendStageEntry(entry) {
  const stage = stageById(entry.stage);
  if (stage) setStage(stage);
  const node = el('div', 'entry stage');
  const line = el('div', 'stage-line');
  const rule = el('div', 'stage-rule');
  const name = el('div', 'stage-name', entry.text || (stage && stage.name) || '');
  const seal = el('img', 'seal');
  seal.alt = '';
  seal.setAttribute('aria-hidden', 'true');
  if (stage) seal.src = makeSeal(stage.seal, { size: 128 });
  line.append(rule, name, seal);
  node.appendChild(line);
  appendNode(node);
}

function appendSystemEntry(entry) {
  const node = el('div', 'entry system');
  const text = el('div', 'entry-text', entry.text || '');
  node.appendChild(text);
  appendNode(node);
}

function appendChoiceEntry(entry) {
  const node = el('div', 'entry choice', entry.text || '');
  state.choiceNode = node;
  appendNode(node);
}

function appendBubble(entry, isUser) {
  const node = el('div', isUser ? 'entry user' : 'entry');
  const bubble = el('div', 'entry-bubble');
  const role = roleBySeat(entry.seat);
  const color = role ? role.color : INK_4;
  const name = el('div', 'entry-name', entry.role_name || '');
  const text = el('div', 'entry-text', entry.text || '');
  if (role && avatarUrl(role.seat)) {
    const avatar = el('img', 'entry-avatar');
    avatar.src = avatarUrl(role.seat);
    avatar.alt = `${role.name || role.title || '席位'}头像`;
    avatar.loading = 'lazy';
    avatar.decoding = 'async';
    bubble.classList.add('with-avatar');
    avatar.addEventListener('error', () => {
      avatar.remove();
      bubble.classList.remove('with-avatar');
    }, { once: true });
    bubble.append(avatar);
  }
  bubble.append(name, text);
  node.appendChild(bubble);
  node.style.setProperty('--name-color', color);
  node.style.setProperty('--name-bg', hexToRgba(color, 0.18));
  node.setAttribute('aria-label', `${entry.role_name || ''}：${entry.text || ''}`);
  appendNode(node);
}

function setFootStatus(text, error = false, dots = false) {
  const status = dom.footStatus;
  if (!status) return;
  status.textContent = '';
  status.classList.toggle('error', error);
  if (dots) {
    const ink = el('span', 'ink-dots');
    for (let i = 0; i < 3; i += 1) ink.appendChild(el('i'));
    status.appendChild(ink);
  }
  if (text) {
    if (dots) status.appendChild(document.createTextNode(' '));
    status.appendChild(document.createTextNode(text));
  }
}

function clearFootActions() {
  if (dom.footActions) dom.footActions.innerHTML = '';
  state.chipsVisible = false;
}

function showChips(chips, seq) {
  state.awaiting = true;
  state.polling = false;
  if (dom.textEntry) dom.textEntry.hidden = false;
  if (dom.learningHint) dom.learningHint.hidden = true;
  if (!dom.footActions) return;
  clearFootActions();
  setFootStatus('', false, false);
  const list = Array.isArray(chips) ? chips : [];
  if (!list.length) return;
  const wrapper = el('div', 'chips');
  for (const chip of list) {
    const button = el('button', 'chip', chip.text || '');
    button.type = 'button';
    button.addEventListener('click', () => replyChip(chip, seq));
    wrapper.appendChild(button);
  }
  dom.footActions.appendChild(wrapper);
  state.chipsVisible = true;
}

function showUserPrompt(entry) {
  state.awaiting = true;
  state.polling = false;
  if (dom.textEntry) dom.textEntry.hidden = false;
  if (dom.learningHint) {
    dom.learningHint.textContent = entry.hint || `请以${entry.role_title || '当前席位'}身份输入本阶段回应。`;
    dom.learningHint.hidden = false;
  }
  clearFootActions();
  setFootStatus('', false, false);
  if (dom.textInput) dom.textInput.focus();
}

async function submitTextReply() {
  if (!state.session || state.replyInFlight || !dom.textInput) return;
  const text = dom.textInput.value.trim();
  if (!text) {
    setFootStatus('请先输入本阶段的回应。', true, false);
    dom.textInput.focus();
    return;
  }
  state.replyInFlight = true;
  if (dom.textSubmit) dom.textSubmit.disabled = true;
  dom.textInput.disabled = true;
  const buttons = dom.footActions
    ? Array.from(dom.footActions.querySelectorAll('.chip'))
    : [];
  buttons.forEach((button) => { button.disabled = true; });
  let response;
  try {
    response = await fetchJSON(
      `/api/session/${state.session.sid}/reply`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      },
      12000
    );
  } catch (error) {
    state.replyInFlight = false;
    if (dom.textSubmit) dom.textSubmit.disabled = false;
    dom.textInput.disabled = false;
    buttons.forEach((button) => { button.disabled = false; });
    setFootStatus(error.message === 'reply_too_long' ? '回应不能超过 4000 字。' : ui().error_generic, true, false);
    return;
  }
  state.replyInFlight = false;
  if (dom.textSubmit) dom.textSubmit.disabled = false;
  dom.textInput.disabled = false;
  if (response.status === 200) {
    let data = {};
    try { data = await response.json(); } catch { data = {}; }
    if (state.choiceNode && state.choiceNode.parentNode) state.choiceNode.parentNode.removeChild(state.choiceNode);
    state.choiceNode = null;
    if (data.echo) appendEntry(data.echo, { force: true });
    dom.textInput.value = '';
    state.awaiting = false;
    if (dom.textEntry) dom.textEntry.hidden = true;
    if (dom.learningHint) dom.learningHint.hidden = true;
    clearFootActions();
    setFootStatus('', false, true);
    beginPolling();
    return;
  }
  buttons.forEach((button) => { button.disabled = false; });
  setFootStatus(ui().error_generic, true, false);
}

async function replyChip(chip, seq) {
  if (!state.session || state.replyInFlight) return;
  state.replyInFlight = true;
  if (dom.textEntry) dom.textEntry.hidden = true;
  const buttons = dom.footActions
    ? Array.from(dom.footActions.querySelectorAll('.chip'))
    : [];
  for (const button of buttons) button.disabled = true;
  let response;
  try {
    response = await fetchJSON(
      `/api/session/${state.session.sid}/reply`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chip_id: chip.id }),
      },
      12000
    );
  } catch {
    state.replyInFlight = false;
    if (dom.textEntry) dom.textEntry.hidden = false;
    for (const button of buttons) button.disabled = false;
    setFootStatus(ui().error_generic, true, false);
    return;
  }
  state.replyInFlight = false;
  if (response.status === 200) {
    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    if (state.choiceNode && state.choiceNode.parentNode) {
      state.choiceNode.parentNode.removeChild(state.choiceNode);
    }
    state.choiceNode = null;
    if (data.echo) appendEntry(data.echo, { force: true });
    state.awaiting = false;
    if (dom.learningHint) dom.learningHint.hidden = true;
    clearFootActions();
    setFootStatus('', false, true);
    beginPolling();
    return;
  }
  if (response.status === 409) {
    state.awaiting = false;
    if (dom.textEntry) dom.textEntry.hidden = true;
    if (dom.learningHint) dom.learningHint.hidden = true;
    if (state.choiceNode && state.choiceNode.parentNode) {
      state.choiceNode.parentNode.removeChild(state.choiceNode);
    }
    clearFootActions();
    beginPolling();
    return;
  }
  if (response.status === 404) {
    sessionLost();
    return;
  }
  for (const button of buttons) button.disabled = false;
  setFootStatus(ui().error_generic, true, false);
}

function stopPolling() {
  state.polling = false;
  state.pollEpoch = (state.pollEpoch || 0) + 1;
  if (state.pollAbort) {
    state.pollAbort.abort();
    state.pollAbort = null;
  }
}

function beginPolling() {
  if (!state.session || state.session.done) return;
  if (state.awaiting || state.polling) return;
  if (state.name !== S.PANEL) return;
  state.polling = true;
  state.pollErrors = 0;
  state.pollEpoch = (state.pollEpoch || 0) + 1;
  state.pollAbort = new AbortController();
  const token = state.pollEpoch;
  setFootStatus('', false, true);
  pollLoop(token);
}

async function pollBackoff(token) {
  if (token !== state.pollEpoch || !state.polling) return false;
  state.pollErrors = (state.pollErrors || 0) + 1;
  if (state.pollErrors > 5) {
    state.polling = false;
    setFootStatus(ui().network_break, true, false);
    if (dom.footActions) {
      dom.footActions.innerHTML = '';
      const retry = el('button', 'paper-btn', ui().retry || '');
      retry.type = 'button';
      retry.addEventListener('click', () => {
        state.pollErrors = 0;
        beginPolling();
      });
      dom.footActions.appendChild(retry);
    }
    return false;
  }
  setFootStatus(ui().network_break, false, false);
  const waits = [1000, 2000, 4000, 4000, 4000];
  await sleep(waits[Math.min(state.pollErrors - 1, waits.length - 1)]);
  return token === state.pollEpoch && state.polling;
}

async function pollLoop(token) {
  while (
    state.polling &&
    token === state.pollEpoch &&
    state.name === S.PANEL &&
    state.session
  ) {
    if (document.hidden) {
      await sleep(400);
      continue;
    }
    const sid = state.session.sid;
    const signal = state.pollAbort ? state.pollAbort.signal : undefined;
    let response;
    try {
      response = await fetchJSON(
        `/api/session/${sid}/next`,
        { cache: 'no-store', signal },
        15000
      );
    } catch {
      if (!state.polling || token !== state.pollEpoch) return;
      if (state.pollAbort && state.pollAbort.signal.aborted) return;
      const keep = await pollBackoff(token);
      if (!keep) return;
      continue;
    }
    if (!state.polling || token !== state.pollEpoch || state.name !== S.PANEL) return;
    if (response.status === 204) {
      state.pollErrors = 0;
      setFootStatus('', false, true);
      const retryAfter = Number(response.headers.get('Retry-After')) || 0;
      await sleep(retryAfter > 0 ? retryAfter * 1000 : 800);
      continue;
    }
    if (response.status === 409) {
      await sleep(400);
      continue;
    }
    if (response.status === 404) {
      sessionLost();
      return;
    }
    if (!response.ok) {
      const keep = await pollBackoff(token);
      if (!keep) return;
      continue;
    }
    let data = {};
    try {
      data = await response.json();
    } catch {
      const keep = await pollBackoff(token);
      if (!keep) return;
      continue;
    }
    state.pollErrors = 0;
    if (!data || data.ok === false) {
      const keep = await pollBackoff(token);
      if (!keep) return;
      continue;
    }
    if (data.done) {
      state.polling = false;
      if (state.session) state.session.done = true;
      setState(S.CLOSING);
      return;
    }
    appendEntry(data);
    if (data.await_user) {
      if (data.human_prompt) showUserPrompt(data);
      else showChips(data.chips, data.seq);
      return;
    }
    if (data.kind !== 'utterance') updateSpeakers(null);
    setFootStatus('', false, true);
  }
}

function sessionLost() {
  stopPolling();
  state.awaiting = false;
  state.session = null;
  setFootStatus(ui().session_lost, true, false);
  if (dom.footActions) {
    dom.footActions.innerHTML = '';
    const restart = el('button', 'paper-btn', ui().restart || '');
    restart.type = 'button';
    restart.addEventListener('click', () => {
      if (state.name === S.PANEL) setState(S.SEATED);
    });
    dom.footActions.appendChild(restart);
  }
}

async function enterPanel(payload, token) {
  if (!state.session || state.session.done) {
    setState(S.SEATED);
    return;
  }
  if (!state.figureMeshes.length) createFiguresForSeat(state.seat);
  updateSpeakers(null);
  ensurePanel();
  openPanel();
  if (state.stageId) setStage(stageById(state.stageId) || stages()[0]);
  if (state.awaiting) return;
  beginPolling();
}

/* ------------------------------------------------------------------ */
/* 散会                                                                */
/* ------------------------------------------------------------------ */

function resetRuler() {
  if (!state.rulerMesh || !state.props || !state.props[0]) return;
  const ruler = state.rulerMesh;
  if (ruler.parent !== state.props[0]) state.props[0].add(ruler);
  ruler.position.set(0, 0.02, 0);
  ruler.rotation.set(0, 0, 0.26);
}

function pulseAt(world, token) {
  if (!scene || !THREE) return Promise.resolve();
  return new Promise((resolve) => {
    const material = new THREE.MeshBasicMaterial({
      color: new THREE.Color('#A83224'),
      transparent: true,
      opacity: 0.7,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.035, 12, 10), material);
    mesh.position.copy(world);
    mesh.position.y += 0.04;
    scene.add(mesh);
    if (reduced()) {
      scene.remove(mesh);
      mesh.geometry.dispose();
      material.dispose();
      resolve();
      return;
    }
    const begin = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - begin) / 600);
      const scale = 0.6 + easeOutCubic(t) * 1.8;
      mesh.scale.setScalar(scale);
      material.opacity = 0.7 * (1 - t);
      if (t >= 1) {
        scene.remove(mesh);
        mesh.geometry.dispose();
        material.dispose();
        resolve();
      } else {
        requestAnimationFrame(step);
      }
    };
    requestAnimationFrame(step);
  });
}

async function handoverRuler(token) {
  const nextSeat = (state.chair + 1) % Math.max(1, roles().length);
  const nextRole = roleBySeat(nextSeat);
  const targetGroup = state.props && state.props[nextSeat];
  if (!targetGroup) return;
  const target = targetGroup.getWorldPosition(new THREE.Vector3());
  target.y = 0.22;
  const ruler = state.rulerMesh;
  if (!ruler) return;
  if (reduced()) {
    scene.attach(ruler);
    ruler.position.copy(target);
    ruler.rotation.x += Math.PI * 2;
    await pulseAt(target, token);
  } else {
    const start = ruler.getWorldPosition(new THREE.Vector3());
    const startRotation = ruler.rotation.x;
    scene.attach(ruler);
    const control = start.clone().add(target).multiplyScalar(0.5);
    control.y += 0.55;
    const begin = performance.now();
    await new Promise((resolve) => {
      const step = (now) => {
        if (token !== state.enterToken) {
          resolve();
          return;
        }
        const t = Math.min(1, (now - begin) / 900);
        const eased = easeInOutCubic(t);
        const inv = 1 - eased;
        ruler.position.set(
          inv * inv * start.x + 2 * inv * eased * control.x + eased * eased * target.x,
          inv * inv * start.y + 2 * inv * eased * control.y + eased * eased * target.y,
          inv * inv * start.z + 2 * inv * eased * control.z + eased * eased * target.z
        );
        ruler.rotation.x = startRotation + Math.PI * 2 * eased;
        if (t >= 1) resolve();
        else requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
    if (token !== state.enterToken) return;
    await pulseAt(target, token);
  }
  if (token !== state.enterToken) return;
  if (nextRole) {
    appendSystemEntry({
      text: fmt(ui().ruler_handover, { name: nextRole.name }),
    });
  }
  scrollLogToBottom(false);
}

function showClosingSeal() {
  if (!dom.panelFoot || !dom.footActions) return;
  if (dom.footStatus) dom.footStatus.hidden = true;
  const existing = dom.panelFoot.querySelector('.closing-seal');
  if (existing) existing.remove();
  const block = el('div', 'closing-seal');
  const seal = el('img', 'seal');
  seal.src = makeSeal(ui().seal_saved, { size: 160 });
  seal.alt = '';
  seal.setAttribute('aria-hidden', 'true');
  const label = el('span', 'sr-only', ui().seal_saved || '');
  block.append(seal, label);
  dom.panelFoot.insertBefore(block, dom.footActions);
  dom.footActions.innerHTML = '';
  const again = el('button', 'paper-btn', ui().again || '');
  again.type = 'button';
  again.addEventListener('click', () => {
    if (state.name !== S.CLOSING) return;
    state.session = null;
    state.lastSeq = 0;
    setState(S.WIPE, { seal: ui().seal_again });
  });
  const leave = el('button', 'paper-btn', ui().leave || '');
  leave.type = 'button';
  leave.addEventListener('click', () => {
    if (state.name !== S.CLOSING) return;
    state.session = null;
    state.lastSeq = 0;
    setState(S.WIPE, { seal: ui().seal_leave });
  });
  dom.footActions.append(again, leave);
}

async function enterClosing(payload, token) {
  state.polling = false;
  state.awaiting = false;
  if (state.session) state.session.done = true;
  if (state.stageId) setStage(stageById(state.stageId) || stages()[0]);
  setFootStatus('', false, true);
  await handoverRuler(token);
  if (token !== state.enterToken) return;
  if (dom.stageHud) {
    dom.stageHud.hidden = false;
    dom.stageHud.classList.add('show');
  }
  showClosingSeal();
}

/* ------------------------------------------------------------------ */
/* 降级                                                                */
/* ------------------------------------------------------------------ */

function enterFallback(payload, token) {
  hideBootNote();
  if (dom.hud) dom.hud.hidden = true;
  if (dom.panel) dom.panel.hidden = true;
  const previous = document.querySelector('.fallback');
  if (previous) previous.remove();
  const root = el('div', 'fallback');
  const inner = el('div', 'fallback-inner');
  const title = el('h1', null, ui().fallback_title || ui().gate_title || document.title);
  const lead = el('p', 'lead', ui().fallback_text || '');
  const warn = el('p', 'warn');
  const feedback = el('p', 'warn');
  feedback.hidden = true;
  if (payload.reason === 'three') warn.textContent = ui().fallback_three || '';
  else warn.textContent = '';

  const form = el('div', 'fallback-foot');
  const codeInput = el('input');
  codeInput.type = 'text';
  codeInput.inputMode = 'numeric';
  codeInput.autocomplete = 'off';
  codeInput.maxLength = 8;
  codeInput.setAttribute('aria-label', ui().code_label || '');
  codeInput.placeholder = ui().code_label || '';
  let repeatInput = null;
  let hintInput = null;
  if (!state.config || !state.config.setup_done) {
    repeatInput = el('input');
    repeatInput.type = 'text';
    repeatInput.inputMode = 'numeric';
    repeatInput.autocomplete = 'off';
    repeatInput.maxLength = 8;
    repeatInput.setAttribute('aria-label', ui().repeat_label || '');
    repeatInput.placeholder = ui().repeat_label || '';
    hintInput = el('input');
    hintInput.type = 'text';
    hintInput.autocomplete = 'off';
    hintInput.maxLength = 20;
    hintInput.setAttribute('aria-label', ui().hint_label || '');
    hintInput.placeholder = ui().hint_placeholder || '';
  }
  const submit = el(
    'button',
    'paper-btn',
    state.config && state.config.setup_done ? ui().unlock_submit || '' : ui().setup_submit || ''
  );
  submit.type = 'button';
  form.append(codeInput);
  if (repeatInput) form.appendChild(repeatInput);
  if (hintInput) form.appendChild(hintInput);
  form.appendChild(submit);

  const seatsTitle = el('p', 'lead', ui().fallback_seats || '');
  const seatGrid = el('div', 'fallback-seats');
  let unlocked = false;
  const seatButtons = [];
  for (const role of roles()) {
    const button = el('button');
    button.type = 'button';
    button.disabled = true;
    button.style.setProperty('--seat-color', role.color);
    button.appendChild(document.createTextNode(`${role.glyph}·${role.name}`));
    const small = el('small', null, role.title);
    button.appendChild(small);
    button.addEventListener('click', () => startFallbackSession(role.seat));
    seatGrid.appendChild(button);
    seatButtons.push(button);
  }
  const log = el('div', 'fallback-log');
  log.hidden = true;
  const sessionFoot = el('div', 'fallback-foot');
  sessionFoot.hidden = true;
  sessionFoot.id = 'fallback-session-foot';

  inner.append(title, lead, warn, feedback, form, seatsTitle, seatGrid, log, sessionFoot);
  root.appendChild(inner);
  document.body.appendChild(root);

  const unlockSeats = () => {
    unlocked = true;
    form.hidden = true;
    for (const button of seatButtons) button.disabled = false;
    feedback.hidden = true;
  };

  const showFeedback = (message) => {
    feedback.textContent = message || '';
    feedback.hidden = !message;
  };

  const tryUnlock = async (code) => {
    let response;
    try {
      response = await fetchJSON('/api/unlock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
    } catch {
      showFeedback(ui().error_generic);
      return;
    }
    if (response.status === 200) {
      unlockSeats();
      return;
    }
    if (response.status === 401) {
      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }
      const message = fmt(ui().unlock_error, { n: Number(data.attempts) || 1 });
      showFeedback(data.hint ? `${message}　${fmt(ui().hint_prefix, { hint: data.hint })}` : message);
      return;
    }
    if (response.status === 429) {
      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }
      showFeedback(fmt(ui().wait_seconds, { n: Number(data.retry_after) || 8 }));
      return;
    }
    if (response.status === 409) {
      if (state.config) state.config.setup_done = false;
      showFeedback(ui().error_generic);
      return;
    }
    showFeedback(ui().error_generic);
  };

  submit.addEventListener('click', async () => {
    const code = codeInput.value.trim();
    if (!/^[0-9]{4,8}$/.test(code)) {
      showFeedback(ui().code_invalid);
      return;
    }
    if (state.config && !state.config.setup_done) {
      if (!repeatInput || repeatInput.value.trim() !== code) {
        showFeedback(ui().mismatch);
        return;
      }
      let response;
      try {
        response = await fetchJSON('/api/setup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, hint: hintInput ? hintInput.value.trim() : '' }),
        });
      } catch {
        showFeedback(ui().error_generic);
        return;
      }
      if (response.status === 201 || response.status === 409) {
        state.config.setup_done = true;
        state.config.attempts = 0;
        unlockSeats();
        return;
      }
      showFeedback(ui().error_generic);
      return;
    }
    await tryUnlock(code);
  });

  const startFallbackSession = async (seat) => {
    if (!unlocked) return;
    for (const button of seatButtons) button.disabled = true;
    const topic =
      (topics().find((item) => item.default) || topics()[0] || {}).id || 'chair';
    let response;
    try {
      response = await fetchJSON('/api/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          seat,
          topic,
          mode: window.huitongMode || state.mode || 'learning',
          material: document.querySelector('#material-input')?.value.trim() || '',
        }),
      });
    } catch {
      showFeedback(ui().error_generic);
      for (const button of seatButtons) button.disabled = false;
      return;
    }
    if (response.status !== 201) {
      showFeedback(response.status === 429 ? ui().session_busy : ui().error_generic);
      for (const button of seatButtons) button.disabled = false;
      return;
    }
    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    if (!data.ok) {
      showFeedback(ui().error_generic);
      for (const button of seatButtons) button.disabled = false;
      return;
    }
    log.hidden = false;
    log.innerHTML = '';
    sessionFoot.hidden = false;
    sessionFoot.innerHTML = '';
    state.fallbackSession = {
      sid: data.sid,
      seat: data.seat,
      topic: data.topic,
      total: data.total,
      done: false,
    };
    fallbackPoll(state.fallbackSession);
  };

  const fallbackPoll = async (session) => {
    while (state.name === S.FALLBACK && state.fallbackSession === session) {
      let response;
      try {
        response = await fetchJSON(
          `/api/session/${session.sid}/next`,
          { cache: 'no-store' },
          15000
        );
      } catch {
        if (state.fallbackSession === session) {
          showFeedback(ui().network_break);
        }
        return;
      }
      if (state.name !== S.FALLBACK || state.fallbackSession !== session) return;
      if (response.status === 204) {
        const retryAfter = Number(response.headers.get('Retry-After')) || 0;
        await sleep(retryAfter > 0 ? retryAfter * 1000 : 800);
        continue;
      }
      if (response.status === 409) {
        await sleep(400);
        continue;
      }
      if (response.status === 404) {
        showFeedback(ui().session_lost);
        return;
      }
      if (!response.ok) {
        showFeedback(ui().network_break);
        return;
      }
      let data = {};
      try {
        data = await response.json();
      } catch {
        showFeedback(ui().network_break);
        return;
      }
      if (data.done) {
        session.done = true;
        const done = el('p', 'lead', ui().seal_saved || '');
        log.appendChild(done);
        sessionFoot.innerHTML = '';
        const again = el('button', 'paper-btn', ui().again || '');
        again.type = 'button';
        again.addEventListener('click', () => {
          state.fallbackSession = null;
          log.hidden = true;
          sessionFoot.hidden = true;
          log.innerHTML = '';
          sessionFoot.innerHTML = '';
          for (const button of seatButtons) button.disabled = false;
        });
        sessionFoot.appendChild(again);
        return;
      }
      if (!data.human_prompt) {
        const line = el('p', data.kind === 'system' ? 'lead' : null);
        if (data.role_name && Number.isInteger(data.seat)) {
          const role = roleBySeat(data.seat);
          const avatar = el('img', 'fallback-avatar');
          avatar.src = avatarUrl(data.seat);
          avatar.alt = `${role?.name || data.role_name}头像`;
          avatar.loading = 'lazy';
          avatar.decoding = 'async';
          avatar.addEventListener('error', () => avatar.remove(), { once: true });
          line.appendChild(avatar);
        }
        line.appendChild(document.createTextNode(data.text || ''));
        if (data.role_name) line.setAttribute('aria-label', `${data.role_name}：${data.text || ''}`);
        log.appendChild(line);
        log.scrollTop = log.scrollHeight;
      }
      if (data.await_user) {
        sessionFoot.innerHTML = '';
        if (data.human_prompt) {
          const hint = el('p', 'learning-hint', data.hint || '请以当前席位身份输入本阶段回应。');
          const input = el('textarea', 'text-entry-input');
          input.rows = 3;
          input.maxLength = 4000;
          input.placeholder = '输入你的观点、材料或回应……';
          const submit = el('button', 'paper-btn seal-btn', '提交文字');
          submit.type = 'button';
          submit.addEventListener('click', async () => {
            const text = input.value.trim();
            if (!text) return;
            input.disabled = true;
            submit.disabled = true;
            const reply = await fetchJSON(`/api/session/${session.sid}/reply`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ text }),
            }).catch(() => null);
            if (reply?.status === 200) {
              let echo = {};
              try { echo = await reply.json(); } catch { echo = {}; }
              if (echo.echo) {
                const mine = el('p', null, echo.echo.text || '');
                log.appendChild(mine);
                log.scrollTop = log.scrollHeight;
              }
              sessionFoot.innerHTML = '';
              fallbackPoll(session);
              return;
            }
            input.disabled = false;
            submit.disabled = false;
          });
          sessionFoot.append(hint, input, submit);
          return;
        }
        const chips = el('div', 'chips');
        for (const chip of data.chips || []) {
          const button = el('button', 'chip', chip.text || '');
          button.type = 'button';
          button.addEventListener('click', async () => {
            for (const item of chips.querySelectorAll('.chip')) item.disabled = true;
            let reply;
            try {
              reply = await fetchJSON(
                `/api/session/${session.sid}/reply`,
                {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ chip_id: chip.id }),
                },
                12000
              );
            } catch {
              showFeedback(ui().error_generic);
              for (const item of chips.querySelectorAll('.chip')) item.disabled = false;
              return;
            }
            if (reply.status === 200) {
              let echo = {};
              try {
                echo = await reply.json();
              } catch {
                echo = {};
              }
              if (echo.echo) {
                const mine = el('p', null, echo.echo.text || '');
                log.appendChild(mine);
                log.scrollTop = log.scrollHeight;
              }
              sessionFoot.innerHTML = '';
              fallbackPoll(session);
            } else {
              showFeedback(ui().error_generic);
              for (const item of chips.querySelectorAll('.chip')) item.disabled = false;
            }
          });
          chips.appendChild(button);
        }
        sessionFoot.appendChild(chips);
        return;
      }
      await sleep(120);
    }
  };
}

/* ------------------------------------------------------------------ */
/* 布局、字体与事件                                                     */
/* ------------------------------------------------------------------ */

let layoutTimer = 0;
let dprQuery = null;

function scheduleLayout() {
  window.clearTimeout(layoutTimer);
  layoutTimer = window.setTimeout(() => {
    applyLayout();
    positionStageHud();
  }, 120);
}

function positionStageHud() {
  if (!dom.stageHud) return;
  if (state.panelOpen) {
    const vw = state.viewport.w || window.innerWidth;
    dom.stageHud.style.left = `${Math.round(vw / 2)}px`;
  } else {
    dom.stageHud.style.left = '50%';
  }
}

function onResize() {
  scheduleLayout();
}

function onVisibility() {
  if (state.visibilityBound) return;
  state.visibilityBound = true;
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      state.lastT = performance.now();
    }
  });
}

function watchDpr() {
  if (dprQuery && dprHandler) {
    if (dprQuery.removeEventListener) dprQuery.removeEventListener('change', dprHandler);
    else if (dprQuery.removeListener) dprQuery.removeListener(dprHandler);
  }
  const dpr = window.devicePixelRatio || 1;
  dprQuery = window.matchMedia(`(resolution: ${dpr}dppx)`);
  dprHandler = () => {
    applyLayout();
    watchDpr();
  };
  if (dprQuery.addEventListener) dprQuery.addEventListener('change', dprHandler, { once: true });
  else if (dprQuery.addListener) dprQuery.addListener(dprHandler);
}

function replaceTexture(material, texture) {
  if (!material) return;
  const old = material.map;
  material.map = texture;
  material.needsUpdate = true;
  if (old && old !== texture) old.dispose();
}

function rebakeTexts() {
  if (!scene || !THREE) return;
  if (state.plaque && state.plaque.material) {
    const texture = new THREE.CanvasTexture(
      makeScrollTexture(ui().gate_title || '', {
        w: 1024,
        h: 288,
        fontSize: 176,
        vertical: false,
        rods: false,
        bg: '#F7EFDC',
      })
    );
    texture.colorSpace = THREE.SRGBColorSpace;
    replaceTexture(state.plaque.material, texture);
  }
  if (state.scrollMaterials) {
    for (const stage of stages()) {
      const material = state.scrollMaterials[stage.id];
      if (!material) continue;
      const texture = new THREE.CanvasTexture(
        makeScrollTexture(stage.name, {
          w: 256,
          h: 1024,
          fontSize: 96,
          vertical: true,
          rods: true,
        })
      );
      texture.colorSpace = THREE.SRGBColorSpace;
      replaceTexture(material, texture);
    }
  }
  if (state.coupletTextures) {
    const family = "'Zhi Mang Xing','Kaiti SC','STKaiti',serif";
    const texts = [ui().couplet_right || '', ui().couplet_left || ''];
    state.coupletTextures.forEach((oldTexture, index) => {
      const texture = new THREE.CanvasTexture(
        makeScrollTexture(texts[index], {
          w: 256,
          h: 1024,
          fontSize: 70,
          vertical: true,
          rods: false,
          bg: false,
          color: '#3A342C',
          font: family,
        })
      );
      texture.colorSpace = THREE.SRGBColorSpace;
      scene.traverse((object) => {
        if (!object.isMesh || !object.material || object.material.map !== oldTexture) return;
        object.material.map = texture;
        object.material.needsUpdate = true;
        oldTexture.dispose();
      });
      state.coupletTextures[index] = texture;
    });
  }
}

function bindGlobalEvents() {
  const canvas = renderer ? renderer.domElement : null;
  state.pointerPx = { x: -1, y: -1 };
  const seatPicker = document.querySelector('#seat-select');
  if (seatPicker) {
    seatPicker.addEventListener('change', () => {
      const selectedSeat = Number(seatPicker.value);
      if (!Number.isInteger(selectedSeat) || selectedSeat < 0 || selectedSeat >= roles().length) return;
      if (state.name === S.PANEL) {
        syncSeatPicker(state.seat);
        return;
      }
      updateSeatedIdentity(selectedSeat);
    });
  }
  if (canvas) {
    canvas.addEventListener('pointerdown', (event) => {
      if (event.button != null && event.button !== 0) return;
      state.pointerPx = { x: event.clientX, y: event.clientY };
      updatePointer(event.clientX, event.clientY);
      if (state.name === S.OVERVIEW) {
        state.clickStart = { x: event.clientX, y: event.clientY, moved: 0 };
      }
    });

    canvas.addEventListener('pointerleave', () => {
      state.pointer = { x: 0, y: 0 };
      state.pointerPx = { x: -1, y: -1 };
    });
  }

  window.addEventListener('pointermove', (event) => {
    updatePointer(event.clientX, event.clientY);
    state.pointerPx = { x: event.clientX, y: event.clientY };
    if (state.clickStart) {
      const dx = event.clientX - state.clickStart.x;
      const dy = event.clientY - state.clickStart.y;
      state.clickStart.moved = Math.max(state.clickStart.moved, Math.hypot(dx, dy));
    }
  });

  window.addEventListener('pointerup', (event) => {
    if (state.clickStart && state.name === S.OVERVIEW) {
      const moved = Math.max(
        state.clickStart.moved,
        Math.hypot(event.clientX - state.clickStart.x, event.clientY - state.clickStart.y)
      );
      state.clickStart = null;
      if (moved >= 8) return;
      const seat = pickSeatAt(event.clientX, event.clientY);
      if (seat != null) {
        selectSeat(seat);
      }
      return;
    }
    state.clickStart = null;
  });

  window.addEventListener('pointercancel', () => {
    state.clickStart = null;
  });

  window.addEventListener('keydown', (event) => {
    if (event.isComposing) return;
    if (event.key === 'Escape') {
      if (state.name === S.SEATED) {
        event.preventDefault();
        leaveSeat();
      } else if (state.name === S.PANEL) {
        event.preventDefault();
        setState(S.SEATED);
      }
    }
  });

  if (window.matchMedia) {
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotion = () => {
      state.reducedMotion = motion.matches;
    };
    if (motion.addEventListener) motion.addEventListener('change', updateMotion);
    else if (motion.addListener) motion.addListener(updateMotion);
  }

  window.addEventListener('pagehide', () => stopPolling());
  positionStageHud();
}

function updatePointer(clientX, clientY) {
  const width = Math.max(1, window.innerWidth);
  const height = Math.max(1, window.innerHeight);
  state.pointer = {
    x: (clientX / width) * 2 - 1,
    y: (0.5 - clientY / height) * 2,
  };
}

/* 启动 */
window.addEventListener('huitong:enter', () => { handleWorkspaceEnter(); });
boot();
