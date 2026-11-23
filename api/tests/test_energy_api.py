"""Unit test endpoint Smart Energy Tim 1 (Bagian 5.5, 5.7, dan 4.6 PDF)."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
import types
import pytest
from fastapi.testclient import TestClient

# Fallback stub psycopg2 hanya jika dijalankan di mesin lokal tanpa psycopg2-binary
try:
    import psycopg2  # noqa: F401
    import psycopg2.extras  # noqa: F401
except ImportError:
    _pg_mod = types.ModuleType("psycopg2")
    _pg_extras = types.ModuleType("psycopg2.extras")
    _pg_extras.RealDictCursor = object
    _pg_mod.extras = _pg_extras
    sys.modules["psycopg2"] = _pg_mod
    sys.modules["psycopg2.extras"] = _pg_extras

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.routers import energy  # noqa: E402

WIB = timezone(timedelta(hours=7))
TEST_API_KEY = "unit-test-energy-key"
HEADERS = {"X-API-Key": TEST_API_KEY}

SAMPLE_DEVICES = [
    {"device_id": "kwh-01", "display_name": "KWh Meter Ruang 3012", "gedung": "bsd-a", "ruang": "r3012"},
    {"device_id": "kwh-02", "display_name": "KWh Meter Ruang 3013", "gedung": "bsd-a", "ruang": "r3013"},
    {"device_id": "kwh-03", "display_name": "KWh Meter Ruang 3017", "gedung": "bsd-a", "ruang": "r3017"},
    {"device_id": "kwh-04", "display_name": "KWh Meter Lab IoT", "gedung": "bsd-a", "ruang": "lab-iot"},
]


class FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def execute(self, _query: str, _params=None) -> None:
        return None

    def fetchall(self) -> list[dict]:
        return [dict(r) for r in self._rows]

    def fetchone(self) -> dict | None:
        return dict(self._rows[0]) if self._rows else None


class FakeConnection:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def cursor(self, cursor_factory=None) -> FakeCursor:
        return FakeCursor(self._rows)

    def close(self) -> None:
        return None


class FakeInfluxRecord:
    def __init__(self, values: dict, field: str, value, ts: datetime) -> None:
        self.values = values
        self._field = field
        self._value = value
        self._time = ts

    def get_field(self) -> str:
        return self._field

    def get_value(self):
        return self._value

    def get_time(self) -> datetime:
        return self._time


class FakeInfluxTable:
    def __init__(self, records: list[FakeInfluxRecord]) -> None:
        self.records = records


class FakeInfluxClient:
    def __init__(self, status_records: list[FakeInfluxRecord], tel_records: list[FakeInfluxRecord]) -> None:
        self._status_records = status_records
        self._tel_records = tel_records

    def query_api(self):
        client = self

        class _QueryApi:
            def query(self, flux: str):
                if '"status"' in flux:
                    return [FakeInfluxTable(client._status_records)]
                return [FakeInfluxTable(client._tel_records)]

        return _QueryApi()

    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", TEST_API_KEY)


def test_energy_endpoints_require_api_key() -> None:
    client = TestClient(app)
    for path in (
        "/api/v1/energy/rooms",
        "/api/v1/energy/rooms/r3012/usage",
        "/api/v1/energy/waste",
        "/api/v1/energy/bill?period=daily",
        "/api/v1/energy/baseline",
    ):
        resp_missing = client.get(path)
        assert resp_missing.status_code == 401
        assert resp_missing.json() == {"error": {"code": "UNAUTHORIZED", "message": "X-API-Key tidak valid"}}

        resp_wrong = client.get(path, headers={"X-API-Key": "salah"})
        assert resp_wrong.status_code == 401


def test_get_energy_rooms_distinguishes_online_lwt_and_nodata(monkeypatch: pytest.MonkeyPatch) -> None:
    now_utc = datetime.now(timezone.utc)
    stale_utc = now_utc - timedelta(seconds=120)

    status_recs = [
        FakeInfluxRecord({"device_id": "kwh-01"}, "online", 1, now_utc),
        FakeInfluxRecord({"device_id": "kwh-02"}, "online", 0, now_utc),      # LWT offline (CRASH)
        FakeInfluxRecord({"device_id": "kwh-03"}, "online", 1, now_utc),      # Status online, tapi telemetry basi (STOP)
        FakeInfluxRecord({"device_id": "kwh-04"}, "online", 1, stale_utc),    # Status online basi >60s & tanpa telemetry
    ]
    tel_recs = [
        FakeInfluxRecord({"device_id": "kwh-01"}, "power_w", 720.5, now_utc),
        FakeInfluxRecord({"device_id": "kwh-01"}, "energy_kwh", 12.3456, now_utc),
        FakeInfluxRecord({"device_id": "kwh-02"}, "power_w", 500.0, now_utc),
        FakeInfluxRecord({"device_id": "kwh-02"}, "energy_kwh", 18.0, now_utc),
        FakeInfluxRecord({"device_id": "kwh-03"}, "power_w", 300.0, stale_utc),
        FakeInfluxRecord({"device_id": "kwh-03"}, "energy_kwh", 9.5, stale_utc),
    ]

    monkeypatch.setattr(energy, "get_pg_connection", lambda: FakeConnection(SAMPLE_DEVICES))
    monkeypatch.setattr(energy, "get_influx_client", lambda: FakeInfluxClient(status_recs, tel_recs))

    client = TestClient(app)
    resp = client.get("/api/v1/energy/rooms", headers=HEADERS)
    assert resp.status_code == 200
    items = {item["device_id"]: item for item in resp.json()}

    assert items["kwh-01"]["status"] == "online"
    assert items["kwh-01"]["power_w"] == 720.5
    assert items["kwh-01"]["energy_kwh"] == 12.3456
    assert items["kwh-02"]["status"] == "offline"
    assert items["kwh-03"]["status"] == "offline"
    assert items["kwh-04"]["status"] == "offline"


def test_get_room_usage_and_csv_export(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(energy, "get_pg_connection", lambda: FakeConnection([SAMPLE_DEVICES[0]]))
    monkeypatch.setattr(
        energy,
        "_query_energy_consumption",
        lambda _s, _e, ruang=None: {
            "kwh-01": {"ruang": "r3012", "consumed_kwh": 2.5, "avg_power_w": 650.0, "max_power_w": 920.0}
        },
    )
    monkeypatch.setattr(
        energy,
        "_query_energy_series",
        lambda _s, _e, ruang=None, limit=500: [
            {"ts": "2026-11-21T10:00:00+07:00", "device_id": "kwh-01", "ruang": "r3012", "power_w": 650.0, "energy_kwh": 12.0},
            {"ts": "2026-11-21T10:05:00+07:00", "device_id": "kwh-01", "ruang": "r3012", "power_w": 920.0, "energy_kwh": 14.5},
        ],
    )

    client = TestClient(app)
    resp = client.get("/api/v1/energy/rooms/r3012/usage", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ruang"] == "r3012"
    assert body["summary"]["consumed_kwh"] == 2.5
    assert body["summary"]["estimasi_tagihan_idr"] == 3750.0
    assert body["tarif_asumsi"]["tarif_per_kwh_idr"] == 1500
    assert len(body["series"]) == 2

    csv_resp = client.get("/api/v1/energy/rooms/r3012/usage/export", headers=HEADERS)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "energy_r3012.csv" in csv_resp.headers["content-disposition"]
    assert "ts_wib,ruang,device_id,power_w,energy_kwh" in csv_resp.text


def test_get_room_usage_not_found_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(energy, "get_pg_connection", lambda: FakeConnection([]))
    client = TestClient(app)

    r_404 = client.get("/api/v1/energy/rooms/tidak-ada/usage", headers=HEADERS)
    assert r_404.status_code == 404
    assert r_404.json()["error"]["code"] == "NOT_FOUND"

    r_bad_range = client.get(
        "/api/v1/energy/rooms/r3012/usage?from=2026-11-21T12:00:00+07:00&to=2026-11-21T10:00:00+07:00",
        headers=HEADERS,
    )
    assert r_bad_range.status_code == 422
    assert r_bad_range.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_energy_waste_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    now_wib = datetime(2026, 11, 21, 20, 30, 0, tzinfo=WIB)
    waste_rows = [
        {
            "id": "ALT-20261121-0001",
            "device_id": "kwh-01",
            "domain": "energy",
            "code": "WASTE_AFTER_HOURS",
            "severity": "warning",
            "message": "Pemborosan di r3012",
            "value": 680.0,
            "ts_raised": now_wib,
            "ts_acked": None,
            "acked_by": None,
            "context": {"ruang": "r3012"},
        },
        {
            "id": "ALT-20261121-0002",
            "device_id": "kwh-02",
            "domain": "energy",
            "code": "WASTE_AFTER_HOURS",
            "severity": "warning",
            "message": "Pemborosan di r3013",
            "value": 710.0,
            "ts_raised": now_wib - timedelta(minutes=10),
            "ts_acked": now_wib - timedelta(minutes=5),
            "acked_by": "aldy",
            "context": {"ruang": "r3013"},
        },
    ]
    monkeypatch.setattr(energy, "get_pg_connection", lambda: FakeConnection(waste_rows))

    client = TestClient(app)
    resp = client.get("/api/v1/energy/waste", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"] == {"total_events": 2, "unacked_count": 1, "acked_count": 1}
    assert data["items"][0]["ts_raised"].endswith("+07:00")
    assert data["items"][0]["acked"] is False
    assert data["items"][1]["acked"] is True


def test_get_energy_bill_daily_and_weekly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(energy, "get_pg_connection", lambda: FakeConnection(SAMPLE_DEVICES[:2]))
    monkeypatch.setattr(
        energy,
        "_query_energy_consumption",
        lambda _s, _e, ruang=None: {
            "kwh-01": {"ruang": "r3012", "consumed_kwh": 1.25},
            "kwh-02": {"ruang": "r3013", "consumed_kwh": 0.75},
        },
    )

    client = TestClient(app)
    for period in ("daily", "weekly"):
        resp = client.get(f"/api/v1/energy/bill?period={period}", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["periode"]["jenis"] == period
        assert body["periode"]["from"].endswith("+07:00")
        assert body["periode"]["to"].endswith("+07:00")
        assert body["tarif_asumsi"]["tarif_per_kwh_idr"] == 1500
        assert "bukan tarif resmi PLN" in body["tarif_asumsi"]["catatan"]
        assert body["total_kwh"] == 2.0
        assert body["estimasi_tagihan_total_idr"] == 3000.0
        assert len(body["per_ruang"]) == 2


def test_get_energy_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(energy, "get_pg_connection", lambda: FakeConnection([SAMPLE_DEVICES[0]]))
    monkeypatch.setattr(
        energy,
        "_query_energy_series",
        lambda _s, _e, ruang=None, limit=1000: [
            # Kamis 10:00 WIB (jam kerja)
            {"ts": "2026-11-19T10:00:00+07:00", "device_id": "kwh-01", "ruang": "r3012", "power_w": 800.0, "energy_kwh": 10.0},
            # Kamis 21:00 WIB (luar jam kerja)
            {"ts": "2026-11-19T21:00:00+07:00", "device_id": "kwh-01", "ruang": "r3012", "power_w": 100.0, "energy_kwh": 11.0},
        ],
    )

    client = TestClient(app)
    resp = client.get("/api/v1/energy/baseline", headers=HEADERS)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["avg_work_hours_w"] == 800.0
    assert items[0]["avg_after_hours_w"] == 100.0
