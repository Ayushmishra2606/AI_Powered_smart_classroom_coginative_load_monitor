/**
 * alerts.js — Alert drawer, toast notifications, and badge updates
 */

let drawerOpen = false;
let lastAlertId = 0;
let isFirstLoad = true;

// Request permission for Desktop Notifications
if ("Notification" in window) {
  if (Notification.permission === "default") {
    // We'll ask when the user first interacts or on load
    document.addEventListener('click', () => {
      if (Notification.permission === "default") Notification.requestPermission();
    }, { once: true });
  }
}

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
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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

      // Check for new alerts to show toasts
      if (!isFirstLoad) {
        alerts.forEach(a => {
          if (a.id > lastAlertId) {
            showToast(a.message, a.severity);
            showDesktopNotification(a.message, a.severity);
          }
        });
      }

      if (alerts.length > 0) {
        lastAlertId = Math.max(...alerts.map(a => a.id));
      }
      isFirstLoad = false;

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
  // We fetch full alerts now to handle toasts/notifications
  loadAlerts();
  
  fetch('/api/alerts/unread-count')
    .then(r => r.json())
    .then(data => {
      const count = data.count;
      ['topbar-alert-count', 'sidebar-alert-count'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
           el.textContent = count;
           el.style.display = count > 0 ? 'flex' : 'none';
        }
      });
    });
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type} fade-in`;
  toast.innerHTML = `<span>${getSeverityIcon(type)}</span><div><div style="font-weight:600;margin-bottom:2px;">${type.toUpperCase()}</div><div>${message}</div></div>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 500);
  }, 5000);
}

function showDesktopNotification(message, type) {
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification("AI Smart Classroom", {
      body: message,
      icon: "/static/img/logo.png" // Fallback if icon exists
    });
  }
}

// Poll alerts every 5s for better real-time feel
setInterval(updateAlertCount, 5000);
document.addEventListener('DOMContentLoaded', updateAlertCount);
