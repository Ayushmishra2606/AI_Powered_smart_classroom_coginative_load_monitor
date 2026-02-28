/**
 * monitoring.js — Live monitoring page SSE consumer
 */

const EMOTION_EMOJI = { neutral:'😐', happy:'😊', confused:'😕', bored:'😴', stressed:'😰', distracted:'🤔' };
const STATE_CLASS = { attentive:'badge-attentive', distracted:'badge-distracted', sleeping:'badge-sleeping', absent:'badge-absent' };
const COG_CLASS   = { low:'badge-low', optimal:'badge-optimal', high:'badge-high' };

function updateCard(d) {
  const card = document.getElementById(`mcard-${d.student_id}`);
  if (!card) return;

  // Update card border class
  card.className = `monitor-card state-${d.attention_state}`;

  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  const setClass = (id, cls) => { const el = document.getElementById(id); if (el) el.className = `badge ${cls}`; };

  // Attention
  document.getElementById(`matt-${d.student_id}`).textContent = d.attention_score + '%';
  document.getElementById(`matt-bar-${d.student_id}`).style.width = d.attention_score + '%';

  // Cognitive
  document.getElementById(`mcog-${d.student_id}`).textContent = d.cognitive_load + '%';
  document.getElementById(`mcog-bar-${d.student_id}`).style.width = d.cognitive_load + '%';

  // State badges
  const stateEl = document.getElementById(`mstate-${d.student_id}`);
  if (stateEl) { stateEl.className = `badge ${STATE_CLASS[d.attention_state] || ''}`; stateEl.textContent = d.attention_state; }

  const cogStateEl = document.getElementById(`mcogstate-${d.student_id}`);
  if (cogStateEl) { cogStateEl.className = `badge ${COG_CLASS[d.cognitive_state] || ''}`; cogStateEl.textContent = 'Load: ' + d.cognitive_state; }

  // Meta
  set(`memotion-${d.student_id}`, (EMOTION_EMOJI[d.emotion] || '😐') + ' ' + d.emotion);
  set(`mblink-${d.student_id}`, d.blink_rate + '/min');
  set(`mpose-${d.student_id}`, d.head_pose);
}

function updateSummary(summary) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  if (!summary || !Object.keys(summary).length) return;
  set('m-avg-att', summary.avg_attention + '%');
  set('m-avg-cog', summary.avg_cognitive_load + '%');
  const sc = summary.state_counts || {};
  set('m-attentive', sc.attentive || 0);
  set('m-distracted', (sc.distracted || 0) + (sc.sleeping || 0) + (sc.absent || 0));
}

function startMonitorStream() {
  const es = new EventSource('/api/monitoring/stream');
  es.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data);
      updateSummary(payload.summary);
      (payload.students || []).forEach(updateCard);
    } catch (err) {
      console.warn('Monitor SSE error', err);
    }
  };
  es.onerror = () => { es.close(); setTimeout(startMonitorStream, 5000); };
}

document.addEventListener('DOMContentLoaded', startMonitorStream);
