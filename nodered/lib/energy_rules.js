/**
 * energy_rules.js - Rule Engine Smart Energy (Tim 1 - AIR24)
 * Mengacu pada kontrak resmi wanlubis/iotkampus-tim3-air24:
 * - Jam kerja acuan: Senin-Jumat 07:00-18:00 WIB (UTC+7)
 * - WASTE_AFTER_HOURS (warning) : power_w > 200 W di luar jam kerja selama >= 2 menit (120 dtk)
 * - HIGH_LOAD (critical)        : power_w > 3000 W selama >= 1 menit (60 dtk)
 * - OFFLINE (critical)          : telemetry/heartbeat hilang >= 60 dtk atau status LWT "offline"
 * - Deduplikasi & Auto-Resolve  : cegah spam alert berulang & pulihkan otomatis saat normal
 * - Format output alert sesuai POST /api/v1/alerts di FastAPI core.py
 */

const DEFAULTS = {
    workStartHour: 7,
    workEndHour: 18,
    wasteThresholdW: 200.0,
    wasteDurationMs: 120 * 1000,      // 2 menit
    highLoadThresholdW: 3000.0,
    highLoadDurationMs: 60 * 1000,    // 1 menit
    offlineTimeoutMs: 60 * 1000       // 60 detik
};

/**
 * Mengecek apakah epoch ms berada pada jam kerja kampus (Senin-Jumat 07:00-18:00 WIB).
 */
function isWorkHourWIB(tsMs, opts = DEFAULTS) {
    // Geser +7 jam ke WIB lalu baca komponen UTC agar independen dari timezone host OS
    const wib = new Date(tsMs + 7 * 3600 * 1000);
    const day = wib.getUTCDay(); // 0=Minggu, 1=Senin .. 5=Jumat, 6=Sabtu
    const hour = wib.getUTCHours();
    const isWeekday = day >= 1 && day <= 5;
    return isWeekday && hour >= opts.workStartHour && hour < opts.workEndHour;
}

/**
 * Evaluasi rule berbasis durasi (sustained threshold) dengan dedup & auto-resolve.
 */
function _evalSustainedRule(state, key, isBreaching, tsMs, durationMs, buildAlertFn, resolveNoteFn) {
    if (isBreaching) {
        if (state.breachSince[key] === undefined) {
            state.breachSince[key] = tsMs;
        }
        const elapsedMs = tsMs - state.breachSince[key];
        if (elapsedMs < durationMs) {
            return { action: 'PENDING', elapsed_ms: elapsedMs, required_ms: durationMs };
        }

        if (state.activeAlerts[key]) {
            // Deduplikasi: alert sudah aktif -> jangan spam POST /api/v1/alerts
            state.activeAlerts[key].occurrence_count += 1;
            state.activeAlerts[key].last_seen_ts = tsMs;
            return {
                action: 'SUPPRESSED',
                code: state.activeAlerts[key].code,
                alert: state.activeAlerts[key]
            };
        }

        const alertPayload = buildAlertFn(Math.round(elapsedMs / 1000));
        state.activeAlerts[key] = {
            ...alertPayload,
            triggered_ts: tsMs,
            last_seen_ts: tsMs,
            occurrence_count: 1
        };
        return {
            action: 'ALERT_TRIGGERED',
            code: alertPayload.code,
            alert: alertPayload
        };
    } else {
        // Kondisi kembali normal -> reset timer & auto-resolve bila sebelumnya OPEN
        delete state.breachSince[key];
        if (state.activeAlerts[key]) {
            const prev = state.activeAlerts[key];
            delete state.activeAlerts[key];
            return {
                action: 'RESOLVED',
                code: prev.code,
                alert: {
                    ...prev,
                    resolved_ts: tsMs,
                    resolution_note: resolveNoteFn()
                }
            };
        }
        return null;
    }
}

/**
 * Evaluasi 1 pesan telemetri `kampus.telemetry.v1` untuk domain `energy`.
 */
function evaluateEnergyTelemetry(data, state, options = {}) {
    if (!data || data.domain !== 'energy') {
        return [];
    }
    const cfg = { ...DEFAULTS, ...options };
    const tsMs = typeof data.ts === 'number' ? data.ts : Date.now();
    const deviceId = data.device_id;
    const gedung = data.gedung || 'bsd-a';
    const ruang = data.ruang || '';
    const metrics = data.metrics || {};
    const powerW = Number(metrics.power_w);
    const energyKwh = Number(metrics.energy_kwh || 0);

    const events = [];

    // Catat telemetri masuk & auto-resolve OFFLINE bila sebelumnya terputus
    state.recordTelemetry(data);
    const offlineKey = `${deviceId}:OFFLINE`;
    if (state.activeAlerts[offlineKey]) {
        const prev = state.activeAlerts[offlineKey];
        delete state.activeAlerts[offlineKey];
        events.push({
            action: 'RESOLVED',
            code: 'OFFLINE',
            alert: {
                ...prev,
                resolved_ts: tsMs,
                resolution_note: `Telemetri kembali diterima dari ${deviceId} (${ruang})`
            }
        });
    }

    // 1. Rule WASTE_AFTER_HOURS (warning): power_w > 200 W di luar jam kerja selama >= 2 menit
    const afterHours = !isWorkHourWIB(tsMs, cfg) || Boolean(data.sim_after_hours);
    const wasteBreach = afterHours && powerW > cfg.wasteThresholdW;
    const wasteEvent = _evalSustainedRule(
        state,
        `${deviceId}:WASTE_AFTER_HOURS`,
        wasteBreach,
        tsMs,
        cfg.wasteDurationMs,
        (durSec) => ({
            device_id: deviceId,
            domain: 'energy',
            code: 'WASTE_AFTER_HOURS',
            severity: 'warning',
            message: `Pemborosan daya di luar jam kerja pada ${ruang} (${powerW} W > ${cfg.wasteThresholdW} W selama ${durSec} dtk)`,
            value: powerW,
            context: {
                gedung,
                ruang,
                duration_sec: durSec,
                threshold_w: cfg.wasteThresholdW,
                energy_kwh: energyKwh,
                simulated_after_hours: Boolean(data.sim_after_hours)
            }
        }),
        () => `Konsumsi daya di ${ruang} kembali normal (${powerW} W)`
    );
    if (wasteEvent) {
        events.push(wasteEvent);
    }

    // 2. Rule HIGH_LOAD (critical): power_w > 3000 W selama >= 1 menit (dalam/luar jam kerja)
    const highLoadBreach = powerW > cfg.highLoadThresholdW;
    const highLoadEvent = _evalSustainedRule(
        state,
        `${deviceId}:HIGH_LOAD`,
        highLoadBreach,
        tsMs,
        cfg.highLoadDurationMs,
        (durSec) => ({
            device_id: deviceId,
            domain: 'energy',
            code: 'HIGH_LOAD',
            severity: 'critical',
            message: `Beban daya sangat tinggi di ${ruang} mencapai ${powerW} W (> ${cfg.highLoadThresholdW} W selama ${durSec} dtk)`,
            value: powerW,
            context: {
                gedung,
                ruang,
                duration_sec: durSec,
                threshold_w: cfg.highLoadThresholdW,
                energy_kwh: energyKwh
            }
        }),
        () => `Beban daya di ${ruang} kembali aman (${powerW} W <= ${cfg.highLoadThresholdW} W)`
    );
    if (highLoadEvent) {
        events.push(highLoadEvent);
    }

    return events;
}

/**
 * Evaluasi pesan status `kampus.status.v1` (Birth online & LWT offline) untuk domain energy.
 */
function evaluateEnergyStatus(data, state) {
    if (!data || data.domain !== 'energy') {
        return [];
    }
    const tsMs = typeof data.ts === 'number' ? data.ts : Date.now();
    const deviceId = data.device_id;
    const gedung = data.gedung || 'bsd-a';
    const ruang = data.ruang || '';
    const status = String(data.status || '').toLowerCase();
    const offlineKey = `${deviceId}:OFFLINE`;

    if (status === 'offline') {
        state.touchDevice(deviceId, tsMs, gedung, ruang, false);
        if (state.activeAlerts[offlineKey]) {
            state.activeAlerts[offlineKey].occurrence_count += 1;
            state.activeAlerts[offlineKey].last_seen_ts = tsMs;
            return [{ action: 'SUPPRESSED', code: 'OFFLINE', alert: state.activeAlerts[offlineKey] }];
        }
        const alertPayload = {
            device_id: deviceId,
            domain: 'energy',
            code: 'OFFLINE',
            severity: 'critical',
            message: `KWh Meter ${deviceId} (${ruang}) terputus dari broker (LWT offline)`,
            value: 0,
            context: { gedung, ruang, trigger: 'lwt_status' }
        };
        state.activeAlerts[offlineKey] = {
            ...alertPayload,
            triggered_ts: tsMs,
            last_seen_ts: tsMs,
            occurrence_count: 1
        };
        return [{ action: 'ALERT_TRIGGERED', code: 'OFFLINE', alert: alertPayload }];
    }

    if (status === 'online') {
        state.touchDevice(deviceId, tsMs, gedung, ruang, true);
        if (state.activeAlerts[offlineKey]) {
            const prev = state.activeAlerts[offlineKey];
            delete state.activeAlerts[offlineKey];
            return [{
                action: 'RESOLVED',
                code: 'OFFLINE',
                alert: {
                    ...prev,
                    resolved_ts: tsMs,
                    resolution_note: `Perangkat ${deviceId} kembali online (Birth message)`
                }
            }];
        }
    }

    return [];
}

/**
 * Watchdog periodik untuk mendeteksi perangkat yang diam (STOP mode / no-data >= 60 detik tanpa LWT).
 */
function checkEnergyOfflineWatchdog(nowMs, state, options = {}) {
    const cfg = { ...DEFAULTS, ...options };
    const events = [];

    for (const [deviceId, info] of Object.entries(state.lastSeen)) {
        const silentMs = nowMs - info.ts;
        const offlineKey = `${deviceId}:OFFLINE`;

        if (silentMs >= cfg.offlineTimeoutMs) {
            if (state.activeAlerts[offlineKey]) {
                state.activeAlerts[offlineKey].occurrence_count += 1;
                state.activeAlerts[offlineKey].last_seen_ts = nowMs;
                events.push({ action: 'SUPPRESSED', code: 'OFFLINE', alert: state.activeAlerts[offlineKey] });
            } else {
                const silentSec = Math.round(silentMs / 1000);
                const alertPayload = {
                    device_id: deviceId,
                    domain: 'energy',
                    code: 'OFFLINE',
                    severity: 'critical',
                    message: `Tidak ada telemetri/heartbeat dari ${deviceId} (${info.ruang}) selama ${silentSec} detik`,
                    value: silentSec,
                    context: {
                        gedung: info.gedung,
                        ruang: info.ruang,
                        trigger: 'no_data_timeout',
                        silent_sec: silentSec
                    }
                };
                state.activeAlerts[offlineKey] = {
                    ...alertPayload,
                    triggered_ts: nowMs,
                    last_seen_ts: nowMs,
                    occurrence_count: 1
                };
                events.push({ action: 'ALERT_TRIGGERED', code: 'OFFLINE', alert: alertPayload });
            }
        }
    }

    return events;
}

module.exports = {
    DEFAULTS,
    isWorkHourWIB,
    evaluateEnergyTelemetry,
    evaluateEnergyStatus,
    checkEnergyOfflineWatchdog
};
