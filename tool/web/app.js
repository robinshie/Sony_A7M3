'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('a7-token');
if (token) sessionStorage.setItem('a7-token', token);
history.replaceState(null, '', '/');
let recipes = [], selected = new Set(), editing = -1, fields = [], pending = false;
const logs = [];
function log(message) {
  logs.push(`${new Date().toLocaleTimeString()}  ${message}`);
  $('log').textContent = logs.join('\n');
  $('log').scrollTop = $('log').scrollHeight;
}
async function api(route, body = {}) {
  const response = await fetch('/api/' + route, {method: 'POST', headers: {'Content-Type':'application/json', 'X-A7-Token': token || ''}, body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '操作失败');
  return result;
}
async function action(task) {
  if (pending) return;
  pending = true; $('busy').hidden = false;
  // Freeze editable controls as well as navigation while a copy is in flight.
  const controls = [...document.querySelectorAll('button,input,select')].filter(x => !x.disabled);
  controls.forEach(x => x.disabled = true);
  try { await task(); } catch (error) { log('失败：' + error.message); alert(error.message); }
  finally { controls.forEach(x => x.disabled = false); pending = false; $('busy').hidden = true; }
}
function download(name, text, type='application/json') {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function renderRecipes() {
  $('recipe-list').replaceChildren();
  recipes.forEach((row, index) => {
    const el = node('div', undefined, 'recipe' + (index === editing ? ' selected' : ''));
    const check = document.createElement('input'); check.type = 'checkbox'; check.checked = selected.has(index);
    check.setAttribute('aria-label', '复制 ' + row.recipe.name);
    check.onchange = () => { check.checked ? selected.add(index) : selected.delete(index); renderCount(); };
    const button = node('button'); button.append(node('strong', row.recipe.name), node('span', row.recipe.base + ' · ' + row.filename));
    button.onclick = () => edit(index);
    el.append(check, button); $('recipe-list').append(el);
  });
  renderCount();
}
function renderCount() { $('selection').textContent = `已选 ${selected.size} / ${recipes.length} 个`; }
function draft() {
  const parameters = {};
  for (const field of fields) {
    const input = $('param-' + field.key);
    if (!input.value.trim() || !input.checkValidity()) throw new Error(field.label + ' 超出范围或不是整数');
    parameters[field.key] = Number(input.value);
  }
  return {filename:$('look-file').value, recipe:{format:'A7FL-LOOK/1', id:$('look-id').value, name:$('look-name').value, base:$('look-base').value, parameters}};
}
function hasDraft() {
  if (editing < 0) return false;
  try { const d = draft(), r = recipes[editing]; return d.filename !== r.filename || ['id','name','base'].some(k => d.recipe[k] !== r.recipe[k]) || fields.some(f => d.recipe.parameters[f.key] !== r.recipe.parameters[f.key]); }
  catch { return true; }
}
function edit(index) {
  if (hasDraft() && !confirm('尚有未应用的编辑。放弃这些编辑并切换配方？')) return;
  editing = index;
  const row = recipes[index];
  $('editor-form').hidden = false; $('editor-empty').hidden = true; $('editor-title').textContent = row.recipe.name;
  $('look-name').value = row.recipe.name; $('look-file').value = row.filename; $('look-id').value = row.recipe.id; $('look-base').value = row.recipe.base;
  fields.forEach(f => $('param-' + f.key).value = row.recipe.parameters[f.key]);
  renderRecipes();
}
document.querySelectorAll('.nav').forEach(button => button.onclick = () => {
  document.querySelectorAll('.page').forEach(p => p.hidden = p.id !== button.dataset.page);
  document.querySelectorAll('.nav').forEach(b => { b.classList.toggle('active', b === button); b === button ? b.setAttribute('aria-current', 'page') : b.removeAttribute('aria-current'); });
});
$('all').onclick = () => { selected = new Set(recipes.map((_, i) => i)); renderRecipes(); };
$('none').onclick = () => { selected.clear(); renderRecipes(); };
$('add-files').onclick = () => $('recipe-files').click();
$('recipe-files').onchange = () => action(async () => {
  const loaded = [];
  for (const file of $('recipe-files').files) {
    if (file.size > 16384) throw new Error(file.name + ' 超过 16 KiB');
    const row = await api('recipe', {filename:file.name, text:await file.text()});
    if ([...recipes, ...loaded].some(r => r.recipe.id === row.recipe.id || r.filename.toLowerCase() === row.filename.toLowerCase()))
      throw new Error('列表已有相同 ID 或文件名：' + row.filename);
    loaded.push(row);
  }
  recipes.push(...loaded); renderRecipes(); log(`添加并校验 ${loaded.length} 份配方。`); $('recipe-files').value = '';
});
$('editor-form').onsubmit = event => {
  event.preventDefault(); action(async () => {
    const d = draft(); const encoded = await api('encode', d);
    if (recipes.some((r,i) => i !== editing && (r.recipe.id === d.recipe.id || r.filename.toLowerCase() === d.filename.toLowerCase())))
      throw new Error('ID 或文件名与另一份配方重复，请修改后再应用。');
    recipes[editing] = await api('recipe', {filename:d.filename, text:encoded.text});
    $('editor-title').textContent = d.recipe.name; renderRecipes(); log('已应用到会话列表：' + d.recipe.name + '；尚未复制到卡。');
  });
};
$('download-recipe').onclick = () => action(async () => { const result = await api('encode', draft()); download(result.filename, result.text); log('已请求浏览器另存配方：' + result.filename); });
function setCards(cards) {
  $('card-options').replaceChildren(...cards.map(c => { const o = document.createElement('option'); o.value = c; return o; }));
  if (cards.length === 1 && !$('card-path').value) $('card-path').value = cards[0];
  log(cards.length ? `找到 ${cards.length} 个候选存储卡目录，请核对目标。` : '未找到已挂载存储卡。请检查电脑挂载状态，或手动填写根目录。');
}
$('scan').onclick = () => action(async () => { const status = await api('status'); setCards(status.cards); });
$('read-card').onclick = () => action(async () => {
  const result = await api('card', {path:$('card-path').value});
  $('card-list').replaceChildren(node('p', `${result.files.length} 份文件 · ${result.card}`));
  result.files.forEach(row => $('card-list').append(node('div', row.filename + ' — ' + (row.error || row.recipe.name), row.error ? 'error' : '')));
  log('已读取卡上配方列表；未修改文件。');
});
$('copy').onclick = () => action(async () => {
  if (hasDraft()) throw new Error('请先点击「应用到待复制列表」，或切换配方放弃编辑，再复制。');
  const body = {path:$('card-path').value, records:[...selected].map(i => recipes[i])};
  const plan = await api('plan', body);
  const count = plan.files.filter(f => f.state === 'copy').length;
  if (!confirm(`目标：${plan.card}\n新增 ${count} 份；已存在 ${plan.files.length-count} 份。\n\n${plan.files.map(f => f.filename).join('\n')}\n\n确认复制？不会刷写机身固件。`)) return;
  const result = await api('copy', body);
  result.files.forEach(f => log((f.state === 'copy' ? '已复制并回读：' : '已有相同配方，跳过：') + f.filename));
  log(result.message);
  if (!result.ok) throw new Error(result.error);
});
$('verify-package').onclick = () => action(async () => {
  const file = $('package-file').files[0];
  $('package-result').hidden = true;
  if (!file || file.size > 64*1024*1024) throw new Error('请选择不超过 64 MiB 的完整功能 ZIP。');
  const bytes = new Uint8Array(await file.arrayBuffer());
  const chunks = []; for (let i=0; i<bytes.length; i+=32768) chunks.push(String.fromCharCode(...bytes.subarray(i,i+32768)));
  const result = await api('package', {base64:btoa(chunks.join('')), expected:$('expected-hash').value});
  const box = $('package-result'); box.hidden = false;
  box.replaceChildren(node('h2', '文件完整性校验通过', 'success'), node('p', result.message),
    node('p', result.external_hash_matched ? '发布页外部 SHA-256：一致' : '未提供发布页 SHA-256；未核对外部来源。', 'muted'),
    node('pre', JSON.stringify({release:result.manifest.release,edition:result.manifest.edition,source_commit:result.manifest.source_commit,files_verified:result.files_verified,sha256:result.sha256,module:result.manifest.module,required_baseline:result.manifest.required_baseline},null,2), 'package-details'),
    node('p', result.install_reason, 'notice'));
  log(`ZIP 校验通过：${result.files_verified} 个文件；未安装到相机。`);
});
$('export-log').onclick = () => download('A7M3-Tool-log.txt', logs.join('\n'), 'text/plain');
$('quit').onclick = () => action(async () => {
  if (!confirm('退出本地工具？未另存的编辑将丢失。')) return;
  await api('quit'); $('connection').textContent = '服务已退出';
  document.querySelectorAll('button,input,select').forEach(x => x.setAttribute('data-closed', 'true'));
  log('本地服务已退出，可以关闭浏览器标签页。');
  setTimeout(() => document.querySelectorAll('[data-closed]').forEach(x => x.disabled = true), 0);
});
window.addEventListener('beforeunload', event => { if (pending || hasDraft()) { event.preventDefault(); event.returnValue = ''; } });
action(async () => {
  const status = await api('status');
  $('connection').textContent = '本地运行 · ' + status.platform;
  $('install-reason').textContent = status.install_reason;
  fields = status.fields;
  $('look-base').replaceChildren(...status.bases.map(base => { const o = node('option', base); o.value = base; return o; }));
  fields.forEach(f => { const label = node('label', f.label, 'param'); const input = document.createElement('input'); input.id = 'param-' + f.key; input.type='number'; input.min=f.low; input.max=f.high; input.step=1; input.required=true; label.append(input); $('parameters').append(label); });
  // Normalize key ordering once so dirty checks are stable across parser input order.
  recipes = status.recipes.map(r => ({...r, recipe:{format:r.recipe.format,id:r.recipe.id,name:r.recipe.name,base:r.recipe.base,parameters:Object.fromEntries(fields.map(f => [f.key,r.recipe.parameters[f.key]]))}}));
  renderRecipes(); setCards(status.cards); log(`工具就绪，载入 ${recipes.length} 份配方。固件刷写未启用。`);
});
