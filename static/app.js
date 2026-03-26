/* ═══════════════════════════════════════════════════════════════════════════
   Job Application Dashboard — Frontend
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
const GET = (p) => api('GET', p);
const POST = (p, b) => api('POST', p, b);
const PUT = (p, b) => api('PUT', p, b);
const DEL = (p) => api('DELETE', p);

// ── Formatting helpers ────────────────────────────────────────────────────────

const STATUS_LABELS = {
  to_apply: 'To Apply', applied: 'Applied', phone_screen: 'Phone Screen',
  interview: 'Interview', offer: 'Offer', rejected: 'Rejected',
  to_reach_out: 'To Reach Out', message_sent: 'Message Sent',
  scheduled: 'Scheduled', completed: 'Completed',
  follow_up: 'Follow Up', no_response: 'No Response',
  to_send: 'To Send', sent: 'Sent', replied: 'Replied',
};

function badge(status) {
  const label = STATUS_LABELS[status] || status;
  return `<span class="badge badge-${status}">${label}</span>`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function relTime(iso) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d === 0) return 'today';
  if (d === 1) return '1 day ago';
  return `${d} days ago`;
}

// ── Tab navigation ────────────────────────────────────────────────────────────

const tabLinks = document.querySelectorAll('.nav-link[data-tab]');
const tabSections = document.querySelectorAll('.tab-section');

tabLinks.forEach(link => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    const tab = link.dataset.tab;
    tabLinks.forEach(l => l.classList.remove('active'));
    tabSections.forEach(s => { s.classList.remove('active'); s.classList.add('hidden'); });
    link.classList.add('active');
    const section = document.getElementById(`tab-${tab}`);
    section.classList.remove('hidden');
    section.classList.add('active');
    closeSidebar();
    loadTab(tab);
  });
});

function loadTab(tab) {
  if (tab === 'overview') loadOverview();
  else if (tab === 'jobs') loadJobs();
  else if (tab === 'coffee') loadCoffeeChats();
  else if (tab === 'email') loadEmails();
  else if (tab === 'resume') loadResume();
  else if (tab === 'setup') loadSetup();
}

// ── Hamburger / Sidebar ───────────────────────────────────────────────────────

const hamburgerBtn = document.getElementById('hamburgerBtn');
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('overlay');

hamburgerBtn.addEventListener('click', () => {
  sidebar.classList.toggle('open');
  overlay.classList.toggle('hidden');
});
overlay.addEventListener('click', closeSidebar);
function closeSidebar() {
  sidebar.classList.remove('open');
  overlay.classList.add('hidden');
}

// ── Notifications ─────────────────────────────────────────────────────────────

const notifBtn = document.getElementById('notifBtn');
const notifPanel = document.getElementById('notifPanel');
const notifBadge = document.getElementById('notifBadge');

notifBtn.addEventListener('click', () => {
  notifPanel.classList.toggle('hidden');
  if (!notifPanel.classList.contains('hidden')) loadNotifications();
});

document.getElementById('markAllReadBtn').addEventListener('click', async () => {
  await PUT('/api/notifications/read-all');
  loadNotifications();
  refreshBadge();
});
document.getElementById('markAllReadBtn2').addEventListener('click', async () => {
  await PUT('/api/notifications/read-all');
  loadNotifFull();
  refreshBadge();
});

async function refreshBadge() {
  const data = await GET('/api/notifications');
  if (data.unread > 0) {
    notifBadge.textContent = data.unread > 99 ? '99+' : data.unread;
    notifBadge.classList.remove('hidden');
  } else {
    notifBadge.classList.add('hidden');
  }
}

async function loadNotifications() {
  const data = await GET('/api/notifications');
  renderNotifList(document.getElementById('notifList'), data.notifications.slice(0, 20));
  refreshBadge();
}

async function loadNotifFull() {
  const data = await GET('/api/notifications');
  renderNotifList(document.getElementById('notifListFull'), data.notifications);
  refreshBadge();
}

function renderNotifList(container, items) {
  if (!items.length) { container.innerHTML = '<p class="empty-state">No notifications yet.</p>'; return; }
  container.innerHTML = items.map(n => `
    <div class="notif-item ${n.type} ${n.read ? 'read' : ''}" data-id="${n.id}">
      <div class="ni-title">${esc(n.title)}</div>
      <div class="ni-msg">${esc(n.message)}</div>
      <div class="ni-time">${fmtDate(n.created_at)}</div>
    </div>
  `).join('');
  container.querySelectorAll('.notif-item').forEach(el => {
    el.addEventListener('click', async () => {
      await PUT(`/api/notifications/${el.dataset.id}/read`);
      el.classList.add('read');
      refreshBadge();
    });
  });
}

// Auto-refresh badge every 30s
setInterval(refreshBadge, 30000);
refreshBadge();

// ── Setup sub-tabs ────────────────────────────────────────────────────────────

document.querySelectorAll('.setup-tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.setup-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.setup-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`setup-${btn.dataset.setup}`).classList.add('active');
    if (btn.dataset.setup === 'notifications') loadNotifFull();
    if (btn.dataset.setup === 'passwords') loadPasswords();
    if (btn.dataset.setup === 'questions') loadProfile();
  });
});

// ── Modal helpers ─────────────────────────────────────────────────────────────

function openModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

document.querySelectorAll('.modal-close, [data-modal]').forEach(el => {
  el.addEventListener('click', (e) => {
    const modal = el.dataset.modal || el.closest('.modal').id;
    if (modal) closeModal(modal);
  });
});
document.querySelectorAll('.modal').forEach(m => {
  m.addEventListener('click', (e) => { if (e.target === m) closeModal(m.id); });
});

function esc(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ═════════════════════════════════════════════════════════════════════════════
// OVERVIEW
// ═════════════════════════════════════════════════════════════════════════════

async function loadOverview() {
  const data = await GET('/api/overview');

  document.getElementById('statsGrid').innerHTML = `
    <div class="stat-card"><div class="stat-value">${data.total_jobs}</div><div class="stat-label">Total Jobs</div></div>
    <div class="stat-card"><div class="stat-value">${data.pipeline.applied || 0}</div><div class="stat-label">Applied</div></div>
    <div class="stat-card"><div class="stat-value">${data.pipeline.interview || 0}</div><div class="stat-label">Interviews</div></div>
    <div class="stat-card"><div class="stat-value">${data.pipeline.offer || 0}</div><div class="stat-label">Offers</div></div>
    <div class="stat-card"><div class="stat-value">${data.total_coffee_chats}</div><div class="stat-label">Coffee Chats</div></div>
    <div class="stat-card"><div class="stat-value">${data.total_emails}</div><div class="stat-label">Emails Sent</div></div>
    <div class="stat-card"><div class="stat-value">${data.unread_notifications}</div><div class="stat-label">Unread Alerts</div></div>
  `;

  const stages = [
    ['to_apply', 'To Apply'], ['applied', 'Applied'], ['phone_screen', 'Phone Screen'],
    ['interview', 'Interview'], ['offer', 'Offer'], ['rejected', 'Rejected'],
  ];
  document.getElementById('pipeline').innerHTML = stages.map(([key, label]) => `
    <div class="pipeline-stage">
      <div class="p-count">${data.pipeline[key] || 0}</div>
      <div class="p-label">${label}</div>
    </div>
  `).join('');

  const coffeeEl = document.getElementById('coffeeFollowups');
  coffeeEl.innerHTML = data.coffee_followups.length
    ? data.coffee_followups.map(c => `
        <div class="followup-item">
          <div class="fi-name">${esc(c.name)} — ${esc(c.company)}</div>
          <div class="fi-sub">Follow up: ${c.follow_up_date} ${badge(c.status)}</div>
        </div>`).join('')
    : '<p class="empty-state">No follow-ups due.</p>';

  const emailEl = document.getElementById('emailFollowups');
  emailEl.innerHTML = data.email_followups.length
    ? data.email_followups.map(e => `
        <div class="followup-item">
          <div class="fi-name">${esc(e.name)} — ${esc(e.company)}</div>
          <div class="fi-sub">Follow up: ${e.follow_up_date} ${badge(e.status)}</div>
        </div>`).join('')
    : '<p class="empty-state">No follow-ups due.</p>';
}

// ═════════════════════════════════════════════════════════════════════════════
// JOBS
// ═════════════════════════════════════════════════════════════════════════════

let allJobs = [];
let activeStatusFilter = '';
let currentAutomateJobId = null;

async function loadJobs() {
  allJobs = await GET('/api/jobs');
  renderPipelineColumns();
  renderJobList();
}

function renderPipelineColumns() {
  const stages = [
    ['to_apply', 'To Apply'], ['applied', 'Applied'], ['phone_screen', 'Phone Screen'],
    ['interview', 'Interview'], ['offer', 'Offer'], ['rejected', 'Rejected'],
  ];
  const counts = {};
  stages.forEach(([k]) => { counts[k] = allJobs.filter(j => j.status === k).length; });

  document.getElementById('jobColumns').innerHTML = stages.map(([key, label]) => `
    <div class="pipeline-col ${activeStatusFilter === key ? 'active' : ''}" data-status="${key}">
      <div class="col-count">${counts[key]}</div>
      <div class="col-label">${label}</div>
    </div>
  `).join('');

  document.querySelectorAll('.pipeline-col').forEach(col => {
    col.addEventListener('click', () => {
      const s = col.dataset.status;
      activeStatusFilter = activeStatusFilter === s ? '' : s;
      document.getElementById('jobStatusFilter').value = activeStatusFilter;
      renderPipelineColumns();
      renderJobList();
    });
  });
}

function renderJobList() {
  const search = document.getElementById('jobSearch').value.toLowerCase();
  const statusF = document.getElementById('jobStatusFilter').value || activeStatusFilter;
  let jobs = allJobs;
  if (statusF) jobs = jobs.filter(j => j.status === statusF);
  if (search) jobs = jobs.filter(j => j.company.toLowerCase().includes(search) || j.title.toLowerCase().includes(search));

  const el = document.getElementById('jobList');
  if (!jobs.length) { el.innerHTML = '<p class="empty-state">No jobs found. Add one!</p>'; return; }

  el.innerHTML = jobs.map(j => `
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">${esc(j.title)} <span style="color:var(--text-muted);font-weight:400">@ ${esc(j.company)}</span></div>
          <div class="card-subtitle">${j.location ? esc(j.location) + ' · ' : ''}${j.salary ? esc(j.salary) : ''}</div>
        </div>
        <div class="card-actions">
          ${j.workday_url ? `<button class="btn btn-sm btn-success" onclick="openAutomateModal(${j.id})">Apply</button>` : ''}
          <button class="btn btn-sm btn-secondary" onclick="editJob(${j.id})">Edit</button>
          <button class="btn-icon" onclick="deleteJob(${j.id})" title="Delete">🗑</button>
        </div>
      </div>
      <div class="card-meta">
        ${badge(j.status)}
        ${j.source ? `<span class="badge" style="background:var(--bg3);color:var(--text-muted)">${esc(j.source)}</span>` : ''}
        ${j.applied_at ? `<span style="font-size:.8rem;color:var(--text-muted)">Applied ${relTime(j.applied_at)}</span>` : ''}
        ${j.url ? `<a href="${esc(j.url)}" target="_blank" style="font-size:.8rem">Job Posting ↗</a>` : ''}
      </div>
      ${j.notes ? `<div style="font-size:.82rem;color:var(--text-muted);margin-top:8px">${esc(j.notes)}</div>` : ''}
    </div>
  `).join('');
}

document.getElementById('jobSearch').addEventListener('input', renderJobList);
document.getElementById('jobStatusFilter').addEventListener('change', (e) => {
  activeStatusFilter = e.target.value;
  renderPipelineColumns();
  renderJobList();
});

// Add Job
document.getElementById('addJobBtn').addEventListener('click', () => {
  resetJobModal();
  document.getElementById('jobModalTitle').textContent = 'Add Job';
  document.getElementById('applyJobBtn').classList.add('hidden');
  openModal('jobModal');
});

function resetJobModal() {
  ['jobId', 'jobCompany', 'jobTitle', 'jobUrl', 'jobWorkdayUrl', 'jobSalary', 'jobLocation', 'jobSource', 'jobNotes'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('jobStatus').value = 'to_apply';
}

async function editJob(id) {
  const j = await GET(`/api/jobs/${id}`);
  document.getElementById('jobId').value = j.id;
  document.getElementById('jobCompany').value = j.company || '';
  document.getElementById('jobTitle').value = j.title || '';
  document.getElementById('jobUrl').value = j.url || '';
  document.getElementById('jobWorkdayUrl').value = j.workday_url || '';
  document.getElementById('jobStatus').value = j.status || 'to_apply';
  document.getElementById('jobSalary').value = j.salary || '';
  document.getElementById('jobLocation').value = j.location || '';
  document.getElementById('jobSource').value = j.source || '';
  document.getElementById('jobNotes').value = j.notes || '';
  document.getElementById('jobModalTitle').textContent = 'Edit Job';
  if (j.workday_url) document.getElementById('applyJobBtn').classList.remove('hidden');
  openModal('jobModal');
}

document.getElementById('saveJobBtn').addEventListener('click', async () => {
  const id = document.getElementById('jobId').value;
  const data = {
    company: document.getElementById('jobCompany').value.trim(),
    title: document.getElementById('jobTitle').value.trim(),
    url: document.getElementById('jobUrl').value.trim() || null,
    workday_url: document.getElementById('jobWorkdayUrl').value.trim() || null,
    status: document.getElementById('jobStatus').value,
    salary: document.getElementById('jobSalary').value.trim() || null,
    location: document.getElementById('jobLocation').value.trim() || null,
    source: document.getElementById('jobSource').value.trim() || null,
    notes: document.getElementById('jobNotes').value.trim() || null,
  };
  if (!data.company || !data.title) { alert('Company and title are required.'); return; }
  try {
    if (id) await PUT(`/api/jobs/${id}`, data);
    else await POST('/api/jobs', data);
    closeModal('jobModal');
    loadJobs();
  } catch (e) { alert(e.message); }
});

document.getElementById('applyJobBtn').addEventListener('click', () => {
  const id = document.getElementById('jobId').value;
  if (!id) return;
  closeModal('jobModal');
  openAutomateModal(parseInt(id));
});

async function deleteJob(id) {
  if (!confirm('Delete this job?')) return;
  await DEL(`/api/jobs/${id}`);
  loadJobs();
}

// Automate
function openAutomateModal(jobId) {
  currentAutomateJobId = jobId;
  document.getElementById('automateEmail').value = '';
  document.getElementById('automatePassword').value = '';
  // Pre-fill email from profile
  GET('/api/profile').then(profile => {
    const email = (profile['Personal Info'] || []).find(q => q.key === 'email');
    if (email && email.answer) document.getElementById('automateEmail').value = email.answer;
  });
  openModal('automateModal');
}

document.getElementById('startAutomateBtn').addEventListener('click', async () => {
  if (!currentAutomateJobId) return;
  const email = document.getElementById('automateEmail').value.trim();
  const password = document.getElementById('automatePassword').value;
  try {
    const res = await POST(`/api/automate/${currentAutomateJobId}`, { email, password });
    closeModal('automateModal');
    alert(res.message || 'Automation started! Check Notifications for updates.');
    refreshBadge();
  } catch (e) { alert(e.message); }
});

// ═════════════════════════════════════════════════════════════════════════════
// COFFEE CHATS
// ═════════════════════════════════════════════════════════════════════════════

async function loadCoffeeChats() {
  const chats = await GET('/api/coffee-chats');
  const el = document.getElementById('coffeeList');
  if (!chats.length) { el.innerHTML = '<p class="empty-state">No coffee chats yet. Add one!</p>'; return; }
  el.innerHTML = chats.map(c => `
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">${esc(c.name)}</div>
          <div class="card-subtitle">${esc(c.company)}${c.role ? ' · ' + esc(c.role) : ''}</div>
        </div>
        <div class="card-actions">
          <button class="btn btn-sm btn-secondary" onclick="editCoffeeChat(${c.id})">Edit</button>
          <button class="btn-icon" onclick="deleteCoffeeChat(${c.id})" title="Delete">🗑</button>
        </div>
      </div>
      <div class="card-meta">
        ${badge(c.status)}
        ${c.follow_up_date ? `<span style="font-size:.8rem;color:var(--text-muted)">Follow up: ${c.follow_up_date}</span>` : ''}
        ${c.linkedin_url ? `<a href="${esc(c.linkedin_url)}" target="_blank" style="font-size:.8rem">LinkedIn ↗</a>` : ''}
      </div>
      ${c.next_action ? `<div style="font-size:.82rem;color:var(--text-muted);margin-top:8px">Next: ${esc(c.next_action)}</div>` : ''}
    </div>
  `).join('');
}

document.getElementById('addCoffeeBtn').addEventListener('click', () => {
  resetCoffeeModal();
  document.getElementById('coffeeModalTitle').textContent = 'Add Coffee Chat';
  openModal('coffeeModal');
});

function resetCoffeeModal() {
  ['coffeeId', 'coffeeName', 'coffeeCompany', 'coffeeRole', 'coffeeLinkedin', 'coffeeMeetingNotes', 'coffeeNextAction', 'coffeeFollowUpDate'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('coffeeStatus').value = 'to_reach_out';
}

async function editCoffeeChat(id) {
  const c = await GET(`/api/coffee-chats/${id}`);
  document.getElementById('coffeeId').value = c.id;
  document.getElementById('coffeeName').value = c.name || '';
  document.getElementById('coffeeCompany').value = c.company || '';
  document.getElementById('coffeeRole').value = c.role || '';
  document.getElementById('coffeeLinkedin').value = c.linkedin_url || '';
  document.getElementById('coffeeStatus').value = c.status || 'to_reach_out';
  document.getElementById('coffeeFollowUpDate').value = c.follow_up_date || '';
  document.getElementById('coffeeMeetingNotes').value = c.meeting_notes || '';
  document.getElementById('coffeeNextAction').value = c.next_action || '';
  document.getElementById('coffeeModalTitle').textContent = 'Edit Coffee Chat';
  openModal('coffeeModal');
}

document.getElementById('saveCoffeeBtn').addEventListener('click', async () => {
  const id = document.getElementById('coffeeId').value;
  const data = {
    name: document.getElementById('coffeeName').value.trim(),
    company: document.getElementById('coffeeCompany').value.trim(),
    role: document.getElementById('coffeeRole').value.trim() || null,
    linkedin_url: document.getElementById('coffeeLinkedin').value.trim() || null,
    status: document.getElementById('coffeeStatus').value,
    follow_up_date: document.getElementById('coffeeFollowUpDate').value || null,
    meeting_notes: document.getElementById('coffeeMeetingNotes').value.trim() || null,
    next_action: document.getElementById('coffeeNextAction').value.trim() || null,
  };
  if (!data.name || !data.company) { alert('Name and company are required.'); return; }
  try {
    if (id) await PUT(`/api/coffee-chats/${id}`, data);
    else await POST('/api/coffee-chats', data);
    closeModal('coffeeModal');
    loadCoffeeChats();
  } catch (e) { alert(e.message); }
});

async function deleteCoffeeChat(id) {
  if (!confirm('Delete this coffee chat?')) return;
  await DEL(`/api/coffee-chats/${id}`);
  loadCoffeeChats();
}

// ═════════════════════════════════════════════════════════════════════════════
// EMAIL OUTREACH
// ═════════════════════════════════════════════════════════════════════════════

async function loadEmails() {
  const emails = await GET('/api/email-outreach');
  const el = document.getElementById('emailList');
  if (!emails.length) { el.innerHTML = '<p class="empty-state">No email outreach yet. Add one!</p>'; return; }
  el.innerHTML = emails.map(e => `
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">${esc(e.name)}</div>
          <div class="card-subtitle">${esc(e.company)}${e.role ? ' · ' + esc(e.role) : ''}</div>
        </div>
        <div class="card-actions">
          <button class="btn btn-sm btn-secondary" onclick="editEmail(${e.id})">Edit</button>
          <button class="btn-icon" onclick="deleteEmail(${e.id})" title="Delete">🗑</button>
        </div>
      </div>
      <div class="card-meta">
        ${badge(e.status)}
        ${e.follow_up_date ? `<span style="font-size:.8rem;color:var(--text-muted)">Follow up: ${e.follow_up_date}</span>` : ''}
        ${e.email ? `<span style="font-size:.8rem;color:var(--text-muted)">${esc(e.email)}</span>` : ''}
      </div>
      ${e.subject ? `<div style="font-size:.82rem;color:var(--text-muted);margin-top:8px">Subject: ${esc(e.subject)}</div>` : ''}
    </div>
  `).join('');
}

document.getElementById('addEmailBtn').addEventListener('click', () => {
  resetEmailModal();
  document.getElementById('emailModalTitle').textContent = 'Add Email Outreach';
  openModal('emailModal');
});

function resetEmailModal() {
  ['emailId', 'emailName', 'emailCompany', 'emailRole', 'emailAddr', 'emailSubject', 'emailBody', 'emailFollowUpDate'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('emailStatus').value = 'to_send';
}

async function editEmail(id) {
  const e = await GET(`/api/email-outreach/${id}`);
  document.getElementById('emailId').value = e.id;
  document.getElementById('emailName').value = e.name || '';
  document.getElementById('emailCompany').value = e.company || '';
  document.getElementById('emailRole').value = e.role || '';
  document.getElementById('emailAddr').value = e.email || '';
  document.getElementById('emailSubject').value = e.subject || '';
  document.getElementById('emailBody').value = e.body || '';
  document.getElementById('emailStatus').value = e.status || 'to_send';
  document.getElementById('emailFollowUpDate').value = e.follow_up_date || '';
  document.getElementById('emailModalTitle').textContent = 'Edit Email Outreach';
  openModal('emailModal');
}

document.getElementById('saveEmailBtn').addEventListener('click', async () => {
  const id = document.getElementById('emailId').value;
  const data = {
    name: document.getElementById('emailName').value.trim(),
    company: document.getElementById('emailCompany').value.trim(),
    role: document.getElementById('emailRole').value.trim() || null,
    email: document.getElementById('emailAddr').value.trim() || null,
    subject: document.getElementById('emailSubject').value.trim() || null,
    body: document.getElementById('emailBody').value.trim() || null,
    status: document.getElementById('emailStatus').value,
    follow_up_date: document.getElementById('emailFollowUpDate').value || null,
  };
  if (!data.name || !data.company) { alert('Name and company are required.'); return; }
  try {
    if (id) await PUT(`/api/email-outreach/${id}`, data);
    else await POST('/api/email-outreach', data);
    closeModal('emailModal');
    loadEmails();
  } catch (e) { alert(e.message); }
});

async function deleteEmail(id) {
  if (!confirm('Delete this email outreach?')) return;
  await DEL(`/api/email-outreach/${id}`);
  loadEmails();
}

// ═════════════════════════════════════════════════════════════════════════════
// RESUME TAILOR
// ═════════════════════════════════════════════════════════════════════════════

async function loadResume() {
  // Load base resume
  try {
    const base = await GET('/api/resume/base');
    document.getElementById('baseResumeText').value = base.content;
  } catch (e) {
    document.getElementById('baseResumeText').value = '';
  }

  // Load jobs for tailor dropdown
  const jobs = await GET('/api/jobs');
  const sel = document.getElementById('tailorJobSelect');
  sel.innerHTML = '<option value="">— None —</option>' +
    jobs.map(j => `<option value="${j.id}">${esc(j.company)} — ${esc(j.title)}</option>`).join('');
}

document.getElementById('saveBaseResumeBtn').addEventListener('click', async () => {
  const content = document.getElementById('baseResumeText').value.trim();
  if (!content) { alert('Please paste your resume first.'); return; }
  try {
    await POST('/api/resume', { content, is_base: true, label: 'Base Resume' });
    alert('Base resume saved!');
  } catch (e) { alert(e.message); }
});

document.getElementById('tailorBtn').addEventListener('click', async () => {
  const jd = document.getElementById('jobDescText').value.trim();
  if (!jd) { alert('Please paste a job description.'); return; }
  const jobId = document.getElementById('tailorJobSelect').value || null;
  const statusEl = document.getElementById('tailorStatus');
  statusEl.className = 'status-msg loading';
  statusEl.textContent = 'Tailoring your resume with Claude AI... this may take 15-30 seconds.';
  statusEl.classList.remove('hidden');
  document.getElementById('tailorBtn').disabled = true;
  try {
    const res = await POST('/api/resume/tailor', { job_description: jd, job_id: jobId ? parseInt(jobId) : null });
    document.getElementById('tailoredResumeOut').value = res.tailored_resume;
    statusEl.className = 'status-msg success';
    statusEl.textContent = 'Resume tailored successfully!';
  } catch (e) {
    statusEl.className = 'status-msg error';
    statusEl.textContent = e.message;
  } finally {
    document.getElementById('tailorBtn').disabled = false;
  }
});

document.getElementById('copyTailoredBtn').addEventListener('click', () => {
  const text = document.getElementById('tailoredResumeOut').value;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => alert('Copied to clipboard!')).catch(() => {
    document.getElementById('tailoredResumeOut').select();
    document.execCommand('copy');
    alert('Copied!');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// JOB SETUP
// ═════════════════════════════════════════════════════════════════════════════

async function loadSetup() {
  loadProfile();
}

// ── Profile / Application Questions ─────────────────────────────────────────

async function loadProfile() {
  const profile = await GET('/api/profile');
  const container = document.getElementById('profileForm');
  container.innerHTML = '';

  Object.entries(profile).forEach(([category, questions]) => {
    const div = document.createElement('div');
    div.className = 'profile-category';
    div.innerHTML = `<h4>${esc(category)}</h4><div class="profile-grid"></div>`;
    const grid = div.querySelector('.profile-grid');
    questions.forEach(q => {
      grid.innerHTML += `
        <div class="form-group">
          <label class="label" for="profile_${q.key}">${esc(q.label)}</label>
          <input type="text" class="input profile-answer" id="profile_${q.key}"
            data-key="${q.key}" value="${esc(q.answer || '')}" />
        </div>
      `;
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
  } catch (e) { alert(e.message); }
});

// ── Passwords ────────────────────────────────────────────────────────────────

async function loadPasswords() {
  const passwords = await GET('/api/passwords');
  const el = document.getElementById('passwordList');
  if (!passwords.length) { el.innerHTML = '<p class="empty-state">No passwords saved yet.</p>'; return; }
  el.innerHTML = passwords.map(p => `
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">${esc(p.company_name)}</div>
          ${p.workday_url_pattern ? `<div class="card-subtitle">${esc(p.workday_url_pattern)}</div>` : ''}
        </div>
        <div class="card-actions">
          <span class="badge" style="background:var(--bg3);color:var(--success)">Password saved</span>
          <button class="btn btn-sm btn-secondary" onclick="editPassword(${p.id}, '${esc(p.company_name)}', '${esc(p.workday_url_pattern || '')}')">Edit</button>
          <button class="btn-icon" onclick="deletePassword(${p.id})" title="Delete">🗑</button>
        </div>
      </div>
    </div>
  `).join('');
}

document.getElementById('addPasswordBtn').addEventListener('click', () => {
  resetPasswordModal();
  document.getElementById('passwordModalTitle').textContent = 'Add Company Password';
  openModal('passwordModal');
});

function resetPasswordModal() {
  ['passwordId', 'passwordCompany', 'passwordUrlPattern', 'passwordValue'].forEach(id => {
    document.getElementById(id).value = '';
  });
}

function editPassword(id, company, urlPattern) {
  document.getElementById('passwordId').value = id;
  document.getElementById('passwordCompany').value = company;
  document.getElementById('passwordUrlPattern').value = urlPattern;
  document.getElementById('passwordValue').value = '';
  document.getElementById('passwordModalTitle').textContent = 'Edit Company Password';
  openModal('passwordModal');
}

document.getElementById('savePasswordBtn').addEventListener('click', async () => {
  const id = document.getElementById('passwordId').value;
  const company = document.getElementById('passwordCompany').value.trim();
  const urlPattern = document.getElementById('passwordUrlPattern').value.trim();
  const password = document.getElementById('passwordValue').value;

  if (!company) { alert('Company name is required.'); return; }
  if (!id && !password) { alert('Password is required.'); return; }

  try {
    if (id) {
      const data = { company_name: company, workday_url_pattern: urlPattern || null };
      if (password) data.password = password;
      await PUT(`/api/passwords/${id}`, data);
    } else {
      await POST('/api/passwords', { company_name: company, workday_url_pattern: urlPattern || null, password });
    }
    closeModal('passwordModal');
    loadPasswords();
  } catch (e) { alert(e.message); }
});

async function deletePassword(id) {
  if (!confirm('Delete this password?')) return;
  await DEL(`/api/passwords/${id}`);
  loadPasswords();
}

// ═════════════════════════════════════════════════════════════════════════════
// INITIAL LOAD
// ═════════════════════════════════════════════════════════════════════════════

loadOverview();
