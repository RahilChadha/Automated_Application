/* ═══════════════════════════════════════════════════════════════════════════
   AutoApply — Frontend (Material Design 3 · White/Purple/Yellow)
   ═══════════════════════════════════════════════════════════════════════════ */

// ── API helpers ──────────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Request failed');
  return json;
}
const GET  = p     => api('GET',    p);
const POST = (p,b) => api('POST',   p, b);
const PUT  = (p,b) => api('PUT',    p, b);
const DEL  = p     => api('DELETE', p);

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
}

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_LABELS = {
  to_apply:'To Apply', applied:'Applied',
  round_1:'Round 1', round_2:'Round 2', round_3:'Round 3', offer:'Offer',
};

const STAGE_CHIPS = {
  to_apply: 'chip-primary',
  applied:  'chip-success',
  round_1:  'chip-round1',
  round_2:  'chip-round2',
  round_3:  'chip-round3',
  offer:    'chip-offer',
};

function statusChip(status) {
  const cls = STAGE_CHIPS[status] || 'chip-surface';
  return `<span class="chip ${cls}">${STATUS_LABELS[status] || status}</span>`;
}

// ── Modal helpers ─────────────────────────────────────────────────────────────

function openModal(id)  { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

document.querySelectorAll('.modal-close, [data-modal]').forEach(el => {
  el.addEventListener('click', () => {
    const m = el.dataset.modal || el.closest('.modal')?.id;
    if (m) closeModal(m);
  });
});
document.querySelectorAll('.modal').forEach(m => {
  m.addEventListener('click', e => { if (e.target === m) closeModal(m.id); });
});

// ── Navigation ────────────────────────────────────────────────────────────────

const navItems = document.querySelectorAll('.nav-item[data-tab]');
const tabs     = document.querySelectorAll('.tab');

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const tab = item.dataset.tab;
    navItems.forEach(i => i.classList.remove('active'));
    tabs.forEach(t => { t.classList.remove('active'); t.classList.add('hidden'); });
    item.classList.add('active');
    const sec = document.getElementById(`tab-${tab}`);
    sec.classList.remove('hidden');
    sec.classList.add('active');
    closeSidebar();
    loadTab(tab);
  });
});

function loadTab(tab) {
  if (tab === 'overview') loadOverview();
  else if (tab === 'jobs') loadJobs();
  else if (tab === 'resume') loadResume();
  else if (tab === 'setup') loadSetup();
}

// ── Sidebar (mobile) ──────────────────────────────────────────────────────────

const navRail = document.getElementById('navRail');
const scrim   = document.getElementById('scrim');

document.getElementById('hamburgerBtn').addEventListener('click', () => {
  navRail.classList.add('open');
  scrim.classList.remove('hidden');
});
scrim.addEventListener('click', closeSidebar);
function closeSidebar() {
  navRail.classList.remove('open');
  scrim.classList.add('hidden');
}

// ── Notification drawer ───────────────────────────────────────────────────────

const notifDrawer = document.getElementById('notifDrawer');

function toggleNotifDrawer() {
  const open = !notifDrawer.classList.contains('hidden');
  if (open) {
    notifDrawer.classList.add('hidden');
    scrim.classList.add('hidden');
  } else {
    notifDrawer.classList.remove('hidden');
    scrim.classList.remove('hidden');
    loadNotifications();
  }
}

document.getElementById('notifBtn').addEventListener('click', toggleNotifDrawer);
document.getElementById('notifBtnMobile').addEventListener('click', toggleNotifDrawer);
document.getElementById('markAllReadBtn').addEventListener('click', async () => {
  await PUT('/api/notifications/read-all');
  refreshBadge();
  loadNotifications();
});
document.getElementById('markAllReadBtn2').addEventListener('click', async () => {
  await PUT('/api/notifications/read-all');
  refreshBadge();
  loadNotifFull();
});

async function refreshBadge() {
  const data = await GET('/api/notifications');
  const count = data.unread;
  [document.getElementById('notifBadge'), document.getElementById('notifBadgeMobile')].forEach(el => {
    if (count > 0) { el.textContent = count > 99 ? '99+' : count; el.classList.remove('hidden'); }
    else el.classList.add('hidden');
  });
}

async function loadNotifications() {
  const data = await GET('/api/notifications');
  renderNotifItems(document.getElementById('notifList'), data.notifications.slice(0, 25));
  refreshBadge();
}

async function loadNotifFull() {
  const data = await GET('/api/notifications');
  renderNotifItems(document.getElementById('notifListFull'), data.notifications);
}

function renderNotifItems(container, items) {
  if (!items.length) { container.innerHTML = '<p class="empty-state">No notifications yet.</p>'; return; }
  container.innerHTML = items.map(n => `
    <div class="notif-item ${n.type} ${n.read ? 'read' : ''}" data-id="${n.id}">
      <div class="ni-title">${esc(n.title)}</div>
      <div class="ni-msg">${esc(n.message)}</div>
      <div class="ni-time">${fmtDate(n.created_at)}</div>
    </div>`).join('');
  container.querySelectorAll('.notif-item').forEach(el => {
    el.addEventListener('click', async () => {
      await PUT(`/api/notifications/${el.dataset.id}/read`);
      el.classList.add('read');
      refreshBadge();
    });
  });
}

setInterval(refreshBadge, 30000);
refreshBadge();

// ── Setup sub-tabs ────────────────────────────────────────────────────────────

document.querySelectorAll('.setup-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.setup-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.setup-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`setup-${btn.dataset.setup}`).classList.add('active');
    if (btn.dataset.setup === 'notifications') loadNotifFull();
    if (btn.dataset.setup === 'passwords') { loadLoginCreds(); loadAccountCreds(); }
    if (btn.dataset.setup === 'questions') loadProfile();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// OVERVIEW
// ═════════════════════════════════════════════════════════════════════════════

async function loadOverview() {
  const data = await GET('/api/overview');
  const p = data.pipeline;

  document.getElementById('statsRow').innerHTML = `
    <div class="stat-card"><div class="stat-value">${data.total_jobs}</div><div class="stat-label">Total</div></div>
    <div class="stat-card"><div class="stat-value">${p.to_apply||0}</div><div class="stat-label">To Apply</div></div>
    <div class="stat-card"><div class="stat-value">${p.applied||0}</div><div class="stat-label">Applied</div></div>
    <div class="stat-card"><div class="stat-value">${p.offer||0}</div><div class="stat-label">Offers</div></div>
    <div class="stat-card"><div class="stat-value">${data.unread_notifications}</div><div class="stat-label">Alerts</div></div>
  `;

  const stages = [
    ['to_apply','To Apply'],['applied','Applied'],
    ['round_1','Round 1'],['round_2','Round 2'],['round_3','Round 3'],['offer','Offer']
  ];
  document.getElementById('pipelineRow').innerHTML = stages.map(([k, label]) => `
    <div class="pipeline-stage">
      <div class="ps-count">${p[k]||0}</div>
      <div class="ps-label">${label}</div>
    </div>`).join('');

  const actEl = document.getElementById('recentActivity');
  if (!data.recent_activity.length) {
    actEl.innerHTML = '<p class="empty-state">No activity yet. Add a job to get started.</p>';
    return;
  }
  actEl.innerHTML = data.recent_activity.map(j => `
    <div class="activity-item">
      <div class="activity-dot"></div>
      <div class="activity-info">
        <div class="ai-company">${esc(j.company)}</div>
        <div class="ai-title">${esc(j.title)}</div>
      </div>
      <div class="activity-status">${statusChip(j.status)}</div>
    </div>`).join('');
}

// ═════════════════════════════════════════════════════════════════════════════
// JOBS
// ═════════════════════════════════════════════════════════════════════════════

let allJobs = [];

async function loadJobs() {
  allJobs = await GET('/api/jobs');
  renderKanban();
}

function renderKanban(search = '') {
  const q = search.toLowerCase();
  const filtered = q
    ? allJobs.filter(j => j.company.toLowerCase().includes(q) || j.title.toLowerCase().includes(q))
    : allJobs;

  const toApply = filtered.filter(j => j.status === 'to_apply');
  const applied  = filtered.filter(j => j.status !== 'to_apply');

  document.getElementById('count-to_apply').textContent = toApply.length;
  document.getElementById('count-applied').textContent  = applied.length;

  document.getElementById('col-to_apply').innerHTML =
    toApply.length ? toApply.map(jobCard).join('') : '<p class="empty-state" style="font-size:.85rem">No jobs here.</p>';
  document.getElementById('col-applied').innerHTML =
    applied.length ? applied.map(jobCard).join('') : '<p class="empty-state" style="font-size:.85rem">No jobs here.</p>';
}

function jobCard(j) {
  const isApplied = j.status !== 'to_apply';
  const roundBtns = isApplied ? `
    <div class="round-btns">
      ${['applied','round_1','round_2','round_3','offer'].map(s => `
        <button class="round-btn ${j.status===s?'active':''}" onclick="setJobStatus(${j.id},'${s}')">${STATUS_LABELS[s]}</button>
      `).join('')}
    </div>` : '';

  const applyBtn = j.url
    ? `<button class="btn-yellow" onclick="openAutomateModal(${j.id})" title="Auto-apply">
         <span class="material-symbols-outlined" style="font-size:16px">play_circle</span> Apply
       </button>`
    : '';

  return `
    <div class="job-card status-${j.status}">
      <div class="job-card-top">
        <div>
          <div class="job-card-title">${esc(j.title)}</div>
          <div class="job-card-company">${esc(j.company)}</div>
        </div>
        <div class="job-card-actions">
          <button class="icon-btn" onclick="editJob(${j.id})" title="Edit">
            <span class="material-symbols-outlined" style="font-size:18px">edit</span>
          </button>
          <button class="icon-btn danger" onclick="deleteJob(${j.id})" title="Delete">
            <span class="material-symbols-outlined" style="font-size:18px">delete</span>
          </button>
        </div>
      </div>
      <div class="job-card-meta">
        ${statusChip(j.status)}
        ${j.source ? `<span class="chip chip-surface">${esc(j.source)}</span>` : ''}
        ${j.url ? `<a href="${esc(j.url)}" target="_blank" style="font-size:.78rem;color:var(--md-primary)">
            <span class="material-symbols-outlined" style="font-size:14px;vertical-align:middle">open_in_new</span> Posting
          </a>` : ''}
      </div>
      ${roundBtns}
      <div class="job-card-footer">
        ${applyBtn}
        ${j.has_description ? `<span class="chip chip-surface" style="font-size:.72rem">
            <span class="material-symbols-outlined" style="font-size:13px">auto_awesome</span> Resume tailored
          </span>` : ''}
      </div>
    </div>`;
}

document.getElementById('jobSearch').addEventListener('input', e => renderKanban(e.target.value));

async function setJobStatus(jobId, status) {
  await PUT(`/api/jobs/${jobId}`, { status });
  loadJobs();
}

// ── Add Job ───────────────────────────────────────────────────────────────────

document.getElementById('addJobBtn').addEventListener('click', () => {
  resetJobModal();
  document.getElementById('jobModalTitle').textContent = 'Add Job';
  openModal('jobModal');
});

function resetJobModal() {
  ['jobId','jobUrl','jobTitle','jobCompany','jobSource','jobNotesTailoring'].forEach(id => {
    document.getElementById(id).value = '';
  });
  const fs = document.getElementById('fetchStatus');
  fs.textContent = ''; fs.className = 'fetch-status hidden';
}

// URL Fetch
document.getElementById('fetchJobBtn').addEventListener('click', async () => {
  const url = document.getElementById('jobUrl').value.trim();
  if (!url) { alert('Please enter a job posting URL first.'); return; }
  const fs = document.getElementById('fetchStatus');
  fs.className = 'fetch-status loading'; fs.textContent = 'Fetching job details…'; fs.classList.remove('hidden');
  document.getElementById('fetchJobBtn').disabled = true;
  try {
    const data = await POST('/api/jobs/scrape-url', { url });
    if (data.title) document.getElementById('jobTitle').value = data.title;
    if (data.company) document.getElementById('jobCompany').value = data.company;
    if (data.source) document.getElementById('jobSource').value = data.source;
    document.getElementById('fetchJobBtn').dataset.description = data.full_description || '';
    fs.className = 'fetch-status success'; fs.textContent = 'Details fetched! Review and edit below.';
  } catch (e) {
    fs.className = 'fetch-status error'; fs.textContent = `Could not fetch: ${e.message}. Fill in manually.`;
  } finally {
    document.getElementById('fetchJobBtn').disabled = false;
  }
});

async function editJob(id) {
  const j = await GET(`/api/jobs/${id}`);
  document.getElementById('jobId').value       = j.id;
  document.getElementById('jobUrl').value      = j.url || '';
  document.getElementById('jobTitle').value    = j.title || '';
  document.getElementById('jobCompany').value  = j.company || '';
  document.getElementById('jobSource').value   = j.source || '';
  document.getElementById('jobNotesTailoring').value = j.notes_for_tailoring || '';
  document.getElementById('jobModalTitle').textContent = 'Edit Job';
  const fs = document.getElementById('fetchStatus');
  fs.textContent = ''; fs.className = 'fetch-status hidden';
  openModal('jobModal');
}

document.getElementById('saveJobBtn').addEventListener('click', async () => {
  const id = document.getElementById('jobId').value;
  const data = {
    company:              document.getElementById('jobCompany').value.trim(),
    title:                document.getElementById('jobTitle').value.trim(),
    url:                  document.getElementById('jobUrl').value.trim() || null,
    source:               document.getElementById('jobSource').value.trim() || null,
    notes_for_tailoring:  document.getElementById('jobNotesTailoring').value.trim() || null,
    scraped_description:  document.getElementById('fetchJobBtn').dataset.description || null,
  };
  if (!data.company || !data.title) { alert('Company and title are required.'); return; }
  try {
    if (id) await PUT(`/api/jobs/${id}`, data);
    else    await POST('/api/jobs', data);
    closeModal('jobModal');
    document.getElementById('fetchJobBtn').dataset.description = '';
    loadJobs();
  } catch(e) { alert(e.message); }
});

async function deleteJob(id) {
  if (!confirm('Delete this job?')) return;
  await DEL(`/api/jobs/${id}`);
  loadJobs();
}

// ── Automate ──────────────────────────────────────────────────────────────────

async function openAutomateModal(jobId) {
  document.getElementById('automateJobId').value = jobId;

  // Load login credentials
  const lcs = await GET('/api/login-credentials');
  const lcSel = document.getElementById('automateLoginCred');
  lcSel.innerHTML = lcs.length
    ? lcs.map(c => `<option value="${c.id}">${esc(c.label)} — ${esc(c.email)} (${c.password_count} passwords)</option>`).join('')
    : '<option value="">No login credentials saved</option>';

  // Load account credentials
  const acs = await GET('/api/account-credentials');
  const acSel = document.getElementById('automateAccountCred');
  acSel.innerHTML = '<option value="">— None —</option>' +
    acs.map(a => `<option value="${a.id}">${esc(a.label)} — ${esc(a.email)}</option>`).join('');

  openModal('automateModal');
}

document.getElementById('startAutomateBtn').addEventListener('click', async () => {
  const jobId   = parseInt(document.getElementById('automateJobId').value);
  const lcId    = parseInt(document.getElementById('automateLoginCred').value);
  const acIdVal = document.getElementById('automateAccountCred').value;
  const acId    = acIdVal ? parseInt(acIdVal) : null;

  if (!lcId) { alert('Please select a login credential.'); return; }
  try {
    const res = await POST(`/api/automate/${jobId}`, {
      login_credential_id: lcId,
      account_credential_id: acId,
    });
    closeModal('automateModal');
    alert(res.message || 'Automation started! Watch the Notifications bell for updates.');
    refreshBadge();
  } catch(e) { alert(e.message); }
});

// ═════════════════════════════════════════════════════════════════════════════
// RESUME
// ═════════════════════════════════════════════════════════════════════════════

async function loadResume() {
  const resumes = await GET('/api/resume');
  const base = resumes.find(r => r.is_base);
  const tailored = resumes.filter(r => !r.is_base);

  // Base resume preview
  const preview = document.getElementById('baseResumePreview');
  if (base) {
    preview.textContent = base.content;
    document.getElementById('baseResumeText').value = base.content;
  } else {
    preview.innerHTML = '<p class="empty-state">No base resume saved yet. Click Edit to add yours.</p>';
  }

  // Tailored list
  const listEl = document.getElementById('tailoredList');
  if (!tailored.length) {
    listEl.innerHTML = '<p class="empty-state">Tailored resumes appear here automatically when you add jobs. Make sure your base resume is saved and ANTHROPIC_API_KEY is set.</p>';
    return;
  }
  listEl.innerHTML = tailored.map(r => `
    <div class="tailored-card">
      <div class="tailored-info">
        <div class="t-company">${esc(r.job_company || 'Unknown Company')}</div>
        <div class="t-title">${esc(r.job_title || r.label || 'Tailored Resume')}</div>
        <div class="t-date">${fmtDate(r.created_at)}</div>
      </div>
      <div class="tailored-actions">
        <button class="btn-tonal" onclick="viewResume(${r.id})">
          <span class="material-symbols-outlined" style="font-size:16px">visibility</span> View
        </button>
        <button class="icon-btn danger" onclick="deleteResume(${r.id})" title="Delete">
          <span class="material-symbols-outlined" style="font-size:18px">delete</span>
        </button>
      </div>
    </div>`).join('');
}

// Edit base resume
document.getElementById('editBaseResumeBtn').addEventListener('click', () => openModal('baseResumeModal'));

document.getElementById('saveBaseResumeBtn').addEventListener('click', async () => {
  const content = document.getElementById('baseResumeText').value.trim();
  if (!content) { alert('Please paste your resume first.'); return; }
  try {
    await POST('/api/resume', { content, is_base: true, label: 'Base Resume' });
    closeModal('baseResumeModal');
    loadResume();
  } catch(e) { alert(e.message); }
});

// View tailored resume
async function viewResume(id) {
  const r = await GET(`/api/resume/${id}`);
  document.getElementById('viewResumeTitle').textContent =
    `${r.job_company || ''} — ${r.job_title || 'Tailored Resume'}`.replace(/^—\s*/, '');
  document.getElementById('viewResumeText').value = r.content;
  const summaryEl = document.getElementById('viewResumeSummary');
  if (r.edit_summary) {
    summaryEl.textContent = r.edit_summary;
    summaryEl.classList.remove('hidden');
  } else {
    summaryEl.classList.add('hidden');
  }
  openModal('viewResumeModal');
}

document.getElementById('copyResumeBtn').addEventListener('click', () => {
  const text = document.getElementById('viewResumeText').value;
  navigator.clipboard.writeText(text)
    .then(() => alert('Copied to clipboard!'))
    .catch(() => { document.getElementById('viewResumeText').select(); document.execCommand('copy'); alert('Copied!'); });
});

async function deleteResume(id) {
  if (!confirm('Delete this tailored resume?')) return;
  await DEL(`/api/resume/${id}`);
  loadResume();
}

// Manual tailor
document.getElementById('manualTailorBtn').addEventListener('click', () => {
  ['mtCompany','mtTitle','mtJobDesc','mtNotes'].forEach(id => document.getElementById(id).value = '');
  const ms = document.getElementById('mtStatus'); ms.className='fetch-status hidden'; ms.textContent='';
  openModal('manualTailorModal');
});

document.getElementById('runManualTailorBtn').addEventListener('click', async () => {
  const jd = document.getElementById('mtJobDesc').value.trim();
  if (!jd) { alert('Please paste a job description.'); return; }
  const ms = document.getElementById('mtStatus');
  ms.className = 'fetch-status loading'; ms.textContent = 'Tailoring with Claude AI… this may take 20–30 seconds.'; ms.classList.remove('hidden');
  document.getElementById('runManualTailorBtn').disabled = true;
  try {
    const r = await POST('/api/resume/tailor', {
      job_description: jd,
      notes_for_tailoring: document.getElementById('mtNotes').value.trim() || null,
      job_company: document.getElementById('mtCompany').value.trim() || null,
      job_title:   document.getElementById('mtTitle').value.trim() || null,
    });
    closeModal('manualTailorModal');
    loadResume();
    setTimeout(() => viewResume(r.id), 300);
  } catch(e) {
    ms.className = 'fetch-status error'; ms.textContent = e.message;
  } finally {
    document.getElementById('runManualTailorBtn').disabled = false;
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// JOB SETUP
// ═════════════════════════════════════════════════════════════════════════════

async function loadSetup() {
  loadLoginCreds();
  loadAccountCreds();
}

// ── Login Credentials ─────────────────────────────────────────────────────────

async function loadLoginCreds() {
  const creds = await GET('/api/login-credentials');
  const el = document.getElementById('loginCredList');
  if (!creds.length) {
    el.innerHTML = '<p class="empty-state">No login credentials saved. Add your Workday email and passwords.</p>';
    return;
  }
  el.innerHTML = creds.map(c => `
    <div class="cred-card">
      <div class="cred-info">
        <div class="cred-label">${esc(c.label)}</div>
        <div class="cred-email">${esc(c.email)}</div>
        <div class="cred-meta">Priority ${c.priority} · ${c.password_count} password${c.password_count!==1?'s':''}</div>
      </div>
      <div class="cred-actions">
        <button class="icon-btn" onclick="editLoginCred(${c.id})" title="Edit">
          <span class="material-symbols-outlined" style="font-size:18px">edit</span>
        </button>
        <button class="icon-btn danger" onclick="deleteLoginCred(${c.id})" title="Delete">
          <span class="material-symbols-outlined" style="font-size:18px">delete</span>
        </button>
      </div>
    </div>`).join('');
}

document.getElementById('addLoginCredBtn').addEventListener('click', () => {
  ['loginCredId','lcLabel','lcEmail','lcPasswords'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('lcPriority').value = '0';
  document.getElementById('loginCredModalTitle').textContent = 'Add Login Credential';
  openModal('loginCredModal');
});

async function editLoginCred(id) {
  const creds = await GET('/api/login-credentials');
  const c = creds.find(x => x.id === id);
  if (!c) return;
  document.getElementById('loginCredId').value = c.id;
  document.getElementById('lcLabel').value     = c.label;
  document.getElementById('lcEmail').value     = c.email;
  document.getElementById('lcPriority').value  = c.priority;
  document.getElementById('lcPasswords').value = '';  // passwords are encrypted, user must re-enter to change
  document.getElementById('loginCredModalTitle').textContent = 'Edit Login Credential';
  openModal('loginCredModal');
}

document.getElementById('saveLoginCredBtn').addEventListener('click', async () => {
  const id        = document.getElementById('loginCredId').value;
  const label     = document.getElementById('lcLabel').value.trim();
  const email     = document.getElementById('lcEmail').value.trim();
  const pwRaw     = document.getElementById('lcPasswords').value;
  const priority  = parseInt(document.getElementById('lcPriority').value) || 0;
  const passwords = pwRaw.split('\n').map(p => p.trim()).filter(Boolean);

  if (!label || !email) { alert('Label and email are required.'); return; }
  if (!id && !passwords.length) { alert('Enter at least one password.'); return; }

  try {
    if (id) {
      const upd = { label, email, priority };
      if (passwords.length) upd.passwords = passwords;
      await PUT(`/api/login-credentials/${id}`, upd);
    } else {
      await POST('/api/login-credentials', { label, email, passwords, priority });
    }
    closeModal('loginCredModal');
    loadLoginCreds();
  } catch(e) { alert(e.message); }
});

async function deleteLoginCred(id) {
  if (!confirm('Delete this login credential?')) return;
  await DEL(`/api/login-credentials/${id}`);
  loadLoginCreds();
}

// ── Account Credentials ───────────────────────────────────────────────────────

async function loadAccountCreds() {
  const creds = await GET('/api/account-credentials');
  const el = document.getElementById('accountCredList');
  if (!creds.length) {
    el.innerHTML = '<p class="empty-state">No account setup credential saved. Add the email and password to use when creating a new Workday account.</p>';
    return;
  }
  el.innerHTML = creds.map(a => `
    <div class="cred-card">
      <div class="cred-info">
        <div class="cred-label">${esc(a.label)}</div>
        <div class="cred-email">${esc(a.email)}</div>
      </div>
      <div class="cred-actions">
        <button class="icon-btn" onclick="editAccountCred(${a.id})" title="Edit">
          <span class="material-symbols-outlined" style="font-size:18px">edit</span>
        </button>
        <button class="icon-btn danger" onclick="deleteAccountCred(${a.id})" title="Delete">
          <span class="material-symbols-outlined" style="font-size:18px">delete</span>
        </button>
      </div>
    </div>`).join('');
}

document.getElementById('addAccountCredBtn').addEventListener('click', () => {
  ['accountCredId','acLabel','acEmail','acPassword'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('accountCredModalTitle').textContent = 'Add Account Setup Credential';
  openModal('accountCredModal');
});

async function editAccountCred(id) {
  const creds = await GET('/api/account-credentials');
  const a = creds.find(x => x.id === id);
  if (!a) return;
  document.getElementById('accountCredId').value = a.id;
  document.getElementById('acLabel').value       = a.label;
  document.getElementById('acEmail').value       = a.email;
  document.getElementById('acPassword').value    = '';
  document.getElementById('accountCredModalTitle').textContent = 'Edit Account Setup Credential';
  openModal('accountCredModal');
}

document.getElementById('saveAccountCredBtn').addEventListener('click', async () => {
  const id       = document.getElementById('accountCredId').value;
  const label    = document.getElementById('acLabel').value.trim();
  const email    = document.getElementById('acEmail').value.trim();
  const password = document.getElementById('acPassword').value;

  if (!label || !email) { alert('Label and email are required.'); return; }
  if (!id && !password) { alert('Password is required.'); return; }

  try {
    if (id) {
      const upd = { label, email };
      if (password) upd.password = password;
      await PUT(`/api/account-credentials/${id}`, upd);
    } else {
      await POST('/api/account-credentials', { label, email, password });
    }
    closeModal('accountCredModal');
    loadAccountCreds();
  } catch(e) { alert(e.message); }
});

async function deleteAccountCred(id) {
  if (!confirm('Delete this account credential?')) return;
  await DEL(`/api/account-credentials/${id}`);
  loadAccountCreds();
}

// ── Application Questions ─────────────────────────────────────────────────────

async function loadProfile() {
  const profile = await GET('/api/profile');
  const container = document.getElementById('profileForm');
  container.innerHTML = '';
  Object.entries(profile).forEach(([cat, questions]) => {
    const div = document.createElement('div');
    div.className = 'profile-category';
    div.innerHTML = `<div class="profile-cat-title">${esc(cat)}</div><div class="profile-grid"></div>`;
    const grid = div.querySelector('.profile-grid');
    questions.forEach(q => {
      grid.innerHTML += `
        <div class="text-field">
          <label class="field-label" for="profile_${q.key}">${esc(q.label)}</label>
          <input type="text" class="field-input profile-answer" id="profile_${q.key}"
            data-key="${q.key}" value="${esc(q.answer || '')}"/>
        </div>`;
    });
    container.appendChild(div);
  });
}

document.getElementById('saveProfileBtn').addEventListener('click', async () => {
  const answers = {};
  document.querySelectorAll('.profile-answer').forEach(el => {
    answers[el.dataset.key] = el.value.trim();
  });
  try {
    await PUT('/api/profile', { answers });
    alert('Profile saved!');
  } catch(e) { alert(e.message); }
});

// ═════════════════════════════════════════════════════════════════════════════
// INIT
// ═════════════════════════════════════════════════════════════════════════════

loadOverview();
