/* Card Scanner UI — vanilla JS, polls /api/status once a second. */
(function () {
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const api = async (path, opts) => {
    const r = await fetch(path, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts || {}));
    if (!r.ok) { let msg = r.statusText; try { msg = (await r.json()).detail || msg; } catch (e) {} throw new Error(msg); }
    return r.status === 204 ? null : r.json();
  };
  const post = (path, body) => api(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
  const fmtPrice = (p) => (p === null || p === undefined) ? '—' : '$' + Number(p).toFixed(2);
  const fmtConf = (c) => (c === null || c === undefined) ? '—' : Math.round(c * 100) + '%';
  const fmtElapsed = (s) => Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
  const imgUrl = (p) => p ? '/files/' + p : '';

  // ---------- tabs ----------
  $$('.tab').forEach((b) => b.addEventListener('click', () => showTab(b.dataset.tab)));
  function showTab(name) {
    $$('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
    $$('.tab-panel').forEach((p) => p.classList.toggle('hidden', p.id !== 'tab-' + name));
    if (name === 'review') loadReview();
    if (name === 'rules') loadRules();
    if (name === 'tunables') loadTunables();
    location.hash = name;
  }

  // ---------- dashboard ----------
  let state = {};
  let bins = [];
  async function poll() {
    try {
      state = await api('/api/status');
      render(state);
    } catch (e) {
      showBanner('Lost connection to the scanner host: ' + e.message);
    }
  }
  function showBanner(msg) { const b = $('#banner'); b.textContent = msg; b.classList.toggle('hidden', !msg); }
  function render(s) {
    const badge = $('#state-badge');
    badge.textContent = s.state; badge.className = 'badge ' + s.state;
    let msg = '';
    if (s.state === 'estop') msg = s.error || 'E-STOP active';
    else if (s.state === 'paused') msg = (s.pause_message || 'Paused') + (s.error && s.pause_reason !== 'operator' ? ' (' + s.error + ')' : '');
    else if (s.error) msg = s.error;
    showBanner(msg);
    const w = $('#warning'); w.textContent = s.warning || ''; w.classList.toggle('hidden', !s.warning);
    $('#session-label').textContent = s.session_id ? 'Session ' + s.session_id : '';
    $('#mock-controls').classList.toggle('hidden', !s.mock);
    const running = s.state === 'running' || s.state === 'homing';
    $('#btn-start').disabled = running || s.state === 'paused' || s.state === 'estop';
    $('#btn-pause').disabled = !running;
    $('#btn-resume').disabled = s.state !== 'paused';
    $('#btn-stop').disabled = !(running || s.state === 'paused');
    const st = s.stats || {};
    $('#st-processed').textContent = st.processed || 0;
    $('#st-rate').textContent = st.cards_per_min || 0;
    $('#st-ok').textContent = st.ok || 0;
    $('#st-review').textContent = st.review || 0;
    $('#st-rejected').textContent = st.rejected || 0;
    $('#st-errors').textContent = st.errors || 0;
    $('#st-hopper').textContent = (s.mcu && s.mcu.hopper !== undefined) ? s.mcu.hopper : '–';
    $('#st-elapsed').textContent = fmtElapsed(st.elapsed_s || 0);
    $('#review-count').textContent = s.review_queue !== undefined ? s.review_queue : (st.review || 0);
    bins = s.bins || [];
    $('#bins').innerHTML = bins.map((b, i) => `<div class="bin"><div class="n">${(st.bins || [])[i] || 0}</div><div class="name">${i}: ${b.name}</div></div>`).join('');
    const lc = s.last_card;
    if (lc) {
      $('#lc-front').src = imgUrl(lc.front_path); $('#lc-back').src = imgUrl(lc.back_path);
      $('#lc-name').textContent = lc.name || lc.label || (lc.status === 'rejected' ? 'Rejected (double feed)' : 'Unknown card');
      $('#lc-set').textContent = lc.set_name ? `${lc.set_name} · #${lc.collector_number || '?'} · ${lc.rarity || ''} · ${lc.game || ''}` : (lc.game ? 'game: ' + lc.game : '');
      $('#lc-price').textContent = fmtPrice(lc.price_usd);
      $('#lc-conf').textContent = fmtConf(lc.confidence) + (lc.method ? ' (' + lc.method + ')' : '');
      $('#lc-bin').textContent = lc.bin !== undefined && lc.bin !== null ? `${lc.bin} · ${lc.bin_name || (bins[lc.bin] || {}).name || ''} · ${lc.rule || ''}` : '—';
      $('#lc-status').textContent = lc.status || '—';
    }
    $('#recent tbody').innerHTML = (s.history || []).map((h) => `<tr><td>${h.seq}</td><td>${h.name || h.label || h.error || '?'}</td><td>${fmtPrice(h.price_usd)}</td><td>${fmtConf(h.confidence)}</td><td>${h.bin}</td></tr>`).join('');
    if (s.session_id) {
      $('#exp-mox').href = '/api/export.csv?format=moxfield&session=' + s.session_id;
      $('#exp-tcg').href = '/api/export.csv?format=tcgplayer&session=' + s.session_id;
    }
  }
  const guard = (fn) => async () => { try { await fn(); await poll(); } catch (e) { showBanner(e.message); } };
  $('#btn-start').addEventListener('click', guard(() => post('/api/control/start', { foil: $('#opt-foil').checked, condition: $('#opt-condition').value, notes: $('#opt-notes').value })));
  $('#btn-pause').addEventListener('click', guard(() => post('/api/control/pause')));
  $('#btn-resume').addEventListener('click', guard(() => post('/api/control/resume')));
  $('#btn-stop').addEventListener('click', guard(() => post('/api/control/stop')));
  $('#btn-reset').addEventListener('click', guard(() => post('/api/control/reset')));
  $$('#mock-controls button').forEach((b) => b.addEventListener('click', guard(() => post('/api/mock/' + b.dataset.mock, b.dataset.mock === 'refill' ? { hopper: 30 } : undefined))));

  // ---------- review queue + combobox ----------
  async function loadReview() {
    const items = await api('/api/review');
    const list = $('#review-list');
    list.innerHTML = '';
    $('#review-empty').classList.toggle('hidden', items.length > 0);
    items.forEach((it) => list.appendChild(reviewItem(it)));
  }
  function reviewItem(it) {
    const node = $('#tpl-review').content.firstElementChild.cloneNode(true);
    node.dataset.id = it.id;
    $('.rv-front', node).src = imgUrl(it.front_path);
    $('.rv-seq', node).textContent = `#${it.seq}`;
    $('.rv-guess', node).textContent = it.name ? `best guess: ${it.name} (${fmtConf(it.confidence)})` : (it.error || 'no match');
    if (it.game) $('.rv-game', node).value = it.game;
    const combo = makeCombo($('.combo', node), () => $('.rv-game', node).value);
    const cands = $('.rv-cands', node);
    (it.candidates || []).slice(0, 5).forEach((c) => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'cand';
      b.textContent = `${c.label}${c.distance < 900 ? ' · d=' + c.distance : ''}`;
      b.addEventListener('click', () => { combo.select({ id: c.id, label: c.label }); $$('.cand', cands).forEach((x) => x.classList.toggle('selected', x === b)); });
      cands.appendChild(b);
    });
    const assign = $('.rv-assign', node);
    combo.onChange = (sel) => { assign.disabled = !sel; };
    assign.addEventListener('click', async () => {
      if (!combo.selected) return;
      try { await post(`/api/review/${it.id}/resolve`, { card_id: combo.selected.id }); node.remove(); poll(); $('#review-empty').classList.toggle('hidden', $('#review-list').children.length > 0); }
      catch (e) { showBanner(e.message); }
    });
    $('.rv-skip', node).addEventListener('click', async () => { await post(`/api/review/${it.id}/skip`); node.remove(); });
    return node;
  }
  /* Searchable combobox backed by /api/index/search.  Never lets the operator
     submit free text: a value is only set by picking an option. */
  function makeCombo(root, gameFn) {
    const input = $('.combo-input', root), list = $('.combo-list', root);
    const combo = { selected: null, onChange: null, select(opt) { combo.selected = opt; input.value = opt.label; root.classList.add('has-selection'); close(); if (combo.onChange) combo.onChange(opt); } };
    let timer = null, active = -1, options = [];
    const close = () => { list.classList.add('hidden'); input.setAttribute('aria-expanded', 'false'); active = -1; };
    async function search() {
      const q = input.value.trim();
      if (q.length < 1) { close(); return; }
      const game = gameFn ? gameFn() : '';
      options = await api(`/api/index/search?q=${encodeURIComponent(q)}&game=${encodeURIComponent(game)}&limit=20`);
      list.innerHTML = options.length ? options.map((o, i) => `<li role="option" data-i="${i}"><span>${o.name}</span><span class="muted">${(o.set_code || '').toUpperCase()} #${o.collector_number || '?'} · ${o.rarity || ''} · ${o.game}</span></li>`).join('') : '<li class="muted">No matches</li>';
      list.classList.remove('hidden'); input.setAttribute('aria-expanded', 'true'); active = -1;
      $$('li[data-i]', list).forEach((li) => li.addEventListener('mousedown', (e) => { e.preventDefault(); combo.select(options[+li.dataset.i]); }));
    }
    input.addEventListener('input', () => { combo.selected = null; root.classList.remove('has-selection'); if (combo.onChange) combo.onChange(null); clearTimeout(timer); timer = setTimeout(search, 150); });
    input.addEventListener('focus', () => { if (input.value && !combo.selected) search(); });
    input.addEventListener('blur', () => setTimeout(close, 120));
    input.addEventListener('keydown', (e) => {
      const items = $$('li[data-i]', list);
      if (e.key === 'ArrowDown') { active = Math.min(items.length - 1, active + 1); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { active = Math.max(0, active - 1); e.preventDefault(); }
      else if (e.key === 'Enter' && active >= 0) { combo.select(options[active]); e.preventDefault(); return; }
      else if (e.key === 'Escape') { close(); return; }
      items.forEach((li, i) => li.classList.toggle('active', i === active));
    });
    return combo;
  }

  // ---------- rules editor ----------
  let ruleOptions = null;
  async function loadRules() {
    if (!ruleOptions) ruleOptions = await api('/api/rules/options');
    const data = await api('/api/rules');
    const tb = $('#rules-table tbody'); tb.innerHTML = '';
    data.rules.forEach((r) => tb.appendChild(ruleRow(r)));
    const db = $('#default-bin');
    db.innerHTML = data.bins.map((b) => `<option value="${b.id}">${b.id}: ${b.name}</option>`).join('');
    db.value = data.default_bin;
    $('#rules-msg').textContent = '';
  }
  const sel = (cls, opts, value, extra) => `<select class="${cls}" ${extra || ''}>${opts.map((o) => `<option value="${o.value}" ${String(o.value) === String(value) ? 'selected' : ''}>${o.label}</option>`).join('')}</select>`;
  const triState = (v) => (v === true ? 'yes' : v === false ? 'no' : '');
  function ruleRow(r) {
    const w = r.when || {};
    const tr = document.createElement('tr');
    const games = [{ value: '', label: 'Any' }].concat(ruleOptions.games);
    const game = Array.isArray(w.game) ? w.game[0] : (w.game || '');
    const rar = Array.isArray(w.rarity) ? w.rarity : (w.rarity ? [w.rarity] : []);
    const yn = [{ value: '', label: 'Any' }, { value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }];
    tr.innerHTML = `
      <td><button class="ghost r-up" title="move up">▲</button><button class="ghost r-down" title="move down">▼</button></td>
      <td><input type="text" class="r-name" value="${r.name || ''}"></td>
      <td>${sel('r-game', games, game)}</td>
      <td><select class="r-rarity" multiple title="Ctrl/Cmd-click for several; none = any">${ruleOptions.rarities.map((x) => `<option value="${x}" ${rar.includes(x) ? 'selected' : ''}>${x}</option>`).join('')}</select></td>
      <td>${sel('r-foil', yn, triState(w.foil))}</td>
      <td>${sel('r-recog', yn, triState(w.recognized))}</td>
      <td><input type="number" class="r-minp" step="0.01" min="0" value="${w.min_price ?? ''}"></td>
      <td><input type="number" class="r-maxp" step="0.01" min="0" value="${w.max_price ?? ''}"></td>
      <td><input type="number" class="r-minc" step="0.05" min="0" max="1" value="${w.min_confidence ?? ''}"></td>
      <td>${sel('r-bin', ruleOptions.bins.map((b) => ({ value: b.id, label: `${b.id}: ${b.name}` })), r.bin)}</td>
      <td><button class="ghost r-del" title="delete">✕</button></td>`;
    $('.r-del', tr).addEventListener('click', () => tr.remove());
    $('.r-up', tr).addEventListener('click', () => tr.previousElementSibling && tr.parentNode.insertBefore(tr, tr.previousElementSibling));
    $('.r-down', tr).addEventListener('click', () => tr.nextElementSibling && tr.parentNode.insertBefore(tr.nextElementSibling, tr));
    return tr;
  }
  function readRules() {
    return $$('#rules-table tbody tr').map((tr) => {
      const when = {};
      const g = $('.r-game', tr).value; if (g) when.game = g;
      const rar = $$('option:checked', $('.r-rarity', tr)).map((o) => o.value); if (rar.length) when.rarity = rar;
      const f = $('.r-foil', tr).value; if (f) when.foil = f === 'yes';
      const rc = $('.r-recog', tr).value; if (rc) when.recognized = rc === 'yes';
      const minp = $('.r-minp', tr).value; if (minp !== '') when.min_price = parseFloat(minp);
      const maxp = $('.r-maxp', tr).value; if (maxp !== '') when.max_price = parseFloat(maxp);
      const minc = $('.r-minc', tr).value; if (minc !== '') when.min_confidence = parseFloat(minc);
      return { name: $('.r-name', tr).value || 'rule', bin: parseInt($('.r-bin', tr).value, 10), when };
    });
  }
  $('#rule-add').addEventListener('click', () => $('#rules-table tbody').appendChild(ruleRow({ name: 'New rule', bin: 1, when: {} })));
  $('#rules-save').addEventListener('click', async () => {
    try {
      await api('/api/rules', { method: 'PUT', body: JSON.stringify({ rules: readRules(), default_bin: parseInt($('#default-bin').value, 10) }) });
      $('#rules-msg').textContent = 'Saved.';
      await loadRules(); $('#rules-msg').textContent = 'Saved.';
    } catch (e) { $('#rules-msg').textContent = 'Error: ' + e.message; }
  });

  // ---------- tunables ----------
  async function loadTunables() {
    const rows = await api('/api/tunables');
    $('#tunables-table tbody').innerHTML = rows.map((r) => `<tr data-key="${r.key}"><td><code>${r.key}</code></td><td class="t-cur">${r.ok ? JSON.stringify(r.value) : '<span class="muted">' + (r.error || 'n/a') + '</span>'}</td><td><input type="text" class="t-val" value="${r.ok ? JSON.stringify(r.value) : ''}"></td><td><button class="ghost t-set">Set</button></td></tr>`).join('');
    $$('#tunables-table .t-set').forEach((b) => b.addEventListener('click', () => setTunable(b.closest('tr').dataset.key, $('.t-val', b.closest('tr')).value)));
  }
  async function setTunable(key, raw) {
    let value = raw; try { value = JSON.parse(raw); } catch (e) {}
    try { const r = await post('/api/tunables', { key, value }); $('#tun-msg').textContent = `${r.key} = ${JSON.stringify(r.value)}`; await loadTunables(); }
    catch (e) { $('#tun-msg').textContent = 'Error: ' + e.message; }
  }
  $('#tun-set').addEventListener('click', () => setTunable($('#tun-key').value.trim(), $('#tun-val').value));
  $('#tun-refresh').addEventListener('click', loadTunables);

  // ---------- boot ----------
  poll(); setInterval(poll, 1000);
  if (location.hash && $('#tab-' + location.hash.slice(1))) showTab(location.hash.slice(1));
})();
