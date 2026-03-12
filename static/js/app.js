/*
  MyTeam360 — Shared Application JavaScript
  © 2026 Praxis Holdings LLC. PROPRIETARY AND CONFIDENTIAL.
*/

const MT360 = {
  // ═══ SIDEBAR TOGGLE ═══
  initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');
    if (!sidebar || !toggle) return;

    const saved = localStorage.getItem('mt360_sidebar');
    if (saved === 'collapsed') sidebar.classList.add('collapsed');

    toggle.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      localStorage.setItem('mt360_sidebar', sidebar.classList.contains('collapsed') ? 'collapsed' : 'expanded');
    });
  },

  // ═══ VOICE CAPTURE ═══
  recording: false,

  initVoice() {
    const fab = document.getElementById('voiceFab');
    if (!fab) return;
    fab.addEventListener('click', () => {
      if (!MT360.recording) {
        MT360.recording = true;
        fab.classList.add('recording');
        document.getElementById('voiceOverlay').classList.add('active');
        MT360.startListening();
      }
    });
  },

  closeVoice() {
    MT360.recording = false;
    const fab = document.getElementById('voiceFab');
    if (fab) fab.classList.remove('recording');
    const overlay = document.getElementById('voiceOverlay');
    if (overlay) overlay.classList.remove('active');
    document.getElementById('voiceResults').style.display = 'none';
    document.getElementById('voiceDone').style.display = 'none';
    document.getElementById('voiceText').textContent = 'Listening...';
    document.getElementById('voiceSub').textContent = 'Speak naturally. Say anything.';
  },

  startListening() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      document.getElementById('voiceText').textContent = 'Voice not supported';
      document.getElementById('voiceSub').textContent = 'Try Chrome or Edge';
      return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.continuous = false; rec.interimResults = true; rec.lang = 'en-US';
    rec.onresult = (e) => {
      const t = Array.from(e.results).map(r => r[0].transcript).join('');
      document.getElementById('voiceText').textContent = t || 'Listening...';
      if (e.results[0].isFinal) MT360.processVoice(t);
    };
    rec.onerror = () => {
      document.getElementById('voiceText').textContent = 'Could not hear you';
      document.getElementById('voiceSub').textContent = 'Tap the mic to try again';
    };
    rec.onend = () => { document.getElementById('voiceFab').classList.remove('recording'); };
    rec.start();
  },

  processVoice(text) {
    document.getElementById('voiceSub').textContent = 'Processing...';
    fetch('/api/voice/capture', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    })
    .then(r => r.json())
    .then(data => {
      const results = document.getElementById('voiceResults');
      results.innerHTML = '';
      if (data.actions) {
        data.actions.forEach(a => {
          const d = document.createElement('div');
          d.className = 'voice-result tag-' + (a.color || 'green');
          d.textContent = (a.icon || '✓') + ' ' + a.label;
          results.appendChild(d);
        });
      }
      results.style.display = 'grid';
      document.getElementById('voiceDone').style.display = 'inline-flex';
      document.getElementById('voiceSub').textContent = (data.actions?.length || 0) + ' actions captured';
      MT360.toast('Voice captured successfully', 'success');
    })
    .catch(() => {
      document.getElementById('voiceSub').textContent = 'Captured — will process when online';
      document.getElementById('voiceDone').style.display = 'inline-flex';
    });
  },

  // ═══ TOAST NOTIFICATIONS ═══
  toast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || icons.info}</span>
      <span>${message}</span>
      <span class="toast-close" onclick="this.parentElement.remove()">✕</span>
    `;
    container.appendChild(toast);
    setTimeout(() => { if (toast.parentElement) toast.remove(); }, duration);
  },

  // ═══ KEYBOARD SHORTCUTS ═══
  initKeyboard() {
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const search = document.getElementById('searchTrigger');
        if (search) search.click();
      }
      if (e.key === 'Escape' && MT360.recording) MT360.closeVoice();
    });
  },

  // ═══ TASK CHECKBOXES ═══
  initTaskChecks() {
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('task-check')) {
        e.target.classList.toggle('done');
        e.target.textContent = e.target.classList.contains('done') ? '✓' : '';
        const text = e.target.nextElementSibling;
        if (text) text.classList.toggle('done');
        if (e.target.classList.contains('done')) {
          MT360.toast('Task completed', 'success');
        }
      }
    });
  },

  // ═══ MODAL HELPERS ═══
  openModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.add('active');
  },
  closeModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.remove('active');
  },

  // ═══ SLIDE PANEL ═══
  openPanel(id) {
    const p = document.getElementById(id);
    if (p) p.classList.add('open');
  },
  closePanel(id) {
    const p = document.getElementById(id);
    if (p) p.classList.remove('open');
  },

  // ═══ TABS ═══
  initTabs() {
    document.querySelectorAll('[data-tab-group]').forEach(group => {
      const tabs = group.querySelectorAll('[data-tab]');
      tabs.forEach(tab => {
        tab.addEventListener('click', () => {
          const target = tab.dataset.tab;
          const groupId = group.dataset.tabGroup;
          tabs.forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          document.querySelectorAll(`[data-tab-content="${groupId}"]`).forEach(c => {
            c.style.display = c.dataset.tabPanel === target ? '' : 'none';
          });
        });
      });
    });
  },

  // ═══ FILTER CHIPS ═══
  initFilters() {
    document.querySelectorAll('.filter-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        chip.classList.toggle('active');
      });
    });
  },

  // ═══ INIT ═══
  init() {
    MT360.initSidebar();
    MT360.initVoice();
    MT360.initKeyboard();
    MT360.initTaskChecks();
    MT360.initTabs();
    MT360.initFilters();
  }
};

document.addEventListener('DOMContentLoaded', MT360.init);
