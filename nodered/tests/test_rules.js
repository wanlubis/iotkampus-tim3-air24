/**
 * test_rules.js - Unit Test Validator & Rule Engine Smart Energy (Tim 1 - AIR24)
 * Memverifikasi seluruh kontrak wanlubis/iotkampus-tim3-air24:
 * - Validasi skema kampus.telemetry.v1 & kampus.status.v1
 * - Deteksi jam kerja WIB (Senin-Jumat 07:00-18:00)
 * - WASTE_AFTER_HOURS (> 200 W luar jam kerja selama >= 2 menit) + dedup + auto-resolve
 * - HIGH_LOAD (> 3000 W selama >= 1 menit) + dedup + auto-resolve
 * - OFFLINE (LWT offline + watchdog no-data 60 detik) + dedup + auto-resolve
 *
 * Jalankan: node nodered/tests/test_rules.js
 */

const assert = require('assert');
const { validateTelemetry, validateStatus } = require('../lib/validator');
const {
    isWorkHourWIB,
    evaluateEnergyTelemetry,
    evaluateEnergyStatus,
    checkEnergyOfflineWatchdog
} = require('../lib/energy_rules');
const { EnergyRuleState } = require('../lib/storage');

let passed = 0;
let total = 0;

function runTest(name, fn) {
    total++;
    try {
        fn();
        console.log(`  [PASS] ${name}`);
        passed++;
    } catch (err) {
        console.error(`  [FAIL] ${name}`);
        console.error(`         ${err.message}`);
    }
}

console.log('==============================================================');
console.log(' TEST SUITE TIM 1 (SMART ENERGY) — KONTRAK AIR24 MONOREPO');
console.log('==============================================================\n');

// Helper membuat timestamp WIB (UTC+7)
function wibEpoch(year, month, day, hour, minute = 0, second = 0) {
    return Date.UTC(year, month - 1, day, hour - 7, minute, second);
}

console.log('--- 1. Validasi Skema MQTT (kampus.telemetry.v1 & kampus.status.v1) ---');

runTest('Menerima payload telemetry v1 domain energy yang sah', () => {
    const res = validateTelemetry({
        schema: 'kampus.telemetry.v1',
        ts: wibEpoch(2026, 11, 23, 10, 0),
        device_id: 'kwh-01',
        domain: 'energy',
        gedung: 'bsd-a',
        ruang: 'r3012',
        metrics: { power_w: 850.5, energy_kwh: 120.51 }
    });
    assert.strictEqual(res.valid, true);
    assert.strictEqual(res.errors.length, 0);
});

runTest('Menolak telemetry jika schema salah atau ts bukan epoch ms numerik', () => {
    const res = validateTelemetry({
        schema: 'wrong.v1',
        ts: '2026-11-23T10:00:00Z',
        device_id: 'kwh-01',
        domain: 'energy',
        gedung: 'bsd-a',
        ruang: 'r3012',
        metrics: { power_w: 500, energy_kwh: 10 }
    });
    assert.strictEqual(res.valid, false);
    assert.ok(res.errors.length >= 2);
});

runTest('Menolak telemetry energy jika power_w negatif atau energy_kwh hilang', () => {
    const res = validateTelemetry({
        schema: 'kampus.telemetry.v1',
        ts: wibEpoch(2026, 11, 23, 10, 0),
        device_id: 'kwh-02',
        domain: 'energy',
        gedung: 'bsd-a',
        ruang: 'r3013',
        metrics: { power_w: -10 }
    });
    assert.strictEqual(res.valid, false);
    assert.ok(res.errors.some(e => e.includes('power_w')));
    assert.ok(res.errors.some(e => e.includes('energy_kwh')));
});

runTest('Memvalidasi status v1 (hanya online/offline huruf kecil)', () => {
    const ok = validateStatus({
        schema: 'kampus.status.v1',
        ts: wibEpoch(2026, 11, 23, 10, 0),
        device_id: 'kwh-01',
        domain: 'energy',
        gedung: 'bsd-a',
        ruang: 'r3012',
        status: 'online'
    });
    assert.strictEqual(ok.valid, true);

    const bad = validateStatus({
        schema: 'kampus.status.v1',
        ts: wibEpoch(2026, 11, 23, 10, 0),
        device_id: 'kwh-01',
        domain: 'energy',
        status: 'ONLINE'
    });
    assert.strictEqual(bad.valid, false);
});

console.log('\n--- 2. Evaluasi Jam Kerja WIB (Senin-Jumat 07:00-18:00 WIB) ---');

runTest('Jam kerja vs luar jam kerja WIB tepat (termasuk akhir pekan)', () => {
    // 23 Nov 2026 = Senin
    assert.strictEqual(isWorkHourWIB(wibEpoch(2026, 11, 23, 7, 0)), true);
    assert.strictEqual(isWorkHourWIB(wibEpoch(2026, 11, 23, 17, 59)), true);
    assert.strictEqual(isWorkHourWIB(wibEpoch(2026, 11, 23, 6, 59)), false);
    assert.strictEqual(isWorkHourWIB(wibEpoch(2026, 11, 23, 18, 0)), false);
    assert.strictEqual(isWorkHourWIB(wibEpoch(2026, 11, 23, 21, 30)), false);
    // 22 Nov 2026 = Minggu
    assert.strictEqual(isWorkHourWIB(wibEpoch(2026, 11, 22, 10, 0)), false);
});

console.log('\n--- 3. Rule WASTE_AFTER_HOURS (> 200 W luar jam kerja >= 2 menit) ---');

runTest('Tidak memicu WASTE_AFTER_HOURS pada jam kerja normal (500 W siang hari)', () => {
    const state = new EnergyRuleState();
    const t0 = wibEpoch(2026, 11, 23, 10, 0, 0);
    const e1 = evaluateEnergyTelemetry({
        schema: 'kampus.telemetry.v1', ts: t0, device_id: 'kwh-02',
        domain: 'energy', gedung: 'bsd-a', ruang: 'r3013',
        metrics: { power_w: 500, energy_kwh: 100.1 }
    }, state);
    const e2 = evaluateEnergyTelemetry({
        schema: 'kampus.telemetry.v1', ts: t0 + 180_000, device_id: 'kwh-02',
        domain: 'energy', gedung: 'bsd-a', ruang: 'r3013',
        metrics: { power_w: 520, energy_kwh: 100.2 }
    }, state);
    assert.strictEqual(e1.length, 0);
    assert.strictEqual(e2.length, 0);
});

runTest('WASTE_AFTER_HOURS PENDING sebelum 2 menit, TRIGGERED pada >= 2 menit, DEDUP, lalu AUTO-RESOLVE', () => {
    const state = new EnergyRuleState();
    const t0 = wibEpoch(2026, 11, 23, 21, 0, 0); // Senin 21:00 WIB

    const makeMsg = (offsetSec, powerW) => ({
        schema: 'kampus.telemetry.v1',
        ts: t0 + offsetSec * 1000,
        device_id: 'kwh-02',
        domain: 'energy',
        gedung: 'bsd-a',
        ruang: 'r3013',
        metrics: { power_w: powerW, energy_kwh: 98.5 }
    });

    // t=0s: mulai pelanggaran -> PENDING
    const r0 = evaluateEnergyTelemetry(makeMsg(0, 620), state);
    assert.strictEqual(r0[0].action, 'PENDING');

    // t=90s: belum 2 menit -> masih PENDING
    const r90 = evaluateEnergyTelemetry(makeMsg(90, 640), state);
    assert.strictEqual(r90[0].action, 'PENDING');

    // t=120s: genap 2 menit -> ALERT_TRIGGERED (warning)
    const r120 = evaluateEnergyTelemetry(makeMsg(120, 650), state);
    assert.strictEqual(r120[0].action, 'ALERT_TRIGGERED');
    assert.strictEqual(r120[0].code, 'WASTE_AFTER_HOURS');
    assert.strictEqual(r120[0].alert.severity, 'warning');
    assert.strictEqual(r120[0].alert.domain, 'energy');
    assert.strictEqual(r120[0].alert.value, 650);

    // t=125s: masih boros -> SUPPRESSED (deduplikasi)
    const r125 = evaluateEnergyTelemetry(makeMsg(125, 660), state);
    assert.strictEqual(r125[0].action, 'SUPPRESSED');
    assert.strictEqual(r125[0].alert.occurrence_count, 2);

    // t=130s: beban turun <= 200 W -> RESOLVED (auto-resolve)
    const r130 = evaluateEnergyTelemetry(makeMsg(130, 85), state);
    assert.strictEqual(r130[0].action, 'RESOLVED');
    assert.strictEqual(r130[0].code, 'WASTE_AFTER_HOURS');
    assert.strictEqual(state.getActiveAlerts().length, 0);
});

runTest('Mode demo sim_after_hours=true memicu WASTE_AFTER_HOURS meski siang hari', () => {
    const state = new EnergyRuleState();
    const t0 = wibEpoch(2026, 11, 23, 11, 0, 0); // Siang hari (demo)
    evaluateEnergyTelemetry({
        schema: 'kampus.telemetry.v1', ts: t0, device_id: 'kwh-02',
        domain: 'energy', gedung: 'bsd-a', ruang: 'r3013', sim_after_hours: true,
        metrics: { power_w: 750, energy_kwh: 99.0 }
    }, state);
    const res = evaluateEnergyTelemetry({
        schema: 'kampus.telemetry.v1', ts: t0 + 120_000, device_id: 'kwh-02',
        domain: 'energy', gedung: 'bsd-a', ruang: 'r3013', sim_after_hours: true,
        metrics: { power_w: 760, energy_kwh: 99.1 }
    }, state);
    assert.strictEqual(res[0].action, 'ALERT_TRIGGERED');
    assert.strictEqual(res[0].code, 'WASTE_AFTER_HOURS');
});

console.log('\n--- 4. Rule HIGH_LOAD (> 3000 W selama >= 1 menit) ---');

runTest('HIGH_LOAD PENDING pada 30 dtk, TRIGGERED (critical) pada >= 60 dtk, DEDUP, lalu AUTO-RESOLVE', () => {
    const state = new EnergyRuleState();
    const t0 = wibEpoch(2026, 11, 23, 14, 0, 0); // Jam kerja siang

    const makeMsg = (offsetSec, powerW) => ({
        schema: 'kampus.telemetry.v1',
        ts: t0 + offsetSec * 1000,
        device_id: 'kwh-03',
        domain: 'energy',
        gedung: 'bsd-a',
        ruang: 'r3017',
        metrics: { power_w: powerW, energy_kwh: 146.0 }
    });

    assert.strictEqual(evaluateEnergyTelemetry(makeMsg(0, 3600), state)[0].action, 'PENDING');
    assert.strictEqual(evaluateEnergyTelemetry(makeMsg(30, 3700), state)[0].action, 'PENDING');

    const r60 = evaluateEnergyTelemetry(makeMsg(60, 3850), state);
    assert.strictEqual(r60[0].action, 'ALERT_TRIGGERED');
    assert.strictEqual(r60[0].code, 'HIGH_LOAD');
    assert.strictEqual(r60[0].alert.severity, 'critical');
    assert.strictEqual(r60[0].alert.value, 3850);

    const r65 = evaluateEnergyTelemetry(makeMsg(65, 3900), state);
    assert.strictEqual(r65[0].action, 'SUPPRESSED');

    const r70 = evaluateEnergyTelemetry(makeMsg(70, 950), state);
    assert.strictEqual(r70[0].action, 'RESOLVED');
    assert.strictEqual(r70[0].code, 'HIGH_LOAD');
});

console.log('\n--- 5. Rule OFFLINE (LWT & Watchdog No-Data 60 Detik) ---');

runTest('LWT offline langsung memicu OFFLINE (critical), dedup, lalu auto-resolve saat online', () => {
    const state = new EnergyRuleState();
    const t0 = wibEpoch(2026, 11, 23, 15, 0, 0);

    const off1 = evaluateEnergyStatus({
        schema: 'kampus.status.v1', ts: t0, device_id: 'kwh-01',
        domain: 'energy', gedung: 'bsd-a', ruang: 'r3012', status: 'offline'
    }, state);
    assert.strictEqual(off1[0].action, 'ALERT_TRIGGERED');
    assert.strictEqual(off1[0].code, 'OFFLINE');
    assert.strictEqual(off1[0].alert.severity, 'critical');

    const off2 = evaluateEnergyStatus({
        schema: 'kampus.status.v1', ts: t0 + 5000, device_id: 'kwh-01',
        domain: 'energy', gedung: 'bsd-a', ruang: 'r3012', status: 'offline'
    }, state);
    assert.strictEqual(off2[0].action, 'SUPPRESSED');

    const on1 = evaluateEnergyStatus({
        schema: 'kampus.status.v1', ts: t0 + 15000, device_id: 'kwh-01',
        domain: 'energy', gedung: 'bsd-a', ruang: 'r3012', status: 'online'
    }, state);
    assert.strictEqual(on1[0].action, 'RESOLVED');
    assert.strictEqual(on1[0].code, 'OFFLINE');
});

runTest('Watchdog no-data (STOP mode) memicu OFFLINE setelah 60 detik, lalu auto-resolve saat telemetry masuk lagi', () => {
    const state = new EnergyRuleState();
    const t0 = wibEpoch(2026, 11, 23, 15, 10, 0);

    // Telemetry terakhir masuk di t0
    evaluateEnergyTelemetry({
        schema: 'kampus.telemetry.v1', ts: t0, device_id: 'kwh-04',
        domain: 'energy', gedung: 'bsd-a', ruang: 'lab-iot',
        metrics: { power_w: 800, energy_kwh: 210.2 }
    }, state);

    // t + 45s -> belum timeout
    assert.strictEqual(checkEnergyOfflineWatchdog(t0 + 45_000, state).length, 0);

    // t + 60s -> timeout 60 detik -> ALERT_TRIGGERED OFFLINE
    const wd60 = checkEnergyOfflineWatchdog(t0 + 60_000, state);
    assert.strictEqual(wd60.length, 1);
    assert.strictEqual(wd60[0].action, 'ALERT_TRIGGERED');
    assert.strictEqual(wd60[0].code, 'OFFLINE');
    assert.strictEqual(wd60[0].alert.severity, 'critical');

    // t + 75s -> SUPPRESSED
    const wd75 = checkEnergyOfflineWatchdog(t0 + 75_000, state);
    assert.strictEqual(wd75[0].action, 'SUPPRESSED');

    // Telemetry baru masuk di t + 80s -> AUTO-RESOLVE OFFLINE
    const recovered = evaluateEnergyTelemetry({
        schema: 'kampus.telemetry.v1', ts: t0 + 80_000, device_id: 'kwh-04',
        domain: 'energy', gedung: 'bsd-a', ruang: 'lab-iot',
        metrics: { power_w: 820, energy_kwh: 210.3 }
    }, state);
    assert.strictEqual(recovered.some(e => e.action === 'RESOLVED' && e.code === 'OFFLINE'), true);
});

runTest('Mengabaikan pesan domain lain (air / coldchain) agar isolasi lintas domain terjaga', () => {
    const state = new EnergyRuleState();
    const res = evaluateEnergyTelemetry({
        schema: 'kampus.telemetry.v1', ts: wibEpoch(2026, 11, 23, 22, 0),
        device_id: 'aq-01', domain: 'air', gedung: 'bsd-a', ruang: 'r3012',
        metrics: { co2_ppm: 2000, pm25_ugm3: 90, noise_db: 80 }
    }, state);
    assert.strictEqual(res.length, 0);
});

console.log('\n==============================================================');
console.log(` HASIL TEST: ${passed} / ${total} BERHASIL`);
console.log('==============================================================\n');

process.exit(passed === total ? 0 : 1);
