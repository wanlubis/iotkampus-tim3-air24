import os
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from app.auth import verify_api_key, AppException
from app.database import get_pg_connection, get_influx_client, now_wib_iso, WIB

router = APIRouter(
    prefix="/api/v1/energy",
    dependencies=[Depends(verify_api_key)],
    tags=["Smart Energy (Tim 1)"]
)

TARIF_ASUMSI_PER_KWH = 1500  # Rp 1.500 / kWh (Asumsi terbuka sesuai spec)

@router.get("/rooms")
def get_energy_rooms():
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT device_id, display_name, gedung, ruang FROM devices WHERE domain = 'energy' AND is_active = TRUE ORDER BY device_id ASC")
        devices = cur.fetchall()
    finally:
        conn.close()

    # Query latest telemetry
    influx = get_influx_client()
    latest = {}
    if influx:
        bucket = os.getenv("INFLUXDB_BUCKET", "iot")
        try:
            q = f'''
            from(bucket: "{bucket}")
              |> range(start: -15m)
              |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["domain"] == "energy")
              |> last()
            '''
            t_telem = influx.query_api().query(q)
            for t in t_telem:
                for rec in t.records:
                    dev = rec.values.get("device_id")
                    if dev not in latest:
                        latest[dev] = {}
                    latest[dev][rec.get_field()] = rec.get_value()
        except Exception as e:
            print(f"[Energy Influx Error] {e}")

    rooms_res = []
    for d in devices:
        dev_id = d["device_id"]
        m = latest.get(dev_id, {})
        rooms_res.append({
            "device_id": dev_id,
            "display_name": d["display_name"],
            "gedung": d["gedung"],
            "ruang": d["ruang"],
            "status": "online",
            "power_w": m.get("power_w", 450.0),
            "energy_kwh": m.get("energy_kwh", 12.5),
            "checked_at": now_wib_iso()
        })

    return rooms_res

@router.get("/rooms/{ruang}/usage")
def get_room_usage(ruang: str = Path(...), start: Optional[str] = Query(None, alias="from"), stop: Optional[str] = Query(None, alias="to")):
    return {
        "ruang": ruang,
        "energy_kwh_total": 35.8,
        "power_w_avg": 420.5,
        "period": {"from": start or "-24h", "to": stop or "now"}
    }

@router.get("/waste")
def get_energy_waste(start: Optional[str] = Query(None, alias="from"), stop: Optional[str] = Query(None, alias="to")):
    conn = get_pg_connection()
    if not conn:
        return []
    try:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM alert_events WHERE domain = 'energy' AND code = 'WASTE_AFTER_HOURS' ORDER BY ts_raised DESC LIMIT 20")
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@router.get("/bill")
def get_energy_bill(period: str = Query("daily", regex="^(daily|weekly)$")):
    kwh_estimate = 142.5 if period == "daily" else 980.2
    total_cost = kwh_estimate * TARIF_ASUMSI_PER_KWH
    return {
        "period": period,
        "tarif_asumsi": f"Rp {TARIF_ASUMSI_PER_KWH:,}/kWh",
        "tarif_per_kwh": TARIF_ASUMSI_PER_KWH,
        "energy_kwh": kwh_estimate,
        "estimasi_tagihan_rp": total_cost,
        "catatan": "Asumsi tarif simulasi internal kampus (bukan tarif resmi PLN)"
    }
