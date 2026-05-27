/**
 * Admin Dashboard — fetches conversations and stats from the API
 * and renders them in the admin.html page.
 */

const API_BASE = window.API_BASE || 'http://localhost:8000';

// ── Bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  loadConversations();

  document.getElementById('refresh-btn').addEventListener('click', () => {
    loadStats();
    loadConversations();
  });

  document.getElementById('search-input').addEventListener('input', (e) => {
    filterConversations(e.target.value.toLowerCase());
  });

  document.getElementById('filter-status').addEventListener('change', (e) => {
    applyFilters();
  });

  // Close detail panel
  document.getElementById('close-detail').addEventListener('click', () => {
    document.getElementById('detail-panel').classList.remove('open');
  });
});

// ── Stats ─────────────────────────────────────────────────────────────────────

async function loadStats() {
  try {
    const data = await apiFetch('/api/stats');
    document.getElementById('stat-total').textContent      = data.total_conversations;
    document.getElementById('stat-resolved').textContent   = data.resolved;
    document.getElementById('stat-escalated').textContent  = data.escalated;
    document.getElementById('stat-messages').textContent   = data.total_messages;
  } catch (err) {
    console.error('Stats load failed:', err);
  }
}

// ── Conversations list ────────────────────────────────────────────────────────

let allConversations = [];

async function loadConversations() {
  const list = document.getElementById('conv-list');
  list.innerHTML = '<div class="loading-spinner">Loading conversations…</div>';

  try {
    allConversations = await apiFetch('/api/conversations');
    renderConversations(allConversations);
  } catch (err) {
    list.innerHTML = `<div class="error-state">Could not load conversations. Is the server running?</div>`;
  }
}

function renderConversations(convs) {
  const list = document.getElementById('conv-list');

  if (!convs.length) {
    list.innerHTML = '<div class="empty-state">No conversations yet. Share your widget to get started!</div>';
    return;
  }

  list.innerHTML = convs.map(conv => `
    <div class="conv-row ${conv.escalated ? 'escalated' : ''}" data-id="${conv.id}" onclick="openConversation('${conv.id}')">
      <div class="conv-avatar">${conv.agent_id.charAt(0).toUpperCase()}</div>
      <div class="conv-body">
        <div class="conv-meta">
          <span class="conv-id">#${conv.id.slice(0, 8)}</span>
          ${conv.escalated ? '<span class="badge badge-red">Escalated</span>' : '<span class="badge badge-green">Resolved</span>'}
        </div>
        <div class="conv-preview">${escHtml(conv.preview)}</div>
        <div class="conv-stats">
          <span>💬 ${conv.message_count} messages</span>
          <span>🕐 ${formatDate(conv.created_at)}</span>
        </div>
      </div>
    </div>`).join('');
}

// ── Filters ───────────────────────────────────────────────────────────────────

function filterConversations(query) {
  applyFilters(query);
}

function applyFilters(query) {
  const searchVal = (query ?? document.getElementById('search-input').value).toLowerCase();
  const statusVal = document.getElementById('filter-status').value;

  const filtered = allConversations.filter(conv => {
    const matchesSearch = !searchVal || conv.preview.toLowerCase().includes(searchVal) || conv.id.includes(searchVal);
    const matchesStatus =
      statusVal === 'all' ||
      (statusVal === 'escalated' && conv.escalated) ||
      (statusVal === 'resolved' && !conv.escalated);
    return matchesSearch && matchesStatus;
  });

  renderConversations(filtered);
}

// ── Detail panel ──────────────────────────────────────────────────────────────

async function openConversation(sessionId) {
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');

  panel.classList.add('open');
  content.innerHTML = '<div class="loading-spinner">Loading…</div>';

  try {
    const conv = await apiFetch(`/api/conversations/${sessionId}`);
    content.innerHTML = renderDetail(conv);
  } catch (err) {
    content.innerHTML = '<div class="error-state">Could not load this conversation.</div>';
  }
}

function renderDetail(conv) {
  const messages = (conv.messages || []).map(msg => {
    const isUser = msg.role === 'user';
    return `
      <div class="detail-msg ${isUser ? 'user' : 'bot'}">
        <div class="detail-role">${isUser ? '👤 User' : '🤖 Agent'}</div>
        <div class="detail-bubble">${escHtml(msg.content)}</div>
        ${msg.sources?.length ? `<div class="detail-sources">${msg.sources.map(s => `<a href="${escHtml(s)}" target="_blank">🔗 Source</a>`).join(' ')}</div>` : ''}
        ${msg.escalate ? '<span class="badge badge-red">Escalation flagged</span>' : ''}
        <div class="detail-time">${formatDate(msg.timestamp)}</div>
      </div>`;
  }).join('');

  return `
    <div class="detail-header">
      <strong>Session</strong> <code>${conv.id}</code>
      <br><strong>Agent</strong> ${escHtml(conv.agent_id)}
      <br><strong>Started</strong> ${formatDate(conv.created_at)}
      ${conv.escalated ? '<br><span class="badge badge-red">Escalated</span>' : '<br><span class="badge badge-green">Resolved</span>'}
    </div>
    <div class="detail-messages">${messages}</div>`;
}

// ── Onboarding form (on index.html, reused here too) ─────────────────────────

if (document.getElementById('onboard-form')) {
  document.getElementById('onboard-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn      = document.getElementById('onboard-btn');
    const progress = document.getElementById('progress-wrap');
    const fill     = document.getElementById('progress-fill');
    const label    = document.getElementById('progress-label');
    const successBox = document.getElementById('success-box');

    const url         = document.getElementById('docs-url').value.trim();
    const productName = document.getElementById('product-name').value.trim();
    const agentId     = productName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

    btn.disabled = true;
    btn.textContent = 'Indexing…';
    progress.style.display = 'block';
    fill.style.width = '15%';
    label.textContent = 'Scraping documentation pages…';

    try {
      const job = await apiFetch('/api/onboard', 'POST', { url, product_name: productName, agent_id: agentId });

      // Poll for completion
      let done = false;
      let pct = 20;
      while (!done) {
        await sleep(1500);
        const status = await apiFetch(`/api/onboard/status/${job.job_id}`);
        pct = Math.min(pct + 15, 90);
        fill.style.width = pct + '%';
        label.textContent = status.status === 'done'
          ? `Indexed ${status.pages_indexed} pages ✓`
          : 'Processing pages…';

        if (status.status === 'done' || status.status === 'error') done = true;
      }

      fill.style.width = '100%';
      progress.style.display = 'none';
      successBox.style.display = 'block';
      document.getElementById('embed-code').textContent =
        `<script>\n  window.AISupportConfig = {\n    agentId: "${agentId}",\n    agentName: "${escHtml(productName)}",\n    apiBase: "http://localhost:8000"\n  };\n<\/script>\n<script src="http://localhost:8000/js/widget.js"><\/script>`;

    } catch (err) {
      label.textContent = 'Something went wrong. Check the server logs.';
      fill.style.background = '#EF4444';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Index Documentation';
    }
  });
}

// ── Utilities ─────────────────────────────────────────────────────────────────

async function apiFetch(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
