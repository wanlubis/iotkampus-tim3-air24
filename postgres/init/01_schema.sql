-- =====================================
-- COLD-CHAIN DATABASE SCHEMA
-- =====================================

CREATE TABLE IF NOT EXISTS devices (
    device_id VARCHAR(50) PRIMARY KEY,
    domain VARCHAR(50) NOT NULL DEFAULT 'coldchain',
    gedung VARCHAR(100) NOT NULL,
    ruang VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'offline',
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_device_status
        CHECK (status IN ('online', 'offline'))
);

-- =====================================
-- MASTER DATA CHAMBERS
-- =====================================

INSERT INTO devices (device_id, gedung, ruang)
VALUES
    ('cc-01', 'bsd-a', 'gudang-a'),
    ('cc-02', 'bsd-a', 'gudang-a'),
    ('cc-03', 'bsd-a', 'gudang-b')
ON CONFLICT (device_id) DO NOTHING;

-- =====================================
-- ALERT EVENTS
-- =====================================

CREATE TABLE IF NOT EXISTS alert_events (
    alert_id BIGSERIAL PRIMARY KEY,

    device_id VARCHAR(50) NOT NULL
        REFERENCES devices(device_id),

    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT,

    status VARCHAR(20) NOT NULL DEFAULT 'active',

    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(100),
    resolved_at TIMESTAMPTZ,

    metadata JSONB DEFAULT '{}'::jsonb,

    CONSTRAINT valid_alert_severity
        CHECK (
            severity IN (
                'info',
                'warning',
                'critical',
                'escalated'
            )
        ),

    CONSTRAINT valid_alert_status
        CHECK (
            status IN (
                'active',
                'acknowledged',
                'resolved'
            )
        )
);

-- =====================================
-- INDEXES
-- =====================================

CREATE INDEX IF NOT EXISTS idx_alert_device
    ON alert_events(device_id);

CREATE INDEX IF NOT EXISTS idx_alert_status
    ON alert_events(status);

CREATE INDEX IF NOT EXISTS idx_alert_triggered
    ON alert_events(triggered_at DESC);