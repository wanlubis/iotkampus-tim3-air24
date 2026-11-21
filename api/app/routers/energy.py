"""Router domain Smart Energy (Tim 1) — Tahap 1: /rooms dan /waste."""

from datetime import datetime, timedelta
import os
from typing import Optional
from fastapi import APIRouter, Depends, Path, Query
from psycopg2.extras import RealDictCursor

from app.auth import AppException, verify_api_key
from app.database import WIB, get_influx_client, get_pg_connection, now_wib_iso

router = APIRouter(
    prefix="/api/v1/energy",
    dependencies=[Depends(verify_api_key)],
    tags=["Smart Energy (Tim 1)"],
)

TARIF_ASUMSI_PER_KWH = int(os.getenv("ENERGY_TARIFF_IDR_PER_KWH", "1500"))
OFFLINE_TIMEOUT_SEC = int(os.getenv("ENERGY_OFFLINE_TIMEOUT_SEC", "60"))


def _parse_wib_dt(raw: Optional[str], default_dt: datetime) -> datetime:
    if not raw:
        return default_dt
    try:
        dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppException(422, "VALIDATION_ERROR", f"Format waktu tidak valid: {raw}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=WIB)
    return dt.astimezone(WIB)


def _to_wib_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=WIB).isoformat()
    return dt.astimezone(WIB).isoformat()


@router.get("/rooms")
def get_energy_rooms():
    """Daftar ruang energy beserta daya terakhir, energi kumulatif, dan status online/offline nyata."""
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT device_id, display_name, gedung, ruang "
            "FROM devices WHERE domain = 'energy' AND is_active = TRUE ORDER BY device_id ASC"
        )
        devices = cur.fetchall()
    finally:
        conn.close()

    influx = get_influx_client()
    latest_tel: dict[str, dict] = {}
    latest_status: dict[str, dict] = {}
    if influx:
        bucket = os.getenv("INFLUXDB_BUCKET", "iot")
        try:
            q_status = f'''
            from(bucket: "{bucket}")
              |> range(start: -7d)
              |> filter(fn: (r) => r["_measurement"] == "status" and r["domain"] == "energy")
              |> group(columns: ["device_id"])
              |> last()
            '''
            for table in influx.query_api().query(q_status):
                for rec in table.records:
                    dev = rec.values.get("device_id")
                    val = rec.get_value()
                    is_on = val == 1 or str(val).lower() == "online"
                    latest_status[dev] = {
                        "online": is_on,
                        "ts": rec.get_time().astimezone(WIB),
                    }

            q_telem = f'''
            from(bucket: "{bucket}")
              |> range(start: -7d)
              |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["domain"] == "energy")
              |> group(columns: ["device_id", "_field"])
              |> last()
            '''
            for table in influx.query_api().query(q_telem):
                for rec in table.records:
                    dev = rec.values.get("device_id")
                    if not dev:
                        continue
                    entry = latest_tel.setdefault(dev, {"ts": None})
                    entry[rec.get_field()] = rec.get_value()
                    rec_dt = rec.get_time().astimezone(WIB)
                    if entry["ts"] is None or rec_dt > entry["ts"]:
                        entry["ts"] = rec_dt
        except Exception as exc:
            print(f"[Energy Influx Error] {exc}")
        finally:
            influx.close()

    now_dt = datetime.now(WIB)
    rooms_res = []
    for d in devices:
        dev_id = d["device_id"]
        tel = latest_tel.get(dev_id, {})
        st = latest_status.get(dev_id)
        last_tel_dt = tel.get("ts")
        no_data = (
            last_tel_dt is not None
            and (now_dt - last_tel_dt).total_seconds() > OFFLINE_TIMEOUT_SEC
        )
        is_online = bool(st and st["online"]) and not no_data
        last_seen_dt = last_tel_dt or (st["ts"] if st else None)

        rooms_res.append({
            "device_id": dev_id,
            "display_name": d["display_name"],
            "gedung": d["gedung"],
            "ruang": d["ruang"],
            "status": "online" if is_online else "offline",
            "online": is_online,
            "power_w": round(float(tel.get("power_w", 0.0)), 2),
            "energy_kwh": round(float(tel.get("energy_kwh", 0.0)), 4),
            "last_seen": _to_wib_iso(last_seen_dt),
            "checked_at": now_wib_iso(),
        })

    return rooms_res


@router.get("/rooms/{ruang}/usage")
def get_room_usage(
    ruang: str = Path(...),
    start: Optional[str] = Query(None, alias="from"),
    stop: Optional[str] = Query(None, alias="to"),
):
    # Tahap 2: akan diisi query profil time-series power_w & selisih energy_kwh dari InfluxDB
    return {
        "ruang": ruang,
        "energy_kwh_total": 0.0,
        "power_w_avg": 0.0,
        "period": {"from": start or "-24h", "to": stop or "now"},
    }


@router.get("/waste")
def get_energy_waste(
    start: Optional[str] = Query(None, alias="from"),
    stop: Optional[str] = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=500),
):
    """Daftar kejadian pemborosan (WASTE_AFTER_HOURS) dan rekap status ACK."""
    now_dt = datetime.now(WIB)
    end_dt = _parse_wib_dt(stop, now_dt)
    start_dt = _parse_wib_dt(start, end_dt - timedelta(days=7))
    if start_dt > end_dt:
        raise AppException(422, "VALIDATION_ERROR", "Parameter 'from' tidak boleh lebih besar dari 'to'")

    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, device_id, domain, code, severity, message, value,
                   ts_raised, ts_acked, acked_by, context
            FROM alert_events
            WHERE domain = 'energy'
              AND code = 'WASTE_AFTER_HOURS'
              AND ts_raised >= %s
              AND ts_raised <= %s
            ORDER BY ts_raised DESC
            LIMIT %s
            """,
            (start_dt, end_dt, limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    items = []
    unacked_count = 0
    for r in rows:
        item = dict(r)
        acked = item.get("ts_acked") is not None
        if not acked:
            unacked_count += 1
        item["acked"] = acked
        item["ts_raised"] = _to_wib_iso(item.get("ts_raised"))
        item["ts_acked"] = _to_wib_iso(item.get("ts_acked"))
        items.append(item)

    return {
        "from": _to_wib_iso(start_dt),
        "to": _to_wib_iso(end_dt),
        "summary": {
            "total_events": len(items),
            "unacked_count": unacked_count,
            "acked_count": len(items) - unacked_count,
        },
        "items": items,
    }


@router.get("/bill")
def get_energy_bill(period: str = Query("daily", pattern="^(daily|weekly)$")):
    # Tahap 2: akan dihitung dari delta energy_kwh harian/mingguan di InfluxDB
    kwh_estimate = 0.0
    return {
        "period": period,
        "tarif_asumsi": f"Rp {TARIF_ASUMSI_PER_KWH:,}/kWh",
        "tarif_per_kwh": TARIF_ASUMSI_PER_KWH,
        "energy_kwh": kwh_estimate,
        "estimasi_tagihan_rp": 0.0,
        "catatan": "Asumsi tarif simulasi internal kampus (bukan tarif resmi PLN)",
    }
