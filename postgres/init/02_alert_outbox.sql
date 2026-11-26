-- =====================================
-- ALERT OUTBOX
-- Transactional synchronization queue
-- =====================================

CREATE TABLE IF NOT EXISTS alert_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,

    alert_id BIGINT NOT NULL
        REFERENCES alert_events(alert_id),

    event_type VARCHAR(30) NOT NULL,

    payload JSONB NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    attempts INTEGER NOT NULL DEFAULT 0,

    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    locked_until TIMESTAMPTZ,

    last_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    synced_at TIMESTAMPTZ,

    CONSTRAINT valid_outbox_status
        CHECK (
            status IN (
                'pending',
                'processing',
                'synced'
            )
        ),

    CONSTRAINT valid_outbox_event
        CHECK (
            event_type IN (
                'CREATED',
                'ACKNOWLEDGED',
                'RESOLVED'
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_alert_outbox_pending
    ON alert_outbox(next_attempt_at, outbox_id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_alert_outbox_alert
    ON alert_outbox(alert_id);

CREATE INDEX IF NOT EXISTS idx_alert_outbox_processing
    ON alert_outbox(locked_until)
    WHERE status = 'processing';
