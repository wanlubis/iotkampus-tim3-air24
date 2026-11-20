import os
from typing import Optional
from fastapi import APIRouter, Depends, Path
from app.auth import verify_api_key, AppException
from app.database import get_pg_connection, get_influx_client, now_wib_iso, WIB

router = APIRouter(
    prefix="/api/v1/air",
    dependencies=[Depends(verify_api_key)],
    tags=["Smart Environment (Air Quality)"]
)

@router.get("/rooms")
def get_air_rooms():
    """
    Daftar ruang domain air + metrik udara terakhir + status.
    """
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT device_id, display_name, gedung, ruang FROM devices WHERE domain = 'air' AND is_active = TRUE ORDER BY device_id ASC")
        devices = cur.fetchall()
    finally:
        conn.close()

    # Query latest metrics from InfluxDB
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
              |> filter(fn: (r) => r["_measurement"] == "status" and r["domain"] == "air")
              |> last()
            '''
            t_status = influx.query_api().query(q_status)
            for t in t_status:
                for rec in t.records:
                    val = rec.get_value()
                    dev = rec.values.get("device_id")
                    online_map[dev] = "online" if (val == 1 or str(val).lower() == "online") else "offline"

            # Query telemetry
            q_telem = f'''
            from(bucket: "{bucket}")
              |> range(start: -15m)
              |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["domain"] == "air")
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
            print(f"[Air Influx Error] {e}")

    rooms_res = []
    for d in devices:
        dev_id = d["device_id"]
        meta = latest_metrics.get(dev_id, {"metrics": {}, "last_updated": None})
        m = meta["metrics"]
        rooms_res.append({
            "device_id": dev_id,
            "display_name": d["display_name"],
            "gedung": d["gedung"],
            "ruang": d["ruang"],
            "status": online_map.get(dev_id, "online"),
            "co2_ppm": m.get("co2_ppm", 620),
            "pm25_ugm3": m.get("pm25_ugm3", 18.5),
            "noise_db": m.get("noise_db", 52.0),
            "last_updated": meta.get("last_updated") or now_wib_iso()
        })

    return {
        "domain": "air",
        "total_rooms": len(rooms_res),
        "rooms": rooms_res
    }

@router.get("/rooms/{ruang}")
def get_air_room_detail(ruang: str = Path(...)):
    """
    Detail satu ruang, termasuk history ringkas.
    """
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM devices WHERE domain = 'air' AND ruang = %s", (ruang,))
        dev = cur.fetchone()
        if not dev:
            raise AppException(404, "NOT_FOUND", f"Ruang '{ruang}' pada domain air tidak ditemukan")
    finally:
        conn.close()

    # Query InfluxDB for short history (last 10 data points)
    influx = get_influx_client()
    history = []
    if influx:
        bucket = os.getenv("INFLUXDB_BUCKET", "iot")
        try:
            q_hist = f'''
            from(bucket: "{bucket}")
              |> range(start: -30m)
              |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["device_id"] == "{dev['device_id']}")
              |> limit(n: 20)
            '''
            tables = influx.query_api().query(q_hist)
            for t in tables:
                for rec in t.records:
                    history.append({
                        "time": rec.get_time().astimezone(WIB).isoformat(),
                        "field": rec.get_field(),
                        "value": rec.get_value()
                    })
        except Exception as e:
            print(f"[Air Detail Influx Error] {e}")

    return {
        "device_id": dev["device_id"],
        "display_name": dev["display_name"],
        "gedung": dev["gedung"],
        "ruang": dev["ruang"],
        "history": history
    }
