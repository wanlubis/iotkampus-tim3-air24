-- Schema resmi Mini IoT Platform Kampus (AIR24)
-- Sesuai Spesifikasi Bagian 4.5 & 4.2

-- Tabel Data Master Perangkat (Registry)
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    domain TEXT NOT NULL, -- energy | coldchain | air
    gedung TEXT NOT NULL,
    ruang TEXT NOT NULL,
    jenis TEXT NOT NULL,  -- kwh-meter | chamber | aq-node
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tabel Riwayat Alert & Status ACK
CREATE TABLE IF NOT EXISTS alert_events (
    id TEXT PRIMARY KEY, -- contoh: ALT-20261119-0007
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    domain TEXT NOT NULL,
    code TEXT NOT NULL, -- CO2_HIGH, PM25_HIGH, NOISE_HIGH, TEMP_HIGH, WASTE_AFTER_HOURS, OFFLINE, dll.
    severity TEXT NOT NULL, -- warning | critical | escalated
    message TEXT NOT NULL,
    value DOUBLE PRECISION,
    ts_raised TIMESTAMPTZ NOT NULL,
    ts_acked TIMESTAMPTZ,
    acked_by TEXT,
    context JSONB
);

-- Index untuk mempercepat query API
CREATE INDEX IF NOT EXISTS idx_devices_domain ON devices(domain);
CREATE INDEX IF NOT EXISTS idx_devices_gedung ON devices(gedung);
CREATE INDEX IF NOT EXISTS idx_alerts_device_id ON alert_events(device_id);
CREATE INDEX IF NOT EXISTS idx_alerts_domain ON alert_events(domain);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alert_events(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_ts_raised ON alert_events(ts_raised DESC);

-- Seed Data: 10 Perangkat Wajib Minimum (Bagian 4.2 & Checklist demo)
INSERT INTO devices (device_id, display_name, domain, gedung, ruang, jenis, is_active)
VALUES
    -- Tim 1: Smart Energy (4 kWh meter)
    ('kwh-01', 'KWh Meter Ruang 3012', 'energy', 'bsd-a', 'r3012', 'kwh-meter', TRUE),
    ('kwh-02', 'KWh Meter Ruang 3013', 'energy', 'bsd-a', 'r3013', 'kwh-meter', TRUE),
    ('kwh-03', 'KWh Meter Ruang 3017', 'energy', 'bsd-a', 'r3017', 'kwh-meter', TRUE),
    ('kwh-04', 'KWh Meter Lab IoT', 'energy', 'bsd-a', 'lab-iot', 'kwh-meter', TRUE),

    -- Tim 2: Cold-Chain (3 chamber)
    ('cc-01', 'Chamber Vaksin Utama', 'coldchain', 'bsd-a', 'gudang-a', 'chamber', TRUE),
    ('cc-02', 'Chamber Sampel Darah', 'coldchain', 'bsd-a', 'gudang-a', 'chamber', TRUE),
    ('cc-03', 'Chamber Reagen Kimia', 'coldchain', 'bsd-a', 'gudang-b', 'chamber', TRUE),

    -- Tim 3: Smart Environment / Air Quality (3 node)
    ('aq-01', 'Air Quality Monitor R3012', 'air', 'bsd-a', 'r3012', 'aq-node', TRUE),
    ('aq-02', 'Air Quality Monitor R3017', 'air', 'bsd-a', 'r3017', 'aq-node', TRUE),
    ('aq-03', 'Air Quality Monitor Koridor 1', 'air', 'bsd-a', 'koridor-1', 'aq-node', TRUE)
ON CONFLICT (device_id) DO UPDATE 
SET display_name = EXCLUDED.display_name,
    domain = EXCLUDED.domain,
    gedung = EXCLUDED.gedung,
    ruang = EXCLUDED.ruang,
    jenis = EXCLUDED.jenis,
    is_active = EXCLUDED.is_active;
