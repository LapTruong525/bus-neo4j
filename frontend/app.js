/* Giao diện tra cứu lộ trình xe buýt — thuần JavaScript + vis-network */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const state = { stations: [], routes: [], colors: {}, labelToId: {}, idToLabel: {}, selectedRoute: null, lastResult: null, activeCard: 'shortest' };

/* ---------------------------------------------------------------- API & tiện ích */
async function api(method, url, body) {
  const res = await fetch(url, {
    method, headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* không có JSON */ }
  if (!res.ok) {
    let msg = data?.detail || `Lỗi ${res.status}`;
    if (Array.isArray(msg)) msg = msg.map((e) => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`).join('; ');
    throw new Error(msg);
  }
  return data;
}
let toastTimer;
function toast(msg, isErr = false) {
  const t = $('#toast');
  t.textContent = msg; t.className = 'toast' + (isErr ? ' err' : ''); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), isErr ? 6000 : 2800);
}
const guard = (fn) => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, true); } };
const fmtMin = (m) => (m >= 60 ? `${Math.floor(m / 60)} giờ ${Math.round(m % 60)} phút` : `${Math.round(m)} phút`);
const colorOf = (code) => state.colors[code] || '#64748b';
const chip = (code) => `<span class="chip" style="background:${colorOf(code)}">${esc(code)}</span>`;

/* ---------------------------------------------------------------- khởi tạo & tab */
$('#tabs').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  $$('#tabs button').forEach((x) => x.classList.toggle('active', x === b));
  $$('.tab').forEach((t) => t.classList.toggle('active', t.id === 'tab-' + b.dataset.tab));
  if (b.dataset.tab === 'graph') loadFullGraph();
});
document.addEventListener('click', (e) => {
  const c = e.target.closest('[data-close]'); if (c) c.closest('dialog').close();
});

async function loadStats() {
  const s = await api('GET', '/api/stats');
  $('#stats').innerHTML = [['stations', 'Trạm'], ['routes', 'Tuyến'], ['edges', 'Cạnh']]
    .map(([k, l]) => `<div class="stat"><b>${s[k]}</b><span>${l}</span></div>`).join('');
}
async function loadStations() {
  state.stations = await api('GET', '/api/stations');
  state.labelToId = {}; state.idToLabel = {};
  for (const s of state.stations) {
    const label = `${s.name}${s.district ? ' · ' + s.district : ''}`;
    state.labelToId[label.toLowerCase()] = s.id; state.idToLabel[s.id] = label;
  }
  $('#stationList').innerHTML = state.stations.map((s) => `<option value="${esc(state.idToLabel[s.id])}"></option>`).join('');
  renderStationRows();
}
async function loadRoutes() {
  state.routes = await api('GET', '/api/routes');
  state.colors = Object.fromEntries(state.routes.map((r) => [r.code, r.color || '#64748b']));
  renderRouteList();
  $('#graphRoute').innerHTML = '<option value="">Tất cả các tuyến</option>' +
    state.routes.map((r) => `<option value="${esc(r.code)}">Tuyến ${esc(r.code)} · ${esc(r.name)}</option>`).join('');
  renderLegend(state.routes);
}
async function refreshAll() {
  await Promise.all([loadStats(), loadStations(), loadRoutes()]);
}
function resolveStation(text) {
  const t = (text || '').trim().toLowerCase();
  if (state.labelToId[t]) return state.labelToId[t];
  const byName = state.stations.filter((s) => s.name.toLowerCase() === t);
  return byName.length ? byName[0].id : null;
}

/* ---------------------------------------------------------------- vẽ đồ thị (vis-network) */
function project(s) { // phép chiếu đơn giản lat/lon -> x/y
  return { x: (s.lon - 106.6) * 9000, y: -(s.lat - 10.7) * 9800 };
}
function drawGraph(el, data, hl) {
  const pos = {};
  const onPath = new Set(hl ? hl.ids : []);
  const nodes = data.nodes.map((s) => {
    const p = project(s); pos[s.id] = p;
    const faded = hl && !onPath.has(s.id);
    return {
      id: s.id, x: p.x, y: p.y, fixed: true, label: faded ? '' : s.name, title: `${s.name} (${s.id})`,
      shape: 'dot', size: faded ? 4 : (hl ? 9 : 7),
      color: faded ? { background: '#cbd5e1', border: '#cbd5e1' } : { background: '#fff', border: hl ? '#0f172a' : '#334155' },
      borderWidth: 2, font: { size: 13, face: 'Be Vietnam Pro, sans-serif', strokeWidth: 4, strokeColor: '#fff' },
    };
  });
  // gom các cạnh song song để uốn cong, tránh chồng nét
  const groups = {};
  const norm = data.edges.map((e) => {
    const [a, b] = e.from < e.to ? [e.from, e.to] : [e.to, e.from];
    (groups[a + '|' + b] = groups[a + '|' + b] || []).push(e.route);
    return { ...e, a, b, key: a + '|' + b };
  });
  const edges = norm.map((e) => {
    const g = groups[e.key]; const i = g.indexOf(e.route);
    const faded = !!hl;
    return {
      from: e.a, to: e.b,
      color: { color: faded ? '#dde3ec' : (e.color || colorOf(e.route)), opacity: faded ? .9 : .95 },
      width: faded ? 1 : 3,
      smooth: g.length > 1 ? { type: 'curvedCW', roundness: (i - (g.length - 1) / 2) * 0.18 } : false,
      title: `Tuyến ${e.route} · ${e.distance_km} km · ${e.time_min} phút`,
    };
  });
  if (hl) { // vẽ đè các đoạn thuộc lộ trình
    hl.legs.forEach((leg) => {
      for (let i = 0; i < leg.stops.length - 1; i++) {
        edges.push({
          from: leg.stops[i].id, to: leg.stops[i + 1].id, width: 6,
          color: { color: colorOf(leg.route) }, arrows: { to: { enabled: true, scaleFactor: .6 } },
          title: `Tuyến ${leg.route}`,
        });
      }
    });
  }
  const net = new vis.Network(el, { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) }, {
    physics: false, interaction: { hover: true, tooltipDelay: 80, zoomView: true },
    edges: { smooth: false },
  });
  net.once('afterDrawing', () => net.fit({ animation: false }));
  return net;
}
function renderLegend(routes) {
  $('#legend').innerHTML = routes.map((r) => `<span><i style="background:${esc(r.color || '#64748b')}"></i>Tuyến ${esc(r.code)}</span>`).join('');
}
let fullNet;
async function loadFullGraph() {
  const route = $('#graphRoute').value;
  const data = await api('GET', '/api/graph' + (route ? `?route=${encodeURIComponent(route)}` : ''));
  fullNet?.destroy();
  fullNet = drawGraph($('#fullGraph'), data);
  renderLegend(route ? state.routes.filter((r) => r.code === route) : state.routes);
}
$('#graphRoute').addEventListener('change', guard(loadFullGraph));

/* ---------------------------------------------------------------- TÌM ĐƯỜNG */
$('#swap').onclick = () => { const o = $('#origin'), d = $('#dest'); [o.value, d.value] = [d.value, o.value]; };
$('#searchForm').addEventListener('submit', guard(async (e) => {
  e.preventDefault();
  const a = resolveStation($('#origin').value), b = resolveStation($('#dest').value);
  if (!a) return toast('Không nhận ra điểm đi — hãy chọn từ danh sách gợi ý', true);
  if (!b) return toast('Không nhận ra điểm đến — hãy chọn từ danh sách gợi ý', true);
  const q = new URLSearchParams({ origin: a, dest: b, metric: $('#metric').value, initial_wait: $('#initialWait').checked });
  state.lastResult = await api('GET', '/api/path/compare?' + q);
  state.activeCard = 'shortest';
  renderResults();
}));

function legHtml(leg, idx, total) {
  const last = idx === total - 1;
  const stops = leg.stops.map((s) => `<li>${esc(s.name)}</li>`).join('');
  return `
  <div class="leg">
    <div class="leg-rail"><span class="leg-badge" style="background:${colorOf(leg.route)}">${esc(leg.route)}</span>${last ? '' : `<span class="leg-line" style="background:${colorOf(leg.route)}33"></span>`}</div>
    <div class="leg-body">
      <div class="title">Lên xe tuyến ${esc(leg.route)} tại ${esc(leg.from.name)}</div>
      <div class="sub">Xuống tại <b>${esc(leg.to.name)}</b> · ${leg.num_stops} chặng · ${fmtMin(leg.ride_min)} · ${leg.distance_km} km</div>
      <details><summary>Xem ${leg.stops.length} trạm</summary><ol>${stops}</ol></details>
    </div>
  </div>`;
}
function cardHtml(key, title, r, highlight) {
  if (!r.found) return `<div class="rcard" data-key="${key}"><div class="rcard-head"><h3>${title}</h3></div><div class="none">Không có tuyến nào nối hai trạm này.</div></div>`;
  const hl = (k) => (highlight === k ? ' hl' : '');
  const legs = r.legs.map((leg, i) => {
    const xfer = i < r.legs.length - 1
      ? `<div class="xfer">🔁 Chuyển sang tuyến ${esc(r.legs[i + 1].route)} tại <b>${esc(leg.to.name)}</b> — chờ khoảng ${fmtMin(r.legs[i + 1].wait_min)}</div>` : '';
    return legHtml(leg, i, r.legs.length) + xfer;
  }).join('');
  const first = r.legs[0].wait_min ? `<div class="sub" style="margin:0 0 10px 52px">⏱ Chờ xe đầu tiên khoảng ${fmtMin(r.legs[0].wait_min)}</div>` : '';
  return `
  <div class="rcard" data-key="${key}">
    <div class="rcard-head"><h3>${title}</h3><span class="badge ${r.transfers === 0 ? 'ok' : ''}">${r.transfers === 0 ? 'Đi thẳng' : r.transfers + ' lần chuyển tuyến'}</span></div>
    <div class="metrics">
      <div class="metric${hl('time')}"><b>${fmtMin(r.total_time_min)}</b><span>Tổng thời gian</span></div>
      <div class="metric${hl('distance')}"><b>${r.total_distance_km} km</b><span>Quãng đường</span></div>
      <div class="metric${hl('transfers')}"><b>${r.transfers}</b><span>Lần chuyển</span></div>
      <div class="metric"><b>${fmtMin(r.wait_time_min)}</b><span>Thời gian chờ</span></div>
    </div>
    ${first}${legs}
  </div>`;
}
function renderResults() {
  const c = state.lastResult;
  const metricName = $('#metric').value === 'distance' ? 'Quãng đường ngắn nhất' : 'Thời gian ngắn nhất';
  const same = c.shortest.found && c.fewest_transfers.found &&
    c.shortest.legs.map((l) => l.route + l.from.id + l.to.id).join() === c.fewest_transfers.legs.map((l) => l.route + l.from.id + l.to.id).join();
  $('#results').innerHTML =
    (same ? '<div class="same-note">Với cặp trạm này, phương án ngắn nhất cũng chính là phương án ít chuyển tuyến nhất.</div>' : '') +
    cardHtml('shortest', metricName, c.shortest, $('#metric').value === 'distance' ? 'distance' : 'time') +
    cardHtml('fewest_transfers', 'Ít chuyển tuyến nhất', c.fewest_transfers, 'transfers');
  $$('#results .rcard').forEach((el) => {
    el.classList.toggle('active', el.dataset.key === state.activeCard);
    el.onclick = (ev) => { if (ev.target.closest('details')) return; state.activeCard = el.dataset.key; renderResults(); };
  });
  const r = c[state.activeCard];
  const wrap = $('#pathGraphWrap');
  if (!r.found) { wrap.hidden = true; return; }
  wrap.hidden = false;
  $('#pathGraphHint').textContent = state.activeCard === 'shortest' ? 'Đang hiển thị phương án nhanh/ngắn nhất' : 'Đang hiển thị phương án ít chuyển tuyến nhất — bấm vào thẻ để đổi';
  api('GET', '/api/graph').then((data) => {
    drawGraph($('#pathGraph'), data, { ids: r.path_station_ids, legs: r.legs });
  }).catch((e) => toast(e.message, true));
}

/* ---------------------------------------------------------------- TRẠM (CRUD) */
function renderStationRows() {
  const q = $('#stationSearch').value.trim().toLowerCase();
  const rows = state.stations.filter((s) => !q || s.name.toLowerCase().includes(q) || (s.district || '').toLowerCase().includes(q));
  $('#stationRows').innerHTML = rows.map((s) => `
    <tr>
      <td class="num">${esc(s.id)}</td><td><b>${esc(s.name)}</b></td><td>${esc(s.district)}</td>
      <td class="num">${Number(s.lat).toFixed(4)}, ${Number(s.lon).toFixed(4)}</td>
      <td>${(s.routes || []).map(chip).join('') || '<span class="muted">—</span>'}</td>
      <td class="act"><button class="btn small" data-edit="${esc(s.id)}">Sửa</button> <button class="btn small danger" data-del="${esc(s.id)}">Xóa</button></td>
    </tr>`).join('') || '<tr><td colspan="6" class="none">Không có trạm phù hợp</td></tr>';
}
$('#stationSearch').addEventListener('input', renderStationRows);
let editingStation = null;
function openStationDlg(st) {
  editingStation = st;
  const f = $('#stationForm');
  $('#stationDlgTitle').textContent = st ? `Sửa trạm ${st.id}` : 'Thêm trạm';
  f.id.value = st?.id || ''; f.id.disabled = !!st;
  f.name.value = st?.name || ''; f.district.value = st?.district || '';
  f.lat.value = st?.lat ?? ''; f.lon.value = st?.lon ?? '';
  $('#stationHint').textContent = st ? 'Đổi tọa độ sẽ tự tính lại khoảng cách và thời gian của các đoạn đường kề trạm này.' : 'Trạm mới chưa thuộc tuyến nào — hãy thêm vào tuyến ở tab "Tuyến xe".';
  $('#stationDlg').showModal();
}
$('#addStation').onclick = () => openStationDlg(null);
$('#stationRows').addEventListener('click', guard(async (e) => {
  const ed = e.target.closest('[data-edit]'), del = e.target.closest('[data-del]');
  if (ed) openStationDlg(state.stations.find((s) => s.id === ed.dataset.edit));
  if (del) {
    const s = state.stations.find((x) => x.id === del.dataset.del);
    const n = (s.routes || []).length;
    if (!confirm(`Xóa trạm "${s.name}"?` + (n ? `\nTrạm thuộc ${n} tuyến; mỗi tuyến sẽ được nối lại trạm trước với trạm sau.` : ''))) return;
    await api('DELETE', `/api/stations/${encodeURIComponent(s.id)}`);
    toast('Đã xóa trạm'); await refreshAll(); if (state.selectedRoute) openRoute(state.selectedRoute);
  }
}));
$('#stationForm').addEventListener('submit', guard(async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = { name: f.name.value.trim(), district: f.district.value.trim(), lat: parseFloat(f.lat.value), lon: parseFloat(f.lon.value) };
  if (editingStation) await api('PUT', `/api/stations/${encodeURIComponent(editingStation.id)}`, body);
  else { if (f.id.value.trim()) body.id = f.id.value.trim(); await api('POST', '/api/stations', body); }
  $('#stationDlg').close(); toast('Đã lưu trạm'); await refreshAll();
  if (state.selectedRoute) openRoute(state.selectedRoute);
}));

/* ---------------------------------------------------------------- bộ chọn trạm theo thứ tự (dùng chung) */
function stopsEditor(container, initialIds) {
  let ids = [...initialIds];
  const dl = 'dl_' + Math.random().toString(36).slice(2, 7);
  function render() {
    const free = state.stations.filter((s) => !ids.includes(s.id));
    container.innerHTML = `
      <ul class="stoplist">${ids.map((id, i) => {
        const s = state.stations.find((x) => x.id === id);
        return `<li><span class="n">${i + 1}</span><span class="nm">${esc(s?.name || id)} <small>${esc(s?.district || '')}</small></span>
          <button type="button" class="mini" data-up="${i}" ${i === 0 ? 'disabled' : ''} title="Lên">↑</button>
          <button type="button" class="mini" data-dn="${i}" ${i === ids.length - 1 ? 'disabled' : ''} title="Xuống">↓</button>
          <button type="button" class="mini" data-rm="${i}" title="Bỏ trạm">✕</button></li>`;
      }).join('') || '<li class="muted">Chưa có trạm nào</li>'}</ul>
      <div class="addrow"><input list="${dl}" placeholder="Gõ tên trạm để thêm vào cuối tuyến…" data-add autocomplete="off">
        <datalist id="${dl}">${free.map((s) => `<option value="${esc(state.idToLabel[s.id])}"></option>`).join('')}</datalist>
        <button type="button" class="btn" data-addbtn>Thêm trạm</button></div>`;
  }
  container.onclick = (e) => {
    const t = e.target.closest('button'); if (!t) return;
    if (t.dataset.up !== undefined) { const i = +t.dataset.up; [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]]; }
    else if (t.dataset.dn !== undefined) { const i = +t.dataset.dn; [ids[i + 1], ids[i]] = [ids[i], ids[i + 1]]; }
    else if (t.dataset.rm !== undefined) ids.splice(+t.dataset.rm, 1);
    else if (t.dataset.addbtn !== undefined) {
      const inp = $('[data-add]', container); const id = resolveStation(inp.value);
      if (!id) return toast('Hãy chọn trạm từ danh sách gợi ý', true);
      if (ids.includes(id)) return toast('Trạm đã có trong tuyến', true);
      ids.push(id);
    } else return;
    render();
  };
  render();
  return { get: () => [...ids] };
}

/* ---------------------------------------------------------------- TUYẾN (CRUD) */
function renderRouteList() {
  $('#routeList').innerHTML = state.routes.map((r) => `
    <div class="ritem ${state.selectedRoute === r.code ? 'active' : ''}" data-code="${esc(r.code)}">
      <span class="code" style="background:${esc(r.color)}">${esc(r.code)}</span>
      <div><div class="nm">${esc(r.name)}</div><div class="meta">${r.num_stops} trạm · ${r.headway_min} phút/chuyến</div></div>
    </div>`).join('') || '<p class="muted">Chưa có tuyến nào</p>';
}
$('#routeList').addEventListener('click', (e) => { const it = e.target.closest('.ritem'); if (it) openRoute(it.dataset.code); });

let routeEd;
const openRoute = guard(async (code, sub = 'stops') => {
  state.selectedRoute = code; renderRouteList();
  const r = await api('GET', `/api/routes/${encodeURIComponent(code)}`);
  const box = $('#routeDetail');
  box.innerHTML = `
    <div class="rd-head"><span class="code" style="background:${esc(r.color)}">${esc(r.code)}</span>
      <h2>${esc(r.name)}</h2><button class="btn danger small" id="delRoute">Xóa tuyến</button></div>
    <div class="grid4">
      <div class="field"><label>Tên tuyến</label><input id="rName" value="${esc(r.name)}"></div>
      <div class="field"><label>Giãn cách (phút)</label><input id="rHead" type="number" min="1" max="240" value="${r.headway_min}"></div>
      <div class="field"><label>Giờ đầu</label><input id="rFirst" type="time" value="${esc(r.first_departure)}"></div>
      <div class="field"><label>Giờ cuối</label><input id="rLast" type="time" value="${esc(r.last_departure)}"></div>
      <button class="btn primary" id="saveInfo">Lưu thông tin</button>
    </div>
    <p class="hint">Đổi giãn cách hoặc giờ đầu/cuối sẽ sinh lại toàn bộ danh sách giờ xuất bến. Giãn cách cũng quyết định thời gian chờ khi chuyển tuyến (= giãn cách / 2).</p>
    <div class="subtabs">
      <button data-sub="stops">Trạm theo thứ tự</button><button data-sub="seg">Trọng số các đoạn</button><button data-sub="dep">Giờ xuất bến</button>
    </div>
    <div id="subBody"></div>`;
  $$('.subtabs button', box).forEach((b) => {
    b.classList.toggle('active', b.dataset.sub === sub);
    b.onclick = () => openRoute(code, b.dataset.sub);
  });
  $('#delRoute').onclick = guard(async () => {
    if (!confirm(`Xóa tuyến ${code} và toàn bộ cạnh CONNECTS_TO của tuyến?`)) return;
    await api('DELETE', `/api/routes/${encodeURIComponent(code)}`);
    state.selectedRoute = null; $('#routeDetail').innerHTML = '<p class="muted pad">Đã xóa tuyến.</p>';
    toast('Đã xóa tuyến'); await refreshAll();
  });
  $('#saveInfo').onclick = guard(async () => {
    await api('PUT', `/api/routes/${encodeURIComponent(code)}`, {
      name: $('#rName').value.trim(), headway_min: +$('#rHead').value,
      first_departure: $('#rFirst').value, last_departure: $('#rLast').value,
    });
    toast('Đã lưu thông tin tuyến'); await refreshAll(); openRoute(code, sub);
  });

  const body = $('#subBody');
  if (sub === 'stops') {
    body.innerHTML = '<div id="edStops"></div><div class="dlg-actions" style="justify-content:flex-start"><button class="btn primary" id="saveStops">Lưu danh sách trạm</button></div><p class="hint">Trọng số của các cặp trạm đã có được giữ nguyên; cặp trạm mới tự ước lượng từ tọa độ.</p>';
    routeEd = stopsEditor($('#edStops'), r.stops.map((s) => s.id));
    $('#saveStops').onclick = guard(async () => {
      await api('PUT', `/api/routes/${encodeURIComponent(code)}`, { stops: routeEd.get() });
      toast('Đã cập nhật các trạm của tuyến'); await refreshAll(); openRoute(code, 'stops');
    });
  } else if (sub === 'seg') {
    body.innerHTML = `<table class="table seg-table"><thead><tr><th>Từ trạm</th><th>Đến trạm</th><th>Khoảng cách (km)</th><th>Thời gian (phút)</th><th></th></tr></thead><tbody>${
      r.segments.map((s, i) => `<tr><td>${esc(s.from_name)}</td><td>${esc(s.to_name)}</td>
        <td><input type="number" step="0.01" min="0.01" value="${s.distance_km}" data-d="${i}"></td>
        <td><input type="number" step="0.1" min="0.1" value="${s.time_min}" data-t="${i}"></td>
        <td class="act"><button class="btn small" data-save="${i}">Lưu</button></td></tr>`).join('')}</tbody></table>
      <p class="hint">Trọng số áp dụng cho cả hai chiều của đoạn đường.</p>`;
    body.onclick = guard(async (e) => {
      const b = e.target.closest('[data-save]'); if (!b) return;
      const i = +b.dataset.save, s = r.segments[i];
      await api('PUT', `/api/routes/${encodeURIComponent(code)}/segments`, {
        from_id: s.from_id, to_id: s.to_id, distance_km: +$(`[data-d="${i}"]`).value, time_min: +$(`[data-t="${i}"]`).value,
      });
      toast('Đã lưu trọng số'); await loadStats();
    });
  } else {
    const col = (dir, title, list) => `<div><h4>${title} <span class="muted">(${list.length} chuyến)</span></h4>
      <div class="chips">${list.map((t) => `<span class="dep">${t}<button data-rm="${dir}|${t}" title="Xóa">×</button></span>`).join('') || '<span class="muted">Chưa có</span>'}</div>
      <div class="addrow"><input type="time" id="new_${dir}"><button class="btn" data-add="${dir}">Thêm giờ</button></div></div>`;
    body.innerHTML = `<div class="dep-cols">${col('out', 'Lượt đi', r.departures_out || [])}${col('in', 'Lượt về', r.departures_in || [])}</div>`;
    body.onclick = guard(async (e) => {
      const rm = e.target.closest('[data-rm]'), add = e.target.closest('[data-add]');
      if (rm) {
        const [dir, t] = rm.dataset.rm.split('|');
        await api('DELETE', `/api/routes/${encodeURIComponent(code)}/departures?direction=${dir}&time=${encodeURIComponent(t)}`);
        openRoute(code, 'dep');
      } else if (add) {
        const dir = add.dataset.add, v = $('#new_' + dir).value;
        if (!v) return toast('Hãy chọn giờ', true);
        await api('POST', `/api/routes/${encodeURIComponent(code)}/departures`, { direction: dir, time: v });
        toast('Đã thêm giờ xuất bến'); openRoute(code, 'dep');
      }
    });
  }
});

let newRouteEd;
$('#addRoute').onclick = () => {
  $('#routeForm').reset();
  newRouteEd = stopsEditor($('#newRouteStops'), []);
  $('#routeDlg').showModal();
};
$('#routeForm').addEventListener('submit', guard(async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = {
    code: f.code.value.trim(), name: f.name.value.trim(), headway_min: +f.headway_min.value,
    first_departure: f.first_departure.value, last_departure: f.last_departure.value,
    color: f.color.value, stops: newRouteEd.get(),
  };
  await api('POST', '/api/routes', body);
  $('#routeDlg').close(); toast(`Đã tạo tuyến ${body.code}`);
  await refreshAll(); openRoute(body.code);
}));

/* ---------------------------------------------------------------- bắt đầu */
(async function init() {
  try {
    await api('GET', '/api/health');
    await refreshAll();
  } catch (e) {
    const b = $('#banner'); b.hidden = false;
    b.innerHTML = `<b>Chưa kết nối được cơ sở dữ liệu.</b> ${esc(e.message)}<br>Hãy kiểm tra Neo4j Desktop đã Start, file <code>.env</code> đúng mật khẩu, và đã chạy <code>python seed/seed.py</code>.`;
  }
})();
