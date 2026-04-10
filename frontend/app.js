// Update API_BASE to your FastAPI server URL when deploying
const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8002' : 'http://localhost:8002';

// State
let currentOffset = 0;
const PAGE_SIZE = 20;
let currentChannel = '';
let totalRuns = 0;
const seenChannels = new Set();

// ---- Fetch Functions ----

async function fetchRuns() {
  let url = `${API_BASE}/api/dashboard/runs?limit=${PAGE_SIZE}&offset=${currentOffset}`;
  if (currentChannel) {
    url += `&channel_id=${encodeURIComponent(currentChannel)}`;
  }

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();
    renderRuns(data);
    updateStats(data);
    hideRunsError();
  } catch (err) {
    showRunsError(`Error loading pipeline runs: ${err.message}`);
  }
}

async function fetchCosts() {
  try {
    const res = await fetch(`${API_BASE}/api/dashboard/costs?days=30`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderCosts(data);
    document.getElementById('stat-cost').textContent = `$${data.total_cost_usd.toFixed(2)}`;
  } catch (err) {
    document.getElementById('cost-bars').innerHTML = `<div class="cost-empty">Error loading costs: ${err.message}</div>`;
  }
}

async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderHealth(data);
  } catch (err) {
    renderHealthError();
  }
}

// ---- Render Functions ----

function renderRuns(data) {
  totalRuns = data.total;
  const tbody = document.getElementById('runs-body');
  tbody.innerHTML = '';

  if (!data.runs || data.runs.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="6">
        <div class="empty-state">
          <div class="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M9.5 8.5L14.5 12L9.5 15.5V8.5Z"/></svg>
          </div>
          No pipeline runs yet. Trigger your first video to get started.
        </div>
      </td></tr>`;
    updatePagination();
    return;
  }

  data.runs.forEach((run) => {
    if (run.channel_id && !seenChannels.has(run.channel_id)) {
      seenChannels.add(run.channel_id);
      updateChannelFilter();
    }

    const statusClass = getStatusClass(run.status);
    const displayStatus = run.status.replace(/_/g, ' ');
    const displayId = run.workflow_id.length > 16
      ? run.workflow_id.substring(0, 16) + '...'
      : run.workflow_id;
    const cost = run.total_cost_usd != null ? `$${run.total_cost_usd.toFixed(2)}` : '--';
    const startedAt = formatRelativeTime(run.started_at);

    const canDownload = run.status === 'ready_to_upload' || run.status === 'completed';
    const actionsHtml = canDownload
      ? `<div class="actions-cell">
           <a href="${API_BASE}/api/pipeline/${encodeURIComponent(run.workflow_id)}/download" class="btn btn-primary">
             <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
             Video
           </a>
           <a href="${API_BASE}/api/pipeline/${encodeURIComponent(run.workflow_id)}/thumbnail" class="btn btn-secondary">Thumb</a>
         </div>`
      : `<span style="color:var(--gray-400);font-size:12px;">--</span>`;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="cell-mono" title="${esc(run.workflow_id)}">${esc(displayId)}</span></td>
      <td>${esc(run.channel_id || '--')}</td>
      <td><span class="badge ${statusClass}">${esc(displayStatus)}</span></td>
      <td>${esc(cost)}</td>
      <td>${esc(startedAt)}</td>
      <td>${actionsHtml}</td>
    `;
    tbody.appendChild(tr);
  });

  updatePagination();
}

function updateStats(data) {
  document.getElementById('stat-total-runs').textContent = data.total;
  document.getElementById('table-info').textContent = `${data.total} run${data.total !== 1 ? 's' : ''}`;

  if (data.runs) {
    const running = data.runs.filter(r => r.status === 'running').length;
    const ready = data.runs.filter(r => r.status === 'ready_to_upload').length;
    document.getElementById('stat-running').textContent = running;
    document.getElementById('stat-ready').textContent = ready;
  }
}

function renderCosts(data) {
  const container = document.getElementById('cost-bars');
  container.innerHTML = '';

  if (!data.by_channel || data.by_channel.length === 0) {
    container.innerHTML = `<div class="cost-empty">No cost data yet</div>`;
    return;
  }

  const maxCost = Math.max(...data.by_channel.map(c => c.total_cost_usd), 0.01);

  data.by_channel.forEach((ch) => {
    const pct = Math.max((ch.total_cost_usd / maxCost) * 100, 2);
    const row = document.createElement('div');
    row.className = 'cost-row';
    row.innerHTML = `
      <span class="cost-channel-name">${esc(ch.channel_id)}</span>
      <div class="cost-bar-track">
        <div class="cost-bar-fill" style="width:${pct}%"></div>
      </div>
      <span class="cost-bar-amount">$${ch.total_cost_usd.toFixed(2)}</span>
    `;
    container.appendChild(row);
  });
}

function renderHealth(data) {
  const grid = document.getElementById('health-grid');
  const items = [
    { name: 'Temporal', ok: data.temporal, val: data.temporal ? 'Connected' : 'Disconnected' },
    { name: 'SQLite', ok: data.sqlite, val: data.sqlite ? 'Healthy' : 'Error' },
    { name: 'Disk', ok: data.disk_free_gb > 5, val: `${data.disk_free_gb.toFixed(1)} GB free` },
  ];

  grid.innerHTML = items.map(it => `
    <div class="health-item ${it.ok ? 'ok' : 'fail'}">
      <span class="health-dot"></span>
      <span class="health-name">${it.name}</span>
      <span class="health-val">${it.val}</span>
    </div>
  `).join('');

  // Update sidebar status
  const statusEl = document.getElementById('system-status');
  const allOk = items.every(i => i.ok);
  const dot = statusEl.querySelector('.status-dot');
  const text = statusEl.querySelector('.status-text');
  dot.className = 'status-dot ' + (allOk ? 'ok' : 'degraded');
  text.textContent = allOk ? 'All systems operational' : 'Degraded';
}

function renderHealthError() {
  const grid = document.getElementById('health-grid');
  grid.innerHTML = `
    <div class="health-item fail"><span class="health-dot"></span><span class="health-name">Temporal</span><span class="health-val">--</span></div>
    <div class="health-item fail"><span class="health-dot"></span><span class="health-name">SQLite</span><span class="health-val">--</span></div>
    <div class="health-item fail"><span class="health-dot"></span><span class="health-name">Disk</span><span class="health-val">--</span></div>
  `;
  const statusEl = document.getElementById('system-status');
  statusEl.querySelector('.status-dot').className = 'status-dot error';
  statusEl.querySelector('.status-text').textContent = 'Cannot reach API';
}

// ---- Helpers ----

function formatRelativeTime(isoStr) {
  if (!isoStr) return '--';
  try {
    const d = new Date(isoStr);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
  } catch {
    return isoStr;
  }
}

function getStatusClass(status) {
  const known = ['ready_to_upload', 'completed', 'running', 'failed', 'waiting_approval'];
  return known.includes(status) ? status : 'unknown';
}

function esc(str) {
  if (str == null) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function updateChannelFilter() {
  const select = document.getElementById('channel-filter');
  const val = select.value;
  while (select.options.length > 1) select.remove(1);
  Array.from(seenChannels).sort().forEach((ch) => {
    const opt = document.createElement('option');
    opt.value = ch;
    opt.textContent = ch;
    select.appendChild(opt);
  });
  select.value = val;
}

function updatePagination() {
  const page = Math.floor(currentOffset / PAGE_SIZE) + 1;
  document.getElementById('page-info').textContent = page;
  document.getElementById('prev-btn').disabled = currentOffset === 0;
  document.getElementById('next-btn').disabled = currentOffset + PAGE_SIZE >= totalRuns;
}

function showRunsError(msg) {
  const banner = document.getElementById('runs-error');
  banner.textContent = msg;
  banner.style.display = 'block';
}

function hideRunsError() {
  document.getElementById('runs-error').style.display = 'none';
}

// ---- Refresh ----

async function refresh() {
  const btn = document.getElementById('refresh-btn');
  btn.classList.add('spinning');

  await Promise.all([fetchRuns(), fetchCosts(), fetchHealth()]);

  btn.classList.remove('spinning');
  document.getElementById('last-updated').textContent =
    new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
}

// ---- Event Listeners ----

document.getElementById('refresh-btn').addEventListener('click', refresh);

document.getElementById('channel-filter').addEventListener('change', (e) => {
  currentChannel = e.target.value;
  currentOffset = 0;
  fetchRuns();
});

document.getElementById('prev-btn').addEventListener('click', () => {
  currentOffset = Math.max(0, currentOffset - PAGE_SIZE);
  fetchRuns();
});

document.getElementById('next-btn').addEventListener('click', () => {
  currentOffset += PAGE_SIZE;
  fetchRuns();
});

// Sidebar nav (visual only — single page)
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');
  });
});

// ---- Init ----
refresh();
setInterval(refresh, 30000);
