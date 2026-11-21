"""Router domain Smart Energy (Tim 1).

Endpoint wajib (Bagian 5.5):
- GET /api/v1/energy/rooms
- GET /api/v1/energy/rooms/{ruang}/usage?from=&to=
- GET /api/v1/energy/waste?from=&to=
- GET /api/v1/energy/bill?period=daily|weekly

Fitur nilai tambah (Bagian 5.7):
- GET /api/v1/energy/rooms/{ruang}/usage/export?from=&to= (ekspor CSV)
- GET /api/v1/energy/baseline?from=&to= (perbandingan jam kerja vs luar jam kerja)
"""

import csv
from datetime import datetime, timedelta, timezone
import io
import os
import re
from typing import Any, Optional
from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
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
WORK_START_HOUR = int(os.getenv("ENERGY_WORK_START_HOUR", "7"))
WORK_END_HOUR = int(os.getenv("ENERGY_WORK_END_HOUR", "18"))
_WORK_DAYS = tuple(
    int(x.strip())
    for x in os.getenv("ENERGY_WORK_DAYS", "1,2,3,4,5").split(",")
    if x.strip().isdigit()
) or (1, 2, 3, 4, 5)
_SAFE_ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def _parse_wib_dt(raw: Optional[str], default_dt: datetime) -> datetime:
    if not raw:
        return default_dt
    text = raw.strip()
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000.0, tz=timezone.utc).astimezone(WIB)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppException(422, "VALIDATION_ERROR", f"Format waktu tidak valid: {raw}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=WIB)
    return dt.astimezone(WIB)


def _to_wib_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=WIB).isoformat(timespec="seconds")
    return dt.astimezone(WIB).isoformat(timespec="seconds")


def _sanitize_identifier(value: str, field_name: str) -> str:
    if not _SAFE_ID_RE.match(value):
        raise AppException(422, "VALIDATION_ERROR", f"Nilai {field_name} tidak valid: {value}")
    return value


def _tariff_assumption() -> dict[str, Any]:
    return {
        "tarif_per_kwh_idr": TARIF_ASUMSI_PER_KWH,
        "satuan": "IDR/kWh",
        "catatan": "Asumsi tarif simulasi internal kampus (bukan tarif resmi PLN).",
        "jam_kerja_wib": f"Senin-Jumat pukul {WORK_START_HOUR:02d}:00-{WORK_END_HOUR:02d}:00 WIB",
    }


def _is_work_hour(dt: datetime) -> bool:
    wib_dt = dt.astimezone(WIB)
    return wib_dt.isoweekday() in _WORK_DAYS and WORK_START_HOUR <= wib_dt.hour < WORK_END_HOUR


def _query_energy_consumption(
    start_dt: datetime,
    end_dt: datetime,
    ruang: Optional[str] = None,
) -> dict[str, dict[str, Any]]:
    """Hitung selisih konsumsi energy_kwh serta rata-rata dan puncak power_w per perangkat."""
    influx = get_influx_client()
    if not influx:
        return {}

    bucket = os.getenv("INFLUXDB_BUCKET", "iot")
    start_utc = start_dt.astimezone(timezone.utc).isoformat()
    stop_utc = end_dt.astimezone(timezone.utc).isoformat()
    ruang_filter = f' and r["ruang"] == "{ruang}"' if ruang else ""

    base_kwh = (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: {start_utc}, stop: {stop_utc})\n'
        f'  |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["domain"] == "energy"{ruang_filter} and r["_field"] == "energy_kwh")\n'
        f'  |> group(columns: ["device_id", "ruang"])\n'
    )
    base_power = (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: {start_utc}, stop: {stop_utc})\n'
        f'  |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["domain"] == "energy"{ruang_filter} and r["_field"] == "power_w")\n'
        f'  |> group(columns: ["device_id", "ruang"])\n'
    )

    stats: dict[str, dict[str, Any]] = {}
    try:
        q_api = influx.query_api()
        for key, flux in (
            ("first_kwh", base_kwh + "  |> first()\n"),
            ("last_kwh", base_kwh + "  |> last()\n"),
            ("avg_power_w", base_power + "  |> mean()\n"),
            ("max_power_w", base_power + "  |> max()\n"),
        ):
            for table in q_api.query(flux):
                for rec in table.records:
                    dev = rec.values.get("device_id")
                    if dev:
                        entry = stats.setdefault(dev, {"ruang": rec.values.get("ruang")})
                        entry[key] = float(rec.get_value() or 0.0)
    except Exception as exc:
        print(f"[Energy Consumption Influx Error] {exc}")
    finally:
        influx.close()

    for entry in stats.values():
        first_kwh = entry.get("first_kwh", 0.0)
        last_kwh = entry.get("last_kwh", 0.0)
        delta = max(0.0, last_kwh - first_kwh) if last_kwh >= first_kwh else last_kwh
        entry["consumed_kwh"] = round(delta, 4)
        entry["avg_power_w"] = round(entry.get("avg_power_w", 0.0), 2)
        entry["max_power_w"] = round(entry.get("max_power_w", 0.0), 2)
    return stats


def _query_energy_series(
    start_dt: datetime,
    end_dt: datetime,
    ruang: Optional[str] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Ambil deret waktu power_w dan energy_kwh dari InfluxDB secara kronologis."""
    influx = get_influx_client()
    if not influx:
        return []

    bucket = os.getenv("INFLUXDB_BUCKET", "iot")
    start_utc = start_dt.astimezone(timezone.utc).isoformat()
    stop_utc = end_dt.astimezone(timezone.utc).isoformat()
    ruang_filter = f' and r["ruang"] == "{ruang}"' if ruang else ""

    flux = f'''
from(bucket: "{bucket}")
  |> range(start: {start_utc}, stop: {stop_utc})
  |> filter(fn: (r) => r["_measurement"] == "telemetry" and r["domain"] == "energy"{ruang_filter})
  |> pivot(rowKey: ["_time", "device_id"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: {int(limit)})
'''
    rows: list[dict[str, Any]] = []
    try:
        for table in influx.query_api().query(flux):
            for rec in table.records:
                vals = rec.values
                rows.append({
                    "ts": _to_wib_iso(vals.get("_time")),
                    "device_id": vals.get("device_id"),
                    "ruang": vals.get("ruang"),
                    "power_w": round(float(vals.get("power_w") or 0.0), 2),
                    "energy_kwh": round(float(vals.get("energy_kwh") or 0.0), 4),
                })
    except Exception as exc:
        print(f"[Energy Series Influx Error] {exc}")
    finally:
        influx.close()

    rows.reverse()
    return rows


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
    limit: int = Query(500, ge=1, le=1000),
):
    """Energi kumulatif periode berjalan dan profil daya (time-series) untuk satu ruang."""
    safe_ruang = _sanitize_identifier(ruang, "ruang")
    now_dt = datetime.now(WIB)
    end_dt = _parse_wib_dt(stop, now_dt)
    start_dt = _parse_wib_dt(start, end_dt - timedelta(hours=1))
    if start_dt > end_dt:
        raise AppException(422, "VALIDATION_ERROR", "Parameter 'from' tidak boleh lebih besar dari 'to'")

    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT device_id, display_name, gedung, ruang "
            "FROM devices WHERE domain = 'energy' AND ruang = %s AND is_active = TRUE LIMIT 1",
            (safe_ruang,),
        )
        device = cur.fetchone()
    finally:
        conn.close()

    if not device:
        raise AppException(404, "NOT_FOUND", f"Ruang energy '{safe_ruang}' tidak ditemukan")

    stats = _query_energy_consumption(start_dt, end_dt, ruang=safe_ruang)
    dev_stats = stats.get(device["device_id"], {})
    consumed_kwh = round(float(dev_stats.get("consumed_kwh", 0.0)), 4)
    series = _query_energy_series(start_dt, end_dt, ruang=safe_ruang, limit=limit)

    return {
        "ruang": safe_ruang,
        "gedung": device["gedung"],
        "device_id": device["device_id"],
        "display_name": device["display_name"],
        "from": _to_wib_iso(start_dt),
        "to": _to_wib_iso(end_dt),
        "summary": {
            "consumed_kwh": consumed_kwh,
            "avg_power_w": dev_stats.get("avg_power_w", 0.0),
            "max_power_w": dev_stats.get("max_power_w", 0.0),
            "estimasi_tagihan_idr": round(consumed_kwh * TARIF_ASUMSI_PER_KWH, 2),
        },
        "tarif_asumsi": _tariff_assumption(),
        "series": series,
    }


@router.get("/rooms/{ruang}/usage/export")
def export_room_usage_csv(
    ruang: str = Path(...),
    start: Optional[str] = Query(None, alias="from"),
    stop: Optional[str] = Query(None, alias="to"),
):
    """Ekspor profil daya dan energi ruang ke berkas CSV (fitur nilai tambah Bagian 5.7)."""
    usage = get_room_usage(ruang=ruang, start=start, stop=stop, limit=1000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ts_wib", "ruang", "device_id", "power_w", "energy_kwh"])
    for row in usage["series"]:
        writer.writerow([row["ts"], usage["ruang"], row["device_id"], row["power_w"], row["energy_kwh"]])

    filename = f"energy_{usage['ruang']}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    """Estimasi tagihan listrik harian atau mingguan per ruang dan total (Bagian 5.5)."""
    now_dt = datetime.now(WIB)
    if period == "daily":
        start_dt = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_dt = (now_dt - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)

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

    consumption = _query_energy_consumption(start_dt, now_dt)
    per_ruang = []
    total_kwh = 0.0
    for d in devices:
        dev_id = d["device_id"]
        kwh = float(consumption.get(dev_id, {}).get("consumed_kwh", 0.0))
        total_kwh += kwh
        per_ruang.append({
            "device_id": dev_id,
            "ruang": d["ruang"],
            "display_name": d["display_name"],
            "energy_kwh": round(kwh, 4),
            "estimasi_tagihan_idr": round(kwh * TARIF_ASUMSI_PER_KWH, 2),
        })

    total_kwh = round(total_kwh, 4)
    return {
        "periode": {
            "jenis": period,
            "from": _to_wib_iso(start_dt),
            "to": _to_wib_iso(now_dt),
        },
        "tarif_asumsi": _tariff_assumption(),
        "total_kwh": total_kwh,
        "estimasi_tagihan_total_idr": round(total_kwh * TARIF_ASUMSI_PER_KWH, 2),
        "per_ruang": per_ruang,
    }


@router.get("/baseline")
def get_energy_baseline(
    start: Optional[str] = Query(None, alias="from"),
    stop: Optional[str] = Query(None, alias="to"),
):
    """Perbandingan daya rata-rata per ruang saat jam kerja vs luar jam kerja (Bagian 5.7)."""
    now_dt = datetime.now(WIB)
    end_dt = _parse_wib_dt(stop, now_dt)
    start_dt = _parse_wib_dt(start, end_dt - timedelta(days=1))
    if start_dt > end_dt:
        raise AppException(422, "VALIDATION_ERROR", "Parameter 'from' tidak boleh lebih besar dari 'to'")

    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT device_id, display_name, ruang "
            "FROM devices WHERE domain = 'energy' AND is_active = TRUE ORDER BY device_id ASC"
        )
        devices = cur.fetchall()
    finally:
        conn.close()

    rows = _query_energy_series(start_dt, end_dt, limit=1000)
    buckets: dict[str, dict[str, list[float]]] = {
        d["ruang"]: {"work_hours": [], "after_hours": []} for d in devices
    }
    for row in rows:
        ruang = row.get("ruang")
        ts_str = row.get("ts")
        if ruang in buckets and ts_str:
            dt = datetime.fromisoformat(ts_str)
            bucket_key = "work_hours" if _is_work_hour(dt) else "after_hours"
            buckets[ruang][bucket_key].append(float(row.get("power_w", 0.0)))

    items = []
    for d in devices:
        ruang = d["ruang"]
        wh = buckets[ruang]["work_hours"]
        ah = buckets[ruang]["after_hours"]
        items.append({
            "ruang": ruang,
            "device_id": d["device_id"],
            "display_name": d["display_name"],
            "avg_work_hours_w": round(sum(wh) / len(wh), 2) if wh else None,
            "avg_after_hours_w": round(sum(ah) / len(ah), 2) if ah else None,
            "samples_work_hours": len(wh),
            "samples_after_hours": len(ah),
        })

    return {
        "from": _to_wib_iso(start_dt),
        "to": _to_wib_iso(end_dt),
        "jam_kerja_wib": f"Senin-Jumat pukul {WORK_START_HOUR:02d}:00-{WORK_END_HOUR:02d}:00 WIB",
        "items": items,
    }
