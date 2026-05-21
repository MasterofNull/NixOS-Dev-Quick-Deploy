// dashboard.js — AI Command Center client logic
// All API schemas validated against live endpoints 2026-05-21.
'use strict';

// ─── CONFIG ────────────────────────────────────────────────────────────────
const BASE   = '';
const T_FAST = 8000;
const T_SLOW = 25000;

// ─── STATE ─────────────────────────────────────────────────────────────────
let activeLens = 'overview';
const lazyLoaded  = new Set();
const histCpu     = [], histGpu = [], histMem = [], histNet = [];
window._layerData = {};
window._aiMetrics = null;   // cached /ai/metrics

// ─── CORE FETCH ─────────────────────────────────────────────────────────────
async function apiFetch(path, opts = {}, ms = T_FAST) {
  const ctrl  = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(`${BASE}/api${path}`, { ...opts, signal: ctrl.signal, cache: 'no-store' });
    if (!r.ok) return null;
    const ct = r.headers.get('content-type') || '';
    if (!ct.includes('json')) return null;   // skip Prometheus text etc.
    return await r.json();
  } catch { return null; }
  finally { clearTimeout(timer); }
}

// ─── DOM HELPERS ────────────────────────────────────────────────────────────
function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v ?? '--'; }
function setHtml(id, h) { const el = document.getElementById(id); if (el) el.innerHTML = h; }
function setColor(id, cls) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('ok', 'warn', 'err', 'cy', 'info');
  if (cls) el.classList.add(cls);
}

// ─── FORMATTERS ─────────────────────────────────────────────────────────────
const pct     = v  => v != null ? `${Math.round(v)}%`             : '--';
const pctF    = v  => v != null ? `${(v * 100).toFixed(1)}%`      : '--';
const pctD    = v  => v != null ? `${v.toFixed(1)}%`              : '--';
const bytes   = b  => b == null ? '--' : b > 1e9 ? `${(b/1e9).toFixed(1)}GB`
                                       : b > 1e6 ? `${(b/1e6).toFixed(0)}MB`
                                       : `${(b/1e3).toFixed(0)}KB`;
const ms2s    = ms => ms != null ? `${(ms/1000).toFixed(1)}s` : '--';
const relTime = iso => {
  if (!iso) return '--';
  const d = new Date(iso), now = Date.now(), diff = Math.round((now - d)/1000);
  if (diff < 60)  return `${diff}s ago`;
  if (diff < 3600) return `${Math.round(diff/60)}m ago`;
  if (diff < 86400) return `${Math.round(diff/3600)}h ago`;
  return d.toLocaleDateString();
};
const statusColor = s => {
  if (!s) return 'info';
  const sl = String(s).toLowerCase();
  if (['online','running','healthy','ok','active','pass','true','operational'].some(k => sl.includes(k))) return 'ok';
  if (['degraded','warn','pending','partial'].some(k => sl.includes(k)))                                   return 'warn';
  if (['offline','down','error','fail','false','critical'].some(k => sl.includes(k)))                      return 'err';
  return 'info';
};

function fwRow(k, v, cls = '') {
  const c = cls || statusColor(v);
  return `<div class="fw-row"><span class="fk">${k}</span><span class="fv ${c}">${v ?? '--'}</span></div>`;
}
function cardBadge(text, cls = 'badge-info') {
  return `<span class="card-badge ${cls}">${text}</span>`;
}

// ─── SPARKLINES ─────────────────────────────────────────────────────────────
function pushHist(arr, v) { arr.push(v); if (arr.length > 40) arr.shift(); }
function sparkPath(arr, w = 200, h = 28) {
  if (arr.length < 2) return `M0,${h/2} L${w},${h/2}`;
  const mx = Math.max(...arr, 1), mn = Math.min(...arr);
  const pts = arr.map((v, i) => {
    const x = (i / (arr.length - 1)) * w;
    const y = h - ((v - mn) / ((mx - mn) || 1)) * (h - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return 'M' + pts.join(' L');
}
function updateSpark(svgId, arr) {
  const el = document.getElementById(svgId);
  if (!el) return;
  const p = el.querySelector('path');
  if (p) p.setAttribute('d', sparkPath(arr));
}

// ─── LENS MANAGEMENT ─────────────────────────────────────────────────────────
function setLens(id) {
  activeLens = id;
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('on'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
  const panel = document.getElementById('panel-' + id);
  const tab   = document.getElementById('tab-' + id);
  if (panel) panel.classList.add('on');
  if (tab)   tab.classList.add('on');
  if (!lazyLoaded.has(id)) { lazyLoaded.add(id); loadLens(id); }
}
function loadLens(id) {
  if      (id === 'overview')     {} // already loaded on init
  else if (id === 'intelligence') loadIntelligence();
  else if (id === 'security')     loadSecurity();
  else if (id === 'operations')   loadOperations();
  else if (id === 'map')          initTopo();
  else if (id === 'logic')        initLogic();
  else if (id === 'logs')         loadLogs();
}
function toggleDrawer() { document.getElementById('drawer').classList.toggle('open'); }

// ─── KPI RIBBON ──────────────────────────────────────────────────────────────
async function loadKPIs() {
  const [metrics, aiM] = await Promise.all([
    apiFetch('/metrics'),
    apiFetch('/ai/metrics'),
  ]);
  window._aiMetrics = aiM;

  if (metrics) {
    const localPct = metrics.llm_routing_local_pct;
    const evalPct  = metrics.eval_latest_pct;
    const cacheHit = metrics.embedding_cache_hit_rate_pct;
    const hintPct  = metrics.hint_adoption_pct;
    setText('kpiLocalPct', pct(localPct));
    setText('kpiCacheHit', pct(cacheHit));
    setText('kpiEval',     pct(evalPct));
    setText('kpiHintPct',  pct(hintPct));
    // KPI ribbon coloring — lower values are concerning here (inverted thresholds)
    if (localPct != null) setColor('kpiLocalPct', localPct < 20 ? 'err' : localPct < 50 ? 'warn' : 'ok');
    if (evalPct  != null) setColor('kpiEval',     evalPct  < 50 ? 'err' : evalPct  < 70 ? 'warn' : 'ok');
    if (cacheHit != null) setColor('kpiCacheHit', cacheHit < 20 ? 'warn' : 'ok');
    // Color header health score
    const scoreEl = document.getElementById('healthScore');
    if (scoreEl && evalPct != null) {
      scoreEl.classList.remove('warn', 'err');
      if (evalPct < 50) scoreEl.classList.add('err');
      else if (evalPct < 70) scoreEl.classList.add('warn');
    }
  }
  if (aiM) {
    const ip = aiM.infra_probes || {};
    const kb = aiM.knowledge_base || {};
    const sv = aiM.services || {};
    const redisOk = ip.redis_ping_ok; const pgOk = ip.postgres_query_ok;
    setText('kpiRedis',    redisOk === true ? 'OK' : redisOk === false ? 'ERR' : '--');
    setText('kpiPg',       pgOk    === true ? 'OK' : pgOk    === false ? 'ERR' : '--');
    setColor('kpiRedis',   redisOk === true ? 'ok' : redisOk === false ? 'err' : 'info');
    setColor('kpiPg',      pgOk    === true ? 'ok' : pgOk    === false ? 'err' : 'info');
    const qdStatus = (sv.qdrant || {}).status || '';
    setText('kpiQdrant', qdStatus || '--');
    setColor('kpiQdrant', statusColor(qdStatus));
    setText('kpiVectors',  kb.total_points != null ? kb.total_points.toLocaleString() : '--');
    const hc = sv.hybrid_coordinator || sv.hybrid || {};
    setText('kpiCoord', hc.status || '--');
    setColor('kpiCoord', statusColor(hc.status));
    // DB latencies in ribbon
    const dbm = aiM.database_metrics || {};
    const pgLat = (dbm.postgresql || {}).latency_ms;
    const rdLat = (dbm.redis || {}).latency_ms;
    if (pgLat != null) { setText('kpiPgLat', `${pgLat.toFixed(0)}ms`); setColor('kpiPgLat', pgLat > 500 ? 'err' : pgLat > 200 ? 'warn' : 'ok'); }
    if (rdLat != null) { setText('kpiRedisLat', `${rdLat.toFixed(1)}ms`); setColor('kpiRedisLat', rdLat > 50 ? 'warn' : 'ok'); }
    // Token savings
    const eff = aiM.effectiveness || {};
    const tokSaved = eff.estimated_tokens_saved;
    if (tokSaved != null) setText('kpiTokSaved', tokSaved > 1000 ? `${(tokSaved/1000).toFixed(0)}k` : String(tokSaved));
  }
  setText('lastUpdate', new Date().toLocaleTimeString());
}

// ─── RAG QUALITY (always visible, aq-qa 60.7.3 contract) ─────────────────────
async function loadRagQuality() {
  const d = await apiFetch('/eval/trend');
  const r = (d && d.ragas_metrics) ? d.ragas_metrics : {};
  const p = v => (v != null && v > 0) ? `${(v * 100).toFixed(1)}%` : '--';
  setText('ragAnswerRelevance',  p(r.answer_relevance_avg));
  setText('ragContextPrecision', p(r.context_precision_avg));
  setText('ragFaithfulness',     p(r.faithfulness_avg));
  setText('ragSampleCount',      r.sample_count != null ? r.sample_count : '--');
  // Mirror into intelligence eval card
  setText('evalAR',      p(r.answer_relevance_avg));
  setText('evalCP',      p(r.context_precision_avg));
  setText('evalFaith',   p(r.faithfulness_avg));
  setText('evalSamples', r.sample_count != null ? r.sample_count : '--');
  if (d) setText('evalRunCount', d.count ?? '--');
}

// ─── OVERVIEW: SYSTEM STATS ───────────────────────────────────────────────────
async function loadSystem() {
  const [sys, metrics] = await Promise.all([
    apiFetch('/metrics/system'),
    apiFetch('/metrics'),
  ]);
  if (sys) {
    const cpu = sys.cpu || {}, mem = sys.memory || {}, dsk = sys.disk || {};
    const gpu = sys.gpu || {}, net = sys.network || {};
    const cpuPct = cpu.usage_percent; const memPct = mem.percent; const dskPct = dsk.percent;
    const gpuPct = gpu.busy_percent;

    if (cpuPct != null) { setText('vCpu', pctD(cpuPct)); pushHist(histCpu, cpuPct); updateSpark('spCpu', histCpu); colorStatTile('statCpu', cpuPct, 75, 90, 'spCpu'); }
    if (gpuPct != null) { setText('vGpu', pctD(gpuPct)); pushHist(histGpu, gpuPct); updateSpark('spGpu', histGpu); colorStatTile('statGpu', gpuPct, 80, 95, 'spGpu'); }
    if (memPct != null) { setText('vMem', pctD(memPct)); pushHist(histMem, memPct); updateSpark('spMem', histMem); colorStatTile('statMem', memPct, 80, 92, 'spMem'); }
    if (dskPct != null) { setText('vDisk', pctD(dskPct)); colorStatTile('statDisk', dskPct, 82, 94); }
    const connCount = net.active_connections ?? 0;
    const netMB = net.bytes_sent != null ? ((net.bytes_sent + net.bytes_recv) / 1e6).toFixed(0) + 'MB' : '--';
    setText('vNet', netMB);
    pushHist(histNet, connCount); updateSpark('spNet', histNet);
    setText('vConnections', net.active_connections ?? '--');
    setText('cpuModel',  cpu.model ? cpu.model.replace(/\s+/g, ' ').trim() : '--');
    const tempStr = cpu.temperature || '';
    const tempRaw = parseFloat(tempStr) || null;
    setText('cpuTemp', tempStr || '--');
    if (tempRaw) colorStatTile('statTemp', tempRaw, 75, 90);
    setText('cpuCores',  cpu.count ?? '--');
    setText('gpuName',   gpu.name ? gpu.name.split(']').pop().trim() : '--');
    setText('gpuVram',   gpu.vram_used_mb && gpu.vram_total_mb ? `${gpu.vram_used_mb}/${gpu.vram_total_mb} MB` : '--');
    setText('memUsed',   mem.used  ? bytes(mem.used)  : '--');
    setText('memTotal',  mem.total ? bytes(mem.total) : '--');
    setText('dskFree',   dsk.free  ? bytes(dsk.free)  : '--');
    setText('dskTotal',  dsk.total ? bytes(dsk.total) : '--');
    // Uptime
    if (sys.uptime != null) {
      const u = sys.uptime, h = Math.floor(u / 3600), m = Math.floor((u % 3600) / 60);
      setText('vUptime', `${h}h ${m}m`);
      setText('kpiUptime', `${h}h`);
    }
    // Load average
    const la = sys.load_average || {};
    if (la.one != null) {
      setText('vLoad1', la.one.toFixed(2));
      setText('vLoad5', la.five != null ? la.five.toFixed(2) : '--');
      setText('vLoad15', la.fifteen != null ? la.fifteen.toFixed(2) : '--');
      const cores = cpu.count || 1;
      const loadPct = (la.one / cores) * 100;
      const loadEl = document.getElementById('statLoad');
      if (loadEl) { loadEl.classList.remove('load-warn','load-err'); if (loadPct > 100) loadEl.classList.add('load-err'); else if (loadPct > 75) loadEl.classList.add('load-warn'); }
    }
    if (sys.hostname) setText('hostname', sys.hostname);
    else if (cpu.arch) setText('hostname', `${cpu.arch} · ${cpu.count ?? '?'} cores`);
    renderAlerts({ cpuPct, gpuPct, memPct, dskPct, tempRaw });
  }
  if (metrics) {
    setText('kpiLocalPct', pct(metrics.llm_routing_local_pct));
    const evalPct = metrics.eval_latest_pct;
    if (evalPct != null) {
      setText('vStack', pct(evalPct));
      colorStatTile('statEval', evalPct, 70, 50);  // inverted: low score = bad
    }
  }
}

// ─── ALERT RENDERER ──────────────────────────────────────────────────────────
function renderAlerts({ cpuPct, gpuPct, memPct, dskPct, tempRaw }) {
  const el = document.getElementById('alertItems');
  if (!el) return;
  const alerts = [];
  const check = (label, val, w, e) => {
    if (val == null) return;
    if (val >= e) alerts.push({ cls: 'err', sev: 'ERR',  label, val: `${val.toFixed(1)}%` });
    else if (val >= w) alerts.push({ cls: 'warn', sev: 'WARN', label, val: `${val.toFixed(1)}%` });
  };
  check('CPU',  cpuPct, 75, 90);
  check('GPU',  gpuPct, 80, 95);
  check('MEM',  memPct, 80, 92);
  check('DISK', dskPct, 82, 94);
  if (tempRaw != null) {
    if (tempRaw >= 90) alerts.push({ cls: 'err',  sev: 'ERR',  label: 'TEMP', val: `${tempRaw}°C` });
    else if (tempRaw >= 75) alerts.push({ cls: 'warn', sev: 'WARN', label: 'TEMP', val: `${tempRaw}°C` });
  }
  if (!alerts.length) {
    el.innerHTML = '<span style="color:var(--fg3);font-size:.6rem">Nominal</span>';
    return;
  }
  el.innerHTML = alerts.map(a =>
    `<div class="deck-alert ${a.cls}">
      <span class="deck-alert-sev" style="color:${a.cls === 'err' ? 'var(--red)' : 'var(--yel)'}">${a.sev}</span>
      <span class="deck-alert-msg">${a.label}</span>
      <span class="deck-alert-meta">${a.val}</span>
    </div>`
  ).join('');
}

// ─── DYNAMIC COLORING HELPERS ────────────────────────────────────────────────
function deckClass(v, w, e) { return v >= e ? 'err' : v >= w ? 'warn' : 'ok'; }

function colorStatTile(id, v, warnT = 70, errT = 90, sparkId = null) {
  const el = document.getElementById(id);
  if (!el) return;
  const cls = deckClass(v, warnT, errT);
  el.classList.remove('ok', 'warn', 'err', 'cy');
  el.classList.add(cls === 'ok' ? 'cy' : cls);   // keep 'cy' for nominal
  if (sparkId) {
    const sp = document.getElementById(sparkId);
    if (sp) { sp.classList.remove('warn', 'err'); if (cls !== 'ok') sp.classList.add(cls); }
  }
}

// ─── OVERVIEW: AI SERVICES ────────────────────────────────────────────────────
async function loadServices() {
  const [svc, aiM] = await Promise.all([
    apiFetch('/services'),
    window._aiMetrics ? Promise.resolve(window._aiMetrics) : apiFetch('/ai/metrics'),
  ]);
  const grid = document.getElementById('svcGrid');
  if (!grid) return;
  const services = Array.isArray(svc) ? svc : [];
  const aiSvcs   = (aiM && aiM.services) ? aiM.services : {};

  const up = services.filter(s => s.status === 'running').length;
  const degraded = services.filter(s => s.status === 'degraded').length;
  setText('svcCount', `${up}/${services.length}`);
  const svcBadge = document.getElementById('svcCount');
  if (svcBadge) svcBadge.className = `card-badge ${up === services.length ? 'badge-ok' : degraded > 0 ? 'badge-warn' : 'badge-err'}`;

  // Build port map from ai/metrics.services (keyed by service name like 'aidb', 'hybrid_coordinator')
  const portMap = {};
  Object.entries(aiSvcs).forEach(([k, v]) => { if (v && v.port) { portMap[k] = v.port; portMap[v.service || ''] = v.port; } });
  // Known port mappings by id
  const knownPorts = { 'ai-aidb': 8002, 'ai-hybrid-coordinator': 8003, 'ai-switchboard': 8085, 'llama-cpp': 8080, 'llama-embed': 8081, 'command-center-dashboard-api': 8889 };
  const cleanName = id => id.replace(/^ai-/, '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  grid.innerHTML = services.map(s => {
    const ok  = s.status === 'running';
    const col = ok ? 'var(--grn)' : (s.status === 'degraded' ? 'var(--yel)' : 'var(--red)');
    const port = portMap[s.id] || knownPorts[s.id] || '';
    return `<div class="svc">
      <div class="svc-dot" style="background:${col}; box-shadow:0 0 4px ${col}"></div>
      <span class="svc-name">${cleanName(s.id)}</span>
      <span class="svc-port">${port ? `:${port}` : ''}</span>
    </div>`;
  }).join('') || '<div style="color:var(--fg3);font-size:.62rem;padding:.5rem">No services</div>';
}

// ─── OVERVIEW: DATABASE METRICS ───────────────────────────────────────────────
async function loadDatabase() {
  const aiM = window._aiMetrics || await apiFetch('/ai/metrics');
  const el  = document.getElementById('dbDetails');
  if (!el) return;
  const dbm = (aiM && aiM.database_metrics) || {};
  const pg  = dbm.postgresql || {};
  const rd  = dbm.redis      || {};
  const qd  = dbm.qdrant     || {};
  if (!Object.keys(dbm).length) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }

  const allOk = [pg, rd, qd].every(d => ['online','healthy','ok'].includes((d.status || '').toLowerCase()));
  const badge = document.getElementById('dbBadge');
  if (badge) { badge.textContent = allOk ? 'all healthy' : 'degraded'; badge.className = `card-badge ${allOk ? 'badge-ok' : 'badge-warn'}`; }

  const latColor = ms => ms == null ? '' : ms > 500 ? 'err' : ms > 100 ? 'warn' : 'ok';
  el.innerHTML = `
    <div class="db-section">
      <div class="db-name">PostgreSQL <span class="db-pill ${statusColor(pg.status)}">${pg.status || '--'}</span></div>
      ${fwRow('Latency',  pg.latency_ms != null ? `${pg.latency_ms.toFixed(0)}ms` : '--', latColor(pg.latency_ms))}
      ${fwRow('Conns',    pg.active_connections != null ? `${pg.active_connections} active · ${pg.idle_connections ?? 0} idle` : '--')}
      ${fwRow('DB Size',  pg.database_size_bytes ? bytes(pg.database_size_bytes) : '--')}
    </div>
    <div class="db-section">
      <div class="db-name">Redis <span class="db-pill ${statusColor(rd.status)}">${rd.status || '--'}</span></div>
      ${fwRow('Latency',  rd.latency_ms != null ? `${rd.latency_ms.toFixed(1)}ms` : '--', latColor(rd.latency_ms))}
      ${fwRow('Keys',     rd.keys != null ? rd.keys.toLocaleString() : '--')}
      ${fwRow('Memory',   rd.memory_human || (rd.memory_bytes ? bytes(rd.memory_bytes) : '--'))}
      ${fwRow('Clients',  rd.connected_clients ?? '--')}
    </div>
    <div class="db-section">
      <div class="db-name">Qdrant <span class="db-pill ${statusColor(qd.status)}">${qd.status || '--'}</span></div>
      ${fwRow('Collections', qd.collection_count ?? '--')}
      ${fwRow('Vectors',     qd.total_vectors != null ? qd.total_vectors.toLocaleString() : '--')}
    </div>`;
}

// ─── OVERVIEW: OSI HEALTH ─────────────────────────────────────────────────────
async function loadOSI() {
  const data = await apiFetch('/health/layered', {}, T_SLOW);
  const badge = document.getElementById('osiBadge');
  if (!data) { if (badge) badge.textContent = 'unavailable'; return; }

  if (data.pending) {
    if (badge) { badge.textContent = 'pending'; badge.className = 'card-badge badge-warn'; }
    setText('osiScore', 'pending');
    setHtml('checkList', `<div style="color:var(--fg3);font-size:.62rem;padding:.75rem">${data.message || 'Run aq-qa to populate layer health.'} <button class="mini-btn" onclick="forceLayerRefresh()">Run Now</button></div>`);
    return;
  }

  const passed = data.passed || 0, total = passed + (data.failed || 0);
  const score  = total ? Math.round((passed / total) * 100) : 0;
  setText('healthScore', score);
  setText('osiScore', `${passed}/${total}`);
  if (badge) { badge.className = `card-badge ${data.failed ? 'badge-err' : 'badge-ok'}`; badge.textContent = data.failed ? `${data.failed} fail` : 'all pass'; }

  window._layerData = data.layers || {};
  for (let i = 0; i <= 7; i++) {
    const checks = (data.layers || {})[String(i)] || [];
    const lp     = checks.filter(c => c.status === 'PASS').length;
    const el     = document.getElementById('ls' + i);
    const tile   = el ? el.closest('.layer') : null;
    if (el) { el.textContent = `${lp}/${checks.length}`; el.style.color = lp === checks.length ? 'var(--grn)' : lp === 0 ? 'var(--red)' : 'var(--yel)'; }
    if (tile) { tile.classList.remove('ok','err','warn'); tile.classList.add(lp === checks.length ? 'ok' : 'err'); }
  }
}

function drillLayer(id) {
  const checks = (window._layerData || {})[id] || [];
  const el = document.getElementById('checkList');
  if (!el) return;
  el.innerHTML = checks.length
    ? checks.map(c => {
        const cls = c.status === 'PASS' ? 'pass' : c.status === 'SKIP' ? 'skip' : 'fail';
        const col = cls === 'pass' ? 'var(--grn)' : cls === 'skip' ? 'var(--yel)' : 'var(--red)';
        return `<div class="check-item ${cls}">
          <span class="ci-status" style="color:${col}">${c.status}</span>
          <span class="ci-id">${c.id}</span>
          <span class="ci-desc">${c.description || ''}</span>
        </div>`;
      }).join('')
    : '<div style="color:var(--fg3);font-size:.62rem;padding:.5rem">No checks for this layer.</div>';
}

// ─── OVERVIEW: ISSUES / AUDIT ─────────────────────────────────────────────────
async function loadRemediations() {
  const d = await apiFetch('/ai/remediation/latest');
  const el = document.getElementById('remediationList');
  if (!el) return;
  // Schema: {status, timestamp} when no active remediation; or {issues:[...]} when active
  const items = Array.isArray(d) ? d : (d && Array.isArray(d.issues) ? d.issues : []);
  const statusMsg = d && d.status ? d.status.replace(/_/g, ' ') : null;
  const badge = document.getElementById('remedBadge');
  if (badge) { badge.textContent = `${items.length} issue${items.length !== 1 ? 's' : ''}`; badge.className = `card-badge ${items.length ? 'badge-warn' : 'badge-ok'}`; }
  if (!items.length && statusMsg) {
    el.innerHTML = `<div style="color:var(--grn);font-size:.62rem;padding:.4rem">${statusMsg}</div>`;
    return;
  }
  el.innerHTML = items.slice(0, 12).map(i =>
    `<div class="check-item ${i.severity === 'critical' ? 'fail' : 'skip'}">
      <span class="ci-status" style="color:${i.severity === 'critical' ? 'var(--red)' : 'var(--yel)'}">${(i.severity || 'warn').toUpperCase()}</span>
      <span class="ci-id">${i.id || '--'}</span>
      <span class="ci-desc">${i.description || i.message || ''}</span>
    </div>`
  ).join('') || '<div style="color:var(--fg3);font-size:.62rem;padding:.5rem">No open issues.</div>';
}

async function loadAuditLog() {
  const d  = await apiFetch('/audit/operator/events');
  const el = document.getElementById('auditList');
  if (!el) return;
  const events = Array.isArray(d) ? d : (d && d.events ? d.events : []);
  // Verify chain integrity: each event should have prev_hash pointing to previous hash
  const chainOk = events.length > 1 ? events.slice(1).every((e, i) => e.prev_hash === events[i].hash) : true;
  const chainBadge = chainOk
    ? `<span style="color:var(--grn);font-size:.55rem">✓ chain intact</span>`
    : `<span style="color:var(--yel);font-size:.55rem">⚠ chain gap</span>`;
  const header = events.length ? `<div style="font-size:.56rem;color:var(--fg3);margin-bottom:.3rem;display:flex;gap:.6rem">
    <span>${events.length} events</span>${chainBadge}
    ${d.path ? `<span style="overflow:hidden;text-overflow:ellipsis;max-width:160px" title="${d.path}">${d.path.split('/').pop()}</span>` : ''}
  </div>` : '';
  el.innerHTML = header + (events.slice(0, 10).map(e => {
    const cat = e.category || '';
    const catColor = cat === 'mutation' ? 'var(--yel)' : cat === 'disabled' ? 'var(--fg3)' : 'var(--fg3)';
    return `<div class="check-item pass">
      <span class="ci-status" style="color:${catColor};width:44px">${relTime(e.ts || e.timestamp || e.created_at)}</span>
      <span class="ci-id">${e.method ? `${e.method} ` : ''}${e.path || e.action || '--'}</span>
      <span class="ci-desc" style="color:${e.status_code >= 400 ? 'var(--red)' : 'var(--fg3)'}">${e.status_code || e.message || ''}</span>
    </div>`;
  }).join('') || '<div style="color:var(--fg3);font-size:.62rem;padding:.5rem">No recent audit events.</div>');
}

// ─── INTELLIGENCE: COORDINATOR ────────────────────────────────────────────────
async function loadCoordinator() {
  const [aiM, rts] = await Promise.all([
    window._aiMetrics ? Promise.resolve(window._aiMetrics) : apiFetch('/ai/metrics'),
    apiFetch('/aistack/advanced/runtime-summary'),
  ]);
  const el = document.getElementById('coordMetrics');
  if (!el) return;
  const sv  = (aiM && aiM.services) || {};
  const hc  = sv.hybrid_coordinator || sv.hybrid || {};
  const eff = (aiM && aiM.effectiveness) || {};
  const sum = (rts && rts.summary) || {};
  setText('coordStatus', hc.status || '--');
  el.innerHTML = [
    fwRow('Status',       hc.status  || '--'),
    fwRow('Port',         hc.port    ? `:${hc.port}` : '--', 'info'),
    fwRow('Local Query%', eff.local_query_percentage != null ? pctD(eff.local_query_percentage) : '--'),
    fwRow('Tokens Saved', eff.estimated_tokens_saved != null ? eff.estimated_tokens_saved.toLocaleString() : '--'),
    fwRow('Vectors',      eff.knowledge_base_vectors  != null ? eff.knowledge_base_vectors.toLocaleString() : '--'),
    fwRow('Offloading',   (sum.offloading || {}).status || '--'),
    fwRow('Context Eff.', (sum.context_efficiency || {}).status || '--'),
    fwRow('Cap Gaps',     (sum.capability_gap || {}).gaps_detected ?? '--'),
  ].join('');
}

// ─── INTELLIGENCE: TASK ROUTING ───────────────────────────────────────────────
async function loadRouting() {
  const d = await apiFetch('/aistack/task-classification/stats');
  const tbody = document.getElementById('routeBody');
  if (!tbody) return;
  if (!d) { tbody.innerHTML = '<tr><td colspan="3" style="color:var(--fg3)">Unavailable</td></tr>'; return; }
  setText('routeTotal',  d.total_classified ?? 0);
  setText('routeLocalP', d.local_pct != null ? pctD(d.local_pct) : '--');
  const types = d.by_task_type || {};
  const recent = d.recent_decisions || [];
  const rows = Object.entries(types).length
    ? Object.entries(types).map(([k, v]) =>
        `<tr><td>${k}</td><td>${typeof v === 'object' ? (v.backend || '--') : '--'}</td><td>${typeof v === 'object' ? (v.count ?? v) : v}</td></tr>`)
    : recent.slice(0, 10).map(r =>
        `<tr><td>${r.task_type || '--'}</td><td>${r.route || r.backend || '--'}</td><td>${relTime(r.timestamp)}</td></tr>`);
  tbody.innerHTML = rows.join('') || '<tr><td colspan="3" style="color:var(--fg3)">No classifications yet</td></tr>';
}

// ─── INTELLIGENCE: MODELS ─────────────────────────────────────────────────────
async function loadModels() {
  const d = await apiFetch('/models');
  const el = document.getElementById('modelList');
  if (!el) return;
  if (!d) { el.innerHTML = '<div style="color:var(--fg3);font-size:.62rem">Unavailable</div>'; return; }
  const models = Array.isArray(d) ? d : (d.models || []);
  setText('mlBadge', `${models.length}`);
  el.innerHTML = models.map(m => {
    const sc  = m.state === 'active' ? 'ms-active' : m.state === 'downloading' ? 'ms-dl' : m.state === 'verified' ? 'ms-ok' : 'ms-av';
    const fe  = m.file_exists;
    const disk = fe === true ? ' ✓' : fe === false ? ' ✗' : '';
    return `<div class="model-row">
      <span class="model-state ${sc}">${m.state || 'available'}</span>
      <span class="model-name">${m.name || m.id}</span>
      <span class="model-size">${m.size_gb ? m.size_gb + 'GB' : ''}${disk}</span>
      <span class="model-actions">
        ${m.state !== 'active' && m.state !== 'downloading' ? `<button class="act-btn" onclick="mlPromote('${m.id}')">Promote</button>` : ''}
        ${m.state === 'downloading' ? `<button class="act-btn err" onclick="mlCancel('${m.id}')">Cancel</button>` : ''}
      </span>
    </div>`;
  }).join('') || '<div style="color:var(--fg3);font-size:.62rem;padding:.5rem">No models</div>';
}

async function mlPromote(id) {
  const r = await apiFetch(`/models/${id}/promote`, { method: 'POST' });
  if (r) { loadModels(); } else alert('Promote failed');
}
async function mlCancel(id) {
  const r = await apiFetch(`/models/${id}/cancel`, { method: 'POST' });
  if (r) loadModels();
}
async function mlRollback(id) {
  const r = await apiFetch(`/models/${id}/rollback`, { method: 'POST' });
  if (r) loadModels();
}

// ─── INTELLIGENCE: SWITCHBOARD ────────────────────────────────────────────────
async function loadSwitchboard() {
  const d = await apiFetch('/aistack/switchboard/profiles');
  const el = document.getElementById('profileList');
  if (!el) return;
  const profiles = d && d.profiles && typeof d.profiles === 'object' ? d.profiles : {};
  const names    = Object.keys(profiles);
  setText('swBadge', `${names.length}`);
  el.innerHTML = names.map(name => {
    const p = profiles[name] || {};
    return `<div class="profile-card">
      <div class="profile-name">${name}</div>
      <div class="profile-meta">${p.maxInputTokens ? `in:${p.maxInputTokens}` : ''} ${p.maxOutputTokens ? `out:${p.maxOutputTokens}` : ''} ${p.intendedUse || ''}</div>
    </div>`;
  }).join('') || '<div style="color:var(--fg3);font-size:.62rem">Unavailable</div>';
}

// ─── INTELLIGENCE: AIDB ───────────────────────────────────────────────────────
async function loadAIDB() {
  const [det, aiM] = await Promise.all([
    apiFetch('/aidb/health/detailed'),
    window._aiMetrics ? Promise.resolve(window._aiMetrics) : apiFetch('/ai/metrics'),
  ]);
  const el = document.getElementById('aidbDetails');
  if (!el) return;
  const kb = (aiM && aiM.knowledge_base) || {};
  const aidbSvc = (aiM && aiM.services && aiM.services.aidb) || {};
  const bgv = (aidbSvc.health_check && aidbSvc.health_check.background_vectorization) || {};
  const lv = (det && det.liveness) || {};
  const rd = (det && det.readiness) || {};
  setText('aidbBadge', lv.status || '--');
  const rows = [
    fwRow('Liveness',  lv.status || '--', statusColor(lv.status)),
    fwRow('Readiness', rd.status || '--', statusColor(rd.status)),
    fwRow('Startup',   det ? (det.startup_complete ? 'yes' : 'no') : '--', det && det.startup_complete ? 'ok' : 'warn'),
    fwRow('Vectors',   kb.total_points != null ? kb.total_points.toLocaleString() : '--'),
    fwRow('Real Embeddings', kb.real_embeddings_percent != null ? pctD(kb.real_embeddings_percent) : '--'),
    fwRow('Vectorize Pending', bgv.pending ?? '--', bgv.pending > 0 ? 'warn' : ''),
    fwRow('Vectorize Done/Fail', bgv.completed != null ? `${bgv.completed}/${bgv.failed ?? 0}` : '--', bgv.failed > 0 ? 'warn' : ''),
    fwRow('Vectorize Skipped', bgv.skipped ?? '--', bgv.skipped > 0 ? 'warn' : ''),
  ];
  if (kb.collections) {
    Object.entries(kb.collections).forEach(([k, v]) => rows.push(fwRow(`  ${k}`, v)));
  }
  el.innerHTML = rows.join('');
}

// ─── INTELLIGENCE: LEARNING ───────────────────────────────────────────────────
async function loadLearning() {
  const d  = await apiFetch('/stats/learning');
  const el = document.getElementById('learningDetails');
  const al = document.getElementById('learningActivity');
  const badge = document.getElementById('learningBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const bp  = d.backpressure || {};
  const act = d.activity || {};
  const paused = bp.paused || d.learning_paused;
  if (badge) { badge.textContent = paused ? 'paused' : 'active'; badge.className = `card-badge ${paused ? 'badge-warn' : 'badge-ok'}`; }

  el.innerHTML = [
    fwRow('Patterns Learned',  d.total_patterns_learned ?? 0),
    fwRow('Events Tracked',    (act.total_events ?? d.total_metrics_tracked) != null ? (act.total_events ?? d.total_metrics_tracked).toLocaleString() : '--'),
    fwRow('Finetune Records',  act.finetune_records ?? d.finetuning_dataset_size ?? '--'),
    fwRow('Avg Feedback',      act.average_feedback_score != null ? act.average_feedback_score.toFixed(3) : '--', act.average_feedback_score > 0.5 ? 'ok' : act.average_feedback_score > 0.2 ? 'warn' : 'err'),
    fwRow('Backpressure',      paused ? 'PAUSED' : 'nominal', paused ? 'warn' : 'ok'),
    fwRow('Unprocessed',       bp.unprocessed_mb != null ? `${bp.unprocessed_mb.toFixed(1)} MB` : '0 MB'),
  ].join('');

  // Activity pills: event counts per pipeline
  if (al && act.total_events) {
    const pills = [
      { k: 'AIDB', v: act.aidb_events },
      { k: 'Hybrid', v: act.hybrid_events },
      { k: 'RALPH', v: act.ralph_events },
      { k: 'Feedback', v: act.hint_feedback_events },
      { k: 'Gaps', v: act.query_gap_events },
      { k: 'High-val', v: act.high_value_events },
    ].filter(p => p.v != null);
    al.innerHTML = `<div class="act-pills">${pills.map(p =>
      `<div class="act-pill">${p.k}&nbsp;<span>${p.v.toLocaleString()}</span></div>`
    ).join('')}</div>`;
    if (act.latest_feedback_at) {
      al.innerHTML += `<div style="font-size:.56rem;color:var(--fg3);margin-top:.3rem">Last feedback: ${relTime(act.latest_feedback_at)}</div>`;
    }
  } else if (al) {
    al.innerHTML = '';
  }
}

// ─── INTELLIGENCE: DRIFT ─────────────────────────────────────────────────────
async function loadDrift() {
  const d = await apiFetch('/traces/drift');
  const el = document.getElementById('driftDetails');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Needs nixos-rebuild', 'warn'); return; }
  const stable = d.drift_score != null && d.drift_score < 0.4;
  setText('driftBadge', stable ? 'stable' : d.drift_score != null ? 'drift' : '--');
  el.innerHTML = [
    fwRow('Drift Score',    d.drift_score != null ? d.drift_score.toFixed(4) : '--', stable ? 'ok' : 'err'),
    fwRow('Intent Flip',    d.intent_flip_rate != null ? d.intent_flip_rate.toFixed(4) : '--'),
    fwRow('Latency Degrad', d.latency_degradation != null ? `${d.latency_degradation > 0 ? '+' : ''}${d.latency_degradation.toFixed(1)}ms` : '--', d.latency_degradation > 0 ? 'warn' : 'ok'),
    fwRow('Threshold',      d.alert_threshold || '0.4'),
    fwRow('Trace Count',    d.trace_count ?? '--'),
  ].join('');
}

// ─── INTELLIGENCE: VERIFIER ───────────────────────────────────────────────────
async function loadVerifier() {
  const d = await apiFetch('/aistack/verify-self/results');
  const el = document.getElementById('verifierDetails');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  el.innerHTML = [
    fwRow('Consistent',    d.consistent ? 'yes' : 'no', d.consistent ? 'ok' : 'err'),
    fwRow('Total Checks',  d.total_checks ?? '--'),
    fwRow('Stale Count',   d.stale_count  ?? '--', d.stale_count > 0 ? 'warn' : 'ok'),
    fwRow('Checked At',    relTime(d.timestamp)),
  ].join('');
}

// ─── INTELLIGENCE: KNOWLEDGE / AGENTIC ────────────────────────────────────────
async function loadKnowledge() {
  const d = await apiFetch('/aistack/knowledge/observatory', {}, T_SLOW);
  const el  = document.getElementById('knowledgeDetails');
  const cl  = document.getElementById('collectionList');
  const badge = document.getElementById('knowledgeBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }

  const totalPts  = d.total_points ?? d.total_documents ?? 0;
  const totalColl = d.total_collections ?? d.collection_count ?? 0;
  if (badge) { badge.textContent = `${totalPts.toLocaleString()} vectors`; badge.className = 'card-badge badge-ok'; }

  el.innerHTML = [
    fwRow('Collections',    totalColl),
    fwRow('Total Vectors',  totalPts.toLocaleString()),
    fwRow('Active',         d.active_collections ?? '--'),
  ].join('');

  // Collections breakdown table
  const colls = Array.isArray(d.collections) ? d.collections : [];
  if (cl && colls.length) {
    const maxPts = Math.max(...colls.map(c => c.points || 0), 1);
    const typeClass = t => t === 'memory' ? 'coll-type-mem' : t === 'training' ? 'coll-type-train' : 'coll-type-know';
    cl.innerHTML = `<table class="coll-table">
      <thead><tr><th>Collection</th><th>Type</th><th>Vectors</th><th></th></tr></thead>
      <tbody>${colls.map(c => {
        const pct = Math.round(((c.points || 0) / maxPts) * 100);
        return `<tr>
          <td style="color:var(--fg)">${c.label || c.name}</td>
          <td class="${typeClass(c.type)}">${c.type || '--'}</td>
          <td style="color:var(--fg2)">${(c.points || 0).toLocaleString()}</td>
          <td><div class="coll-bar-wrap"><div class="coll-bar" style="width:${pct}%"></div></div></td>
        </tr>`;
      }).join('')}</tbody>
    </table>`;
  } else if (cl) {
    cl.innerHTML = '';
  }
}

async function loadAgentic() {
  const d = await apiFetch('/aistack/model-optimization/readiness');
  const el = document.getElementById('agenticDetails');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const rd = d.readiness || {};
  const items = Object.entries(rd).map(([k, v]) => {
    const st = typeof v === 'object' ? v.status : v;
    return fwRow(k.replace(/_/g, ' '), st, statusColor(st));
  });
  el.innerHTML = items.join('') || fwRow('Status', 'No data');
  const next = d.next_steps || [];
  if (next.length) {
    el.innerHTML += `<div style="margin-top:.5rem;font-size:.58rem;color:var(--fg3)">Next: ${next.slice(0,2).join(', ')}</div>`;
  }
}

async function loadIntelligence() {
  await Promise.allSettled([
    loadCoordinator(), loadRouting(), loadModels(), loadSwitchboard(),
    loadAIDB(), loadLearning(), loadDrift(), loadVerifier(),
    loadKnowledge(), loadAgentic(), loadRagQuality(),
  ]);
}

// ─── SECURITY ─────────────────────────────────────────────────────────────────
async function loadFirewall() {
  const d = await apiFetch('/firewall/status');
  const el = document.getElementById('fwDetails');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  setText('fwBadge', d.enabled ? d.backend || 'enabled' : 'disabled');
  el.innerHTML = [
    fwRow('Enabled',          d.enabled ? 'yes' : 'no', d.enabled ? 'ok' : 'err'),
    fwRow('Backend',          d.backend || '--', 'info'),
    fwRow('CrowdSec',         d.crowdsec_active ? 'active' : 'inactive', d.crowdsec_active ? 'ok' : 'warn'),
    fwRow('Captive Portal',   d.captive_portal_bypass ? 'bypass ON' : 'off', d.captive_portal_bypass ? 'warn' : 'ok'),
    fwRow('Open Ports',       (d.open_ports || []).join(', ') || 'none'),
    fwRow('Interfaces',       Object.keys(d.interfaces || {}).join(', ') || '--'),
  ].join('');
}

async function loadSecMon() {
  const sys = await apiFetch('/metrics/system');
  const el  = document.getElementById('secMonitor');
  if (!el || !sys) return;
  const sec = sys.security || {};
  const fw  = sec.firewall || {};
  const mac = sec.mandatory_access_control || {};
  // Actual schema: fw.active (bool), fw.provider (str), mac.apparmor_active (bool)
  const fwActive  = fw.active ?? fw.enabled;
  const aaActive  = mac.apparmor_active;
  const net       = sys.network || {};
  el.innerHTML = [
    fwRow('Firewall Provider', fw.provider || fw.backend || '--', 'info'),
    fwRow('Firewall Active',   fwActive != null ? (fwActive ? 'yes' : 'no') : '--', fwActive ? 'ok' : 'warn'),
    fwRow('AppArmor',          aaActive != null ? (aaActive ? 'active' : 'inactive') : '--', aaActive ? 'ok' : 'warn'),
    fwRow('Active Conns',      net.active_connections ?? '--', net.active_connections > 1000 ? 'warn' : 'ok'),
    fwRow('Interface',         net.interface || '--', 'info'),
  ].join('');
}

async function loadCircuitBreakers() {
  const d  = await apiFetch('/stats/circuit-breakers');
  const el = document.getElementById('cbDetails');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const cbs = d.circuit_breakers || {};
  const entries = Object.entries(cbs);
  setText('cbBadge', `${entries.filter(([,v]) => v.state === 'open').length} open`);
  el.innerHTML = entries.length
    ? entries.map(([k, v]) => fwRow(k, v.state, statusColor(v.state))).join('')
    : fwRow('Status', 'No breakers registered', 'info');
}

async function loadHardening() {
  const d  = await apiFetch('/harness/overview');
  const el = document.getElementById('hardeningDetails');
  const sc = document.getElementById('harnessScorecard');
  const badge = document.getElementById('harnessBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const h    = d.harness || {};
  const s    = h.stats || {};
  const pl   = d.policies || {};
  const card = h.scorecard || {};
  const infe = card.inference_optimizations || {};
  const disc = card.discovery || {};
  const acc  = card.acceptance || {};
  if (badge) { badge.textContent = d.status || '--'; badge.className = `card-badge ${statusColor(d.status) === 'ok' ? 'badge-ok' : 'badge-warn'}`; }
  el.innerHTML = [
    fwRow('Status',       d.status || '--', statusColor(d.status)),
    fwRow('Scorecards',   s.scorecards_generated ?? '--', s.scorecards_generated > 0 ? 'ok' : 'info'),
    fwRow('Safety Mode',  pl.safety_mode || '--', 'info'),
    fwRow('Lesson Refs',  (s.active_lesson_refs || []).length),
  ].join('');

  // Scorecard — inference optimizations + discovery rates
  if (sc) {
    sc.innerHTML = [
      '<div style="font-size:.58rem;color:var(--fg3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:.3rem">Scorecard</div>',
      fwRow('Prompt Cache',      infe.prompt_cache_policy_enabled ? 'enabled' : 'disabled', infe.prompt_cache_policy_enabled ? 'ok' : 'warn'),
      fwRow('Spec Decoding',     infe.speculative_decoding_enabled ? 'enabled' : 'disabled', infe.speculative_decoding_enabled ? 'ok' : 'info'),
      fwRow('Ctx Compression',   infe.context_compression_enabled ? 'enabled' : 'disabled', infe.context_compression_enabled ? 'ok' : 'warn'),
      fwRow('Discovery Cache%',  disc.invoked ? pctD((disc.cache_hits / disc.invoked) * 100) : '--'),
      fwRow('Discovery Errors',  disc.errors ?? 0, disc.errors > 0 ? 'err' : 'ok'),
      fwRow('Acceptance Rate',   acc.total > 0 ? pctD(acc.pass_rate * 100) : 'no runs', acc.ok === true ? 'ok' : acc.ok === false ? 'err' : 'info'),
    ].join('');
  }
}

async function loadSecurity() {
  await Promise.allSettled([loadFirewall(), loadSecMon(), loadCircuitBreakers(), loadHardening()]);
}

// ─── OPERATIONS ───────────────────────────────────────────────────────────────
async function loadQA() {
  const d = await apiFetch('/aistack/aq-qa/run/0', {}, T_SLOW);
  const badge = document.getElementById('qaBadge');
  if (!d) { if (badge) { badge.textContent = 'ERR'; badge.className = 'card-badge badge-err'; } return; }
  if (d.pending || d.running) {
    setText('qaStatus', d.running ? 'running...' : 'pending');
    if (badge) { badge.textContent = 'pending'; badge.className = 'card-badge badge-warn'; }
    return;
  }
  setText('qaPassed',  d.passed  ?? '--');
  setText('qaFailed',  d.failed  ?? '--');
  setText('qaSkipped', d.skipped ?? '--');
  setText('qaDuration', d.duration_s ? `${d.duration_s.toFixed(1)}s` : '--');
  setText('qaStatus',  d.failed === 0 ? 'ALL PASS' : `${d.failed} FAIL`);
  if (badge) { badge.textContent = d.failed === 0 ? 'PASS' : 'FAIL'; badge.className = `card-badge ${d.failed === 0 ? 'badge-ok' : 'badge-err'}`; }
}

async function loadDeployments() {
  const d  = await apiFetch('/deployments/history');
  const el = document.getElementById('deployDetails');
  if (!el) return;
  if (!d) { el.innerHTML = '<div style="color:var(--fg3);font-size:.62rem">Unavailable</div>'; return; }
  const list = d.deployments || [];
  setText('deployBadge', `${d.total ?? list.length}`);
  el.innerHTML = list.length
    ? `<table class="route-table"><thead><tr><th>ID</th><th>Command</th><th>Status</th><th>Progress</th><th>Started</th></tr></thead><tbody>
        ${list.slice(0, 8).map(i =>
          `<tr>
            <td style="font-size:.56rem">${(i.deployment_id || '--').slice(-8)}</td>
            <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${i.command || '--'}</td>
            <td style="color:${i.status === 'success' ? 'var(--grn)' : i.status === 'running' ? 'var(--cyan)' : 'var(--red)'}">${i.status}</td>
            <td>${i.progress != null ? i.progress + '%' : '--'}</td>
            <td>${relTime(i.started_at)}</td>
          </tr>`).join('')}
      </tbody></table>`
    : '<div style="color:var(--fg3);font-size:.62rem">No deployments</div>';
}

async function loadPRSI() {
  const d  = await apiFetch('/prsi/actions');
  const el = document.getElementById('prsiList');
  if (!el) return;
  const items = (d && d.prsi && d.prsi.actions) ? d.prsi.actions : [];
  setText('prsiBadge', `${items.length}`);
  el.innerHTML = items.slice(0, 10).map(a =>
    `<div class="check-item">
      <span class="ci-id">${a.action || a.id || '--'}</span>
      <span class="ci-desc">${a.raw_action ? JSON.stringify(a.raw_action).slice(0, 60) : (a.label || '')}</span>
      <span class="ci-status" style="color:var(--fg3);font-size:.56rem">${relTime(a.created_at)}</span>
    </div>`
  ).join('') || '<div style="color:var(--fg3);font-size:.62rem;padding:.5rem">Queue empty</div>';
}

async function loadRuntimeDetails() {
  const d  = await apiFetch('/aistack/advanced/runtime-summary');
  const el = document.getElementById('runtimeDetails');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const s = d.summary || {};
  el.innerHTML = Object.entries(s).map(([k, v]) =>
    fwRow(k.replace(/_/g, ' '), typeof v === 'object' ? (v.status || JSON.stringify(v).slice(0, 40)) : v, statusColor(typeof v === 'object' ? v.status : v))
  ).join('');
}

async function loadHarnessOv() {
  const d  = await apiFetch('/harness/overview');
  const el = document.getElementById('harnessDetails');
  const badge = document.getElementById('harnessOvBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const s = (d.harness || {}).stats || {};
  const card = (d.harness || {}).scorecard || {};
  if (badge) { badge.textContent = d.status || '--'; badge.className = `card-badge ${statusColor(d.status) === 'ok' ? 'badge-ok' : 'badge-warn'}`; }
  const fails = (card.failures || {}).recent_failed_cases || [];
  el.innerHTML = [
    fwRow('Total Runs',   s.total_runs ?? 0),
    fwRow('Passed',       s.passed ?? 0, (s.passed || 0) > 0 ? 'ok' : 'info'),
    fwRow('Failed',       s.failed ?? 0, (s.failed || 0) > 0 ? 'err' : 'ok'),
    fwRow('Scorecards',   s.scorecards_generated ?? '--'),
    fwRow('Last Run',     s.last_run_at ? relTime(s.last_run_at) : 'never'),
    fwRow('Analysis',     card.failures && card.failures.analysis_ready ? 'ready' : 'no data', 'info'),
  ].join('');
  if (fails.length) {
    el.innerHTML += `<div style="margin-top:.4rem;font-size:.57rem;color:var(--red)">Recent failures: ${fails.slice(0,3).join(', ')}</div>`;
  }
}

async function loadOperations() {
  await Promise.allSettled([loadQA(), loadDeployments(), loadPRSI(), loadRuntimeDetails(), loadHarnessOv()]);
}

// ─── NEURAL MAP (D3) ──────────────────────────────────────────────────────────
async function initTopo() {
  const data = await apiFetch('/topology');
  const c    = document.getElementById('topoCanvas');
  if (!c) return;
  c.querySelectorAll('svg').forEach(s => s.remove());
  if (!data || !window.d3) { setText('topoHud', 'DATA_UNAVAILABLE'); return; }
  const w = c.clientWidth, h = c.clientHeight;
  const svg = d3.select('#topoCanvas').append('svg').attr('width','100%').attr('height','100%');
  const g   = svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.1,8]).on('zoom', e => g.attr('transform', e.transform)));
  const sim = d3.forceSimulation(data.nodes)
    .force('link',   d3.forceLink(data.edges).id(d => d.id).distance(90))
    .force('charge', d3.forceManyBody().strength(-250))
    .force('center', d3.forceCenter(w/2, h/2))
    .force('coll',   d3.forceCollide(14));
  const link = g.append('g').selectAll('line').data(data.edges).enter().append('line').attr('class','link-line');
  const node = g.append('g').selectAll('g').data(data.nodes).enter().append('g')
    .call(d3.drag()
      .on('start', (e,d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on('drag',  (e,d) => { d.fx=e.x; d.fy=e.y; })
      .on('end',   (e,d) => { if (!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }));
  node.append('circle')
    .attr('r', d => d.type === 'service' ? 10 : d.type === 'directory' ? 7 : 5)
    .attr('fill', d => d.type === 'service' ? 'var(--cyan)' : d.type === 'directory' ? 'var(--mag)' : 'var(--fg3)')
    .attr('stroke','var(--bg)').attr('stroke-width',1.5);
  node.append('text').attr('class','node-label').attr('dx',13).attr('dy','.35em').text(d => d.label || d.id);
  sim.on('tick', () => {
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
  setText('topoHud', `NODES:${data.nodes.length} EDGES:${data.edges.length}`);
}

// ─── LOGIC DAG (Mermaid) ──────────────────────────────────────────────────────
async function initLogic() {
  const data = await apiFetch('/topology/flow');
  const c    = document.getElementById('logicCanvas');
  if (!c) return;
  if (!data || !data.flowchart) { setText('logicHud', 'DATA_UNAVAILABLE'); return; }
  if (!window.mermaid) { setText('logicHud', 'MERMAID_LOADING'); setTimeout(initLogic, 1000); return; }
  try {
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose',
      themeVariables: { primaryColor: '#0d1220', primaryTextColor: '#e2eaf4',
        primaryBorderColor: '#00d9ff', lineColor: '#d400ff', background: '#080c12' }});
    const id = 'mermaid-flow';
    c.innerHTML = `<div id="${id}" style="width:100%;height:100%;overflow:auto;padding:1rem"></div>`;
    const { svg } = await mermaid.render('mermaid-svg', data.flowchart);
    document.getElementById(id).innerHTML = svg;
    setText('logicHud', 'REQUEST_FLOW: RENDERED');
  } catch (e) {
    c.innerHTML = `<pre style="color:var(--fg2);font-size:.65rem;padding:1rem;overflow:auto;height:100%">${data.flowchart}</pre>`;
    setText('logicHud', 'RAW_MERMAID');
  }
}

// ─── LOGS ─────────────────────────────────────────────────────────────────────
async function loadLogs() {
  const el = document.getElementById('logPanel');
  if (!el) return;
  el.innerHTML = '<div class="log-line"><span class="log-ts">...</span>Fetching events...</div>';
  const events = await apiFetch('/ai/homeostasis/events', {}, T_SLOW);
  if (!events || !events.length) {
    el.innerHTML = '<div class="log-line"><span class="log-ts">--</span>No homeostasis events recorded.</div>';
    return;
  }
  el.innerHTML = events.slice(-200).reverse().map(e => {
    const ts  = e.timestamp ? new Date(e.timestamp * 1000).toLocaleTimeString() : '--';
    const typ = e.type || e.level || 'INFO';
    const msg = e.message || e.event || JSON.stringify(e);
    return `<div class="log-line"><span class="log-ts">${ts}</span><span class="log-type">[${typ}]</span>${msg}</div>`;
  }).join('');
}

// ─── ACTIONS ─────────────────────────────────────────────────────────────────
async function forceSync() {
  try {
    await apiFetch('/actions/execute', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ label:'run-aq-qa-0' }) });
  } catch {}
  location.reload();
}

async function forceLayerRefresh() {
  lazyLoaded.delete('overview');
  await loadOSI();
}

async function refreshAll() {
  lazyLoaded.clear();
  lazyLoaded.add('overview');
  window._aiMetrics = null;
  await Promise.allSettled([loadKPIs(), loadRagQuality(), loadSystem(), loadServices(), loadDatabase(), loadOSI(), loadRemediations(), loadAuditLog()]);
  loadLens(activeLens);
}

// ─── INIT ────────────────────────────────────────────────────────────────────
window.addEventListener('error', e => {
  const b = document.getElementById('err-banner');
  if (b) { b.textContent = `JS Error: ${e.message} (${e.filename}:${e.lineno})`; b.style.display = 'block'; }
});

document.addEventListener('DOMContentLoaded', () => {
  // Immediate: fast data
  Promise.allSettled([loadKPIs(), loadRagQuality(), loadSystem(), loadServices()]);
  // Deferred: DB metrics + slow OSI health + audit
  setTimeout(() => { loadDatabase(); loadOSI(); loadRemediations(); loadAuditLog(); }, 400);
  // Periodic refresh
  setInterval(loadKPIs,       30_000);
  setInterval(loadRagQuality, 60_000);
  setInterval(loadSystem,     30_000);
  setInterval(loadServices,   30_000);
  setInterval(loadDatabase,   60_000);
  setInterval(() => { if (activeLens !== 'overview') loadLens(activeLens); }, 60_000);
});

// Expose to HTML onclick handlers
window.setLens       = setLens;
window.toggleDrawer  = toggleDrawer;
window.drillLayer    = drillLayer;
window.forceSync     = forceSync;
window.forceLayerRefresh = forceLayerRefresh;
window.refreshAll    = refreshAll;
window.mlPromote     = mlPromote;
window.mlCancel      = mlCancel;
window.mlRollback    = mlRollback;
