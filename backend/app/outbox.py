from psycopg.types.json import Jsonb


VALID_EVENTS = {
    "CREATED",
    "ACKNOWLEDGED",
    "RESOLVED",
}


def enqueue_alert_event(cur, alert, event_type: str):
    """
    Menambahkan event alert ke PostgreSQL Outbox.

    Harus dipanggil menggunakan cursor dan transaksi
    PostgreSQL yang sama dengan perubahan alert.
    """

    if event_type not in VALID_EVENTS:
        raise ValueError(
            f"Event type tidak valid: {event_type}"
        )

    if not alert:
        raise ValueError("Data alert tidak tersedia")

    cur.execute(
        """
        SELECT domain
        FROM devices
        WHERE device_id = %s
        """,
        (alert["device_id"],),
    )

    device = cur.fetchone()

    if not device:
        raise ValueError("Device tidak ditemukan")

    payload = {
        "alert_id": alert["alert_id"],
        "device_id": alert["device_id"],
        "domain": device["domain"],
        "alert_type": alert["alert_type"],
        "severity": alert["severity"],
        "message": alert.get("message"),
        "status": alert["status"],
        "triggered_at": (
            alert["triggered_at"].isoformat()
            if alert.get("triggered_at")
            else None
        ),
        "acknowledged_at": (
            alert["acknowledged_at"].isoformat()
            if alert.get("acknowledged_at")
            else None
        ),
        "acknowledged_by": alert.get("acknowledged_by"),
        "resolved_at": (
            alert["resolved_at"].isoformat()
            if alert.get("resolved_at")
            else None
        ),
        "metadata": alert.get("metadata") or {},
    }

    cur.execute(
        """
        INSERT INTO alert_outbox (
            alert_id,
            event_type,
            payload
        )
        VALUES (%s, %s, %s)
        RETURNING outbox_id
        """,
        (
            alert["alert_id"],
            event_type,
            Jsonb(payload),
        ),
    )

    return cur.fetchone()["outbox_id"]
