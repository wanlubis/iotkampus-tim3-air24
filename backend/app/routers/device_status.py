from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database import get_db_connection
from app.outbox import enqueue_alert_event


router = APIRouter(
    prefix="/api/v1/internal",
    tags=["Device Status"],
)


# ==========================================
# API KEY AUTHENTICATION
# ==========================================

def verify_api_key(x_api_key: str = Header(default="")):
    if not settings.API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY belum dikonfigurasi",
        )

    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=401,
            detail="API Key tidak valid",
        )


# ==========================================
# REQUEST MODEL
# ==========================================

class DeviceStatus(BaseModel):
    device_id: str
    status: str
    ts: int | None = None


# ==========================================
# UPDATE DEVICE STATUS
# ==========================================

@router.post(
    "/device-status",
    dependencies=[Depends(verify_api_key)],
)
def update_device_status(payload: DeviceStatus):

    if payload.status not in ("online", "offline"):
        raise HTTPException(
            status_code=400,
            detail="Status harus online atau offline",
        )

    try:
        event_time = (
            datetime.fromtimestamp(
                payload.ts / 1000,
                tz=timezone.utc,
            )
            if payload.ts is not None
            else datetime.now(timezone.utc)
        )

    except (ValueError, OverflowError, OSError):
        raise HTTPException(
            status_code=400,
            detail="Timestamp tidak valid",
        )

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:

                # ==============================
                # UPDATE STATUS PERANGKAT
                # ==============================

                cur.execute(
                    """
                    UPDATE devices
                    SET status = %s,
                        last_seen = CASE
                            WHEN %s = 'online'
                            THEN GREATEST(last_seen, %s)
                            ELSE last_seen
                        END,
                        updated_at = NOW()
                    WHERE device_id = %s
                      AND domain = 'coldchain'
                    RETURNING device_id, status, last_seen
                    """,
                    (
                        payload.status,
                        payload.status,
                        event_time,
                        payload.device_id,
                    ),
                )

                device = cur.fetchone()

                if not device:
                    raise HTTPException(
                        status_code=404,
                        detail="Device tidak ditemukan",
                    )

                alert_created = False
                alerts_resolved = 0

                # ==============================
                # CREATE OFFLINE ALERT (LWT)
                # ==============================

                if payload.status == "offline":

                    cur.execute(
                        """
                        INSERT INTO alert_events (
                            device_id,
                            alert_type,
                            severity,
                            message,
                            status,
                            metadata
                        )
                        SELECT
                            %s,
                            'OFFLINE',
                            'critical',
                            %s,
                            'active',
                            jsonb_build_object(
                                'source', 'device_status',
                                'device_status', 'offline',
                                'reason', 'mqtt_offline'
                            )
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM alert_events
                            WHERE device_id = %s
                              AND alert_type = 'OFFLINE'
                              AND metadata->>'source'
                                  = 'device_status'
                              AND status IN (
                                  'active',
                                  'acknowledged'
                              )
                        )
                        RETURNING *
                        """,
                        (
                            payload.device_id,
                            f"Perangkat {payload.device_id} offline",
                            payload.device_id,
                        ),
                    )

                    alert = cur.fetchone()
                    alert_created = alert is not None

                    if alert:
                        enqueue_alert_event(
                            cur,
                            alert,
                            "CREATED",
                        )

                # ==============================
                # AUTOMATIC LWT RECOVERY
                # ==============================

                elif payload.status == "online":

                    cur.execute(
                        """
                        UPDATE alert_events
                        SET status = 'resolved',
                            resolved_at = NOW()
                        WHERE device_id = %s
                          AND alert_type = 'OFFLINE'
                          AND metadata->>'source'
                              = 'device_status'
                          AND status IN (
                              'active',
                              'acknowledged'
                          )
                        RETURNING *
                        """,
                        (payload.device_id,),
                    )

                    alerts = cur.fetchall()
                    alerts_resolved = len(alerts)

                    for alert in alerts:
                        enqueue_alert_event(
                            cur,
                            alert,
                            "RESOLVED",
                        )

                conn.commit()

                return {
                    "message": "Status perangkat berhasil diperbarui",
                    "data": device,
                    "alert_created": alert_created,
                    "alerts_resolved": alerts_resolved,
                }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )