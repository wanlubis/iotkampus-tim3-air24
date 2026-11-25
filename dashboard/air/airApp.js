// Smart Environment / Air Quality (Tim 3) Dashboard Module
// Mengelola KPI, Peta Zona SVG 2D, Kartu Ruang, Grafik 3 Metrik (Chart.js), dan Feed Alert Domain Air

let selectedAirDevice = 'all';
let selectedAirRange = '-30m';
let co2Chart = null;
let pm25Chart = null;
let noiseChart = null;

function getAirSeverity(co2, pm25, noise, status) {
  if (status === 'offline') return 'offline';
  if (co2 > 1500 || pm25 > 75) return 'critical';
  if (co2 > 1000 || pm25 > 35 || noise > 70) return 'warning';
  return 'normal';
}

function getSeverityStyle(sev) {
  switch (sev) {
    case 'critical':
      return {
        label: 'KRITIS',
        badge: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
        border: 'border-rose-500/60',
        fill: 'rgba(244, 63, 94, 0.22)',
        stroke: '#f43f5e',
        dot: 'bg-rose-400'
      };
    case 'warning':
      return {
        label: 'WASPADA',
        badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
        border: 'border-amber-500/60',
        fill: 'rgba(245, 158, 11, 0.22)',
        stroke: '#f59e0b',
        dot: 'bg-amber-400'
      };
    case 'offline':
      return {
        label: 'OFFLINE',
        badge: 'bg-slate-700 text-slate-400 border-slate-600',
        border: 'border-slate-700',
        fill: 'rgba(51, 65, 85, 0.4)',
        stroke: '#64748b',
        dot: 'bg-slate-500'
      };
    default:
      return {
        label: 'SEHAT',
        badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
        border: 'border-slate-700/80',
        fill: 'rgba(16, 185, 129, 0.16)',
        stroke: '#10b981',
        dot: 'bg-emerald-400'
      };
  }
}

export function selectAirRoom(deviceId) {
  selectedAirDevice = (selectedAirDevice === deviceId) ? 'all' : deviceId;
  const selectEl = document.getElementById('air-chart-device-filter');
  if (selectEl) selectEl.value = selectedAirDevice;
  fetchAirDashboard();
}

export function setAirTimeRange(rangeStr) {
  selectedAirRange = rangeStr;
  document.querySelectorAll('.air-range-btn').forEach(btn => {
    const active = btn.dataset.range === rangeStr;
    btn.className = active
      ? 'air-range-btn px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-600 text-white transition'
      : 'air-range-btn px-2.5 py-1 rounded-md text-[11px] font-medium bg-slate-800 text-slate-400 hover:text-white transition';
  });
  fetchAirCharts();
}

export function copyDemoCmd(cmdText, btnEl) {
  navigator.clipboard.writeText(cmdText).then(() => {
    const orig = btnEl.textContent;
    btnEl.textContent = 'Tersalin!';
    btnEl.classList.add('text-emerald-400');
    setTimeout(() => {
      btnEl.textContent = orig;
      btnEl.classList.remove('text-emerald-400');
    }, 1500);
  });
}

async function fetchAirRoomsAndKpi() {
  const errBanner = document.getElementById('air-error-banner');
  try {
    const res = await fetch('/api/v1/air/rooms');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rooms = data.rooms || [];

    if (errBanner) errBanner.classList.add('hidden');

    if (rooms.length === 0) {
      document.getElementById('air-rooms-container').innerHTML = `
        <div class="col-span-3 text-center py-8 text-xs text-slate-400 bg-slate-800/50 rounded-2xl border border-slate-700">
          Belum ada data ruang Smart Environment yang terdaftar.
        </div>`;
      return;
    }

    // Hitung 4 KPI Domain Air (Bagian 7.4)
    let totalCo2 = 0;
    let maxPm25 = 0;
    let maxNoise = 0;
    let onlineCount = 0;

    rooms.forEach(r => {
      totalCo2 += Number(r.co2_ppm || 0);
      if (Number(r.pm25_ugm3 || 0) > maxPm25) maxPm25 = Number(r.pm25_ugm3 || 0);
      if (Number(r.noise_db || 0) > maxNoise) maxNoise = Number(r.noise_db || 0);
      if (r.status === 'online') onlineCount++;
    });

    const avgCo2 = Math.round(totalCo2 / rooms.length);

    document.getElementById('air-kpi-co2-avg').textContent = avgCo2;
    document.getElementById('air-kpi-co2-avg').className =
      `text-2xl font-extrabold mt-1 ${avgCo2 > 1500 ? 'text-rose-400' : (avgCo2 > 1000 ? 'text-amber-400' : 'text-emerald-400')}`;

    document.getElementById('air-kpi-pm25-max').textContent = maxPm25.toFixed(1);
    document.getElementById('air-kpi-pm25-max').className =
      `text-2xl font-extrabold mt-1 ${maxPm25 > 75 ? 'text-rose-400' : (maxPm25 > 35 ? 'text-amber-400' : 'text-emerald-400')}`;

    document.getElementById('air-kpi-noise-max').textContent = maxNoise.toFixed(1);
    document.getElementById('air-kpi-noise-max').className =
      `text-2xl font-extrabold mt-1 ${maxNoise > 70 ? 'text-amber-400' : 'text-emerald-400'}`;

    document.getElementById('air-kpi-online').textContent = `${onlineCount}/${rooms.length}`;

    // Sinkronkan juga KPI PM2.5 di Tab Overview jika elemen ada
    const topPmEl = document.getElementById('kpi-air-pm25-val');
    if (topPmEl) topPmEl.textContent = maxPm25 > 0 ? maxPm25.toFixed(1) : '--';

    // Update SVG Floorplan Zones
    updateAirFloorplan(rooms);

    // Render 3 Kartu Ruang
    const container = document.getElementById('air-rooms-container');
    container.innerHTML = rooms.map(r => {
      const co2 = Number(r.co2_ppm || 0);
      const pm = Number(r.pm25_ugm3 || 0);
      const noise = Number(r.noise_db || 0);
      const sev = getAirSeverity(co2, pm, noise, r.status);
      const st = getSeverityStyle(sev);
      const isSelected = selectedAirDevice === r.device_id;

      const co2Color = co2 > 1500 ? 'text-rose-400' : (co2 > 1000 ? 'text-amber-400' : 'text-emerald-400');
      const pmColor = pm > 75 ? 'text-rose-400' : (pm > 35 ? 'text-amber-400' : 'text-emerald-400');
      const noiseColor = noise > 70 ? 'text-amber-400' : 'text-emerald-400';

      const co2Pct = Math.min(100, Math.round((co2 / 2000) * 100));
      const pmPct = Math.min(100, Math.round((pm / 100) * 100));
      const noisePct = Math.min(100, Math.round((noise / 100) * 100));

      return `
        <div onclick="window.airApp.selectRoom('${r.device_id}')"
             class="cursor-pointer bg-slate-800/90 border ${isSelected ? 'border-emerald-400 ring-2 ring-emerald-500/30' : st.border} rounded-2xl p-5 shadow-sm space-y-4 hover:border-emerald-500/60 transition">
          <div class="flex items-start justify-between gap-2">
            <div>
              <div class="flex items-center space-x-2">
                <h3 class="font-bold text-white text-base">${r.display_name}</h3>
              </div>
              <p class="text-xs text-slate-400 font-mono mt-0.5">${r.device_id} · ${r.gedung} / ${r.ruang}</p>
            </div>
            <div class="flex flex-col items-end space-y-1">
              <span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${st.badge}">
                <span class="w-1.5 h-1.5 rounded-full ${st.dot}"></span>
                <span>${st.label}</span>
              </span>
              <span class="text-[10px] ${r.status === 'online' ? 'text-emerald-400' : 'text-slate-500'} font-mono">
                ${r.status.toUpperCase()}
              </span>
            </div>
          </div>

          <!-- Metrics Grid with Progress Bars -->
          <div class="grid grid-cols-3 gap-2.5 text-center">
            <div class="bg-slate-900/60 p-2.5 rounded-xl border border-slate-700/60">
              <div class="text-[10px] text-slate-400 font-medium">CO₂</div>
              <div class="text-lg font-extrabold ${co2Color} mt-0.5">${co2}</div>
              <div class="text-[9px] text-slate-500">ppm</div>
              <div class="w-full h-1 bg-slate-700 rounded-full mt-2 overflow-hidden">
                <div class="h-full ${co2 > 1500 ? 'bg-rose-500' : (co2 > 1000 ? 'bg-amber-500' : 'bg-emerald-500')}" style="width: ${co2Pct}%"></div>
              </div>
            </div>

            <div class="bg-slate-900/60 p-2.5 rounded-xl border border-slate-700/60">
              <div class="text-[10px] text-slate-400 font-medium">PM2.5</div>
              <div class="text-lg font-extrabold ${pmColor} mt-0.5">${pm.toFixed(1)}</div>
              <div class="text-[9px] text-slate-500">µg/m³</div>
              <div class="w-full h-1 bg-slate-700 rounded-full mt-2 overflow-hidden">
                <div class="h-full ${pm > 75 ? 'bg-rose-500' : (pm > 35 ? 'bg-amber-500' : 'bg-emerald-500')}" style="width: ${pmPct}%"></div>
              </div>
            </div>

            <div class="bg-slate-900/60 p-2.5 rounded-xl border border-slate-700/60">
              <div class="text-[10px] text-slate-400 font-medium">Noise</div>
              <div class="text-lg font-extrabold ${noiseColor} mt-0.5">${noise.toFixed(1)}</div>
              <div class="text-[9px] text-slate-500">dB</div>
              <div class="w-full h-1 bg-slate-700 rounded-full mt-2 overflow-hidden">
                <div class="h-full ${noise > 70 ? 'bg-amber-500' : 'bg-emerald-500'}" style="width: ${noisePct}%"></div>
              </div>
            </div>
          </div>

          <div class="pt-2 border-t border-slate-700/40 flex items-center justify-between text-[10px] text-slate-400">
            <span>Update: ${r.last_updated ? new Date(r.last_updated).toLocaleTimeString('id-ID') : '--'}</span>
            <span class="text-emerald-400/80">${isSelected ? '✓ Terpilih di Grafik' : 'Klik untuk filter grafik'}</span>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.error("Air rooms error:", err);
    if (errBanner) {
      errBanner.classList.remove('hidden');
      document.getElementById('air-error-msg').textContent = `Gagal memuat data Smart Environment: ${err.message}`;
    }
  }
}

function updateAirFloorplan(rooms) {
  rooms.forEach(r => {
    const zoneEl = document.getElementById(`air-zone-${r.device_id}`);
    const valEl = document.getElementById(`air-zone-val-${r.device_id}`);
    const statusEl = document.getElementById(`air-zone-status-${r.device_id}`);
    if (!zoneEl) return;

    const sev = getAirSeverity(r.co2_ppm, r.pm25_ugm3, r.noise_db, r.status);
    const st = getSeverityStyle(sev);
    const isSelected = selectedAirDevice === r.device_id;

    zoneEl.setAttribute('fill', st.fill);
    zoneEl.setAttribute('stroke', isSelected ? '#38bdf8' : st.stroke);
    zoneEl.setAttribute('stroke-width', isSelected ? '3' : '2');

    if (valEl) valEl.textContent = r.status === 'online' ? `${r.co2_ppm} ppm · ${r.pm25_ugm3.toFixed(1)} µg` : 'OFFLINE';
    if (statusEl) statusEl.textContent = st.label;
  });
}

async function fetchAirAlerts() {
  const container = document.getElementById('air-alerts-container');
  const countBadge = document.getElementById('air-kpi-alerts-count');
  if (!container) return;

  try {
    const res = await fetch('/api/v1/alerts?domain=air&limit=15');
    if (!res.ok) return;
    const alerts = await res.json();

    const activeUnacked = alerts.filter(a => !a.ts_acked).length;
    if (countBadge) countBadge.textContent = activeUnacked;

    if (!alerts || alerts.length === 0) {
      container.innerHTML = `
        <div class="text-center py-8 text-xs text-slate-400">
          Tidak ada alert kualitas udara saat ini. Semua ruang dalam batas aman.
        </div>`;
      return;
    }

    container.innerHTML = alerts.map(a => {
      const isAcked = !!a.ts_acked;
      const sevClass = a.severity === 'critical'
        ? 'border-rose-500/50 bg-rose-500/10 text-rose-300'
        : 'border-amber-500/50 bg-amber-500/10 text-amber-300';

      return `
        <div class="border rounded-xl p-3 text-xs ${sevClass}">
          <div class="flex items-center justify-between font-semibold">
            <span class="font-mono text-[11px]">[${a.code}] ${a.device_id}</span>
            <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-slate-900/50">${a.severity}</span>
          </div>
          <p class="mt-1 text-slate-200 text-[11px] leading-relaxed">${a.message}</p>
          <div class="mt-2 pt-2 border-t border-slate-700/40 flex items-center justify-between text-[10px] text-slate-400">
            <span>${a.ts_raised ? new Date(a.ts_raised).toLocaleTimeString('id-ID') : '--'}</span>
            ${isAcked ? `
              <span class="text-emerald-400 font-semibold">✓ Di-ACK (${a.acked_by || 'operator'})</span>
            ` : `
              <button onclick="window.airApp.ackAirAlert('${a.id}')"
                      class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium border border-slate-600 transition">
                Tandai ACK
              </button>
            `}
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error("Air alerts error:", err);
  }
}

export async function ackAirAlert(alertId) {
  try {
    const res = await fetch(`/api/v1/alerts/${alertId}/ack`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ acked_by: 'Tim 3 Operator' })
    });
    if (res.ok) {
      await fetchAirAlerts();
      if (typeof window.fetchAlerts === 'function') window.fetchAlerts();
      if (typeof window.fetchSummary === 'function') window.fetchSummary();
    }
  } catch (err) {
    console.error("ACK error:", err);
  }
}

async function fetchAirCharts() {
  if (typeof Chart === 'undefined') return;

  try {
    let url = `/api/v1/telemetry?domain=air&from=${encodeURIComponent(selectedAirRange)}&limit=400`;
    if (selectedAirDevice !== 'all') {
      url += `&device_id=${encodeURIComponent(selectedAirDevice)}`;
    }
    const res = await fetch(url);
    if (!res.ok) return;
    const json = await res.json();
    const rows = json.data || [];

    // Kelompokkan data per field dan device_id
    const devices = ['aq-01', 'aq-02', 'aq-03'];
    const colors = {
      'aq-01': '#10b981', // emerald
      'aq-02': '#38bdf8', // sky
      'aq-03': '#a78bfa'  // violet
    };

    const grouped = { co2_ppm: {}, pm25_ugm3: {}, noise_db: {} };
    devices.forEach(d => {
      grouped.co2_ppm[d] = [];
      grouped.pm25_ugm3[d] = [];
      grouped.noise_db[d] = [];
    });

    rows.forEach(r => {
      if (grouped[r.field] && grouped[r.field][r.device_id]) {
        grouped[r.field][r.device_id].push({
          t: new Date(r.time).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          ts: new Date(r.time).getTime(),
          y: Number(r.value)
        });
      }
    });

    const buildDatasets = (fieldKey, warnThreshold) => {
      const targetDevs = selectedAirDevice === 'all' ? devices : [selectedAirDevice];
      const datasets = targetDevs.map(dev => {
        const pts = grouped[fieldKey][dev].sort((a, b) => a.ts - b.ts).slice(-25);
        return {
          label: dev,
          data: pts.map(p => p.y),
          borderColor: colors[dev],
          backgroundColor: colors[dev] + '22',
          borderWidth: 2,
          pointRadius: 2,
          tension: 0.3
        };
      });

      // Ambil label waktu dari dataset terpanjang
      let labels = [];
      targetDevs.forEach(dev => {
        const pts = grouped[fieldKey][dev].sort((a, b) => a.ts - b.ts).slice(-25);
        if (pts.length > labels.length) labels = pts.map(p => p.t);
      });

      if (labels.length > 0 && warnThreshold) {
        datasets.push({
          label: `Ambang (${warnThreshold})`,
          data: labels.map(() => warnThreshold),
          borderColor: '#f59e0b',
          borderDash: [5, 5],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false
        });
      }
      return { labels, datasets };
    };

    const chartOpts = (yLabel) => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: {
          labels: { color: '#94a3b8', font: { size: 10 }, boxWidth: 10 }
        }
      },
      scales: {
        x: {
          ticks: { color: '#64748b', maxTicksLimit: 6, font: { size: 9 } },
          grid: { color: 'rgba(51, 65, 85, 0.3)' }
        },
        y: {
          ticks: { color: '#94a3b8', font: { size: 10 } },
          grid: { color: 'rgba(51, 65, 85, 0.4)' },
          title: { display: true, text: yLabel, color: '#64748b', font: { size: 10 } }
        }
      }
    });

    const co2Data = buildDatasets('co2_ppm', 1000);
    const pmData = buildDatasets('pm25_ugm3', 35);
    const noiseData = buildDatasets('noise_db', 70);

    const ctxCo2 = document.getElementById('air-chart-co2');
    if (ctxCo2) {
      if (co2Chart) {
        co2Chart.data = co2Data;
        co2Chart.update('none');
      } else {
        co2Chart = new Chart(ctxCo2, { type: 'line', data: co2Data, options: chartOpts('ppm') });
      }
    }

    const ctxPm = document.getElementById('air-chart-pm25');
    if (ctxPm) {
      if (pm25Chart) {
        pm25Chart.data = pmData;
        pm25Chart.update('none');
      } else {
        pm25Chart = new Chart(ctxPm, { type: 'line', data: pmData, options: chartOpts('µg/m³') });
      }
    }

    const ctxNoise = document.getElementById('air-chart-noise');
    if (ctxNoise) {
      if (noiseChart) {
        noiseChart.data = noiseData;
        noiseChart.update('none');
      } else {
        noiseChart = new Chart(ctxNoise, { type: 'line', data: noiseData, options: chartOpts('dB') });
      }
    }
  } catch (err) {
    console.error("Air charts error:", err);
  }
}

export async function fetchAirDashboard() {
  await Promise.all([
    fetchAirRoomsAndKpi(),
    fetchAirAlerts(),
    fetchAirCharts()
  ]);
}

// Expose ke global window agar bisa dipanggil dari inline HTML & auto-refresh
window.airApp = {
  fetchAirDashboard,
  selectRoom: selectAirRoom,
  setTimeRange: setAirTimeRange,
  ackAirAlert,
  copyDemoCmd,
  onDeviceFilterChange: (val) => {
    selectedAirDevice = val;
    fetchAirDashboard();
  }
};
