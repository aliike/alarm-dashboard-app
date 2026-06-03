/* ── API Helpers ─────────────────────────────────────────────── */

async function apiGet(path) {
  const res = await fetch('/api' + path);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || body.detail || res.statusText);
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch('/api' + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw new Error(b.error || b.detail || res.statusText);
  }
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch('/api' + path, { method: 'DELETE' });
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw new Error(b.error || b.detail || res.statusText);
  }
  return res.json();
}

/* ── Toast ───────────────────────────────────────────────────── */

function showToast(message, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = 'opacity 0.3s';
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ── Date helpers ────────────────────────────────────────────── */

function formatDateTime(utcString) {
  if (!utcString) return '—';
  const s = utcString.endsWith('Z') ? utcString : utcString + 'Z';
  const date = new Date(s);
  const diffMs = Date.now() - date.getTime();
  const secs  = Math.floor(diffMs / 1000);
  const mins  = Math.floor(secs  / 60);
  const hours = Math.floor(mins  / 60);
  const days  = Math.floor(hours / 24);

  if (secs  < 60)  return 'az önce';
  if (mins  < 60)  return `${mins} dk önce`;
  if (hours < 24)  return `${hours} sa önce`;
  if (days  < 7)   return `${days} gün önce`;
  return date.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDateTimeAbsolute(utcString) {
  if (!utcString) return '—';
  const s = utcString.endsWith('Z') ? utcString : utcString + 'Z';
  const date = new Date(s);
  return date.toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/* ── Badge helpers ───────────────────────────────────────────── */

function stateBadge(state) {
  const map = { ALARM: 'badge-alarm', INSUFFICIENT_DATA: 'badge-insufficient', OK: 'badge-ok' };
  const cls = map[state] || 'badge-pending';
  const label = state === 'INSUFFICIENT_DATA' ? 'INSUF.' : (state || '?');
  return `<span class="badge ${cls}">${label}</span>`;
}

function syncBadge(status) {
  const map = { ok: 'badge-ok', error: 'badge-error', pending: 'badge-pending' };
  return `<span class="badge ${map[status] || 'badge-pending'}">${status || 'pending'}</span>`;
}

/* ── HTML escape ─────────────────────────────────────────────── */

function escHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── Navbar active link ──────────────────────────────────────── */

(function initNavbar() {
  const path = window.location.pathname;
  document.querySelectorAll('.navbar-links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href === path || (href !== '/' && href !== '/index.html' && path.startsWith(href))) {
      a.classList.add('active');
    } else if ((href === '/' || href === '/index.html') && (path === '/' || path === '/index.html')) {
      a.classList.add('active');
    }
  });
})();

/* ── Code copy buttons ───────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.code-wrap').forEach(wrap => {
    const btn = wrap.querySelector('.code-copy-btn');
    const block = wrap.querySelector('.code-block');
    if (!btn || !block) return;
    btn.addEventListener('click', () => {
      const text = block.textContent.trim();
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = 'Copy'; }, 1800);
      });
    });
  });
});
