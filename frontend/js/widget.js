/**
 * AI Support Widget — Embeddable Chat Interface
 *
 * Usage: add these two lines before </body> in any HTML page:
 *   <script>window.AISupportConfig = { agentId: "YOUR_AGENT_ID", apiBase: "https://your-api.com" };</script>
 *   <script src="widget.js"></script>
 */

(function () {
  'use strict';

  const CONFIG = window.AISupportConfig || {};
  const API_BASE   = CONFIG.apiBase   || 'http://localhost:8000';
  const AGENT_ID   = CONFIG.agentId   || 'default';
  const AGENT_NAME = CONFIG.agentName || 'Support Agent';
  const WELCOME_MSG = CONFIG.welcomeMessage || `Hi there 👋 I'm your support assistant. Ask me anything about ${AGENT_NAME}!`;
  const QUICK_PROMPTS = CONFIG.quickPrompts || [
    'How do I get started?',
    'What are the pricing plans?',
    'How do I contact support?',
  ];

  // Unique session per browser visit
  const SESSION_ID = _getOrCreateSession();

  let msgCount = 0;  // Tracks assistant message index for feedback
  let isOpen = false;

  // ── Build DOM ───────────────────────────────────────────────────────────────

  function buildWidget() {
    injectCSS();

    // Launcher button
    const launcher = document.createElement('button');
    launcher.id = 'ai-support-launcher';
    launcher.setAttribute('aria-label', 'Open support chat');
    launcher.innerHTML = `
      <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
      </svg>
      <span class="notif-dot"></span>`;
    launcher.addEventListener('click', toggleWidget);

    // Chat window
    const widget = document.createElement('div');
    widget.id = 'ai-support-widget';
    widget.setAttribute('role', 'dialog');
    widget.setAttribute('aria-label', 'Customer support chat');
    widget.innerHTML = `
      <div class="widget-header">
        <div class="widget-avatar">🤖</div>
        <div class="widget-info">
          <div class="widget-name">${escHtml(AGENT_NAME)}</div>
          <div class="widget-status">
            <span class="status-dot"></span> Online · Replies instantly
          </div>
        </div>
        <button class="widget-close" aria-label="Close chat">✕</button>
      </div>

      <div class="widget-messages" id="widget-messages">
        <div class="widget-welcome">
          <div class="welcome-avatar">🤖</div>
          <h3>${escHtml(AGENT_NAME)}</h3>
          <p>${escHtml(WELCOME_MSG)}</p>
          <div class="quick-prompts" id="quick-prompts"></div>
        </div>
      </div>

      <div class="widget-input-area">
        <div class="input-row">
          <textarea
            id="widget-input"
            placeholder="Ask a question..."
            rows="1"
            aria-label="Type your message"
          ></textarea>
          <button id="widget-send" aria-label="Send message">
            <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
          </button>
        </div>
        <div class="widget-footer-text">Powered by <a href="#" target="_blank">AI Support Agent</a></div>
      </div>`;

    document.body.appendChild(launcher);
    document.body.appendChild(widget);

    // Wire up events
    widget.querySelector('.widget-close').addEventListener('click', toggleWidget);
    document.getElementById('widget-send').addEventListener('click', sendMessage);
    const inputEl = document.getElementById('widget-input');
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    inputEl.addEventListener('input', () => autoResize(inputEl));

    // Quick prompt buttons
    const promptsContainer = document.getElementById('quick-prompts');
    QUICK_PROMPTS.forEach((prompt) => {
      const btn = document.createElement('button');
      btn.className = 'quick-prompt';
      btn.textContent = prompt;
      btn.addEventListener('click', () => {
        clearWelcome();
        _sendWithText(prompt);
      });
      promptsContainer.appendChild(btn);
    });

    // Show notification dot after 3s to grab attention
    setTimeout(() => {
      launcher.querySelector('.notif-dot').style.display = 'block';
    }, 3000);
  }

  // ── Toggle ──────────────────────────────────────────────────────────────────

  function toggleWidget() {
    isOpen = !isOpen;
    const widget = document.getElementById('ai-support-widget');
    widget.classList.toggle('open', isOpen);
    if (isOpen) {
      document.getElementById('ai-support-launcher').querySelector('.notif-dot').style.display = 'none';
      document.getElementById('widget-input').focus();
    }
  }

  // ── Send message ────────────────────────────────────────────────────────────

  function sendMessage() {
    const input = document.getElementById('widget-input');
    const text = input.value.trim();
    if (!text) return;

    clearWelcome();
    input.value = '';
    autoResize(input);
    _sendWithText(text);
  }

  async function _sendWithText(text) {
    appendMessage('user', text);

    const sendBtn = document.getElementById('widget-send');
    sendBtn.disabled = true;
    document.getElementById('widget-input').disabled = true;

    const typingId = showTyping();

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: SESSION_ID, agent_id: AGENT_ID }),
      });

      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();

      removeTyping(typingId);
      appendBotMessage(data.answer, data.sources || [], data.escalate || false);
    } catch (err) {
      removeTyping(typingId);
      appendBotMessage("I'm having trouble connecting right now. Please try again in a moment.", [], false);
    } finally {
      sendBtn.disabled = false;
      document.getElementById('widget-input').disabled = false;
      document.getElementById('widget-input').focus();
    }
  }

  // ── Render helpers ──────────────────────────────────────────────────────────

  function appendMessage(role, text) {
    const container = document.getElementById('widget-messages');
    const msgEl = document.createElement('div');
    msgEl.className = `msg ${role}`;
    msgEl.innerHTML = `
      <div class="msg-bubble">${role === 'bot' ? renderMarkdown(text) : escHtml(text)}</div>
      <span class="msg-time">${_now()}</span>`;
    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;
    return msgEl;
  }

  function appendBotMessage(text, sources, escalate) {
    const idx = ++msgCount;
    const container = document.getElementById('widget-messages');
    const msgEl = document.createElement('div');
    msgEl.className = 'msg bot';

    let sourcesHtml = '';
    if (sources.length) {
      const links = sources.map(s => `<a class="source-link" href="${escHtml(s)}" target="_blank">🔗 Source</a>`).join('');
      sourcesHtml = `<div class="msg-sources">${links}</div>`;
    }

    let escalateHtml = '';
    if (escalate) {
      escalateHtml = `<div class="escalation-banner">⚠️ This might need human attention. <a href="mailto:support@example.com">Contact support →</a></div>`;
    }

    msgEl.innerHTML = `
      <div class="msg-bubble">${renderMarkdown(text)}</div>
      ${sourcesHtml}
      ${escalateHtml}
      <div class="msg-feedback">
        <button class="fb-btn" data-idx="${idx}" data-rating="1" title="Helpful">👍</button>
        <button class="fb-btn" data-idx="${idx}" data-rating="-1" title="Not helpful">👎</button>
      </div>
      <span class="msg-time">${_now()}</span>`;

    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;

    // Feedback click handlers
    msgEl.querySelectorAll('.fb-btn').forEach(btn => {
      btn.addEventListener('click', () => sendFeedback(btn, idx, parseInt(btn.dataset.rating)));
    });
  }

  async function sendFeedback(btn, idx, rating) {
    btn.parentElement.querySelectorAll('.fb-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    await fetch(`${API_BASE}/api/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: SESSION_ID, message_index: idx, rating }),
    }).catch(() => {});
  }

  function showTyping() {
    const container = document.getElementById('widget-messages');
    const el = document.createElement('div');
    el.className = 'msg bot';
    const id = `typing-${Date.now()}`;
    el.id = id;
    el.innerHTML = `
      <div class="msg-bubble">
        <div class="typing-indicator">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>`;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
    return id;
  }

  function removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function clearWelcome() {
    const welcome = document.querySelector('.widget-welcome');
    if (welcome) welcome.remove();
  }

  // ── Utilities ───────────────────────────────────────────────────────────────

  function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Minimal markdown: bold, inline code, lists
  function renderMarkdown(text) {
    return escHtml(text)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/^- (.+)/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
      .replace(/\n/g, '<br>');
  }

  function _now() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function _getOrCreateSession() {
    const key = `ai_support_session_${AGENT_ID}`;
    let id = sessionStorage.getItem(key);
    if (!id) { id = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2); sessionStorage.setItem(key, id); }
    return id;
  }

  function injectCSS() {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `${CONFIG.cssBase || ''}/css/widget.css`;
    document.head.appendChild(link);
  }

  // ── Init ────────────────────────────────────────────────────────────────────

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildWidget);
  } else {
    buildWidget();
  }
})();
