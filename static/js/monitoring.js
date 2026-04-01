/**
 * monitoring.js — Live monitoring page SSE consumer
 * Hardened: null-safe DOM access, reconnect UI, nudge feedback toast.
 */

const EMOTION_EMOJI = { neutral:'😐', happy:'😊', confused:'😕', bored:'😴', stressed:'😰', distracted:'🤔' };
const STATE_CLASS   = { attentive:'badge-attentive', distracted:'badge-distracted', sleeping:'badge-sleeping', absent:'badge-absent' };
const COG_CLASS     = { low:'badge-low', optimal:'badge-optimal', high:'badge-high' };

// ── Utilities ──────────────────────────────────────────────────────────────
function el(id) { return document.getElementById(id); }
function set(id, val) { const e = el(id); if (e) e.textContent = val; }
function setClass(id, cls) { const e = el(id); if (e) e.className = `badge ${cls}`; }

// ── SSE Status ─────────────────────────────────────────────────────────────
function setSSEStatus(state) {
  const dot   = el('sse-dot');
  const label = el('sse-label');
  if (!dot || !label) return;
  if (state === 'live') {
    dot.style.background   = '#10b981';
    dot.style.boxShadow    = '0 0 8px #10b981';
    label.textContent      = '🟢 Live';
  } else if (state === 'reconnecting') {
    dot.style.background   = '#f59e0b';
    dot.style.boxShadow    = '0 0 8px #f59e0b';
    label.textContent      = '🔴 Reconnecting…';
  } else {
    dot.style.background   = '#6b7280';
    dot.style.boxShadow    = 'none';
    label.textContent      = 'Connecting…';
  }
}

// ── Nudge Toast ────────────────────────────────────────────────────────────
function showNudgeToast(msg, ok) {
  const toast = el('nudge-toast');
  if (!toast) return;
  toast.textContent       = ok ? `⚡ ${msg}` : `❌ ${msg}`;
  toast.style.background  = ok ? '#10b981' : '#ef4444';
  toast.style.display     = 'block';
  toast.style.opacity     = '1';
  setTimeout(() => { toast.style.opacity = '0'; }, 2500);
  setTimeout(() => { toast.style.display = 'none'; toast.style.opacity = '1'; }, 2900);
}

// ── Card Update ────────────────────────────────────────────────────────────
function updateCard(d) {
  const card = el(`mcard-${d.student_id}`);
  if (!card) return;

  card.className = `monitor-card state-${d.attention_state}`;

  // Attention
  set(`matt-${d.student_id}`, d.attention_score + '%');
  const attBar = el(`matt-bar-${d.student_id}`);
  if (attBar) attBar.style.width = d.attention_score + '%';

  // Cognitive
  set(`mcog-${d.student_id}`, d.cognitive_load + '%');
  const cogBar = el(`mcog-bar-${d.student_id}`);
  if (cogBar) cogBar.style.width = d.cognitive_load + '%';

  // Attention state badge
  const stateEl = el(`mstate-${d.student_id}`);
  if (stateEl) {
    stateEl.className = `badge ${STATE_CLASS[d.attention_state] || ''}`;
    stateEl.textContent = d.is_present ? d.attention_state : 'AWAY';
    if (!d.is_present) stateEl.className = 'badge badge-danger';
  }

  // Cognitive state badge
  const cogStateEl = el(`mcogstate-${d.student_id}`);
  if (cogStateEl) {
    cogStateEl.className = `badge ${COG_CLASS[d.cognitive_state] || ''}`;
    cogStateEl.textContent = 'Load: ' + d.cognitive_state;
  }

  // Meta
  set(`memotion-${d.student_id}`, (EMOTION_EMOJI[d.emotion] || '😐') + ' ' + d.emotion);
  set(`mblink-${d.student_id}`,   d.blink_rate + '/min');
  set(`mpose-${d.student_id}`,    d.head_pose);
}

// ── Summary Update ─────────────────────────────────────────────────────────
function updateSummary(summary) {
  if (!summary || !Object.keys(summary).length) return;
  set('m-avg-att',    (summary.avg_attention      || 0) + '%');
  set('m-avg-cog',    (summary.avg_cognitive_load || 0) + '%');
  set('m-engagement', (summary.engagement_index   || 0) + '%');
  const sc = summary.state_counts || {};
  set('m-attentive',  sc.attentive || 0);
  set('m-distracted', (sc.distracted || 0) + (sc.sleeping || 0) + (sc.absent || 0));
}

// ── Nudge ──────────────────────────────────────────────────────────────────
function nudgeStudent(sid) {
  if (!confirm('Send a focus nudge to this student?')) return;
  const sessionId = document.body.dataset.sessionId;
  if (!sessionId || sessionId === '0') {
    showNudgeToast('No active session — cannot send nudge', false);
    return;
  }
  fetch(`/classroom/${sessionId}/signal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: 'nudge', student_id: sid, message: 'Please focus!' })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showNudgeToast('Nudge sent!', true);
    } else {
      showNudgeToast(data.error || 'Failed to send nudge', false);
    }
  })
  .catch(() => showNudgeToast('Network error — nudge not sent', false));
}

// ── SSE Stream ─────────────────────────────────────────────────────────────
function startMonitorStream() {
  const sessionId = document.body.dataset.sessionId;
  const url = sessionId && sessionId !== '0'
    ? `/api/monitoring/stream?session_id=${sessionId}`
    : '/api/monitoring/stream';

  setSSEStatus('connecting');
  const es = new EventSource(url);

  es.onopen = () => setSSEStatus('live');

  es.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data);
      if (payload.error) { console.warn('Monitor SSE error payload:', payload.error); return; }
      setSSEStatus('live');
      updateSummary(payload.summary);
      (payload.students || []).forEach(updateCard);
    } catch (err) {
      console.warn('Monitor SSE parse error', err);
    }
  };

  es.onerror = () => {
    setSSEStatus('reconnecting');
    es.close();
    setTimeout(startMonitorStream, 5000);
  };
}

document.addEventListener('DOMContentLoaded', startMonitorStream);

// ── Screen Share ───────────────────────────────────────────────────────────
let screenStream = null;
let screenCaptureInterval = null;

async function toggleScreenShare() {
  const btn = el('screenShareBtn');
  if (screenStream) {
    screenStream.getTracks().forEach(track => track.stop());
    screenStream = null;
    clearInterval(screenCaptureInterval);
    if (btn) { btn.textContent = 'Share Screen 🖥️'; btn.className = 'btn btn-primary'; }
    fetch('/api/upload_screen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: null })
    }).catch(() => {});
    return;
  }

  try {
    screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
    if (btn) { btn.textContent = 'Stop Sharing ⏹️'; btn.className = 'btn btn-danger'; }

    const video = document.createElement('video');
    video.srcObject = screenStream;
    video.play();

    const canvas = document.createElement('canvas');
    const ctx    = canvas.getContext('2d');

    screenCaptureInterval = setInterval(async () => {
      if (!screenStream) return;
      canvas.width  = 640;
      canvas.height = (video.videoHeight / video.videoWidth) * canvas.width || 360;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.6);
      fetch('/api/upload_screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: dataUrl })
      }).catch(() => {});
    }, 200); // 5 FPS

    screenStream.getVideoTracks()[0].onended = () => {
      if (screenStream) toggleScreenShare();
    };
  } catch (err) {
    console.error('Screen share error:', err);
    alert('Failed to share screen. Please allow screen capture permissions.');
    screenStream = null;
  }
}
