# Simulator Smart Energy (Tim 1 — AIR24)

Simulator resmi **4 kWh meter** (`kwh-01` s.d. `kwh-04`) untuk domain **Smart Energy** pada monorepo **Mini IoT Platform Kampus (`wanlubis/iotkampus-tim3-air24`)**.

---

## 1. Daftar Perangkat & Pemetaan Topik MQTT

| Device ID | Display Name | Gedung | Ruang | Topik Telemetri (QoS 1) |
| :--- | :--- | :--- | :--- | :--- |
| `kwh-01` | KWh Meter Ruang 3012 | `bsd-a` | `r3012` | `kampus/energy/bsd-a/r3012/kwh-01/telemetry` |
| `kwh-02` | KWh Meter Ruang 3013 | `bsd-a` | `r3013` | `kampus/energy/bsd-a/r3013/kwh-02/telemetry` |
| `kwh-03` | KWh Meter Ruang 3017 | `bsd-a` | `r3017` | `kampus/energy/bsd-a/r3017/kwh-03/telemetry` |
| `kwh-04` | KWh Meter Lab IoT | `bsd-a` | `lab-iot` | `kampus/energy/bsd-a/lab-iot/kwh-04/telemetry` |

Channel tambahan per perangkat:
- `status` (QoS 1, `retain = true`): Birth `"online"` & Last Will and Testament (LWT) `"offline"` (`kampus.status.v1`).
- `heartbeat` (QoS 0, interval 15 detik): status `"alive"`.
- `cmd` (QoS 1): perintah ganti mode dinamis (`{"command": "set_mode", "args": {"mode": "BOROS"}}`).

---

## 2. Format Payload JSON

### Telemetry (`kampus.telemetry.v1`)
```json
{
  "schema": "kampus.telemetry.v1",
  "ts": 1795057200000,
  "device_id": "kwh-01",
  "domain": "energy",
  "gedung": "bsd-a",
  "ruang": "r3012",
  "metrics": {
    "power_w": 685.4,
    "energy_kwh": 120.5009
  }
}
```
- `power_w`: Daya aktif sesaat dalam satuan **Watt (W)**.
- `energy_kwh`: Energi kumulatif **non-menurun** dalam satuan **kWh**.

### Status (`kampus.status.v1`)
```json
{
  "schema": "kampus.status.v1",
  "ts": 1795057200000,
  "device_id": "kwh-01",
  "domain": "energy",
  "gedung": "bsd-a",
  "ruang": "r3012",
  "status": "online"
}
```

---

## 3. Cara Menjalankan

### A. Via Docker Compose Monorepo (Profile `team-1`)
```bash
docker compose --profile team-1 up --build -d energy-simulator
```

### B. Lokal (Host Python)
Set kredensial MQTT sesuai `.env`:
```powershell
$env:MQTT_HOST="localhost"
$env:MQTT_PORT="1883"
$env:MQTT_USERNAME="air24_user"
$env:MQTT_PASSWORD="<isi_password_dari_.env>"

python simulators/energy/simulator.py --mode NORMAL --device all --interval 5
```

---

## 4. Injektor Gangguan (Demo Menit 8–12)

Dapat dijalankan via `inject.py` atau `inject_event.py` (keduanya identik):

| Skenario | Perintah (Standalone) | Perintah (Live ke Container via MQTT `cmd`) | Ekspektasi Rule Engine |
| :--- | :--- | :--- | :--- |
| **Pemborosan Luar Jam Kerja** | `python simulators/energy/inject.py boros -d kwh-02` | `python simulators/energy/inject.py boros -d kwh-02 --via cmd` | `WASTE_AFTER_HOURS` (`warning`) setelah `power_w > 200 W` selama **2 menit** |
| **Lonjakan Beban Tinggi** | `python simulators/energy/inject.py lonjakan -d kwh-03` | `python simulators/energy/inject.py lonjakan -d kwh-03 --via cmd` | `HIGH_LOAD` (`critical`) setelah `power_w > 3000 W` selama **1 menit** |
| **Berhenti Kirim Data (No-Data)** | `python simulators/energy/inject.py stop -d kwh-04` | `python simulators/energy/inject.py stop -d kwh-04 --via cmd` | `OFFLINE` (`critical`) setelah **60 detik** tanpa telemetry/heartbeat (tanpa LWT) |
| **Putus Mendadak (LWT)** | `python simulators/energy/inject.py crash -d kwh-01` | `python simulators/energy/inject.py crash -d kwh-01 --via cmd` | Broker terbitkan LWT `"offline"` -> `OFFLINE` (`critical`) instan |
| **Pulihkan Normal** | `Ctrl+C` lalu jalankan mode `NORMAL` | `python simulators/energy/inject.py normal -d all --via cmd` | Kondisi kembali normal & state insiden di-reset (*auto-resolve*) |

---

## 5. Unit Test
```bash
python simulators/energy/test_simulator.py
```
