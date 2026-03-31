// student_dashboard.js — placeholder for future enhancements
// Main chart rendering is inline in the templates using Chart.js
// This file can be used for additional student dashboard JS
console.log('Student dashboard loaded');

document.addEventListener('DOMContentLoaded', () => {
    // Face Upload Form Handler
    const faceForm = document.getElementById('faceUploadForm');
    if (faceForm) {
        faceForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('uploadBtn');
            const statusLabel = document.getElementById('uploadStatus');
            const fileInput = document.getElementById('facePhotoInput');
            
            if (!fileInput.files.length) {
                statusLabel.textContent = 'Please select a photo first.';
                statusLabel.style.color = 'var(--accent-red)';
                return;
            }
            
            btn.disabled = true;
            btn.innerHTML = 'Uploading & Training... <span class="loader" style="width:12px;height:12px;border-bottom:2px solid white;border-right:2px solid white;border-radius:100%;margin-left:8px;display:inline-block;animation:spin 1s linear infinite;"></span>';
            statusLabel.textContent = '';
            
            try {
                const formData = new FormData(faceForm);
                const resp = await fetch('/face-attendance/upload_face', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await resp.json();
                
                if (data.success) {
                    statusLabel.textContent = '✅ ' + data.message;
                    statusLabel.style.color = '#10b981';
                    setTimeout(() => window.location.reload(), 1500);
                } else {
                    statusLabel.textContent = '❌ Error: ' + (data.error || 'Upload failed');
                    statusLabel.style.color = 'var(--accent-red)';
                    btn.disabled = false;
                    btn.textContent = 'Upload & Train Model';
                }
            } catch (err) {
                statusLabel.textContent = '❌ Network error during upload.';
                statusLabel.style.color = 'var(--accent-red)';
                btn.disabled = false;
                btn.textContent = 'Upload & Train Model';
            }
        });
    }
});
