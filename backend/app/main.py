
import asyncio
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Depends, HTTPException, Header, Request
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
