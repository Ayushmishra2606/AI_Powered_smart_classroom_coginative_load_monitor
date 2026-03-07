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
  if (stateEl) { 
      stateEl.className = `badge ${STATE_CLASS[d.attention_state] || ''}`; 
      stateEl.textContent = d.is_present ? d.attention_state : 'AWAY';
      if (!d.is_present) stateEl.className = 'badge badge-danger';
  }

  const cogStateEl = document.getElementById(`mcogstate-${d.student_id}`);
  if (cogStateEl) { cogStateEl.className = `badge ${COG_CLASS[d.cognitive_state] || ''}`; cogStateEl.textContent = 'Load: ' + d.cognitive_state; }

  // Meta
  set(`memotion-${d.student_id}`, (EMOTION_EMOJI[d.emotion] || '😐') + ' ' + d.emotion);
  set(`mblink-${d.student_id}`, d.blink_rate + '/min');
  set(`mpose-${d.student_id}`, d.head_pose);
}

function nudgeStudent(sid) {
    if (!confirm('Send a focus nudge to this student?')) return;
    const sessionId = document.body.dataset.sessionId; // Need to set this in live.html
    fetch(`/classroom/${sessionId}/signal`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({type: 'nudge', student_id: sid, message: 'Please focus!'})
    });
}

function updateSummary(summary) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  if (!summary || !Object.keys(summary).length) return;
  set('m-avg-att', (summary.avg_attention || 0) + '%');
  set('m-avg-cog', (summary.avg_cognitive_load || 0) + '%');
  // New Engagement Index
  set('m-engagement', (summary.engagement_index || 0) + '%');
  
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

let screenStream = null;
let screenCaptureInterval = null;

async function toggleScreenShare() {
    const btn = document.getElementById('screenShareBtn');
    
    if (screenStream) {
        // Stop sharing
        screenStream.getTracks().forEach(track => track.stop());
        screenStream = null;
        clearInterval(screenCaptureInterval);
        btn.textContent = 'Share Screen 🖥️';
        btn.className = 'btn btn-primary';
        // Notify server
        fetch('/api/upload_screen', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({image: null}) // Signal stop
        });
        return;
    }

    try {
        screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
        btn.textContent = 'Stop Sharing ⏹️';
        btn.className = 'btn btn-danger';

        const video = document.createElement('video');
        video.srcObject = screenStream;
        video.play();

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        screenCaptureInterval = setInterval(async () => {
            if (!screenStream) return;
            canvas.width = 640; // Reduced for performance
            canvas.height = (video.videoHeight / video.videoWidth) * canvas.width;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.6);
            
            await fetch('/api/upload_screen', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({image: dataUrl})
            });
        }, 200); // 5 FPS

        screenStream.getVideoTracks()[0].onended = () => {
            if (screenStream) toggleScreenShare();
        };

    } catch (err) {
        console.error("Error sharing screen:", err);
        alert("Failed to share screen. Please ensure you have given permissions.");
    }
}
