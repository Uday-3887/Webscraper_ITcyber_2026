const $ = (selector, root=document) => root.querySelector(selector);
const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];

document.getElementById('sidebarToggle')?.addEventListener('click', () => {
  document.getElementById('sidebar')?.classList.toggle('open');
});

function showToast(message, type='success') {
  const id = `toast-${Date.now()}`;
  const bg = type === 'error' ? 'text-bg-danger' : type === 'warning' ? 'text-bg-warning' : 'text-bg-success';
  document.getElementById('toastContainer').insertAdjacentHTML('beforeend', `<div id="${id}" class="toast ${bg}" role="alert"><div class="d-flex"><div class="toast-body">${escapeHtml(message)}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div></div>`);
  const element = document.getElementById(id);
  const toast = new bootstrap.Toast(element, {delay: 4000}); toast.show();
  element.addEventListener('hidden.bs.toast', () => element.remove());
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#039;','"':'&quot;'}[char]));
}

async function api(url, options={}) {
  const response = await fetch(url, {headers:{'Content-Type':'application/json', ...(options.headers||{})}, ...options});
  const data = await response.json().catch(() => ({success:false,message:'Invalid server response'}));
  if (!response.ok || data.success === false) throw new Error(data.message || `HTTP ${response.status}`);
  return data;
}

async function deleteJob(id) {
  if (!confirm('Delete this scraping job and its exported files?')) return;
  try { await api(`/api/jobs/${id}`, {method:'DELETE'}); document.getElementById(`job-row-${id}`)?.remove(); showToast('Job deleted.'); }
  catch (error) { showToast(error.message, 'error'); }
}

function filterTable(tableId, query) {
  const value = query.toLowerCase();
  $$(`#${tableId} tbody tr`).forEach(row => row.hidden = !row.textContent.toLowerCase().includes(value));
}

function copyText(button) {
  const text = button.parentElement.querySelector('pre').textContent;
  navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard.'));
}

function initSettingsPage() {
  const settings = JSON.parse(localStorage.getItem('scrapeFlowSettings') || '{}');
  $('#settingHeadless').checked = settings.headless ?? true;
  $('#settingPages').value = settings.maxPages ?? 3;
  $('#settingDelay').value = settings.delay ?? 1;
  $('#saveSettingsBtn').addEventListener('click', () => {
    localStorage.setItem('scrapeFlowSettings', JSON.stringify({
      headless: $('#settingHeadless').checked,
      maxPages: Number($('#settingPages').value),
      delay: Number($('#settingDelay').value),
    }));
    showToast('Settings saved in this browser.');
  });
}
