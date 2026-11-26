
import asyncio
import re
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Depends, HTTPException, Header, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import get_db_connection
from app.influx import query_influx
from app.outbox_worker import run_outbox_worker
from app.routers.coldchain import router as coldchain_router
from app.routers.device_status import router as device_status_router
from app.routers.alerts import router as alerts_router


# =========================
# APPLICATION LIFESPAN
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = threading.Event()

    worker = threading.Thread(
        target=run_outbox_worker,
        args=(stop_event,),
        name="alert-outbox-worker",
        daemon=True,
    )

    worker.start()

    try:
        yield
    finally:
        stop_event.set()
        await asyncio.to_thread(worker.join, 30)


app = FastAPI(
    lifespan=lifespan,
    title="Cold-Chain IoT API",
    description="API untuk monitoring sistem cold-chain",
    version="1.0.0",
)

# =========================
# SAFE VALIDATION ERROR HANDLER
# =========================

@app.exception_handler(RequestValidationError)
async def safe_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
):
    errors = []

    for error in exc.errors():
        errors.append({
            "type": str(error.get("type", "validation_error")),
            "loc": [
                item if isinstance(item, (str, int)) else str(item)
                for item in error.get("loc", ())
            ],
            "msg": str(error.get("msg", "Invalid request")),
        })

    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


app.include_router(coldchain_router)
app.include_router(device_status_router)
app.include_router(alerts_router)


VALID_DOMAINS = ("energy", "coldchain", "air")
WIB = timezone(timedelta(hours=7))


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
# HEALTH CHECK
# =========================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "coldchain-api",
        "time": datetime.now(WIB).isoformat(),
        "version": app.version,
    }


# =========================
# DEVICE ENDPOINTS
# =========================

@app.get(
    "/api/v1/devices",
    dependencies=[Depends(verify_api_key)],
)
def get_devices(
    domain: str = None,
    gedung: str = None,
    ruang: str = None,
):
    try:
        if domain and domain not in VALID_DOMAINS:
            raise HTTPException(
                status_code=400,
                detail="Domain tidak valid",
            )

        conditions = []
        params = []

        if domain:
            conditions.append("domain = %s")
            params.append(domain)

        if gedung:
            conditions.append("gedung = %s")
            params.append(gedung)

        if ruang:
            conditions.append("ruang = %s")
            params.append(ruang)

        query = """
            SELECT device_id, domain, gedung, ruang,
                   status, last_seen
            FROM devices
        """

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY device_id"

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return cur.fetchall()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@app.get(
    "/api/v1/devices/{device_id}",
    dependencies=[Depends(verify_api_key)],
)
def get_device(device_id: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT device_id, domain, gedung, ruang,
                           status, last_seen
                    FROM devices
                    WHERE device_id = %s
                    """,
                    (device_id,),
                )

                device = cur.fetchone()

                if not device:
                    raise HTTPException(
                        status_code=404,
                        detail="Device tidak ditemukan",
                    )

                return device

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =========================
# DEVICE STATUS - INFLUXDB
# =========================

@app.get(
    "/api/v1/devices/{device_id}/status",
    dependencies=[Depends(verify_api_key)],
)
def get_device_status(device_id: str):
    try:
        if not device_id or not all(
            c.isalnum() or c in "-_" for c in device_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Device ID tidak valid",
            )

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT device_id, domain, status, last_seen
                    FROM devices
                    WHERE device_id = %s
                    """,
                    (device_id,),
                )

                device = cur.fetchone()

        if not device:
            raise HTTPException(
                status_code=404,
                detail="Device tidak ditemukan",
            )

        domain = device["domain"]

        if domain not in VALID_DOMAINS:
            raise HTTPException(
                status_code=500,
                detail="Domain perangkat tidak valid",
            )

        flux_query = f'''
            from(bucket: "{settings.INFLUXDB_BUCKET}")
                |> range(start: -7d)
                |> filter(fn: (r) =>
                    r._measurement == "status" and
                    r._field == "online" and
                    r.device_id == "{device_id}" and
                    r.domain == "{domain}"
                )
                |> group(columns: ["device_id"])
                |> sort(columns: ["_time"], desc: true)
                |> limit(n: 1)
        '''

        records = query_influx(flux_query)

        last_seen = device["last_seen"]

        if last_seen is not None:
            last_seen = last_seen.astimezone(WIB).isoformat()

        if not records:
            return {
                "device_id": device_id,
                "domain": domain,
                "status": "unknown",
                "online": None,
                "last_seen": last_seen,
                "timestamp": None,
                "source": "influxdb",
                "message": "Data status belum tersedia",
            }

        record = records[0]
        value = record.get("_value")

        if value not in (0, 1):
            raise HTTPException(
                status_code=500,
                detail="Nilai status InfluxDB tidak valid",
            )

        online = int(value)
        timestamp = record.get("_time")

        if timestamp is not None:
            timestamp = timestamp.astimezone(WIB).isoformat()

        return {
            "device_id": device_id,
            "domain": domain,
            "status": "online" if online == 1 else "offline",
            "online": online,
            "last_seen": last_seen,
            "timestamp": timestamp,
            "source": "influxdb",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =========================
# TELEMETRY HISTORY VALIDATION
# =========================

def parse_telemetry_timestamp(
    name: str,
    value: str | None,
) -> datetime | None:
    if value is None:
        return None

    pattern = (
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
        r"T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?"
        r"(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
    )

    if not re.fullmatch(pattern, value):
        raise HTTPException(
            status_code=422,
            detail=f"Parameter {name} wajib menggunakan ISO 8601 dengan timezone",
        )

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        utc_value = parsed.astimezone(timezone.utc)

        if not 1970 <= utc_value.year <= 2261:
            raise ValueError("Timestamp out of supported range")

        return utc_value

    except (ValueError, OverflowError):
        raise HTTPException(
            status_code=422,
            detail=f"Parameter {name} tidak valid",
        )


def validate_telemetry_history_filters(
    domain: str | None,
    device_id: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
):
    if domain is not None and domain not in VALID_DOMAINS:
        raise HTTPException(
            status_code=422,
            detail="Domain tidak valid",
        )

    if device_id is not None and not re.fullmatch(
        r"[A-Za-z0-9_-]{1,50}", device_id
    ):
        raise HTTPException(
            status_code=422,
            detail="Device ID tidak valid",
        )

    for name, value in (
        ("from", from_time),
        ("to", to_time),
    ):
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Parameter {name} wajib memiliki timezone",
            )

    end = (
        to_time.astimezone(timezone.utc)
        if to_time is not None
        else datetime.now(timezone.utc)
    )

    start = (
        from_time.astimezone(timezone.utc)
        if from_time is not None
        else end - timedelta(hours=1)
    )

    if start >= end:
        raise HTTPException(
            status_code=422,
            detail="Parameter from harus lebih awal dari to",
        )

    if start.year < 1970 or end.year > 2261:
        raise HTTPException(
            status_code=422,
            detail="Timestamp di luar rentang yang didukung",
        )

    if end - start > timedelta(days=7):
        raise HTTPException(
            status_code=422,
            detail="Rentang telemetry maksimal 7 hari",
        )

    return start, end


# =========================
# TELEMETRY HISTORY ENDPOINT
# =========================

@app.get(
    "/api/v1/telemetry",
    dependencies=[Depends(verify_api_key)],
)
def get_telemetry_history(
    domain: str | None = Query(default=None),
    device_id: str | None = Query(default=None),
    from_time: str | None = Query(default=None, alias="from"),
    to_time: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
):
    start, end = validate_telemetry_history_filters(
        domain,
        device_id,
        parse_telemetry_timestamp("from", from_time),
        parse_telemetry_timestamp("to", to_time),
    )

    start_iso = start.isoformat().replace("+00:00", "Z")
    end_iso = end.isoformat().replace("+00:00", "Z")

    filters = []

    if domain is not None:
        filters.append(
            f'|> filter(fn: (r) => r.domain == "{domain}")'
        )

    if device_id is not None:
        filters.append(
            f'|> filter(fn: (r) => r.device_id == "{device_id}")'
        )

    filter_query = "\n".join(filters)

    flux_query = f'''
        from(bucket: "{settings.INFLUXDB_BUCKET}")
            |> range(
                start: time(v: "{start_iso}"),
                stop: time(v: "{end_iso}")
            )
            |> filter(fn: (r) =>
                r._measurement == "telemetry"
            )
            {filter_query}
            |> pivot(
                rowKey: ["_time"],
                columnKey: ["_field"],
                valueColumn: "_value"
            )
            |> group(columns: [])
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: {limit})
    '''

    try:
        records = query_influx(flux_query)

        records.sort(
            key=lambda r: (
                r["_time"],
                r.get("domain", ""),
                r.get("device_id", ""),
            ),
            reverse=True,
        )

        excluded_fields = {
            "result",
            "table",
            "_start",
            "_stop",
            "_time",
            "_measurement",
            "device_id",
            "domain",
            "gedung",
            "ruang",
        }

        data = []

        for record in records[:limit]:
            metrics = {
                key: value
                for key, value in record.items()
                if key not in excluded_fields
                and value is not None
            }

            data.append({
                "timestamp": record["_time"].astimezone(WIB).isoformat(),
                "device_id": record.get("device_id"),
                "domain": record.get("domain"),
                "gedung": record.get("gedung"),
                "ruang": record.get("ruang"),
                "metrics": metrics,
            })

        return {
            "count": len(data),
            "from": start.astimezone(WIB).isoformat(),
            "to": end.astimezone(WIB).isoformat(),
            "limit": limit,
            "data": data,
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Gagal mengambil riwayat telemetry",
        )


# =========================
# LATEST TELEMETRY ENDPOINT
# =========================

@app.get(
    "/api/v1/telemetry/latest",
    dependencies=[Depends(verify_api_key)],
)
def get_latest_telemetry(
    device_id: str = None,
    domain: str = None,
):
    try:
        if device_id and not all(
            c.isalnum() or c in "-_" for c in device_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Device ID tidak valid",
            )

        if domain and domain not in VALID_DOMAINS:
            raise HTTPException(
                status_code=400,
                detail="Domain tidak valid",
            )

        device_filter = ""
        domain_filter = ""

        if device_id:
            device_filter = f'''
                |> filter(fn: (r) =>
                    r.device_id == "{device_id}"
                )
            '''

        if domain:
            domain_filter = f'''
                |> filter(fn: (r) =>
                    r.domain == "{domain}"
                )
            '''

        flux_query = f'''
            from(bucket: "{settings.INFLUXDB_BUCKET}")
                |> range(start: -24h)
                |> filter(fn: (r) =>
                    r._measurement == "telemetry"
                )
                {domain_filter}
                {device_filter}
                |> pivot(
                    rowKey: ["_time"],
                    columnKey: ["_field"],
                    valueColumn: "_value"
                )
                |> group(columns: ["domain", "device_id"])
                |> sort(columns: ["_time"], desc: true)
                |> limit(n: 1)
        '''

        records = query_influx(flux_query)

        return {
            "count": len(records),
            "data": records,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
