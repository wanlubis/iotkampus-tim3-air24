"""
devices_config.py - Konfigurasi 4 Smart Energy Meter (Tim 1 - AIR24)
Mengacu pada kontrak resmi monorepo wanlubis/iotkampus-tim3-air24
(postgres/init/01_schema.sql, docs/MQTT_CONTRACT.md, README.md).
"""

# Asumsi Domain Smart Energy (bukan tarif resmi PLN)
TARIFF_IDR_PER_KWH = 1500

# Jam kerja kampus (WIB / UTC+7): Senin-Jumat 07:00-18:00
WORK_START_HOUR = 7
WORK_END_HOUR = 18
WORK_DAYS = (1, 2, 3, 4, 5)  # ISO weekday: 1=Senin .. 5=Jumat

# Ambang batas rule engine (README.md Bagian 4)
WASTE_THRESHOLD_W = 200.0        # > 200 W di luar jam kerja
WASTE_DURATION_SEC = 120         # sustained 2 menit
HIGH_LOAD_THRESHOLD_W = 3000.0   # > 3000 W (dalam/luar jam kerja)
HIGH_LOAD_DURATION_SEC = 60      # sustained 1 menit
OFFLINE_TIMEOUT_SEC = 60         # no telemetry/heartbeat 60 detik atau LWT offline

# Mode operasi simulator (simulators/energy/README.md)
MODES = (
    "NORMAL",
    "BOROS",
    "LONJAKAN",
    "STOP",
    "CRASH",
)

# 4 Perangkat Wajib Minimum Domain Smart Energy (Bagian 4.2)
DEVICES = [
    {
        "id": "kwh-01",
        "domain": "energy",
        "gedung": "bsd-a",
        "ruang": "r3012",
        "jenis": "kwh-meter",
        "display_name": "KWh Meter Ruang 3012",
        "work_power_w": (450.0, 1200.0),
        "after_hours_power_w": (40.0, 140.0),
        "initial_kwh": 120.5000,
    },
    {
        "id": "kwh-02",
        "domain": "energy",
        "gedung": "bsd-a",
        "ruang": "r3013",
        "jenis": "kwh-meter",
        "display_name": "KWh Meter Ruang 3013",
        "work_power_w": (400.0, 1100.0),
        "after_hours_power_w": (35.0, 130.0),
        "initial_kwh": 98.2000,
    },
    {
        "id": "kwh-03",
        "domain": "energy",
        "gedung": "bsd-a",
        "ruang": "r3017",
        "jenis": "kwh-meter",
        "display_name": "KWh Meter Ruang 3017",
        "work_power_w": (500.0, 1400.0),
        "after_hours_power_w": (45.0, 150.0),
        "initial_kwh": 145.8000,
    },
    {
        "id": "kwh-04",
        "domain": "energy",
        "gedung": "bsd-a",
        "ruang": "lab-iot",
        "jenis": "kwh-meter",
        "display_name": "KWh Meter Lab IoT",
        "work_power_w": (700.0, 1900.0),
        "after_hours_power_w": (60.0, 175.0),
        "initial_kwh": 210.0000,
    },
]

DEVICES_BY_ID = {d["id"]: d for d in DEVICES}
