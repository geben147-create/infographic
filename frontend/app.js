// Update API_BASE to your FastAPI server URL when deploying to Netlify
const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'http://localhost:8000';

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
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    renderRuns(data);
    hideRunsError();
  } catch (err) {
    showRunsError(`Error loading pipeline runs: ${err.message}`);
    console.error('fetchRuns error:', err);
  }
}

async function fetchCosts() {
  const url = `${API_BASE}/api/dashboard/costs?days=30`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    renderCosts(data);
  } catch (err) {
    const container = document.getElementById('cost-cards');
    container.innerHTML = `<div class="error-banner">Error loading cost data: ${err.message}</div>`;
    console.error('fetchCosts error:', err);
  }
}

// ---- Render Functions ----

function renderRuns(data) {
  totalRuns = data.total;
  const tbody = document.getElementById('runs-body');
  tbody.innerHTML = '';

  if (!data.runs || data.runs.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="7" class="empty-state">No pipeline runs found.</td>`;
    tbody.appendChild(tr);
    updatePagination();
    return;
  }

  data.runs.forEach((run) => {
    // Track unique channels for filter dropdown
    if (run.channel_id && !seenChannels.has(run.channel_id)) {
      seenChannels.add(run.channel_id);
      updateChannelFilter();
    }

    const statusClass = getStatusClass(run.status);
    const displayId = run.workflow_id.length > 20
      ? run.workflow_id.substring(0, 20) + '...'
      : run.workflow_id;
    const cost = run.total_cost_usd != null
      ? `$${run.total_cost_usd.toFixed(2)}`
      : '--';
    const startedAt = formatDate(run.started_at);
    const completedAt = formatDate(run.completed_at);

    const canDownload = run.status === 'ready_to_upload' || run.status === 'completed';
    const actionsHtml = canDownload
      ? `<a href="${API_BASE}/api/pipeline/${encodeURIComponent(run.workflow_id)}/download"
            class="btn btn-download">Download Video</a>
         <a href="${API_BASE}/api/pipeline/${encodeURIComponent(run.workflow_id)}/thumbnail"
            class="btn btn-thumbnail">Thumbnail</a>`
      : '<span style="color:#9ca3af;font-size:12px;">N/A</span>';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td title="${escapeHtml(run.workflow_id)}">${escapeHtml(displayId)}</td>
      <td>${escapeHtml(run.channel_id || '--')}</td>
      <td><span class="badge ${statusClass}">${escapeHtml(run.status)}</span></td>
      <td>${escapeHtml(cost)}</td>
      <td>${escapeHtml(startedAt)}</td>
      <td>${escapeHtml(completedAt)}</td>
      <td>${actionsHtml}</td>
    `;
    tbody.appendChild(tr);
  });

  updatePagination();
}

function renderCosts(data) {
  const container = document.getElementById('cost-cards');
  container.innerHTML = '';

  // Total card
  const totalCard = document.createElement('div');
  totalCard.className = 'cost-card total-card';
  totalCard.innerHTML = `
    <div class="amount">$${data.total_cost_usd.toFixed(2)}</div>
    <div class="label">Total (${data.days} days)</div>
  `;
  container.appendChild(totalCard);

  // Per-channel cards
  if (data.by_channel && data.by_channel.length > 0) {
    data.by_channel.forEach((ch) => {
      const card = document.createElement('div');
      card.className = 'cost-card';
      card.innerHTML = `
        <div class="amount">$${ch.total_cost_usd.toFixed(2)}</div>
        <div class="label">${escapeHtml(ch.channel_id)} (${ch.run_count} runs)</div>
      `;
      container.appendChild(card);
    });
  }
}

// ---- Helper Functions ----

function formatDate(isoStr) {
  if (!isoStr) return '--';
  try {
    return new Date(isoStr).toLocaleString();
  } catch {
    return isoStr;
  }
}

function getStatusClass(status) {
  const known = ['ready_to_upload', 'completed', 'running', 'failed', 'waiting_approval'];
  return known.includes(status) ? status : 'unknown';
}

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function updateChannelFilter() {
  const select = document.getElementById('channel-filter');
  const currentVal = select.value;

  // Remove existing channel options (keep "All Channels")
  while (select.options.length > 1) {
    select.remove(1);
  }

  // Re-add sorted channels
  Array.from(seenChannels).sort().forEach((ch) => {
    const opt = document.createElement('option');
    opt.value = ch;
    opt.textContent = ch;
    select.appendChild(opt);
  });

  // Restore selection
  select.value = currentVal;
}

function updatePagination() {
  const page = Math.floor(currentOffset / PAGE_SIZE) + 1;
  document.getElementById('page-info').textContent = `Page ${page}`;
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

// ---- Refresh & Auto-Refresh ----

function refresh() {
  fetchRuns();
  fetchCosts();
  document.getElementById('last-updated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
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

// ---- Initial Load ----

refresh();

// ---- Auto-Refresh every 30 seconds ----

setInterval(refresh, 30000);
