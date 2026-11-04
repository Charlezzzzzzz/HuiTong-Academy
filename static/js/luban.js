/* 会通书院 · 鲁班锁
 * 六杆门锁、拖拽回中、开锁时间轴，以及拨码 / 立口令面板。
 */

import * as THREE from 'three';
import { makeSplatTexture } from './ink.js';

const INK_COLOR = '#26231F';
const GOLD = '#FFF2CC';
const LOCK_TILT = -0.06;

// 六片径向锁簧：从正面看是一个有秩序的“墨花”，避免旧版六根方棍叠成粗重十字。
const BAR_SPECS = Array.from({ length: 6 }, (_, index) => {
  const angle = (index * Math.PI) / 3;
  return {
    id: `R${index + 1}`,
    axis: 'x',
    angle,
    offset: [0, 0, 0],
    dir: [Math.cos(angle), Math.sin(angle), 0],
    spinAxis: 'z',
    key: index === 0,
  };
});

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function easeInOutQuad(t) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function easeOutQuint(t) {
  return 1 - Math.pow(1 - t, 5);
}

function makeTickTexture(index, vertical) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, 256, 64);
  ctx.strokeStyle = 'rgba(201,180,140,0.64)';
  ctx.fillStyle = index % 2 ? 'rgba(168,50,36,0.72)' : 'rgba(201,180,140,0.72)';
  ctx.lineWidth = 2;
  for (let i = 0; i < 7; i += 1) {
    const x = 24 + i * 34;
    ctx.beginPath();
    ctx.moveTo(x, 16);
    ctx.lineTo(x + (i % 2 ? 4 : -4), 48);
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.arc(128 + (index % 3 - 1) * 22, 32, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = 'rgba(239,227,200,0.30)';
  ctx.beginPath();
  ctx.moveTo(4, 8.5);
  ctx.lineTo(252, 8.5);
  ctx.moveTo(4, 55.5);
  ctx.lineTo(252, 55.5);
  ctx.stroke();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  if (vertical) {
    texture.center.set(0.5, 0.5);
    texture.rotation = Math.PI / 2;
  }
  texture.needsUpdate = true;
  return texture;
}

function barPickSize(axis) {
  if (axis === 'x') return [0.62, 0.062, 0.062];
  if (axis === 'y') return [0.062, 0.62, 0.062];
  return [0.062, 0.062, 0.62];
}

function axisSpin(axis) {
  if (axis === 'x') return 'x';
  if (axis === 'y') return 'y';
  return 'z';
}

export function createBurr(options = {}) {
  const size = options.size || 0.62;
  const inkColor = options.inkColor || INK_COLOR;
  const group = new THREE.Group();
  group.name = 'burr';
  group.userData.isBurr = true;

  const body = new THREE.Group();
  body.rotation.x = LOCK_TILT;
  group.add(body);

  const barMaterial = new THREE.MeshStandardMaterial({
    color: new THREE.Color(inkColor),
    roughness: 0.68,
    metalness: 0.12,
    transparent: false,
  });
  const barMaterials = [barMaterial];
  const bars = [];
  const tickMaterials = [];

  const scale = size / 0.62;
  for (let index = 0; index < BAR_SPECS.length; index += 1) {
    const spec = BAR_SPECS[index];
    const dims = barPickSize(spec.axis);
    const length = Math.max(dims[0], dims[1], dims[2]) * scale;
    const radius = 0.052 * scale;
    const geometry = new THREE.CylinderGeometry(radius * 0.86, radius, length, 8, 1, false);
    const mesh = new THREE.Mesh(geometry, barMaterial);
    if (spec.axis === 'x') mesh.rotation.z = spec.angle || 0;
    if (spec.axis === 'z') mesh.rotation.x = Math.PI / 2;
    mesh.position.set(
      spec.offset[0] * scale,
      spec.offset[1] * scale,
      spec.offset[2] * scale
    );
    mesh.userData.axis = spec.axis;
    mesh.userData.base = mesh.position.clone();
    mesh.userData.dir = new THREE.Vector3(...spec.dir);
    mesh.userData.isKey = Boolean(spec.key);
    mesh.userData.barId = spec.id;
    mesh.userData.spinAxis = spec.spinAxis || axisSpin(spec.axis);
    body.add(mesh);
    bars.push(mesh);

    const vertical = spec.axis !== 'x';
    const tickTexture = makeTickTexture(index, vertical);
    const tickMaterial = new THREE.MeshBasicMaterial({
      map: tickTexture,
      transparent: true,
      depthWrite: false,
      depthTest: true,
      side: THREE.DoubleSide,
      opacity: 1,
    });
    tickMaterials.push(tickMaterial);
    const planeWidth = spec.axis === 'x' ? size : 0.062 * scale;
    const planeHeight = spec.axis === 'x' ? 0.062 * scale : size;
    const tick = new THREE.Mesh(new THREE.PlaneGeometry(planeWidth, planeHeight), tickMaterial);
    const normal = new THREE.Vector3(0, 0, 1);
    if (spec.axis === 'x') {
      tick.position.set(0, 0, 0.032 * scale);
    } else if (spec.axis === 'y') {
      normal.set(1, 0, 0);
      tick.position.set(0.032 * scale, 0, 0);
    } else {
      normal.set(0, 1, 0);
      tick.position.set(0, 0.032 * scale, 0);
    }
    tick.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
    tick.renderOrder = 3;
    mesh.add(tick);
  }

  const coreMaterial = new THREE.MeshStandardMaterial({
    color: new THREE.Color('#8B6C45'),
    roughness: 0.46,
    metalness: 0.58,
  });
  const core = new THREE.Mesh(new THREE.DodecahedronGeometry(0.13 * scale, 0), coreMaterial);
  core.name = 'lock-core';
  body.add(core);
  const collar = new THREE.Mesh(
    new THREE.TorusGeometry(0.19 * scale, 0.012 * scale, 8, 28),
    new THREE.MeshStandardMaterial({ color: new THREE.Color('#A83224'), roughness: 0.6, metalness: 0.18 })
  );
  collar.rotation.x = Math.PI / 2;
  collar.position.z = 0.012 * scale;
  body.add(collar);

  const lineMaterial = new THREE.MeshBasicMaterial({
    color: new THREE.Color(inkColor),
    transparent: true,
    opacity: 1,
  });
  const lineHeight = 2.05;
  const lineGeometry = new THREE.CylinderGeometry(0.006, 0.006, lineHeight, 6);
  const line = new THREE.Mesh(lineGeometry, lineMaterial);
  line.position.y = lineHeight / 2;
  line.name = 'burr-line';
  group.add(line);

  const splatMaterial = new THREE.MeshBasicMaterial({
    map: new THREE.CanvasTexture(makeSplatTexture()),
    transparent: true,
    depthWrite: false,
    depthTest: true,
    opacity: 0,
    side: THREE.DoubleSide,
  });
  splatMaterial.map.colorSpace = THREE.SRGBColorSpace;
  const splat = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 1.6), splatMaterial);
  splat.position.set(0, 0, 0.17);
  splat.scale.setScalar(0.3);
  splat.visible = false;
  splat.renderOrder = 4;
  group.add(splat);

  const goldMaterial = new THREE.MeshBasicMaterial({
    color: new THREE.Color(GOLD),
    transparent: true,
    opacity: 0,
    depthWrite: false,
    depthTest: true,
    side: THREE.DoubleSide,
  });
  const gold = new THREE.Mesh(new THREE.PlaneGeometry(0.022, 3.4), goldMaterial);
  gold.position.set(0, 0.15, 0.17);
  gold.renderOrder = 5;
  group.add(gold);

  group.userData.body = body;
  group.userData.bars = bars;
  group.userData.line = line;
  group.userData.splat = splat;
  group.userData.goldLine = gold;
  group.userData.barMaterials = barMaterials;
  group.userData.tickMaterials = tickMaterials;
  group.userData.lineMaterial = lineMaterial;
  group.userData.openState = { done: false, animating: false };

  return group;
}

export function updateBurr(group, dt, interaction = {}) {
  if (!group || !group.userData.body) return;
  const body = group.userData.body;
  const dragging = Boolean(interaction.dragging);
  const pointer = interaction.pointer || { x: 0, y: 0 };
  const targetY = dragging ? clamp(pointer.x, -1, 1) * 0.436 : 0;
  const targetX = LOCK_TILT + (dragging ? clamp(pointer.y, -1, 1) * 0.262 : 0);
  const k = 1 - Math.exp(-Math.max(0, dt) * 7.2);
  body.rotation.y += (targetY - body.rotation.y) * k;
  body.rotation.x += (targetX - body.rotation.x) * k;
}

function setBurrOpacity(group, opacity) {
  for (const material of group.userData.barMaterials) {
    material.transparent = true;
    material.opacity = opacity;
    material.needsUpdate = true;
  }
  for (const material of group.userData.tickMaterials) {
    material.opacity = opacity;
  }
}

export function playOpen(group, options = {}) {
  if (!group || !group.userData.isBurr) return Promise.resolve();
  if (group.userData.openState.animating) return Promise.resolve();
  if (group.userData.openState.done) return Promise.resolve();
  group.userData.openState.animating = true;

  const bars = group.userData.bars;
  const keyBar = bars.find((bar) => bar.userData.isKey);
  const others = bars.filter((bar) => !bar.userData.isKey);
  const line = group.userData.line;
  const splat = group.userData.splat;
  const gold = group.userData.goldLine;
  const barMaterial = group.userData.barMaterials[0];
  const lineMaterial = group.userData.lineMaterial;
  const reducedMotion = Boolean(options.reducedMotion);
  const onSplat = options.onSplat;

  const startPositions = new Map();
  for (const bar of bars) {
    startPositions.set(bar, bar.position.clone());
    bar.userData.baseRotation = { x: bar.rotation.x, y: bar.rotation.y, z: bar.rotation.z };
  }

  if (reducedMotion) {
    return new Promise((resolve) => {
      setBurrOpacity(group, 1);
      barMaterial.transparent = true;
      lineMaterial.transparent = true;
      splat.visible = true;
      if (onSplat) onSplat();
      const begin = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - begin) / 400);
        const fade = 1 - easeOutCubic(t);
        setBurrOpacity(group, fade);
        lineMaterial.opacity = fade;
        gold.material.opacity = 0.6 * easeOutCubic(t);
        splat.material.opacity = 0.9 * (1 - t);
        splat.scale.setScalar(0.3 + 1.3 * easeOutQuint(t));
        for (const bar of others) {
          bar.position.copy(startPositions.get(bar));
        }
        if (t >= 1) {
          group.userData.body.visible = false;
          line.visible = false;
          splat.visible = false;
          group.userData.openState.animating = false;
          group.userData.openState.done = true;
          resolve(true);
        } else {
          requestAnimationFrame(step);
        }
      };
      requestAnimationFrame(step);
    });
  }

  return new Promise((resolve) => {
    const begin = performance.now();
    let splatFired = false;
    const step = (now) => {
      const t = now - begin;

      // 0–240：键绕自身 Z 轴转 90°
      const spinT = clamp(t / 240, 0, 1);
      if (keyBar) {
        keyBar.rotation.z = keyBar.userData.baseRotation.z + (Math.PI / 2) * easeInOutQuad(spinT);
      }

      // 240–520：键沿 +Z 移出 0.18m
      const pullT = clamp((t - 240) / 280, 0, 1);
      if (keyBar) {
        keyBar.position.z = keyBar.userData.base.z + 0.18 * easeOutCubic(pullT);
      }

      // 520–1600：其余五杆依次沿各自轴向移出 0.34m，并绕长轴转 12°
      for (let i = 0; i < others.length; i += 1) {
        const bar = others[i];
        const local = clamp((t - 520 - i * 70) / 1100, 0, 1);
        const eased = easeInOutCubic(local);
        const base = startPositions.get(bar);
        bar.position.copy(base).addScaledVector(bar.userData.dir, 0.34 * eased);
        const axis = bar.userData.spinAxis || axisSpin(bar.userData.axis);
        bar.rotation[axis] = bar.userData.baseRotation[axis] + (Math.PI / 15) * eased;
      }

      // 760–1200：整体淡出，墨溅展开
      const fadeT = clamp((t - 760) / 440, 0, 1);
      if (t >= 760) {
        if (!splatFired) {
          splatFired = true;
          splat.visible = true;
          if (onSplat) onSplat();
        }
        setBurrOpacity(group, 1 - fadeT);
        lineMaterial.opacity = 1;
        splat.material.opacity = 0.9 * (1 - fadeT);
        splat.scale.setScalar(0.3 + 1.3 * easeOutQuint(fadeT));
      }

      // 1500–2100：悬线淡出，门缝金光浮出
      const goldT = clamp((t - 1500) / 600, 0, 1);
      if (t >= 1500) {
        lineMaterial.opacity = 1 - easeInOutCubic(goldT);
        gold.material.opacity = 0.6 * goldT;
      }

      if (t >= 2100) {
        setBurrOpacity(group, 0);
        lineMaterial.opacity = 0;
        splat.visible = false;
        group.userData.body.visible = false;
        line.visible = false;
        group.userData.openState.animating = false;
        group.userData.openState.done = true;
        resolve(true);
      } else {
        requestAnimationFrame(step);
      }
    };
    requestAnimationFrame(step);
  });
}

/* ------------------------------------------------------------------ */
/* 拨码面板                                                            */
/* ------------------------------------------------------------------ */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function makeWheel(index, value, onInput) {
  const wheel = el('button', 'wheel');
  wheel.type = 'button';
  wheel.setAttribute('role', 'spinbutton');
  wheel.setAttribute('aria-valuemin', '0');
  wheel.setAttribute('aria-valuemax', '9');
  wheel.setAttribute('aria-valuenow', String(value));
  wheel.dataset.index = String(index);
  const digit = el('span', 'digit', String(value));
  wheel.appendChild(digit);
  wheel.addEventListener('click', (event) => {
    if (wheel.classList.contains('frozen')) return;
    const rect = wheel.getBoundingClientRect();
    const upper = event.clientY < rect.top + rect.height / 2;
    onInput(upper ? 1 : -1, index);
  });
  return wheel;
}

function setWheelValue(wheel, value) {
  wheel.dataset.value = String(value);
  wheel.setAttribute('aria-valuenow', String(value));
  const digit = wheel.querySelector('.digit');
  if (digit) digit.textContent = String(value);
}

function wheelValue(wheel) {
  return Number(wheel.dataset.value || 0);
}

export function createDial(options = {}) {
  const mode = options.mode === 'setup' ? 'setup' : 'unlock';
  const MIN_CODE_LENGTH = 4;
  const MAX_CODE_LENGTH = 8;
  const initialCodeLength = clamp(
    Number(options.codeLength) || MIN_CODE_LENGTH,
    MIN_CODE_LENGTH,
    MAX_CODE_LENGTH
  );
  const labels = options.labels || {};
  const anchor = typeof options.anchor === 'function' ? options.anchor : () => null;
  const onSubmit = typeof options.onSubmit === 'function' ? options.onSubmit : () => Promise.resolve();
  const onCancel = typeof options.onCancel === 'function' ? options.onCancel : null;
  const root = document.getElementById('dial');
  if (!root) return null;

  root.innerHTML = '';
  root.setAttribute('aria-label', mode === 'setup' ? labels.setup_title || '' : labels.dial_aria || '');
  root.setAttribute('role', 'dialog');
  root.setAttribute('aria-modal', 'true');
  root.hidden = true;

  for (const corner of ['tl', 'tr', 'bl', 'br']) {
    root.appendChild(el('i', `dial-corner ${corner}`));
  }

  const head = el('div', 'dial-head');
  const title = el('div', 'dial-title', mode === 'setup' ? labels.setup_title || '' : labels.dial_aria || '');
  const mark = el('div', 'dial-mark', labels.dial_error_seal || '');
  head.appendChild(title);
  head.appendChild(mark);
  root.appendChild(head);

  const wheels = [];
  const repeatWheels = [];
  let codeLength = initialCodeLength;
  let activeWheels = wheels;
  let hintInput = null;
  let lengthSelect = null;
  let focusIndex = 0;

  const syncWheelVisibility = () => {
    for (const [index, wheel] of wheels.entries()) {
      const visible = index < codeLength;
      wheel.hidden = !visible;
      wheel.tabIndex = visible ? 0 : -1;
      wheel.setAttribute('aria-hidden', String(!visible));
    }
    for (const [index, wheel] of repeatWheels.entries()) {
      const visible = index < codeLength;
      wheel.hidden = !visible;
      wheel.tabIndex = visible ? 0 : -1;
      wheel.setAttribute('aria-hidden', String(!visible));
    }
    focusIndex = Math.min(focusIndex, codeLength - 1);
  };

  const setCodeLength = (value) => {
    codeLength = clamp(Number(value) || MIN_CODE_LENGTH, MIN_CODE_LENGTH, MAX_CODE_LENGTH);
    if (lengthSelect) lengthSelect.value = String(codeLength);
    syncWheelVisibility();
  };

  const onWheelInput = (delta, index) => {
    const wheel = wheels[index];
    const next = (wheelValue(wheel) + delta + 10) % 10;
    setWheelValue(wheel, next);
    focusIndex = index;
  };

  if (mode === 'setup') {
    const rows = el('div', 'setup-rows');
    const lengthRow = el('div', 'setup-row');
    lengthRow.appendChild(el('label', null, labels.length_label || '位数'));
    lengthSelect = el('select', 'code-length');
    lengthSelect.setAttribute('aria-label', labels.length_label || '口令位数');
    for (let length = MIN_CODE_LENGTH; length <= MAX_CODE_LENGTH; length += 1) {
      const option = el('option', null, `${length}`);
      option.value = String(length);
      lengthSelect.appendChild(option);
    }
    lengthSelect.value = String(codeLength);
    lengthSelect.addEventListener('change', () => setCodeLength(lengthSelect.value));
    lengthRow.appendChild(lengthSelect);
    rows.appendChild(lengthRow);

    const codeRow = el('div', 'setup-row');
    codeRow.appendChild(el('label', null, labels.code_label || ''));
    const codeWheels = el('div', 'wheels');
    for (let i = 0; i < MAX_CODE_LENGTH; i += 1) {
      const wheel = makeWheel(i, 0, onWheelInput);
      wheel.setAttribute('aria-label', `${labels.code_label || ''} ${i + 1}`);
      codeWheels.appendChild(wheel);
      wheels.push(wheel);
    }
    codeRow.appendChild(codeWheels);
    rows.appendChild(codeRow);

    const repeatRow = el('div', 'setup-row');
    repeatRow.appendChild(el('label', null, labels.repeat_label || ''));
    const repeatRowWheels = el('div', 'wheels');
    for (let i = 0; i < MAX_CODE_LENGTH; i += 1) {
      const wheel = makeWheel(i, 0, (delta, index) => {
        const next = (wheelValue(repeatWheels[index]) + delta + 10) % 10;
        setWheelValue(repeatWheels[index], next);
        activeWheels = repeatWheels;
        focusIndex = index;
      });
      wheel.setAttribute('aria-label', `${labels.repeat_label || ''} ${i + 1}`);
      repeatRowWheels.appendChild(wheel);
      repeatWheels.push(wheel);
    }
    repeatRow.appendChild(repeatRowWheels);
    rows.appendChild(repeatRow);

    const hintRow = el('div', 'setup-row');
    hintRow.appendChild(el('label', null, labels.hint_label || ''));
    hintInput = el('input', 'hint-input');
    hintInput.type = 'text';
    hintInput.maxLength = 20;
    hintInput.autocomplete = 'off';
    hintInput.placeholder = labels.hint_placeholder || '';
    hintInput.setAttribute('aria-label', labels.hint_label || '');
    hintRow.appendChild(hintInput);
    rows.appendChild(hintRow);

    root.appendChild(rows);
    root.appendChild(el('p', 'setup-note', labels.setup_note || ''));
  } else {
    const codeWheels = el('div', 'wheels');
    for (let i = 0; i < MAX_CODE_LENGTH; i += 1) {
      const wheel = makeWheel(i, 0, onWheelInput);
      wheel.setAttribute('aria-label', `${labels.code_label || ''} ${i + 1}`);
      codeWheels.appendChild(wheel);
      wheels.push(wheel);
    }
    root.appendChild(codeWheels);
  }

  const errorLine = el('div', 'dial-error');
  errorLine.setAttribute('role', 'status');
  const hintLine = el('div', 'dial-hint');
  hintLine.hidden = true;
  const actions = el('div', 'dial-actions');
  const wait = el('span', 'dial-wait');
  for (let i = 0; i < 3; i += 1) wait.appendChild(el('i'));
  const submit = el('button', 'dial-submit', mode === 'setup' ? labels.setup_submit || '' : labels.unlock_submit || '');
  submit.type = 'button';
  submit.setAttribute('aria-label', mode === 'setup' ? labels.setup_title || '' : labels.dial_aria || '');
  actions.appendChild(wait);
  actions.appendChild(submit);
  root.appendChild(errorLine);
  root.appendChild(hintLine);
  root.appendChild(actions);

  let pending = false;
  let lastFocus = null;
  let dialOpen = false;

  const dial = {
    element: root,
    mode,
    wheels,
    repeatWheels,
    hintInput,
    anchor,
    labels,
    get codeLength() {
      return codeLength;
    },
    lengthSelect,
    get values() {
      return wheels.slice(0, codeLength).map((wheel) => wheelValue(wheel));
    },
    get repeatValues() {
      return repeatWheels.slice(0, codeLength).map((wheel) => wheelValue(wheel));
    },
    get pending() {
      return pending;
    },
    _onSubmit: onSubmit,
    _onCancel: onCancel,
  };

  const resetPending = () => {
    pending = false;
    submit.disabled = false;
    submit.classList.remove('sunk');
    wait.classList.remove('show');
    for (const wheel of wheels.concat(repeatWheels)) wheel.classList.remove('frozen');
  };

  const submitDial = async () => {
    if (pending || submit.disabled) return;
    const code = dial.values.join('');
    let hint = '';
    if (mode === 'setup') {
      if (dial.repeatValues.join('') !== code) {
        setDialError(dial, labels.mismatch || '');
        return;
      }
      hint = hintInput ? hintInput.value.trim() : '';
    }
    pending = true;
    submit.disabled = true;
    submit.classList.add('sunk');
    wait.classList.add('show');
    for (const wheel of wheels.concat(repeatWheels)) wheel.classList.add('frozen');
    errorLine.textContent = '';
    mark.classList.remove('show');
    try {
      await dial._onSubmit(code, hint);
    } catch {
      resetPending();
    }
  };

  submit.addEventListener('click', submitDial);

  const keydown = (event) => {
    if (event.isComposing) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      if (dial._onCancel) dial._onCancel();
      return;
    }
    if (event.key === 'Tab') {
      const focusables = Array.from(
        root.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])')
      ).filter((node) => !node.disabled && node.offsetParent !== null);
      if (!focusables.length) return;
      const current = focusables.indexOf(document.activeElement);
      const next = event.shiftKey
        ? (current <= 0 ? focusables.length - 1 : current - 1)
        : (current + 1) % focusables.length;
      event.preventDefault();
      focusables[next].focus();
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      submitDial();
      return;
    }
    if (document.activeElement === hintInput) return;
    const targetList = activeWheels;
    if (/^[0-9]$/.test(event.key)) {
      const target = targetList[focusIndex] || targetList[targetList.length - 1];
      setWheelValue(target, Number(event.key));
      focusIndex = Math.min(targetList.length - 1, focusIndex + 1);
      event.preventDefault();
      return;
    }
    if (event.key === 'Backspace') {
      focusIndex = Math.max(0, focusIndex - 1);
      const target = targetList[focusIndex];
      if (target) setWheelValue(target, 0);
      event.preventDefault();
      return;
    }
    if (event.key === 'ArrowUp' || event.key === 'ArrowRight') {
      const target = targetList[focusIndex] || targetList[0];
      setWheelValue(target, (wheelValue(target) + 1) % 10);
      event.preventDefault();
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowLeft') {
      const target = targetList[focusIndex] || targetList[0];
      setWheelValue(target, (wheelValue(target) + 9) % 10);
      event.preventDefault();
    }
  };

  root.addEventListener('keydown', keydown);
  for (let i = 0; i < wheels.length; i += 1) {
    wheels[i].addEventListener('focus', () => {
      activeWheels = wheels;
      focusIndex = i;
    });
  }
  for (let i = 0; i < repeatWheels.length; i += 1) {
    repeatWheels[i].addEventListener('focus', () => {
      activeWheels = repeatWheels;
      focusIndex = i;
    });
  }

  dial.reset = () => {
    setCodeLength(initialCodeLength);
    for (const wheel of wheels) setWheelValue(wheel, 0);
    for (const wheel of repeatWheels) setWheelValue(wheel, 0);
    if (hintInput) hintInput.value = '';
    errorLine.textContent = '';
    hintLine.textContent = '';
    hintLine.hidden = true;
    mark.classList.remove('show');
    window.clearInterval(dial._frozenTimer || 0);
    resetPending();
    activeWheels = wheels;
    focusIndex = 0;
  };

  syncWheelVisibility();

  dial.close = () => closeDial(dial);
  dial.open = () => openDial(dial);
  dial.submit = submitDial;
  dial.focusFirst = () => {
    if (wheels[0]) wheels[0].focus();
  };
  dial._root = root;
  dial._errorLine = errorLine;
  dial._hintLine = hintLine;
  dial._mark = mark;
  dial._submit = submit;
  dial._wait = wait;
  dial._resetPending = resetPending;
  dial._clearFrozen = () => {
    window.clearInterval(dial._frozenTimer || 0);
    dial._frozenTimer = 0;
    submit.disabled = false;
    wait.classList.remove('show');
  };
  dial._isOpen = () => dialOpen;
  dial._setOpen = (value) => {
    dialOpen = value;
  };
  dial._lastFocus = () => lastFocus;
  dial._setLastFocus = (value) => {
    lastFocus = value;
  };
  dial._frozenTimer = 0;

  return dial;
}

export function openDial(dial) {
  if (!dial || !dial.element) return;
  dial._setLastFocus(document.activeElement);
  dial.element.hidden = false;
  dial._setOpen(true);
  dial._clearFrozen();
  window.setTimeout(() => {
    if (dial && dial.element && !dial.element.hidden) {
      const first = dial.wheels[0];
      if (first) first.focus();
    }
  }, 30);
}

export function closeDial(dial) {
  if (!dial || !dial.element) return;
  dial.element.hidden = true;
  dial._setOpen(false);
  window.clearInterval(dial._frozenTimer || 0);
  if (dial._hintLine) {
    dial._hintLine.hidden = true;
    dial._hintLine.textContent = '';
  }
  const last = dial._lastFocus();
  if (last && last.focus) {
    try {
      last.focus();
    } catch {
      // 焦点元素已离开文档时无需处理
    }
  }
}

export function setDialError(dial, message, options = {}) {
  if (!dial || !dial.element) return;
  const root = dial.element;
  root.classList.remove('dial-shake');
  void root.offsetWidth;
  root.classList.add('dial-shake');
  window.setTimeout(() => root.classList.remove('dial-shake'), 380);
  if (dial._mark) dial._mark.classList.add('show');
  if (dial._errorLine) dial._errorLine.textContent = message || '';

  dial._resetPending();

  const frozenSeconds = options.frozenSeconds || 0;
  if (frozenSeconds > 0) {
    let remaining = Math.ceil(frozenSeconds);
    const submit = dial._submit;
    const wait = dial._wait;
    if (submit) submit.disabled = true;
    if (wait) wait.classList.remove('show');
    const waitTemplate = dial.labels.wait_seconds || '{n}';
    if (dial._errorLine) {
      dial._errorLine.textContent = waitTemplate.replace('{n}', String(remaining));
    }
    window.clearInterval(dial._frozenTimer || 0);
    dial._frozenTimer = window.setInterval(() => {
      if (!dial._isOpen()) {
        window.clearInterval(dial._frozenTimer || 0);
        dial._frozenTimer = 0;
        return;
      }
      remaining -= 1;
      if (remaining <= 0) {
        window.clearInterval(dial._frozenTimer || 0);
        dial._frozenTimer = 0;
        if (submit) submit.disabled = false;
        if (dial._errorLine) dial._errorLine.textContent = message || '';
        return;
      }
      if (dial._errorLine) {
        dial._errorLine.textContent = waitTemplate.replace('{n}', String(remaining));
      }
    }, 1000);
    if (dial._hintLine) dial._hintLine.hidden = true;
  }
  if (options.hint) {
    if (dial._hintLine) {
      dial._hintLine.hidden = false;
      dial._hintLine.textContent = (dial.labels.hint_prefix || '{hint}').replace('{hint}', options.hint);
    }
  }
}

export function updateDialPosition(dial, camera, renderer) {
  if (!dial || !dial.element || dial.element.hidden || !camera || !renderer) return;
  const world = dial.anchor();
  if (!world) return;
  const canvas = renderer.domElement;
  const rect = canvas.getBoundingClientRect();
  if (rect.width < 2 || rect.height < 2) return;
  const projected = world.clone().project(camera);
  if (projected.z > 1) {
    dial.element.style.visibility = 'hidden';
    return;
  }
  dial.element.style.visibility = 'visible';
  const x = (projected.x * 0.5 + 0.5) * rect.width + rect.left;
  const y = (-projected.y * 0.5 + 0.5) * rect.height + rect.top;
  const width = dial.element.offsetWidth || 320;
  const height = dial.element.offsetHeight || 260;
  const margin = 12;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const left = clamp(x - width / 2, margin, Math.max(margin, vw - width - margin));
  const top = clamp(y - 24 - height, margin, Math.max(margin, vh - height - margin));
  dial.element.style.left = `${Math.round(left)}px`;
  dial.element.style.top = `${Math.round(top)}px`;
}
