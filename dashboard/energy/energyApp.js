// Smart Energy BMS Main Orchestrator (ES Module)
// Preserves all FastAPI integrations, state management, simulation mode, ACK, and CSV export.

import {
  FLOORPLAN_ROOMS,
  buildEnergyPreviewSnapshot,
  computeRoomStatus,
  resolveEnergyAlertRoom
} from './constants.js';
import { EnergyFloorPlanComponent } from './floorplan.js';
import { updateEnergyKpiStrip } from './kpiStrip.js';
import { EnergyAnalyticsComponent } from './analyticsCharts.js';
import { renderAnomalyFeed, renderRoomDetailPanel } from './roomDetailPanel.js';

const enState = {
  previewMode: false,
  selectedRoom: 'r3012',
  hasUserSelectedRoom: false,
  rooms: [],
  alerts: [],
  bill: null,
  waste: null,
  telemetry: [],
  baseline: [],
  roomsMap: new Map(),
  sortKey: 'device_id',
  sortAsc: true,
  activeExtraTab: 'baseline',
  previewAckedIds: {},
  lastApiError: null
};

const floorPlanHost = document.getElementById('en-floorplan-host');
const floorPlan = new EnergyFloorPlanComponent(floorPlanHost, {
  onSelectRoom: (ruang) => selectRoom(ruang)
});
const analytics = new EnergyAnalyticsComponent();

function updateConsolidatedStatusPill(mode, detailText = '') {
  const pill = document.getElementById('en-status-pill');
  const dot = document.getElementById('en-status-pill-dot');
  const text = document.getElementById('en-status-pill-text');
  if (!pill || !dot || !text) return;

  if (mode === 'sim') {
    pill.className = 'inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-200 border border-amber-400/35 whitespace-nowrap';
    dot.className = 'w-1.5 h-1.5 rounded-full bg-amber-400';
    text.textContent = 'Mode Simulasi';
  } else if (mode === 'error') {
    pill.className = 'inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full bg-rose-500/15 text-rose-200 border border-rose-500/35 whitespace-nowrap';
    dot.className = 'w-1.5 h-1.5 rounded-full bg-rose-400';
    text.textContent = detailText || 'API Terputus';
  } else {
    pill.className = 'inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-200 border border-emerald-400/30 whitespace-nowrap';
    dot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-400';
    text.textContent = 'Live FastAPI';
  }
}

function buildRoomsMap({ rooms, bill, alerts, baseline }) {
  const roomApiMap = new Map((rooms || []).map(r => [r.ruang, r]));
  const billMap = new Map((bill?.per_ruang || []).map(b => [b.ruang, b]));
  const baseMap = new Map((baseline || []).map(b => [b.ruang, b]));
  const map = new Map();

  for (const cfg of FLOORPLAN_ROOMS) {
    const rApi = roomApiMap.get(cfg.ruang) || {};
    const bApi = billMap.get(cfg.ruang) || {};
    const bsApi = baseMap.get(cfg.ruang) || {};
    const rAlerts = (alerts || []).filter(a => {
      const aRoom = resolveEnergyAlertRoom(a, rooms);
      return a.device_id === cfg.device_id || aRoom === cfg.ruang;
    });
    const online = rApi.status === 'online' || Boolean(rApi.online);
    const pw = Number(rApi.power_w || 0);
    const visualStatus = computeRoomStatus(rApi, rAlerts);

    map.set(cfg.ruang, {
      ...cfg,
      online,
      visualStatus,
      power_w: pw,
      energy_kwh: Number(bApi.energy_kwh ?? rApi.energy_kwh ?? 0),
      bill_idr: Number(bApi.estimasi_tagihan_idr ?? 0),
      avg_work_w: bsApi.avg_work_hours_w ?? null,
      avg_after_w: bsApi.avg_after_hours_w ?? null,
      last_seen: rApi.last_seen || null,
      alerts: rAlerts
    });
  }
  return map;
}

function selectRoom(ruang) {
  if (!FLOORPLAN_ROOMS.some(r => r.ruang === ruang)) return;
  enState.selectedRoom = ruang;
  enState.hasUserSelectedRoom = true;
  renderAllViews();
}

function renderAllViews() {
  const period = document.getElementById('en-bill-period')?.value || 'daily';
  const roomFilter = document.getElementById('en-room-filter')?.value || 'all';
  const winSel = document.getElementById('en-window-select');
  const winLabel = winSel?.options[winSel.selectedIndex]?.textContent || '1 Jam';

  // If user filtered to a specific room, keep selection synced to that room
  if (roomFilter !== 'all' && FLOORPLAN_ROOMS.some(r => r.ruang === roomFilter)) {
    enState.selectedRoom = roomFilter;
  } else if (!enState.hasUserSelectedRoom) {
    // Pick the most interesting room automatically (alert > online > r3012)
    const priority = Array.from(enState.roomsMap.values()).find(r => r.visualStatus === 'high_load' || r.visualStatus === 'waste')
      || Array.from(enState.roomsMap.values()).find(r => r.online)
      || enState.roomsMap.get('r3012');
    if (priority) enState.selectedRoom = priority.ruang;
  }

  updateEnergyKpiStrip({
    rooms: enState.rooms,
    bill: enState.bill,
    waste: enState.waste,
    period,
    roomFilter
  });

  floorPlan.update({
    roomsMap: enState.roomsMap,
    selectedRoom: enState.selectedRoom,
    roomFilter
  });

  analytics.renderPowerChart(enState.telemetry, roomFilter, winLabel);
  analytics.renderDonutChart(enState.bill?.per_ruang || [], roomFilter);
  analytics.renderBaselineChart(enState.baseline, roomFilter);
  analytics.renderMetersTable({
    rooms: enState.rooms,
    roomFilter,
    sortKey: enState.sortKey,
    sortAsc: enState.sortAsc,
    onSelectRoom: (ruang) => selectRoom(ruang)
  });

  renderRoomDetailPanel({
    roomsMap: enState.roomsMap,
    selectedRoom: enState.selectedRoom,
    allAlerts: enState.alerts,
    allRooms: enState.rooms,
    roomFilter,
    onSelectRoom: (ruang) => selectRoom(ruang),
    onAckAlert: (alertId) => ackEnergyAlert(alertId),
    onFilterToRoom: (targetRoom) => {
      const sel = document.getElementById('en-room-filter');
      if (sel) {
        sel.value = targetRoom;
        fetchEnergyRooms();
      }
    },
    onExportRoomCsv: (targetRoom) => exportEnergyCsv(targetRoom)
  });

  document.querySelectorAll('.en-empty-preview-btn').forEach(el => {
    el.classList.toggle('hidden', enState.previewMode);
  });
}

function applyEnergyDashboardData({ rooms, bill, waste, alerts, telemetry, baseline }) {
  enState.rooms = rooms || [];
  enState.bill = bill || null;
  enState.waste = waste || null;
  enState.alerts = alerts || [];
  enState.telemetry = telemetry || [];
  enState.baseline = baseline || [];
  enState.roomsMap = buildRoomsMap({ rooms: enState.rooms, bill: enState.bill, alerts: enState.alerts, baseline: enState.baseline });
  renderAllViews();
}

async function fetchEnergyRooms() {
  const period = document.getElementById('en-bill-period')?.value || 'daily';
  const winSel = document.getElementById('en-window-select');
  const winRel = winSel?.value || '-1h';
  const winMins = Number(winSel?.options[winSel.selectedIndex]?.dataset?.mins || 60);
  const loadingEl = document.getElementById('en-loading-indicator');
  const errStrip = document.getElementById('en-error-strip');
  const errText = document.getElementById('en-error-text');

  if (enState.previewMode) {
    errStrip?.classList.add('hidden');
    loadingEl?.classList.add('hidden');
    updateConsolidatedStatusPill('sim');
    applyEnergyDashboardData(buildEnergyPreviewSnapshot(period, winMins, enState.previewAckedIds));
    return;
  }

  loadingEl?.classList.remove('hidden');
  try {
    const [roomsRes, billRes, wasteRes, alertsRes, telemRes, baseRes] = await Promise.all([
      fetch('/api/v1/energy/rooms'),
      fetch(`/api/v1/energy/bill?period=${encodeURIComponent(period)}`),
      fetch('/api/v1/energy/waste'),
      fetch('/api/v1/alerts?domain=energy&limit=25'),
      fetch(`/api/v1/telemetry?domain=energy&from=${encodeURIComponent(winRel)}&limit=600`),
      fetch('/api/v1/energy/baseline')
    ]);

    const [rooms, bill, waste, alerts, telem, base] = await Promise.all([
      roomsRes.ok ? roomsRes.json() : [],
      billRes.ok ? billRes.json() : null,
      wasteRes.ok ? wasteRes.json() : null,
      alertsRes.ok ? alertsRes.json() : [],
      telemRes.ok ? telemRes.json() : { data: [] },
      baseRes.ok ? baseRes.json() : { items: [] }
    ]);

    if (!enState.previewMode) {
      if (roomsRes.ok) {
        updateConsolidatedStatusPill('live');
        errStrip?.classList.add('hidden');
      } else {
        updateConsolidatedStatusPill('error', `API Error (${roomsRes.status})`);
        if (errText) errText.textContent = `Endpoint /api/v1/energy/rooms mengembalikan HTTP ${roomsRes.status}. Pastikan layanan API berjalan.`;
        errStrip?.classList.remove('hidden');
      }
    }

    applyEnergyDashboardData({
      rooms,
      bill,
      waste,
      alerts,
      telemetry: telem.data || [],
      baseline: base.items || []
    });
  } catch (e) {
    console.error('Energy fetch error:', e);
    if (!enState.previewMode) {
      updateConsolidatedStatusPill('error', 'API Terputus');
      if (errText) errText.textContent = `Koneksi ke FastAPI Smart Energy gagal (${e.message || 'network error'}).`;
      errStrip?.classList.remove('hidden');
    }
  } finally {
    loadingEl?.classList.add('hidden');
  }
}

function toggleEnergyPreviewMode() {
  enState.previewMode = !enState.previewMode;
  enState.hasUserSelectedRoom = false;
  const btn = document.getElementById('en-mode-toggle');
  if (btn) {
    if (enState.previewMode) {
      btn.textContent = 'Kembali ke Live';
      btn.className = 'en-tap px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/45 text-xs font-medium text-amber-200 transition whitespace-nowrap';
    } else {
      btn.textContent = 'Mode Simulasi';
      btn.className = 'en-bms-btn en-tap px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap';
    }
  }
  fetchEnergyRooms();
}

async function ackEnergyAlert(alertId) {
  if (enState.previewMode) {
    enState.previewAckedIds[alertId] = new Date().toISOString();
    fetchEnergyRooms();
    return;
  }
  try {
    const res = await fetch(`/api/v1/alerts/${encodeURIComponent(alertId)}/ack`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ acked_by: 'Tim 1 Energy Operator' })
    });
    if (res.ok) {
      fetchEnergyRooms();
      if (typeof window.fetchAlerts === 'function') window.fetchAlerts();
      if (typeof window.fetchSummary === 'function') window.fetchSummary();
    }
  } catch (e) {
    console.error('Energy ACK error:', e);
  }
}

async function exportEnergyCsv(explicitRoom) {
  const roomFilter = document.getElementById('en-room-filter')?.value || 'all';
  const targetRuang = explicitRoom || (roomFilter === 'all' ? (enState.selectedRoom || 'r3012') : roomFilter);
  const winSel = document.getElementById('en-window-select');
  const mins = Number(winSel?.options[winSel.selectedIndex]?.dataset?.mins || 60);

  if (enState.previewMode) {
    const snap = buildEnergyPreviewSnapshot('daily', mins, enState.previewAckedIds);
    const rows = snap.telemetry.filter(r => r.ruang === targetRuang);
    const csvLines = ['ts_wib,ruang,device_id,power_w', ...rows.map(r => `${r.time},${r.ruang},${r.device_id},${r.value}`)];
    const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `energy_${targetRuang}_preview.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return;
  }

  const fromIso = new Date(Date.now() - mins * 60 * 1000).toISOString();
  try {
    const res = await fetch(`/api/v1/energy/rooms/${encodeURIComponent(targetRuang)}/usage/export?from=${encodeURIComponent(fromIso)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `energy_${targetRuang}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('Gagal mengekspor CSV Energy: ' + e.message);
  }
}

function sortEnergyTable(key) {
  if (enState.sortKey === key) {
    enState.sortAsc = !enState.sortAsc;
  } else {
    enState.sortKey = key;
    enState.sortAsc = true;
  }
  ['device_id', 'status', 'power_w', 'energy_kwh'].forEach(k => {
    const ind = document.getElementById(`en-sort-${k}`);
    if (ind) ind.textContent = k === enState.sortKey ? (enState.sortAsc ? '↑' : '↓') : '↕';
  });
  analytics.renderMetersTable({
    rooms: enState.rooms,
    roomFilter: document.getElementById('en-room-filter')?.value || 'all',
    sortKey: enState.sortKey,
    sortAsc: enState.sortAsc,
    onSelectRoom: (ruang) => selectRoom(ruang)
  });
}

function switchExtraTab(tabKey) {
  enState.activeExtraTab = tabKey;
  const basePane = document.getElementById('en-extra-pane-baseline');
  const tablePane = document.getElementById('en-extra-pane-table');
  basePane?.classList.toggle('hidden', tabKey !== 'baseline');
  tablePane?.classList.toggle('hidden', tabKey !== 'table');

  document.querySelectorAll('.en-extra-tab-btn').forEach(btn => {
    const active = btn.dataset.enExtab === tabKey;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', String(active));
  });

  if (tabKey === 'baseline') {
    setTimeout(() => analytics.resizeAll(), 40);
  }
}

function toggleEnergyInfoPopover(ev) {
  if (ev) ev.stopPropagation();
  const pop = document.getElementById('en-info-popover');
  const trigger = document.getElementById('en-info-btn-title');
  if (!pop) return;
  const isNowHidden = pop.classList.toggle('hidden');
  if (trigger) trigger.setAttribute('aria-expanded', String(!isNowHidden));
}

function closeEnergyInfoPopover() {
  const pop = document.getElementById('en-info-popover');
  const trigger = document.getElementById('en-info-btn-title');
  if (pop) pop.classList.add('hidden');
  if (trigger) trigger.setAttribute('aria-expanded', 'false');
}

function bindEvents() {
  document.getElementById('en-window-select')?.addEventListener('change', () => fetchEnergyRooms());
  document.getElementById('en-bill-period')?.addEventListener('change', () => fetchEnergyRooms());
  document.getElementById('en-room-filter')?.addEventListener('change', () => fetchEnergyRooms());
  document.getElementById('en-mode-toggle')?.addEventListener('click', () => toggleEnergyPreviewMode());
  document.getElementById('en-export-csv')?.addEventListener('click', () => exportEnergyCsv());
  document.getElementById('en-info-btn-title')?.addEventListener('click', (ev) => toggleEnergyInfoPopover(ev));
  document.getElementById('en-info-btn-bill')?.addEventListener('click', (ev) => toggleEnergyInfoPopover(ev));
  document.getElementById('en-info-close-btn')?.addEventListener('click', () => closeEnergyInfoPopover());
  document.getElementById('en-error-retry')?.addEventListener('click', () => fetchEnergyRooms());
  document.getElementById('en-error-sim')?.addEventListener('click', () => {
    if (!enState.previewMode) toggleEnergyPreviewMode();
  });

  document.getElementById('en-alert-filter')?.addEventListener('change', () => {
    renderAnomalyFeed({
      allAlerts: enState.alerts,
      allRooms: enState.rooms,
      selectedRoom: enState.selectedRoom,
      onAckAlert: (id) => ackEnergyAlert(id)
    });
  });
  document.getElementById('en-alert-scope')?.addEventListener('change', () => {
    renderAnomalyFeed({
      allAlerts: enState.alerts,
      allRooms: enState.rooms,
      selectedRoom: enState.selectedRoom,
      onAckAlert: (id) => ackEnergyAlert(id)
    });
  });

  document.getElementById('en-table-search')?.addEventListener('input', () => {
    analytics.renderMetersTable({
      rooms: enState.rooms,
      roomFilter: document.getElementById('en-room-filter')?.value || 'all',
      sortKey: enState.sortKey,
      sortAsc: enState.sortAsc,
      onSelectRoom: (ruang) => selectRoom(ruang)
    });
  });

  document.querySelectorAll('.en-sort-btn').forEach(btn => {
    btn.addEventListener('click', () => sortEnergyTable(btn.dataset.sortKey));
  });

  document.querySelectorAll('.en-extra-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchExtraTab(btn.dataset.enExtab));
  });

  document.querySelectorAll('.en-empty-preview-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (!enState.previewMode) toggleEnergyPreviewMode();
    });
  });

  document.addEventListener('click', (e) => {
    const pop = document.getElementById('en-info-popover');
    if (!pop || pop.classList.contains('hidden')) return;
    if (pop.contains(e.target)) return;
    if (e.target.closest('#en-info-btn-title') || e.target.closest('#en-info-btn-bill')) return;
    closeEnergyInfoPopover();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const pop = document.getElementById('en-info-popover');
    if (pop && !pop.classList.contains('hidden')) {
      closeEnergyInfoPopover();
    }
  });
}

// Mount SVG blueprint immediately and expose clean global hooks for index.html tab switcher
floorPlan.mount();
bindEvents();

window.fetchEnergyRooms = fetchEnergyRooms;
window.closeEnergyInfoPopover = closeEnergyInfoPopover;
window.energyApp = {
  fetchEnergyRooms,
  selectRoom,
  toggleEnergyPreviewMode,
  exportEnergyCsv,
  onTabActivated: () => {
    fetchEnergyRooms();
    setTimeout(() => analytics.resizeAll(), 80);
  }
};

// If the user is already on Smart Energy tab on load, fetch immediately
const energyTabEl = document.getElementById('content-energy');
if (energyTabEl && !energyTabEl.classList.contains('hidden')) {
  window.energyApp.onTabActivated();
}
