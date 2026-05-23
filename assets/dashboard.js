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
const fmtImplStatus = s => s === 'implementation_exists' ? 'ready' : (s || '--');
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
  else if (id === 'map')          { initTopo(); loadWorkflowGraph(); }
  else if (id === 'logic')        initLogic();
  else if (id === 'logs')         loadLogs();
}
function toggleDrawer() { document.getElementById('drawer').classList.toggle('open'); }

// ─── KPI RIBBON ──────────────────────────────────────────────────────────────
async function loadKPIs() {
  const [metrics, aiM, hs, analytics] = await Promise.all([
    apiFetch('/metrics'),
    apiFetch('/ai/metrics'),
    apiFetch('/metrics/health-score'),
    apiFetch('/insights/routing/analytics'),
  ]);
  window._aiMetrics = aiM;

  // Populate header health score immediately (before OSI layer health completes)
  if (hs && hs.score != null) {
    const scoreEl = document.getElementById('healthScore');
    if (scoreEl && scoreEl.textContent === '--') {
      scoreEl.textContent = hs.score;
      scoreEl.classList.remove('warn', 'err');
      if (hs.score < 50) scoreEl.classList.add('err');
      else if (hs.score < 80) scoreEl.classList.add('warn');
    }
    const hsKpi = document.getElementById('kpiHealthScore');
    if (hsKpi) {
      hsKpi.textContent = hs.score;
      hsKpi.className = 'kpi-v ' + (hs.score < 50 ? 'err' : hs.score < 80 ? 'warn' : 'ok');
    }
  }

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
    // Color header health score from OSI eval pct too (overrides if available)
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
  }
  // Ops/7d from routing analytics
  if (analytics) {
    const w7d = ((analytics.windows && analytics.windows.windows) || {})['7d'] || {};
    const cur  = analytics.current || {};
    const totalOps = w7d.query_ok_n ?? cur.query_ok_n;
    if (totalOps != null) {
      const label = totalOps >= 1000 ? `${(totalOps/1000).toFixed(1)}k` : String(totalOps);
      setText('kpiTokSaved', label);
      // Populate Overview OPS/DAY tile (loadCoordinator also sets this but only from Intelligence tab)
      const opsDay = Math.round(totalOps / 7);
      setText('vOpsDay', opsDay >= 1000 ? `${(opsDay/1000).toFixed(1)}k` : String(opsDay));
    }
    // KPI ribbon p95 latency from hotspots is fetched separately in loadSystem()
  }
  setText('lastUpdate', new Date().toLocaleTimeString());
}

// ─── RAG QUALITY (always visible, aq-qa 60.7.3 contract) ─────────────────────
async function loadRagQuality() {
  const d = await apiFetch('/eval/trend');
  const r = (d && d.ragas_metrics) ? d.ragas_metrics : {};
  const noData = !d || (d.count === 0);
  const p = v => (v != null && v > 0) ? `${(v * 100).toFixed(1)}%` : (noData ? 'no evals' : '--');
  setText('ragAnswerRelevance',  p(r.answer_relevance_avg));
  setText('ragContextPrecision', p(r.context_precision_avg));
  setText('ragFaithfulness',     p(r.faithfulness_avg));
  setText('ragSampleCount',      noData ? '0' : (r.sample_count != null ? r.sample_count : '--'));
  // Mirror into intelligence eval card
  setText('evalAR',      p(r.answer_relevance_avg));
  setText('evalCP',      p(r.context_precision_avg));
  setText('evalFaith',   p(r.faithfulness_avg));
  setText('evalSamples', noData ? '0' : (r.sample_count != null ? r.sample_count : '--'));
  if (d) setText('evalRunCount', d.count ?? '0');
}

// ─── OVERVIEW: SYSTEM STATS ───────────────────────────────────────────────────
async function loadSystem() {
  const [sys, metrics, hotspots] = await Promise.all([
    apiFetch('/metrics/system'),
    apiFetch('/metrics'),
    apiFetch('/insights/performance/hotspots'),
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
    const gpuMatches = gpu.name ? gpu.name.match(/\[([^\]]+)\]/g) : null;
    const gpuDisplay = gpuMatches && gpuMatches.length > 1
      ? gpuMatches[gpuMatches.length - 1].slice(1, -1)
      : (gpu.name || '--').split(']').pop().replace(/\(rev[^)]+\)/, '').trim();
    setText('gpuName', gpuDisplay || '--');
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
  if (hotspots) {
    const rl = hotspots.route_latency || {};
    const cache = hotspots.cache || {};
    const p95 = rl.backend_valid_p95_ms;
    const cacheHit = cache.hit_pct;
    if (p95 != null) { setText('vLatP95', `${p95.toFixed(0)}ms`); colorStatTile('statLatP95', p95, 500, 2000); }
    if (cacheHit != null) setText('vCacheHit', `${cacheHit.toFixed(0)}%`);
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
  const [aiM, rts, analytics] = await Promise.all([
    window._aiMetrics ? Promise.resolve(window._aiMetrics) : apiFetch('/ai/metrics'),
    apiFetch('/aistack/advanced/runtime-summary'),
    apiFetch('/insights/routing/analytics'),
  ]);
  const el = document.getElementById('coordMetrics');
  if (!el) return;
  const sv   = (aiM && aiM.services) || {};
  const hc   = sv.hybrid_coordinator || sv.hybrid || {};
  const eff  = (aiM && aiM.effectiveness) || {};
  const sum  = (rts && rts.summary) || {};
  // Use routing analytics for accurate local% and ops counts (eff counters may be 0)
  const cur  = (analytics && analytics.current) || {};
  const w7d  = ((analytics && analytics.windows && analytics.windows.windows) || {})['7d'] || {};
  const localPct   = cur.local_pct ?? w7d.local_pct ?? eff.local_query_percentage;
  const totalOps   = w7d.query_ok_n ?? cur.query_ok_n ?? 0;
  const backendN   = w7d.local_n   ?? cur.local_n   ?? 0;
  const vectors    = (aiM && aiM.knowledge_base && aiM.knowledge_base.total_points) ?? eff.knowledge_base_vectors;
  setText('coordStatus', hc.status || '--');
  // Populate Overview Ops/Day tile from the analytics already fetched here
  if (totalOps) {
    const opsDay = Math.round(totalOps / 7);
    setText('vOpsDay', opsDay >= 1000 ? `${(opsDay/1000).toFixed(1)}k` : String(opsDay));
    setText('vBackendN', backendN ? Math.round(backendN / 7).toLocaleString() : '0');
  }
  el.innerHTML = [
    fwRow('Status',        hc.status || '--',                               statusColor(hc.status)),
    fwRow('Port',          hc.port ? `:${hc.port}` : '--',                  'info'),
    fwRow('Local %',       localPct != null ? pctD(localPct) : '--',        localPct >= 80 ? 'ok' : localPct >= 40 ? 'warn' : 'err'),
    fwRow('Ops (7d)',      totalOps ? totalOps.toLocaleString() : '--'),
    fwRow('Backend Calls', backendN ? backendN.toLocaleString() : '--',     'info'),
    fwRow('Vectors',       vectors  != null ? vectors.toLocaleString() : '--'),
    fwRow('Offloading',    fmtImplStatus((sum.offloading || {}).status),    statusColor((sum.offloading || {}).status)),
    fwRow('Cap Gaps',      (sum.capability_gap || {}).gaps_detected ?? '--', (sum.capability_gap || {}).gaps_detected > 0 ? 'warn' : 'ok'),
  ].join('');
}

// ─── INTELLIGENCE: TASK ROUTING ───────────────────────────────────────────────
async function loadRouting() {
  // Use traces summary for per-intent breakdown; analytics for totals
  const [analytics, cls, traceSummary] = await Promise.all([
    apiFetch('/insights/routing/analytics'),
    apiFetch('/aistack/task-classification/stats'),
    apiFetch('/traces/summary'),
  ]);
  const tbody = document.getElementById('routeBody');
  if (!tbody) return;

  const cur = (analytics || {}).current || {};
  const w7d = ((analytics || {}).windows || {}).windows?.['7d'] || {};
  const localN = cur.local_n ?? w7d.local_n ?? (cls || {}).local_count ?? 0;
  // Compute local_pct from traces backend_breakdown when analytics returns null
  const traceBB = (traceSummary && traceSummary.backend_breakdown) || {};
  const traceCount = (traceSummary && traceSummary.count) || 0;
  const traceLocalPct = (traceBB.local != null && traceCount > 0)
    ? Math.round(100 * traceBB.local / traceCount) : null;
  const localPct = cur.local_pct ?? w7d.local_pct ?? (cls || {}).local_pct ?? traceLocalPct;
  const totalOk = cur.query_ok_n ?? (traceCount > 0 ? traceCount : localN);

  setText('routeTotal',  totalOk.toLocaleString());
  setText('routeLocalP', localPct != null ? pctD(localPct) : `${localN}`);

  // Show per-intent breakdown from traces (most accurate), then profiles, then fallbacks
  const traceIntents = (traceSummary && traceSummary.intent_breakdown) || {};
  const profiles = w7d.top_profiles || cur.top_profiles || [];
  const recentD  = (cls || {}).recent_decisions || [];
  const clsTypes = (cls || {}).by_task_type || {};

  let rows = '';
  if (Object.entries(traceIntents).length) {
    rows = Object.entries(traceIntents).slice(0, 10).map(([intent, count]) =>
      `<tr><td>${intent.replace(/_/g,' ')}</td><td>local</td><td>${count.toLocaleString()}</td></tr>`).join('');
  } else if (profiles.length) {
    rows = profiles.slice(0,8).map(([name, count]) =>
      `<tr><td>${name}</td><td>local</td><td>${count.toLocaleString()}</td></tr>`).join('');
  } else if (Object.entries(clsTypes).length) {
    rows = Object.entries(clsTypes).map(([k, v]) =>
      `<tr><td>${k}</td><td>${typeof v==='object'?(v.backend||'--'):'--'}</td><td>${typeof v==='object'?(v.count??v):v}</td></tr>`).join('');
  } else if (recentD.length) {
    rows = recentD.slice(0,10).map(r =>
      `<tr><td>${r.task_type||'--'}</td><td>${r.route||r.backend||'--'}</td><td>${relTime(r.timestamp)}</td></tr>`).join('');
  } else {
    // Synthesize summary rows from aggregate analytics when no per-intent breakdown available
    const remoteN = (cur.query_ok_n ?? w7d.query_ok_n ?? 0) - localN;
    if (localN > 0)
      rows += `<tr><td>all intents</td><td>local (llama.cpp)</td><td>${localN.toLocaleString()}</td></tr>`;
    if (remoteN > 0)
      rows += `<tr><td>offloaded</td><td>remote</td><td>${remoteN.toLocaleString()}</td></tr>`;
  }
  tbody.innerHTML = rows || '<tr><td colspan="3" style="color:var(--fg3)">No routing data yet</td></tr>';
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
  // If detailed probe has null liveness, derive status from service reachability
  const aidbStatus = lv.status || (det && det.service === 'aidb' ? (det.startup_complete ? 'healthy' : 'running') : '--');
  setText('aidbBadge', aidbStatus);
  const rows = [
    fwRow('Liveness',  lv.status || aidbStatus, statusColor(lv.status || aidbStatus)),
    fwRow('Readiness', rd.status || (det && det.service === 'aidb' ? 'ok' : '--'), statusColor(rd.status || 'ok')),
    fwRow('Startup',   det ? (det.startup_complete ? 'yes' : 'no') : '--', det && det.startup_complete ? 'ok' : 'info'),
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
  // Agentic Readiness: combine memory status + verify-self for richer info
  const [mem, vs] = await Promise.all([
    apiFetch('/ai/memory/status'),
    apiFetch('/verify-self/results'),
  ]);
  const el = document.getElementById('agenticDetails');
  const badge = document.getElementById('agenticBadge');
  if (!el) return;
  const memInit = (mem || {}).initialized;
  const memTypes = (mem || {}).memory_types || [];
  const contradictions = (mem || {}).contradiction_pairs ?? 0;
  const vsOk = (vs || {}).consistent;
  const vsChecks = (vs || {}).total_checks ?? 0;

  if (badge) {
    const ok = memInit && vsOk !== false;
    badge.textContent = ok ? 'ready' : 'warn';
    badge.className = `card-badge ${ok ? 'badge-ok' : 'badge-warn'}`;
  }
  el.innerHTML = [
    fwRow('Memory Init',    memInit ? 'yes' : 'no', memInit ? 'ok' : 'warn'),
    fwRow('Memory Types',   memTypes.length || '--', memTypes.length >= 5 ? 'ok' : 'warn'),
    fwRow('Contradictions', contradictions, contradictions > 10 ? 'warn' : 'ok'),
    fwRow('Self-Verify',    vsOk ? 'pass' : vsOk === false ? 'FAIL' : '--', vsOk ? 'ok' : 'err'),
    fwRow('Verify Checks',  vsChecks || '--'),
    memTypes.length ? fwRow('Types', memTypes.slice(0,4).join(', ') + (memTypes.length>4?'…':''), 'info') : '',
  ].join('');
}

// ─── INTELLIGENCE: PERFORMANCE HOTSPOTS ──────────────────────────────────────
async function loadPerfHotspots() {
  const d  = await apiFetch('/insights/performance/hotspots');
  const el = document.getElementById('perfHotspotDetails');
  const badge = document.getElementById('perfHotspotBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }

  const rl = d.route_latency || {};
  const cache = d.cache || {};
  const rag = d.rag_posture || {};
  const hotspots = d.hotspots || [];
  const watching = hotspots.filter(h => h.status === 'watch').length;

  if (badge) {
    badge.textContent = watching > 0 ? `${watching} watch` : 'healthy';
    badge.className = `card-badge ${watching > 0 ? 'badge-warn' : 'badge-ok'}`;
  }

  // Latency section
  const p50 = rl.backend_valid_p50_ms; const p95 = rl.backend_valid_p95_ms;
  const cacheHit = cache.hit_pct; const totalCalls = rl.total_calls;

  el.innerHTML = [
    fwRow('p50 Latency',     p50 != null ? `${p50.toFixed(0)}ms` : '--', p50 > 500 ? 'warn' : 'ok'),
    fwRow('p95 Latency',     p95 != null ? `${p95.toFixed(0)}ms` : '--', p95 > 1000 ? 'warn' : p95 > 2000 ? 'err' : 'ok'),
    fwRow('Cache Hit Rate',  cacheHit != null ? `${cacheHit.toFixed(0)}%` : '--', cacheHit >= 60 ? 'ok' : 'warn'),
    fwRow('Total Calls (7d)',totalCalls != null ? totalCalls.toLocaleString() : '--'),
    fwRow('Memory Recall %', rag.memory_recall_share_pct != null ? `${rag.memory_recall_share_pct.toFixed(0)}%` : '--', 'info'),
    fwRow('Recall Miss',     rag.memory_recall_miss_pct != null ? `${rag.memory_recall_miss_pct.toFixed(0)}%` : '--', rag.memory_recall_miss_pct > 5 ? 'warn' : 'ok'),
    fwRow('Error Rate',      rl.client_error_count != null && totalCalls ? `${((rl.client_error_count/totalCalls)*100).toFixed(1)}%` : '--',
                             rl.client_error_count > 500 ? 'warn' : 'ok'),
  ].join('');

  // Top bottlenecks mini-list
  const bottlenecks = (d.top_bottlenecks || []).filter(b => b.status === 'watch').slice(0,3);
  if (bottlenecks.length) {
    el.innerHTML += `<div style="margin-top:.4rem;border-top:1px solid rgba(255,255,255,.05);padding-top:.35rem">` +
      bottlenecks.map(b => fwRow('  '+b.label.replace(/^\w+:/,''), `p95=${b.p95_ms.toFixed(0)}ms`, 'warn')).join('') +
      `</div>`;
  }
}

// ─── SECURITY: COMPLIANCE CONTROLS ───────────────────────────────────────────
async function loadSecCompliance() {
  const d  = await apiFetch('/insights/security/compliance');
  const el = document.getElementById('secComplianceDetails');
  const badge = document.getElementById('secComplianceBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }

  const controls = d.controls || {};
  const rl = d.rate_limiting || {};
  const audit = d.audit || {};
  const allPassed = Object.values(controls).every(v => v === true);
  const passCount = Object.values(controls).filter(v => v === true).length;

  if (badge) {
    badge.textContent = `${passCount}/${Object.keys(controls).length}`;
    badge.className = `card-badge ${allPassed ? 'badge-ok' : 'badge-warn'}`;
  }

  el.innerHTML = [
    ...Object.entries(controls).map(([k, v]) =>
      fwRow(k.replace(/_/g,' '), v ? 'pass' : 'FAIL', v ? 'ok' : 'err')),
    fwRow('Rate Limit',   rl.enabled ? `${rl.default_rpm} RPM` : 'disabled', rl.enabled ? 'ok' : 'warn'),
    fwRow('Audit Events', audit.total_events != null ? audit.total_events.toLocaleString() : '--', 'info'),
    fwRow('Audit Sealed', audit.tamper_evident ? 'yes' : 'no', audit.tamper_evident ? 'ok' : 'warn'),
  ].join('');
}

// ─── INTELLIGENCE: AGENT EVAL TRENDS ─────────────────────────────────────────
async function loadAgentEvalTrends() {
  const d  = await apiFetch('/orchestration/evaluations/trends');
  const el = document.getElementById('agentEvalDetails');
  const badge = document.getElementById('agentEvalBadge');
  if (!el) return;
  if (!d || !d.trends) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const trends = d.trends || [];
  if (badge) { badge.textContent = `${d.agent_count || trends.length} agents`; badge.className = 'card-badge badge-ok'; }
  el.innerHTML = trends.map(t => {
    const revScore = t.average_review_score != null ? (t.average_review_score * 100).toFixed(0) + '%' : '--';
    const rtScore  = t.average_runtime_score != null ? (t.average_runtime_score * 100).toFixed(0) + '%' : '--';
    const col = t.average_review_score >= 0.7 ? 'ok' : t.average_review_score >= 0.4 ? 'warn' : 'err';
    return [
      fwRow(t.agent, `rev ${revScore} · rt ${rtScore}`, col),
    ].join('');
  }).join('') || fwRow('Status', 'No agent data yet');
}

// ─── INTELLIGENCE: ORCHESTRATION SESSIONS ────────────────────────────────────
async function loadOrchestrationSessions() {
  const d  = await apiFetch('/orchestration/sessions');
  const el = document.getElementById('orchSessionDetails');
  const badge = document.getElementById('orchSessionBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const sessions = d.sessions || [];
  const active   = sessions.filter(s => s.status === 'in_progress').length;
  const completed= sessions.filter(s => s.status === 'completed').length;
  const failed   = sessions.filter(s => s.status === 'failed').length;
  if (badge) { badge.textContent = `${active} active`; badge.className = `card-badge ${active > 200 ? 'badge-warn' : 'badge-ok'}`; }
  // Token/tool burn across active sessions
  const asl  = sessions.filter(s => s.status === 'in_progress').slice(0, 50);
  const tokU = asl.reduce((s, x) => s + (x.usage?.tokens_used || 0), 0);
  const tokB = asl.reduce((s, x) => s + (x.budget?.token_limit || 0), 0);
  const toolU= asl.reduce((s, x) => s + (x.usage?.tool_calls_used || 0), 0);
  el.innerHTML = [
    fwRow('Total Sessions', sessions.length.toLocaleString()),
    fwRow('Active',     active.toLocaleString(),    active > 200 ? 'warn' : 'ok'),
    fwRow('Completed',  completed.toLocaleString(), completed > 0 ? 'ok' : 'info'),
    fwRow('Failed',     failed.toLocaleString(),    failed > 0 ? 'err' : 'ok'),
    tokB  ? fwRow('Token Burn', `${tokU.toLocaleString()} / ${tokB.toLocaleString()}`, 'info') : '',
    toolU ? fwRow('Tool Calls', toolU.toLocaleString()) : '',
  ].filter(Boolean).join('');
  // Non-ping sessions sample
  const real = sessions.filter(s => s.objective && s.objective !== 'ping').slice(0, 4);
  if (real.length) {
    el.innerHTML += `<div style="margin-top:.35rem;padding-top:.3rem;border-top:1px solid rgba(255,255,255,.05)">` +
      real.map(s => fwRow((s.objective || '--').slice(0, 26), s.status, s.status === 'completed' ? 'ok' : s.status === 'failed' ? 'err' : 'info')).join('') + `</div>`;
  }
}

// ─── INTELLIGENCE: RAG PIPELINE HEALTH ───────────────────────────────────────
async function loadRAGHealth() {
  const [rag, perf] = await Promise.all([
    apiFetch('/ai/health/rag'),
    apiFetch('/insights/performance/hotspots'),
  ]);
  const el = document.getElementById('ragHealthDetails');
  const badge = document.getElementById('ragHealthBadge');
  if (!el) return;
  const st = (rag || {}).status || 'unknown';
  const aug= (rag || {}).augmented; const tot = (rag || {}).total;
  const posture = (rag || {}).posture || '--';
  const winSz   = (rag || {}).window_size;
  if (badge) { badge.textContent = st; badge.className = `card-badge ${st === 'healthy' ? 'badge-ok' : st === 'degraded' ? 'badge-warn' : 'badge-err'}`; }
  const augPct = (tot && aug != null) ? Math.round((aug / tot) * 100) : null;
  el.innerHTML = [
    fwRow('Status',    st,     st === 'healthy' ? 'ok' : 'warn'),
    fwRow('Posture',   posture, posture === 'active' ? 'ok' : 'warn'),
    fwRow('Augmented', augPct != null ? `${aug}/${tot} (${augPct}%)` : '--', augPct != null && augPct >= 80 ? 'ok' : 'warn'),
    winSz ? fwRow('Window', `last ${winSz} queries`) : '',
  ].filter(Boolean).join('');
  if (perf) {
    const rp = perf.rag_posture || {};
    el.innerHTML += [
      rp.memory_recall_share_pct != null ? fwRow('Memory Recall %', `${rp.memory_recall_share_pct.toFixed(0)}%`, 'info') : '',
      rp.memory_recall_miss_pct  != null ? fwRow('Recall Miss %', `${rp.memory_recall_miss_pct.toFixed(0)}%`, rp.memory_recall_miss_pct > 5 ? 'warn' : 'ok') : '',
    ].filter(Boolean).join('');
  }
}

// ─── INTELLIGENCE: ROUTING FRONTDOOR CONFIG ──────────────────────────────────
async function loadRoutingConfig() {
  const d  = await apiFetch('/aistack/routing/summary');
  const el = document.getElementById('routingConfigDetails');
  const badge = document.getElementById('routingConfigBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const fd = d.frontdoor || {};
  const aliases = fd.aliases || {};
  const uniqueTargets = [...new Set(Object.values(aliases))];
  if (badge) { badge.textContent = `${uniqueTargets.length} targets`; badge.className = 'card-badge badge-ok'; }
  el.innerHTML = [
    fwRow('Alias Count',   Object.keys(aliases).length),
    fwRow('Targets',       uniqueTargets.length),
    ...uniqueTargets.map(t => fwRow('→ ' + t, `${Object.values(aliases).filter(v => v === t).length} aliases`, 'info')),
  ].join('');
}

// ─── INTELLIGENCE: HOMEOSTASIS & REMEDIATION ─────────────────────────────────
async function loadHomeostasis() {
  const [events, rem] = await Promise.all([
    apiFetch('/ai/homeostasis/events'),
    apiFetch('/ai/remediation/latest'),
  ]);
  const el = document.getElementById('homeostasisDetails');
  const badge = document.getElementById('homeostasisBadge');
  if (!el) return;
  const remSt   = (rem || {}).status || 'unknown';
  const isActive= remSt === 'active' || remSt === 'in_progress';
  if (badge) { badge.textContent = isActive ? 'active' : 'nominal'; badge.className = `card-badge ${isActive ? 'badge-warn' : 'badge-ok'}`; }
  const evts = Array.isArray(events) ? events : [];
  el.innerHTML = [
    fwRow('Remediation',  remSt.replace(/_/g,' '), remSt === 'no_remediation_active' ? 'ok' : isActive ? 'warn' : 'info'),
    fwRow('Events Logged', evts.length, evts.length > 50 ? 'warn' : 'ok'),
    evts.length ? fwRow('Last Event', relTime(evts[evts.length-1]?.timestamp ? new Date((evts[evts.length-1].timestamp)*1000).toISOString() : null)) : '',
  ].filter(Boolean).join('');
  if (evts.length) {
    el.innerHTML += `<div style="margin-top:.35rem;padding-top:.3rem;border-top:1px solid rgba(255,255,255,.05)">` +
      evts.slice(-4).reverse().map(e => {
        const ts = e.timestamp ? new Date(e.timestamp*1000).toLocaleTimeString() : '--';
        const msg = (e.message || e.event || e.type || '').toString().slice(0,38);
        return `<div style="font-size:.56rem;color:var(--fg2);margin:.1rem 0">${ts} ${msg}</div>`;
      }).join('') + `</div>`;
  } else {
    el.innerHTML += fwRow('Loop State', 'nominal · no events', 'ok');
  }
}

// ─── INTELLIGENCE: LOGIC PATTERN MAP (graph/vector) ──────────────────────────
async function loadLogicPatterns() {
  const d  = await apiFetch('/graph/vector');
  const el = document.getElementById('logicPatternsDetails');
  if (!el) return;
  if (!d || !d.nodes) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const nodes = d.nodes || [];
  const groups = {};
  nodes.forEach(n => { const g = n.group || 'unknown'; groups[g] = (groups[g] || 0) + 1; });
  const topGroups = Object.entries(groups).sort((a,b) => b[1]-a[1]).slice(0,6);
  setText('logicPatternsBadge', nodes.length.toLocaleString());
  el.innerHTML = [
    fwRow('Total Patterns', nodes.length.toLocaleString(), 'ok'),
    fwRow('Unique Groups',  Object.keys(groups).length.toString(), 'info'),
    ...topGroups.map(([g,n]) => fwRow(g, n.toString(), 'info')),
  ].join('');
}

// ─── NEURAL MAP: ROUTING WORKFLOW (graph/workflow) ────────────────────────────
async function loadWorkflowGraph() {
  const data = await apiFetch('/graph/workflow');
  const c = document.getElementById('workflowCanvas');
  if (!c) return;
  c.querySelectorAll('svg').forEach(s => s.remove());
  if (!window.d3) { setText('workflowHud', 'D3_LOADING…'); setTimeout(loadWorkflowGraph, 800); return; }
  if (!data || !data.nodes) { setText('workflowHud', 'DATA_UNAVAILABLE'); return; }
  const edges = (data.edges || data.links || []).map(e => ({
    source: e.source || e.from, target: e.target || e.to, label: e.label || ''
  }));
  const w = c.clientWidth  || 800;
  const h = c.clientHeight || 400;
  const svg = d3.select('#workflowCanvas').append('svg').attr('width','100%').attr('height','100%');
  const g   = svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.2,6]).on('zoom', e => g.attr('transform', e.transform)));
  const groupColor = gr => gr === 'input' ? '#ffffff' : gr === 'router' ? '#f4a261'
    : gr === 'local' ? '#2ec4b6' : gr === 'remote' ? '#e76f51' : gr === 'service' ? '#a8dadc'
    : gr === 'vector-db' ? '#f4d35e' : gr === 'rag' ? '#ee6c4d' : 'var(--fg3)';
  const sim = d3.forceSimulation(data.nodes)
    .force('link',   d3.forceLink(edges).id(d => d.id).distance(110))
    .force('charge', d3.forceManyBody().strength(-280))
    .force('center', d3.forceCenter(w/2, h/2))
    .force('coll',   d3.forceCollide(22));
  const link = g.append('g').selectAll('line').data(edges).enter().append('line').attr('class','link-line');
  const node = g.append('g').selectAll('g').data(data.nodes).enter().append('g')
    .call(d3.drag()
      .on('start', (e,d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on('drag',  (e,d) => { d.fx=e.x; d.fy=e.y; })
      .on('end',   (e,d) => { if (!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }));
  node.append('circle')
    .attr('r', d => (d.val || 3) * 1.8)
    .attr('fill', d => d.color || groupColor(d.group))
    .attr('stroke','var(--bg)').attr('stroke-width',2);
  node.append('text').attr('class','node-label').attr('dx',14).attr('dy','.35em')
    .text(d => d.name || d.id);
  sim.on('tick', () => {
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
  setText('workflowHud', `ROUTING_WORKFLOW: ${data.nodes.length} NODES`);
}

async function loadIntelligence() {
  await Promise.allSettled([
    loadCoordinator(), loadRouting(), loadModels(), loadSwitchboard(),
    loadAIDB(), loadLearning(), loadDrift(), loadVerifier(),
    loadKnowledge(), loadAgentic(), loadRagQuality(), loadAgentEvalTrends(),
    loadPerfHotspots(), loadOrchestrationSessions(), loadRAGHealth(),
    loadRoutingConfig(), loadHomeostasis(), loadSchedulerStatus(), loadCLMStatus(),
    loadMemoryBroker(), loadAffectiveState(), loadHintsRegistry(),
    loadAICoordinator(), loadReasoningProfiles(),
    loadAgentOpsStatus(), loadAgentLessons(), loadMemStats(),
    loadLogicPatterns(), loadLocalInsights(),
  ]);
}

// ─── LOCAL INSIGHTS (aq-insights output) ──────────────────────────────────────
async function loadLocalInsights() {
  const ctrl  = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 6000);
  let d = null;
  try { d = await apiFetch('/aistack/local-insights/latest', {}, 6000); }
  finally { clearTimeout(timer); }
  const el    = document.getElementById('localInsightsDetails');
  const badge = document.getElementById('localInsightsBadge');
  if (!el) return;
  if (!d || !d.available) {
    el.innerHTML = fwRow('Status', 'No insights yet — run aq-insights', 'warn');
    if (badge) { badge.textContent = '--'; badge.className = 'card-badge badge-warn'; }
    return;
  }
  if (badge) {
    badge.textContent = d.date_tag || 'ready';
    badge.className = 'card-badge badge-ok';
  }
  // Show meta then a preview of the markdown content (first ~400 chars)
  const preview = (d.content || '').replace(/^#+\s/gm, '').slice(0, 400).trim();
  el.innerHTML = [
    fwRow('Date',      d.date_tag || '--',           'info'),
    fwRow('Generated', d.generated_at ? d.generated_at.replace('Z', ' UTC') : '--', 'info'),
    fwRow('Snapshot',  d.report_snapshot ? d.report_snapshot.slice(0, 28) + '…' : '--', 'info'),
  ].join('') +
    `<div style="margin-top:.4rem;padding:.4rem;background:rgba(255,255,255,.03);border-radius:3px;` +
    `font-size:.57rem;color:var(--fg2);white-space:pre-wrap;line-height:1.5;max-height:8rem;overflow:hidden" id="localInsightsPreview"></div>`;
  const previewEl = document.getElementById('localInsightsPreview');
  if (previewEl) previewEl.textContent = preview + (d.content && d.content.length > 400 ? '\n…' : '');
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
    fwRow('Interfaces',       Object.keys(d.interfaces || {}).join(', ') || 'none'),
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
  const tep  = pl.tool_execution_policy || {};
  const infe = card.inference_optimizations || {};
  const disc = card.discovery || {};
  const acc  = card.acceptance || {};
  if (badge) { badge.textContent = d.status || '--'; badge.className = `card-badge ${statusColor(d.status) === 'ok' ? 'badge-ok' : 'badge-warn'}`; }
  el.innerHTML = [
    fwRow('Status',        d.status || '--', statusColor(d.status)),
    fwRow('Scorecards',    s.scorecards_generated ?? '--', (s.scorecards_generated || 0) > 0 ? 'ok' : 'info'),
    fwRow('Med Risk Tools',tep.allow_medium_risk_tools ? 'allowed' : 'blocked', tep.allow_medium_risk_tools ? 'warn' : 'ok'),
    fwRow('High Risk Tools',tep.allow_high_risk_tools  ? 'ALLOWED' : 'blocked', tep.allow_high_risk_tools  ? 'err'  : 'ok'),
    fwRow('Lesson Refs',   (s.active_lesson_refs || []).length, (s.active_lesson_refs || []).length > 0 ? 'ok' : 'info'),
  ].join('');

  // Scorecard — inference optimizations + discovery rates
  if (sc) {
    sc.innerHTML = [
      '<div style="font-size:.58rem;color:var(--fg3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:.3rem">Scorecard</div>',
      fwRow('Prompt Cache',      infe.prompt_cache_policy_enabled ? 'enabled' : 'disabled', infe.prompt_cache_policy_enabled ? 'ok' : 'warn'),
      fwRow('Spec Decoding',     infe.speculative_decoding_enabled ? `enabled (${infe.speculative_decoding_mode||'draft'})` : 'disabled (MTP)', infe.speculative_decoding_enabled ? 'ok' : 'info'),
      fwRow('Ctx Compression',   infe.context_compression_enabled ? 'enabled' : 'disabled', infe.context_compression_enabled ? 'ok' : 'warn'),
      fwRow('Discovery Cache%',  disc.cache_hit_rate != null ? pctD(disc.cache_hit_rate * 100) : '--'),
      fwRow('Discovery Errors',  disc.errors ?? 0, disc.errors > 0 ? 'err' : 'ok'),
      fwRow('Acceptance Rate',   acc.total > 0 ? pctD(acc.pass_rate * 100) : 'no runs', acc.ok === true ? 'ok' : acc.ok === false ? 'err' : 'info'),
    ].join('');
  }
}

// ─── SECURITY: BEHAVIORAL DRIFT MONITOR ─────────────────────────────────────
async function loadSecDrift() {
  const d  = await apiFetch('/traces/drift');
  const el = document.getElementById('secDriftDetails');
  const badge = document.getElementById('secDriftBadge');
  if (!el) return;
  if (!d || !d.available) {
    el.innerHTML = fwRow('Status', 'no trace data yet', 'info');
    if (badge) { badge.textContent = 'idle'; badge.className = 'card-badge badge-info'; }
    return;
  }
  const score = d.drift_score;
  const scoreColor = score == null ? '' : score > 0.7 ? 'err' : score > 0.4 ? 'warn' : 'ok';
  if (badge) {
    badge.textContent = score != null ? (score > 0.7 ? 'ALERT' : score > 0.4 ? 'WATCH' : 'OK') : '--';
    badge.className   = `card-badge ${score != null && score > 0.4 ? 'badge-warn' : 'badge-ok'}`;
  }
  el.innerHTML = [
    fwRow('Drift Score',    score != null ? score.toFixed(3) : '--', scoreColor),
    fwRow('Intent Flip%',   d.intent_flip_rate  != null ? pctD(d.intent_flip_rate * 100) : '--',
          d.intent_flip_rate  != null && d.intent_flip_rate  > 0.1 ? 'warn' : 'ok'),
    fwRow('Lat Degrad',     d.latency_degradation != null ? `${d.latency_degradation.toFixed(1)}ms` : '--',
          d.latency_degradation != null && d.latency_degradation > 200 ? 'err' : d.latency_degradation > 50 ? 'warn' : 'ok'),
    fwRow('Trace Count',    d.trace_count ?? '--', 'info'),
  ].join('');
}

// ─── SECURITY: AGENT POOL SECURITY ──────────────────────────────────────────
async function loadAgentPool() {
  const d  = await apiFetch('/aistack/advanced/runtime-summary');
  const el = document.getElementById('agentPoolDetails');
  const badge = document.getElementById('agentPoolBadge');
  if (!el) return;
  const profiles = ((d || {}).raw || {}).quality_profiles || {};
  const agents = profiles.profiles || [];
  if (!agents.length) {
    el.innerHTML = fwRow('Status', 'no pool data', 'info');
    if (badge) { badge.textContent = '0'; badge.className = 'card-badge badge-warn'; }
    return;
  }
  const avail = agents.filter(a => a.status === 'available').length;
  if (badge) {
    badge.textContent = `${avail}/${agents.length}`;
    badge.className   = `card-badge ${avail === agents.length ? 'badge-ok' : 'badge-warn'}`;
  }
  el.innerHTML = agents.map(a => {
    const score = a.composite_score != null ? (a.composite_score * 100).toFixed(0) : '--';
    const shortName = a.name && a.name.length > 18 ? a.name.slice(0, 17) + '…' : (a.name || '--');
    return fwRow(shortName, `${a.status} · ${score}%`, statusColor(a.status));
  }).join('');
}

// ─── SECURITY: VULNERABILITY AUDIT ───────────────────────────────────────────
async function loadVulnAudit() {
  const d  = await apiFetch('/security/audit');
  const el = document.getElementById('vulnAuditDetails');
  const badge = document.getElementById('vulnAuditBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const s   = d.summary || {};
  const pip = s.pip || {};
  const npm = s.npm || {};
  const sr  = s.secrets_rotation || {};
  const dop = s.dashboard_operator || {};
  const vulnTotal = (pip.vulnerabilities_total || 0) + (npm.high || 0) + (npm.critical || 0);
  if (badge) { badge.textContent = vulnTotal > 0 ? `${vulnTotal} issues` : '0 vulns'; badge.className = `card-badge ${vulnTotal > 0 ? 'badge-err' : 'badge-ok'}`; }
  el.innerHTML = [
    fwRow('Scan Date',    d.generated_at ? relTime(d.generated_at) : '--', 'info'),
    fwRow('pip Vulns',    pip.vulnerabilities_total ?? '--', (pip.vulnerabilities_total || 0) > 0 ? 'err' : 'ok'),
    fwRow('pip Files',    pip.files_scanned ?? '--', 'info'),
    fwRow('npm High',     npm.high ?? '--',           (npm.high || 0) > 0 ? 'err' : 'ok'),
    fwRow('npm Critical', npm.critical ?? '--',       (npm.critical || 0) > 0 ? 'err' : 'ok'),
    sr.status      ? fwRow('Secrets',    sr.status,    sr.status === 'current' ? 'ok' : 'warn') : '',
    dop.status     ? fwRow('Dashboard Op', dop.status, dop.status === 'ok' ? 'ok' : 'warn') : '',
  ].filter(Boolean).join('');
}

// ─── SECURITY: AUDIT SUMMARY ─────────────────────────────────────────────────
async function loadAuditSummary() {
  const d  = await apiFetch('/audit/operator/summary');
  const el = document.getElementById('auditSummaryDetails');
  const badge = document.getElementById('auditSummaryBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const topPaths = d.top_paths || [];
  const methods  = d.methods  || {};
  const statuses = d.statuses || {};
  const okRate   = statuses['200'] && d.total_events ? Math.round((statuses['200'] / d.total_events) * 100) : null;
  if (badge) { badge.textContent = d.total_events ? `${d.total_events.toLocaleString()} events` : '--'; badge.className = 'card-badge badge-ok'; }
  el.innerHTML = [
    fwRow('Total Events',  d.total_events != null ? d.total_events.toLocaleString() : '--'),
    fwRow('Tamper-Evident', d.tamper_evident ? 'yes' : 'no', d.tamper_evident ? 'ok' : 'warn'),
    okRate != null ? fwRow('Success Rate', `${okRate}%`, okRate >= 95 ? 'ok' : 'warn') : '',
    fwRow('Last Event', relTime(d.last_event_at)),
    Object.keys(methods).length ? fwRow('Methods', Object.entries(methods).map(([k,v]) => `${k}:${v}`).join(' '), 'info') : '',
  ].filter(Boolean).join('');
  if (topPaths.length) {
    el.innerHTML += `<div style="margin-top:.35rem;padding-top:.3rem;border-top:1px solid rgba(255,255,255,.05)">` +
      `<div style="font-size:.56rem;color:var(--fg3);text-transform:uppercase;margin-bottom:.2rem">Top Paths</div>` +
      topPaths.slice(0, 5).map(([path, cnt]) => fwRow(path.replace('/api','').slice(0,28), cnt, 'info')).join('') +
      `</div>`;
  }
}

async function loadToolDenyStats() {
  const d    = await apiFetch('/aistack/policy/tool-deny-stats');
  const el   = document.getElementById('toolDenyDetails');
  const badge = document.getElementById('toolDenyBadge');
  if (!el) return;
  if (!d || d.available === false) {
    el.innerHTML = fwRow('Status', 'Unavailable (needs rebuild)', 'warn');
    if (badge) { badge.textContent = '--'; badge.className = 'card-badge badge-warn'; }
    return;
  }
  const total = d.total_denials || 0;
  if (badge) {
    badge.textContent = total > 0 ? `${total} denied` : 'clean';
    badge.className = `card-badge ${total > 0 ? 'badge-warn' : 'badge-ok'}`;
  }
  const byTool    = d.by_tool    || {};
  const byProfile = d.by_profile || {};
  const policy    = d.policy     || {};
  const readonlyBlocked = (policy['readonly-strict'] || []).length;
  el.innerHTML = [
    fwRow('Total Denials',       total,           total > 0 ? 'warn' : 'ok'),
    fwRow('Readonly-strict',     byProfile['readonly-strict']  ?? 0, 'info'),
    fwRow('Execute-guarded',     byProfile['execute-guarded']  ?? 0, 'info'),
    fwRow('Blocked tools (policy)', readonlyBlocked, 'info'),
  ].join('');
  if (Object.keys(byTool).length) {
    el.innerHTML += `<div style="margin-top:.35rem;padding-top:.3rem;border-top:1px solid rgba(255,255,255,.05)">` +
      `<div style="font-size:.56rem;color:var(--fg3);text-transform:uppercase;margin-bottom:.2rem">Top Denied Tools</div>` +
      Object.entries(byTool).sort((a, b) => b[1] - a[1]).slice(0, 4)
        .map(([t, c]) => fwRow(t.replace(/_/g, ' ').slice(0, 28), c, 'warn')).join('') +
      `</div>`;
  }
}

async function loadSecurity() {
  await Promise.allSettled([
    loadFirewall(), loadSecMon(), loadCircuitBreakers(), loadHardening(),
    loadSecDrift(), loadAgentPool(), loadSecCompliance(),
    loadVulnAudit(), loadAuditSummary(), loadToolDenyStats(),
  ]);
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
  const off = s.offloading          || {};
  const ce  = s.context_efficiency  || {};
  const cg  = s.capability_gap      || {};
  const lrn = s.learning            || {};
  const rows = [
    fwRow('Offloading',    fmtImplStatus(off.status), 'ok'),
    fwRow('· profiles',    `${off.benchmarked_profiles ?? 0}/${off.quality_profiles ?? 0}`, 'info'),
    fwRow('· fallback',    off.local_fallback_mode || '--', 'info'),
    fwRow('Ctx Eff.',      fmtImplStatus(ce.status), 'ok'),
    fwRow('· A/B variants',ce.ab_variants ?? '--', 'info'),
    fwRow('· tokens saved',ce.tokens_saved != null ? ce.tokens_saved.toLocaleString() : '--'),
    fwRow('Cap Gaps',      fmtImplStatus(cg.status), 'ok'),
    fwRow('· detected',    cg.gaps_detected ?? 0, cg.gaps_detected > 0 ? 'warn' : 'ok'),
    fwRow('Learning',      fmtImplStatus(lrn.status), 'ok'),
    fwRow('· signals',     lrn.signals_recorded ?? 0),
    fwRow('· recommends',  lrn.recommendation_count ?? 0, lrn.recommendation_count > 0 ? 'ok' : ''),
  ];
  el.innerHTML = rows.join('');
}

async function loadHarnessOv() {
  const d  = await apiFetch('/harness/overview');
  const el = document.getElementById('harnessDetails');
  const badge = document.getElementById('harnessOvBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const s    = (d.harness || {}).stats || {};
  const card = (d.harness || {}).scorecard || {};
  const inf  = card.inference_optimizations || {};
  const disc = card.discovery || {};
  if (badge) { badge.textContent = d.status || '--'; badge.className = `card-badge ${statusColor(d.status) === 'ok' ? 'badge-ok' : 'badge-warn'}`; }
  const fails = (card.failures || {}).recent_failed_cases || [];
  el.innerHTML = [
    fwRow('Total Runs',   s.total_runs ?? 0),
    fwRow('Passed',       s.passed ?? 0,          (s.passed || 0) > 0 ? 'ok' : 'info'),
    fwRow('Failed',       s.failed ?? 0,           (s.failed || 0) > 0 ? 'err' : 'ok'),
    fwRow('Scorecards',   s.scorecards_generated ?? '--'),
    fwRow('Last Run',     s.last_run_at ? relTime(s.last_run_at) : 'never'),
    // Discovery metrics from scorecard
    disc.invoked != null ? fwRow('Discovery', `${disc.invoked} invoked · ${disc.skipped ?? 0} skip`, 'info') : '',
    disc.cache_hit_rate != null ? fwRow('Disc Cache', `${(disc.cache_hit_rate*100).toFixed(0)}%`, disc.cache_hit_rate > 0 ? 'ok' : 'warn') : '',
    // Inference optimization config (professional AI dashboard standard — always show)
    `<div style="margin-top:.35rem;padding-top:.3rem;border-top:1px solid rgba(255,255,255,.05);font-size:.56rem;color:var(--fg3);text-transform:uppercase;letter-spacing:.06em">Inference Config</div>`,
    fwRow('Prompt Cache',  inf.prompt_cache_policy_enabled ? 'enabled' : 'disabled', inf.prompt_cache_policy_enabled ? 'ok' : 'warn'),
    fwRow('Spec Decode',   inf.speculative_decoding_enabled ? `enabled (${inf.speculative_decoding_mode || 'draft'})` : 'disabled (MTP)', inf.speculative_decoding_enabled ? 'ok' : 'info'),
    fwRow('Ctx Compress',  inf.context_compression_enabled ? 'enabled' : 'disabled', inf.context_compression_enabled ? 'ok' : 'warn'),
  ].filter(Boolean).join('');
  if (fails.length) {
    el.innerHTML += `<div style="margin-top:.4rem;font-size:.57rem;color:var(--red)">Recent failures: ${fails.slice(0,3).join(', ')}</div>`;
  }
}

// ─── OPERATIONS: MODEL OPTIMIZATION ──────────────────────────────────────────
async function loadModelOptimization() {
  const d  = await apiFetch('/model-optimization/readiness');
  const el = document.getElementById('modelOptDetails');
  const badge = document.getElementById('modelOptBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const rd = d.readiness || {};
  const statusMap = { operational: 'ok', infrastructure_ready: 'ok', runtime_integrated: 'warn', pending: 'warn' };
  const rows = Object.entries(rd).map(([k, v]) => {
    const st = typeof v === 'object' ? (v.status || '') : String(v);
    const col = statusMap[st] || 'info';
    const extra = typeof v === 'object' && (v.captured_count != null || v.jobs != null || v.generated_files != null)
      ? ` (${v.captured_count ?? v.jobs ?? v.generated_files ?? 0})` : '';
    return fwRow(k.replace(/_/g, ' '), st + extra, col);
  });
  el.innerHTML = rows.join('') || fwRow('Status', 'No data');
  const allOp = Object.values(rd).every(v => (typeof v === 'object' ? v.status : v) === 'operational');
  if (badge) { badge.textContent = allOp ? 'ready' : 'partial'; badge.className = `card-badge ${allOp ? 'badge-ok' : 'badge-warn'}`; }
}

// ─── OPERATIONS: LEARNING PIPELINE ───────────────────────────────────────────
async function loadLearnPipeline() {
  const d  = await apiFetch('/stats/learning');
  const el = document.getElementById('learnPipelineDetails');
  const badge = document.getElementById('learnPipelineBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const bp  = d.backpressure || {};
  const act = d.activity || {};
  const paused = bp.paused || d.learning_paused;
  const files  = bp.file_sizes || {};
  const totalBytes = Object.values(files).reduce((s, b) => s + b, 0);
  const totalMb    = totalBytes / 1048576;
  if (badge) { badge.textContent = paused ? 'paused' : 'active'; badge.className = `card-badge ${paused ? 'badge-warn' : 'badge-ok'}`; }

  // KPI rows
  const kpis = [
    fwRow('Total Events',     act.total_events != null ? act.total_events.toLocaleString() : '--'),
    fwRow('Finetune Records', d.finetuning_dataset_size ?? '--', (d.finetuning_dataset_size || 0) > 0 ? 'ok' : 'info'),
    fwRow('Avg Feedback',     act.average_feedback_score != null ? act.average_feedback_score.toFixed(3) : '--',
                              act.average_feedback_score > 0.5 ? 'ok' : act.average_feedback_score > 0.2 ? 'warn' : 'err'),
    fwRow('Backpressure',     paused ? 'PAUSED' : 'nominal', paused ? 'warn' : 'ok'),
  ].join('');

  // Pipeline ingestion bars — visual volume indicator
  const maxBytes = Math.max(...Object.values(files), 1);
  const pipeNames = { 'hybrid-events': 'Hybrid', 'aidb-events': 'AIDB', 'ralph-events': 'RALPH', 'hint-feedback': 'Feedback', 'query-gaps': 'Gaps' };
  const bars = Object.entries(files).map(([fname, bytes]) => {
    const mb  = (bytes / 1048576).toFixed(0);
    const pct = Math.round((bytes / maxBytes) * 100);
    const key = Object.keys(pipeNames).find(k => fname.includes(k));
    const label = key ? pipeNames[key] : fname.replace('-events.jsonl','').replace('.jsonl','');
    return `<div style="display:flex;align-items:center;gap:.4rem;margin:.18rem 0">
      <span style="min-width:4.2rem;font-size:.57rem;color:var(--fg2)">${label}</span>
      <div style="flex:1;background:rgba(255,255,255,.06);border-radius:2px;height:6px">
        <div style="width:${pct}%;height:6px;border-radius:2px;background:var(--cyan);opacity:.7"></div>
      </div>
      <span style="min-width:2.8rem;text-align:right;font-size:.57rem;color:var(--fg3)">${mb}MB</span>
    </div>`;
  }).join('');

  el.innerHTML = kpis +
    `<div style="margin-top:.4rem;padding-top:.3rem;border-top:1px solid rgba(255,255,255,.05)">
      <div style="font-size:.56rem;color:var(--fg3);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.25rem">
        Pipeline Ingestion · ${totalMb.toFixed(0)}MB total
      </div>${bars}</div>`;
}

// ─── OPERATIONS: RALPH TASK TRACKER ──────────────────────────────────────────
async function loadRalph() {
  const d  = await apiFetch('/ralph/stats');
  const el = document.getElementById('ralphDetails');
  const badge = document.getElementById('ralphBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const total = (d.active_tasks || 0) + (d.completed_tasks || 0) + (d.failed_tasks || 0);
  const sRate = total > 0 && d.completed_tasks ? Math.round((d.completed_tasks / total) * 100) : null;
  if (badge) { badge.textContent = d.active_tasks ? `${d.active_tasks} active` : 'idle'; badge.className = `card-badge ${d.active_tasks > 0 ? 'badge-ok' : 'badge-info'}`; }
  el.innerHTML = [
    fwRow('Active Tasks',  d.active_tasks   ?? 0, (d.active_tasks || 0) > 0   ? 'ok'  : 'info'),
    fwRow('Completed',     d.completed_tasks ?? 0, (d.completed_tasks || 0) > 0 ? 'ok' : 'info'),
    fwRow('Failed',        d.failed_tasks   ?? 0, (d.failed_tasks || 0) > 0   ? 'err' : 'ok'),
    fwRow('Iterations',    d.total_iterations ?? 0),
    sRate != null ? fwRow('Success Rate', `${sRate}%`, sRate >= 80 ? 'ok' : 'warn') : '',
  ].filter(Boolean).join('');
}

// ─── OPERATIONS: TRAINING DATA CAPTURE ───────────────────────────────────────
async function loadTrainingData() {
  const d  = await apiFetch('/model-optimization/training-data/stats');
  const el = document.getElementById('trainingDataDetails');
  const badge = document.getElementById('trainingDataBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const cap  = d.capture_stats || {};
  const totFiles = (d.files || 0) + (d.synthetic_files || 0);
  const totBytes = (d.total_size_bytes || 0) + (d.synthetic_size_bytes || 0);
  if (badge) { badge.textContent = `${totFiles} files`; badge.className = `card-badge ${totFiles > 0 ? 'badge-ok' : 'badge-info'}`; }
  el.innerHTML = [
    fwRow('Captured',      cap.captured  ?? 0, (cap.captured || 0) > 0 ? 'ok' : 'info'),
    fwRow('Pending',       cap.pending   ?? 0, (cap.pending  || 0) > 10 ? 'warn' : 'ok'),
    fwRow('PII Filtered',  cap.filtered_pii ?? 0, (cap.filtered_pii || 0) > 0 ? 'warn' : 'ok'),
    fwRow('Low Quality',   cap.filtered_low_quality ?? 0, 'info'),
    fwRow('Train Files',   d.files         ?? 0),
    fwRow('Synth Files',   d.synthetic_files ?? 0, 'info'),
    totBytes > 0 ? fwRow('Total Size', `${(totBytes/1024).toFixed(0)} KB`) : fwRow('Total Size', '0 KB', 'info'),
  ].filter(Boolean).join('');
}

// ─── OPERATIONS: SYSTEM CONTROLS ─────────────────────────────────────────────
async function ctrlAction(endpoint, method, body, confirmMsg) {
  if (confirmMsg && !confirm(confirmMsg)) return;
  const opts = { method: method || 'POST', headers: {'Content-Type':'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const r = await apiFetch(endpoint, opts);
  const el = document.getElementById('ctrlResult');
  if (el) {
    el.textContent = r ? (r.status || r.message || 'done') : 'error';
    el.style.color = r ? 'var(--grn)' : 'var(--red)';
    setTimeout(() => { if (el) el.textContent = ''; }, 4000);
  }
  return r;
}

async function loadOperations() {
  await Promise.allSettled([
    loadQA(), loadDeployments(), loadPRSI(), loadRuntimeDetails(),
    loadHarnessOv(), loadModelOptimization(), loadLearnPipeline(),
    loadRalph(), loadTrainingData(), loadParityScorecard(),
    loadFleetSummary(), loadBudgetPolicy(), loadPortsRegistry(), loadHealthAggregate(),
  ]);
}

// ─── NEURAL MAP (D3) ──────────────────────────────────────────────────────────
async function initTopo() {
  const data = await apiFetch('/topology');
  const c    = document.getElementById('topoCanvas');
  if (!c) return;
  c.querySelectorAll('svg').forEach(s => s.remove());
  if (!window.d3) { setText('topoHud', 'D3_LOADING…'); setTimeout(initTopo, 800); return; }
  if (!data || !data.nodes) { setText('topoHud', 'DATA_UNAVAILABLE'); return; }
  // Normalise edge shape: topology uses from/to, D3 needs source/target
  const edges = (data.edges || data.links || []).map(e => ({
    source: e.source || e.from, target: e.target || e.to, label: e.label || ''
  }));
  const w = c.clientWidth  || 800;
  const h = c.clientHeight || 500;
  const svg = d3.select('#topoCanvas').append('svg').attr('width','100%').attr('height','100%');
  const g   = svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.1,8]).on('zoom', e => g.attr('transform', e.transform)));
  const sim = d3.forceSimulation(data.nodes)
    .force('link',   d3.forceLink(edges).id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(w/2, h/2))
    .force('coll',   d3.forceCollide(18));
  const link = g.append('g').selectAll('line').data(edges).enter().append('line').attr('class','link-line');
  const node = g.append('g').selectAll('g').data(data.nodes).enter().append('g')
    .call(d3.drag()
      .on('start', (e,d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on('drag',  (e,d) => { d.fx=e.x; d.fy=e.y; })
      .on('end',   (e,d) => { if (!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }));
  const roleColor = r => r === 'inference' ? 'var(--cyan)' : r === 'coordinator' ? 'var(--mag)'
    : r === 'vector-db' ? '#f4a261' : r === 'rag' ? '#2ec4b6' : r === 'embeddings' ? '#a8dadc'
    : r === 'dashboard' ? '#e9c46a' : 'var(--fg3)';
  node.append('circle')
    .attr('r', d => d.role === 'coordinator' ? 12 : d.role === 'inference' ? 10 : 8)
    .attr('fill', d => d.color || roleColor(d.role || d.type))
    .attr('stroke','var(--bg)').attr('stroke-width',2);
  node.append('text').attr('class','node-label').attr('dx',15).attr('dy','.35em')
    .text(d => d.label || d.id);
  sim.on('tick', () => {
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
  setText('topoHud', `NODES:${data.nodes.length} EDGES:${edges.length}`);
}

// ─── LOGIC DAG (Mermaid) ──────────────────────────────────────────────────────
let _logicRetries = 0;
async function initLogic() {
  const data = await apiFetch('/topology/flow');
  const c    = document.getElementById('logicCanvas');
  if (!c) return;
  const flowchart = data && (data.flowchart || data.mermaid);
  if (!flowchart) { setText('logicHud', 'DATA_UNAVAILABLE'); return; }
  if (!window.mermaid) {
    _logicRetries++;
    if (_logicRetries > 10) {
      // Mermaid CDN failed — show raw text fallback
      c.innerHTML = `<pre style="color:var(--fg2);font-size:.65rem;padding:1rem;overflow:auto;height:100%">${flowchart}</pre>`;
      setText('logicHud', 'RAW_MERMAID (CDN unavailable)');
      return;
    }
    setText('logicHud', `MERMAID_LOADING (${_logicRetries}/10)`);
    setTimeout(initLogic, 1000);
    return;
  }
  _logicRetries = 0;
  try {
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose',
      themeVariables: { primaryColor: '#0d1220', primaryTextColor: '#e2eaf4',
        primaryBorderColor: '#00d9ff', lineColor: '#d400ff', background: '#080c12' }});
    const id = 'mermaid-flow';
    c.innerHTML = `<div id="${id}" style="width:100%;overflow:auto;padding:1rem"></div>`;
    const uid = 'mermaid-svg-' + Date.now();
    const { svg } = await mermaid.render(uid, flowchart);
    document.getElementById(id).innerHTML = svg;
    setText('logicHud', 'REQUEST_FLOW: RENDERED');
  } catch (e) {
    c.innerHTML = `<pre style="color:var(--fg2);font-size:.65rem;padding:1rem;overflow:auto;height:100%">${flowchart}</pre>`;
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

// ─── OVERVIEW: HARDWARE THERMAL STATE ────────────────────────────────────────
async function loadHardwareState() {
  const d  = await apiFetch('/hardware/state');
  const el = document.getElementById('hwStateDetails');
  const badge = document.getElementById('hwStateBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const tier = d.thermal_tier || 'unknown';
  const tierColor = tier === 'optimal' ? 'ok' : tier === 'warm' ? 'warn' : tier === 'critical' || tier === 'shutdown' ? 'err' : 'info';
  if (badge) { badge.textContent = tier; badge.className = `card-badge ${tierColor === 'ok' ? 'badge-ok' : tierColor === 'warn' ? 'badge-warn' : 'badge-err'}`; }
  // Also update the KPI thermal badge if present
  setText('kpiThermal', tier);
  const kpiTh = document.getElementById('kpiThermal');
  if (kpiTh) kpiTh.className = `kpi-v ${tierColor}`;
  el.innerHTML = [
    fwRow('Thermal Tier',   tier,                                            tierColor),
    fwRow('CPU Temp',       d.temp_cpu_c != null ? `${d.temp_cpu_c.toFixed(1)}°C` : '--',
                            d.temp_cpu_c >= 85 ? 'err' : d.temp_cpu_c >= 75 ? 'warn' : 'ok'),
    fwRow('GPU Temp',       d.temp_gpu_c != null ? `${d.temp_gpu_c.toFixed(1)}°C` : '--',
                            d.temp_gpu_c >= 85 ? 'err' : d.temp_gpu_c >= 70 ? 'warn' : 'ok'),
    fwRow('RAM Used',       d.ram_used_pct != null ? `${d.ram_used_pct.toFixed(1)}%` : '--',
                            d.ram_used_pct >= 90 ? 'err' : d.ram_used_pct >= 75 ? 'warn' : 'ok'),
    fwRow('RAM Free',       d.ram_free_gb != null ? `${d.ram_free_gb.toFixed(1)} GB` : '--'),
    fwRow('GPU Layers',     d.n_gpu_layers_current ?? '--', 'info'),
    d.mtp_acceptance_rate != null ? fwRow('MTP Accept', `${(d.mtp_acceptance_rate*100).toFixed(1)}%`) : '',
  ].filter(Boolean).join('');
}

// ─── INTELLIGENCE: MLFQ SCHEDULER STATUS ─────────────────────────────────────
async function loadSchedulerStatus() {
  const d  = await apiFetch('/scheduler/status');
  const el = document.getElementById('schedulerDetails');
  const badge = document.getElementById('schedulerBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const tier   = d.thermal_tier || 'unknown';
  const queues = d.queue_depths || {};
  const limits = d.concurrency_limits || {};
  const cfgLim = d.configured_concurrency_limits || {};
  const budget = d.token_budget || {};
  const totalQ = Object.values(queues).reduce((s, v) => s + v, 0);
  const tierColor = tier === 'optimal' ? 'ok' : tier === 'warm' ? 'warn' : 'err';
  if (badge) { badge.textContent = tier; badge.className = `card-badge ${tierColor === 'ok' ? 'badge-ok' : tierColor === 'warn' ? 'badge-warn' : 'badge-err'}`; }
  el.innerHTML = [
    fwRow('Thermal Gate',    tier, tierColor),
    fwRow('Running',         d.running_count ?? 0),
    fwRow('Zombies',         d.zombie_count ?? 0, (d.zombie_count || 0) > 0 ? 'warn' : 'ok'),
    fwRow('Queue (L0/1/2)',  `${queues.L0||0} / ${queues.L1||0} / ${queues.L2||0}`, totalQ > 0 ? 'info' : 'ok'),
    // Concurrency: show current vs configured (thermal gating may reduce L1)
    fwRow('Concur L0',       `${limits.L0??'--'} / ${cfgLim.L0??'--'}`, 'info'),
    fwRow('Concur L1',       `${limits.L1??'--'} / ${cfgLim.L1??'--'}`, limits.L1 < cfgLim.L1 ? 'warn' : 'ok'),
    fwRow('Concur L2',       `${limits.L2??'--'} / ${cfgLim.L2??'--'}`, 'info'),
    budget.L0 ? fwRow('Token Budget', `${((budget.L0+budget.L1+budget.L2)/1e6).toFixed(2)}M total`, 'info') : '',
  ].filter(Boolean).join('');
}

// ─── INTELLIGENCE: CONTEXT LIFECYCLE MANAGER ─────────────────────────────────
async function loadCLMStatus() {
  const d  = await apiFetch('/context/lifecycle/status');
  const el = document.getElementById('clmDetails');
  const badge = document.getElementById('clmBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const tiers    = d.tiers || {};
  const pressure = d.pressure_pct || 0;
  const suspended= d.compaction_suspended;
  const tierColor= pressure >= 85 ? 'err' : pressure >= 60 ? 'warn' : 'ok';
  if (badge) { badge.textContent = suspended ? 'suspended' : 'active'; badge.className = `card-badge ${suspended ? 'badge-warn' : 'badge-ok'}`; }
  const thresholds = d.thresholds || {};
  el.innerHTML = [
    fwRow('Hot Sessions',     tiers.hot  ?? 0, (tiers.hot  || 0) > 0 ? 'ok' : 'info'),
    fwRow('Warm Sessions',    tiers.warm ?? 0, 'info'),
    fwRow('Cold Sessions',    tiers.cold ?? 0, 'info'),
    fwRow('Session Count',    d.session_count ?? 0),
    fwRow('Hot Redis',        d.hot_redis_mb != null ? `${d.hot_redis_mb.toFixed(1)} MB / ${d.hot_max_mb||256} MB` : '--'),
    fwRow('Pressure',         `${pressure.toFixed(1)}%`, tierColor),
    fwRow('Compaction',       suspended ? 'SUSPENDED (thermal)' : 'active', suspended ? 'warn' : 'ok'),
    thresholds.hot_idle_secs  ? fwRow('Hot Idle TTL',  `${thresholds.hot_idle_secs}s`,  'info') : '',
    thresholds.warm_idle_secs ? fwRow('Warm Idle TTL', `${thresholds.warm_idle_secs}s`, 'info') : '',
  ].filter(Boolean).join('');
}

// ─── INTELLIGENCE: HINTS REGISTRY ────────────────────────────────────────────
async function loadHintsRegistry() {
  const d  = await apiFetch('/hints/active');
  const el = document.getElementById('hintsRegistryDetails');
  const badge = document.getElementById('hintsRegistryBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const hints = d.hints || [];
  if (badge) { badge.textContent = `${hints.length} hints`; badge.className = 'card-badge badge-ok'; }
  el.innerHTML = hints.length
    ? hints.slice(0, 8).map(h =>
        `<div class="fw-row"><span class="fk" style="max-width:10rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${h.title || h.id}</span><span class="fv info">${h.type || 'hint'} · ${h.score != null ? (h.score*100).toFixed(0)+'%' : ''}</span></div>`
      ).join('')
    : fwRow('Hints', 'No active hints', 'info');
}

// ─── INTELLIGENCE: MEMORY BROKER + CRYSTALLIZATION ───────────────────────────
async function loadMemoryBroker() {
  const [broker, crystal] = await Promise.all([
    apiFetch('/memory/broker/status'),
    apiFetch('/memory/crystalline/status'),
  ]);
  const el = document.getElementById('memoryBrokerDetails');
  const badge = document.getElementById('memoryBrokerBadge');
  if (!el) return;
  const brokerOk = broker && broker.initialized;
  if (badge) { badge.textContent = brokerOk ? 'online' : 'offline'; badge.className = `card-badge ${brokerOk ? 'badge-ok' : 'badge-warn'}`; }
  const types = (broker && broker.memory_types) || [];
  const contradictions = broker ? (broker.contradiction_pairs ?? 0) : 0;
  const sessionsProcessed = crystal ? (crystal.sessions_processed ?? 0) : '--';
  const insightsStored    = crystal ? (crystal.insights_stored    ?? 0) : '--';
  const lastRun = crystal && crystal.last_run ? relTime(crystal.last_run) : 'never';
  el.innerHTML = [
    fwRow('Status',              brokerOk ? 'initialized' : 'offline', brokerOk ? 'ok' : 'err'),
    fwRow('Memory Types',        types.length ? types.join(', ') : '--', 'info'),
    fwRow('Contradiction Pairs', contradictions, contradictions > 10 ? 'warn' : 'ok'),
    '<div style="font-size:.55rem;color:var(--fg3);margin:.45rem 0 .2rem;text-transform:uppercase">Crystallization</div>',
    fwRow('Sessions Processed',  sessionsProcessed, sessionsProcessed > 0 ? 'ok' : 'info'),
    fwRow('Insights Stored',     insightsStored,    insightsStored > 0    ? 'ok' : 'info'),
    fwRow('Last Run',            lastRun, 'info'),
  ].filter(Boolean).join('');
}

// ─── INTELLIGENCE: AFFECTIVE STATE ───────────────────────────────────────────
async function loadAffectiveState() {
  const d  = await apiFetch('/affective/state');
  const el = document.getElementById('affectiveDetails');
  const badge = document.getElementById('affectiveBadge');
  if (!el) return;
  if (!d || d.available === false || !d.enabled) {
    el.innerHTML = fwRow('Status', 'not enabled', 'info');
    if (badge) { badge.textContent = 'off'; badge.className = 'card-badge badge-info'; }
    return;
  }
  const s = d.state || {};
  const dominant = s.dominant_signal || 'neutral';
  const domColor = dominant === 'neutral' ? 'ok' : dominant === 'positive' ? 'ok' : 'warn';
  if (badge) { badge.textContent = dominant; badge.className = `card-badge ${domColor === 'ok' ? 'badge-ok' : 'badge-warn'}`; }
  el.innerHTML = [
    fwRow('Dominant Signal',   dominant,                    domColor),
    fwRow('Empathy Signal',    s.empathy_signal     != null ? s.empathy_signal.toFixed(3)     : '--', 'info'),
    fwRow('Reciprocity Debt',  s.reciprocity_debt   != null ? s.reciprocity_debt.toFixed(3)   : '--', s.reciprocity_debt > 0.5 ? 'warn' : 'ok'),
    fwRow('Aesthetic Gap',     s.aesthetic_gap      != null ? s.aesthetic_gap.toFixed(3)      : '--', 'info'),
    fwRow('Compassion Level',  s.compassion_level   != null ? s.compassion_level.toFixed(3)   : '--', 'info'),
    s.timestamp ? fwRow('Updated', relTime(s.timestamp), 'info') : '',
  ].filter(Boolean).join('');
}

// ─── OPERATIONS: PARITY SCORECARD ────────────────────────────────────────────
async function loadParityScorecard() {
  const d  = await apiFetch('/parity/scorecard');
  const el = document.getElementById('parityDetails');
  const badge = document.getElementById('parityBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const sc = d.scorecard || {};
  const tracks = sc.tracks || [];
  const totalScore = sc.total_score ?? null;
  const pass = tracks.filter(t => t.status === 'complete').length;
  const partial = tracks.filter(t => t.status === 'partial').length;
  const fail = tracks.filter(t => t.status === 'failing').length;
  const color = fail > 0 ? 'err' : partial > 0 ? 'warn' : 'ok';
  if (badge) { badge.textContent = totalScore != null ? `${(totalScore*100).toFixed(0)}%` : `${pass}/${tracks.length}`; badge.className = `card-badge badge-${color === 'ok' ? 'ok' : color === 'warn' ? 'warn' : 'err'}`; }
  el.innerHTML = tracks.length
    ? tracks.map(t => fwRow(t.id.replace(/_/g,' '), t.status, t.status==='complete'?'ok':t.status==='partial'?'warn':'err')).join('')
    : fwRow('Status', 'No tracks', 'info');
}

// ─── INTELLIGENCE: AI COORDINATOR ────────────────────────────────────────────
async function loadAICoordinator() {
  const d  = await apiFetch('/coordinator/ai-status');
  const el = document.getElementById('aiCoordDetails');
  const badge = document.getElementById('aiCoordBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const ok = d.status === 'ok';
  if (badge) { badge.textContent = d.status || '--'; badge.className = `card-badge ${ok ? 'badge-ok' : 'badge-warn'}`; }
  const aliases = d.remote_aliases || {};
  const aliasCount = Object.keys(aliases).length;
  const skills = (d.shared_skill_registry || {}).total ?? '--';
  el.innerHTML = [
    fwRow('Status',          d.status || '--',            ok ? 'ok' : 'warn'),
    fwRow('Switchboard',     d.switchboard_url ? 'connected' : '--', d.switchboard_url ? 'ok' : 'warn'),
    fwRow('Remote Aliases',  aliasCount > 0 ? `${aliasCount} configured` : '--', aliasCount > 0 ? 'ok' : 'info'),
    fwRow('Skill Registry',  skills !== '--' ? `${skills} skills` : '--',         skills > 0 ? 'ok' : 'info'),
    ...Object.entries(aliases).map(([name, model]) =>
      fwRow(`  ∟ ${name}`, model.split('/').slice(-1)[0] || model, 'info')
    ),
  ].join('');
}

// ─── INTELLIGENCE: REASONING PROFILES ────────────────────────────────────────
async function loadReasoningProfiles() {
  const d  = await apiFetch('/reasoning/profiles');
  const el = document.getElementById('reasoningProfilesDetails');
  const badge = document.getElementById('reasoningProfilesBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const profiles = d.profiles || d.data || [];
  if (badge) { badge.textContent = `${profiles.length} profiles`; badge.className = 'card-badge badge-info'; }
  if (!profiles.length) { el.innerHTML = fwRow('Profiles', 'none', 'info'); return; }
  el.innerHTML = profiles.slice(0, 8).map(p => {
    const active = p.active || p.is_active;
    const name   = p.name || p.id || '--';
    const style  = p.reasoning_style || p.style || '--';
    return `<div class="fw-row" style="align-items:flex-start">
      <span class="fk" style="color:${active ? 'var(--grn)' : 'var(--fg2)'}">${name}</span>
      <span class="fv info" style="text-align:right;max-width:55%">${style}</span>
    </div>`;
  }).join('');
}

// ─── OPERATIONS: FLEET RUNTIMES ───────────────────────────────────────────────
async function loadFleetSummary() {
  const d  = await apiFetch('/fleet/summary');
  const el = document.getElementById('fleetDetails');
  const badge = document.getElementById('fleetBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const total = d.total_runtimes ?? '--';
  const byStatus  = d.by_status  || {};
  const byProfile = d.by_profile || {};
  const ready  = byStatus.ready  ?? 0;
  const active = byStatus.active ?? 0;
  const color  = total > 0 ? 'ok' : 'warn';
  if (badge) { badge.textContent = `${total} runtimes`; badge.className = `card-badge badge-${color}`; }
  el.innerHTML = [
    fwRow('Total Runtimes',  total,  color),
    fwRow('Ready',           ready,  ready > 0 ? 'ok' : 'info'),
    fwRow('Active',          active, active > 0 ? 'ok' : 'info'),
    ...Object.entries(byProfile).slice(0, 8).map(([prof, cnt]) =>
      fwRow(`  ∟ ${prof}`, cnt, 'info')
    ),
  ].join('');
}

// ─── OPERATIONS: BUDGET POLICY ────────────────────────────────────────────────
async function loadBudgetPolicy() {
  const d  = await apiFetch('/budget/policy');
  const el = document.getElementById('budgetDetails');
  const badge = document.getElementById('budgetBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const policy = d.policy || {};
  const def    = policy.default || {};
  const enf    = policy.enforcement || {};
  const enfEnabled = enf.enabled ?? false;
  if (badge) { badge.textContent = enfEnabled ? 'enforced' : 'passive'; badge.className = `card-badge ${enfEnabled ? 'badge-ok' : 'badge-warn'}`; }
  el.innerHTML = [
    fwRow('Enforcement',     enfEnabled ? 'active' : 'disabled',          enfEnabled ? 'ok' : 'warn'),
    fwRow('Token Limit',     def.token_limit     ? `${def.token_limit.toLocaleString()}` : '--',  'info'),
    fwRow('Tool Call Limit', def.tool_call_limit ?? '--',                   'info'),
    fwRow('Time Limit',      def.time_limit_seconds ? `${def.time_limit_seconds}s` : '--',        'info'),
    fwRow('Warn Threshold',  def.warn_threshold_pct ? `${def.warn_threshold_pct}%` : '--',        'info'),
    fwRow('Fail Safe',       def.fail_safe || '--',                         def.fail_safe === 'abort' ? 'warn' : 'info'),
    fwRow('Scope',           (enf.scope || []).join(', ') || '--',          'info'),
  ].join('');
}

// ─── INTELLIGENCE: AGENT OPS STATUS ──────────────────────────────────────────
async function loadAgentOpsStatus() {
  const d  = await apiFetch('/agent-ops/status');
  const el = document.getElementById('agentOpsDetails');
  const badge = document.getElementById('agentOpsBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const alertOn  = d.alert_active;
  const drift    = d.drift_score ?? 0;
  const override = d.profile_override;
  const color    = alertOn ? 'err' : drift > 0.4 ? 'warn' : 'ok';
  if (badge) { badge.textContent = alertOn ? 'ALERT' : override ? 'override' : 'nominal'; badge.className = `card-badge ${color === 'ok' ? 'badge-ok' : color === 'warn' ? 'badge-warn' : 'badge-err'}`; }
  el.innerHTML = [
    fwRow('Alert Active',    alertOn ? 'YES' : 'no',                       alertOn ? 'err' : 'ok'),
    fwRow('Drift Score',     drift.toFixed(3),                              drift > 0.4 ? 'warn' : 'ok'),
    fwRow('Profile Override',override || 'none',                            override ? 'warn' : 'ok'),
    fwRow('Window Size',     d.window_size ?? '--',                         'info'),
    d.since ? fwRow('Alert Since', relTime(d.since), 'warn') : '',
  ].filter(Boolean).join('');
}

// ─── INTELLIGENCE: AGENT LESSONS ─────────────────────────────────────────────
async function loadAgentLessons() {
  const d  = await apiFetch('/hints/report');
  const el = document.getElementById('agentLessonsDetails');
  const badge = document.getElementById('agentLessonsBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const lessons = (d.agent_lessons || {}).registry || {};
  const entries = (lessons.entries || []).filter(e => e.state === 'promoted');
  if (badge) { badge.textContent = `${entries.length} promoted`; badge.className = 'card-badge badge-ok'; }
  if (!entries.length) { el.innerHTML = fwRow('Promoted Lessons', '0', 'info'); return; }
  el.innerHTML = entries.slice(0, 6).map(e => {
    const parts = (e.lesson_key || '').split('::');
    const agent = parts[0] || '--';
    const label = parts.slice(1).join('::').replace(/-/g,' ').slice(0,30) || '--';
    const conf  = e.confidence != null ? `${(e.confidence*100).toFixed(0)}%` : '--';
    return `<div class="fw-row">
      <span class="fk" title="${e.lesson_key}">${agent}: ${label}</span>
      <span class="fv ok">${conf}</span>
    </div>`;
  }).join('');
}

// ─── INTELLIGENCE: MEMORY STATS ───────────────────────────────────────────────
async function loadMemStats() {
  const d  = await apiFetch('/memory/stats');
  const el = document.getElementById('memStatsDetails');
  const badge = document.getElementById('memStatsBadge');
  if (!el) return;
  if (!d || d.available === false) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  if (badge) { badge.textContent = `${d.memory_type_count ?? '--'} types`; badge.className = 'card-badge badge-info'; }
  el.innerHTML = [
    fwRow('Initialized',       d.initialized ? 'yes' : 'no',             d.initialized ? 'ok' : 'warn'),
    fwRow('Memory Types',      d.memory_type_count ?? '--',               'info'),
    fwRow('Contradiction Pairs',d.contradiction_pairs ?? 0,               d.contradiction_pairs > 0 ? 'warn' : 'ok'),
    fwRow('Supersession Events',d.supersession_events ?? 0,               d.supersession_events > 0 ? 'ok' : 'info'),
    fwRow('Sessions Processed',d.sessions_processed ?? 0,                 'info'),
    fwRow('Insights Stored',   d.insights_stored ?? 0,                    'info'),
    d.timestamp ? fwRow('Updated', relTime(d.timestamp), 'info') : '',
  ].filter(Boolean).join('');
}

// ─── OPERATIONS: PORTS REGISTRY ──────────────────────────────────────────────
async function loadPortsRegistry() {
  const d  = await apiFetch('/ports/registry');
  const el = document.getElementById('portsRegDetails');
  const badge = document.getElementById('portsRegBadge');
  if (!el) return;
  if (!d || !d.services) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const svcCount = Object.keys(d.services).length;
  if (badge) { badge.textContent = `${svcCount} services`; badge.className = 'card-badge badge-info'; }
  el.innerHTML = Object.entries(d.services).slice(0, 12).map(([name, info]) => {
    const port = info.port || info.Port || '--';
    const label = name.replace(/_/g,' ');
    return fwRow(label, `:${port}`, 'info');
  }).join('');
}

// ─── OPERATIONS: HEALTH AGGREGATE ────────────────────────────────────────────
async function loadHealthAggregate() {
  const d  = await apiFetch('/health/aggregate');
  const el = document.getElementById('healthAggDetails');
  const badge = document.getElementById('healthAggBadge');
  if (!el) return;
  if (!d) { el.innerHTML = fwRow('Status', 'Unavailable', 'warn'); return; }
  const overall = d.overall_status || 'unknown';
  const color   = overall === 'healthy' ? 'ok' : overall === 'degraded' ? 'warn' : 'err';
  if (badge) { badge.textContent = overall; badge.className = `card-badge badge-${color}`; }
  const svcs    = d.services || {};
  const summary = d.summary  || {};
  el.innerHTML = [
    fwRow('Overall',    overall,                                   color),
    fwRow('Healthy',    summary.healthy   ?? Object.values(svcs).filter(s=>s.status==='healthy').length,   'ok'),
    fwRow('Degraded',   summary.degraded  ?? Object.values(svcs).filter(s=>s.status==='degraded').length,  'warn'),
    fwRow('Unhealthy',  summary.unhealthy ?? Object.values(svcs).filter(s=>s.status==='unhealthy').length, 'err'),
    ...Object.entries(svcs).slice(0, 8).map(([name, info]) => {
      const st = info.status || 'unknown';
      const c  = st === 'healthy' ? 'ok' : st === 'degraded' ? 'warn' : 'err';
      return fwRow(`  ∟ ${name.replace(/^ai-/,'').replace(/-/g,' ')}`, st, c);
    }),
  ].join('');
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
  await Promise.allSettled([loadKPIs(), loadRagQuality(), loadSystem(), loadServices(), loadDatabase(), loadOSI(), loadRemediations(), loadAuditLog(), loadHardwareState()]);
  loadLens(activeLens);
}

// ─── INIT ────────────────────────────────────────────────────────────────────
window.addEventListener('error', e => {
  const b = document.getElementById('err-banner');
  if (b) { b.textContent = `JS Error: ${e.message} (${e.filename}:${e.lineno})`; b.style.display = 'block'; }
});

document.addEventListener('DOMContentLoaded', () => {
  // Immediate: fast data (hardware state included — thermal is real-time critical)
  Promise.allSettled([loadKPIs(), loadRagQuality(), loadSystem(), loadServices(), loadHardwareState()]);
  // Deferred: DB metrics + slow OSI health + audit
  setTimeout(() => { loadDatabase(); loadOSI(); loadRemediations(); loadAuditLog(); }, 400);
  // Periodic refresh
  setInterval(loadKPIs,          30_000);
  setInterval(loadRagQuality,    60_000);
  setInterval(loadSystem,        30_000);
  setInterval(loadServices,      30_000);
  setInterval(loadDatabase,      60_000);
  setInterval(loadHardwareState, 30_000);  // thermal tier changes fast
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
