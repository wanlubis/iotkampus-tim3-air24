# MQTT Integration Contract — Mini IoT Platform Kampus (AIR24)
**Wali Integrasi: Tim 3**

Dokumen ini mendefinisikan kontrak komunikasi MQTT yang mengikat ketiga domain (`energy`, `coldchain`, `air`).

---

## 1. Konvensi Penamaan Topic

Format resmi (Bagian 4.1):
```text
kampus/{domain}/{gedung}/{ruang}/{device_id}/{channel}
```

### Rincian Segmen:
| Segmen | Aturan | Nilai yang Diizinkan / Contoh |
|---|---|---|
| `domain` | Huruf kecil, tanpa spasi | `energy` \| `coldchain` \| `air` |
| `gedung` | Huruf kecil, angka, tanda hubung | `bsd-a` |
| `ruang` | Huruf kecil, angka, tanda hubung | `r3012`, `r3013`, `r3017`, `lab-iot`, `gudang-a`, `gudang-b`, `koridor-1` |
| `device_id` | Unik di seluruh kelas, pola `jenis-nn` | `kwh-01` s.d. `kwh-04`, `cc-01` s.d. `cc-03`, `aq-01` s.d. `aq-03` |
| `channel` | Satu token huruf kecil | `telemetry` \| `status` \| `heartbeat` \| `cmd` |

### QoS & Retain:
- `telemetry`: **QoS 1**, `retain = false`. Interval: ~5 detik.
- `status`: **QoS 1**, `retain = true`. Digunakan untuk Birth message (`online`) dan Last Will and Testament (LWT) (`offline`).
- `heartbeat`: **QoS 0/1**, interval: 15 detik.
- `cmd`: **QoS 1**, perintah turun dari API/operator ke simulator.

---

## 2. Skema Payload JSON

### A. Channel Telemetry (`kampus.telemetry.v1`)
Setiap data telemetry wajib menggunakan amplop standar berikut:
```json
{
  "schema": "kampus.telemetry.v1",
  "ts": 1795057200000,
  "device_id": "aq-01",
  "domain": "air",
  "gedung": "bsd-a",
  "ruang": "r3012",
  "metrics": {
    "co2_ppm": 650,
    "pm25_ugm3": 18.4,
    "noise_db": 52.0
  }
}
```

#### Metrics per Domain:
- **Air Quality (Tim 3)**:
  - `co2_ppm` (number, ppm)
  - `pm25_ugm3` (number, µg/m³)
  - `noise_db` (number, dB)
- **Smart Energy (Tim 1)**:
  - `power_w` (number, Watt)
  - `energy_kwh` (number, kWh kumulatif non-menurun)
- **Cold-Chain (Tim 2)**:
  - `temp_c` (number, °C)
  - `humidity_pct` (number, %)
  - `door_open` (boolean, true/false)
  - `battery_pct` (number, %)
  - `rssi_dbm` (number, dBm)

### B. Channel Status (`kampus.status.v1`)
Mencatat ketersediaan perangkat (Birth & LWT):
```json
{
  "schema": "kampus.status.v1",
  "ts": 1795057200000,
  "device_id": "aq-01",
  "domain": "air",
  "gedung": "bsd-a",
  "ruang": "r3012",
  "status": "online"
}
```
*Catatan:* Nilai `status` hanya boleh bernilai `"online"` atau `"offline"` (huruf kecil).

### C. Channel Command (`cmd`)
Perintah turun dari platform ke perangkat:
```json
{
  "command": "setpoint",
  "args": {
    "temp_c": 3.5
  }
}
```

---

## 3. Validasi Ingest di Node-RED
Pesan yang masuk ke broker akan diperiksa oleh Node-RED:
1. Skema harus dikenal (`kampus.telemetry.v1` atau `kampus.status.v1`).
2. Timestamp `ts` harus berupa epoch milidetik numerik.
3. Field `metrics` wajib ada dan seluruh nilainya numerik (kecuali `door_open` boolean).
4. Pesan tidak valid akan ditolak dan dicatat pada audit log.
