document.addEventListener('DOMContentLoaded', () => {
  let ws = new WebSocket(`ws://${window.location.host}/ws`);
  ws.onopen = () => updateStatus('Connected', 'online');
  ws.onclose = () => updateStatus('Disconnected', 'offline');
  ws.onerror = () => updateStatus('Error', 'offline');
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    switch (msg.type) {
      case 'phi_update': updateHud(msg.payload); break;
      case 'wiring_proposal': appendMessage('New self-wiring proposal received.', 'assistant'); break;
      case 'agi_response': appendMessage(msg.payload.answer, 'assistant'); break;
    }
  };
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelector('.nav-tab.active').classList.remove('active');
      tab.classList.add('active');
      document.querySelector('.panel.active').classList.remove('active');
      document.getElementById(`${tab.dataset.panel}Panel`).classList.add('active');
      if (tab.dataset.panel === 'system') {
        loadSystem();
        loadApprovals();
      }
    });
  });
  const chatInput = document.getElementById('chatInput');
  const sendButton = document.getElementById('sendButton');
  const fileEl = document.getElementById('fileUpload');
  const fileNameEl = document.getElementById('fileName');
  sendButton.addEventListener('click', sendChatMessage);
  chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); } });
  if (fileEl) fileEl.addEventListener('change', () => { const f=fileEl.files[0]; if (fileNameEl) fileNameEl.textContent = f ? f.name : ''; });
  async function sendChatMessage(){
    const message = chatInput.value.trim();
    const f = fileEl && fileEl.files[0];
    if (!message && !f) return;
    appendMessage(message || (f ? `[Attached: ${f.name}]` : ''), 'user');
    chatInput.value = '';
    try {
      if (f) {
        const form = new FormData();
        form.append('q', message || 'Document question');
        form.append('file', f);
        const resp = await fetch('/ask_with_document', { method: 'POST', body: form });
        await resp.json();
      } else {
        const response = await fetch('/ask', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ q: message }) });
        await response.json();
      }
    } catch (e) { appendMessage('Error: Request failed', 'system'); }
  }
  async function loadSystem(){ try { const resp = await fetch('/state/summary'); const data = await resp.json(); updateHud(data.self_awareness_metrics); } catch(e) {} }
  async function loadApprovals(){
    try{
      const resp = await fetch('/approvals');
      const approvals = await resp.json();
      const container = document.getElementById('approvalQueue');
      if (!container) return;
      container.innerHTML = '';
      approvals.forEach(item => {
        const div = document.createElement('div');
        div.className = 'approval-item';
        const span = document.createElement('span');
        span.textContent = item.content;
        const actions = document.createElement('div');
        actions.className = 'approval-actions';
        const approveBtn = document.createElement('button');
        approveBtn.className = 'approve';
        approveBtn.textContent = 'Approve';
        approveBtn.addEventListener('click', async () => {
          await fetch(`/approvals/${item.id}/approve`, { method: 'POST' });
          loadApprovals();
        });
        const denyBtn = document.createElement('button');
        denyBtn.className = 'deny';
        denyBtn.textContent = 'Deny';
        denyBtn.addEventListener('click', async () => {
          await fetch(`/approvals/${item.id}/deny`, { method: 'POST' });
          loadApprovals();
        });
        actions.appendChild(approveBtn);
        actions.appendChild(denyBtn);
        div.appendChild(span);
        div.appendChild(actions);
        container.appendChild(div);
      });
    } catch(e) {
      // ignore errors quietly
    }
  }
  function updateStatus(text, klass){ document.getElementById('statusText').textContent = text; const dot = document.querySelector('.status-dot'); dot.className = `status-dot ${klass}`; }
  function appendMessage(content, sender){ const c = document.getElementById('chatMessages'); const msg = document.createElement('div'); msg.className=`message ${sender}`; msg.innerHTML = window.marked.parse(content || "..."); c.appendChild(msg); c.scrollTop = c.scrollHeight; }
  function updateHud(m){ if (!m) return; const phi=document.getElementById('phiValue'); const g=document.getElementById('glyphsValue'); if (phi&&m.phi!==undefined) phi.textContent = (+m.phi).toFixed(4); if (g&&m.glyphs) g.textContent = (m.glyphs||[]).join(' ')||'∅'; }
});
