import logging
import re
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.database import get_db_connection
from app.influx import query_influx
from app.mqtt import publish_command


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/v1/coldchain",
    tags=["Cold-Chain"],
)


# =========================
# API KEY AUTHENTICATION
# =========================

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


# =========================
# HELPER: LATEST TELEMETRY
# =========================

def get_latest_telemetry(device_id: str = None):
    device_filter = ""

    if device_id:
        if not all(c.isalnum() or c in "-_" for c in device_id):
            raise HTTPException(
                status_code=400,
                detail="Device ID tidak valid",
            )

        device_filter = f'''
            |> filter(fn: (r) => r.device_id == "{device_id}")
        '''

    flux_query = f'''
        from(bucket: "{settings.INFLUXDB_BUCKET}")
            |> range(start: -24h)
            |> filter(fn: (r) =>
                r._measurement == "telemetry"
            )
            |> filter(fn: (r) =>
                r.domain == "coldchain"
            )
            |> filter(fn: (r) =>
                r._field == "temp_c" or
                r._field == "humidity_pct" or
                r._field == "door_open" or
                r._field == "battery_pct" or
                r._field == "rssi_dbm" or
                r._field == "setpoint_c"
            )
            {device_filter}
            |> pivot(
                rowKey: ["_time"],
                columnKey: ["_field"],
                valueColumn: "_value"
            )
            |> group(columns: ["device_id"])
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: 1)
    '''

    records = query_influx(flux_query)

    telemetry = {}

    for record in records:
        device = record.get("device_id")

        if device:
            telemetry[device] = {
                "timestamp": record.get("_time"),
                "temp_c": record.get("temp_c"),
                "humidity_pct": record.get("humidity_pct"),
                "door_open": record.get("door_open"),
                "battery_pct": record.get("battery_pct"),
                "rssi_dbm": record.get("rssi_dbm"),
                "setpoint_c": record.get("setpoint_c"),
            }

    return telemetry


# =========================
# GET ALL CHAMBERS
# =========================

@router.get(
    "/chambers",
    dependencies=[Depends(verify_api_key)],
)
def get_chambers():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT device_id, domain, gedung, ruang,
                           status, last_seen
                    FROM devices
                    WHERE domain = 'coldchain'
                    ORDER BY device_id
                """)

                devices = cur.fetchall()

        telemetry = get_latest_telemetry()

        chambers = []

        for device in devices:
            device_data = dict(device)
            device_id = device_data["device_id"]

            device_data["telemetry"] = telemetry.get(device_id)

            chambers.append(device_data)

        return {
            "count": len(chambers),
            "data": chambers,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# GET CHAMBER DETAIL
# =========================

@router.get(
    "/chambers/{device_id}",
    dependencies=[Depends(verify_api_key)],
)
def get_chamber(device_id: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT device_id, domain, gedung, ruang,
                           status, last_seen
                    FROM devices
                    WHERE device_id = %s
                      AND domain = 'coldchain'
                    """,
                    (device_id,),
                )

                device = cur.fetchone()

                if not device:
                    raise HTTPException(
                        status_code=404,
                        detail="Chamber tidak ditemukan",
                    )

        device_data = dict(device)
        telemetry = get_latest_telemetry(device_id)

        device_data["telemetry"] = telemetry.get(device_id)

        return device_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# GET COLD-CHAIN ESCALATIONS
# =========================

@router.get(
    "/escalations",
    dependencies=[Depends(verify_api_key)],
)
def get_escalations():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        a.alert_id,
                        a.device_id,
                        a.alert_type,
                        a.severity,
                        a.message,
                        a.status,
                        a.triggered_at,
                        a.acknowledged_at,
                        a.acknowledged_by,
                        a.resolved_at,
                        a.metadata
                    FROM alert_events a
                    JOIN devices d
                        ON a.device_id = d.device_id
                    WHERE d.domain = 'coldchain'
                      AND a.alert_type = 'TEMP_ESCALATED'
                    ORDER BY a.triggered_at DESC
                """)

                alerts = cur.fetchall()

                return {
                    "count": len(alerts),
                    "data": alerts,
                }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# SETPOINT COMMAND MODELS
# =========================

class SetpointArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temp_c: float = Field(
        ...,
        strict=True,
        ge=0,
        le=10,
        allow_inf_nan=False,
    )


class SetpointCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal["setpoint"]
    args: SetpointArgs


# =========================
# POST SETPOINT COMMAND
# =========================

@router.post(
    "/cmd/{device_id}",
    dependencies=[Depends(verify_api_key)],
)
def send_setpoint_command(
    device_id: str,
    request: SetpointCommand,
):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", device_id):
        raise HTTPException(
            status_code=422,
            detail="Device ID tidak valid",
        )

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT device_id, domain, gedung, ruang, status
                    FROM devices
                    WHERE device_id = %s
                      AND domain = 'coldchain'
                    """,
                    (device_id,),
                )

                device = cur.fetchone()

    except Exception:
        logger.exception("Failed to query chamber registry")
        raise HTTPException(
            status_code=500,
            detail="Gagal mengakses registry device",
        )

    if not device:
        raise HTTPException(
            status_code=404,
            detail="Chamber tidak ditemukan",
        )

    if device["status"] != "online":
        raise HTTPException(
            status_code=409,
            detail="Chamber sedang offline",
        )

    segments = [
        device["domain"],
        device["gedung"],
        device["ruang"],
        device["device_id"],
    ]

    if not all(
        isinstance(segment, str)
        and re.fullmatch(r"[A-Za-z0-9_-]+", segment)
        for segment in segments
    ):
        raise HTTPException(
            status_code=500,
            detail="Registry MQTT topic tidak valid",
        )

    topic = "kampus/" + "/".join(segments) + "/cmd"

    payload = {
        "command": "setpoint",
        "args": {
            "temp_c": request.args.temp_c,
        },
    }

    try:
        publish_command(topic, payload)

    except Exception as error:
        logger.warning(
            "MQTT command failed for %s: %s",
            device_id,
            type(error).__name__,
        )

        raise HTTPException(
            status_code=503,
            detail="Gagal mengirim command ke MQTT broker",
        )

    return {
        "message": "Setpoint command berhasil dipublish",
        "device_id": device_id,
        "topic": topic,
        "command": payload["command"],
        "args": payload["args"],
        "status": "published",
    }
