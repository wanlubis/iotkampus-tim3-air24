import os
import psycopg2
from psycopg2.extras import RealDictCursor
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))


def now_wib_iso():
    return datetime.now(WIB).isoformat()


def get_pg_connection():
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        print("[DB Error] POSTGRES_PASSWORD is not configured")
        return None

    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "kampus"),
            user=os.getenv("POSTGRES_USER", "iot_user"),
            password=password
        )
        return conn
    except Exception as e:
        print(f"[DB Error] PostgreSQL connection error: {e}")
        return None


def get_influx_client():
    url = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
    token = os.getenv("INFLUXDB_TOKEN")
    org = os.getenv("INFLUXDB_ORG", "prasmul")

    if not token:
        print("[Influx Error] INFLUXDB_TOKEN is not configured")
        return None

    try:
        client = InfluxDBClient(url=url, token=token, org=org, timeout=3000)
        return client
    except Exception as e:
        print(f"[Influx Error] Client init error: {e}")
        return None
