/**
 * validator.js - Validasi Skema MQTT sesuai docs/MQTT_CONTRACT.md (AIR24)
 * Mendukung amplop kampus.telemetry.v1 dan kampus.status.v1
 */

function validateTelemetry(data) {
    const errors = [];

    if (!data || typeof data !== 'object') {
        return { valid: false, errors: ['Payload harus berupa JSON object'] };
    }

    if (data.schema !== 'kampus.telemetry.v1') {
        errors.push(`Schema harus 'kampus.telemetry.v1', diterima: '${data.schema}'`);
    }

    if (typeof data.ts !== 'number' || !Number.isFinite(data.ts) || data.ts <= 0) {
        errors.push(`Timestamp 'ts' wajib epoch milidetik numerik positif, diterima: ${data.ts}`);
    }

    for (const field of ['device_id', 'domain', 'gedung', 'ruang']) {
        if (!data[field] || typeof data[field] !== 'string') {
            errors.push(`Field '${field}' wajib diisi berupa string`);
        }
    }

    if (!data.metrics || typeof data.metrics !== 'object' || Array.isArray(data.metrics)) {
        errors.push("Field 'metrics' wajib berupa objek JSON");
    } else {
        for (const [k, v] of Object.entries(data.metrics)) {
            const isValidType = typeof v === 'number' || (k === 'door_open' && typeof v === 'boolean');
            if (!isValidType || (typeof v === 'number' && !Number.isFinite(v))) {
                errors.push(`Metric '${k}' memiliki nilai tidak valid: ${v}`);
            }
        }

        // Validasi khusus domain Smart Energy (Bagian 5.2)
        if (data.domain === 'energy') {
            if (typeof data.metrics.power_w !== 'number' || data.metrics.power_w < 0) {
                errors.push(`metrics.power_w wajib angka >= 0, diterima: ${data.metrics.power_w}`);
            }
            if (typeof data.metrics.energy_kwh !== 'number' || data.metrics.energy_kwh < 0) {
                errors.push(`metrics.energy_kwh wajib angka >= 0, diterima: ${data.metrics.energy_kwh}`);
            }
        }
    }

    return {
        valid: errors.length === 0,
        errors
    };
}

function validateStatus(data) {
    const errors = [];

    if (!data || typeof data !== 'object') {
        return { valid: false, errors: ['Payload status harus berupa JSON object'] };
    }

    if (data.schema !== 'kampus.status.v1') {
        errors.push(`Schema harus 'kampus.status.v1', diterima: '${data.schema}'`);
    }

    if (typeof data.ts !== 'number' || !Number.isFinite(data.ts) || data.ts <= 0) {
        errors.push(`Timestamp 'ts' wajib epoch milidetik numerik positif`);
    }

    if (!data.device_id || typeof data.device_id !== 'string') {
        errors.push("Field 'device_id' wajib berupa string");
    }

    if (!data.domain || typeof data.domain !== 'string') {
        errors.push("Field 'domain' wajib berupa string");
    }

    if (data.status !== 'online' && data.status !== 'offline') {
        errors.push(`Status wajib 'online' atau 'offline' (huruf kecil), diterima: '${data.status}'`);
    }

    return {
        valid: errors.length === 0,
        errors
    };
}

module.exports = {
    validateTelemetry,
    validateStatus
};
