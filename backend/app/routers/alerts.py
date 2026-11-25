import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_db_connection


router = APIRouter(tags=["Alerts"])

VALID_SEVERITIES = ("info", "warning", "critical", "escalated")
VALID_STATUSES = ("active", "acknowledged", "resolved")


# =====================================
# AUTHENTICATION
# =====================================

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


# =====================================
# MODELS
# =====================================

class AlertCreate(BaseModel):
    device_id: str
    alert_type: str
    severity: str
    message: str
    metadata: dict = Field(default_factory=dict)


class AlertAcknowledge(BaseModel):
    acked_by: str | None = None
    acknowledged_by: str | None = None


# =====================================
# INTERNAL: CREATE ALERT
# =====================================

@router.post(
    "/api/v1/internal/alerts",
    dependencies=[Depends(verify_api_key)],
)
def create_alert(alert: AlertCreate):
    if alert.severity not in VALID_SEVERITIES:
        raise HTTPException(
            status_code=400,
            detail="Severity tidak valid",
        )

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:

                # Lock perangkat untuk mencegah request
                # bersamaan menghasilkan alert duplikat.
                cur.execute(
                    """
                    SELECT device_id
                    FROM devices
                    WHERE device_id = %s
                    FOR UPDATE
                    """,
                    (alert.device_id,),
                )

                if not cur.fetchone():
                    raise HTTPException(
                        status_code=404,
                        detail="Device tidak ditemukan",
                    )

                source = alert.metadata.get("source", "")

                cur.execute(
                    """
                    SELECT *
                    FROM alert_events
                    WHERE device_id = %s
                      AND alert_type = %s
                      AND status IN ('active', 'acknowledged')
                      AND (
                          alert_type <> 'OFFLINE'
                          OR COALESCE(metadata->>'source', '') = %s
                      )
                    ORDER BY alert_id DESC
                    LIMIT 1
                    """,
                    (
                        alert.device_id,
                        alert.alert_type,
                        source,
                    ),
                )

                existing = cur.fetchone()

                if existing:
                    return {
                        "message": "Alert sudah tersedia",
                        "created": False,
                        "data": existing,
                    }

                cur.execute(
                    """
                    INSERT INTO alert_events (
                        device_id,
                        alert_type,
                        severity,
                        message,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        alert.device_id,
                        alert.alert_type,
                        alert.severity,
                        alert.message,
                        json.dumps(alert.metadata),
                    ),
                )

                result = cur.fetchone()

            conn.commit()

        return {
            "message": "Alert berhasil disimpan",
            "created": True,
            "data": result,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =====================================
# GET ALL ALERTS
# =====================================

@router.get(
    "/api/v1/alerts",
    dependencies=[Depends(verify_api_key)],
)
def get_alerts(
    status: str | None = None,
    domain: str | None = None,
    severity: str | None = None,
    acked: bool | None = None,
    device_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
):
    if status and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Status tidak valid",
        )

    if severity and severity not in VALID_SEVERITIES:
        raise HTTPException(
            status_code=400,
            detail="Severity tidak valid",
        )

    conditions = []
    params = []

    if status:
        conditions.append("a.status = %s")
        params.append(status)

    if domain:
        conditions.append("d.domain = %s")
        params.append(domain)

    if severity:
        conditions.append("a.severity = %s")
        params.append(severity)

    if device_id:
        conditions.append("a.device_id = %s")
        params.append(device_id)

    if acked is True:
        conditions.append("a.acknowledged_at IS NOT NULL")

    elif acked is False:
        conditions.append("a.acknowledged_at IS NULL")

    query = """
        SELECT a.*, d.domain
        FROM alert_events a
        JOIN devices d
          ON a.device_id = d.device_id
    """

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY a.triggered_at DESC LIMIT %s"
    params.append(limit)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                alerts = cur.fetchall()

        return {
            "count": len(alerts),
            "data": alerts,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =====================================
# GET ALERT DETAIL
# =====================================

@router.get(
    "/api/v1/alerts/{alert_id}",
    dependencies=[Depends(verify_api_key)],
)
def get_alert(alert_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.*, d.domain
                    FROM alert_events a
                    JOIN devices d
                      ON a.device_id = d.device_id
                    WHERE a.alert_id = %s
                    """,
                    (alert_id,),
                )

                alert = cur.fetchone()

        if not alert:
            raise HTTPException(
                status_code=404,
                detail="Alert tidak ditemukan",
            )

        return alert

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =====================================
# ACKNOWLEDGE ALERT
# =====================================

@router.post(
    "/api/v1/alerts/{alert_id}/ack",
    dependencies=[Depends(verify_api_key)],
)
def acknowledge_alert(
    alert_id: int,
    body: AlertAcknowledge | None = None,
):
    operator = "operator"

    if body:
        operator = (
            body.acked_by
            or body.acknowledged_by
            or "operator"
        ).strip()

    if not operator or len(operator) > 100:
        raise HTTPException(
            status_code=400,
            detail="Nama operator tidak valid",
        )

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT *
                    FROM alert_events
                    WHERE alert_id = %s
                    FOR UPDATE
                    """,
                    (alert_id,),
                )

                existing = cur.fetchone()

                if not existing:
                    raise HTTPException(
                        status_code=404,
                        detail="Alert tidak ditemukan",
                    )

                if existing["acknowledged_at"] is not None:
                    return {
                        "message": "Alert sudah di-acknowledge",
                        "data": existing,
                    }

                if existing["status"] == "resolved":
                    raise HTTPException(
                        status_code=409,
                        detail="Alert sudah resolved",
                    )

                cur.execute(
                    """
                    UPDATE alert_events
                    SET status = 'acknowledged',
                        acknowledged_at = NOW(),
                        acknowledged_by = %s
                    WHERE alert_id = %s
                    RETURNING *
                    """,
                    (operator, alert_id),
                )

                alert = cur.fetchone()

            conn.commit()

        return {
            "message": "Alert berhasil di-acknowledge",
            "data": alert,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =====================================
# INTERNAL: AUTO ESCALATION
# =====================================

@router.post(
    "/api/v1/internal/alerts/escalate",
    dependencies=[Depends(verify_api_key)],
)
def escalate_alerts():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:

                # Mencegah pemeriksaan eskalasi paralel.
                cur.execute(
                    "SELECT pg_advisory_xact_lock(20261125)"
                )

                # Lock alert yang memenuhi syarat.
                cur.execute(
                    """
                    SELECT alert_id
                    FROM alert_events
                    WHERE status = 'active'
                      AND alert_type = 'TEMP_HIGH'
                      AND acknowledged_at IS NULL
                      AND triggered_at <=
                          NOW() - INTERVAL '5 minutes'
                    FOR UPDATE
                    """
                )

                cur.fetchall()

                cur.execute(
                    """
                    INSERT INTO alert_events (
                        device_id,
                        alert_type,
                        severity,
                        message,
                        metadata
                    )
                    SELECT
                        a.device_id,
                        'TEMP_ESCALATED',
                        'escalated',
                        'Alert belum di-acknowledge selama 5 menit',
                        jsonb_build_object(
                            'original_alert_id', a.alert_id,
                            'original_alert_type', a.alert_type,
                            'duration_seconds', 300
                        )
                    FROM alert_events a
                    WHERE a.status = 'active'
                      AND a.alert_type = 'TEMP_HIGH'
                      AND a.acknowledged_at IS NULL
                      AND a.triggered_at <=
                          NOW() - INTERVAL '5 minutes'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM alert_events e
                          WHERE e.alert_type = 'TEMP_ESCALATED'
                            AND e.metadata->>'original_alert_id'
                                = a.alert_id::text
                      )
                    RETURNING *
                    """
                )

                escalations = cur.fetchall()

            conn.commit()

        return {
            "message": "Pemeriksaan eskalasi selesai",
            "count": len(escalations),
            "data": escalations,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =====================================
# RESOLVE SINGLE ALERT
# =====================================

@router.post(
    "/api/v1/alerts/{alert_id}/resolve",
    dependencies=[Depends(verify_api_key)],
)
def resolve_alert(alert_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE alert_events
                    SET status = 'resolved',
                        resolved_at = NOW()
                    WHERE alert_id = %s
                      AND status IN ('active', 'acknowledged')
                    RETURNING *
                    """,
                    (alert_id,),
                )

                alert = cur.fetchone()

            conn.commit()

        if not alert:
            raise HTTPException(
                status_code=404,
                detail="Alert tidak ditemukan atau sudah resolved",
            )

        return {
            "message": "Alert berhasil di-resolve",
            "data": alert,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =====================================
# INTERNAL: RESOLVE TEMPERATURE ALERTS
# =====================================

@router.post(
    "/api/v1/internal/alerts/resolve-device/{device_id}",
    dependencies=[Depends(verify_api_key)],
)
def resolve_device_alerts(device_id: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE alert_events
                    SET status = 'resolved',
                        resolved_at = NOW()
                    WHERE device_id = %s
                      AND alert_type IN (
                          'TEMP_WARN',
                          'TEMP_HIGH',
                          'TEMP_ESCALATED'
                      )
                      AND status IN ('active', 'acknowledged')
                    RETURNING *
                    """,
                    (device_id,),
                )

                alerts = cur.fetchall()

            conn.commit()

        return {
            "message": "Alert suhu berhasil di-resolve",
            "device_id": device_id,
            "count": len(alerts),
            "data": alerts,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =====================================
# INTERNAL: RESOLVE ALERT BY TYPE
# =====================================

@router.post(
    "/api/v1/internal/alerts/resolve-type/{device_id}/{alert_type}",
    dependencies=[Depends(verify_api_key)],
)
def resolve_alert_by_type(
    device_id: str,
    alert_type: str,
    source: str | None = None,
):
    if alert_type == "OFFLINE" and not source:
        raise HTTPException(
            status_code=400,
            detail="Source diperlukan untuk recovery OFFLINE",
        )

    query = """
        UPDATE alert_events
        SET status = 'resolved',
            resolved_at = NOW()
        WHERE device_id = %s
          AND alert_type = %s
          AND status IN ('active', 'acknowledged')
    """

    params = [device_id, alert_type]

    if source is not None:
        query += " AND metadata->>'source' = %s"
        params.append(source)

    query += " RETURNING *"

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                alerts = cur.fetchall()

            conn.commit()

        return {
            "message": "Recovery alert selesai",
            "device_id": device_id,
            "alert_type": alert_type,
            "count": len(alerts),
            "data": alerts,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )