/**
 * alerts.js — Alert drawer, toast notifications, and badge updates
 */

let drawerOpen = false;

function openAlertDrawer() {
  document.getElementById('alertDrawer').classList.add('open');
  document.getElementById('drawerOverlay').style.display = 'block';
  drawerOpen = true;
  loadAlerts();
}

function closeAlertDrawer() {
  document.getElementById('alertDrawer').classList.remove('open');
  document.getElementById('drawerOverlay').style.display = 'none';
  drawerOpen = false;
}

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function loadAlerts() {
  fetch('/api/alerts')
    .then(r => r.json())
    .then(alerts => {
      const list = document.getElementById('alertList');
      if (!alerts.length) {
        list.innerHTML = '<div class="empty-state"><div class="empty-icon">🎉</div><p>No alerts yet</p></div>';
        return;
      }
      list.innerHTML = alerts.map(a => `
        <div class="alert-item ${a.is_read ? '' : a.severity}" id="alert-item-${a.id}">
          <div class="alert-msg">${getSeverityIcon(a.severity)} ${a.message}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
            <span class="alert-time">${formatTime(a.timestamp)}</span>
            ${!a.is_read ? `<button onclick="markRead(${a.id})" class="btn btn-ghost btn-sm" style="padding:2px 8px;font-size:10px;">Dismiss</button>` : ''}
          </div>
        </div>
      `).join('');
    });
}

function getSeverityIcon(sev) {
  return sev === 'critical' ? '🚨' : sev === 'warning' ? '⚠️' : 'ℹ️';
}

function markRead(id) {
  fetch(`/api/alerts/${id}/read`, { method: 'POST' })
    .then(() => { loadAlerts(); updateAlertCount(); });
}

function markAllRead() {
  fetch('/api/alerts/read-all', { method: 'POST' })
    .then(() => { loadAlerts(); updateAlertCount(); });
}

function updateAlertCount() {
  fetch('/api/alerts/unread-count')
    .then(r => r.json())
    .then(data => {
      const count = data.count;
      ['topbar-alert-count', 'sidebar-alert-count'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = count;
      });
    });
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${getSeverityIcon(type)}</span><div><div style="font-weight:600;margin-bottom:2px;">${type.toUpperCase()}</div><div>${message}</div></div>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 5000);
}

// Poll alert count every 10s
setInterval(updateAlertCount, 10000);
document.addEventListener('DOMContentLoaded', updateAlertCount);
