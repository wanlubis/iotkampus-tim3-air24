// KPI Strip Component (Top 4 Primary BMS Metric Cards)

import { escapeEnHtml, formatEnIdr, formatEnTimeWib, resolveEnergyAlertRoom } from './constants.js';

export function updateEnergyKpiStrip({ rooms, bill, waste, period, roomFilter }) {
  const scopedRooms = (rooms || []).filter(r => roomFilter === 'all' || r.ruang === roomFilter);
  const totalPower = scopedRooms.reduce((sum, r) => sum + (r.status === 'online' ? Number(r.power_w || 0) : 0), 0);
  const onlineCnt = scopedRooms.filter(r => r.status === 'online').length;
  const capMax = Math.max(1, scopedRooms.length * 3000);
  const utilPct = ((totalPower / capMax) * 100).toFixed(1);

  const elPower = document.getElementById('en-kpi-power');
  const elOnline = document.getElementById('en-kpi-online');
  const elPowerDelta = document.getElementById('en-kpi-power-delta');

  if (elPower) elPower.textContent = `${totalPower.toFixed(1)} W`;
  if (elOnline) elOnline.textContent = `${onlineCnt}/${scopedRooms.length} meter online`;
  if (elPowerDelta) {
    elPowerDelta.textContent = `${utilPct}% beban`;
    elPowerDelta.className = Number(utilPct) > 70
      ? 'en-num text-[11px] font-medium px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30 whitespace-nowrap'
      : (Number(utilPct) > 25
          ? 'en-num text-[11px] font-medium px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 whitespace-nowrap'
          : 'en-num text-[11px] font-medium px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 whitespace-nowrap');
  }

  const scopedPerRuang = (bill?.per_ruang || []).filter(r => roomFilter === 'all' || r.ruang === roomFilter);
  const scopedKwh = scopedPerRuang.reduce((s, r) => s + Number(r.energy_kwh || 0), 0);
  const scopedBill = scopedPerRuang.reduce((s, r) => s + Number(r.estimasi_tagihan_idr || 0), 0);
  const tarif = bill?.tarif_asumsi?.tarif_per_kwh_idr ?? 1500;

  const elKwh = document.getElementById('en-kpi-kwh');
  const elKwhDelta = document.getElementById('en-kpi-kwh-delta');
  const elPeriodNote = document.getElementById('en-kpi-period-note');
  const elBill = document.getElementById('en-kpi-bill');
  const elTariff = document.getElementById('en-kpi-tariff');

  if (elKwh) elKwh.textContent = `${scopedKwh.toFixed(3)} kWh`;
  if (elKwhDelta) elKwhDelta.textContent = period === 'daily' ? 'Harian' : 'Mingguan';
  const periodNote = `${formatEnTimeWib(bill?.periode?.from)} - ${formatEnTimeWib(bill?.periode?.to)}`;
  if (elPeriodNote) {
    elPeriodNote.textContent = periodNote;
    elPeriodNote.title = periodNote;
  }
  if (elBill) elBill.textContent = formatEnIdr(scopedBill);
  if (elTariff) elTariff.textContent = `Rp ${Number(tarif).toLocaleString('id-ID')}/kWh`;

  const bannerEl = document.getElementById('en-assumptions-banner');
  if (bannerEl && bill?.tarif_asumsi) {
    bannerEl.innerHTML =
      `<strong>Tarif Simulasi:</strong> <strong class="text-emerald-300">Rp ${Number(tarif).toLocaleString('id-ID')} / kWh</strong> (${escapeEnHtml(bill.tarif_asumsi.catatan)})<br/><strong>Jam Kerja Kampus:</strong> ${escapeEnHtml(bill.tarif_asumsi.jam_kerja_wib)}.`;
  }

  const scopedWasteItems = (waste?.items || []).filter(item => {
    if (roomFilter === 'all') return true;
    const wRoom = resolveEnergyAlertRoom(item, rooms);
    return !wRoom || wRoom === roomFilter;
  });
  const unackedWaste = roomFilter === 'all'
    ? Number(waste?.summary?.unacked_count ?? 0)
    : scopedWasteItems.filter(item => !item.ts_acked && !item.acked).length;
  const totalWaste = roomFilter === 'all'
    ? Number(waste?.summary?.total_events ?? 0)
    : scopedWasteItems.length;

  const elWasteUnacked = document.getElementById('en-kpi-waste-unacked');
  const elWasteTotal = document.getElementById('en-kpi-waste-total');
  const elWasteBadge = document.getElementById('en-kpi-waste-badge');

  if (elWasteUnacked) elWasteUnacked.textContent = String(unackedWaste);
  if (elWasteTotal) elWasteTotal.textContent = `Total kejadian: ${totalWaste}`;
  if (elWasteBadge) {
    if (unackedWaste > 0) {
      elWasteBadge.textContent = 'Perlu ACK';
      elWasteBadge.className = 'text-[11px] font-medium px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30 whitespace-nowrap';
    } else {
      elWasteBadge.textContent = 'Aman';
      elWasteBadge.className = 'text-[11px] font-medium px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 whitespace-nowrap';
    }
  }
}
