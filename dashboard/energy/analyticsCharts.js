// Permanent 2D Analytics Charts & Supplemental Baseline / Meters Table Component

import { ENERGY_ROOM_COLORS, escapeEnHtml, formatEnIdr, formatEnTimeWib } from './constants.js';

export class EnergyAnalyticsComponent {
  constructor() {
    this.charts = {
      power: null,
      donut: null,
      baseline: null
    };
  }

  renderPowerChart(rows, roomFilter, winLabel) {
    const pillEl = document.getElementById('en-trend-window-pill');
    if (pillEl) {
      pillEl.textContent = `${winLabel}${roomFilter === 'all' ? '' : ' · ' + roomFilter}`;
    }

    const canvas = document.getElementById('en-chart-power');
    const emptyBox = document.getElementById('en-chart-power-empty');
    if (!canvas || typeof Chart === 'undefined') return;

    const byRoom = {};
    const timeMap = new Map();
    for (const row of (rows || [])) {
      if (row.field !== 'power_w') continue;
      const ruang = row.ruang || row.device_id || 'unknown';
      if (roomFilter !== 'all' && ruang !== roomFilter) continue;
      const ms = new Date(row.time).getTime();
      if (Number.isNaN(ms)) continue;
      const label = formatEnTimeWib(row.time).replace(' WIB', '');
      if (!timeMap.has(label) || ms < timeMap.get(label)) {
        timeMap.set(label, ms);
      }
      if (!byRoom[ruang]) byRoom[ruang] = {};
      byRoom[ruang][label] = Number(row.value || 0);
    }

    const labels = Array.from(timeMap.entries())
      .sort((a, b) => a[1] - b[1])
      .map(([label]) => label);
    const roomNames = Object.keys(byRoom).sort();

    if (labels.length === 0 || roomNames.length === 0) {
      emptyBox?.classList.remove('hidden');
      if (this.charts.power) {
        this.charts.power.destroy();
        this.charts.power = null;
      }
      return;
    }
    emptyBox?.classList.add('hidden');

    const ctx = canvas.getContext('2d');
    const fallbackColors = ['#fb7185', '#2dd4bf', '#a3e635', '#facc15'];
    const datasets = roomNames.map((ruang, idx) => {
      const color = ENERGY_ROOM_COLORS[ruang] || fallbackColors[idx % fallbackColors.length];
      const grad = ctx.createLinearGradient(0, 0, 0, 210);
      grad.addColorStop(0, color + '38');
      grad.addColorStop(1, color + '03');
      return {
        label: ruang,
        data: labels.map(l => (byRoom[ruang][l] !== undefined ? byRoom[ruang][l] : null)),
        borderColor: color,
        backgroundColor: grad,
        fill: true,
        tension: 0.32,
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5,
        spanGaps: true
      };
    });

    if (this.charts.power) {
      this.charts.power.data.labels = labels;
      this.charts.power.data.datasets = datasets;
      this.charts.power.update('none');
      return;
    }

    this.charts.power = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        animation: { duration: 220 },
        plugins: {
          legend: {
            position: 'top',
            align: 'start',
            labels: { color: '#cbd5e1', usePointStyle: true, boxWidth: 7, padding: 12, font: { size: 11 } }
          },
          tooltip: {
            backgroundColor: 'rgba(11, 18, 32, 0.96)',
            borderColor: 'rgba(148, 163, 184, 0.28)',
            borderWidth: 1,
            titleColor: '#f8fafc',
            bodyColor: '#e2e8f0',
            padding: 10,
            callbacks: {
              label: (ctxItem) => ` ${ctxItem.dataset.label}: ${Number(ctxItem.parsed.y || 0).toFixed(1)} W`
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(51, 65, 85, 0.25)' },
            ticks: { color: '#94a3b8', maxTicksLimit: 6, font: { size: 10 } }
          },
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(51, 65, 85, 0.25)' },
            ticks: { color: '#94a3b8', font: { size: 10 }, callback: (v) => `${v} W` }
          }
        }
      }
    });
  }

  renderDonutChart(perRuang, roomFilter) {
    const canvas = document.getElementById('en-chart-donut');
    const emptyBox = document.getElementById('en-chart-donut-empty');
    if (!canvas || typeof Chart === 'undefined') return;

    const filtered = (perRuang || []).filter(r => roomFilter === 'all' || r.ruang === roomFilter);
    const totalVal = filtered.reduce((s, r) => s + Number(r.energy_kwh || 0), 0);
    if (totalVal <= 0) {
      emptyBox?.classList.remove('hidden');
      if (this.charts.donut) {
        this.charts.donut.destroy();
        this.charts.donut = null;
      }
      return;
    }
    emptyBox?.classList.add('hidden');

    const labels = filtered.map(r => r.ruang);
    const values = filtered.map(r => Number(r.estimasi_tagihan_idr || 0));
    const kwhs = filtered.map(r => Number(r.energy_kwh || 0));
    const colors = labels.map(r => ENERGY_ROOM_COLORS[r] || '#38bdf8');
    const meta = { labels, values, kwhs, totalVal };

    if (this.charts.donut) {
      this.charts.donut.$enMeta = meta;
      this.charts.donut.data.labels = labels;
      this.charts.donut.data.datasets[0].data = values;
      this.charts.donut.data.datasets[0].backgroundColor = colors;
      this.charts.donut.update('none');
      return;
    }

    const donutChart = new Chart(canvas.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: '#0c1526',
          borderWidth: 2,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '66%',
        animation: { duration: 220 },
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#cbd5e1', usePointStyle: true, boxWidth: 8, padding: 12, font: { size: 11 } }
          },
          tooltip: {
            backgroundColor: 'rgba(11, 18, 32, 0.96)',
            borderColor: 'rgba(148, 163, 184, 0.28)',
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctxItem) => {
                const m = ctxItem.chart.$enMeta || meta;
                const idx = ctxItem.dataIndex;
                const rp = m.values[idx] || 0;
                const kwh = m.kwhs[idx] || 0;
                const pct = m.totalVal > 0 ? ((kwh / m.totalVal) * 100).toFixed(1) : '0.0';
                return ` ${m.labels[idx]}: ${formatEnIdr(rp)} (${kwh.toFixed(2)} kWh · ${pct}%)`;
              }
            }
          }
        }
      }
    });
    donutChart.$enMeta = meta;
    this.charts.donut = donutChart;
  }

  renderBaselineChart(items, roomFilter) {
    const canvas = document.getElementById('en-chart-baseline');
    const emptyBox = document.getElementById('en-chart-baseline-empty');
    if (!canvas || typeof Chart === 'undefined') return;

    const filtered = (items || []).filter(b => roomFilter === 'all' || b.ruang === roomFilter);
    const hasData = filtered.some(b => b.avg_work_hours_w !== null || b.avg_after_hours_w !== null);
    if (!hasData) {
      emptyBox?.classList.remove('hidden');
      if (this.charts.baseline) {
        this.charts.baseline.destroy();
        this.charts.baseline = null;
      }
      return;
    }
    emptyBox?.classList.add('hidden');

    const labels = filtered.map(b => b.ruang);
    const workData = filtered.map(b => Number(b.avg_work_hours_w || 0));
    const afterData = filtered.map(b => Number(b.avg_after_hours_w || 0));

    if (this.charts.baseline) {
      this.charts.baseline.data.labels = labels;
      this.charts.baseline.data.datasets[0].data = workData;
      this.charts.baseline.data.datasets[1].data = afterData;
      this.charts.baseline.update('none');
      return;
    }

    this.charts.baseline = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Jam Kerja (07:00-18:00 WIB)',
            data: workData,
            backgroundColor: 'rgba(56, 189, 248, 0.78)',
            borderColor: '#38bdf8',
            borderWidth: 1,
            borderRadius: 4
          },
          {
            label: 'Luar Jam Kerja (Malam/Libur)',
            data: afterData,
            backgroundColor: 'rgba(245, 158, 11, 0.78)',
            borderColor: '#f59e0b',
            borderWidth: 1,
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 220 },
        plugins: {
          legend: {
            position: 'top',
            align: 'start',
            labels: { color: '#cbd5e1', usePointStyle: true, boxWidth: 8, font: { size: 11 } }
          },
          tooltip: {
            backgroundColor: 'rgba(11, 18, 32, 0.96)',
            borderColor: 'rgba(245, 158, 11, 0.35)',
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctxItem) => ` ${ctxItem.dataset.label}: ${Number(ctxItem.parsed.y || 0).toFixed(1)} W`
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#cbd5e1', font: { size: 11 } } },
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(51, 65, 85, 0.25)' },
            ticks: { color: '#94a3b8', font: { size: 10 }, callback: (v) => `${v} W` }
          }
        }
      }
    });
  }

  renderMetersTable({ rooms, roomFilter, sortKey, sortAsc, onSelectRoom }) {
    const tbody = document.getElementById('energy-container');
    if (!tbody) return;
    const query = (document.getElementById('en-table-search')?.value || '').trim().toLowerCase();

    let rows = (rooms || []).filter(r => {
      if (roomFilter !== 'all' && r.ruang !== roomFilter) return false;
      if (!query) return true;
      return `${r.device_id} ${r.display_name} ${r.ruang} ${r.status}`.toLowerCase().includes(query);
    });

    const dir = sortAsc ? 1 : -1;
    rows.sort((a, b) => {
      const va = a[sortKey] ?? '';
      const vb = b[sortKey] ?? '';
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });

    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-slate-400">Tidak ada kWh meter yang cocok dengan filter.</td></tr>`;
      return;
    }

    tbody.innerHTML = rows.map(r => {
      const isOn = r.status === 'online';
      const pw = Number(r.power_w || 0);
      const loadPct = Math.min(100, Math.round((pw / 3500) * 100));
      const barColor = pw > 3000 ? 'bg-rose-500' : (pw > 200 ? 'bg-amber-400' : 'bg-sky-400');
      const badge = isOn
        ? `<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/25"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>Online</span>`
        : `<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-700/40 text-slate-300 border border-slate-600/50"><span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span>Offline</span>`;
      return `
        <tr data-meter-room="${escapeEnHtml(r.ruang)}" class="hover:bg-slate-800/45 transition cursor-pointer">
          <td class="py-2.5 px-3">
            <div class="en-num font-semibold text-slate-100">${escapeEnHtml(r.device_id)}</div>
            <div class="text-[11px] text-slate-400">${escapeEnHtml(r.display_name)} · <span class="text-sky-300">${escapeEnHtml(r.ruang)}</span></div>
          </td>
          <td class="py-2.5 px-3">${badge}</td>
          <td class="py-2.5 px-3 min-w-[160px]">
            <div class="flex items-center justify-between text-xs mb-1">
              <strong class="en-num text-white">${pw.toFixed(1)} W</strong>
              <span class="en-num text-[10px] text-slate-400">${loadPct}%</span>
            </div>
            <div class="w-full h-1.5 rounded bg-slate-800 overflow-hidden">
              <div class="h-1.5 rounded ${barColor} transition-all duration-300" style="width:${loadPct}%"></div>
            </div>
          </td>
          <td class="py-2.5 px-3 text-slate-200 en-num font-medium">${Number(r.energy_kwh || 0).toFixed(4)} kWh</td>
          <td class="py-2.5 px-3 text-slate-400 en-num text-[11px]">${escapeEnHtml(formatEnTimeWib(r.last_seen))}</td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('tr[data-meter-room]').forEach(tr => {
      tr.addEventListener('click', () => {
        if (typeof onSelectRoom === 'function') onSelectRoom(tr.dataset.meterRoom);
      });
    });
  }

  resizeAll() {
    this.charts.power?.resize();
    this.charts.donut?.resize();
    this.charts.baseline?.resize();
  }
}
