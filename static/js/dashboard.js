/**
 * dashboard.js — Live SSE dashboard updates & Chart.js charts
 */

const EMOTION_EMOJI = {
  neutral: '😐', happy: '😊', confused: '😕',
  bored: '😴', stressed: '😰', distracted: '🤔'
};

const POSE_LABEL = {
  forward: '⬆️ Forward', left: '⬅️ Left',
  right: '➡️ Right', down: '⬇️ Down'
};

// Doughnut charts
let cognitiveChart, attentionChart;

function initCharts() {
  const chartOpts = {
    responsive: true,
    cutout: '72%',
    plugins: { legend: { display: false }, tooltip: { enabled: true } }
  };

  const cogCtx = document.getElementById('cognitiveChart');
  if (cogCtx) {
    cognitiveChart = new Chart(cogCtx, {
      type: 'doughnut',
      data: {
        labels: ['Low', 'Optimal', 'High'],
        datasets: [{ data: [1, 1, 1], backgroundColor: ['#475569', '#10b981', '#ef4444'], borderWidth: 0, hoverOffset: 4 }]
      },
      options: chartOpts
    });
  }

  const attCtx = document.getElementById('attentionChart');
  if (attCtx) {
    attentionChart = new Chart(attCtx, {
      type: 'doughnut',
      data: {
        labels: ['Attentive', 'Distracted', 'Sleeping', 'Absent'],
        datasets: [{ data: [1, 1, 1, 1], backgroundColor: ['#10b981', '#f59e0b', '#8b5cf6', '#ef4444'], borderWidth: 0, hoverOffset: 4 }]
      },
      options: chartOpts
    });
  }
}

function updateStatCard(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function getAttentionBadgeClass(state) {
  const map = { attentive: 'badge-attentive', distracted: 'badge-distracted', sleeping: 'badge-sleeping', absent: 'badge-absent' };
  return 'badge ' + (map[state] || '');
}

function updateStudentRow(id, data) {
  const attVal = document.getElementById(`att-val-${id}`);
  const attBar = document.getElementById(`att-bar-${id}`);
  const cogVal = document.getElementById(`cog-val-${id}`);
  const cogBar = document.getElementById(`cog-bar-${id}`);
  const stateEl = document.getElementById(`att-state-${id}`);
  const emotionEl = document.getElementById(`emotion-${id}`);
  const poseEl = document.getElementById(`pose-${id}`);

  if (attVal) attVal.textContent = data.attention_score + '%';
  if (attBar) attBar.style.width = data.attention_score + '%';
  if (cogVal) cogVal.textContent = data.cognitive_load + '%';
  if (cogBar) cogBar.style.width = data.cognitive_load + '%';
  if (stateEl) { stateEl.className = getAttentionBadgeClass(data.attention_state); stateEl.textContent = data.attention_state; }
  if (emotionEl) emotionEl.textContent = (EMOTION_EMOJI[data.emotion] || '😐') + ' ' + data.emotion;
  if (poseEl) poseEl.textContent = POSE_LABEL[data.head_pose] || data.head_pose;
}

function startLiveStream() {
  const es = new EventSource('/api/dashboard/live');
  es.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data);
      const summary = payload.summary;
      const students = payload.students;

      if (!summary || !Object.keys(summary).length) return;

      // Update stat cards
      updateStatCard('stat-avg-attention', summary.avg_attention + '%');
      updateStatCard('stat-cognitive', summary.avg_cognitive_load + '%');

      const sc = summary.state_counts || {};
      updateStatCard('stat-attentive', sc.attentive || 0);
      updateStatCard('stat-distracted', (sc.distracted || 0) + (sc.sleeping || 0) + (sc.absent || 0));

      const cc = summary.cognitive_counts || {};
      if (cognitiveChart) {
        cognitiveChart.data.datasets[0].data = [cc.low || 0, cc.optimal || 0, cc.high || 0];
        cognitiveChart.update('none');
      }
      if (attentionChart) {
        attentionChart.data.datasets[0].data = [sc.attentive || 0, sc.distracted || 0, sc.sleeping || 0, sc.absent || 0];
        attentionChart.update('none');
      }

      // Update student table rows
      for (const [sid, data] of Object.entries(students)) {
        updateStudentRow(sid, data);
      }
    } catch (err) {
      console.warn('SSE parse error', err);
    }
  };
  es.onerror = () => { es.close(); setTimeout(startLiveStream, 5000); };
}

document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  startLiveStream();
});
