import os
from typing import Optional
from fastapi import APIRouter, Depends, Path, Body
from pydantic import BaseModel, Field
from app.auth import verify_api_key, AppException
from app.database import get_pg_connection, get_influx_client, now_wib_iso, WIB

router = APIRouter(
    prefix="/api/v1/coldchain",
    dependencies=[Depends(verify_api_key)],
    tags=["Cold-Chain / Smart Storage (Tim 2)"]
)

class CmdRequest(BaseModel):
    command: str = "setpoint"
    args: dict = Field(default_factory=lambda: {"temp_c": 3.5})

# In-memory store for setpoint updates (or could be published to MQTT)
CHAMBER_SETPOINTS = {
    "cc-01": 4.0,
    "cc-02": 3.5,
    "cc-03": -18.0
}

@router.get("/chambers")
def get_chambers():
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT device_id, display_name, gedung, ruang FROM devices WHERE domain = 'coldchain' AND is_active = TRUE ORDER BY device_id ASC")
        devices = cur.fetchall()
    finally:
        conn.close()

    chambers_res = []
    for d in devices:
        dev_id = d["device_id"]
        chambers_res.append({
            "device_id": dev_id,
            "display_name": d["display_name"],
            "gedung": d["gedung"],
            "ruang": d["ruang"],
            "status": "online",
            "temp_c": 3.8 if dev_id == "cc-01" else (4.2 if dev_id == "cc-02" else -18.5),
            "humidity_pct": 75.0,
            "door_open": False,
            "setpoint_c": CHAMBER_SETPOINTS.get(dev_id, 4.0),
            "checked_at": now_wib_iso()
        })
    return chambers_res

@router.get("/chambers/{device_id}")
def get_chamber_detail(device_id: str = Path(...)):
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM devices WHERE domain = 'coldchain' AND device_id = %s", (device_id,))
        dev = cur.fetchone()
        if not dev:
            raise AppException(404, "NOT_FOUND", f"Chamber '{device_id}' tidak ditemukan")
    finally:
        conn.close()

    return {
        "device_id": device_id,
        "display_name": dev["display_name"],
        "gedung": dev["gedung"],
        "ruang": dev["ruang"],
        "temp_c": 3.8,
        "humidity_pct": 75.0,
        "door_open": False,
        "battery_pct": 92,
        "rssi_dbm": -65,
        "setpoint_c": CHAMBER_SETPOINTS.get(device_id, 4.0),
        "last_updated": now_wib_iso()
    }

@router.get("/escalations")
def get_coldchain_escalations():
    conn = get_pg_connection()
    if not conn:
        return []
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM alert_events WHERE domain = 'coldchain' AND severity = 'escalated' ORDER BY ts_raised DESC LIMIT 20")
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@router.post("/cmd/{device_id}")
def post_coldchain_cmd(device_id: str = Path(...), body: CmdRequest = Body(...)):
    if body.command == "setpoint":
        temp_val = body.args.get("temp_c")
        if temp_val is None or not (-30.0 <= float(temp_val) <= 20.0):
            raise AppException(422, "VALIDATION_ERROR", "Nilai setpoint temp_c di luar rentang yang diizinkan (-30 s.d 20 °C)")
        CHAMBER_SETPOINTS[device_id] = float(temp_val)
        return {
            "device_id": device_id,
            "command": "setpoint",
            "status": "dispatched",
            "applied_setpoint_c": float(temp_val),
            "dispatched_at": now_wib_iso()
        }
    return {
        "device_id": device_id,
        "command": body.command,
        "status": "acknowledged",
        "timestamp": now_wib_iso()
    }
