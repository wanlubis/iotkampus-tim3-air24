// Right Column (~40%) Room Detail Inspector & Anomaly Alert Panel Component

import {
  FLOORPLAN_ROOMS,
  STATUS_META,
  escapeEnHtml,
  formatEnIdr,
  formatEnTimeWib,
  resolveEnergyAlertRoom
} from './constants.js';

export function renderRoomDetailPanel({
  roomsMap,
  selectedRoom,
  allAlerts,
  allRooms,
  roomFilter,
  onSelectRoom,
  onAckAlert,
  onFilterToRoom,
  onExportRoomCsv
}) {
  const room = roomsMap.get(selectedRoom) || roomsMap.values().next().value;
  if (!room) return;

  const meta = STATUS_META[room.visualStatus] || STATUS_META.offline;

  // Quick room selector pills in right panel
  const switcherEl = document.getElementById('en-detail-room-pills');
  if (switcherEl) {
    switcherEl.innerHTML = FLOORPLAN_ROOMS.map(cfg => {
      const rItem = roomsMap.get(cfg.ruang);
      const st = STATUS_META[rItem?.visualStatus || 'offline'] || STATUS_META.offline;
      const isSel = cfg.ruang === room.ruang;
      return `
        <button
          type="button"
          data-detail-room="${cfg.ruang}"
          aria-pressed="${isSel}"
          class="en-num text-[11px] font-medium px-2 py-1 rounded-md border transition flex items-center gap-1.5 ${
            isSel
              ? 'bg-sky-500/15 border-sky-400/50 text-sky-100'
              : 'bg-slate-900/50 border-slate-700/60 text-slate-400 hover:text-slate-200 hover:border-slate-600'
          }"
        >
          <span class="w-1.5 h-1.5 rounded-full ${st.dotClass}" aria-hidden="true"></span>
          <span>${cfg.codeLabel}</span>
        </button>
      `;
    }).join('');

    switcherEl.querySelectorAll('button[data-detail-room]').forEach(btn => {
      btn.addEventListener('click', () => onSelectRoom(btn.dataset.detailRoom));
    });
  }

  // Room header metadata
  const titleEl = document.getElementById('en-detail-title');
  const badgeEl = document.getElementById('en-detail-badge');
  const subEl = document.getElementById('en-detail-sub');
  const seenEl = document.getElementById('en-detail-lastseen');

  if (titleEl) titleEl.textContent = `${room.codeLabel}: ${room.label}`;
  if (badgeEl) {
    badgeEl.textContent = meta.label;
    badgeEl.className = `text-[10px] font-semibold px-2 py-0.5 rounded border whitespace-nowrap ${meta.badgeClass}`;
  }
  if (subEl) subEl.textContent = `${room.device_id} · ${room.subtitle}`;
  if (seenEl) seenEl.textContent = `Terakhir: ${formatEnTimeWib(room.last_seen)}`;

  // Metrics 2x2
  const loadPct = Math.min(100, Math.round((Number(room.power_w || 0) / 3000) * 100));
  const powerEl = document.getElementById('en-detail-power');
  const energyEl = document.getElementById('en-detail-energy');
  const billEl = document.getElementById('en-detail-bill');
  const loadEl = document.getElementById('en-detail-load');
  const loadBarEl = document.getElementById('en-detail-load-bar');

  if (powerEl) powerEl.textContent = room.online ? `${room.power_w.toFixed(1)} W` : '0.0 W (Offline)';
  if (energyEl) energyEl.textContent = `${room.energy_kwh.toFixed(3)} kWh`;
  if (billEl) billEl.textContent = formatEnIdr(room.bill_idr);
  if (loadEl) loadEl.textContent = `${loadPct}%`;
  if (loadBarEl) {
    loadBarEl.style.width = `${loadPct}%`;
    loadBarEl.className = `h-full rounded transition-all duration-300 ${
      loadPct > 85 ? 'bg-rose-500' : (loadPct > 45 ? 'bg-amber-400' : 'bg-sky-400')
    }`;
  }

  // Baseline bars
  const workEl = document.getElementById('en-detail-work');
  const afterEl = document.getElementById('en-detail-after');
  const workBar = document.getElementById('en-detail-work-bar');
  const afterBar = document.getElementById('en-detail-after-bar');
  if (workEl) workEl.textContent = room.avg_work_w !== null ? `${Number(room.avg_work_w).toFixed(1)} W` : '-';
  if (afterEl) afterEl.textContent = room.avg_after_w !== null ? `${Number(room.avg_after_w).toFixed(1)} W` : '-';
  if (workBar) workBar.style.width = `${Math.min(100, (Number(room.avg_work_w || 0) / 3000) * 100)}%`;
  if (afterBar) afterBar.style.width = `${Math.min(100, (Number(room.avg_after_w || 0) / 3000) * 100)}%`;

  // Room action buttons
  const syncBtn = document.getElementById('en-detail-btn-filter');
  if (syncBtn) {
    const isScopedHere = roomFilter === room.ruang;
    syncBtn.textContent = isScopedHere ? 'Tampilkan Semua Ruang' : `Fokus Grafik: ${room.codeLabel}`;
    syncBtn.onclick = () => onFilterToRoom(isScopedHere ? 'all' : room.ruang);
  }
  const csvBtn = document.getElementById('en-detail-btn-csv');
  if (csvBtn) {
    csvBtn.textContent = `Ekspor CSV ${room.codeLabel}`;
    csvBtn.onclick = () => onExportRoomCsv(room.ruang);
  }

  // Anomaly & Alert Feed (Bottom section of Right Column)
  renderAnomalyFeed({
    allAlerts,
    allRooms,
    selectedRoom: room.ruang,
    onAckAlert
  });
}

export function renderAnomalyFeed({ allAlerts, allRooms, selectedRoom, onAckAlert }) {
  const feed = document.getElementById('en-alerts-feed');
  const countEl = document.getElementById('en-alerts-count');
  if (!feed) return;

  const filter = document.getElementById('en-alert-filter')?.value || 'all';
  const scope = document.getElementById('en-alert-scope')?.value || 'all';

  const filtered = (allAlerts || []).filter(a => {
    if (filter === 'unacked' && a.ts_acked) return false;
    if ((filter === 'WASTE_AFTER_HOURS' || filter === 'HIGH_LOAD' || filter === 'OFFLINE') && a.code !== filter) return false;
    if (scope === 'room') {
      const alertRoom = resolveEnergyAlertRoom(a, allRooms);
      if (alertRoom && alertRoom !== selectedRoom) return false;
    }
    return true;
  });

  if (countEl) countEl.textContent = `${filtered.length} kejadian`;

  if (!filtered.length) {
    feed.innerHTML = `<div class="text-center py-6 text-xs text-slate-400">Tidak ada alert anomali yang cocok dengan filter saat ini.</div>`;
    return;
  }

  feed.innerHTML = filtered.map(a => {
    const isAcked = Boolean(a.ts_acked);
    const alertRoom = resolveEnergyAlertRoom(a, allRooms);
    const isCurrentRoom = alertRoom === selectedRoom;
    const isCrit = a.severity === 'critical';
    const cardTone = isAcked
      ? 'border-slate-700/50 bg-slate-900/45 text-slate-300 opacity-75'
      : (isCrit
          ? 'border-rose-500/35 bg-rose-500/10 text-rose-200'
          : 'border-amber-500/35 bg-amber-500/10 text-amber-200');
    return `
      <div class="border rounded-lg p-3 text-xs transition ${cardTone} ${isCurrentRoom ? 'ring-1 ring-sky-400/35' : ''}">
        <div class="flex items-center justify-between gap-2">
          <span class="en-num text-[11px] font-semibold">[${escapeEnHtml(a.code || a.type)}] ${escapeEnHtml(a.device_id)}</span>
          <span class="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-slate-950/60">${escapeEnHtml(a.severity || 'info')}</span>
        </div>
        <p class="mt-1 text-slate-200 text-[11px] leading-relaxed">${escapeEnHtml(a.message || a.code)}</p>
        <div class="mt-2 pt-2 border-t border-slate-700/40 flex items-center justify-between gap-2 text-[10px] text-slate-400">
          <span class="en-num">${escapeEnHtml(formatEnTimeWib(a.ts_raised))}</span>
          ${isAcked
            ? `<span class="text-emerald-400 font-semibold">ACK oleh ${escapeEnHtml(a.acked_by || 'operator')}</span>`
            : `<button type="button" data-ack-id="${escapeEnHtml(a.id)}" class="en-ack-btn px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-100 font-semibold border border-slate-600/80 transition">Tandai ACK</button>`
          }
        </div>
      </div>
    `;
  }).join('');

  feed.querySelectorAll('.en-ack-btn').forEach(btn => {
    btn.addEventListener('click', () => onAckAlert(btn.dataset.ackId));
  });
}
