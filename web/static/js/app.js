/* ROBODİ Dashboard - Global JS */

// Saat güncelle
function updateDateTime() {
  const el = document.getElementById('datetime');
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleString('tr-TR', {
    weekday: 'short', hour: '2-digit', minute: '2-digit'
  });
}
updateDateTime();
setInterval(updateDateTime, 1000);

// Toast bildirimi
function showToast(message, duration = 3000) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100px)';
    toast.style.transition = 'all 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// Durum güncelle (global)
async function updateRobotStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();

    const dot = document.querySelector('.status-dot');
    const text = document.querySelector('.status-text');
    const currentUser = document.getElementById('currentUser');

    if (dot && text) {
      if (d.running) {
        dot.className = 'status-dot online';
        text.textContent = 'Çevrimiçi';
      } else {
        dot.className = 'status-dot offline';
        text.textContent = 'Çevrimdışı';
      }
    }

    if (currentUser && d.current_user) {
      currentUser.textContent = '👤 ' + d.current_user;
    }
  } catch(e) {
    const dot = document.querySelector('.status-dot');
    if (dot) dot.className = 'status-dot offline';
  }
}

updateRobotStatus();
setInterval(updateRobotStatus, 5000);
