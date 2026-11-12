'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('kj-token') || '';
sessionStorage.setItem('kj-token', token);
history.replaceState(null, '', location.pathname);
let state = null, updateSignature = '', planSignature = '', resultSignature = '';
let selected = new Set(), selectedFiles = new Set(), pending = false;
const size = bytes => bytes >= 1073741824 ? (bytes / 1073741824).toFixed(2) + ' GB' : (bytes / 1048576).toFixed(1) + ' MB';
function element(tag, text, className) { const node = document.createElement(tag); if (text != null) node.textContent = text; if (className) node.className = className; return node; }
function link(text, href) { const a = element('a', text); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; }
async function api(path, body) {
  const response = await fetch('/api/' + path, {method: body === undefined ? 'GET' : 'POST', headers: {'X-KJ-Token': token, 'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json(); if (!response.ok) throw Error(data.error || '요청 실패'); return data;
}
function showError(error) { $('error').hidden = false; $('error').textContent = error.message; }
async function action(path, body) {
  if (pending) return; pending = true; disableControls(true);
  try { await api(path, body); await poll(); } catch (error) { showError(error); }
  finally { pending = false; disableControls(state?.busy || false); }
}
function disableControls(busy) {
  for (const id of ['search','version','since','until','inclusive','dotnet','preview','select-all','select-none','prepare','download','retry','prerequisites','folder','browse','quit']) $(id).disabled = busy;
  document.querySelectorAll('#updates input,#files input').forEach(input => input.disabled = busy);
  $('prepare').disabled = busy || selected.size === 0;
  $('download').disabled = busy || selectedFiles.size === 0;
  $('retry').disabled = busy || !state?.results.some(r => !r.success);
}
function renderUpdates() {
  $('updates').replaceChildren(); selected = new Set();
  $('count').textContent = state.updates.length;
  $('empty').hidden = state.updates.length > 0;
  if (state.operation === 'search' && !state.busy) $('empty').textContent = '선택한 기간과 조건에 해당하는 업데이트가 없습니다.';
  for (const u of state.updates) {
    const row = element('tr'), check = element('input'); check.type = 'checkbox'; check.setAttribute('aria-label', u.title + ' 선택');
    check.onchange = () => { if (check.checked) selected.add(u.id); else selected.delete(u.id); disableControls(state.busy); };
    check.dataset.id = u.id; const cell = element('td'); cell.append(check); row.append(cell);
    const title = element('td', u.title); title.append(element('small', u.classification)); row.append(title, element('td', u.date), element('td', size(u.size)));
    const source = element('td'); source.append(link(u.kb || 'Catalog', u.url)); row.append(source); $('updates').append(row);
  }
}
function fileCount() { $('file-count').textContent = selectedFiles.size + '개 파일 선택 · 중복 파일은 한 번만 저장'; disableControls(state?.busy || false); }
function renderPlan() {
  $('plan-panel').hidden = !state.plan; selectedFiles.clear(); $('files').replaceChildren();
  if (!state.plan) return;
  $('prerequisites').checked = true;
  for (const file of state.plan.files) {
    selectedFiles.add(file.key);
    const label = element('label', null, 'file'), check = element('input'); check.type = 'checkbox'; check.checked = true; check.dataset.key = file.key; check.dataset.optional = String(file.prerequisite);
    check.onchange = () => { if (check.checked) selectedFiles.add(file.key); else selectedFiles.delete(file.key); fileCount(); };
    const info = element('span'); info.append(element('b', file.prerequisite ? '선행·권장' : '선택 업데이트', 'tag'), document.createTextNode(file.name));
    info.append(element('small', [file.kb, file.date || '날짜 확인 필요', file.algorithm.toUpperCase() + ' 검증', '관련 ' + file.parents.join(', ')].join(' · ')));
    label.append(check, info); $('files').append(label);
  }
  $('warnings').hidden = !state.plan.warnings.length; $('warnings').textContent = state.plan.warnings.join('\n');
  $('note-list').replaceChildren(); $('notes').hidden = !state.plan.notes.length;
  for (const note of state.plan.notes) { const p = element('p', note.text + ' '); p.append(link(note.kb + ' 공식 문서', note.url)); $('note-list').append(p); }
  fileCount();
}
function renderResults() {
  $('results-panel').hidden = !state.results.length; $('results').replaceChildren();
  for (const r of state.results) { const div = element('div', r.status, r.success ? 'result' : 'result failed'); div.append(element('small', r.name)); $('results').append(div); }
}
async function poll() {
  const next = await api('state');
  if (!state) {
    $('until').value = next.today; const d = new Date(next.today + 'T12:00:00'); d.setDate(d.getDate() - 90); $('since').value = d.toISOString().slice(0,10); $('folder').value = next.folder;
  }
  state = next; $('message').textContent = state.message; $('error').hidden = !state.error; $('error').textContent = state.error;
  $('cancel').hidden = !state.busy; $('progress').hidden = !state.busy;
  if (state.total) $('progress').value = Math.min(100, state.received / state.total * 100); else if (state.busy) $('progress').removeAttribute('value');
  $('transfer').hidden = !(state.busy && state.operation === 'download');
  $('transfer').textContent = (state.index + 1) + '/' + state.count + ' 파일 · ' + size(state.received) + (state.total ? ' / ' + size(state.total) : '');
  const us = JSON.stringify(state.updates); if (us !== updateSignature) { updateSignature = us; renderUpdates(); }
  if (state.operation === 'search' && !state.busy && !state.updates.length && !state.error) $('empty').textContent = '선택한 기간과 조건에 해당하는 업데이트가 없습니다.';
  const ps = JSON.stringify(state.plan); if (ps !== planSignature) { planSignature = ps; renderPlan(); }
  const rs = JSON.stringify(state.results); if (rs !== resultSignature) { resultSignature = rs; renderResults(); }
  disableControls(state.busy || pending);
}
$('search-form').onsubmit = event => { event.preventDefault(); action('search', {version: $('version').value, since: $('since').value, until: $('until').value, inclusive: $('inclusive').checked, dotnet: $('dotnet').checked, preview: $('preview').checked}); };
for (const [id, checked] of [['select-all', true], ['select-none', false]]) $(id).onclick = () => { document.querySelectorAll('#updates input').forEach(c => { c.checked = checked; c.dispatchEvent(new Event('change')); }); };
$('prepare').onclick = () => action('plan', {ids: [...selected]});
$('prerequisites').onchange = () => { document.querySelectorAll('#files input[data-optional=true]').forEach(c => { c.checked = $('prerequisites').checked; if (c.checked) selectedFiles.add(c.dataset.key); else selectedFiles.delete(c.dataset.key); }); fileCount(); };
$('download').onclick = () => action('download', {keys: [...selectedFiles], folder: $('folder').value});
$('retry').onclick = () => action('download', {keys: state.results.filter(r => !r.success).map(r => r.key), folder: $('folder').value});
$('cancel').onclick = () => action('cancel', {});
$('browse').onclick = async () => { try { const result = await api('folder', {}); if (result.folder) $('folder').value = result.folder; } catch (error) { showError(error); } };
$('open-folder').onclick = () => action('open-folder', {});
let closed = false;
$('quit').onclick = async () => { try { await api('quit', {}); closed = true; $('message').textContent = '앱이 종료되었습니다. 이 창을 닫아 주세요.'; disableControls(true); } catch (error) { showError(error); } };
async function loop() { if (closed) return; try { await poll(); } catch (error) { showError(Error('앱에 연결할 수 없습니다. 실행 파일을 다시 열어 주세요.')); } setTimeout(loop, 900); }
loop();
