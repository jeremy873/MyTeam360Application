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
    fetch('/api/capture', {
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
        MT360.openCmd();
      }
      if (e.key === 'Escape') {
        if (MT360.recording) MT360.closeVoice();
        MT360.closeCmd();
      }
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

  // ═══ API HELPER ═══
  async api(url, opts = {}) {
    try {
      let body = undefined;
      if (opts.body !== undefined && opts.body !== null) {
        body = typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body);
      }
      const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
        body,
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return await res.json();
    } catch (err) {
      MT360.toast(err.message || 'Request failed', 'error');
      throw err;
    }
  },

  // ═══ COMMAND PALETTE ═══
  initCmd() {
    const palette = document.getElementById('cmdPalette');
    const input = document.getElementById('cmdInput');
    if (!palette || !input) return;

    input.addEventListener('input', () => {
      const query = input.value.toLowerCase();
      const items = palette.querySelectorAll('.cmd-item');
      let firstVisible = null;
      items.forEach(item => {
        const match = item.textContent.toLowerCase().includes(query);
        item.style.display = match ? '' : 'none';
        item.classList.remove('highlight');
        if (match && !firstVisible) firstVisible = item;
      });
      if (firstVisible) firstVisible.classList.add('highlight');
    });

    input.addEventListener('keydown', (e) => {
      const items = Array.from(palette.querySelectorAll('.cmd-item')).filter(i => i.style.display !== 'none');
      const current = items.findIndex(i => i.classList.contains('highlight'));

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (current >= 0) items[current].classList.remove('highlight');
        const next = current + 1 < items.length ? current + 1 : 0;
        if (items[next]) items[next].classList.add('highlight');
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (current >= 0) items[current].classList.remove('highlight');
        const prev = current - 1 >= 0 ? current - 1 : items.length - 1;
        if (items[prev]) items[prev].classList.add('highlight');
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const highlighted = palette.querySelector('.cmd-item.highlight');
        if (highlighted) {
          const href = highlighted.dataset.href || highlighted.getAttribute('href');
          if (href) window.location.href = href;
        }
        MT360.closeCmd();
      }
    });

    palette.addEventListener('click', (e) => {
      if (e.target === palette) MT360.closeCmd();
    });
  },

  openCmd() {
    const p = document.getElementById('cmdPalette');
    if (p) { p.classList.add('active'); document.getElementById('cmdInput')?.focus(); }
  },

  closeCmd() {
    const p = document.getElementById('cmdPalette');
    if (p) { p.classList.remove('active'); const inp = document.getElementById('cmdInput'); if (inp) inp.value = ''; }
  },

  // ═══ DRAG-DROP ═══
  initDragDrop() {
    if (!window.Sortable) return;
    document.querySelectorAll('[data-sortable]').forEach(el => {
      new Sortable(el, {
        group: el.dataset.sortable,
        animation: 150,
        ghostClass: 'drag-ghost',
        dragClass: 'drag-active',
        handle: '.drag-handle',
        onEnd: MT360.onDragEnd,
      });
    });
  },

  onDragEnd(evt) {
    const item = evt.item;
    const moveUrl = item?.dataset?.moveUrl;
    if (!moveUrl) return;
    MT360.api(moveUrl, {
      method: 'POST',
      body: {
        from: evt.oldIndex,
        to: evt.newIndex,
        fromColumn: evt.from.dataset.column,
        toColumn: evt.to.dataset.column,
      },
    })
      .then(() => MT360.toast('Item moved', 'success'))
      .catch(() => {});
  },

  // ═══ LOADING SKELETON HELPERS ═══
  showSkeleton(containerId) {
    const el = document.getElementById(containerId);
    if (el) el.classList.add('loading');
  },

  hideSkeleton(containerId) {
    const el = document.getElementById(containerId);
    if (el) el.classList.remove('loading');
  },

  // ═══ DATE RANGE HANDLER ═══
  rangeCallbacks: {},

  initDateRanges() {
    document.querySelectorAll('[data-range-group]').forEach(container => {
      const groupId = container.dataset.rangeGroup;
      container.querySelectorAll('[data-range]').forEach(btn => {
        btn.addEventListener('click', () => {
          container.querySelectorAll('[data-range]').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const value = btn.dataset.range;
          if (MT360.rangeCallbacks[groupId]) {
            MT360.rangeCallbacks[groupId](value);
          }
        });
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
    MT360.initCmd();
    MT360.initDragDrop();
    MT360.initDateRanges();
  }
};

document.addEventListener('DOMContentLoaded', MT360.init);
