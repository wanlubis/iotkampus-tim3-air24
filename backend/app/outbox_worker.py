import logging
import math
import threading
from datetime import datetime

from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from app.config import settings
from app.database import get_db_connection
from app.influx import get_influx_client


logger = logging.getLogger(__name__)

POLL_INTERVAL = 2
MAX_RETRY_DELAY = 300


def claim_event():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH candidate AS (
                    SELECT outbox_id
                    FROM alert_outbox
                    WHERE (
                        status = 'pending'
                        AND next_attempt_at <= NOW()
                    )
                    OR (
                        status = 'processing'
                        AND locked_until <= NOW()
                    )
                    ORDER BY outbox_id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE alert_outbox AS o
                SET status = 'processing',
                    attempts = o.attempts + 1,
                    locked_until = NOW() + INTERVAL '120 seconds'
                FROM candidate AS c
                WHERE o.outbox_id = c.outbox_id
                RETURNING o.*
                """
            )

            event = cur.fetchone()

        conn.commit()

    return event


def get_device_domain(device_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain
                FROM devices
                WHERE device_id = %s
                """,
                (device_id,),
            )

            device = cur.fetchone()

    if not device:
        raise ValueError("Device tidak ditemukan")

    return device["domain"]


def write_event(event):
    payload = event["payload"]
    event_type = event["event_type"]
    metadata = payload.get("metadata") or {}

    domain = payload.get("domain")

    if not domain:
        domain = get_device_domain(
            payload["device_id"]
        )

    timestamp_fields = {
        "CREATED": "triggered_at",
        "ACKNOWLEDGED": "acknowledged_at",
        "RESOLVED": "resolved_at",
    }

    timestamp = datetime.fromisoformat(
        payload[timestamp_fields[event_type]]
    )

    measurement = (
        "alerts"
        if event_type == "CREATED"
        else "alert_lifecycle"
    )

    point = (
        Point(measurement)
        .tag("domain", domain)
        .tag("device_id", payload["device_id"])
        .tag("code", payload["alert_type"])
        .tag("severity", payload["severity"])
        .tag("alert_id", str(payload["alert_id"]))
        .tag("event_type", event_type)
        .field("message", payload.get("message") or "")
        .field("status", payload["status"])
        .field("outbox_id", event["outbox_id"])
        .time(timestamp, WritePrecision.NS)
    )

    code = payload["alert_type"]
    value = None

    if code.startswith("TEMP_"):
        value = metadata.get("temp_c")

    elif code == "DOOR_OPEN_LONG":
        value = 1.0

    elif code == "OFFLINE":
        value = 0.0

    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    ):
        point.field("value", float(value))

    if payload.get("acknowledged_by"):
        point.field(
            "acked_by",
            payload["acknowledged_by"],
        )

    with get_influx_client() as client:
        with client.write_api(
            write_options=SYNCHRONOUS
        ) as write_api:
            write_api.write(
                bucket=settings.INFLUXDB_BUCKET,
                org=settings.INFLUXDB_ORG,
                record=point,
            )


def mark_synced(event):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alert_outbox
                SET status = 'synced',
                    synced_at = NOW(),
                    locked_until = NULL,
                    last_error = NULL
                WHERE outbox_id = %s
                  AND attempts = %s
                  AND status = 'processing'
                """,
                (
                    event["outbox_id"],
                    event["attempts"],
                ),
            )

            updated = cur.rowcount == 1

        conn.commit()

    return updated


def mark_retry(event, error):
    delay = min(
        2 ** min(event["attempts"], 9),
        MAX_RETRY_DELAY,
    )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alert_outbox
                SET status = 'pending',
                    next_attempt_at =
                        NOW() + (%s * INTERVAL '1 second'),
                    locked_until = NULL,
                    last_error = %s
                WHERE outbox_id = %s
                  AND attempts = %s
                  AND status = 'processing'
                """,
                (
                    delay,
                    type(error).__name__,
                    event["outbox_id"],
                    event["attempts"],
                ),
            )

            updated = cur.rowcount == 1

        conn.commit()

    return updated


def process_one_event():
    event = claim_event()

    if event is None:
        return False

    try:
        write_event(event)

        if mark_synced(event):
            logger.info(
                "Outbox synced: %s",
                event["outbox_id"],
            )
        else:
            logger.warning(
                "Outbox ownership lost before sync update: %s",
                event["outbox_id"],
            )

    except Exception as error:
        if mark_retry(event, error):
            logger.warning(
                "Outbox retry: %s (%s)",
                event["outbox_id"],
                type(error).__name__,
            )
        else:
            logger.warning(
                "Outbox ownership lost before retry update: %s",
                event["outbox_id"],
            )

    return True


def run_outbox_worker(stop_event: threading.Event):
    logger.info("Outbox worker started")

    while not stop_event.is_set():
        try:
            processed = process_one_event()

            if not processed:
                stop_event.wait(POLL_INTERVAL)

        except Exception as error:
            logger.error(
                "Outbox worker error: %s",
                type(error).__name__,
            )

            stop_event.wait(POLL_INTERVAL)

    logger.info("Outbox worker stopped")
