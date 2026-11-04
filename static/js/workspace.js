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
  modalTrigger: null,
  seatName: '',
};

const $ = (selector, root = document) => root.querySelector(selector);

function setAuthStatus(message, kind = '') { const el = $('#auth-status'); if (el) { el.textContent = message; el.className = `auth-status${kind ? ` ${kind}` : ''}`; } }
function syncModalState() {
  const open = ['#settings-panel', '#admin-panel'].some((selector) => {
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
  const panel = ['#settings-panel', '#admin-panel']
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
  closeAdmin();
  closeSettings();
  const adminNav = $('#admin-nav');
  if (adminNav) adminNav.remove();
  if (state.poll) window.clearInterval(state.poll);
  state.poll = null;
  state.room = null;
  state.seatName = '';
  state.participantToken = null;
  state.participant = null;
  document.body.classList.remove('workspace-ready');
  renderTaskCard();
  gate.hidden = false; $('#app-shell').style.display = 'none';
  $('#auth-title').textContent = '登录会通书院工作区';
  $('#auth-subtitle').textContent = '登录后进入会通书院厅堂、房间、模型设置和会录管理。';
  $('#auth-confirm-row').hidden = true; $('#auth-role-row').hidden = true;
  $('#auth-confirm').required = false; $('.auth-submit').textContent = '登录';
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
      if (settled) return;
      window.removeEventListener('huitong:scene-ready', start);
      window.addEventListener('huitong:entered', finish);
      window.dispatchEvent(new CustomEvent('huitong:enter'));
    };
    const timer = window.setTimeout(finish, 5000);
    if (window.huitongSceneReady) start();
    else window.addEventListener('huitong:scene-ready', start);
  });
}
function queueSceneEntrance() {
  const fire = () => window.dispatchEvent(new CustomEvent('huitong:enter'));
  if (window.huitongSceneReady) fire();
  else window.addEventListener('huitong:scene-ready', fire, { once: true });
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
  // Do not silently restore a browser cookie on a new page load.  The local
  // session remains valid on the server, but the user must explicitly enter
  // the workspace again.  This prevents an old browser cookie from appearing
  // as an unauthenticated entry into the workbench.
  showAuth();
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
  $('#logout-button')?.addEventListener('click', async () => { await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }); state.session = null; state.room = null; state.participantToken = null; showAuth(); });
  $('#admin-close')?.addEventListener('click', closeAdmin);
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
  const headers = { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) };
  if (state.participantToken && url.includes('/api/rooms/')) headers['X-Participant-Token'] = state.participantToken;
  const response = await fetch(url, {
    ...fetchOptions,
    signal: externalSignal || controller.signal,
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
    setDock('连接异常', [{ title: '房间状态暂不可用', detail: error.message, warn: true }]);
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
    state.room = data.room;
    const joined = await jsonFetch(`/api/rooms/${state.room.id}/join`, {
      method: 'POST',
      body: JSON.stringify({ seat_id: seatId, display_name: state.session?.username || '我', kind: 'human' }),
    });
    state.participant = joined.participant;
    state.participantToken = joined.participant_token || null;
    state.seatName = seatSelect?.selectedOptions?.[0]?.textContent?.split(' · ')[0] || `席位 ${seatId + 1}`;
    if (material?.value.trim()) {
      await jsonFetch(`/api/rooms/${state.room.id}/events`, {
        method: 'POST',
        body: JSON.stringify({
          event_type: 'material.submitted',
          stage: 'intake',
          payload: { topic, material: material.value.trim(), mode: state.mode },
        }),
      });
    }
    setDock('房间成员与证据', [{ title: `${state.session?.username || '我'} · ${state.seatName}`, detail: `${state.room.mode === 'learning' ? '学习模式' : '生产模式'} 已启动` }, { title: '证据状态', detail: '等待本轮材料与出处进入账本' }]);
    const meta = $('.stage-meta b');
    if (meta) meta.textContent = `房间 ${state.room.id.slice(0, 6)} · 主持席已入席`;
    if (state.poll) window.clearInterval(state.poll);
    state.poll = window.setInterval(refreshRoom, 2500);
    const aiButton = $('#ai-research');
    if (aiButton) aiButton.hidden = false;
    renderTaskCard();
  } catch (error) {
    setDock('房间创建失败', [{ title: '请检查本地服务', detail: error.message, warn: true }]);
  } finally {
    if (button) button.disabled = Boolean(state.room);
  }
}

function researchText(result) {
  if (typeof result === 'string') return result;
  if (!result || typeof result !== 'object') return String(result || '');
  return result.answer || result.summary || result.conclusion || JSON.stringify(result);
}

async function runTeamResearch() {
  if (!state.room?.id || !state.participantToken) return;
  const button = $('#ai-research');
  if (button) button.disabled = true;
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
  setDock('七席 AI 生成中', [{ title: '正在调用真实模型', detail: '会通服务端会按席位记录每次研究调用。' }]);
  for (const [agentId, label] of agents) {
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
      results.push({ title: `${label} · ${agentId}`, detail: researchText(data.result).slice(0, 420) });
      setDock('七席 AI 结果', results);
    } catch (error) {
      results.push({ title: `${label} · 调用失败`, detail: error.message, warn: true });
      setDock('七席 AI 结果', results);
    }
  }
  if (button) button.disabled = false;
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
  const { provider } = settingsElements();
  if (!provider) return;
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
  settingsStatus(current.api_key_configured ? `当前 Key：${current.api_key_masked}` : '尚未配置 API Key');
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
      if (label.includes('厅堂')) setDock('厅堂', [
        { title: state.room ? '当前会通房间' : '准备进入会通', detail: state.room ? '可以继续论证，或从三维场景选择席位。' : '选择模式、主题和席位后创建房间。' },
        { title: '七席协作', detail: '立论、澄清、问难、证据、异议与编辑会按阶段接续。' },
        { title: '当前席位', detail: state.seatName || '尚未选择席位' },
      ], {
        title: '入席提示',
        copy: '学习模式由你占据一个席位并直接回应。<br>生产模式由七席智能体协作整理材料。',
      });
      if (label.includes('设置')) openSettings(button);
      if (label.includes('证据')) setDock('证据账本', [
        { title: 'P02_S01 · 《学记》原文', detail: '材料包示例 · 待核对引文与出处' },
        { title: 'P02_S02 · 注疏节选', detail: '支持关系示例 · 与主张逐条绑定' },
        { title: 'P08_S01 · 历史边界', detail: '异议示例 · 等待席位回应' },
      ], {
        title: '证据处置示例',
        copy: '来源进入会谈后，会按“支持、限制、待核验”分层记录。<br>共同记忆和席位记录均由后台维护。',
      });
      if (label.includes('会录')) setDock('会录回放', [
        { title: '示例 01 · 材料导入', detail: '主持席确认问题边界，锁定 P02 与 P08 材料包。' },
        { title: '示例 02 · 证据核验', detail: '证据席标记一条出处待核查，并保留限定条件。' },
        { title: '示例 03 · 异议登记', detail: '异议席保留替代解释，等待最终编辑回应。' },
      ], {
        title: '会录阶段摘要',
        copy: '材料导入 → 独立立论 → 概念澄清 → 问难核验 → 回应修订 → 异议登记 → 受约束编辑。',
      });
    });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Tab') { trapModalFocus(event); return; }
    if (event.key !== 'Escape') return;
    const settings = $('#settings-panel');
    const admin = $('#admin-panel');
    if (settings && !settings.hidden) { closeSettings(); return; }
    if (admin && !admin.hidden) { closeAdmin(); return; }
  });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initWorkspace);
else initWorkspace();

