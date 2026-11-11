/* 会通书院工作台：圆角应用壳的轻量交互层。
 * 3D 场景仍由 main.js 管理；这里负责模式、房间和右侧研究信息的同步。
 */

const state = {
  mode: 'learning',
  room: null,
  participant: null,
  poll: null,
  providers: {},
  clearKey: false,
  session: null,
  participantToken: null,
  agentSettings: null,
  agentSettingsBusy: false,
  agentSettingsDirty: false,
  personalAgentProfile: null,
  personalAgentMode: 'chat',
  modalTrigger: null,
  seatName: '',
  dockView: '厅堂',
  dockRequestId: 0,
  researchRunId: 0,
};

const ROOM_STORAGE_KEY = 'huitong.room-context.v1';
window.huitongRoomContext = null;

const $ = (selector, root = document) => root.querySelector(selector);

function setAuthStatus(message, kind = '') { const el = $('#auth-status'); if (el) { el.textContent = message; el.className = `auth-status${kind ? ` ${kind}` : ''}`; } }
function syncModalState() {
  const open = ['#settings-panel', '#admin-panel', '#agent-settings-panel', '#personal-agent-panel'].some((selector) => {
    const node = $(selector);
    return node && !node.hidden;
  });
  document.body.classList.toggle('modal-open', open);
}
function closeAdmin(restoreFocus = true) {
  const panel = $('#admin-panel');
  if (panel) panel.hidden = true;
  syncModalState();
  if (restoreFocus && state.modalTrigger?.isConnected) state.modalTrigger.focus();
  if (restoreFocus) state.modalTrigger = null;
}
function focusModal(panel) {
  const first = panel?.querySelector('button:not([disabled]), input, select, textarea');
  if (first) window.setTimeout(() => first.focus(), 0);
}
function modalFocusable(panel) {
  if (!panel) return [];
  return [...panel.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')]
    .filter((node) => !node.hidden && node.offsetParent !== null);
}
function trapModalFocus(event) {
  const panel = ['#settings-panel', '#admin-panel', '#agent-settings-panel', '#personal-agent-panel']
    .map((selector) => $(selector))
    .find((node) => node && !node.hidden);
  if (!panel) return;
  const focusable = modalFocusable(panel);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (!panel.contains(document.activeElement)) {
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
    return;
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
function showAuth() {
  const gate = $('#auth-gate'); if (!gate) return;
  window.dispatchEvent(new CustomEvent('huitong:auth-logout'));
  closeAdmin();
  closeSettings();
  closeAgentSettings(false);
  closePersonalAgent(false);
  const adminNav = $('#admin-nav');
  if (adminNav) adminNav.remove();
  if (state.poll) window.clearInterval(state.poll);
  state.poll = null;
  state.room = null;
  state.seatName = '';
  state.participantToken = null;
  state.participant = null;
  state.agentSettings = null;
  state.agentSettingsDirty = false;
  state.personalAgentProfile = null;
  state.dockView = '厅堂';
  state.dockRequestId += 1;
  state.researchRunId += 1;
  const settingsButton = $('#agent-settings-open');
  if (settingsButton) settingsButton.hidden = true;
  publishRoomContext();
  document.body.classList.remove('workspace-ready');
  renderTaskCard();
  gate.hidden = false; $('#app-shell').style.display = 'none';
  gate.classList.remove('login-open');
  const authCard = $('#auth-card'); if (authCard) authCard.hidden = true;
  const landingEnter = $('#landing-enter');
  if (landingEnter) landingEnter.setAttribute('aria-expanded', 'false');
  $('#auth-title').textContent = '登录会通书院工作区';
  $('#auth-subtitle').textContent = '登录后进入会通书院厅堂、房间、模型设置和会录管理。';
  $('#auth-confirm-row').hidden = true; $('#auth-role-row').hidden = true;
  $('#auth-confirm').required = false; $('.auth-submit').textContent = '登录';
  const password = $('#auth-password'); if (password) password.value = '';
  const confirm = $('#auth-confirm'); if (confirm) confirm.value = '';
  setAuthStatus('');
  const toggle = $('#auth-toggle'); if (toggle) { toggle.textContent = '本地管理员账号由服务端初始化'; toggle.hidden = true; }
}
function playSceneEntrance() {
  return new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      window.removeEventListener('huitong:entered', finish);
      window.removeEventListener('huitong:scene-ready', start);
      window.clearTimeout(timer);
      resolve();
    };
    const start = () => {
      window.removeEventListener('huitong:scene-ready', start);
      if (!state.session) return;
      if (settled) {
        window.dispatchEvent(new CustomEvent('huitong:enter'));
        return;
      }
      window.addEventListener('huitong:entered', finish);
      window.dispatchEvent(new CustomEvent('huitong:enter'));
    };
    const timer = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      window.removeEventListener('huitong:entered', finish);
      resolve();
    }, 5000);
    if (window.huitongSceneReady) start();
    else window.addEventListener('huitong:scene-ready', start);
  });
}
function queueSceneEntrance() {
  const fire = () => window.dispatchEvent(new CustomEvent('huitong:enter'));
  if (window.huitongSceneReady) fire();
  else window.addEventListener('huitong:scene-ready', fire, { once: true });
}

function publishRoomContext() {
  const context = state.room && state.participantToken
    ? {
        room: state.room,
        participant: state.participant,
        participantToken: state.participantToken,
        seatName: state.seatName,
        mode: state.mode,
      }
    : null;
  window.huitongRoomContext = context;
  try {
    if (context) sessionStorage.setItem(ROOM_STORAGE_KEY, JSON.stringify(context));
    else sessionStorage.removeItem(ROOM_STORAGE_KEY);
  } catch {
    // Session storage can be disabled.  The in-memory context remains valid.
  }
}

function restoreRoomContext() {
  let context = null;
  try {
    context = JSON.parse(sessionStorage.getItem(ROOM_STORAGE_KEY) || 'null');
  } catch {
    context = null;
  }
  if (!context?.room?.id || !context?.participantToken) return;
  state.room = context.room;
  state.participant = context.participant || null;
  state.participantToken = context.participantToken;
  state.seatName = context.seatName || '';
  if (context.mode === 'learning' || context.mode === 'production') state.mode = context.mode;
  const restoredSeat = Number(context.participant?.seat_id);
  const seatPicker = $('#seat-select');
  if (seatPicker && Number.isInteger(restoredSeat) && restoredSeat >= 0 && restoredSeat < seatPicker.options.length) {
    seatPicker.value = String(restoredSeat);
  }
  window.huitongMode = state.mode;
  window.dispatchEvent(new CustomEvent('huitong:room-restored', { detail: { seat: restoredSeat } }));
  publishRoomContext();
  renderTaskCard();
  refreshRoom();
  const aiButton = $('#ai-research');
  if (aiButton) aiButton.hidden = false;
  const settingsButton = $('#agent-settings-open');
  if (settingsButton) settingsButton.hidden = false;
  if (state.poll) window.clearInterval(state.poll);
  state.poll = window.setInterval(refreshRoom, 2500);
  setDock('房间已恢复', [{
    title: `${state.session?.username || '当前成员'} · ${state.seatName || '已入席'}`,
    detail: '已恢复房间身份和会录入口。当前未恢复的进行中模型回合不会显示替代内容。',
  }]);
}
async function enterWorkspace(account, options = {}) {
  state.session = account;
  $('#auth-gate').hidden = true;
  if (options.restored) {
    document.body.classList.add('workspace-ready');
    $('#app-shell').style.display = '';
    queueSceneEntrance();
  } else {
    $('#app-shell').style.display = 'none';
    await playSceneEntrance();
    document.body.classList.add('workspace-ready');
    $('#app-shell').style.display = '';
  }
  const label = $('#session-label'); if (label) label.textContent = `${account.username} · ${account.role === 'admin' ? '管理员' : '成员'}`;
  const nav = $('.app-nav');
  if (account.role === 'admin' && nav && !$('#admin-nav')) { const b = document.createElement('button'); b.id = 'admin-nav'; b.type = 'button'; b.innerHTML = '<span>管理</span>'; nav.appendChild(b); b.addEventListener('click', () => openAdmin(b)); }
  if (account.role !== 'admin') {
    const adminNav = $('#admin-nav');
    if (adminNav) adminNav.remove();
  }
}
async function openAdmin(trigger = null) {
  closeSettings(false);
  state.modalTrigger = trigger || document.activeElement;
  const panel = $('#admin-panel'); if (!panel) return; panel.hidden = false; syncModalState(); focusModal(panel);
  $('#admin-summary').innerHTML = '<div class="admin-loading">正在读取工作区信息……</div>';
  try {
    const data = await jsonFetch('/api/admin/overview');
    const users = data.users || []; const rooms = data.rooms || [];
    $('#admin-summary').innerHTML = `<div class="admin-stat"><b>${users.length}</b><small>用户</small></div><div class="admin-stat"><b>${rooms.length}</b><small>房间</small></div><div class="admin-stat"><b>${rooms.reduce((n, r) => n + (r.last_seq || 0), 0)}</b><small>事件</small></div>`;
    const table = $('#admin-table');
    table.innerHTML = '<div class="admin-row head"><span>用户</span><span>角色</span><span>创建时间</span></div>';
    users.forEach((account) => {
      const row = document.createElement('div'); row.className = 'admin-row';
      [account.username, account.role === 'admin' ? '管理员' : '成员', account.created_at ? new Date(account.created_at * 1000).toLocaleString() : '—'].forEach((value) => { const cell = document.createElement('span'); cell.textContent = value; row.appendChild(cell); });
      table.appendChild(row);
    });
    if (!users.length) table.insertAdjacentHTML('beforeend', '<div class="admin-row"><span>暂无用户</span></div>');
  } catch (error) { $('#admin-table').textContent = `读取后台数据失败：${error.message}`; }
}
async function initAuth() {
  const restoredPromise = (async () => {
    try {
      const response = await fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store' });
      if (response.ok) {
        const data = await response.json();
        return data?.user || null;
      }
    } catch {
      // The login controls are already available.  A failed session probe
      // should leave the cover usable instead of delaying its first click.
    }
    return null;
  })();
  $('#landing-enter')?.addEventListener('click', () => {
    const gate = $('#auth-gate');
    const card = $('#auth-card');
    if (!gate || !card) return;
    gate.classList.add('login-open');
    card.hidden = false;
    $('#landing-enter').setAttribute('aria-expanded', 'true');
    window.setTimeout(() => $('#auth-username')?.focus(), 0);
  });
  $('#auth-back')?.addEventListener('click', () => {
    const gate = $('#auth-gate');
    const card = $('#auth-card');
    if (!gate || !card) return;
    card.hidden = true;
    gate.classList.remove('login-open');
    $('#landing-enter')?.setAttribute('aria-expanded', 'false');
    $('#landing-enter')?.focus();
  });
  $('#auth-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = $('#auth-username').value.trim();
    const password = $('#auth-password').value;
    const submit = $('.auth-submit');
    if (submit) submit.disabled = true;
    setAuthStatus('正在登录……');
    try {
      const response = await fetch('/api/auth/login', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
      const data = await response.json();
      if (!response.ok) {
        const error = new Error(data.error || 'credentials_invalid');
        error.retryAfter = data.retry_after;
        throw error;
      }
      enterWorkspace(data.user);
    } catch (error) {
      if (error.message === 'login_rate_limited') {
        const seconds = Number(error.retryAfter || 60);
        setAuthStatus(`尝试次数过多，请 ${seconds} 秒后再试。`, 'error');
      } else {
        setAuthStatus(error.message === 'credentials_invalid' ? '用户名或密码不正确。' : `登录失败：${error.message}`, 'error');
      }
    } finally {
      if (submit) submit.disabled = false;
    }
  });
  $('#logout-button')?.addEventListener('click', async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
    } finally {
      // Clear local identity and room context even when the network is down,
      // so a failed logout request cannot leave the UI looking authenticated.
      state.session = null;
      state.room = null;
      state.participantToken = null;
      publishRoomContext();
      showAuth();
    }
  });
  $('#admin-close')?.addEventListener('click', closeAdmin);
  const restored = await restoredPromise;
  if (restored) {
    await enterWorkspace(restored, { restored: true });
    restoreRoomContext();
  } else {
    showAuth();
  }
}

function renderTaskCard() {
  const eyebrow = $('.task-card .eyebrow');
  const title = $('.task-card h2');
  const copy = $('.task-card p');
  const primary = $('.workspace-primary');
  if (!title || !copy) return;
  if (state.room) {
    const seat = state.seatName || '已选席位';
    if (eyebrow) eyebrow.textContent = '当前任务 · 已入席';
    title.textContent = '房间已经建立';
    copy.textContent = `你以「${seat}」入席，房间会录已开始记录。可查看会录导出，或在侧栏继续核对设置。`;
    if (primary) { primary.textContent = '房间已建立'; primary.disabled = true; }
    return;
  }
  if (eyebrow) eyebrow.textContent = '当前任务 01';
  if (state.mode === 'production') {
    title.textContent = '召集个人智能体团队';
    copy.textContent = '你提供主题和材料，由七个功能席位独立立论、问难、核验并保留分歧。';
  } else {
    title.textContent = '辨认席位，开启会通';
    copy.textContent = '你作为论证智能体中的一环参与论证，可在每个阶段直接输入观点或材料。';
  }
  if (primary) { primary.textContent = '创建会通房间'; primary.disabled = false; }
}

function setMode(mode) {
  if (state.room) {
    setDock('模式已锁定', [{ title: '房间已经建立', detail: '当前房间的学习/生产模式不能在会谈中切换。', warn: true }]);
    return;
  }
  state.mode = mode;
  window.huitongMode = mode;
  window.dispatchEvent(new CustomEvent('huitong:mode-change', { detail: { mode } }));
  document.querySelectorAll('.mode-switch [data-mode]').forEach((button) => {
    button.classList.toggle('active', button.dataset.mode === mode);
  });
  renderTaskCard();
}

function setDock(title, items = [], ledger = {}) {
  const dock = $('.evidence-dock');
  if (!dock) return;
  const list = $('.evidence-list', dock);
  if (!list) return;
  list.innerHTML = '';
  items.slice(0, 4).forEach((item) => {
    const node = document.createElement('div');
    node.className = `evidence-item${item.warn ? ' warn' : ''}`;
    const title = document.createElement('span');
    title.textContent = item.title || '';
    const detail = document.createElement('small');
    detail.textContent = item.detail || '';
    node.append(title, detail);
    list.appendChild(node);
  });
  const heading = $('h3', dock);
  if (heading && title) heading.textContent = title;
  const ledgerTitle = $('.ledger-title', dock);
  const ledgerPlaceholder = $('.ledger-placeholder', dock);
  if (ledgerTitle && ledger.title) ledgerTitle.textContent = ledger.title;
  if (ledgerPlaceholder && ledger.copy) ledgerPlaceholder.innerHTML = ledger.copy;
}

async function jsonFetch(url, options = {}) {
  const controller = new AbortController();
  const timeoutMs = Number(options.timeoutMs || 12000);
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  const { timeoutMs: _timeoutMs, signal: externalSignal, ...fetchOptions } = options;
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }
  const headers = { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) };
  if (state.participantToken && (url.includes('/api/rooms/') || url === '/api/research' || url.startsWith('/api/session/'))) headers['X-Participant-Token'] = state.participantToken;
  const response = await fetch(url, {
    ...fetchOptions,
    signal: controller.signal,
    headers,
  }).finally(() => window.clearTimeout(timer));
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    showAuth();
    throw new Error('login_required');
  }
  if (!response.ok) throw new Error(data.error || `http_${response.status}`);
  return data;
}

async function refreshRoom() {
  if (!state.room) return;
  try {
    const data = await jsonFetch(`/api/rooms/${state.room.id}/state`);
    const members = (data.participants || []).map((item) => ({
      title: `席位 ${Number(item.seat_id) + 1} · ${item.display_name}`,
      detail: item.kind === 'human' ? '学习者已入席' : '功能智能体',
    }));
    setDock('房间成员与证据', members.length ? [...members, { title: '证据状态', detail: '待会谈材料与出处核验' }] : [{ title: '尚未入席', detail: '可以从厅堂选择一个席位' }, { title: '证据状态', detail: '进入会谈后显示来源与处置记录' }]);
    const stage = $('.stage-meta b');
    if (stage) stage.textContent = `房间 ${state.room.id.slice(0, 6)} · ${data.last_seq || 0} 条事件`;
  } catch (error) {
    if (['participant_token_invalid', 'room_membership_denied', 'participant_not_in_room'].includes(error.message)) {
      state.room = null;
      state.participant = null;
      state.participantToken = null;
      state.seatName = '';
      state.researchRunId += 1;
      if (state.poll) window.clearInterval(state.poll);
      state.poll = null;
      publishRoomContext();
      window.dispatchEvent(new CustomEvent('huitong:room-membership-expired'));
      const aiButton = $('#ai-research');
      if (aiButton) aiButton.hidden = true;
      const settingsButton = $('#agent-settings-open');
      if (settingsButton) settingsButton.hidden = true;
      renderTaskCard();
      setDock('需要重新入席', [{ title: '房间身份已失效', detail: '参与者令牌已过期或不再属于当前房间，请重新创建并入席。', warn: true }]);
      return;
    }
    setDock('连接异常', [{ title: '房间状态暂不可用', detail: error.message, warn: true }]);
  }
}

function roomEventLabel(event) {
  const payload = event?.payload || {};
  const type = event?.type || 'room.event';
  const role = payload.role_id || payload.agent_id || '';
  const roleLabel = role ? ` · ${role}` : '';
  if (type === 'material.submitted') return { title: '材料已提交', detail: String(payload.material || '已进入待核验材料区').slice(0, 180) };
  if (type === 'agent.message' || type === 'agent.prompt') return { title: `${type === 'agent.prompt' ? '智能体提示' : '智能体发言'}${roleLabel}`, detail: String(payload.text || '').slice(0, 180) || '已记录智能体回应' };
  if (type === 'user.message') return { title: `学习者回应${roleLabel}`, detail: String(payload.text || '').slice(0, 180) || '已记录学习者回应' };
  if (type === 'research.completed') {
    const result = payload.result || {};
    return { title: `研究结果${roleLabel}`, detail: String(result.display_text || result.answer || result.summary || '已记录研究结果').slice(0, 180) };
  }
  if (type === 'agent.settings.saved') return { title: `回应偏好已启用 · v${payload.settings_version ?? 0}`, detail: `${role || '当前智能体'} · ${Array.isArray(payload.changed_fields) ? payload.changed_fields.join('、') : '设置已更新'}` };
  if (type === 'session.failed' || type === 'research.failed') return { title: '生成失败', detail: String(payload.error || '服务端未返回替代内容').slice(0, 180), warn: true };
  return { title: type, detail: payload.stage || event?.stage || '已写入房间会录' };
}

async function loadRoomEventsDock(view = state.dockView) {
  state.dockView = view;
  const requestId = ++state.dockRequestId;
  const heading = view === '会录' ? '会录回放' : '证据账本';
  if (!state.room?.id) {
    setDock(heading, [{ title: '当前没有房间', detail: '创建房间并入席后，这里会显示当前房间事件。' }], { title: heading, copy: '当前没有可展示的房间事件。' });
    return;
  }
  setDock(heading, [{ title: '正在读取房间事件……', detail: '仅显示当前登录成员有权查看的事件。' }]);
  try {
    const data = await jsonFetch(`/api/rooms/${encodeURIComponent(state.room.id)}/events?after_seq=0`);
    const events = Array.isArray(data.events) ? data.events : [];
    const filtered = view === '会录'
      ? events
      : events.filter((event) => ['material.submitted', 'evidence_link.added', 'claim.created', 'research.completed', 'research.failed', 'agent.settings.saved'].includes(event.type));
    const items = filtered.slice(-6).reverse().map(roomEventLabel);
    if (requestId !== state.dockRequestId || view !== state.dockView) return;
    setDock(heading, items.length ? items : [{ title: '当前没有相关事件', detail: '完成材料提交、研究或会谈后，这里会显示可核验记录。' }], {
      title: heading,
      copy: view === '会录' ? `当前房间共 ${events.length} 条可见事件，按时间倒序显示。` : '只把当前房间已写入的材料、证据关系和研究事件显示为待核验记录。',
    });
  } catch (error) {
    if (requestId !== state.dockRequestId || view !== state.dockView) return;
    setDock(view === '会录' ? '会录读取失败' : '证据读取失败', [{ title: '无法读取当前房间事件', detail: error.message, warn: true }, { title: '重试', detail: '再次点击侧栏中的会录或证据即可重试。' }], { title: '暂不可用', copy: '服务端事件接口暂时不可用。' });
  }
}

async function createRoom() {
  if (state.room) return;
  const button = $('.workspace-primary');
  const seatSelect = $('#seat-select');
  const seatId = Number(seatSelect?.value || 0);
  const topicSelect = $('#topic-select');
  const customTopic = $('#custom-topic');
  const material = $('#material-input');
  const selectedTopic = topicSelect?.value || 'daofu';
  const topic = selectedTopic === 'custom'
    ? customTopic?.value.trim()
    : topicSelect?.selectedOptions?.[0]?.textContent?.trim() || selectedTopic;
  if (!topic) {
    setDock('还需要一个主题', [{ title: '请输入自定义主题', detail: '主题会写入房间会录，创建后可继续提交材料。', warn: true }]);
    customTopic?.focus();
    return;
  }
  if (button) button.disabled = true;
  try {
    const data = await jsonFetch('/api/rooms', {
      method: 'POST',
      body: JSON.stringify({
        topic,
        mode: state.mode,
        task_id: selectedTopic === 'custom' ? 'custom' : selectedTopic,
      }),
    });
    const room = data.room;
    const joined = await jsonFetch(`/api/rooms/${room.id}/join`, {
      method: 'POST',
      body: JSON.stringify({ seat_id: seatId, display_name: state.session?.username || '我', kind: 'human' }),
    });
    state.room = room;
    state.participant = joined.participant;
    state.participantToken = joined.participant_token || null;
    state.seatName = seatSelect?.selectedOptions?.[0]?.textContent?.split(' · ')[0] || `席位 ${seatId + 1}`;
    if (material?.value.trim()) {
      await jsonFetch(`/api/rooms/${room.id}/events`, {
        method: 'POST',
        body: JSON.stringify({
          event_type: 'material.submitted',
          stage: 'intake',
          payload: { topic, material: material.value.trim(), mode: state.mode },
        }),
      });
    }
    publishRoomContext();
    setDock('房间成员与证据', [{ title: `${state.session?.username || '我'} · ${state.seatName}`, detail: `${state.room.mode === 'learning' ? '学习模式' : '生产模式'} 已启动` }, { title: '证据状态', detail: '等待本轮材料与出处进入账本' }]);
    const meta = $('.stage-meta b');
    if (meta) meta.textContent = `房间 ${state.room.id.slice(0, 6)} · 主持席已入席`;
    if (state.poll) window.clearInterval(state.poll);
    state.poll = window.setInterval(refreshRoom, 2500);
    const aiButton = $('#ai-research');
    if (aiButton) aiButton.hidden = false;
    const settingsButton = $('#agent-settings-open');
    if (settingsButton) settingsButton.hidden = false;
    loadRoomEventsDock(state.dockView).catch(() => {});
    renderTaskCard();
  } catch (error) {
    // A room may already exist server-side when joining or material logging
    // fails.  Clear the local context so the UI never presents a partial room
    // as an established workspace.  The server-side room remains auditable.
    state.room = null;
    state.participant = null;
    state.participantToken = null;
    state.seatName = '';
    publishRoomContext();
    renderTaskCard();
    setDock('房间创建失败', [{ title: '请检查本地服务', detail: error.message, warn: true }]);
  } finally {
    if (button) button.disabled = Boolean(state.room);
  }
}

function researchText(result) {
  if (typeof result === 'string') return result;
  if (!result || typeof result !== 'object') return String(result || '');
  if (typeof result.display_text === 'string') return result.display_text;
  return result.answer || result.summary || result.conclusion || JSON.stringify(result);
}

async function hasValidResearchHash(result, provenance) {
  if (!window.crypto?.subtle || !window.TextEncoder) return false;
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(researchText(result)));
  const actual = Array.from(new Uint8Array(bytes), (value) => value.toString(16).padStart(2, '0')).join('');
  return actual.toLowerCase() === String(provenance?.output_hash || '').toLowerCase();
}

async function runTeamResearch() {
  if (!state.room?.id || !state.participantToken) return;
  const button = $('#ai-research');
  if (button) button.disabled = true;
  const runId = ++state.researchRunId;
  const roomId = state.room.id;
  const participantToken = state.participantToken;
  const isCurrentRun = () => runId === state.researchRunId &&
    state.room?.id === roomId && state.participantToken === participantToken;
  const topicSelect = $('#topic-select');
  const customTopic = $('#custom-topic');
  const material = $('#material-input')?.value.trim() || '';
  const selected = topicSelect?.value || 'daofu';
  const topic = selected === 'custom'
    ? customTopic?.value.trim()
    : topicSelect?.selectedOptions?.[0]?.textContent?.trim() || selected;
  const agents = [
    ['chair', '主持'],
    ['speaker', '立论'],
    ['clarifier', '概念澄清'],
    ['challenger', '问难'],
    ['evidence', '证据核验'],
    ['recorder', '异议记录'],
    ['editor', '最终编辑'],
  ];
  const results = [];
  setDock('七席实时生成中', [{ title: '正在请求服务端实时模型', detail: '只有带有服务端 provenance 的结果才会展示。' }]);
  for (const [agentId, label] of agents) {
    if (!isCurrentRun()) break;
    try {
      const data = await jsonFetch('/api/research', {
        method: 'POST',
        timeoutMs: 30000,
        body: JSON.stringify({
          room_id: state.room.id,
          agent_id: agentId,
          question: `请以${label}席位围绕以下主题提出一份可核验的阶段材料：${topic}`,
          context: material || `当前为${state.mode === 'learning' ? '学习模式' : '生产模式'}，用户作为论证链中的一环参与。请明确事实、推测与待核验问题。`,
        }),
      });
      const provenance = data.result?.provenance;
      const valid = provenance?.source === 'live_api' && provenance?.ai_generated === true &&
        provenance.room_id === state.room.id && provenance.agent_id === agentId &&
        provenance.session_id === `research:${provenance.event_id}` &&
        typeof provenance.provider === 'string' && provenance.provider.length > 0 &&
        typeof provenance.model === 'string' && provenance.model.length > 0 &&
        typeof provenance.server_request_id === 'string' && provenance.server_request_id.length > 0 &&
        typeof provenance.message_id === 'string' && provenance.message_id.length > 0 &&
        typeof provenance.event_id === 'string' && provenance.event_id.length > 0 &&
        Number.isInteger(Number(provenance.settings_version)) && Number(provenance.settings_version) >= 0 &&
        /^[0-9a-f]{64}$/i.test(String(provenance.settings_hash || '')) &&
        /^[0-9a-f]{64}$/i.test(String(provenance.output_hash || '')) &&
        await hasValidResearchHash(data.result, provenance);
      if (!valid) throw new Error('实时模型来源未通过服务端校验');
      if (!isCurrentRun()) break;
      results.push({ title: `${label} · 已核验实时结果`, detail: researchText(data.result).slice(0, 420) });
      setDock('七席 AI 结果', results);
    } catch (error) {
      if (!isCurrentRun()) break;
      results.push({ title: `${label} · 调用失败`, detail: error.message, warn: true });
      setDock('七席 AI 结果', results);
    }
  }
  if (button && isCurrentRun()) button.disabled = false;
}

async function exportRoom() {
  if (!state.room?.id) {
    setDock('会录回放', [{ title: '当前还没有会录', detail: '先创建房间并完成至少一次操作' }, { title: '会谈阶段', detail: '创建房间后会按阶段显示过程记录' }]);
    return;
  }
  const button = $('.workspace-secondary');
  if (button) button.disabled = true;
  try {
    const data = await jsonFetch(`/api/rooms/${state.room.id}/export`, { timeoutMs: 15000 });
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `huitong-room-${state.room.id.slice(0, 8)}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setDock('会录已导出', [{ title: `${data.event_count || 0} 条事件`, detail: 'JSON 会录已下载，可交给 research/normalize_room_export.py 脱敏' }]);
  } catch (error) {
    setDock('会录导出失败', [{ title: '无法导出当前房间', detail: error.message, warn: true }]);
  } finally {
    if (button) button.disabled = false;
  }
}

function settingsElements() {
  const panel = $('#settings-panel');
  return {
    panel,
    close: panel?.querySelector('.settings-close'),
    provider: $('#settings-provider'),
    model: $('#settings-model'),
    apiKey: $('#settings-api-key'),
    baseUrl: $('#settings-base-url'),
    workspace: $('#settings-workspace'),
    region: $('#settings-region'),
    saveMode: $('#settings-save-mode'),
    status: $('#settings-status'),
  };
}

function settingsStatus(message, kind = '') {
  const { status } = settingsElements();
  if (!status) return;
  status.textContent = message;
  status.className = `settings-status${kind ? ` ${kind}` : ''}`;
}

function fillModels(providerId, selected = '') {
  const { model, baseUrl, workspace, apiKey } = settingsElements();
  const preset = state.providers[providerId] || {};
  if (!model) return;
  const models = Array.isArray(preset.models) ? preset.models : [];
  model.innerHTML = '';
  models.forEach((modelId) => {
    const option = document.createElement('option');
    option.value = modelId;
    option.textContent = modelId;
    model.appendChild(option);
  });
  if (selected && !models.includes(selected)) {
    const option = document.createElement('option');
    option.value = selected;
    option.textContent = `${selected} · 已配置`;
    model.appendChild(option);
  }
  if (selected) model.value = selected;
  if (baseUrl) baseUrl.value = preset.base_url || (providerId === 'aliyun' ? '' : baseUrl.value);
  if (workspace) {
    workspace.disabled = !preset.needs_workspace;
    workspace.placeholder = preset.needs_workspace ? '阿里云百炼工作空间 ID' : '此服务商不需要工作空间 ID';
    if (workspace.disabled) workspace.value = '';
  }
  if (apiKey) {
    const keyRequired = preset.api_key_required !== false;
    apiKey.disabled = !keyRequired;
    apiKey.placeholder = keyRequired ? '输入后保存；留空则沿用当前服务商已保存密钥' : '本地服务通常无需 API Key';
    if (!keyRequired) apiKey.value = '';
  }
}

function setProvider(providerId, modelId = '') {
  const { provider, apiKey, baseUrl } = settingsElements();
  if (!provider) return;
  const changed = Boolean(provider.value && provider.value !== providerId);
  if (changed) {
    if (apiKey) apiKey.value = '';
    if (baseUrl) baseUrl.value = '';
    state.clearKey = false;
  }
  provider.value = providerId;
  fillModels(providerId, modelId);
}

async function loadSettings() {
  const data = await jsonFetch('/api/settings/providers');
  state.providers = data.providers || {};
  const { provider, model, baseUrl, workspace, region } = settingsElements();
  if (!provider) return;
  provider.innerHTML = '';
  Object.entries(state.providers).forEach(([id, item]) => {
    const option = document.createElement('option');
    option.value = id;
    option.textContent = item.label || id;
    provider.appendChild(option);
  });
  const current = data.current || {};
  setProvider(current.provider || 'aliyun', current.model || data.default_model);
  if (baseUrl) baseUrl.value = current.base_url || '';
  if (workspace) workspace.value = current.workspace_id || '';
  if (region) region.value = current.region || 'cn-beijing';
  settingsStatus(current.api_key_configured ? '已配置 API Key（仅服务端可见）' : '尚未配置 API Key');
}

function openSettings(trigger = null) {
  closeAdmin(false);
  state.modalTrigger = trigger || document.activeElement;
  const { panel } = settingsElements();
  if (!panel) return;
  panel.hidden = false;
  syncModalState();
  focusModal(panel);
  settingsStatus('正在读取配置……');
  loadSettings().catch((error) => settingsStatus(`读取配置失败：${error.message}`, 'error'));
}

function closeSettings(restoreFocus = true) {
  const { panel } = settingsElements();
  if (panel) panel.hidden = true;
  syncModalState();
  if (restoreFocus && state.modalTrigger?.isConnected) state.modalTrigger.focus();
  if (restoreFocus) state.modalTrigger = null;
}

function agentSettingsElements() {
  const panel = $('#agent-settings-panel');
  return {
    panel,
    close: $('#agent-settings-close'),
    role: $('#agent-settings-role'),
    scope: $('#agent-settings-scope'),
    version: $('#agent-settings-version'),
    rollback: $('#agent-settings-rollback'),
    status: $('#agent-settings-status'),
  };
}

function agentSettingsStatus(message, kind = '') {
  const { status } = agentSettingsElements();
  if (!status) return;
  status.textContent = message;
  status.className = `settings-status${kind ? ` ${kind}` : ''}`;
}

function agentSettingsAgentId() {
  const seat = Number(state.participant?.seat_id);
  return roles().find((role) => role.seat === seat)?.id || '';
}

function agentSettingsPath(agentId = agentSettingsAgentId()) {
  return state.room?.id && agentId
    ? `/api/rooms/${encodeURIComponent(state.room.id)}/agent-settings/${encodeURIComponent(agentId)}`
    : '';
}

function applyAgentSettings(settings = {}) {
  document.querySelectorAll('[data-agent-setting]').forEach((control) => {
    const field = control.dataset.agentSetting;
    const value = settings[field];
    if (value == null) return;
    if (control.type === 'checkbox') control.checked = Boolean(value);
    else control.value = String(value);
    const output = document.querySelector(`[data-agent-output="${field}"]`);
    if (output) output.textContent = String(value);
  });
  state.agentSettingsDirty = false;
}

function collectAgentSettings() {
  const changes = {};
  document.querySelectorAll('[data-agent-setting]').forEach((control) => {
    const field = control.dataset.agentSetting;
    changes[field] = control.type === 'checkbox' ? control.checked : (control.type === 'range' ? Number(control.value) : control.value);
  });
  return changes;
}

function renderAgentSettings(data) {
  const settings = data?.settings || {};
  state.agentSettings = data;
  applyAgentSettings(settings.current || {});
  const { role, scope, version, rollback } = agentSettingsElements();
  if (role) {
    role.innerHTML = '';
    const strong = document.createElement('strong');
    strong.textContent = `${data.role?.name || '当前智能体'} · ${data.role?.title || '回应偏好'}`;
    const detail = document.createElement('span');
    detail.textContent = data.role?.mission || data.role?.duty || '';
    role.append(strong, detail);
  }
  if (scope) scope.textContent = `作用范围 · ${data.scope?.room_id || '当前房间'} · ${data.scope?.agent_id || agentSettingsAgentId()}`;
  if (version) version.textContent = `当前版本 v${data.current_version || 0} · 设置哈希 ${String(data.current_hash || '').slice(0, 12)}… · ${state.agentSettingsDirty ? '有未保存更改' : '新设置只作用于下一次生成'}`;
  if (rollback) {
    rollback.innerHTML = '<option value="">选择已有版本</option>';
    (data.versions || []).filter((item) => item.status !== 'active').reverse().forEach((item) => {
      const option = document.createElement('option');
      option.value = item.settings_version;
      option.textContent = `v${item.settings_version} · ${item.reason || '保存'} · ${new Date((item.created_at || 0) * 1000).toLocaleString()}`;
      rollback.appendChild(option);
    });
  }
}

async function loadAgentSettings() {
  const path = agentSettingsPath();
  if (!path) throw new Error('请先创建并加入房间');
  const data = await jsonFetch(path);
  renderAgentSettings(data.settings);
}

function openAgentSettings(trigger = null) {
  if (!state.room?.id || !state.participantToken) {
    setDock('回应偏好', [{ title: '尚未入席', detail: '创建房间并选择席位后才能调整当前智能体的回应偏好。', warn: true }]);
    return;
  }
  closeSettings(false);
  state.modalTrigger = trigger || document.activeElement;
  const { panel } = agentSettingsElements();
  if (!panel) return;
  panel.hidden = false;
  syncModalState();
  focusModal(panel);
  agentSettingsStatus('正在读取当前席位设置……');
  loadAgentSettings().then(() => agentSettingsStatus('已加载当前版本。')).catch((error) => agentSettingsStatus(`读取失败：${error.message}`, 'error'));
}

function closeAgentSettings(restoreFocus = true) {
  if (restoreFocus && state.agentSettingsDirty && !window.confirm('当前回应偏好有未保存更改，仍要关闭吗？')) return;
  const { panel } = agentSettingsElements();
  if (panel) panel.hidden = true;
  syncModalState();
  if (restoreFocus && state.modalTrigger?.isConnected) state.modalTrigger.focus();
  if (restoreFocus) state.modalTrigger = null;
}

function personalAgentElements() {
  return {
    panel: $('#personal-agent-panel'),
    name: $('#personal-agent-name'),
    mission: $('#personal-agent-mission'),
    scope: $('#personal-agent-scope'),
    subtitle: $('#personal-agent-subtitle'),
    task: $('#personal-agent-task'),
    result: $('#personal-agent-preview-result'),
    specialists: $('#personal-agent-specialists-grid'),
  };
}

function renderPersonalAgentProfile(profile) {
  state.personalAgentProfile = profile;
  const { name, mission, scope, subtitle, specialists } = personalAgentElements();
  if (name) name.textContent = profile?.name || '会通总师';
  if (mission) mission.textContent = profile?.mission || '把目标拆成可执行的下一步。';
  if (scope) scope.textContent = `个人身份 · ${profile?.memory_policy || '按权限读取项目上下文'}`;
  if (subtitle) subtitle.textContent = profile?.working_style || '一个主智能体，背后连接七席专家团队。';
  if (specialists) {
    specialists.innerHTML = '';
    (profile?.specialists || []).forEach((role) => {
      const card = document.createElement('div');
      card.className = 'personal-agent-specialist';
      card.style.setProperty('--agent-color', `var(--seat-${role.seat})`);
      const image = document.createElement('img');
      image.src = role.avatar;
      image.alt = `${role.name}，${role.title}头像`;
      const text = document.createElement('div');
      const strong = document.createElement('strong');
      strong.textContent = role.name;
      const small = document.createElement('small');
      small.textContent = role.title;
      text.append(strong, small);
      card.append(image, text);
      specialists.appendChild(card);
    });
  }
}

async function loadPersonalAgentProfile() {
  const data = await jsonFetch('/api/personal-agent/profile');
  renderPersonalAgentProfile(data.profile || {});
}

function personalAgentModeName() {
  return ({ chat: '普通对话', research: '研究核验', debate: '论证辩论', draft: '受约束写作' })[state.personalAgentMode] || '普通对话';
}

function previewPersonalAgent() {
  const { task, result } = personalAgentElements();
  const text = task?.value.trim() || '';
  if (!result) return;
  if (!text) {
    result.innerHTML = '<strong>还需要一个目标</strong><p>写下你想完成的事情，本地预览会把它整理成一个个人智能体任务卡。</p>';
    task?.focus();
    return;
  }
  result.innerHTML = '';
  const title = document.createElement('strong');
  title.textContent = `${personalAgentModeName()} · 本地任务预览`;
  const body = document.createElement('p');
  body.textContent = `目标：${text}\n\n下一步：明确交付物 → 补充材料与证据边界 → 决定是否带入七席会通。\n\n当前预览不会调用模型服务，也不会写入长期记忆。`;
  result.append(title, body);
}

async function bridgePersonalTaskToRoom() {
  const { task } = personalAgentElements();
  const text = task?.value.trim() || '';
  if (!text) {
    setDock('个人任务', [{ title: '还没有任务内容', detail: '先在“我的智能体”中写下要完成的事情。', warn: true }]);
    return;
  }
  const material = $('#material-input');
  if (material) material.value = text;
  if (state.room?.id && state.participantToken) {
    const button = $('#personal-agent-room');
    if (button) button.disabled = true;
    try {
      await jsonFetch(`/api/rooms/${encodeURIComponent(state.room.id)}/events`, {
        method: 'POST',
        body: JSON.stringify({
          event_type: 'material.submitted',
          stage: 'intake',
          payload: { material: text, mode: state.personalAgentMode, origin: 'personal_agent' },
          idempotency_key: `personal-task:${agentSettingsRequestId()}`,
        }),
      });
      closePersonalAgent();
      setDock('任务已提交到七席', [{ title: personalAgentModeName(), detail: '个人任务已写入当前房间会录，后续由你确认并继续处理。' }]);
      loadRoomEventsDock(state.dockView).catch(() => {});
    } catch (error) {
      setDock('任务提交失败', [{ title: '个人任务未写入会录', detail: error.message, warn: true }]);
    } finally {
      if (button) button.disabled = false;
    }
    return;
  }
  closePersonalAgent();
  setDock('任务已准备进入七席', [{ title: personalAgentModeName(), detail: '创建房间后，任务会进入材料入口。' }]);
}

function openPersonalAgent(trigger = null) {
  closeSettings(false);
  closeAdmin(false);
  state.modalTrigger = trigger || document.activeElement;
  const { panel, result } = personalAgentElements();
  if (!panel) return;
  panel.hidden = false;
  syncModalState();
  focusModal(panel);
  if (result && !state.personalAgentProfile) result.innerHTML = '<strong>正在读取配置</strong><p>正在加载会通总师和七席能力层。</p>';
  loadPersonalAgentProfile().catch((error) => {
    if (result) {
      result.innerHTML = '';
      const title = document.createElement('strong');
      title.textContent = '配置读取失败';
      const message = document.createElement('p');
      message.textContent = error.message;
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'settings-secondary';
      retry.textContent = '重新读取配置';
      retry.addEventListener('click', () => {
        retry.disabled = true;
        result.innerHTML = '<strong>正在读取配置</strong><p>正在加载会通总师和七席能力层。</p>';
        loadPersonalAgentProfile().catch((retryError) => {
          retry.disabled = false;
          result.innerHTML = '';
          const retryTitle = document.createElement('strong');
          retryTitle.textContent = '配置读取失败';
          const retryMessage = document.createElement('p');
          retryMessage.textContent = retryError.message;
          result.append(retryTitle, retryMessage, retry);
        });
      });
      result.append(title, message, retry);
    }
  });
}

function closePersonalAgent(restoreFocus = true) {
  const { panel } = personalAgentElements();
  if (panel) panel.hidden = true;
  syncModalState();
  if (restoreFocus && state.modalTrigger?.isConnected) state.modalTrigger.focus();
  if (restoreFocus) state.modalTrigger = null;
}

function agentSettingsRequestId() {
  return window.crypto?.randomUUID ? window.crypto.randomUUID() : `agent-settings-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function previewAgentSettings() {
  const basePath = agentSettingsPath();
  if (!basePath || !state.agentSettings) return;
  const path = `${basePath}/preview`;
  agentSettingsStatus('正在生成本地预览……');
  try {
    const data = await jsonFetch(path, { method: 'POST', body: JSON.stringify({ changes: collectAgentSettings() }) });
    agentSettingsStatus(`预览完成。版本仍为 v${data.preview.settings_version}，尚未保存。`, 'ok');
  } catch (error) {
    agentSettingsStatus(`预览失败：${error.message}`, 'error');
  }
}

async function saveAgentSettings() {
  const button = $('#agent-settings-save');
  if (button) button.disabled = true;
  const currentVersion = Number(state.agentSettings?.current_version || 0);
  agentSettingsStatus('正在保存并启用……');
  try {
    const data = await jsonFetch(agentSettingsPath(), {
      method: 'POST',
      body: JSON.stringify({ changes: collectAgentSettings(), expected_version: currentVersion, idempotency_key: agentSettingsRequestId() }),
    });
    renderAgentSettings(data.settings);
    agentSettingsStatus(`已启用 v${data.settings.current_version}。下一次生成会使用这一版本。`, 'ok');
  } catch (error) {
    agentSettingsStatus(error.message === 'agent_settings_version_conflict' ? '版本冲突。已重新读取当前设置，请确认后再次保存。' : `保存失败：${error.message}`, 'error');
    if (error.message === 'agent_settings_version_conflict') loadAgentSettings().catch(() => {});
  } finally {
    if (button) button.disabled = false;
  }
}

async function resetAgentSettings() {
  if (!state.agentSettings) return;
  if (!window.confirm('将当前席位的回应偏好重置为默认值，并生成一个新版本。继续吗？')) return;
  const button = $('#agent-settings-reset');
  if (button) button.disabled = true;
  try {
    const data = await jsonFetch(`${agentSettingsPath()}/reset`, { method: 'POST', body: JSON.stringify({ expected_version: Number(state.agentSettings.current_version || 0), idempotency_key: agentSettingsRequestId() }) });
    renderAgentSettings(data.settings);
    agentSettingsStatus(`已重置为默认并启用 v${data.settings.current_version}。`, 'ok');
  } catch (error) {
    agentSettingsStatus(`重置失败：${error.message}`, 'error');
  } finally {
    if (button) button.disabled = false;
  }
}

async function rollbackAgentSettings() {
  const target = Number($('#agent-settings-rollback')?.value || 0);
  if (!target || !state.agentSettings) return;
  const button = $('#agent-settings-rollback-button');
  if (button) button.disabled = true;
  try {
    const data = await jsonFetch(`${agentSettingsPath()}/rollback`, { method: 'POST', body: JSON.stringify({ target_version: target, expected_version: Number(state.agentSettings.current_version || 0), idempotency_key: agentSettingsRequestId() }) });
    renderAgentSettings(data.settings);
    agentSettingsStatus(`已从 v${target} 创建并启用新版本 v${data.settings.current_version}。`, 'ok');
  } catch (error) {
    agentSettingsStatus(`回滚失败：${error.message}`, 'error');
  } finally {
    if (button) button.disabled = false;
  }
}

function settingsPayload() {
  const { provider, model, apiKey, baseUrl, workspace, region, saveMode } = settingsElements();
  return {
    provider: provider?.value || 'aliyun',
    model: model?.value || '',
    api_key: apiKey?.value || '',
    base_url: baseUrl?.value || '',
    workspace_id: workspace?.value || '',
    region: region?.value || 'cn-beijing',
    save_mode: saveMode?.value || 'session',
    clear_api_key: state.clearKey,
  };
}

async function testSettings() {
  const button = $('#settings-test');
  if (button) button.disabled = true;
  settingsStatus('正在测试连接……');
  try {
    const data = await jsonFetch('/api/settings/test', { method: 'POST', body: JSON.stringify(settingsPayload()) });
    settingsStatus(`连接成功：${data.settings.model}（${data.test.mode}）`, 'ok');
  } catch (error) {
    settingsStatus(`连接失败：${error.message}`, 'error');
  } finally {
    if (button) button.disabled = false;
  }
}

async function saveSettings() {
  const button = $('#settings-save');
  if (button) button.disabled = true;
  settingsStatus('正在保存配置……');
  try {
    const data = await jsonFetch('/api/settings', { method: 'POST', body: JSON.stringify(settingsPayload()) });
    state.clearKey = false;
    settingsStatus(`已保存：${data.settings.model} · ${data.saved === 'persistent' ? '本机保存' : '当前会话'}`, 'ok');
    const foot = $('.app-sidebar-foot');
    if (foot) foot.innerHTML = '<span class="status-dot"></span>模型已配置';
  } catch (error) {
    settingsStatus(`保存失败：${error.message}`, 'error');
  } finally {
    if (button) button.disabled = false;
  }
}

function initWorkspace() {
  window.addEventListener('huitong:auth-expired', () => {
    state.session = null;
    state.room = null;
    state.participant = null;
    state.participantToken = null;
    state.seatName = '';
    publishRoomContext();
    showAuth();
  }, { once: false });
  initAuth();
  window.huitongMode = state.mode;
  const topicSelect = $('#topic-select');
  const customTopicRow = $('#custom-topic-row');
  const materialRow = $('#material-row');
  const syncTopicInputs = () => {
    if (customTopicRow) customTopicRow.hidden = topicSelect?.value !== 'custom';
    if (materialRow) materialRow.hidden = state.mode !== 'production';
  };
  document.querySelectorAll('.mode-switch [data-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      setMode(button.dataset.mode);
      syncTopicInputs();
    });
  });
  topicSelect?.addEventListener('change', syncTopicInputs);
  syncTopicInputs();
  const create = $('.workspace-primary');
  if (create) create.addEventListener('click', createRoom);
  const replay = $('.workspace-secondary');
  if (replay) replay.addEventListener('click', exportRoom);
  $('#ai-research')?.addEventListener('click', runTeamResearch);
  $('#personal-agent-close')?.addEventListener('click', () => closePersonalAgent());
  $('#personal-agent-preview')?.addEventListener('click', previewPersonalAgent);
  $('#personal-agent-room')?.addEventListener('click', bridgePersonalTaskToRoom);
  document.querySelectorAll('[data-personal-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      state.personalAgentMode = button.dataset.personalMode || 'chat';
      document.querySelectorAll('[data-personal-mode]').forEach((item) => item.classList.toggle('active', item === button));
      previewPersonalAgent();
    });
  });
  $('#agent-settings-open')?.addEventListener('click', (event) => openAgentSettings(event.currentTarget));
  $('#agent-settings-close')?.addEventListener('click', () => closeAgentSettings());
  $('#agent-settings-cancel')?.addEventListener('click', () => closeAgentSettings());
  $('#agent-settings-preview')?.addEventListener('click', previewAgentSettings);
  $('#agent-settings-save')?.addEventListener('click', saveAgentSettings);
  $('#agent-settings-reset')?.addEventListener('click', resetAgentSettings);
  $('#agent-settings-rollback-button')?.addEventListener('click', rollbackAgentSettings);
  document.querySelectorAll('[data-agent-setting][type="range"]').forEach((control) => {
    control.addEventListener('input', () => {
      const output = document.querySelector(`[data-agent-output="${control.dataset.agentSetting}"]`);
      if (output) output.textContent = control.value;
      state.agentSettingsDirty = true;
      agentSettingsStatus('有未保存更改。预览或保存后才会作用于下一次生成。');
    });
  });
  document.querySelectorAll('[data-agent-setting]:not([type="range"])').forEach((control) => {
    control.addEventListener('change', () => {
      state.agentSettingsDirty = true;
      agentSettingsStatus('有未保存更改。预览或保存后才会作用于下一次生成。');
    });
  });
  const { provider, close } = settingsElements();
  if (provider) provider.addEventListener('change', () => fillModels(provider.value));
  if (close) close.addEventListener('click', closeSettings);
  const test = $('#settings-test');
  if (test) test.addEventListener('click', testSettings);
  const save = $('#settings-save');
  if (save) save.addEventListener('click', saveSettings);
  const clearKey = $('#settings-clear-key');
  if (clearKey) clearKey.addEventListener('click', () => {
    state.clearKey = true;
    const { apiKey, saveMode } = settingsElements();
    if (apiKey) apiKey.value = '';
    if (saveMode) saveMode.value = 'persistent';
    settingsStatus('已标记清除本机 Key，点击“保存配置”后生效。');
  });
  document.querySelectorAll('[data-quick-provider]').forEach((button) => {
    button.addEventListener('click', () => {
      setProvider(button.dataset.quickProvider, button.dataset.quickModel || '');
      const preset = state.providers[button.dataset.quickProvider] || {};
      settingsStatus(preset.api_key_required === false
        ? `已选择 ${button.textContent.trim()}，本地服务无需 API Key，确认服务已启动后测试或保存。`
        : `已选择 ${button.textContent.trim()}，请输入 Key 后测试或保存。`);
    });
  });
  document.querySelectorAll('.app-nav button').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.app-nav button').forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      const label = button.textContent.trim();
      if (label.includes('我的智能体')) {
        openPersonalAgent(button);
        return;
      }
      state.dockView = label.includes('会录') ? '会录' : label.includes('证据') ? '证据' : '厅堂';
      if (label.includes('厅堂')) setDock('厅堂', [
        { title: state.room ? '当前会通房间' : '准备进入会通', detail: state.room ? '可以继续论证，或从三维场景选择席位。' : '选择模式、主题和席位后创建房间。' },
        { title: '七席协作', detail: '立论、澄清、问难、证据、异议与编辑会按阶段接续。' },
        { title: '当前席位', detail: state.seatName || '尚未选择席位' },
      ], {
        title: '入席提示',
        copy: '学习模式由你占据一个席位并直接回应。<br>生产模式由七席智能体协作整理材料。',
      });
      if (label.includes('设置')) openSettings(button);
      if (label.includes('证据') || label.includes('会录')) loadRoomEventsDock(state.dockView);
    });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Tab') { trapModalFocus(event); return; }
    if (event.key !== 'Escape') return;
    const settings = $('#settings-panel');
    const admin = $('#admin-panel');
    const agentSettings = $('#agent-settings-panel');
    const personalAgent = $('#personal-agent-panel');
    if (settings && !settings.hidden) { closeSettings(); return; }
    if (admin && !admin.hidden) { closeAdmin(); return; }
    if (agentSettings && !agentSettings.hidden) { closeAgentSettings(); return; }
    if (personalAgent && !personalAgent.hidden) { closePersonalAgent(); return; }
  });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initWorkspace);
else initWorkspace();

