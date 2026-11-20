import os
import json
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Path
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
from app.auth import verify_api_key, AppException
from app.database import get_pg_connection, get_influx_client, now_wib_iso, WIB

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)],
    tags=["Core & Integration"]
)

class CreateAlertRequest(BaseModel):
    id: Optional[str] = None
    device_id: str
    domain: str
    code: str
    severity: str  # warning | critical | escalated
    message: str
    value: Optional[float] = None
    context: Optional[dict] = None

class AckRequest(BaseModel):
    acked_by: Optional[str] = "operator"

# ==============================================================================
# DEVICES REGISTRY
# ==============================================================================
@router.get("/devices")
def get_devices(
    domain: Optional[str] = Query(None, description="energy | coldchain | air"),
    gedung: Optional[str] = Query(None),
    ruang: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None)
):
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT device_id, display_name, domain, gedung, ruang, jenis, is_active, created_at FROM devices WHERE 1=1"
        params = []
        if domain:
            query += " AND domain = %s"
            params.append(domain)
        if gedung:
            query += " AND gedung = %s"
            params.append(gedung)
        if ruang:
            query += " AND ruang = %s"
            params.append(ruang)
        if is_active is not None:
            query += " AND is_active = %s"
            params.append(is_active)
        query += " ORDER BY device_id ASC"
        cur.execute(query, params)
        rows = cur.fetchall()
        # Convert created_at to WIB isoformat
        result = []
        for r in rows:
            item = dict(r)
            if item.get("created_at"):
                item["created_at"] = item["created_at"].astimezone(WIB).isoformat()
            result.append(item)
        return result
    finally:
        conn.close()

@router.get("/devices/{device_id}")
def get_device_detail(device_id: str = Path(...)):
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM devices WHERE device_id = %s", (device_id,))
        row = cur.fetchone()
        if not row:
            raise AppException(404, "NOT_FOUND", f"Perangkat dengan id '{device_id}' tidak ditemukan")
        item = dict(row)
        if item.get("created_at"):
            item["created_at"] = item["created_at"].astimezone(WIB).isoformat()
        return item
    finally:
        conn.close()

@router.get("/devices/{device_id}/status")
def get_device_status(device_id: str = Path(...)):
    # Verifikasi device ada
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT device_id, domain, gedung, ruang FROM devices WHERE device_id = %s", (device_id,))
        dev = cur.fetchone()
        if not dev:
            raise AppException(404, "NOT_FOUND", f"Perangkat '{device_id}' tidak ditemukan")
    finally:
        conn.close()

    # Query InfluxDB status measurement
    influx = get_influx_client()
    status_val = "offline"
    last_seen = None
    if influx:
        try:
            bucket = os.getenv("INFLUXDB_BUCKET", "iot")
            query = f'''
            from(bucket: "{bucket}")
              |> range(start: -1d)
              |> filter(fn: (r) => r["_measurement"] == "status" and r["device_id"] == "{device_id}")
              |> last()
            '''
            tables = influx.query_api().query(query)
            for table in tables:
                for record in table.records:
                    if record.get_value() == 1 or record.get_value() == "online":
                        status_val = "online"
                    else:
                        status_val = "offline"
                    last_seen = record.get_time().astimezone(WIB).isoformat()
        except Exception as e:
            print(f"[Influx Query Error] {e}")

    return {
        "device_id": device_id,
        "status": status_val,
        "last_seen": last_seen,
        "checked_at": now_wib_iso()
    }

# ==============================================================================
# TELEMETRY
# ==============================================================================
@router.get("/telemetry")
def get_telemetry_history(
    domain: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
    start: Optional[str] = Query("-1h", alias="from"),
    stop: Optional[str] = Query(None, alias="to"),
    limit: int = Query(200, ge=1, le=1000)
):
    influx = get_influx_client()
    if not influx:
        raise AppException(500, "INTERNAL", "InfluxDB tidak dapat dihubungi")

    bucket = os.getenv("INFLUXDB_BUCKET", "iot")
    range_clause = f'range(start: {start})' if not stop else f'range(start: {start}, stop: {stop})'
    filter_clauses = ['r["_measurement"] == "telemetry"']
    if domain:
        filter_clauses.append(f'r["domain"] == "{domain}"')
    if device_id:
        filter_clauses.append(f'r["device_id"] == "{device_id}"')

    filter_str = " and ".join(filter_clauses)
    query = f'''
    from(bucket: "{bucket}")
      |> {range_clause}
      |> filter(fn: (r) => {filter_str})
      |> limit(n: {limit})
    '''
    try:
        tables = influx.query_api().query(query)
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "time": record.get_time().astimezone(WIB).isoformat(),
                    "device_id": record.values.get("device_id"),
                    "domain": record.values.get("domain"),
                    "gedung": record.values.get("gedung"),
                    "ruang": record.values.get("ruang"),
                    "field": record.get_field(),
                    "value": record.get_value()
                })
        return {
            "total": len(results),
            "data": results
        }
    except Exception as e:
        return {"total": 0, "data": [], "note": f"Tidak ada data telemetry: {str(e)}"}

@router.get("/telemetry/latest")
def get_telemetry_latest(domain: Optional[str] = Query(None)):
    influx = get_influx_client()
    if not influx:
        return {"devices": []}
    bucket = os.getenv("INFLUXDB_BUCKET", "iot")
    filter_clause = 'r["_measurement"] == "telemetry"'
    if domain:
        filter_clause += f' and r["domain"] == "{domain}"'

    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -1d)
      |> filter(fn: (r) => {filter_clause})
      |> last()
    '''
    try:
        tables = influx.query_api().query(query)
        by_device = {}
        for table in tables:
            for record in table.records:
                dev_id = record.values.get("device_id")
                if not dev_id:
                    continue
                if dev_id not in by_device:
                    by_device[dev_id] = {
                        "device_id": dev_id,
                        "domain": record.values.get("domain"),
                        "gedung": record.values.get("gedung"),
                        "ruang": record.values.get("ruang"),
                        "timestamp": record.get_time().astimezone(WIB).isoformat(),
                        "metrics": {}
                    }
                by_device[dev_id]["metrics"][record.get_field()] = record.get_value()
        return list(by_device.values())
    except Exception as e:
        return []

# ==============================================================================
# ALERTS & ACK
# ==============================================================================
@router.get("/alerts")
def get_alerts(
    domain: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    acked: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500)
):
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT id, device_id, domain, code, severity, message, value, ts_raised, ts_acked, acked_by, context FROM alert_events WHERE 1=1"
        params = []
        if domain:
            query += " AND domain = %s"
            params.append(domain)
        if severity:
            query += " AND severity = %s"
            params.append(severity)
        if acked is not None:
            if acked:
                query += " AND ts_acked IS NOT NULL"
            else:
                query += " AND ts_acked IS NULL"
        query += " ORDER BY ts_raised DESC LIMIT %s"
        params.append(limit)
        cur.execute(query, params)
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

@router.post("/alerts")
def create_alert(body: CreateAlertRequest):
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Cek dedup: jika sudah ada alert aktif untuk device_id dan code yang sama dalam 60 detik terakhir
        cur.execute("""
            SELECT id FROM alert_events
            WHERE device_id = %s AND code = %s AND ts_acked IS NULL
              AND ts_raised > NOW() - INTERVAL '60 seconds'
        """, (body.device_id, body.code))
        existing = cur.fetchone()
        if existing:
            return {"id": existing["id"], "status": "deduplicated", "message": "Alert serupa masih aktif (dedup 60s)"}

        alert_id = body.id
        if not alert_id:
            # Format contoh: ALT-20261119-0007
            import uuid
            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            suffix = str(uuid.uuid4())[:4].upper()
            alert_id = f"ALT-{today_str}-{suffix}"

        now_dt = datetime.now(timezone.utc)
        cur.execute("""
            INSERT INTO alert_events (id, device_id, domain, code, severity, message, value, ts_raised, context)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            alert_id,
            body.device_id,
            body.domain,
            body.code,
            body.severity,
            body.message,
            body.value,
            now_dt,
            json.dumps(body.context or {})
        ))
        inserted = cur.fetchone()
        conn.commit()

        # Juga catat ke InfluxDB measurement 'alerts'
        influx = get_influx_client()
        if influx:
            try:
                from influxdb_client import Point
                from influxdb_client.client.write_api import SYNCHRONOUS
                bucket = os.getenv("INFLUXDB_BUCKET", "iot")
                org = os.getenv("INFLUXDB_ORG", "prasmul")
                p = Point("alerts") \
                    .tag("domain", body.domain) \
                    .tag("device_id", body.device_id) \
                    .tag("code", body.code) \
                    .tag("severity", body.severity) \
                    .field("value", float(body.value or 0.0)) \
                    .field("message", str(body.message))
                influx.write_api(write_options=SYNCHRONOUS).write(bucket=bucket, org=org, record=p)
            except Exception as e:
                print(f"[Influx Alert Write Error] {e}")

        res = dict(inserted)
        if res.get("ts_raised"):
            res["ts_raised"] = res["ts_raised"].astimezone(WIB).isoformat()
        return res
    finally:
        conn.close()

@router.get("/alerts/{alert_id}")
def get_alert_detail(alert_id: str = Path(...)):
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM alert_events WHERE id = %s", (alert_id,))
        row = cur.fetchone()
        if not row:
            raise AppException(404, "NOT_FOUND", f"Alert dengan id '{alert_id}' tidak ditemukan")
        item = dict(row)
        if item.get("ts_raised"):
            item["ts_raised"] = item["ts_raised"].astimezone(WIB).isoformat()
        if item.get("ts_acked"):
            item["ts_acked"] = item["ts_acked"].astimezone(WIB).isoformat()
        return item
    finally:
        conn.close()

@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: str = Path(...), body: AckRequest = None):
    acked_by = (body.acked_by if body else "operator") or "operator"
    conn = get_pg_connection()
    if not conn:
        raise AppException(500, "INTERNAL", "Database PostgreSQL tidak dapat dihubungi")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Cek apakah alert ada
        cur.execute("SELECT * FROM alert_events WHERE id = %s", (alert_id,))
        alert = cur.fetchone()
        if not alert:
            raise AppException(404, "NOT_FOUND", f"Alert dengan id '{alert_id}' tidak ditemukan")

        # Jika sudah di-ACK, idempoten
        if alert.get("ts_acked") is not None:
            return {
                "id": alert_id,
                "status": "already_acknowledged",
                "acked_by": alert["acked_by"],
                "ts_acked": alert["ts_acked"].astimezone(WIB).isoformat()
            }

        now_dt = datetime.now(timezone.utc)
        cur.execute(
            "UPDATE alert_events SET ts_acked = %s, acked_by = %s WHERE id = %s RETURNING *",
            (now_dt, acked_by, alert_id)
        )
        updated = cur.fetchone()
        conn.commit()

        return {
            "id": alert_id,
            "status": "acknowledged",
            "acked_by": updated["acked_by"],
            "ts_acked": updated["ts_acked"].astimezone(WIB).isoformat()
        }
    finally:
        conn.close()

# ==============================================================================
# SUMMARY (KONTRAK RESMI BAGIAN 7.5)
# ==============================================================================
@router.get("/summary")
def get_summary():
    """
    Endpoint resmi yang memenuhi skema JSON Bagian 7.5 spesifikasi tugas akhir.
    """
    conn = get_pg_connection()
    total_devices = 10
    devices_per_domain = {"energy": 4, "coldchain": 3, "air": 3}
    active_alerts = {"warning": 0, "critical": 0, "escalated": 0}
    domain_active_alerts = {"energy": 0, "coldchain": 0, "air": 0}

    if conn:
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            # Count total devices per domain
            cur.execute("SELECT domain, COUNT(*) as cnt FROM devices WHERE is_active = TRUE GROUP BY domain")
            for r in cur.fetchall():
                d = r["domain"]
                if d in devices_per_domain:
                    devices_per_domain[d] = r["cnt"]
            total_devices = sum(devices_per_domain.values())

            # Count unacked alerts
            cur.execute("""
                SELECT domain, severity, COUNT(*) as cnt 
                FROM alert_events 
                WHERE ts_acked IS NULL 
                GROUP BY domain, severity
            """)
            for r in cur.fetchall():
                sev = r["severity"]
                dom = r["domain"]
                cnt = r["cnt"]
                if sev in active_alerts:
                    active_alerts[sev] += cnt
                if dom in domain_active_alerts:
                    domain_active_alerts[dom] += cnt
        except Exception as e:
            print(f"[Summary PG Error] {e}")
        finally:
            conn.close()

    # Query Status & KPIs from InfluxDB
    influx = get_influx_client()
    domain_online = {"energy": 4, "coldchain": 3, "air": 3}
    kpi_energy = {"name": "power_w_total", "value": 0.0, "unit": "W"}
    kpi_coldchain = {"name": "temp_c_max", "value": 4.0, "unit": "°C"}
    kpi_air = {"name": "co2_ppm_max", "value": 450.0, "unit": "ppm"}

    if influx:
        bucket = os.getenv("INFLUXDB_BUCKET", "iot")
        try:
            # Check online devices from measurement 'status'
            q_status = f'''
            from(bucket: "{bucket}")
              |> range(start: -2m)
              |> filter(fn: (r) => r["_measurement"] == "status")
              |> last()
            '''
            t_status = influx.query_api().query(q_status)
            online_set = {"energy": set(), "coldchain": set(), "air": set()}
            for t in t_status:
                for rec in t.records:
                    dom = rec.values.get("domain")
                    dev = rec.values.get("device_id")
                    val = rec.get_value()
                    if (val == 1 or val == "online" or str(val).lower() == "online") and dom in online_set:
                        online_set[dom].add(dev)
            
            # If records found in last 2m, update online counts
            if any(len(s) > 0 for s in online_set.values()):
                domain_online["energy"] = len(online_set["energy"])
                domain_online["coldchain"] = len(online_set["coldchain"])
                domain_online["air"] = len(online_set["air"])

            # Query KPIs from latest telemetry
            q_telemetry = f'''
            from(bucket: "{bucket}")
              |> range(start: -15m)
              |> filter(fn: (r) => r["_measurement"] == "telemetry")
              |> last()
            '''
            t_telem = influx.query_api().query(q_telemetry)
            energy_sum = 0.0
            cc_max = None
            air_co2_max = None

            for t in t_telem:
                for rec in t.records:
                    field = rec.get_field()
                    val = float(rec.get_value() or 0)
                    dom = rec.values.get("domain")
                    if dom == "energy" and field == "power_w":
                        energy_sum += val
                    elif dom == "coldchain" and field == "temp_c":
                        if cc_max is None or val > cc_max:
                            cc_max = val
                    elif dom == "air" and field == "co2_ppm":
                        if air_co2_max is None or val > air_co2_max:
                            air_co2_max = val

            if energy_sum > 0:
                kpi_energy["value"] = round(energy_sum, 1)
            if cc_max is not None:
                kpi_coldchain["value"] = round(cc_max, 1)
            if air_co2_max is not None:
                kpi_air["value"] = round(air_co2_max, 1)

        except Exception as e:
            print(f"[Summary Influx Query Error] {e}")

    total_online = sum(domain_online.values())
    total_offline = max(0, total_devices - total_online)

    return {
        "generated_at": now_wib_iso(),
        "devices": {
            "total": total_devices,
            "online": total_online,
            "offline": total_offline
        },
        "alerts_active": active_alerts,
        "domains": {
            "energy": {
                "devices_online": domain_online["energy"],
                "devices_total": devices_per_domain["energy"],
                "kpi": kpi_energy,
                "alerts_active": domain_active_alerts["energy"]
            },
            "coldchain": {
                "devices_online": domain_online["coldchain"],
                "devices_total": devices_per_domain["coldchain"],
                "kpi": kpi_coldchain,
                "alerts_active": domain_active_alerts["coldchain"]
            },
            "air": {
                "devices_online": domain_online["air"],
                "devices_total": devices_per_domain["air"],
                "kpi": kpi_air,
                "alerts_active": domain_active_alerts["air"]
            }
        }
    }

# Aliases for integration dashboard (Section 7.5)
@router.get("/integration/devices")
def integration_devices():
    return get_devices()

@router.get("/integration/alerts")
def integration_alerts():
    return get_alerts()
