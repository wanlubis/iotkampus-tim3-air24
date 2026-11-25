// Shared constants, room architectural metadata, formatters, and preview snapshot
// Scoped to Tim 1 Smart Energy (Gedung BSD-A Lantai 3)

export const ENERGY_ROOM_COLORS = {
  r3012: '#38bdf8',
  r3013: '#22c55e',
  r3017: '#f59e0b',
  'lab-iot': '#c084fc'
};

export const FLOORPLAN_ROOMS = [
  {
    ruang: 'r3012',
    codeLabel: 'R3012',
    device_id: 'kwh-01',
    label: 'Ruang Kuliah 3012',
    subtitle: 'Kelas Reguler · 2 AC Split + Proyektor',
    wing: 'Utara Barat',
    areaM2: 64,
    type: 'classroom',
    // SVG architectural geometry (viewBox 0 0 820 440)
    rect: { x: 88, y: 36, w: 300, h: 152 },
    door: { x: 304, y: 188, w: 36, dir: 'up-left' },
    meterPos: { x: 280, y: 184 }
  },
  {
    ruang: 'r3013',
    codeLabel: 'R3013',
    device_id: 'kwh-02',
    label: 'Ruang Kuliah 3013',
    subtitle: 'Kelas Seminar · AC Cassette + Audio',
    wing: 'Utara Timur',
    areaM2: 72,
    type: 'seminar',
    rect: { x: 432, y: 36, w: 332, h: 152 },
    door: { x: 468, y: 188, w: 36, dir: 'up-right' },
    meterPos: { x: 526, y: 184 }
  },
  {
    ruang: 'r3017',
    codeLabel: 'R3017',
    device_id: 'kwh-03',
    label: 'Ruang Diskusi 3017',
    subtitle: 'Studio Kolaborasi · Smart TV + Lighting',
    wing: 'Selatan Barat',
    areaM2: 64,
    type: 'studio',
    rect: { x: 88, y: 252, w: 300, h: 152 },
    door: { x: 304, y: 252, w: 36, dir: 'down-left' },
    meterPos: { x: 280, y: 256 }
  },
  {
    ruang: 'lab-iot',
    codeLabel: 'Lab-IoT',
    device_id: 'kwh-04',
    label: 'Lab IoT & Embedded',
    subtitle: '30 Workstation · Server Rack + Oscilloscope',
    wing: 'Selatan Timur',
    areaM2: 86,
    type: 'lab',
    rect: { x: 432, y: 252, w: 332, h: 152 },
    door: { x: 468, y: 252, w: 36, dir: 'down-right' },
    meterPos: { x: 526, y: 256 }
  }
];

export const STATUS_META = {
  normal: {
    key: 'normal',
    label: 'NORMAL',
    shortLabel: 'Normal',
    stroke: '#38bdf8',
    fillTint: 'rgba(56, 189, 248, 0.08)',
    fillHover: 'rgba(56, 189, 248, 0.14)',
    glowId: 'en-glow-normal',
    textHex: '#7dd3fc',
    dotClass: 'bg-sky-400',
    badgeClass: 'bg-sky-500/15 text-sky-300 border-sky-400/30'
  },
  waste: {
    key: 'waste',
    label: 'WASTE >200W',
    shortLabel: 'Waste',
    stroke: '#f59e0b',
    fillTint: 'rgba(245, 158, 11, 0.11)',
    fillHover: 'rgba(245, 158, 11, 0.18)',
    glowId: 'en-glow-waste',
    textHex: '#fcd34d',
    dotClass: 'bg-amber-400',
    badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-400/35'
  },
  high_load: {
    key: 'high_load',
    label: 'HIGH LOAD',
    shortLabel: 'High-Load',
    stroke: '#f43f5e',
    fillTint: 'rgba(244, 63, 94, 0.12)',
    fillHover: 'rgba(244, 63, 94, 0.20)',
    glowId: 'en-glow-high',
    textHex: '#fda4af',
    dotClass: 'bg-rose-500',
    badgeClass: 'bg-rose-500/15 text-rose-300 border-rose-500/35'
  },
  offline: {
    key: 'offline',
    label: 'OFFLINE',
    shortLabel: 'Offline',
    stroke: '#475569',
    fillTint: 'rgba(71, 85, 105, 0.10)',
    fillHover: 'rgba(100, 116, 139, 0.18)',
    glowId: 'en-glow-offline',
    textHex: '#94a3b8',
    dotClass: 'bg-slate-500',
    badgeClass: 'bg-slate-700/40 text-slate-300 border-slate-600/50'
  }
};

export function escapeEnHtml(val) {
  return String(val ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function formatEnIdr(val) {
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    maximumFractionDigits: 0
  }).format(Number(val || 0));
}

export function formatEnTimeWib(isoStr) {
  if (!isoStr) return '-';
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return isoStr;
  return d.toLocaleTimeString('id-ID', {
    timeZone: 'Asia/Jakarta',
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }) + ' WIB';
}

export function resolveEnergyAlertRoom(alertObj, roomsList = []) {
  if (alertObj?.context?.ruang) return alertObj.context.ruang;
  if (alertObj?.ruang) return alertObj.ruang;
  const dev = (roomsList || []).find(r => r.device_id === alertObj?.device_id);
  return dev ? dev.ruang : null;
}

export function computeRoomStatus(roomData, roomAlerts = []) {
  const online = roomData?.status === 'online' || Boolean(roomData?.online);
  const pw = Number(roomData?.power_w || 0);
  const unacked = (roomAlerts || []).filter(a => !a.ts_acked);
  if (!online) return 'offline';
  if (pw > 3000 || unacked.some(a => (a.code || a.type) === 'HIGH_LOAD')) return 'high_load';
  if (unacked.some(a => (a.code || a.type) === 'WASTE_AFTER_HOURS')) return 'waste';
  return 'normal';
}

// Realistic local simulation snapshot (only used when user enables Mode Simulasi)
export function buildEnergyPreviewSnapshot(period, winMins, previewAckedIds = {}) {
  const nowMs = Date.now();
  const scale = period === 'weekly' ? 6.4 : 1.0;
  const tarif = 1500;

  const rooms = [
    { device_id: 'kwh-01', display_name: 'KWh Meter Ruang 3012', gedung: 'bsd-a', ruang: 'r3012', status: 'online', online: true, power_w: 785.4, energy_kwh: 18.42, last_seen: new Date(nowMs - 4000).toISOString() },
    { device_id: 'kwh-02', display_name: 'KWh Meter Ruang 3013', gedung: 'bsd-a', ruang: 'r3013', status: 'online', online: true, power_w: 3180.0, energy_kwh: 29.85, last_seen: new Date(nowMs - 3000).toISOString() },
    { device_id: 'kwh-03', display_name: 'KWh Meter Ruang 3017', gedung: 'bsd-a', ruang: 'r3017', status: 'online', online: true, power_w: 412.6, energy_kwh: 14.11, last_seen: new Date(nowMs - 5000).toISOString() },
    { device_id: 'kwh-04', display_name: 'KWh Meter Lab IoT', gedung: 'bsd-a', ruang: 'lab-iot', status: 'offline', online: false, power_w: 0.0, energy_kwh: 34.90, last_seen: new Date(nowMs - 185000).toISOString() }
  ];

  const perRuang = [
    { device_id: 'kwh-01', ruang: 'r3012', display_name: 'KWh Meter Ruang 3012', energy_kwh: Number((5.4 * scale).toFixed(3)), estimasi_tagihan_idr: Math.round(5.4 * scale * tarif) },
    { device_id: 'kwh-02', ruang: 'r3013', display_name: 'KWh Meter Ruang 3013', energy_kwh: Number((8.9 * scale).toFixed(3)), estimasi_tagihan_idr: Math.round(8.9 * scale * tarif) },
    { device_id: 'kwh-03', ruang: 'r3017', display_name: 'KWh Meter Ruang 3017', energy_kwh: Number((3.6 * scale).toFixed(3)), estimasi_tagihan_idr: Math.round(3.6 * scale * tarif) },
    { device_id: 'kwh-04', ruang: 'lab-iot', display_name: 'KWh Meter Lab IoT', energy_kwh: Number((6.2 * scale).toFixed(3)), estimasi_tagihan_idr: Math.round(6.2 * scale * tarif) }
  ];
  const totalKwh = Number(perRuang.reduce((a, b) => a + b.energy_kwh, 0).toFixed(3));

  const points = 12;
  const stepMs = (winMins * 60 * 1000) / points;
  const curves = {
    r3012: [610, 640, 720, 790, 810, 770, 740, 760, 805, 820, 795, 785],
    r3013: [890, 940, 1120, 1450, 2200, 2890, 3150, 3240, 3110, 3080, 3210, 3180],
    r3017: [290, 310, 350, 420, 440, 400, 380, 395, 430, 450, 425, 413],
    'lab-iot': [980, 1020, 990, 950, 880, 820, 610, 420, 120, 0, 0, 0]
  };
  const telemData = [];
  for (let i = 0; i < points; i++) {
    const tsIso = new Date(nowMs - (points - 1 - i) * stepMs).toISOString();
    for (const r of rooms) {
      telemData.push({
        time: tsIso,
        device_id: r.device_id,
        ruang: r.ruang,
        field: 'power_w',
        value: curves[r.ruang][i]
      });
    }
  }

  const rawAlerts = [
    {
      id: 'ALT-PREVIEW-0001',
      device_id: 'kwh-02',
      domain: 'energy',
      code: 'HIGH_LOAD',
      severity: 'critical',
      message: 'Lonjakan beban di r3013 (kwh-02): 3180.0 W (> 3000 W selama 1 menit)',
      value: 3180.0,
      context: { ruang: 'r3013', gedung: 'bsd-a' },
      ts_raised: new Date(nowMs - 140000).toISOString(),
      ts_acked: previewAckedIds['ALT-PREVIEW-0001'] || null,
      acked_by: previewAckedIds['ALT-PREVIEW-0001'] ? 'Tim 1 Energy Operator' : null
    },
    {
      id: 'ALT-PREVIEW-0002',
      device_id: 'kwh-01',
      domain: 'energy',
      code: 'WASTE_AFTER_HOURS',
      severity: 'warning',
      message: 'Indikasi pemborosan di r3012 (kwh-01): 785.4 W di luar jam kerja (> 200 W)',
      value: 785.4,
      context: { ruang: 'r3012', gedung: 'bsd-a' },
      ts_raised: new Date(nowMs - 480000).toISOString(),
      ts_acked: previewAckedIds['ALT-PREVIEW-0002'] || null,
      acked_by: previewAckedIds['ALT-PREVIEW-0002'] ? 'Tim 1 Energy Operator' : null
    },
    {
      id: 'ALT-PREVIEW-0003',
      device_id: 'kwh-04',
      domain: 'energy',
      code: 'OFFLINE',
      severity: 'critical',
      message: 'Perangkat kwh-04 (lab-iot) berstatus offline (LWT / no-data > 60 detik)',
      value: 0.0,
      context: { ruang: 'lab-iot', gedung: 'bsd-a' },
      ts_raised: new Date(nowMs - 185000).toISOString(),
      ts_acked: previewAckedIds['ALT-PREVIEW-0003'] || null,
      acked_by: previewAckedIds['ALT-PREVIEW-0003'] ? 'Tim 1 Energy Operator' : null
    }
  ];

  const wasteAlerts = rawAlerts.filter(a => a.code === 'WASTE_AFTER_HOURS');
  const unackedWaste = wasteAlerts.filter(a => !a.ts_acked).length;

  return {
    rooms,
    bill: {
      periode: {
        jenis: period,
        from: new Date(nowMs - (period === 'weekly' ? 6 : 0.5) * 86400000).toISOString(),
        to: new Date(nowMs).toISOString()
      },
      tarif_asumsi: {
        tarif_per_kwh_idr: tarif,
        satuan: 'IDR/kWh',
        catatan: 'Asumsi tarif simulasi internal kampus (bukan tarif resmi PLN).',
        jam_kerja_wib: 'Senin-Jumat pukul 07:00-18:00 WIB'
      },
      total_kwh: totalKwh,
      estimasi_tagihan_total_idr: Math.round(totalKwh * tarif),
      per_ruang: perRuang
    },
    waste: {
      summary: {
        total_events: wasteAlerts.length,
        unacked_count: unackedWaste,
        acked_count: wasteAlerts.length - unackedWaste
      },
      items: wasteAlerts
    },
    alerts: rawAlerts,
    telemetry: telemData,
    baseline: [
      { ruang: 'r3012', device_id: 'kwh-01', avg_work_hours_w: 790.5, avg_after_hours_w: 410.2, samples_work_hours: 120, samples_after_hours: 48 },
      { ruang: 'r3013', device_id: 'kwh-02', avg_work_hours_w: 1420.0, avg_after_hours_w: 185.0, samples_work_hours: 118, samples_after_hours: 50 },
      { ruang: 'r3017', device_id: 'kwh-03', avg_work_hours_w: 520.3, avg_after_hours_w: 92.4, samples_work_hours: 120, samples_after_hours: 52 },
      { ruang: 'lab-iot', device_id: 'kwh-04', avg_work_hours_w: 1080.0, avg_after_hours_w: 115.6, samples_work_hours: 96, samples_after_hours: 40 }
    ]
  };
}
