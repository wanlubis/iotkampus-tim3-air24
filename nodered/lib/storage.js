/**
 * storage.js - Manajemen State Rule Engine Smart Energy (Tim 1 - AIR24)
 * Menyimpan timer durasi pelanggaran, status alert aktif (dedup/auto-resolve),
 * dan jejak waktu terakhir (lastSeen) untuk deteksi OFFLINE 60 detik.
 */

class EnergyRuleState {
    constructor(maxHistory = 50) {
        this.maxHistory = maxHistory;
        this.breachSince = {};   // { "kwh-01:WASTE_AFTER_HOURS": epochMs }
        this.activeAlerts = {};  // { "kwh-01:HIGH_LOAD": { ...alertMeta } }
        this.lastSeen = {};      // { "kwh-01": { ts, gedung, ruang, online } }
        this.telemetryRing = {}; // { "kwh-01": [ ...latest ] }
    }

    recordTelemetry(data) {
        const id = data.device_id;
        if (!this.telemetryRing[id]) {
            this.telemetryRing[id] = [];
        }
        this.telemetryRing[id].unshift(data);
        if (this.telemetryRing[id].length > this.maxHistory) {
            this.telemetryRing[id].pop();
        }
        this.touchDevice(id, data.ts, data.gedung, data.ruang, true);
    }

    touchDevice(deviceId, tsMs, gedung = 'bsd-a', ruang = '', online = true) {
        const prev = this.lastSeen[deviceId] || {};
        this.lastSeen[deviceId] = {
            ts: tsMs,
            gedung: gedung || prev.gedung || 'bsd-a',
            ruang: ruang || prev.ruang || '',
            online
        };
    }

    getLatestTelemetry(deviceId) {
        const arr = this.telemetryRing[deviceId];
        return arr && arr.length > 0 ? arr[0] : null;
    }

    getActiveAlerts() {
        return Object.values(this.activeAlerts);
    }
}

module.exports = {
    EnergyRuleState
};
