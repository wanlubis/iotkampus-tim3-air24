import os
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Path, Body
from pydantic import BaseModel, Field
from app.auth import verify_api_key, AppException
from app.database import get_pg_connection, get_influx_client, now_wib_iso, WIB

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/coldchain",
    dependencies=[Depends(verify_api_key)],
    tags=["Cold-Chain / Smart Storage (Tim 2)"]
)

class CmdArgs(BaseModel):
    temp_c: Optional[float] = Field(None, description="Nilai setpoint suhu baru (0.0 - 10.0 °C)")

class CmdRequest(BaseModel):
    command: str = Field("setpoint", description="Perintah turun, contoh: setpoint")
    args: dict = Field(default_factory=lambda: {"temp_c": 3.5})

# Fallback setpoints bila belum ada data telemetri
DEFAULT_SETPOINTS = {
    "cc-01": 4.5,
    "cc-02": 3.8,
    "cc-03": 5.2
}

def publish_mqtt_command(topic: str, payload: dict) -> bool:
    """Helper untuk publish command downlink ke broker Mosquitto."""
    try:
        import paho.mqtt.client as mqtt
        broker_host = os.getenv("MQTT_HOST", "mosquitto")
        broker_port = int(os.getenv("MQTT_PORT", "1883"))
        username = os.getenv("MQTT_USERNAME", "air24_user")
        password = os.getenv("MQTT_PASSWORD", "0")

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="air24-api-cmd-publisher"
        )
        if username:
            client.username_pw_set(username, password)

        client.connect(broker_host, broker_port, keepalive=10)
        client.publish(topic, json.dumps(payload), qos=1, retain=False)
        client.disconnect()
        return True
    except Exception as e:
        logger.error(f"[MQTT Cmd Error] Gagal mem-publish ke {topic}: {e}")
        return False

@router.get("/chambers")
def get_chambers():
    """
    Daftar chamber + suhu/pintu/status terakhir (Bagian 6.5).
    """
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT device_id, display_name, gedung, ruang 
            FROM devices 
            WHERE domain = 'coldchain' AND is_active = TRUE 
            ORDER BY device_id ASC
        """)
        devices = cur.fetchall()
    finally:
        conn.close()

    # Query latest telemetry & status from InfluxDB
    influx = get_influx_client()
    latest_metrics = {}
    online_map = {}

    if influx:
        bucket = os.getenv("INFLUXDB_BUCKET", "iot")
        try:
            # Query status
            q_status = f'''
            from(bucket: "{bucket}")
              |> range(start: -5m)
              |> filter(fn: (r) => r["_measurement"] == "status" and r["domain"] == "coldchain")
              |> last()
            '''
            t_status = influx.query_api().query(q_status)
            for t in t_status:
                for rec in t.records:
                    dev = rec.values.get("device_id")
                    val = rec.get_value()
                    online_map[dev] = "online" if (val == 1 or str(val).lower() == "online") else "offline"

            # Query telemetry
            q_telem = f'''
            from(bucket: "{bucket}")
              |> range(start: -30m)
              |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["domain"] == "coldchain")
              |> last()
            '''
            t_telem = influx.query_api().query(q_telem)
            for t in t_telem:
                for rec in t.records:
                    dev = rec.values.get("device_id")
                    if dev not in latest_metrics:
                        latest_metrics[dev] = {
                            "last_updated": rec.get_time().astimezone(WIB).isoformat(),
                            "metrics": {}
                        }
                    latest_metrics[dev]["metrics"][rec.get_field()] = rec.get_value()
        except Exception as e:
            logger.error(f"[Coldchain Influx Error] {e}")

    chambers_res = []
    for d in devices:
        dev_id = d["device_id"]
        meta = latest_metrics.get(dev_id, {"metrics": {}, "last_updated": None})
        m = meta["metrics"]

        # Default fallback values jika simulator belum aktif
        default_base = DEFAULT_SETPOINTS.get(dev_id, 4.0)
        temp_val = m.get("temp_c", default_base)
        humidity_val = m.get("humidity_pct", 65.0)
        door_open_val = bool(m.get("door_open", False))
        battery_val = m.get("battery_pct", 95)
        rssi_val = m.get("rssi_dbm", -62)
        setpoint_val = m.get("setpoint_c", default_base)

        chambers_res.append({
            "device_id": dev_id,
            "display_name": d["display_name"],
            "gedung": d["gedung"],
            "ruang": d["ruang"],
            "status": online_map.get(dev_id, "offline" if not m else "online"),
            "temp_c": round(float(temp_val), 2),
            "humidity_pct": round(float(humidity_val), 1),
            "door_open": door_open_val,
            "battery_pct": int(battery_val),
            "rssi_dbm": int(rssi_val),
            "setpoint_c": round(float(setpoint_val), 2),
            "last_updated": meta.get("last_updated") or now_wib_iso()
        })

    return chambers_res

@router.get("/chambers/{device_id}")
def get_chamber_detail(device_id: str = Path(...)):
    """
    Detail satu chamber, termasuk setpoint terakhir jika ada (Bagian 6.5).
    """
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

    # Query latest telemetry & status from InfluxDB
    influx = get_influx_client()
    metrics = {}
    status_val = "offline"
    last_updated = None

    if influx:
        bucket = os.getenv("INFLUXDB_BUCKET", "iot")
        try:
            q_status = f'''
            from(bucket: "{bucket}")
              |> range(start: -5m)
              |> filter(fn: (r) => r["_measurement"] == "status" and r["device_id"] == "{device_id}")
              |> last()
            '''
            for t in influx.query_api().query(q_status):
                for rec in t.records:
                    val = rec.get_value()
                    status_val = "online" if (val == 1 or str(val).lower() == "online") else "offline"

            q_telem = f'''
            from(bucket: "{bucket}")
              |> range(start: -30m)
              |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["device_id"] == "{device_id}")
              |> last()
            '''
            for t in influx.query_api().query(q_telem):
                for rec in t.records:
                    metrics[rec.get_field()] = rec.get_value()
                    last_updated = rec.get_time().astimezone(WIB).isoformat()
        except Exception as e:
            logger.error(f"[Coldchain Detail Influx Error] {e}")

    default_base = DEFAULT_SETPOINTS.get(device_id, 4.0)
    return {
        "device_id": device_id,
        "display_name": dev["display_name"],
        "gedung": dev["gedung"],
        "ruang": dev["ruang"],
        "status": status_val,
        "temp_c": round(float(metrics.get("temp_c", default_base)), 2),
        "humidity_pct": round(float(metrics.get("humidity_pct", 65.0)), 1),
        "door_open": bool(metrics.get("door_open", False)),
        "battery_pct": int(metrics.get("battery_pct", 95)),
        "rssi_dbm": int(metrics.get("rssi_dbm", -62)),
        "setpoint_c": round(float(metrics.get("setpoint_c", default_base)), 2),
        "last_updated": last_updated or now_wib_iso()
    }

@router.get("/escalations")
def get_coldchain_escalations():
    """
    Alert yang sedang dalam rantai eskalasi (Bagian 6.5).
    """
    conn = get_pg_connection()
    if not conn:
        return []
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, device_id, domain, code, severity, message, value, ts_raised, ts_acked, acked_by, context 
            FROM alert_events 
            WHERE domain = 'coldchain' AND severity = 'escalated' 
            ORDER BY ts_raised DESC 
            LIMIT 20
        """)
        rows = cur.fetchall()
        result = []
        for r in rows:
            item = dict(r)
            if item.get("ts_raised"):
                item["ts_raised"] = item["ts_raised"].astimezone(WIB).isoformat()
            if item.get("ts_acked"):
                item["ts_acked"] = item["ts_acked"].astimezone(WIB).isoformat()
            result.append(item)
        return result
    finally:
        conn.close()

@router.post("/cmd/{device_id}")
def post_coldchain_cmd(device_id: str = Path(...), body: CmdRequest = Body(...)):
    """
    Perintah turun minimal {"command":"setpoint","args":{"temp_c":3.5}}.
    Validasi rentang 0-10 °C, lalu publish ke channel cmd (Bagian 6.5).
    """
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM devices WHERE domain = 'coldchain' AND device_id = %s", (device_id,))
        chamber = cur.fetchone()
        if not chamber:
            raise AppException(404, "NOT_FOUND", f"Chamber '{device_id}' tidak ditemukan di registry")
    finally:
        conn.close()

    topic = f"kampus/coldchain/{chamber['gedung']}/{chamber['ruang']}/{device_id}/cmd"

    if body.command == "setpoint":
        temp_val = body.args.get("temp_c")
        if temp_val is None:
            raise AppException(422, "VALIDATION_ERROR", "Field args.temp_c wajib disertakan")
        try:
            temp_num = float(temp_val)
        except (ValueError, TypeError):
            raise AppException(422, "VALIDATION_ERROR", "Field args.temp_c harus berupa angka")

        # Validasi rentang 0-10 °C sesuai panduan Bagian 6.5 & simulator
        if not (0.0 <= temp_num <= 10.0):
            raise AppException(422, "VALIDATION_ERROR", f"Nilai setpoint temp_c ({temp_num} °C) di luar rentang yang diizinkan (0 s.d 10 °C)")

        payload = {
            "command": "setpoint",
            "args": {
                "temp_c": temp_num
            }
        }

        published = publish_mqtt_command(topic, payload)

        return {
            "device_id": device_id,
            "command": "setpoint",
            "topic": topic,
            "status": "published" if published else "queued",
            "applied_setpoint_c": temp_num,
            "dispatched_at": now_wib_iso()
        }

    # Perintah lain (misal force-close door, reset)
    published = publish_mqtt_command(topic, body.dict())
    return {
        "device_id": device_id,
        "command": body.command,
        "topic": topic,
        "status": "published" if published else "queued",
        "dispatched_at": now_wib_iso()
    }
